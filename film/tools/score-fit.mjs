// Fit the chosen Lyria take to the locked film windows -> audio/music-bed.wav (48 kHz stereo, exactly timing.json
// duration). No ducking, no voice carving (the mix does that). Only a slow, musical level arc by section, a short
// fade-in, and the final-chord fade inside s8. The music itself is not cut, re-ordered, retimed or re-pitched.
//   node tools/score-fit.mjs --take audio/music/take3-raw.wav
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const FILM = resolve(fileURLToPath(new URL("..", import.meta.url)));
const { values } = parseArgs({ options: { map: { type: "boolean" }, take: { type: "string" }, out: { type: "string", default: "audio/music-bed.wav" }, lufs: { type: "string", default: "-18" } } });
const timing = JSON.parse(readFileSync(join(FILM, "timing.json"), "utf8"));
const T = timing.duration;
const S = Object.fromEntries(timing.sections.map((s) => [s.id, s]));
const W = JSON.parse(readFileSync(join(FILM, "audio/words.json"), "utf8"));
// the film-time anchors of the arc. s6 builds at the same fractions of its narrated span as take 3 was steered
// (130 and 148 s of 114.1-165.2); the lift starts 0.4 s before the unnarrated run; the fade starts 1 s before s8's
// last word ends and the final chord rings out to the end.
const s6end = W.marks.run.start - 0.4;
const at = (f) => +(S.s6.start + f * (s6end - S.s6.start)).toFixed(3);
const A = { s1: 0, s2: S.s2.start, s3: S.s3.start, s4: S.s4.start, s5: S.s5.start, s6: S.s6.start, b2: at((130 - 114.1) / (165.2 - 114.1)), b3: at((148 - 114.1) / (165.2 - 114.1)), lift: +s6end.toFixed(3), s7: S.s7.start, s8: S.s8.start };
if (values.map) {
  // take-3 source times of the same anchors (the old 217.4 s windows it was steered to)
  const SRC = { s1: 0, s2: 18, s3: 40.3, s4: 55.7, s5: 86.9, s6: 114.1, b2: 130, b3: 148, lift: 165.2, s7: 173.6, s8: 205.1 };
  const anchors = Object.keys(A).map((k) => ({ label: k, src: SRC[k], dst: A[k] }));
  // the s8 resolution plays to the film's end (take 3 holds its chord to 224 s; use only what the window needs)
  const map = { take: "audio/music/take3-raw.wav", anchors, end: { src: Math.min(224, SRC.s8 + (T - A.s8)), dst: T } };
  writeFileSync(join(FILM, "audio/music/retime-map.json"), JSON.stringify(map, null, 1));
  console.log(JSON.stringify(map));
  process.exit(0);
}
const take = resolve(FILM, values.take);

const meanDb = (a, b) => {
  const e = spawnSync("ffmpeg", ["-hide_banner", "-ss", String(a), "-t", String(b - a), "-i", take, "-af", "ebur128", "-f", "null", "-"], { encoding: "utf8" }).stderr;
  return Number(/I:\s+(-?[\d.]+) LUFS/.exec(e.slice(e.lastIndexOf("Summary")))[1]);
};
// target loudness of each stretch, relative (the whole is normalised afterwards): the briefed arc
const s6 = A.s6, lift = A.lift;
const zones = [
  { a: 0, b: S.s3.start, target: -21, label: "s1-s2 sparse pulse" },
  { a: S.s3.start, b: S.s4.start, target: -18.5, label: "s3 harmony opens" },
  { a: S.s4.start, b: S.s5.start, target: -18.5, label: "s4 curious, light" },
  { a: S.s5.start, b: s6, target: -17, label: "s5 confident groove" },
  { a: s6, b: A.b2, target: -17.5, label: "s6 build 1" },
  { a: A.b2, b: A.b3, target: -16.5, label: "s6 build 2" },
  { a: A.b3, b: lift, target: -15.5, label: "s6 build 3" },
  { a: lift, b: S.s7.start, target: -14, label: "s6 unnarrated lift" },
  { a: S.s7.start, b: S.s8.start, target: -17, label: "s7 steady" },
  { a: S.s8.start, b: T, target: -18, label: "s8 resolve" },
];
for (const z of zones) { z.measured = meanDb(z.a, z.b); z.gain = +(z.target - z.measured).toFixed(2); }
// gain points (dB): hold each zone's gain, ramp across boundaries (2 s, 1 s into the lift, centred on the boundary)
const pts = [];
zones.forEach((z, i) => {
  const r = i === 0 ? 0 : z.label.includes("lift") ? 1.0 : 2.0;
  pts.push([Math.max(0, z.a - (i ? r / 2 : 0)), i ? zones[i - 1].gain : z.gain]);
  pts.push([z.a + (i ? r / 2 : 0), z.gain]);
});
pts.push([T, zones.at(-1).gain]);
let expr = `${pts.at(-1)[1]}`;
for (let i = pts.length - 2; i >= 0; i--) {
  const [x0, g0] = pts[i], [x1, g1] = pts[i + 1];
  const seg = x1 - x0 < 1e-3 ? `${g1}` : `${g0}+(${(g1 - g0).toFixed(3)})*(t-${x0.toFixed(3)})/${(x1 - x0).toFixed(3)}`;
  expr = `if(lt(t,${x1.toFixed(3)}),${seg},${expr})`;
}
const FADE_IN = 1.2, FADE_OUT_START = +(W.sections.s8.speech[1] - 1.0).toFixed(3); // the last chord rings into the end of the film
const chain = [
  `apad=whole_dur=${T}`, `atrim=0:${T}`, "asetpts=PTS-STARTPTS", // a re-timed take can end a few ms short: pad to the film
  `volume='pow(10,(${expr})/20)':eval=frame`,
  `afade=t=in:d=${FADE_IN}`,
  `afade=t=out:st=${FADE_OUT_START}:d=${(T - FADE_OUT_START).toFixed(3)}:curve=qsin`,
].join(",");
const tmp = join(FILM, "audio/music/_bed-shaped.wav");
const ff = (a) => execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...a]);
ff(["-i", take, "-af", chain, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", tmp]);
// one linear gain to the bed's reference loudness, 4x-oversampled peak limit at -1.5 dBFS
const I = Number(/I:\s+(-?[\d.]+) LUFS/.exec(spawnSync("ffmpeg", ["-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"], { encoding: "utf8" }).stderr.split("Summary").pop())[1]);
const g = Number(values.lufs) - I;
const out = resolve(FILM, values.out);
ff(["-i", tmp, "-af", `volume=${g.toFixed(2)}dB,aresample=192000,alimiter=limit=${Math.pow(10, -1.5 / 20).toFixed(4)}:level=false:attack=1:release=80,aresample=48000:resampler=soxr,atrim=0:${T}`, "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", out]);
const dur = Number(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out]).toString());
const report = { take: values.take, duration: dur, film: T, zones, fadeIn: FADE_IN, fadeOutStart: FADE_OUT_START, gainToRef: +g.toFixed(2), refLufs: Number(values.lufs) };
writeFileSync(join(FILM, "audio/music/fit.json"), JSON.stringify(report, null, 1));
execFileSync(process.platform === "win32" ? "cmd" : "rm", process.platform === "win32" ? ["/c", "del", tmp.replace(/\//g, "\\")] : ["-f", tmp]);
console.log(JSON.stringify(report, null, 1));
