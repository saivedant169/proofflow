// Gemini TTS: one request per line -> 24 kHz mono WAV. Standalone Node 24 (global fetch, no packages).
//
//   GEMINI_KEYS_FILE=<keys.json> node tools/tts-gemini.mjs --model gemini-3.8-flash-tts --voice Sulafat \
//       --style "<instruction prefix>" --out take.wav --text "Words to read."
//   GEMINI_KEYS_FILE=... node tools/tts-gemini.mjs --jobs jobs.json [--concurrency 4]
//       jobs.json: [{ "out": "...wav", "text": "...", "voice": "...", "model": "...", "style": "..." }]
//
// Keys rotate round robin per request (see gemini-pool.mjs). The style direction goes in a "# DIRECTOR'S NOTES"
// block ahead of a "# TRANSCRIPT" block, which steers the model without being read aloud.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { parseArgs } from "node:util";
import { KeyPool, generate, pcmToWav } from "./gemini-pool.mjs";

export async function tts(pool, { model, voice, text, style, out, log = console.error }) {
  // A plain "Read aloud in a calm voice: <text>" prefix IS spoken by gemini-3.8-flash-tts (Whisper caught it), and
  // systemInstruction is refused ("Developer instruction is not enabled"). A director's-notes / transcript layout
  // is honoured and not read aloud (verified with Whisper on every take).
  const prompt = style ? `# DIRECTOR'S NOTES\n${style}\n\n# TRANSCRIPT\n${text}` : text;
  const body = {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: {
      responseModalities: ["AUDIO"],
      speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } },
    },
  };
  const { json, keyId } = await generate(pool, model, body, { log });
  const part = json.candidates?.[0]?.content?.parts?.find((p) => p.inlineData?.data);
  if (!part) throw new Error(`no audio in response (finish: ${json.candidates?.[0]?.finishReason ?? "?"})`);
  const rate = Number(/rate=(\d+)/.exec(part.inlineData.mimeType ?? "")?.[1] ?? 24000);
  const pcm = Buffer.from(part.inlineData.data, "base64");
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, pcmToWav(pcm, rate));
  return { out, keyId, seconds: pcm.length / 2 / rate };
}

if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, "/").replace(/^\//, "")}` || process.argv[1]?.endsWith("tts-gemini.mjs")) {
  const { values } = parseArgs({
    options: {
      model: { type: "string", default: "gemini-3.8-flash-tts" },
      voice: { type: "string", default: "Sulafat" },
      style: { type: "string" },
      text: { type: "string" },
      out: { type: "string" },
      jobs: { type: "string" },
      concurrency: { type: "string", default: "4" },
    },
  });
  const pool = new KeyPool();
  const jobs = values.jobs
    ? JSON.parse(readFileSync(values.jobs, "utf8"))
    : [{ out: values.out, text: values.text, voice: values.voice, model: values.model, style: values.style }];
  let i = 0, failed = 0;
  const worker = async () => {
    while (i < jobs.length) {
      const j = jobs[i++];
      const job = { model: values.model, voice: values.voice, style: values.style, ...j };
      try {
        const r = await tts(pool, job);
        console.log(`ok ${r.out} ${r.seconds.toFixed(2)}s key#${r.keyId}`);
      } catch (e) {
        failed++;
        console.log(`FAIL ${job.out}: ${pool.scrub(e.message)}`);
      }
    }
  };
  await Promise.all(Array.from({ length: Math.max(1, Number(values.concurrency)) }, worker));
  console.error(`pool: ${pool.summary()}`);
  process.exit(failed ? 1 : 0);
}
