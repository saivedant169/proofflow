# ProofFlow walkthrough

`proofflow-walkthrough.mp4` is the current two-minute narrated walkthrough. It combines actual browser captures with clearly labeled saved-evidence cards for retail v2 and the separate actual MCP-client integration. The application values and measured results are preserved. This is an edited capture walkthrough, not an uninterrupted live recording.

The file is 1920 × 1080 at 30 fps, with H.264 video, AAC mono narration, burned captions and an optional embedded text track. It is 5,151,087 bytes. Narration uses the local macOS Samantha voice; rendering invokes no external voice service or paid API.

## Reproduce

From the project root on macOS, with `ffmpeg`, `ffprobe`, `say` and Pillow installed:

```sh
.venv/bin/python video/render.py
```

`manifest.json` defines narration and approved screenshot selections. Source images resolve relative to the repository root. `evidence_extract.json` freezes the evidence-card values from the saved retail and MCP records. The renderer rejects missing screenshots and requires approved captures. `.work/` contains intermediate narration and frames and is ignored by Git. The MP4 is the release asset.

## Evidence

- [Narration and timeline](../docs/VIDEO_SCRIPT.md)
- [Retail v2 results and limits](../docs/RETAIL_V2_RESULTS.md)
- [Actual MCP-client results](../docs/MCP_AGENT_RESULTS.md)
- `render_manifest.json`: exact duration, output and source hashes, scene timings and narration provenance.
- `media_validation.json` and `quality_review.json`: media metadata and visual/audio validation scope.
- `captions.srt`: caption sidecar. `poster.jpg`: frame extracted from the film.

The complete dependency path uses 69.41% fewer evidence tokens than full context and refreshes 38/38 recoverable affected reports, while blocking 4/4 unavailable reports. The exact dependency baseline ties; every arm shares the Hydra-assisted executor. The fixed 2,048-token graph result is 8/38, and the development efficiency gate failed. The actual MCP client is one recorded authored two-row integration after a retained configuration failure, separate from the retail benchmark.

No model-cost savings, universal agent reliability, public-source access or hosting availability is claimed. The source repository remains private.
