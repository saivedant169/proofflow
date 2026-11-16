"""Local Whisper word times for many takes with one model load.

    python tools/whisper-words.py --model small --out words.json take1.wav take2.wav ...

Writes {"<file>": {"text": str, "duration": s, "words": [{"w", "start", "end"}]}} (times in the take's own seconds).
"""
import argparse
import json
import warnings

warnings.filterwarnings("ignore")
import whisper  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="small")
ap.add_argument("--out", required=True)
ap.add_argument("--prompt", default=None)
ap.add_argument("files", nargs="+")
a = ap.parse_args()
m = whisper.load_model(a.model)
out = {}
for f in a.files:
    audio = whisper.load_audio(f)
    r = m.transcribe(audio, language="en", word_timestamps=True, fp16=False, temperature=0.0,
                     condition_on_previous_text=False, initial_prompt=a.prompt)
    words = [{"w": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3)}
             for s in r["segments"] for w in s.get("words", [])]
    out[f] = {"text": r["text"].strip(), "duration": round(len(audio) / 16000, 3), "words": words}
    print(f, "|", r["text"].strip(), flush=True)
json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1)
