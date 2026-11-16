// Lyria RealTime (models/lyria-realtime-exp, BidiGenerateMusic over WebSocket) -> one continuous 48 kHz stereo WAV.
// The generateContent Lyria models (lyria-3.5, lyria-3-pro-preview, lyria-3-clip-preview) answer "limit: 0" on these
// free-tier keys, so the score is steered live: one session, fixed BPM/scale, weighted prompts that crossfade on a
// timeline. The key goes in the x-goog-api-key header of the WebSocket handshake (never in the URL) and is never logged.
//
//   GEMINI_KEYS_FILE=... node tools/lyria-rt.mjs --plan audio/music/plan.json --out audio/music/score-raw.wav
//   plan: { "bpm": 100, "scale": "D_MAJOR_B_MINOR", "duration": 210, "config": {...},
//           "timeline": [ { "at": 0, "prompts": [{ "text": "...", "weight": 1 }], "config": { "density": 0.3 } }, ... ],
//           "xfade": 4 }
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { parseArgs } from "node:util";
import { KeyPool, pcmToWav } from "./gemini-pool.mjs";

const { values } = parseArgs({ options: { plan: { type: "string" }, out: { type: "string" }, key: { type: "string" } } });
const plan = JSON.parse(readFileSync(values.plan, "utf8"));
const pool = new KeyPool();
const URL_WS = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateMusic";
const RATE = 48000, CH = 2, BPS = RATE * CH * 2;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// weighted prompts at time t: crossfade from the previous cue to the current one over `xfade` seconds
function promptsAt(t) {
  const tl = plan.timeline;
  let i = tl.findLastIndex((c) => c.at <= t);
  if (i < 0) i = 0;
  const cur = tl[i], prev = tl[i - 1], xf = cur.xfade ?? plan.xfade ?? 4;
  const a = prev ? Math.min(1, (t - cur.at) / xf) : 1;
  const m = new Map();
  for (const p of cur.prompts) m.set(p.text, (m.get(p.text) ?? 0) + p.weight * a);
  if (prev && a < 1) for (const p of prev.prompts) m.set(p.text, (m.get(p.text) ?? 0) + p.weight * (1 - a));
  return [...m].filter(([, w]) => w > 0.01).map(([text, weight]) => ({ text, weight: +weight.toFixed(3) }));
}
function configAt(t) {
  const tl = plan.timeline;
  let i = tl.findLastIndex((c) => c.at <= t);
  if (i < 0) i = 0;
  const c = { ...plan.config };
  for (let k = 0; k <= i; k++) Object.assign(c, tl[k].config ?? {});
  return c;
}

const k = await pool.next("lyria-realtime-exp");
const ws = new WebSocket(URL_WS, { headers: { "x-goog-api-key": k.key } });
const chunks = [];
let bytes = 0, setupDone = false, closed = null, lastCfg = "";
const notes = [];
ws.binaryType = "arraybuffer";
ws.onmessage = async (ev) => {
  const txt = typeof ev.data === "string" ? ev.data : Buffer.from(ev.data).toString("utf8");
  let msg;
  try { msg = JSON.parse(txt); } catch { return; }
  if (msg.setupComplete) setupDone = true;
  for (const c of msg.serverContent?.audioChunks ?? []) {
    const b = Buffer.from(c.data, "base64");
    chunks.push(b);
    bytes += b.length;
  }
  if (msg.filteredPrompt) notes.push({ filteredPrompt: msg.filteredPrompt });
  if (msg.warning) notes.push({ warning: msg.warning });
};
ws.onclose = (ev) => { closed = `${ev.code} ${pool.scrub(ev.reason)}`; };
ws.onerror = (ev) => { notes.push({ error: pool.scrub(ev.message ?? "ws error") }); };
await new Promise((res, rej) => { ws.onopen = res; setTimeout(() => rej(new Error("ws open timeout " + closed)), 20000); });
const send = (o) => ws.send(JSON.stringify(o));
send({ setup: { model: "models/lyria-realtime-exp" } });
for (let w = 0; !setupDone && w < 100; w++) { if (closed) throw new Error("closed: " + closed); await sleep(100); }
if (!setupDone) throw new Error("no setupComplete");
send({ musicGenerationConfig: { bpm: plan.bpm, scale: plan.scale, ...configAt(0) } });
send({ clientContent: { weightedPrompts: promptsAt(0) } });
send({ playbackControl: "PLAY" });
console.error(`session open (key #${k.id}), recording ${plan.duration}s`);
let lastPrompts = JSON.stringify(promptsAt(0));
lastCfg = JSON.stringify(configAt(0));
// steer by the generated audio clock (seconds of audio received), not wall time
while (bytes / BPS < plan.duration) {
  if (closed) { console.error("closed early: " + closed); break; }
  await sleep(250);
  const t = bytes / BPS + (plan.lookahead ?? 1.5); // the model buffers ahead; steer slightly early
  const p = JSON.stringify(promptsAt(t));
  if (p !== lastPrompts) { send({ clientContent: { weightedPrompts: JSON.parse(p) } }); lastPrompts = p; }
  const c = JSON.stringify(configAt(t));
  if (c !== lastCfg) { send({ musicGenerationConfig: { bpm: plan.bpm, scale: plan.scale, ...JSON.parse(c) } }); lastCfg = c; }
  if (Math.floor(bytes / BPS) % 15 === 0) process.stderr.write(`  ${(bytes / BPS).toFixed(1)}s\r`);
}
try { send({ playbackControl: "STOP" }); ws.close(); } catch {}
const pcm = Buffer.concat(chunks).subarray(0, Math.floor(plan.duration * RATE) * CH * 2);
mkdirSync(dirname(values.out), { recursive: true });
writeFileSync(values.out, pcmToWav(pcm, RATE, CH));
writeFileSync(values.out.replace(/\.wav$/, ".json"), JSON.stringify({ model: "lyria-realtime-exp", plan, seconds: pcm.length / BPS, notes, closed }, null, 1));
console.log(`wrote ${values.out} ${(pcm.length / BPS).toFixed(1)}s notes=${notes.length} closed=${closed}`);
process.exit(0);
