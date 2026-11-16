// Ask Gemini (audio understanding) to describe a score against the planned arc.
//   GEMINI_KEYS_FILE=... node tools/music-judge.mjs <score.wav> [--plan audio/music/plan.json]
import { execFileSync } from "node:child_process";
import { readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { KeyPool, generate } from "./gemini-pool.mjs";

const { values, positionals } = parseArgs({ allowPositionals: true, options: { plan: { type: "string" }, model: { type: "string", default: "gemini-3.8-flash" } } });
const mp3 = join(mkdtempSync(join(tmpdir(), "mj-")), "s.mp3");
execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-i", positionals[0], "-ac", "2", "-b:a", "96k", mp3]);
const plan = values.plan ? JSON.parse(readFileSync(values.plan, "utf8")) : null;
const arc = plan ? plan.timeline.map((c) => `${c.at}s: ${c.label}`).join("\n") : "";
const pool = new KeyPool();
const body = {
  contents: [{ role: "user", parts: [
    { inlineData: { mimeType: "audio/mp3", data: readFileSync(mp3).toString("base64") } },
    { text: `You are a strict film-music supervisor. This is an instrumental score for a calm, precise, optimistic product film.
Intended arc (timestamps):
${arc}
Listen to the whole track. For each arc segment, say in <=20 words what you actually hear (instruments, density, energy) and score 1-10 how well it matches the intent.
Then report: any vocals or vocal-like sounds (timestamps), any glitches/abrupt changes/artifacts (timestamps), any heavy drops or trailer clichés, whether the ending resolves on a clear final chord, and an overall score 1-10. Be concise and critical.` },
  ] }],
  generationConfig: { temperature: 0.2 },
};
const { json } = await generate(pool, values.model, body, { log: (m) => console.error(m), timeoutMs: 300000 });
console.log(json.candidates[0].content.parts.map((p) => p.text ?? "").join(""));
