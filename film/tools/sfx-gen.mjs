// Synthesizes the few subtle cues the CC0 library lacks (pure ffmpeg tones/noise, no samples):
//   node tools/sfx-gen.mjs  ->  audio/sfx-library/gen-dull-bong.wav, gen-rise-swish.wav, gen-tick-run.wav (48 kHz)
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { join, resolve } from "node:path";

const LIB = join(resolve(fileURLToPath(new URL("..", import.meta.url))), "audio/sfx-library");
const ff = (args) => execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", ...args]);
const norm = "alimiter=limit=0.7:level=false,loudnorm=I=-20:TP=-3:linear=true";

// fail-closed: dull, damped low bong (G3 with soft partials), low-passed so it reads as "stop", not "alert"
ff(["-f", "lavfi", "-i",
  "aevalsrc='0.6*sin(2*PI*196*t)*exp(-5.5*t)+0.22*sin(2*PI*392.4*t)*exp(-9*t)+0.08*sin(2*PI*589*t)*exp(-15*t)':s=48000:d=1.1",
  "-af", `afade=t=in:d=0.004,lowpass=f=1100,${norm},afade=t=out:st=0.95:d=0.15`, "-ar", "48000", "-ac", "1", join(LIB, "gen-dull-bong.wav")]);

// stale pulse travelling: soft pink-noise swish whose level and band rise, with a faint rising tone under it
ff(["-f", "lavfi", "-i", "anoisesrc=color=pink:r=48000:d=0.75:seed=7",
  "-f", "lavfi", "-i", "aevalsrc='0.08*sin(2*PI*(420*t+700*t*t))':s=48000:d=0.75",
  "-filter_complex",
  "[0:a]highpass=f=700,lowpass=f=5200,volume='pow(t/0.75,2.2)':eval=frame[n];[1:a]volume='t/0.75':eval=frame[s];" +
  `[n][s]amix=inputs=2:normalize=0,${norm},afade=t=in:d=0.05,afade=t=out:st=0.62:d=0.13`,
  "-ar", "48000", "-ac", "1", join(LIB, "gen-rise-swish.wav")]);

// HydraDB traversal: a quick run of 7 soft ticks, slightly rising in pitch, slightly accelerating
let at = 0, terms = [];
for (let i = 0; i < 7; i++) {
  const f = 2300 + i * 110, g = (0.55 - i * 0.03).toFixed(3);
  terms.push(`${g}*gte(t,${at.toFixed(3)})*sin(2*PI*${f}*(t-${at.toFixed(3)}))*exp(-260*(t-${at.toFixed(3)}))`);
  at += 0.062 - i * 0.004;
}
ff(["-f", "lavfi", "-i", `aevalsrc='${terms.join("+")}':s=48000:d=0.6`, "-af", `highpass=f=900,${norm},afade=t=out:st=0.5:d=0.1`, "-ar", "48000", "-ac", "1", join(LIB, "gen-tick-run.wav")]);
console.log("wrote gen-dull-bong.wav, gen-rise-swish.wav, gen-tick-run.wav");
