// ProofFlow film narration: one Gemini TTS take per script line, Whisper-checked, trimmed, assembled per section.
//
//   GEMINI_KEYS_FILE=<keys.json> node tools/narration-build.mjs gen      --work <scratch dir> [--voice Gacrux]
//   node tools/narration-build.mjs assemble --work <scratch dir>
//
// gen:      takes every line of research/script.md that has no passing take (max 3 tries), trims leading/trailing
//           silence to ~40 ms (internal pauses untouched), resamples to 48 kHz, runs local Whisper on the trimmed take
//           and passes it only if the spoken words equal the script (ignoring punctuation, spacing, number format).
// assemble: writes audio/narration/sN.wav (lead-in, fixed pauses, two-pass loudnorm -16 LUFS / -1.5 dBTP, linear
//           gain, no time-stretch), audio/narration/lines/<id>.wav and audio/narration-timing.json (clip seconds).
import { execFileSync, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

const FILM = resolve(fileURLToPath(new URL("..", import.meta.url)));
const PY = "C:\\Users\\user\\anaconda3\\python.exe";
const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    work: { type: "string" },
    voice: { type: "string", default: "Gacrux" },
    model: { type: "string", default: "gemini-3.8-flash-tts" },
    whisper: { type: "string", default: "small" },
    tries: { type: "string", default: "3" },
    only: { type: "string" },
    group: { type: "string" }, // max words per grouped request (0 = one request per line)
  },
});
const cmd = positionals[0];
if (!values.work || !["gen", "assemble"].includes(cmd)) throw new Error("usage: narration-build.mjs gen|assemble --work <dir>");
const WORK = resolve(values.work);
mkdirSync(join(WORK, "raw"), { recursive: true });
mkdirSync(join(WORK, "trim"), { recursive: true });

export const STYLE =
  "Style: calm, warm, credible documentary narrator; clear, quietly confident, modern; unhurried and natural, about 135 words per minute.";
const PRON = {
  ProofFlow: 'Pronunciation: "ProofFlow" is said "proof flow".',
  HydraDB: 'Pronunciation: "HydraDB" is said "Hydra D B".',
  MCP: 'Pronunciation: "MCP" is said "M C P".',
  CSV: 'Pronunciation: "CSV" is said "C S V".',
};
// silence between lines, measured from the previous line's speech end to the next line's speech onset
const PAUSE_BEFORE = { "4d": 0.7, "4e": 0.7, "6b": 0.7, "7b": 0.7 };
const SECTION_GAP = { s1: 0.8 };
const PRIMARY = "gemini-3.8-flash-tts"; // the chosen model; takes from any other model are provisional
const LEAD_IN = 0.35, GAP = 0.5, TAIL = 0.2; // lead-in to first onset; tail after last speech end

// ---------- script ----------
export function readScript() {
  const sections = {};
  let cur = null;
  for (const raw of readFileSync(join(FILM, "research/script.md"), "utf8").split(/\r?\n/)) {
    const h = /^## (s\d)\b/.exec(raw);
    if (h) { cur = sections[h[1]] = { lines: [] }; continue; }
    const m = /^\[(\d[a-z])\]\s+(.+?)\s*$/.exec(raw);
    if (m && cur) cur.lines.push({ id: m[1], text: m[2] });
  }
  return sections;
}

// ---------- normalisation ----------
const ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ");
const TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(" ");
function n2w(n) {
  if (n < 20) return ONES[n];
  if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? " " + ONES[n % 10] : "");
  if (n < 1000) return ONES[Math.floor(n / 100)] + " hundred" + (n % 100 ? " " + n2w(n % 100) : "");
  if (n < 1e6) return n2w(Math.floor(n / 1000)) + " thousand" + (n % 1000 ? " " + n2w(n % 1000) : "");
  return String(n);
}
// a token -> spoken words (lowercase letters only)
export function spoken(tok) {
  let t = tok.toLowerCase().replace(/[\u2019']/g, "'");
  let suffix = "";
  t = t.replace(/^\$(.*)$/, (_, x) => ((suffix = " dollars"), x));
  t = t.replace(/^(.*?)%(.*)$/, (_, x) => ((suffix = " percent" + suffix), x));
  t = t.replace(/(\d),(\d{3})/g, "$1$2");
  t = t.replace(/\d+(\.\d+)?/g, (num) => {
    const [i, d] = num.split(".");
    return " " + n2w(Number(i)) + (d ? " point " + [...d].map((c) => ONES[c]).join(" ") : "") + " ";
  });
  return (t + suffix).replace(/[^a-z]+/g, " ").trim();
}
const letters = (s) => s.replace(/[^a-z]/g, "");

function lev(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}
export function compare(scriptText, whisperText) {
  const sw = scriptText.split(/\s+/).map(spoken).join(" ").split(/\s+/).filter(Boolean);
  const ww = whisperText.split(/\s+/).map(spoken).join(" ").split(/\s+/).filter(Boolean);
  const exact = letters(sw.join("")) === letters(ww.join(""));
  return { exact, wordErrors: exact ? 0 : lev(sw, ww), charDist: lev(letters(sw.join("")), letters(ww.join(""))) };
}

// ---------- audio helpers ----------
const ff = (args) => execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args]);
function trim(inp, out) {
  const sr = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04:detection=peak";
  ff(["-i", inp, "-af", `${sr},areverse,${sr},areverse,aresample=48000:resampler=soxr`, "-ac", "1", "-c:a", "pcm_s16le", out]);
}
function duration(f) {
  return Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).toString().trim());
}
function whisper(files, model = values.whisper) {
  const out = join(WORK, `whisper-${Date.now()}.json`);
  const r = spawnSync(PY, [join(FILM, "tools/whisper-words.py"), "--model", model, "--prompt", "ProofFlow, HydraDB, MCP, CSV, runtime.", "--out", out, ...files], { encoding: "utf8", maxBuffer: 1 << 26 });
  if (r.status !== 0) throw new Error("whisper failed: " + r.stderr.slice(-800));
  return JSON.parse(readFileSync(out, "utf8"));
}

// ---------- state ----------
const STATE = join(WORK, "state.json");
const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { voice: values.voice, model: values.model, lines: {} };
const save = () => writeFileSync(STATE, JSON.stringify(state, null, 1));
const sections = readScript();
const allLines = Object.entries(sections).flatMap(([s, { lines }]) => lines.map((l) => ({ ...l, section: s })));

if (cmd === "gen") {
  const { KeyPool } = await import("./gemini-pool.mjs");
  const { tts } = await import("./tts-gemini.mjs");
  const pool = new KeyPool();
  const maxTries = Number(values.tries);
  const groupWords = Number(values.group ?? 0); // >0: consecutive lines of a section share one request, split at silences
  const forced = new Set((values.only ?? "").split(",").filter(Boolean));
  for (let round = 0; round < maxTries + 3; round++) {
    const todo = allLines.filter((l) => {
      const st = (state.lines[l.id] ??= { tries: [] });
      if (forced.has(l.id)) return st.tries.length < maxTries + 3;
      // work per model: a line is done for this model once it has an exact take from it
      if (st.tries.some((t) => t.exact && (t.model ?? PRIMARY) === PRIMARY)) return false; // final take exists
      const mine = st.tries.filter((t) => (t.model ?? PRIMARY) === values.model);
      return !mine.some((t) => t.exact) && mine.length < maxTries;
    });
    forced.clear();
    if (!todo.length) break;
    // requests: single lines, or runs of consecutive lines in one section up to `groupWords` words
    const idx = (x) => allLines.findIndex((y) => y.id === x.id);
    const nw = (t) => t.split(/\s+/).filter(Boolean).length;
    const reqs = [];
    for (const l of todo) {
      const last = reqs.at(-1), prev = last?.at(-1);
      if (groupWords && last && prev.section === l.section && idx(l) === idx(prev) + 1 && last.reduce((a, x) => a + nw(x.text), 0) + nw(l.text) <= groupWords) last.push(l);
      else reqs.push([l]);
    }
    console.log(`round ${round + 1}: ${todo.length} lines in ${reqs.length} requests`);
    const made = [];
    let i = 0, quotaOut = false;
    const worker = async () => {
      while (i < reqs.length) {
        const g = reqs[i++];
        const ns = g.map((l) => nextN(l.id, made));
        const tag = g.map((l, k) => `${l.id}-t${ns[k]}`).join("_");
        const raw = join(WORK, "raw", `${tag}.wav`);
        const style = g.length > 1 ? `${STYLE}\nLeave a short, natural pause between paragraphs.` : STYLE;
        try {
          const r = await tts(pool, { model: values.model, voice: values.voice, text: g.map((l) => l.text).join("\n\n"), style, out: raw, log: () => {} });
          console.log(`  ${tag} ${r.seconds.toFixed(2)}s key#${r.keyId}`);
          if (g.length === 1) {
            const tr = join(WORK, "trim", `${g[0].id}-t${ns[0]}.wav`);
            trim(raw, tr);
            made.push({ l: g[0], n: ns[0], tr });
          } else made.push(...splitGroup(g, ns, raw));
        } catch (e) {
          if (/no usable keys/.test(e.message)) quotaOut = true;
          console.log(`  ${tag} FAIL ${pool.scrub(e.message).slice(0, 200)}`);
        }
      }
    };
    await Promise.all(Array.from({ length: 6 }, worker));
    if (!made.length) break;
    const asr = whisper(made.map((m) => m.tr));
    const recheck = [];
    for (const m of made) {
      const w = asr[m.tr];
      const c = compare(m.l.text, w.text);
      const t = { model: values.model, n: m.n, file: m.tr, heard: w.text, ...c, words: w.words, duration: duration(m.tr) };
      state.lines[m.l.id].tries.push(t);
      if (!c.exact) recheck.push({ m, t });
    }
    // a mismatch heard by `small` is re-heard by `medium` before it costs a retake (small mishears, e.g. "Mrs." for "misses")
    if (recheck.length) {
      const asr2 = whisper(recheck.map((r) => r.m.tr), "medium");
      for (const { m, t } of recheck) {
        const w = asr2[m.tr], c = compare(m.l.text, w.text);
        if (c.exact) Object.assign(t, { heard: w.text, ...c, words: w.words, asr: "medium" });
        else console.log(`  ${m.l.id} t${m.n} MISMATCH (${c.wordErrors}w/${c.charDist}c): "${w.text}"`);
      }
    }
    save();
    console.log(`pool: ${pool.summary()}`);
    if (quotaOut) break;
  }
  const bad = allLines.filter((l) => !state.lines[l.id]?.tries.some((t) => t.exact && (t.model ?? PRIMARY) === values.model));
  console.log(bad.length ? `no exact take from ${values.model}: ${bad.map((l) => l.id).join(", ")}` : "all lines have an exact take");
}

function nextN(id, made) {
  return state.lines[id].tries.length + made.filter((m) => m.l.id === id).length + 1;
}

// One take of several lines -> one trimmed file per line, cut in the silence nearest each line boundary.
function splitGroup(g, ns, raw) {
  const full = raw.replace(/\.wav$/, "-48k.wav");
  ff(["-i", raw, "-af", "aresample=48000:resampler=soxr", "-ac", "1", "-c:a", "pcm_s16le", full]);
  const w = whisper([full])[full];
  const al = alignWords(g.map((l) => l.text).join(" "), w.words);
  let k = 0;
  const spans = g.map((l) => {
    const ws = al.slice(k, (k += l.text.split(/\s+/).filter(Boolean).length));
    return [ws[0].start, ws.at(-1).end];
  });
  const sd = spawnSync("ffmpeg", ["-hide_banner", "-i", full, "-af", "silencedetect=noise=-42dB:d=0.12", "-f", "null", "-"], { encoding: "utf8" }).stderr;
  const sil = [];
  for (const m of sd.matchAll(/silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)/g)) sil.push([+m[1], +m[2]]);
  const cuts = [0];
  for (let b = 0; b < g.length - 1; b++) {
    const lo = spans[b][1] - 0.3, hi = spans[b + 1][0] + 0.3;
    const cand = sil.filter(([s, e]) => e > lo && s < hi).sort((x, y) => y[1] - y[0] - (x[1] - x[0]))[0];
    cuts.push(cand ? (cand[0] + cand[1]) / 2 : (spans[b][1] + spans[b + 1][0]) / 2);
  }
  cuts.push(duration(full));
  return g.map((l, b) => {
    const piece = join(WORK, "raw", `${l.id}-t${ns[b]}-piece.wav`), tr = join(WORK, "trim", `${l.id}-t${ns[b]}.wav`);
    ff(["-i", full, "-ss", cuts[b].toFixed(3), "-to", cuts[b + 1].toFixed(3), "-c:a", "pcm_s16le", piece]);
    trim(piece, tr);
    return { l, n: ns[b], tr };
  });
}

if (cmd === "assemble") {
  const outDir = join(FILM, "audio/narration");
  mkdirSync(join(outDir, "lines"), { recursive: true });
  const timing = { voice: state.voice, model: PRIMARY, note: "lines[].model names the TTS model of each take; any line not from the primary model is provisional and will be replaced (same words; durations shift slightly).", generated: new Date().toISOString(), sections: {} };
  for (const [sid, { lines }] of Object.entries(sections)) {
    // pick: exact take (first), else lowest char distance; manual override via state.lines[id].pick
    const picks = lines.map((l) => {
      const st = state.lines[l.id];
      if (!st?.tries.length) throw new Error(`no take for ${l.id}`);
      // preference: exact take from the primary model (latest first), then exact from any model, then closest
      const t = st.pick ? st.tries.find((x) => x.n === st.pick)
        : [...st.tries].reverse().find((x) => x.exact && (x.model ?? PRIMARY) === PRIMARY) ?? st.tries.find((x) => x.exact) ?? [...st.tries].sort((a, b) => a.charDist - b.charDist)[0];
      return { l, t };
    });
    // layout on measured speech bounds: each take is cut to its audible speech (+20 ms head, +50 ms tail, short
    // fades), so residual silence/noise left by the trim never widens a gap. No time-stretch anywhere.
    mkdirSync(join(WORK, "seg"), { recursive: true });
    const HEAD = 0.02, TAILPAD = 0.05;
    const parts = [], placed = [];
    let cursor = 0, prevEnd = null;
    picks.forEach(({ l, t }, k) => {
      const b = speechBounds(t.file, t.duration, t.words);
      const c0 = Math.max(0, b.on - HEAD), c1 = Math.min(t.duration, b.off + TAILPAD);
      const seg = join(WORK, "seg", `${l.id}.wav`);
      // atrim + asetpts so the fades run on the segment's own clock (output-side -ss would leave the filter clock on
      // the take's timeline and the fade-out would land inside the speech)
      ff(["-i", t.file, "-af", `atrim=start=${c0.toFixed(4)}:end=${c1.toFixed(4)},asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st=${(c1 - c0 - 0.03).toFixed(4)}:d=0.03`, "-c:a", "pcm_s16le", seg]);
      const onAbs = k === 0 ? LEAD_IN : prevEnd + (PAUSE_BEFORE[l.id] ?? SECTION_GAP[sid] ?? GAP);
      const segStart = onAbs - (b.on - c0);
      parts.push(+(segStart - cursor).toFixed(4));
      parts.push(seg);
      placed.push({ l, t, shift: segStart - c0, onAbs, offAbs: segStart + (b.off - c0) });
      cursor = segStart + (c1 - c0);
      prevEnd = segStart + (b.off - c0);
      copyFileSync(seg, join(outDir, "lines", `${l.id}.wav`));
    });
    parts.push(+(prevEnd + TAIL - cursor).toFixed(4));
    for (const q of parts) if (typeof q === "number" && q < 0) throw new Error(`negative silence in ${sid}`);
    // concat via filter graph (anullsrc for silences), then loudnorm two-pass
    const inputs = [], labels = [];
    for (const q of parts) {
      if (typeof q === "number" && q <= 0.0005) continue;
      if (typeof q === "number") inputs.push("-f", "lavfi", "-t", q.toFixed(4), "-i", "anullsrc=r=48000:cl=mono");
      else inputs.push("-i", q);
      labels.push(`[${labels.length}:a]`);
    }
    const raw = join(WORK, `${sid}-concat.wav`);
    ff([...inputs, "-filter_complex", `${labels.join("")}concat=n=${labels.length}:v=0:a=1[o]`, "-map", "[o]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", raw]);
    const meas = spawnSync("ffmpeg", ["-hide_banner", "-i", raw, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], { encoding: "utf8" }).stderr;
    const j = JSON.parse(meas.slice(meas.lastIndexOf("{"), meas.lastIndexOf("}") + 1));
    const out = join(outDir, `${sid}.wav`);
    // one constant gain per section to -16 LUFS integrated (pass 1 measured it), then a 4x-oversampled peak limiter
    // at -1.6 dBFS that only touches the rare plosive peaks; no dynamic loudness riding.
    let gain = -16 - Number(j.input_i), k2;
    for (let pass = 0; pass < 3; pass++) {
      ff(["-i", raw, "-af", `volume=${gain.toFixed(2)}dB,aresample=192000,alimiter=limit=${Math.pow(10, -2.0 / 20).toFixed(4)}:level=false:attack=0.5:release=40,aresample=48000:resampler=soxr`, "-ac", "1", "-c:a", "pcm_s16le", out]);
      const m2 = spawnSync("ffmpeg", ["-hide_banner", "-i", out, "-af", "loudnorm=I=-16:TP=-1.5:print_format=json", "-f", "null", "-"], { encoding: "utf8" }).stderr;
      k2 = JSON.parse(m2.slice(m2.lastIndexOf("{"), m2.lastIndexOf("}") + 1));
      if (Math.abs(-16 - Number(k2.input_i)) < 0.15) break;
      gain += -16 - Number(k2.input_i); // the limiter shaved a little loudness: add it back and re-limit
    }
    const j2 = { output_i: k2.input_i, output_tp: k2.input_tp, normalization_type: `linear gain ${gain.toFixed(2)} dB + peak limit -2 dBFS (4x oversampled)` };
    const dur = duration(out);
    // words: align script words to whisper tokens by characters
    const words = [], lineTimes = {};
    for (const { l, t, shift, onAbs, offAbs } of placed) {
      // whisper times shifted into the section and clamped to the measured speech span (whisper pins starts to 0 and
      // often ends a final fricative early): first word starts at the onset, last word ends at the measured speech end
      const clamp = (x) => Math.min(offAbs, Math.max(onAbs, x));
      const ws = alignWords(l.text, t.words).map((w) => ({ w: w.w, start: clamp(w.start + shift), end: clamp(w.end + shift), line: l.id }));
      ws[0].start = onAbs;
      ws.at(-1).end = offAbs;
      for (const w of ws) { w.start = +w.start.toFixed(3); w.end = +Math.max(w.end, w.start + 0.02).toFixed(3); }
      words.push(...ws);
      lineTimes[l.id] = { start: ws[0].start, end: ws.at(-1).end, text: l.text, take: `t${t.n}`, model: t.model ?? PRIMARY, exact: t.exact };
    }
    timing.sections[sid] = {
      file: `narration/${sid}.wav`,
      duration: +dur.toFixed(3),
      speech: [words[0].start, words.at(-1).end],
      loudness: { input_i: +j.input_i, output_i: +j2.output_i, output_tp: +j2.output_tp, type: j2.normalization_type },
      lines: lineTimes,
      words,
    };
    console.log(`${sid}: ${dur.toFixed(2)}s, ${words.length} words, ${j2.normalization_type} I=${j2.output_i} TP=${j2.output_tp}`);
  }
  timing.total = +Object.values(timing.sections).reduce((a, s) => a + s.duration, 0).toFixed(3);
  writeFileSync(join(FILM, "audio/narration-timing.json"), JSON.stringify(timing, null, 1));
  console.log(`total ${timing.total}s`);
}

// audible speech span of a take, anchored on Whisper's words: TTS takes carry breaths and tiny blips in the
// "silence", so onset = end of the last >=120 ms silence (-40 dB) that starts before the first word ends, and
// offset = start of the first >=150 ms silence that begins after the last word's (often early) Whisper end.
function speechBounds(file, dur, words) {
  const e = spawnSync("ffmpeg", ["-hide_banner", "-i", file, "-af", "silencedetect=noise=-40dB:d=0.12", "-f", "null", "-"], { encoding: "utf8" }).stderr;
  const sil = [];
  for (const m of e.matchAll(/silence_start: (-?[\d.]+)|silence_end: ([\d.]+)/g)) {
    if (m[1] !== undefined) sil.push([Math.max(0, +m[1]), dur]);
    else if (sil.length) sil.at(-1)[1] = +m[2];
  }
  const w0end = words[0]?.end ?? 0.3, wNend = words.at(-1)?.end ?? dur;
  const lead = sil.filter(([st]) => st < Math.max(0.05, w0end - 0.08));
  const on = lead.length ? Math.min(lead.at(-1)[1], w0end - 0.05) : 0;
  const tail = sil.find(([st, en]) => st >= wNend - 0.15 && st > on && en - st >= 0.15);
  return { on: Math.max(0, on), off: tail ? tail[0] : dur };
}

// Map script words (truth) to Whisper token times through a character alignment of their spoken letters.
function alignWords(text, wtoks) {
  const sw = text.split(/\s+/).filter(Boolean);
  const S = [], sOwner = [];
  sw.forEach((w, k) => { for (const c of letters(spoken(w).replace(/ /g, ""))) { S.push(c); sOwner.push(k); } });
  const W = [], wTime = [];
  for (const t of wtoks) {
    const cs = letters(spoken(t.w).replace(/ /g, ""));
    [...cs].forEach((c, i) => { W.push(c); wTime.push([t.start + ((t.end - t.start) * i) / cs.length, t.start + ((t.end - t.start) * (i + 1)) / cs.length]); });
  }
  // Needleman-Wunsch
  const n = S.length, m = W.length, D = Array.from({ length: n + 1 }, () => new Int32Array(m + 1)), B = Array.from({ length: n + 1 }, () => new Uint8Array(m + 1));
  for (let i = 1; i <= n; i++) { D[i][0] = i; B[i][0] = 1; }
  for (let j = 1; j <= m; j++) { D[0][j] = j; B[0][j] = 2; }
  for (let i = 1; i <= n; i++)
    for (let j = 1; j <= m; j++) {
      const a = D[i - 1][j - 1] + (S[i - 1] === W[j - 1] ? 0 : 1), b = D[i - 1][j] + 1, c = D[i][j - 1] + 1;
      if (a <= b && a <= c) { D[i][j] = a; B[i][j] = 0; } else if (b <= c) { D[i][j] = b; B[i][j] = 1; } else { D[i][j] = c; B[i][j] = 2; }
    }
  const map = new Array(n).fill(-1);
  for (let i = n, j = m; i > 0 || j > 0; ) {
    const b = B[i][j];
    if (b === 0) { map[i - 1] = j - 1; i--; j--; } else if (b === 1) i--; else j--;
  }
  const out = sw.map((w) => ({ w, start: null, end: null }));
  map.forEach((j, i) => {
    if (j < 0) return;
    const o = out[sOwner[i]];
    if (o.start === null) o.start = wTime[j][0];
    o.end = wTime[j][1];
  });
  // words with no aligned letters: interpolate between neighbours
  for (let k = 0; k < out.length; k++) {
    if (out[k].start !== null) continue;
    const prev = out.slice(0, k).reverse().find((o) => o.end !== null)?.end ?? wtoks[0]?.start ?? 0;
    const next = out.slice(k + 1).find((o) => o.start !== null)?.start ?? prev;
    out[k].start = prev; out[k].end = Math.max(prev, next);
  }
  return out.map((o) => ({ w: o.w, start: o.start, end: Math.max(o.end, o.start + 0.02) }));
}
