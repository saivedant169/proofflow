"""ProofFlow film: build the render-only bundle for the Mac mini.
    python tools/bundle-mac.py            -> out/proofflow-film-render.zip
Contains exactly what HyperFrames needs to render the picture: the mount, the look, the helper, the generated
film data, every section, fonts/vendor, stills, and the audio slots. Run `node tools/sync.mjs` first.
"""
import pathlib, sys, zipfile

root = pathlib.Path(__file__).resolve().parents[1]
out = root / "out" / "proofflow-film-render.zip"
out.parent.mkdir(exist_ok=True)

files = [
    "index.html", "film.css", "film.js", "film-data.js", "hyperframes.json", "timing.json",
    "RENDER-ON-MAC.md",
]
globs = [
    "compositions/s*.html", "assets/fonts/*", "assets/vendor/*", "stills/*.png", "stills/stills.json",
    "audio/narration/s*.wav", "audio/music-bed.wav", "audio/sfx.wav", "audio/words.json",
]
missing = [f for f in files if not (root / f).exists()]
if missing:
    sys.exit(f"bundle: missing {missing}")
paths = [root / f for f in files]
for g in globs:
    paths += sorted(root.glob(g))

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in paths:
        z.write(p, p.relative_to(root).as_posix())
size = out.stat().st_size / 1e6
audio_note = "" if (root / "audio/music-bed.wav").exists() else "  (no music-bed.wav/sfx.wav yet: dry-run bundle)"
print(f"bundle: {out} {len(paths)} files {size:.1f} MB{audio_note}")
