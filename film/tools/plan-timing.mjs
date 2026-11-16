// ProofFlow film: turn SOUND's measured narration (audio/narration-timing.json, clip-relative times) into
//   timing.json  — the section windows (narration length + designed air after it), and
//   audio/words.json — every word in film seconds (the contract shape FILM reads).
// Run after any new narration fit:   node tools/plan-timing.mjs   (then node tools/sync.mjs)
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => JSON.parse(readFileSync(join(root, p), "utf8"));
const r3 = (v) => Math.round(v * 1000) / 1000;

// The film's sections, in order. `tail` is air after the narration clip ends: music breaths, the unnarrated
// architecture run (s6) and the final hold (s8). Change it here, never in a scene.
const SECTIONS = [
  { id: "s1", composition: "s1-monday", title: "Monday", tail: 1.0 },
  { id: "s2", composition: "s2-problem", title: "The problem", tail: 0.9 },
  { id: "s3", composition: "s3-idea", title: "The idea", tail: 1.6 },
  { id: "s4", composition: "s4-how", title: "How it works", tail: 1.4 },
  { id: "s5", composition: "s5-product", title: "Working today", tail: 1.2 },
  { id: "s6", composition: "s6-architecture", title: "Under the hood", tail: 8.0 },
  { id: "s7", composition: "s7-results", title: "Results", tail: 1.4 },
  { id: "s8", composition: "s8-close", title: "Close", tail: 3.6 },
];

const narration = read("audio/narration-timing.json");
const timing = { version: 1, duration: 0, canvas: { width: 1920, height: 1080 }, fps: 30, outputScale: 2, sections: [] };
const words = { version: 1, unit: "film seconds", duration: 0, measured: true, sections: {}, marks: {} };

let cursor = 0;
for (const s of SECTIONS) {
  const n = narration.sections?.[s.id];
  if (!n) throw new Error(`narration-timing.json has no ${s.id}`);
  const duration = r3(Math.ceil((n.duration + s.tail) * 10) / 10); // windows on tenths of a second
  timing.sections.push({ id: s.id, composition: s.composition, file: `compositions/${s.composition}.html`, title: s.title, start: r3(cursor), duration });
  const shift = (v) => r3(cursor + v);
  const lines = {};
  for (const [k, v] of Object.entries(n.lines ?? {})) lines[k] = { start: shift(v.start), end: shift(v.end), text: v.text };
  words.sections[s.id] = {
    start: r3(cursor),
    end: shift(n.duration),
    clip: n.file.startsWith("narration/") ? n.file : `narration/${s.id}.wav`,
    speech: [shift(n.speech[0]), shift(n.speech[1])],
    text: Object.values(n.lines ?? {}).map((l) => l.text).join(" "),
    lines,
    words: n.words.map((w) => ({ w: w.w, start: shift(w.start), end: shift(w.end), line: w.line })),
  };
  cursor = r3(cursor + duration);
}
timing.duration = r3(cursor);
words.duration = timing.duration;
// Named musical/visual marks scenes may sync to.
const first = (id, line) => words.sections[id].lines[line];
words.marks = {
  name: { start: first("s3", "3a").start, end: first("s3", "3a").end },
  correction: { start: first("s4", "4d").start, end: first("s4", "4d").end },
  run: { start: words.sections.s6.end, end: r3(timing.sections[5].start + timing.sections[5].duration) },
  finalName: { start: first("s8", "8a").start, end: first("s8", "8a").end },
};
writeFileSync(join(root, "timing.json"), JSON.stringify(timing, null, 2) + "\n");
writeFileSync(join(root, "audio/words.json"), JSON.stringify(words, null, 2) + "\n");
console.log(`plan-timing: ${timing.sections.map((s) => `${s.id} ${s.start}+${s.duration}`).join("  ")}  total ${timing.duration}s`);
