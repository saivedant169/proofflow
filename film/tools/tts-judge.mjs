// Blind listening scores for TTS takes with Gemini audio understanding.
//   GEMINI_KEYS_FILE=... node tools/tts-judge.mjs --model gemini-3.8-flash --out scores.json a.wav b.wav ...
// Each take is sent alone under an anonymous label (no voice name), with the intended text, and the model
// returns JSON scores 1-10 for clarity, warmth, natural pacing and absence of artifacts.
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { KeyPool, generate } from "./gemini-pool.mjs";

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { model: { type: "string", default: "gemini-3.8-flash" }, out: { type: "string" }, texts: { type: "string" } },
});
const pool = new KeyPool();
const texts = values.texts ? JSON.parse(readFileSync(values.texts, "utf8")) : {};
const results = {};
let n = 0;
await Promise.all(
  positionals.map(async (file, i) => {
    const label = `take-${String(i + 1).padStart(2, "0")}`;
    const intended = texts[file] ? `The intended script is: "${texts[file]}"\n` : "";
    const body = {
      contents: [
        {
          role: "user",
          parts: [
            { inlineData: { mimeType: "audio/wav", data: readFileSync(file).toString("base64") } },
            {
              text:
                `You are an exacting audio director casting a narrator for a calm, warm, credible product film. ` +
                `Listen to this voice-over take (${label}). ${intended}` +
                `Rate it 1-10 on: clarity (diction, intelligibility), warmth (pleasant, human, inviting), ` +
                `pacing (natural, unhurried, ~135 wpm, no rushing or dragging), artifacts (10 = no glitches, clicks, ` +
                `robotic tones, odd prosody or mispronunciations). Be critical and use the full scale. ` +
                `Reply ONLY with JSON: {"clarity":n,"warmth":n,"pacing":n,"artifacts":n,"note":"<=20 words"}`,
            },
          ],
        },
      ],
      generationConfig: { responseMimeType: "application/json", temperature: 0.2 },
    };
    try {
      const { json } = await generate(pool, values.model, body, { log: () => {} });
      const t = json.candidates[0].content.parts.map((p) => p.text ?? "").join("");
      const s = JSON.parse(t.slice(t.indexOf("{"), t.lastIndexOf("}") + 1));
      s.mean = (s.clarity + s.warmth + s.pacing + s.artifacts) / 4;
      results[file] = s;
    } catch (e) {
      results[file] = { error: pool.scrub(e.message).slice(0, 200) };
    }
    process.stderr.write(`${++n}/${positionals.length}\r`);
  }),
);
if (values.out) writeFileSync(values.out, JSON.stringify(results, null, 1));
for (const [f, s] of Object.entries(results)) console.log(f, JSON.stringify(s));
