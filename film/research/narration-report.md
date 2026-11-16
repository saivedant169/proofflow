# Narration report (ProofFlow film)

## Status

- Every line of `research/script.md`, s1 through s8 ([1a] to [8c]), is narrated word for word. Whisper re-heard each assembled section and nothing is clipped.
- Files:
  - `audio/narration/s1.wav` … `s8.wav`: 48 kHz mono.
  - `audio/narration/lines/<id>.wav`: the cut take for each line.
  - `audio/narration-timing.json`: clip-relative times.
  - `node tools/plan-timing.mjs` has been run, so `timing.json` and `audio/words.json` match these files. The film total is **217.4 s**.
- **Part of the narration is provisional.**
  - Final: s1, s2 (except [2b]), s3 and [4c]–[4e]. These lines are on the chosen model, `gemini-3.8-flash-tts`.
  - Provisional: the other 27 lines, [2b], [4a] [4b] [4f] [4g] and all of s5–s8, are on `gemini-3.8-flash-lite-tts`. Each line's `model` field in `narration-timing.json` says which model made it.
  - Why: the free tier allows **10 `gemini-3.8-flash-tts` requests per project per day**, and the 11 working keys ran out partway through. Several keys seem to share projects, because the pool ran dry after about 47 requests. The quota resets at midnight Pacific (08:00 UTC).
  - To replace the provisional lines with the same voice on the primary model:
    `GEMINI_KEYS_FILE=… node tools/narration-build.mjs gen --work <scratch>/narr/build --group 34`
    then `node tools/narration-build.mjs assemble --work …`, then `node tools/plan-timing.mjs`.
    The words stay the same and the durations shift a little.

## Model

| Model | Result |
|---|---|
| `gemini-2.5-pro-preview-tts` | Not available: 429 with "limit: 0" on all 11 working keys (free tier). |
| `gemini-3.8-flash-tts` | **Chosen.** It scored best in the blind test below. |
| `gemini-3.8-flash-lite-tts` | Mean 7.25 against 8.5 for 3.8-flash with the same voice and lines. Used only as the provisional fill. |
| `gemini-3.1-flash-tts-preview` | Mean 7.1 on 2 takes; returned many generic 429s. |
| `gemini-2.5-flash-preview-tts` | 7.75 on 1 take; returned generic 429s. |

## Voice: **Gacrux** (Charon was not considered)

The audition used lines 1a, 1b and 6b on `gemini-3.8-flash-tts`. Each take was judged three ways:

- **Whisper words:** local Whisper `small` word accuracy.
- **Blind score:** `gemini-3.8-flash` listened to each take under an anonymous, shuffled label and rated it 1–10 for clarity, warmth, pacing and artifacts. The table shows the mean.
- **Pace:** words per minute inside the lines, not counting pauses.

| Voice | Whisper words | Blind score (1a / 1b / 6b) | Mean | Pace (wpm) |
|---|---|---|---|---|
| **Gacrux** | 3/3 exact | 8.75 / 8.75 / 8.75 | **8.75** | **133** |
| Achird | 3/3 | 8.75 / 7.25 / 8.75 | 8.25 | 146 |
| Iapetus | 3/3 | 6.25 / 8.25 / 8.75 | 7.75 | 143 |
| Schedar | 3/3 ("run time") | 8.5 / 6.25 / 8.0 | 7.58 | 130 |
| Sulafat | 3/3 | 7.5 / 5.5 / 7.75 | 6.92 | 126 |

Gacrux had the highest and most even score, and its pace is the closest to 135 wpm.

## Method

- **Requests.** Lines were sent one per request. The provisional fill grouped 2–3 consecutive lines of one section (34 words at most, about 8–18 s) into a request, then split the take in the silence nearest each line boundary. These short takes did not speed up. No audio was time-stretched.
- **Style direction.** A plain prefix ("Read aloud in a calm voice: …") was **spoken aloud** by 3.8-flash-tts, and `systemInstruction` is refused for this model. A `# DIRECTOR'S NOTES` block followed by a `# TRANSCRIPT` block works. Whisper checked every take. The notes leaked once, in [2b] take 1, and that take was redone.
- **Checks.** A line passes when Whisper's words equal the script, ignoring punctuation, spacing and number format: "$5,565" counts as a match for "five thousand, five hundred sixty-five dollars". If `small` heard a mismatch, `medium` listened again before a retake was spent.
  - [2d]: `small` heard "Mrs. Numbers"; `medium` heard "misses numbers", so the take was accepted.
  - [6i] take 1 said "type tools", so it was retaken.
- **Spacing**, after the lead's revision. Each take is cut to its audible speech, found with `silencedetect` at -40 dB and anchored on Whisper's words, with 20 ms before, 50 ms after and short fades. Then:
  - 0.35 s lead-in before the first line
  - 0.5 s between lines, measured from the end of one line's speech to the start of the next
  - 0.8 s between lines in s1
  - 0.7 s before [4d], [4e], [6b] and [7b]
  - 0.2 s after the last word
- **Loudness.** pass 1 measures the section, then one fixed gain per section brings it to -16 LUFS integrated, followed by a 4x-oversampled limiter at -2 dBFS. Results are -16.0 to -16.1 LUFS with true peak at or below -1.9 dBTP. Nothing rides the level up and down.
- **Word times.** Whisper `small` timed each line's take. Its tokens were mapped to the script's words by character alignment, so the script text is the source of truth and Whisper only supplies the times. The first word of each line starts at the measured speech onset, and the last word ends at the measured speech end.

## Durations (seconds, section file)

| s1 | s2 | s3 | s4 | s5 | s6 | s7 | s8 | Total |
|---|---|---|---|---|---|---|---|---|
| 16.99 | 21.35 | 13.75 | 29.75 | 25.98 | 51.50 | 30.06 | 8.69 | **198.08** |

## Tools

- `tools/gemini-pool.mjs`: round-robin key pool. A 429 moves to the next key, a daily or "limit: 0" quota retires that key for that model, and a key that fails auth is dropped. Errors are scrubbed of keys, and keys travel only in a header.
- `tools/tts-gemini.mjs`: one TTS request to a WAV file.
- `tools/tts-judge.mjs`: blind Gemini listening scores.
- `tools/whisper-words.py`: Whisper word times.
- `tools/narration-build.mjs`: `gen` and `assemble`.
