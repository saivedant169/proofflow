// ProofFlow effects stem: audio/sfx-cues.json -> audio/sfx.wav (exactly the film's length, 48 kHz stereo, 24-bit)
// and audio/cue-sheet.txt; writes each cue's measured gain back into audio/sfx-cues.json.
//
//   node tools/sound-sfx.mjs            (from film/)
//
// Sources are audio/sfx-library/ only (CC0, credits in research/prior-sfx-credits.txt; gen-* synthesized by
// tools/sfx-gen.mjs). Nothing is processed but a cut with a short fade, an optional filter (the thud's low-pass)
// and level. Levels are set by measurement against the narration, not by ear: a cue's loudest 400 ms and loudest
// 50 ms (K-weighted, BS.1770) both sit `under` dB (never less than `minUnder`) below what the voice reaches in
// windows of the same length (95th percentile while it speaks), and no cue's sample peak passes `peakCap` dBFS.
// Rules checked (the render fails if one breaks):
//  - never stacked: a cue starts only after the previous one has decayed (24 dB under its peak);
//  - a loud cue (under < loudUnder) never has its loud point within +-onsetGuard s of a word onset;
//  - every cue >= minUnder dB under the voice.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const FFMPEG = process.env.HYPERFRAMES_FFMPEG_PATH ?? "ffmpeg";
const SR = 48000;
const audio = new URL("../audio/", import.meta.url);
const lib = new URL("sfx-library/", audio);
const path = (url) => fileURLToPath(url);
const sheetUrl = new URL("sfx-cues.json", audio);
const sheet = JSON.parse(readFileSync(sheetUrl, "utf8"));
const words = JSON.parse(readFileSync(new URL("words.json", audio), "utf8"));
const N = Math.round(words.duration * SR);
const r2 = (v) => Math.round(v * 100) / 100;
const r3 = (v) => Math.round(v * 1000) / 1000;
const db = (v) => 10 ** (v / 20);

function decode(file, channels, filter = null) {
  const args = ["-hide_banner", "-nostats", "-i", file];
  if (filter) args.push("-af", filter);
  args.push("-ac", String(channels), "-ar", String(SR), "-f", "f32le", "-");
  const run = spawnSync(FFMPEG, args, { maxBuffer: 1 << 30 });
  if (run.status !== 0) throw new Error(`ffmpeg failed on ${file}: ${String(run.stderr).slice(-400)}`);
  return new Float32Array(run.stdout.buffer.slice(run.stdout.byteOffset, run.stdout.byteOffset + run.stdout.length));
}
const KW = [
  { b: [1.53512485958697, -2.69169618940638, 1.19839281085285], a: [-1.69065929318241, 0.73248077421585] },
  { b: [1.0, -2.0, 1.0], a: [-1.99004745483398, 0.99007225036621] },
];
function kPower(data, channels) {
  const n = data.length / channels;
  const power = new Float64Array(n);
  for (let c = 0; c < channels; c++) {
    const st = KW.map(() => [0, 0, 0, 0]);
    for (let i = 0; i < n; i++) {
      let x = data[i * channels + c];
      for (const [k, f] of KW.entries()) {
        const s = st[k];
        const y = f.b[0] * x + f.b[1] * s[0] + f.b[2] * s[1] - f.a[0] * s[2] - f.a[1] * s[3];
        s[1] = s[0];
        s[0] = x;
        s[3] = s[2];
        s[2] = y;
        x = y;
      }
      power[i] += x * x;
    }
  }
  return power;
}
/** Loudness (LUFS) of every window of `seconds`, one each 5 ms, with the window's start sample. */
function windows(power, seconds, from = 0, to = power.length) {
  const w = Math.round(seconds * SR);
  const hop = SR / 200;
  const pre = new Float64Array(power.length + 1);
  for (let i = 0; i < power.length; i++) pre[i + 1] = pre[i] + power[i];
  const out = [];
  for (let i = Math.max(0, from); i + w <= Math.min(power.length, to); i += hop)
    out.push([-0.691 + 10 * Math.log10(Math.max(0, pre[i + w] - pre[i]) / w + 1e-20), i]);
  return out;
}
const loudest = (list) => list.reduce((m, v) => (v[0] > m[0] ? v : m), [Number.NEGATIVE_INFINITY, 0]);

// ------------------------------------------------------------------------------------------- the voice's level
const voice = new Float32Array(N);
const onsets = [];
for (const [id, s] of Object.entries(words.sections)) {
  const samples = decode(path(new URL(`narration/${id}.wav`, audio)), 1);
  const at = Math.round(s.start * SR);
  for (let i = 0; i < samples.length && at + i < N; i++) voice[at + i] += samples[i];
  for (const w of s.words) onsets.push({ t: w.start, w: w.w });
}
const voicePower = kPower(voice, 1).map((p) => 2 * p); // the voice plays in both channels
const spoken = (list) => list.map((v) => v[0]).filter((v) => v > -40).sort((a, b) => a - b);
const p95 = (list) => list[Math.floor(list.length * 0.95)];
const REF = {
  momentary: r2(p95(spoken(windows(voicePower, 0.4)))),
  short: r2(p95(spoken(windows(voicePower, 0.05)))),
};

// ------------------------------------------------------------------------------------------------ the sounds
const sounds = {};
for (const [name, def] of Object.entries(sheet.sounds)) {
  let samples = decode(path(new URL(def.file, lib)), 2, def.filter ?? null);
  if (def.cut && samples.length / 2 > def.cut * SR) {
    const len = Math.round(def.cut * SR);
    const fade = Math.round(0.06 * SR);
    samples = samples.slice(0, len * 2);
    for (let i = len - fade; i < len; i++) for (let c = 0; c < 2; c++) samples[i * 2 + c] *= (len - i) / fade;
  }
  const len = samples.length / 2;
  const pad = Math.round(0.4 * SR);
  const local = new Float32Array((len + 2 * pad) * 2);
  local.set(samples, pad * 2);
  const power = kPower(local, 2);
  const m400 = loudest(windows(power, 0.4));
  const m50 = loudest(windows(power, 0.05));
  let peak = 0;
  let peakAt = 0;
  for (let i = 0; i < len; i++) {
    const v = Math.max(Math.abs(samples[i * 2]), Math.abs(samples[i * 2 + 1]));
    if (v > peak) {
      peak = v;
      peakAt = i;
    }
  }
  // the decay point: the last sample within 24 dB of the peak (the cue's audible body)
  let body = 0;
  for (let i = len - 1; i >= 0; i--)
    if (Math.max(Math.abs(samples[i * 2]), Math.abs(samples[i * 2 + 1])) > peak * db(-24)) {
      body = i;
      break;
    }
  sounds[name] = {
    ...def,
    samples,
    len,
    m400: m400[0],
    m50: m50[0],
    peakDb: 20 * Math.log10(peak),
    peakAt: peakAt / SR,
    loudAt: Math.max(0, (m50[1] - pad) / SR + 0.025), // centre of its loudest 50 ms, from the sound's start
    body: body / SR,
  };
}

// ------------------------------------------------------------------------------------------------------ the cues
const out = new Float32Array(N * 2);
const rows = [];
const problems = [];
const cues = [...sheet.cues].sort((a, b) => a.t - b.t);
let prev = null;
for (const [k, cue] of cues.entries()) {
  const snd = sounds[cue.s];
  if (!snd) throw new Error(`cue at ${cue.t}: no sound "${cue.s}"`);
  const under = cue.under ?? snd.under;
  if (under < sheet.minUnder) problems.push(`${cue.t}: under ${under} < ${sheet.minUnder}`);
  let gain = -under - Math.max(snd.m400 - REF.momentary, snd.m50 - REF.short);
  let limitedBy = snd.m400 - REF.momentary > snd.m50 - REF.short ? "400 ms" : "50 ms";
  if (snd.peakDb + gain > sheet.peakCap) {
    gain = sheet.peakCap - snd.peakDb;
    limitedBy = "peak";
  }
  const align = cue.align ?? snd.align ?? "start";
  const start = align === "end" ? cue.t - snd.len / SR : cue.t;
  const loudPoint = align === "end" ? cue.t - 0.03 : start + snd.loudAt;
  const end = start + snd.body;
  // rules
  if (prev && start < prev.end - 1e-6)
    problems.push(`${r3(cue.t)} ${cue.s} starts ${r3(prev.end - start)} s before the ${prev.s} at ${r3(prev.t)} has decayed`);
  const near = onsets.filter((o) => Math.abs(o.t - loudPoint) <= sheet.onsetGuard);
  if (under < sheet.loudUnder && near.length)
    problems.push(`${r3(cue.t)} ${cue.s} (loud) within ${sheet.onsetGuard * 1000} ms of "${near[0].w}" at ${near[0].t}`);
  // place it
  const g = db(gain);
  const s0 = Math.round(start * SR);
  for (let i = 0; i < snd.len; i++) {
    const j = s0 + i;
    if (j < 0 || j >= N) continue;
    out[j * 2] += snd.samples[i * 2] * g;
    out[j * 2 + 1] += snd.samples[i * 2 + 1] * g;
  }
  const a = Math.round((start - 0.2) * SR);
  const b = Math.round((start + snd.len / SR + 0.2) * SR);
  const voiceNear = loudest(windows(voicePower, 0.4, a, b))[0];
  const nearest = onsets.reduce((m, o) => (Math.abs(o.t - loudPoint) < Math.abs(m.t - loudPoint) ? o : m), onsets[0]);
  const row = {
    n: k + 1,
    t: r3(cue.t),
    start: r3(start),
    end: r3(start + snd.len / SR),
    s: cue.s,
    file: `audio/sfx-library/${snd.file}`,
    under,
    gainDb: r2(gain),
    peakDbfs: r2(snd.peakDb + gain),
    momentaryLufs: r2(snd.m400 + gain),
    shortLufs: r2(snd.m50 + gain),
    underVoiceDb: r2(Math.min(REF.momentary - (snd.m400 + gain), REF.short - (snd.m50 + gain))),
    limitedBy,
    nearestWordMs: Math.round((loudPoint - nearest.t) * 1000),
    voiceNearLufs: voiceNear > -45 ? r2(voiceNear) : null,
    note: cue.note,
  };
  rows.push(row);
  if (row.underVoiceDb < sheet.minUnder - 0.01) problems.push(`${row.t}: only ${row.underVoiceDb} dB under the voice`);
  prev = { t: cue.t, s: cue.s, end };
}
for (const [k, v] of Object.entries(sounds)) console.log(`sound ${k} loudAt ${r3(v.loudAt)} body ${r3(v.body)} len ${r3(v.len / SR)}`);
if (problems.length) {
  console.error(problems.join("\n"));
  throw new Error(`${problems.length} cue rule(s) broken`);
}

// --------------------------------------------------------------------------------------------- write the stem
function writeWav24(url, data, channels) {
  const frames = data.length / channels;
  const bytes = frames * channels * 3;
  const buf = Buffer.alloc(44 + bytes);
  buf.write("RIFF", 0, "ascii");
  buf.writeUInt32LE(36 + bytes, 4);
  buf.write("WAVEfmt ", 8, "ascii");
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(channels, 22);
  buf.writeUInt32LE(SR, 24);
  buf.writeUInt32LE(SR * channels * 3, 28);
  buf.writeUInt16LE(channels * 3, 32);
  buf.writeUInt16LE(24, 34);
  buf.write("data", 36, "ascii");
  buf.writeUInt32LE(bytes, 40);
  let o = 44;
  for (let i = 0; i < data.length; i++) {
    const v = Math.max(-8388608, Math.min(8388607, Math.round(data[i] * 8388607)));
    buf.writeIntLE(v, o, 3);
    o += 3;
  }
  writeFileSync(url, buf);
}
writeWav24(new URL("sfx.wav", audio), out, 2);
let stemPeak = 0;
for (const v of out) stemPeak = Math.max(stemPeak, Math.abs(v));

// the sheet keeps its authored fields, plus the measured gain of every cue
sheet.voiceReference = REF;
sheet.cues = cues.map((cue, i) => ({ ...cue, file: rows[i].file, gainDb: rows[i].gainDb, start: rows[i].start }));
writeFileSync(sheetUrl, `${JSON.stringify(sheet, null, 2)}\n`);

const pad = (v, n) => String(v).padEnd(n);
const lpad = (v, n) => String(v).padStart(n);
const lines = [
  "ProofFlow film: sound-effects cue sheet (audio/sfx.wav, 48 kHz stereo 24-bit, " + words.duration + " s)",
  "Generated by tools/sound-sfx.mjs from audio/sfx-cues.json. Times are film seconds; each cue marks one on-screen event.",
  `Voice reference (95th pct, K-weighted): 400 ms ${REF.momentary} LUFS, 50 ms ${REF.short} LUFS. Every cue sits at least ${sheet.minUnder} dB under it;`,
  `no loud cue (< ${sheet.loudUnder} dB under) lands within +-${sheet.onsetGuard * 1000} ms of a word onset; cues never overlap. ${rows.length} cues. Stem peak ${r2(20 * Math.log10(stemPeak))} dBFS.`,
  "Sources: audio/sfx-library (CC0; credits in research/prior-sfx-credits.txt; gen-* synthesized by tools/sfx-gen.mjs).",
  "",
  `${lpad("#", 3)}  ${pad("event", 8)} ${pad("start", 8)} ${pad("sound", 8)} ${lpad("gain", 7)} ${lpad("under", 6)} ${lpad("word", 6)}  file / what it marks`,
];
for (const r of rows)
  lines.push(
    `${lpad(r.n, 3)}  ${pad(r.t.toFixed(3), 8)} ${pad(r.start.toFixed(3), 8)} ${pad(r.s, 8)} ${lpad(r.gainDb.toFixed(1), 7)} ${lpad(r.underVoiceDb.toFixed(1), 6)} ${lpad(r.nearestWordMs, 6)}  ${r.file.replace("audio/sfx-library/", "")}\n${" ".repeat(43)}${r.note}`,
  );
lines.push("", "Columns: event = the on-screen moment; start = where the file begins (swishes end on the event); gain = dB applied to the file;",
  "under = dB below the voice reference (worst of 400 ms / 50 ms); word = ms from the cue's loud point to the nearest word onset.");
writeFileSync(new URL("cue-sheet.txt", audio), `${lines.join("\n")}\n`);
console.log(`REF ${JSON.stringify(REF)}  cues ${rows.length}  stem peak ${r2(20 * Math.log10(stemPeak))} dBFS`);
for (const r of rows) console.log(`${r.t}\t${r.s}\t${r.gainDb}\t${r.underVoiceDb}\t${r.limitedBy}\t${r.nearestWordMs}`);
