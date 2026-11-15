# ProofFlow walkthrough

`proofflow-walkthrough.mp4` is the two-minute narrated walkthrough. It opens with browser CSV preview and report creation, switches explicitly to a separate guided correction flow, then shows an audited saved model comparison and separate actual MCP-client evidence. This is an edited walkthrough from actual browser captures and saved evidence cards. It does not show a live model.

The file is 1920 × 1080 at 30 fps, with H.264 video, AAC mono narration, burned captions and an optional embedded text track. Narration uses the local macOS Samantha voice; rendering invokes no external voice service or paid API.

## Reproduce

From the project root on macOS with `ffmpeg`, `ffprobe`, `say` and Pillow installed:

```sh
.venv/bin/python video/extract_evidence.py
.venv/bin/python video/render.py
```

`manifest.json` defines the narration, original scene slots and approved screenshot selections. `evidence_extract.json` freezes values from the recorded audits and earlier deterministic limit. `.work/` holds intermediate media and is ignored by Git.

## Evidence

- [Narration and timeline](../docs/VIDEO_SCRIPT.md)
- [Audited model comparison](../docs/MODEL_COMPARISON_RESULTS.md)
- [Earlier deterministic retail results and limits](../docs/RETAIL_V2_RESULTS.md)
- [Actual MCP-client results](../docs/MCP_AGENT_RESULTS.md)
- [Local Docker delivery](../evidence/video_delivery_v4.json): exact file hash, video MIME type, and matching HTTP partial content.
- `render_manifest.json`, `media_validation.json` and `quality_review.json`: asset hashes, timings and technical review.
- `captions.srt`: caption sidecar. `poster.jpg`: opening frame, unchanged from the previous version.

Graph, exact traversal and full context each refresh 32/32 recoverable reports. Graph uses 60.67% fewer provider input tokens than full context in the seven non-no-op cases. Exact traversal receives the same prompts as graph; all six methods share the same executor. This is one model sample per case/method with adaptive evidence allowances and uncapped full context. The earlier deterministic test remains separate and retains its fixed-cap shortfall and failed development gate. The video claims no cost savings, latency benefit, hosting availability or public source access.
