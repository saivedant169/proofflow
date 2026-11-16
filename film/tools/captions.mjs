// ProofFlow film: write audio/captions.vtt from the measured narration (audio/words.json).
//   node tools/captions.mjs
// One cue per narration line, split into chunks of at most ~42 characters (two-line limit at 21 cps is plenty),
// timed from the first word's start to the last word's end of each chunk. Soft captions only (finish.mjs muxes them).
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const words = JSON.parse(readFileSync(join(root, "audio/words.json"), "utf8"));
const MAX = 42;
const stamp = (t) => {
  const ms = Math.round(t * 1000);
  const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms % 1000).padStart(3, "0")}`;
};

const cues = [];
for (const section of Object.values(words.sections)) {
  const byLine = new Map();
  for (const w of section.words) {
    if (!byLine.has(w.line)) byLine.set(w.line, []);
    byLine.get(w.line).push(w);
  }
  for (const list of byLine.values()) {
    let chunk = [];
    const flush = () => {
      if (chunk.length) cues.push({ start: chunk[0].start, end: chunk[chunk.length - 1].end, text: chunk.map((w) => w.w).join(" ") });
      chunk = [];
    };
    for (const w of list) {
      const next = [...chunk, w].map((x) => x.w).join(" ");
      // prefer breaking after punctuation once a chunk is half full
      if (next.length > MAX) flush();
      chunk.push(w);
      if (/[.,:;?!]$/.test(w.w) && chunk.map((x) => x.w).join(" ").length > MAX / 2) flush();
    }
    flush();
  }
}
cues.sort((a, b) => a.start - b.start);
// keep each cue on screen at least 1 s, never overlapping the next
for (let i = 0; i < cues.length; i++) {
  const nextStart = cues[i + 1]?.start ?? Infinity;
  cues[i].end = Math.min(Math.max(cues[i].end + 0.25, cues[i].start + 1), nextStart - 0.04);
}
const body = "WEBVTT\n\n" + cues.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join("\n");
writeFileSync(join(root, "audio/captions.vtt"), body);
console.log(`captions: ${cues.length} cues -> audio/captions.vtt`);
