// ProofFlow film: PROVISIONAL narration timing from research/script.md (no audio), so scenes can be built and
// checked before the real Gemini narration exists. Writes audio/narration-timing.json in the measured shape with
// "provisional": true. The real `narration-build.mjs assemble` overwrites it; scenes key to words via FILM.at, so
// they follow the real timing automatically.
//
//   node tools/provisional-narration.mjs && node tools/plan-timing.mjs && node tools/sync.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = readFileSync(join(root, "research/script.md"), "utf8");
const r3 = (v) => Math.round(v * 1000) / 1000;

const WORD = 0.31; // s per word (~140 wpm with pauses)
const SYL = 0.055; // extra per letter beyond 5
const COMMA = 0.22, STOP = 0.42, LINE = 0.55, LEAD = 0.35, TAIL = 0.3;

const sections = {};
let current = null;
for (const raw of script.split(/\r?\n/)) {
  const h = /^## (s\d) /.exec(raw);
  if (h) { current = h[1]; sections[current] = []; continue; }
  const l = /^\[(\d+[a-z])\]\s+(.+)$/.exec(raw);
  if (l && current) sections[current].push({ id: l[1], text: l[2].trim() });
}

const out = { voice: "provisional", model: "none", provisional: true, generated: new Date(0).toISOString(), sections: {} };
for (const [sid, lines] of Object.entries(sections)) {
  let t = LEAD;
  const L = {}, words = [];
  lines.forEach((line, i) => {
    if (i) t += LINE;
    const start = t;
    for (const w of line.text.split(/\s+/)) {
      const core = w.replace(/[^\p{L}\p{N}]/gu, "");
      const d = WORD + Math.max(0, core.length - 5) * SYL;
      words.push({ w, start: r3(t), end: r3(t + d * 0.85), line: line.id });
      t += d;
      if (/[.?!:]$/.test(w)) t += STOP; else if (/[,;]$/.test(w)) t += COMMA;
    }
    L[line.id] = { start: r3(start), end: r3(t), text: line.text };
  });
  const duration = r3(t + TAIL);
  out.sections[sid] = { file: `narration/${sid}.wav`, duration, speech: [LEAD, r3(t)], lines: L, words };
}
writeFileSync(join(root, "audio/narration-timing.json"), JSON.stringify(out, null, 1) + "\n");
console.log("provisional:", Object.entries(out.sections).map(([k, v]) => `${k} ${v.duration}s`).join("  "));
