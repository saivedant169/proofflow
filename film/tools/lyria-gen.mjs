// Gemini Lyria music generation through generateContent (round-robin KeyPool, keys never logged).
//   GEMINI_KEYS_FILE=... node tools/lyria-gen.mjs --model lyria-3-pro-preview --out audio/music/seg.wav --prompt "..."
// Saves every audio part (decoded to the container its mimeType names, WAV/MP3 kept as-is, raw PCM wrapped as WAV)
// and writes <out>.json with the prompt, model, mimeTypes, text parts and any metadata the response carries.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { parseArgs } from "node:util";
import { KeyPool, generate, pcmToWav } from "./gemini-pool.mjs";

const { values } = parseArgs({
  options: {
    model: { type: "string", default: "lyria-3-pro-preview" },
    prompt: { type: "string" },
    "prompt-file": { type: "string" },
    out: { type: "string" },
    extra: { type: "string" }, // JSON merged into generationConfig (to probe options)
  },
});
const prompt = values.prompt ?? readFileSync(values["prompt-file"], "utf8");
const pool = new KeyPool();
const body = { contents: [{ role: "user", parts: [{ text: prompt }] }] };
if (values.extra) body.generationConfig = JSON.parse(values.extra);
const t0 = Date.now();
const { json, keyId } = await generate(pool, values.model, body, { log: (m) => console.error(m), timeoutMs: 600000, tries: 14 });
const parts = json.candidates?.[0]?.content?.parts ?? [];
mkdirSync(dirname(values.out), { recursive: true });
const saved = [];
parts.forEach((p, i) => {
  if (!p.inlineData) return;
  const mt = p.inlineData.mimeType ?? "";
  const buf = Buffer.from(p.inlineData.data, "base64");
  let file = values.out.replace(/\.\w+$/, "") + (i ? `-${i}` : "");
  if (/wav/.test(mt)) file += ".wav", writeFileSync(file, buf);
  else if (/mpeg|mp3/.test(mt)) file += ".mp3", writeFileSync(file, buf);
  else if (/pcm|L16/i.test(mt)) {
    const rate = Number(/rate=(\d+)/.exec(mt)?.[1] ?? 48000), ch = Number(/channels=(\d+)/.exec(mt)?.[1] ?? 2);
    file += ".wav", writeFileSync(file, pcmToWav(buf, rate, ch));
  } else file += ".bin", writeFileSync(file, buf);
  saved.push({ file, mimeType: mt, bytes: buf.length });
});
const meta = {
  model: values.model,
  prompt,
  generationConfig: body.generationConfig,
  seconds: (Date.now() - t0) / 1000,
  keyId,
  saved,
  text: parts.filter((p) => p.text).map((p) => p.text),
  finishReason: json.candidates?.[0]?.finishReason,
  modelVersion: json.modelVersion,
  usage: json.usageMetadata,
  otherFields: Object.keys(json).filter((k) => !["candidates", "usageMetadata", "modelVersion", "responseId"].includes(k)),
  candidateFields: Object.keys(json.candidates?.[0] ?? {}),
};
writeFileSync(values.out.replace(/\.\w+$/, "") + ".json", JSON.stringify(meta, null, 1));
console.log(JSON.stringify({ saved, text: meta.text.map((t) => t.slice(0, 300)), finish: meta.finishReason, cand: meta.candidateFields, other: meta.otherFields }, null, 1));
