# ProofFlow walkthrough script

A two-minute edited walkthrough using actual browser captures and saved execution evidence. Narration is generated locally with macOS Samantha; no voice impersonation or outside service is used. It is not presented as an uninterrupted live recording.

The browser workflow is guided. The model-chosen composition is a separate, explicitly recorded local experiment. The repository remains private.

## 1. Saved work can outlive its inputs.

**Visual:** ../evidence/ui/workspace-final.jpg

Reports can look finished after their inputs change. ProofFlow helps analytics agents keep saved work current. These briefs reuse earlier calculations. Every tool records the input versions it actually consumed. Hydra D B connects those execution receipts across runs.

## 2. A correction makes dependent claims stale.

**Visual:** ../evidence/ui/source-drawer.jpg, then ../evidence/ui/workspace-stale-final.jpg

Correct the euro-to-dollar rate from one point one zero to one point two zero. The revenue claims become stale. ProofFlow withholds current values and labels the previous numbers as historical.

## 3. The path is queried from HydraDB.

**Visual:** ../evidence/ui/evidence-path-final.jpg

Open the evidence. Hydra D B shows the dependency path from that correction to this calculation and both reports.

## 4. Four tools. Two updated reports. Preserved support.

**Visual:** ../evidence/ui/workspace-refreshed-final.jpg

Refresh affected work. Four tools run. E U revenue becomes two thousand two hundred eighty dollars; company revenue becomes five thousand seven hundred fifty-five. The independent support result stays unchanged.

## 5. Measured against fair retrieval baselines.

**Visual:** ../evidence/ui/benchmark-primary.jpg

Our frozen pilot has twelve authored scenarios, identical evidence, and a two-thousand-forty-eight-token limit. ProofFlow refreshed sixteen of twenty-nine affected reports; B M twenty-five refreshed six, dense retrieval one, and iterative hybrid nine. Every method shares the same Hydra-assisted executor. Exact dependency traversal ties ProofFlow. Full context completes all twenty-nine.

## 6. A model chose the workflow. Tools calculated the values.

**Visual:** ../evidence/ui/recorded-agent-detail.jpg

Separately, two actual Fable five point two calls chose a seven-tool report workflow, then created a new brief reusing three earlier artifacts. All seventeen composition-and-refresh checks passed. This is recorded local model execution, separate from the guided browser demo.

## 7. Bring your own CSV through the CLI.

**Visual:** A command example and schema drawn from the verified CSV importer; not a fabricated execution log.

You can also import your own bounded C S V through the command line and reuse this same calculation runtime.

## 8. ProofFlow — current evidence for analytics agents.

**Visual:** ../evidence/ui/workspace-refreshed-final.jpg

ProofFlow: follow what changed, refresh what depends on it, and preserve work that remains valid.

## Evidence and production notes

- Benchmark: `docs/BENCHMARK_RESULTS.md`, frozen 12-case pilot, 2,048 evidence tokens. Show the exact-flat tie, 29/29 full-context ceiling, and common Hydra-assisted executor visibly.
- Model workflow: `evidence/agent_composition.json`; two actual Fable 5.2/high calls, 17/17 checks, recorded locally. This is not the browser running a live hosted model.
- CSV integration: `scripts/import_csv.py` and `results/import-smoke-v1/verification.json`; supports bounded user-provided files. The verification data is authored, not customer evidence.
- The final film closes with “ProofFlow — current evidence for analytics agents.” No deployment URL was available at render time, so the video has no hosting address. A verified URL can be added to the closing title before a later render.
- The final screenshots passed browser workflow and visual review. The source drawer precedes the stale view; selected regions are cropped for legibility. Captions and graphics must not alter the saved application values.
- Rendered length: 120 seconds at 1920 × 1080, 30 fps. The 241-word script uses a locally generated Samantha narration with gentle pacing adjustment. The MP4 includes burned captions and an optional embedded caption track. Exact media measurements and source hashes are in `video/render_manifest.json` and `video/media_validation.json`.
