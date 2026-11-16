// ProofFlow film: carry the render's audio through git as lossless FLAC (WAV is gitignored).
//
//   node tools/handoff-audio.mjs pack     (Windows, after the final mix)   audio/**.wav  -> audio/handoff/*.flac
//   node tools/handoff-audio.mjs unpack   (Mac, before rendering)          audio/handoff/*.flac -> the WAV paths
//
// The WAVs are the stems the composition mounts (audio/narration/s1..s8.wav, audio/music-bed.wav, audio/sfx.wav)
// and the final mix that tools/finish.mjs muxes (audio/mix.wav). FLAC keeps every sample (24-bit) and format.
// Needs ffmpeg on PATH.
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(root, "audio", "handoff");
const STEMS = [
  ...[1, 2, 3, 4, 5, 6, 7, 8].map((n) => `audio/narration/s${n}.wav`),
  "audio/music-bed.wav",
  "audio/sfx.wav",
  "audio/mix.wav",
];
const flacName = (wav) => wav.replace(/^audio\//, "").replace(/\//g, "__").replace(/\.wav$/, ".flac");
const ff = (args) => {
  const r = spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args], { stdio: "inherit" });
  if (r.status !== 0) throw new Error(`ffmpeg failed: ${args.join(" ")}`);
};
const probe = (file) =>
  spawnSync("ffprobe", ["-v", "error", "-show_entries", "stream=sample_rate,channels,bits_per_raw_sample,bits_per_sample:format=duration",
    "-of", "json", file], { encoding: "utf8" }).stdout;

const mode = process.argv[2];
if (mode === "pack") {
  mkdirSync(dir, { recursive: true });
  const manifest = {};
  for (const wav of STEMS) {
    const src = join(root, wav);
    if (!existsSync(src)) throw new Error(`missing ${wav}`);
    const dst = join(dir, flacName(wav));
    ff(["-i", src, "-c:a", "flac", "-compression_level", "8", "-sample_fmt", "s32", dst]);
    const info = JSON.parse(probe(src));
    manifest[wav] = { flac: `audio/handoff/${flacName(wav)}`, sample_rate: +info.streams[0].sample_rate,
      channels: info.streams[0].channels, bits: +(info.streams[0].bits_per_sample || info.streams[0].bits_per_raw_sample || 24),
      duration: +(+info.format.duration).toFixed(3) };
    console.log(`pack: ${wav} -> ${manifest[wav].flac}`);
  }
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
} else if (mode === "unpack") {
  const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  for (const [wav, m] of Object.entries(manifest)) {
    const dst = join(root, wav);
    mkdirSync(dirname(dst), { recursive: true });
    const fmt = m.bits > 16 ? "pcm_s24le" : "pcm_s16le";
    ff(["-i", join(root, m.flac), "-c:a", fmt, "-ar", String(m.sample_rate), "-ac", String(m.channels), dst]);
    console.log(`unpack: ${m.flac} -> ${wav}`);
  }
} else {
  console.error("usage: node tools/handoff-audio.mjs pack|unpack");
  process.exit(2);
}
