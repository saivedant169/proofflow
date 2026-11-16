# ProofFlow score

**Deliverable:** `audio/music-bed.wav` — 48 kHz stereo, 24-bit PCM, exactly the length of `timing.json` (245.8 s for the v2 narration).

- It is not ducked and has no voice carving. The mix does that.
- Loudness is -18.0 LUFS integrated, with a true peak of -1.7 dBTP.

## Model and how it was made

The three generateContent Lyria models (`lyria-3.5`, `lyria-3-pro-preview`, `lyria-3-clip-preview`) all return 429 "limit: 0" on these free-tier keys, so none of them can be used.

The score was made with **`lyria-realtime-exp`** (Lyria RealTime) instead:

- It runs as one continuous WebSocket session (`BidiGenerateMusic`, v1alpha). The key is sent in the `x-goog-api-key` handshake header.
- BPM and key were fixed for the whole session: **100 BPM, D major** (`scale: D_MAJOR_B_MINOR`).
- The music was steered live along the film's timeline. Weighted prompts crossfade over about 4 s, and `density`, `brightness` and `muteDrums` change by section (drums stay muted until s5 and come off again in s8).
- Because it is one generation, there are no joins and the music stays coherent end to end.
- The script is `tools/lyria-rt.mjs`. The full prompts and times are in `plan-take3.json`; the arc is:

| Film time (s) | Section | Prompt gist |
|---|---|---|
| 0 | s1–s2 | Dry woodblock tick on eighths, clean sine plucks, single felt-piano notes; sparse, a little unresolved |
| 20 | s2 | Adds a soft, questioning synth-bass pulse |
| 40.3 | s3 | Warm opening harmony: felt-piano chords, a pad swelling, a slow arpeggio (not a drop) |
| 55.7 | s4 | Light, curious plucked and mallet arpeggios |
| 86.9 | s5 | Confident modern groove: light crisp percussion, warm bass, clean arpeggio |
| 114.1 / 130 / 148 | s6 | Builds layer by layer: pulse and bass, then interlocking arpeggios, then steady percussion |
| 165.2 | s6, unnarrated run | Fuller lift: bright layered arpeggios, driving light percussion (restrained) |
| 173.6 | s7 | Steady, grounded groove with soft piano chords |
| 205.1 | s8 | Gentle resolution on a warm, sustained D major chord |

## Takes

Three takes were recorded. Each was checked in two ways:

- `gemini-3.8-flash` listened blind to the whole track against the arc (`tools/music-judge.mjs`).
- Every 28 s chunk was checked separately for any voice.

| Take | Result |
|---|---|
| take1 | **Rejected.** A faint spoken or whispered voice-like artifact at about 20–24 s, flagged twice. The opening also sounded muffled. |
| take2 | Scored 9.5/10, but one chunk check flagged "vocal chops" around 3–5 s. That was not confirmed, but it was not cleared either. |
| **take3** | **Chosen.** Scored 9.5/10, and all 8 chunk checks were voice-free. Its opening is dry and clean. |

## Fitting the take to the film (`tools/score-fit.mjs`)

- **What was not changed.** The take was not cut, re-ordered, time-stretched or re-pitched. It is trimmed to 217.4 s.
- **Level arc.** Lyria RealTime returns roughly constant loudness, so a slow level arc was added. Each section has a target loudness, with 2 s ramps between sections (1 s into the lift):
  - s1–s2: -21
  - s3–s4: -18.5
  - s5: -17
  - s6: -17.5, rising through -16.5 and -15.5
  - unnarrated lift: -14
  - s7: -17
  - s8: -18
- **Fades.** A 1.2 s fade-in at the start. In s8, a fade from 212.6 s to 217.4 s (the narration ends at 213.6 s) lets the final chord settle to silence at the end of the film.
- **Output.** One linear gain to -18 LUFS, then a 4x-oversampled limiter at -1.5 dBFS.
- The measured values are in `fit.json`.

## Re-fit to the v2 narration (245.8 s)

The v2 script moved every window, so take 3 was re-timed before the fit, with no new generation. Nothing was time-stretched or re-pitched.

- `node tools/score-fit.mjs --map` writes `retime-map.json`. It maps the take's steered anchors (the old section starts, the s6 build steps, the lift, s8) to their new film times from `timing.json` and `words.json`.
- `tools/score-retime.py` plays each stretch between anchors in order. It lengthens or shortens a stretch with one or two jumps: a repeat or a skip between moments whose ±2.4 s context matches (chroma, timbre and onsets). Each cut is refined on the waveform (±30 ms) and crossfaded equal-power over 80 ms.
- The 11 edits are listed in `retime.json`. Every tight anchor lands within 0.15 s: s3 -0.03 s, lift -0.01 s, s7 -0.04 s, s8 -0.14 s, end -0.02 s.
- The s6 build steps land within 0.85 s. They are only level-zone boundaries under a 4 s prompt crossfade.
- No splice shows a level step beyond the bed's own 95th percentile (2.2 dB), and none shows a click.
- `score-fit.mjs` then applies the same level arc and fades as before, now read from the new windows, and writes `fit.json`. The bed is padded to the exact film length.
- A blind `music-judge.mjs` listen of the fitted bed reported no glitches, abrupt changes or vocals. It scored 9.8/10.

## Terms and attribution

- Google's docs say Lyria RealTime is "an experimental model", that it "generates instrumental music only", and that its output "is always watermarked for identification". The watermark is SynthID, and Google describes it as imperceptible.
- No attribution requirement is stated in the API response or on the music-generation docs pages. Use falls under the Gemini API Terms of Service and the Generative AI Prohibited Use Policy.
- Suggested credit line: "Original score generated with Google Lyria RealTime (Gemini API)".
- This is **not** Scott Buckley's music. The structure is also different from the previous film: there is no drone, silence and hit; the score opens up and builds steadily.

## Files

- `take1-raw.wav`, `take2-raw.wav`, `take3-raw.wav` and their `.json` files: the raw 224 s recordings, with the plan, notes and the close status of each session.
- `plan.json` and `plan-take2.json`: the plan used for take 2.
- `plan-take3.json`: the plan used for the chosen take.
- `fit.json`: the fit report.
