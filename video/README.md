# ProofFlow walkthrough

`proofflow-walkthrough.mp4` is a two-minute, narrated walkthrough made from actual approved application captures. The application values and measured results are preserved. Captions, chapter headings, selected crops, and the CSV command card are editorial presentation. This is an edited capture walkthrough, not an uninterrupted live recording.

The final file is 1920 × 1080 at 30 fps, with H.264 video, AAC mono narration, burned captions, and an optional embedded text track. It is 4.96 MB (4,964,280 bytes). Narration is generated locally using the macOS Samantha voice. No external voice service or paid API is used for rendering.

## Reproduce

From the project root on macOS, with `ffmpeg`, `ffprobe`, `say`, and Pillow installed:

```sh
.venv/bin/python video/render.py
```

`manifest.json` defines the source images, approved crops, narration, and chapter titles. The renderer requires `screens_approved: true` and rejects missing images. `.work/` contains intermediate narration and frames and is ignored by Git. The final MP4 is included in the private repository and Docker application; it is served at `/walkthrough.mp4` on the deployed app's host. The file can also be attached separately for judging.

## Evidence

- `../docs/VIDEO_SCRIPT.md` contains narration and source references.
- `render_manifest.json` contains exact duration, file size, source-image hashes, output hash, scene timings, and audio provenance.
- `media_validation.json` contains final ffprobe output; `quality_review.json` records visual, duration, audio-level, and independent narrative checks.
- `captions.srt` is the caption sidecar; `poster.jpg` is extracted from the final movie.

The benchmark is the authored 12-scenario pilot under a shared 2,048-token budget and shared Hydra-assisted executor. The exact dependency baseline ties ProofFlow; full context completes all 29 affected reports. The recorded Fable composition is identified separately from the guided browser workflow. No deployment address, upload, or submission is claimed.
