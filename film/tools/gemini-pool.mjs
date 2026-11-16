// Shared Gemini client for the sound tools: a round-robin KeyPool plus a generateContent() helper.
// Keys are read ONLY at runtime from the JSON file named by the GEMINI_KEYS_FILE env var
// ({"gemini_api_keys": [...]}). A key is never printed, logged, written to disk or put in a URL:
// it travels in the x-goog-api-key header, and every error string is scrubbed before it surfaces.
import { readFileSync } from "node:fs";

const API = "https://generativelanguage.googleapis.com/v1beta/models";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class KeyPool {
  constructor(file = process.env.GEMINI_KEYS_FILE) {
    if (!file) throw new Error("set GEMINI_KEYS_FILE to the keys JSON path");
    const keys = JSON.parse(readFileSync(file, "utf8")).gemini_api_keys ?? [];
    if (!keys.length) throw new Error("no keys in GEMINI_KEYS_FILE");
    // id is a 1-based label (#1..#n) that is safe to log
    this.keys = keys.map((k, i) => ({ id: i + 1, key: k, dead: false, coolUntil: 0, exhausted: new Set() }));
    this.cursor = 0;
  }
  scrub(s) {
    let out = String(s ?? "");
    for (const k of this.keys) if (k.key) out = out.split(k.key).join("[key]");
    return out.replace(/key=[^&\s"']+/gi, "key=[key]");
  }
  alive(model) {
    return this.keys.filter((k) => !k.dead && !k.exhausted.has(model));
  }
  // next usable key, rotating round robin; waits if every live key is cooling down
  async next(model) {
    for (;;) {
      const live = this.alive(model);
      if (!live.length) throw new Error(`no usable keys left for ${model}`);
      const now = Date.now();
      for (let i = 0; i < this.keys.length; i++) {
        const k = this.keys[(this.cursor + i) % this.keys.length];
        if (k.dead || k.exhausted.has(model) || k.coolUntil > now) continue;
        this.cursor = (this.keys.indexOf(k) + 1) % this.keys.length;
        return k;
      }
      const wait = Math.max(250, Math.min(...live.map((k) => k.coolUntil)) - now);
      await sleep(Math.min(wait, 15000));
    }
  }
  summary() {
    return this.keys.map((k) => `#${k.id}:${k.dead ? "dead" : k.exhausted.size ? "exh(" + [...k.exhausted].join(",") + ")" : "ok"}`).join(" ");
  }
}

// POST models/{model}:generateContent with rotation. 429 -> next key (backoff); 401/403 auth -> drop key.
export async function generate(pool, model, body, { tries = 24, log = () => {}, timeoutMs = 180000 } = {}) {
  let last = "";
  for (let attempt = 0; attempt < tries; attempt++) {
    const k = await pool.next(model);
    let res, text;
    try {
      res = await fetch(`${API}/${model}:generateContent`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-goog-api-key": k.key },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
      text = await res.text();
    } catch (e) {
      last = pool.scrub(e.message);
      log(`key #${k.id} network error: ${last}`);
      k.coolUntil = Date.now() + 2000;
      continue;
    }
    if (res.ok) {
      const json = JSON.parse(text);
      return { json, keyId: k.id };
    }
    const msg = pool.scrub(text).slice(0, 600);
    last = `${res.status} ${msg}`;
    if (res.status === 401 || (res.status === 403 && /api[ _]?key|API_KEY|unregistered/i.test(msg))) {
      k.dead = true;
      log(`key #${k.id} dropped (${res.status})`);
    } else if (res.status === 403) {
      k.exhausted.add(model); // model-level permission refusal: this key cannot use this model
      log(`key #${k.id} 403 for ${model}`);
    } else if (res.status === 429) {
      // "limit: 0" = model not available to this key at all; daily quota = done for today
      if (/limit: 0\b|PerDay|per day/i.test(msg)) {
        k.exhausted.add(model);
        const q = /"quotaId"\s*:\s*"([^"]+)"[\s\S]*?"quotaValue"\s*:\s*"?(\d+)/.exec(msg);
        log(`key #${k.id} exhausted for ${model}${q ? ` (${q[1]} limit ${q[2]})` : ""}`);
      } else {
        const m = /retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s/.exec(msg);
        k.coolUntil = Date.now() + (m ? Number(m[1]) * 1000 : 4000 + attempt * 500);
        log(`key #${k.id} 429, cooling`);
      }
      await sleep(300);
    } else if (res.status >= 500) {
      k.coolUntil = Date.now() + 3000;
      log(`key #${k.id} ${res.status}, retrying`);
      await sleep(1000);
    } else {
      throw new Error(`${model} ${last}`);
    }
  }
  throw new Error(`${model} failed after ${tries} tries: ${last}`);
}

export function pcmToWav(pcm, rate = 24000, channels = 1, bits = 16) {
  const h = Buffer.alloc(44);
  h.write("RIFF", 0);
  h.writeUInt32LE(36 + pcm.length, 4);
  h.write("WAVE", 8);
  h.write("fmt ", 12);
  h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20);
  h.writeUInt16LE(channels, 22);
  h.writeUInt32LE(rate, 24);
  h.writeUInt32LE((rate * channels * bits) / 8, 28);
  h.writeUInt16LE((channels * bits) / 8, 32);
  h.writeUInt16LE(bits, 34);
  h.write("data", 36);
  h.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([h, pcm]);
}
