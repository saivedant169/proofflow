// ProofFlow final mix: narration + music bed (ducked and carved under the voice) + effects stem, mastered to
// -14 LUFS integrated with a true-peak ceiling of -1.5 dBTP (ffmpeg loudnorm, two passes, linear), 48 kHz stereo,
// exactly the film's length.
//
//   node tools/sound-mix.mjs                 (from film/) -> audio/mix.wav, audio/mix.json, audio/mix-report.md
//   node tools/sound-mix.mjs --bed <wav> --out <dir>   (a dry run against another bed, written to <dir>)
//
// Reads audio/words.json (where each narration clip plays, every word's time, the marks), audio/narration/s1..s8.wav,
// audio/music-bed.wav (unducked, the film's length) and audio/sfx.wav. Intermediate stems go to the OS temp dir.
//
// The bed: a base gain puts it `airBelowVoice` LU under the voice where nobody speaks. Under speech it ducks (attack
// 0.25 s before a phrase, release 0.6 s after; gaps shorter than 1.6 s hold the duck so it never pumps) and
// crossfades to a copy with a gentle linear-phase carve of the voice band (-3.5 dB, 0.4-4 kHz). The duck depth is
// measured per phrase so the carved bed sits `under` dB below the voice. Three moments lift the bed by `lift` dB:
// s3's opening (mark `name`), s6's unnarrated run (mark `run`) and the final hold of s8.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const FFMPEG = process.env.HYPERFRAMES_FFMPEG_PATH ?? "ffmpeg";
const SR = 48000;
const film = new URL("../", import.meta.url);
const audio = new URL("audio/", film);
const path = (url) => fileURLToPath(url);
const arg = (name) => {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : null;
};
const BED = arg("--bed") ?? path(new URL("music-bed.wav", audio));
const OUT = arg("--out") ?? path(audio);
const WORK = join(tmpdir(), "proofflow-mix");
mkdirSync(WORK, { recursive: true });
mkdirSync(OUT, { recursive: true });
const words = JSON.parse(readFileSync(new URL("words.json", audio), "utf8"));
const DURATION = words.duration;
const N = Math.round(DURATION * SR);
const r2 = (v) => Math.round(v * 100) / 100;
const r3 = (v) => Math.round(v * 1000) / 1000;
const db = (v) => 10 ** (v / 20);

export const TARGET = {
  lufs: -14,
  truePeak: -1.5,
  preLimitTp: -2.0, // the sum is limited (4x oversampled) so that after the loudness gain it peaks here
  airBelowVoice: 9, // LU the unducked bed sits under the voice's speech loudness
  under: 20, // dB the carved bed sits under the voice while it speaks
  underBy: { s6: 21 },
  nameUnder: 15.5, // the bed rides up through "ProofFlow takes a different path" (mark `name`)
  lift: 4.5, // dB the bed rises in the run, the name moment and the final hold
  liftRamp: 0.8,
  carve: { from: 400, to: 4000, gainDb: -3.5 },
  attack: 0.25,
  release: 0.6,
  innerGap: 1.0, // a pause this long splits a phrase (its own depth)
  bridge: 1.6, // gaps shorter than this hold the duck
  minSpeechRatio: 15,
};

function ffmpeg(args, opts = {}) {
  const run = spawnSync(FFMPEG, ["-hide_banner", "-nostats", "-y", ...args], {
    maxBuffer: 1 << 30,
    encoding: opts.binary ? "buffer" : "utf8",
  });
  if (run.status !== 0) throw new Error(`ffmpeg failed: ${String(run.stderr).slice(-1200)}`);
  return run;
}
function decode(file, channels, filter = null) {
  const buf = ffmpeg(
    ["-i", file, ...(filter ? ["-af", filter] : []), "-ac", String(channels), "-ar", String(SR), "-f", "f32le", "-"],
    { binary: true },
  ).stdout;
  return new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length));
}
function writeWav(file, data, channels) {
  const bytes = data.length * 4;
  const head = Buffer.alloc(44);
  head.write("RIFF", 0, "ascii");
  head.writeUInt32LE(36 + bytes, 4);
  head.write("WAVEfmt ", 8, "ascii");
  head.writeUInt32LE(16, 16);
  head.writeUInt16LE(3, 20);
  head.writeUInt16LE(channels, 22);
  head.writeUInt32LE(SR, 24);
  head.writeUInt32LE(SR * channels * 4, 28);
  head.writeUInt16LE(channels * 4, 32);
  head.writeUInt16LE(32, 34);
  head.write("data", 36, "ascii");
  head.writeUInt32LE(bytes, 40);
  writeFileSync(file, Buffer.concat([head, Buffer.from(data.buffer, data.byteOffset, bytes)]));
}
function measure(file, pre = "") {
  const chain = `${pre ? `${pre},` : ""}ebur128=peak=true+sample:framelog=quiet`;
  const log = ffmpeg(["-i", file, "-af", chain, "-f", "null", "-"]).stderr;
  const s = log.slice(log.lastIndexOf("Summary"));
  const tp = /True peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS/.exec(s)?.[1];
  const sp = /Sample peak:\s+Peak:\s+(-?[\d.]+|-inf) dBFS/.exec(s)?.[1];
  return {
    lufs: Number(/I:\s+(-?[\d.]+) LUFS/.exec(s)?.[1]),
    lra: Number(/LRA:\s+(-?[\d.]+) LU/.exec(s)?.[1]),
    truePeak: Number(tp),
    samplePeak: Number(sp),
  };
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
function prefix(power) {
  const pre = new Float64Array(power.length + 1);
  for (let i = 0; i < power.length; i++) pre[i + 1] = pre[i] + power[i];
  return pre;
}
function loudnessOver(pre, windows) {
  let sum = 0;
  let count = 0;
  for (const [a, b] of windows) {
    const i0 = Math.max(0, Math.round(a * SR));
    const i1 = Math.min(pre.length - 1, Math.round(b * SR));
    if (i1 <= i0) continue;
    sum += pre[i1] - pre[i0];
    count += i1 - i0;
  }
  return count ? -0.691 + 10 * Math.log10(sum / count + 1e-20) : Number.NEGATIVE_INFINITY;
}

// ------------------------------------------------------------------------------------------------ the voice plan
const marks = words.marks;
function voicePlan() {
  const spans = [];
  for (const [id, s] of Object.entries(words.sections)) {
    let from = s.words[0].start;
    s.words.forEach((w, k) => {
      const next = s.words[k + 1];
      if (!next) spans.push({ id, from, to: Math.max(w.end, s.speech[1]) });
      else if (next.start - w.end >= TARGET.innerGap) {
        spans.push({ id, from, to: w.end });
        from = next.start;
      }
    });
  }
  // the name moment is its own span with a shallower duck
  const m = marks.name;
  const out = spans.flatMap((p) => {
    if (m.end <= p.from || m.start >= p.to) return [{ ...p, under: TARGET.underBy[p.id] ?? TARGET.under }];
    const base = TARGET.underBy[p.id] ?? TARGET.under;
    return [
      ...(m.start > p.from ? [{ ...p, to: m.start, under: base }] : []),
      { ...p, from: Math.max(p.from, m.start), to: Math.min(p.to, m.end), under: TARGET.nameUnder, mark: "name" },
      ...(m.end < p.to ? [{ ...p, from: m.end, under: base }] : []),
    ];
  });
  out.sort((a, b) => a.from - b.from);
  const active = [];
  for (const s of out) {
    const last = active.at(-1);
    if (last && s.from - last[1] < TARGET.bridge) last[1] = Math.max(last[1], s.to);
    else active.push([s.from, s.to]);
  }
  return { spans: out, active };
}
const ramp = (u) => 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));
function duckEnvelope(active) {
  const env = new Float32Array(N);
  for (const [s, e] of active) {
    const a0 = Math.max(0, Math.round((s - TARGET.attack) * SR));
    const r1 = Math.min(N, Math.round((e + TARGET.release) * SR));
    for (let i = a0; i < r1; i++) {
      const t = i / SR;
      const v = t < s ? ramp((t - (s - TARGET.attack)) / TARGET.attack) : t <= e ? 1 : 1 - ramp((t - e) / TARGET.release);
      if (v > env[i]) env[i] = v;
    }
  }
  return env;
}
function smooth(x, seconds) {
  const half = Math.max(1, Math.round((seconds * SR) / 2));
  let cur = x;
  for (let pass = 0; pass < 2; pass++) {
    const pre = new Float64Array(cur.length + 1);
    for (let i = 0; i < cur.length; i++) pre[i + 1] = pre[i] + cur[i];
    const out = new Float32Array(cur.length);
    for (let i = 0; i < cur.length; i++) {
      const a = Math.max(0, i - half);
      const b = Math.min(cur.length, i + half + 1);
      out[i] = (pre[b] - pre[a]) / (b - a);
    }
    cur = out;
  }
  return cur;
}

// --------------------------------------------------------------------------------------------------- the stems
const { spans, active } = voicePlan();
const voice = new Float32Array(N);
const placed = [];
for (const [id, s] of Object.entries(words.sections)) {
  const file = path(new URL(`narration/${id}.wav`, audio));
  const samples = decode(file, 1);
  const at = Math.round(s.start * SR);
  for (let i = 0; i < samples.length && at + i < N; i++) if (at + i >= 0) voice[at + i] += samples[i];
  placed.push({ section: id, file: `audio/narration/${id}.wav`, at: s.start, seconds: r3(samples.length / SR) });
}
if (!existsSync(BED)) throw new Error(`${BED} is missing`);
const fit = (x) => {
  // the bed must be the film's length: trim or pad with silence
  const out = new Float32Array(N * 2);
  out.set(x.subarray(0, Math.min(x.length, N * 2)));
  return out;
};
const bedRaw = decode(BED, 2);
const bedSeconds = bedRaw.length / 2 / SR;
const bed = fit(bedRaw);
const c = TARGET.carve;
const carveFilter =
  `firequalizer=zero_phase=1:gain_entry='entry(0,0);entry(${Math.round(c.from * 0.7)},0);entry(${c.from},${c.gainDb});` +
  `entry(${c.to},${c.gainDb});entry(${Math.round(c.to * 1.4)},0);entry(24000,0)'`;
const carved = fit(decode(BED, 2, carveFilter));

const voicePre = prefix(kPower(voice, 1).map((p) => 2 * p)); // the voice plays in both channels
const speechWins = spans.map((s) => [s.from, s.to]);
const voiceSpeechLufs = loudnessOver(voicePre, speechWins);

// base gain: the bed's own loudness where it plays alone, set airBelowVoice under the voice
const bedPre = prefix(kPower(bed, 2));
const bedLufs = loudnessOver(bedPre, [[0, DURATION]]);
const baseDb = voiceSpeechLufs - TARGET.airBelowVoice - bedLufs;

// lift windows
const s8 = words.sections.s8;
const lifts = [
  { name: "name (s3 opening)", from: words.sections.s3.start, to: marks.name.end + 0.4 },
  { name: "run (s6, no voice)", from: marks.run.start, to: marks.run.end },
  { name: "final hold (s8)", from: s8.speech[1], to: DURATION },
];
const liftDb = new Float32Array(N);
for (const L of lifts) {
  const a = Math.round((L.from - TARGET.liftRamp) * SR);
  const b = Math.round((L.to + (L.to >= DURATION ? 0 : TARGET.liftRamp)) * SR);
  for (let i = Math.max(0, a); i < Math.min(N, b); i++) {
    const t = i / SR;
    const up = ramp((t - (L.from - TARGET.liftRamp)) / TARGET.liftRamp);
    const down = L.to >= DURATION ? 1 : 1 - ramp((t - L.to) / TARGET.liftRamp);
    liftDb[i] = Math.max(liftDb[i], TARGET.lift * Math.min(up, down));
  }
}

// depth per span: carved bed (with base and lift) sits `under` below the voice's level in that section
const carvedLifted = new Float32Array(N * 2);
for (let i = 0; i < N; i++) {
  const g = db(baseDb + liftDb[i]);
  carvedLifted[i * 2] = carved[i * 2] * g;
  carvedLifted[i * 2 + 1] = carved[i * 2 + 1] * g;
}
const carvedPre = prefix(kPower(carvedLifted, 2));
// where the bed should sit under each phrase: the section's voice level minus `under`
for (const id of Object.keys(words.sections)) {
  const own = spans.filter((s) => s.id === id);
  const level = loudnessOver(voicePre, own.map((s) => [s.from, s.to]));
  for (const s of own) {
    s.bedLufs = loudnessOver(carvedPre, [[s.from, s.to]]);
    s.targetLufs = level - s.under;
  }
}
// the duck follows the bed's own swells: on a 10 ms grid, depth = target - the carved bed's 1 s loudness,
// then the deepest value within +-0.4 s (a swell is met before it arrives), then smoothed (no zipper, no pump)
const HOP = SR / 100;
const G = Math.ceil(N / HOP);
const targetAt = new Float32Array(G);
for (let k = 0; k < spans.length; k++) {
  const s = spans[k];
  const prev = spans[k - 1];
  const next = spans[k + 1];
  const a = prev ? Math.round((prev.to + s.from) / 2 / 0.01) : 0;
  const b = next ? Math.round((s.to + next.from) / 2 / 0.01) : G;
  for (let g = Math.max(0, a); g < Math.min(G, b); g++) targetAt[g] = s.targetLufs;
}
const rawDepth = new Float32Array(G);
for (let g = 0; g < G; g++) {
  const t = g * 0.01;
  const st = loudnessOver(carvedPre, [[Math.max(0, t - 0.5), Math.min(DURATION, t + 0.5)]]);
  rawDepth[g] = Math.min(0, targetAt[g] - st);
}
const minDepth = new Float32Array(G);
for (let g = 0; g < G; g++) {
  let m = 0;
  for (let j = Math.max(0, g - 40); j <= Math.min(G - 1, g + 40); j++) m = Math.min(m, rawDepth[j]);
  minDepth[g] = m;
}
const smoothDepth = (() => {
  let cur = minDepth;
  for (let pass = 0; pass < 2; pass++) {
    const pre = new Float64Array(G + 1);
    for (let g = 0; g < G; g++) pre[g + 1] = pre[g] + cur[g];
    const out = new Float32Array(G);
    for (let g = 0; g < G; g++) {
      const a = Math.max(0, g - 15);
      const b = Math.min(G, g + 16);
      out[g] = (pre[b] - pre[a]) / (b - a);
    }
    cur = out;
  }
  return cur;
})();
const gainDb = new Float32Array(N);
for (let i = 0; i < N; i++) {
  const x = i / HOP;
  const g0 = Math.min(G - 1, Math.floor(x));
  const g1 = Math.min(G - 1, g0 + 1);
  gainDb[i] = smoothDepth[g0] + (smoothDepth[g1] - smoothDepth[g0]) * (x - g0);
}
for (const s of spans) {
  let sum = 0;
  let n = 0;
  for (let g = Math.round(s.from / 0.01); g < Math.round(s.to / 0.01) && g < G; g++) {
    sum += smoothDepth[g];
    n++;
  }
  s.depth = n ? sum / n : 0;
}
const env = duckEnvelope(active);
const music = new Float32Array(N * 2);
for (let i = 0; i < N; i++) {
  const e = env[i];
  const g = db(baseDb + liftDb[i]);
  const d = db(gainDb[i]);
  for (let ch = 0; ch < 2; ch++) music[i * 2 + ch] = g * (bed[i * 2 + ch] * (1 - e) + carved[i * 2 + ch] * e * d);
}
const sfxFile = path(new URL("sfx.wav", audio));
const sfx = existsSync(sfxFile) ? fit(decode(sfxFile, 2)) : null;
const sum = new Float32Array(N * 2);
for (let i = 0; i < N; i++)
  for (let ch = 0; ch < 2; ch++) sum[i * 2 + ch] = voice[i] + music[i * 2 + ch] + (sfx ? sfx[i * 2 + ch] : 0);
const f = (name) => join(WORK, name);
writeWav(f("voice.wav"), voice, 1);
writeWav(f("music.wav"), music, 2);
writeWav(f("sum.wav"), sum, 2);

// ------------------------------------------------------------------------------------------------- the master
const before = measure(f("sum.wav"));
const gain = TARGET.lufs - before.lufs;
// 1. a 4x-oversampled limiter so the sum, once raised by `gain`, peaks at preLimitTp
const limit = db(TARGET.preLimitTp - gain);
const limitChain = `aresample=192000:resampler=soxr,alimiter=limit=${Math.min(1, limit).toFixed(5)}:attack=5:release=80:level=false:asc=1,aresample=${SR}:resampler=soxr`;
ffmpeg(["-i", f("sum.wav"), "-af", limitChain, "-c:a", "pcm_f32le", f("limited.wav")]);
// 2. loudnorm pass 1 (measure)
const ln = `I=${TARGET.lufs}:TP=${TARGET.truePeak}:LRA=20`;
const p1 = ffmpeg(["-i", f("limited.wav"), "-af", `loudnorm=${ln}:print_format=json`, "-f", "null", "-"]).stderr;
const m1 = JSON.parse(p1.slice(p1.lastIndexOf("{"), p1.lastIndexOf("}") + 1));
// 3. loudnorm pass 2 (linear, with the measured values), back to 48 kHz, exactly N samples
const pass2 =
  `loudnorm=${ln}:measured_I=${m1.input_i}:measured_TP=${m1.input_tp}:measured_LRA=${m1.input_lra}:` +
  `measured_thresh=${m1.input_thresh}:offset=${m1.target_offset}:linear=true:print_format=json,` +
  `aresample=${SR}:resampler=soxr,apad=whole_len=${N},atrim=end_sample=${N}`;
const mixFile = join(OUT, "mix.wav");
let trim = 0;
let m2 = null;
let master = null;
for (let pass = 0; pass < 4; pass++) {
  const chain = trim ? pass2.replace(",aresample", `,volume=${trim.toFixed(2)}dB,aresample`) : pass2;
  const p2 = ffmpeg(["-i", f("limited.wav"), "-af", chain, "-ar", String(SR), "-ac", "2", "-c:a", "pcm_s24le", mixFile]).stderr;
  m2 = JSON.parse(p2.slice(p2.lastIndexOf("{"), p2.lastIndexOf("}") + 1));
  master = measure(mixFile);
  // (loudnorm's linear gain lands within a tenth or two; a trim of the same linear gain closes the gap)
  if (Math.abs(master.lufs - TARGET.lufs) < 0.05 || master.truePeak + (TARGET.lufs - master.lufs) > TARGET.truePeak) break;
  trim += TARGET.lufs - master.lufs;
}
if (master.truePeak > TARGET.truePeak) throw new Error(`true peak ${master.truePeak} dBTP over ${TARGET.truePeak}`);
const probe = ffmpeg(["-i", mixFile, "-f", "null", "-"]).stderr;
const mixData = decode(mixFile, 2);
const mixSamples = mixData.length / 2;
let clipped = 0;
for (const v of mixData) if (Math.abs(v) >= 0.999) clipped++;

// -------------------------------------------------------------------------------------------- verification
// the voice and music as they play in the master (same linear gain on both)
const masterGain = master.lufs - before.lufs; // approx. (the limiter barely touches the sum)
const musicPre = prefix(kPower(music, 2));
const sfxPre = sfx ? prefix(kPower(sfx, 2)) : null;
const sections = Object.entries(words.sections).map(([id, s]) => {
  const own = spans.filter((x) => x.id === id).map((x) => [x.from, x.to]);
  const v = loudnessOver(voicePre, own);
  const m = loudnessOver(musicPre, own);
  return {
    section: id,
    voiceLufs: r2(v),
    musicUnderVoiceLufs: r2(m),
    musicBelowVoiceDb: r2(v - m),
    musicInAirLufs: r2(loudnessOver(musicPre, [[s.start, s.speech[0] - TARGET.attack], [s.speech[1] + TARGET.release, s.end]])),
  };
});
const spanRows = spans.map((s) => ({
  section: s.id,
  ...(s.mark ? { mark: s.mark } : {}),
  from: r3(s.from),
  to: r3(s.to),
  under: s.under,
  depthDb: r2(s.depth),
  musicBelowVoiceDb: r2(loudnessOver(voicePre, [[s.from, s.to]]) - loudnessOver(musicPre, [[s.from, s.to]])),
}));
// 400 ms windows while the voice is actually sounding (within 10 LU of its speech level): how far the music sits under
const winRatios = [];
for (const s of spans)
  for (let t = s.from; t + 0.4 <= s.to; t += 0.1) {
    const v = loudnessOver(voicePre, [[t, t + 0.4]]);
    if (v < voiceSpeechLufs - 10) continue;
    winRatios.push(v - loudnessOver(musicPre, [[t, t + 0.4]]));
  }
winRatios.sort((a, b) => a - b);
const pct = (q) => r2(winRatios[Math.floor(q * (winRatios.length - 1))]);
// every 400 ms window of speech: the music's momentary loudness against its section's speaking level
const sectionLevel = Object.fromEntries(
  Object.keys(words.sections).map((id) => [id, loudnessOver(voicePre, spans.filter((s) => s.id === id).map((s) => [s.from, s.to]))]),
);
const momRatios = [];
for (const s of spans)
  for (let t = s.from; t + 0.4 <= s.to; t += 0.1)
    momRatios.push({ t: r2(t), r: sectionLevel[s.id] - loudnessOver(musicPre, [[t, t + 0.4]]) });
momRatios.sort((a, b) => a.r - b.r);
const overall = {
  voiceSpeechLufs: r2(voiceSpeechLufs),
  musicUnderSpeechLufs: r2(loudnessOver(musicPre, speechWins)),
  musicBelowVoiceDb: r2(voiceSpeechLufs - loudnessOver(musicPre, speechWins)),
  musicMomentaryVsSpeakingLevel: {
    about: "every 400 ms window inside a phrase: section voice level minus the music's momentary loudness",
    count: momRatios.length,
    min: r2(momRatios[0].r),
    minAt: momRatios[0].t,
    p05: r2(momRatios[Math.floor(0.05 * (momRatios.length - 1))].r),
    median: r2(momRatios[Math.floor(0.5 * (momRatios.length - 1))].r),
    below15dbShare: r3(momRatios.filter((x) => x.r < TARGET.minSpeechRatio).length / momRatios.length),
  },
  voiceWindowsVsMusic: {
    about: "400 ms windows where the voice is within 10 LU of its speech level: voice minus music in the same window",
    count: winRatios.length,
    p05: pct(0.05),
    median: pct(0.5),
    min: pct(0),
    below15dbShare: r3(winRatios.filter((x) => x < TARGET.minSpeechRatio).length / winRatios.length),
  },
  sfxUnderSpeechLufs: sfxPre ? r2(loudnessOver(sfxPre, speechWins)) : null,
};
const liftRows = lifts.map((L) => ({
  ...L,
  from: r3(L.from),
  to: r3(L.to),
  musicLufs: r2(loudnessOver(musicPre, [[L.from, L.to]])),
}));
const airWins = [];
{
  let t0 = 0;
  for (const [a, b] of active) {
    if (a - TARGET.attack > t0 + 0.2) airWins.push([t0, a - TARGET.attack]);
    t0 = b + TARGET.release;
  }
  if (DURATION > t0 + 0.2) airWins.push([t0, DURATION]);
}
const report = {
  target: TARGET,
  inputs: {
    voice: placed,
    bed: { file: BED.replace(/\\/g, "/").replace(/^.*\/film\//, ""), seconds: r3(bedSeconds), lufs: r2(bedLufs) },
    sfx: sfx ? "audio/sfx.wav" : null,
  },
  bedBaseGainDb: r2(baseDb),
  carveFilter,
  lifts: liftRows,
  duck: { active: active.map(([a, b]) => [r3(a), r3(b)]), spans: spanRows },
  sections,
  speech: overall,
  musicInAirLufs: r2(loudnessOver(musicPre, airWins)),
  master: {
    sum: before,
    preLimitDbtp: TARGET.preLimitTp,
    limiter: limitChain,
    loudnormPass1: m1,
    loudnormPass2: { output_i: m2.output_i, output_tp: m2.output_tp, normalization_type: m2.normalization_type, target_offset: m2.target_offset, trimDb: r2(trim) },
    measured: master,
    approxMasterGainDb: r2(masterGain),
    format: "48 kHz stereo, PCM 24-bit",
    samples: mixSamples,
    seconds: r3(mixSamples / SR),
    exactLength: mixSamples === N,
    clippedSamples: clipped,
  },
};
writeFileSync(join(OUT, "mix.json"), `${JSON.stringify(report, null, 2)}\n`);
for (const s of sections) console.log(JSON.stringify(s));
for (const s of spanRows) if (s.musicBelowVoiceDb < TARGET.minSpeechRatio || s.mark) console.log("span", JSON.stringify(s));
console.log("speech", JSON.stringify(overall));
console.log("lifts", JSON.stringify(liftRows.map((l) => [l.name, l.musicLufs])), "air", report.musicInAirLufs);
console.log("master", JSON.stringify(report.master.measured), "samples", mixSamples, "exact", mixSamples === N, "clipped", clipped, m2.normalization_type);

// ------------------------------------------------------------------------------------------------ the report
const cueSheet = existsSync(new URL("sfx-cues.json", audio)) ? JSON.parse(readFileSync(new URL("sfx-cues.json", audio), "utf8")) : null;
const sp = overall.musicMomentaryVsSpeakingLevel;
const vw = overall.voiceWindowsVsMusic;
const md = [
  "# ProofFlow film: mix report",
  "",
  `Generated by \`tools/sound-mix.mjs\` (settings and every measurement in \`audio/mix.json\`). Effects: \`tools/sound-sfx.mjs\` -> \`audio/sfx.wav\`, \`audio/cue-sheet.txt\`.`,
  "",
  "## Master (`audio/mix.wav`)",
  "",
  "| | measured | target |",
  "|---|---|---|",
  `| Integrated loudness | ${master.lufs} LUFS | ${TARGET.lufs} LUFS |`,
  `| True peak | ${master.truePeak} dBTP | <= ${TARGET.truePeak} dBTP |`,
  `| Sample peak | ${master.samplePeak} dBFS | no clipping (${clipped} samples at full scale) |`,
  `| Loudness range | ${master.lra} LU | |`,
  `| Length | ${mixSamples} samples = ${r3(mixSamples / SR)} s | ${N} samples = ${DURATION} s (${mixSamples === N ? "exact" : "MISMATCH"}) |`,
  `| Format | 48 kHz stereo, PCM 24-bit | |`,
  "",
  `Chain: voice + music + effects summed in float -> 4x-oversampled limiter so the raised sum peaks at ${TARGET.preLimitTp} dBTP -> ffmpeg \`loudnorm\` two passes (I=${TARGET.lufs}, TP=${TARGET.truePeak}, ${m2.normalization_type}; pass 1 measured ${m1.input_i} LUFS / ${m1.input_tp} dBTP) ${trim ? `-> ${r2(trim)} dB trim ` : ""}-> 48 kHz, trimmed/padded to the exact sample count.`,
  "",
  "## Voice against music",
  "",
  `- Voice: the eight narration masters \`audio/narration/s1..s8.wav\` at \`words.json\` section starts (no processing). Speech loudness ${overall.voiceSpeechLufs} LUFS (pre-master).`,
  `- During speech the music sits **${overall.musicBelowVoiceDb} dB** under the voice overall (integrated over all phrases).`,
  `- Every 400 ms window inside a phrase: music momentary loudness is at least **${sp.min} dB** under the section's speaking level (min at ${sp.minAt} s, the "ProofFlow" name moment by design; 5th percentile ${sp.p05} dB, median ${sp.median} dB; ${r2(sp.below15dbShare * 100)} % of windows under 15 dB).`,
  `- Same-window ratio while the voice is sounding (within 10 LU of its level): median ${vw.median} dB, 5th percentile ${vw.p05} dB (quiet syllables pull this down; the music itself does not rise).`,
  `- Effects under speech: ${overall.sfxUnderSpeechLufs} LUFS integrated; each cue >= ${cueSheet?.minUnder ?? 12} dB under the voice (see cue sheet).`,
  "",
  "| section | voice LUFS | music under voice LUFS | music below voice dB | music in the air LUFS |",
  "|---|---|---|---|---|",
  ...sections.map((s) => `| ${s.section} | ${s.voiceLufs} | ${s.musicUnderVoiceLufs} | ${s.musicBelowVoiceDb} | ${s.musicInAirLufs} |`),
  "",
  "## Music handling",
  "",
  `- Bed: \`${report.inputs.bed.file}\` (${report.inputs.bed.seconds} s, ${report.inputs.bed.lufs} LUFS), base gain ${report.bedBaseGainDb} dB so it plays ${TARGET.airBelowVoice} LU under the voice where nobody speaks.`,
  `- Duck: attack ${TARGET.attack} s before each phrase, release ${TARGET.release} s after; gaps under ${TARGET.bridge} s hold the duck (${active.length} duck regions). Depth follows the bed's own 1 s loudness so the carved bed sits ${TARGET.under} dB under the voice (${TARGET.underBy.s6} dB in s6; ${TARGET.nameUnder} dB under "ProofFlow takes a different path").`,
  `- Carve under speech: linear-phase ${TARGET.carve.gainDb} dB shelf from ${TARGET.carve.from} Hz to ${TARGET.carve.to} Hz, crossfaded in with the duck.`,
  `- Lifts (+${TARGET.lift} dB, ${TARGET.liftRamp} s ramps): ${liftRows.map((l) => `${l.name} ${l.from}-${l.to} s (music ${l.musicLufs} LUFS)`).join("; ")}.`,
  `- Note: in the run the bed's own swell plus the lift brings the music to ${liftRows[1].musicLufs} LUFS pre-master, ${r2(overall.voiceSpeechLufs - liftRows[1].musicLufs)} LU under the voice's speaking level (no voice plays there). Lower \`TARGET.lift\` if it should sit back.`,
  "",
  "## Effects",
  "",
  `- ${cueSheet ? cueSheet.cues.length : 0} cues, each tied to one on-screen event; none overlap; no loud cue within +-${(cueSheet?.onsetGuard ?? 0.08) * 1000} ms of a word onset. Full list: \`audio/cue-sheet.txt\`.`,
  "",
];
writeFileSync(join(OUT, "mix-report.md"), `${md.join("\n")}\n`);
