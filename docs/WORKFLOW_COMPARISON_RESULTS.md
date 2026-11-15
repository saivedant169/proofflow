# Small CSV close workflow comparison

Both workflows matched all eight expected outputs for the initial close and both corrections. Each rejected all four stale handoff attempts and accepted all three current handoffs. Full recalculation with a shared version check covered this small-file workflow. ProofFlow additionally preserved unaffected artifact heads and execution receipts and provided a native path explaining why each report became stale. [Frozen protocol](WORKFLOW_COMPARISON_PROTOCOL.md) · [Machine-readable results](../results/workflow-comparison-v1/summary.json)

The builder-run probe used nine synthetic orders in three currencies. Both methods received identical CSV bytes, explicit rate strings, a selected region, and an independently hand-specified oracle. Cold means a new import workspace. Warm means correcting a previously published close in the same workspace. [Inputs and oracle](../fixtures/workflow_comparison/cases.json)

| Phase | Company net | NORTH net | Ordinary fresh logical outputs | ProofFlow newly recorded outputs | ProofFlow retained heads and receipts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cold initial close | $631.29 | $242.01 | 8 | 8 | 0 |
| Warm EUR rate correction | $636.79 | $247.51 | 8 | 4 | 4 |
| Warm SOUTH refund correction | $631.79 | $247.51 | 8 | 6 | 2 |

Each ordinary run parsed and validated all nine rows in one scan, recomputed all eight logical outputs from scratch, and passed four reconciliation controls. Both arms separately matched 24 expected output values across the three phases. An output can contain totals for multiple regions. Ordinary outputs can be computed together in the same loop. [Ordinary calculation and control totals](../results/workflow-comparison-v1/attempt-001/ordinary-progress.json) · [ProofFlow heads, receipts, and values](../results/workflow-comparison-v1/attempt-001/proofflow-progress.json)

## Work retained and checked

The rate correction retained the exact gross, refund, net, and support artifact heads and their producing receipts. The refund correction retained the gross and support heads and receipts. The eight cold receipts and ten new warm receipts matched the artifact IDs produced by the corresponding recorded executions. ProofFlow also returned a native HydraDB path from each superseded source version to each of the two prior reports. For example, the previous FX source was consumed by `convert_to_usd`, whose regional USD artifact was consumed by `compose_report` to produce the previous NORTH report. The refund path passes through `refunds_by_region`, `net_by_region`, and `convert_to_usd` before reaching the NORTH report. The unchanged NORTH amount was still withheld as a current claim until refresh because its report depends on the versioned refunds source. [FX paths](../results/workflow-comparison-v1/attempt-001/proofflow-fx-correction-stale-paths.json) · [Refund paths](../results/workflow-comparison-v1/attempt-001/proofflow-refund-correction-stale-paths.json) · [Refund stale state](../results/workflow-comparison-v1/attempt-001/proofflow-refund-correction-update.json)

| ProofFlow step | Preflight analytics invocations | Recorded analytics invocations | Fresh verification invocations | Total |
| --- | ---: | ---: | ---: | ---: |
| New session, authored demo bootstrap | 0 | 8 | 0 | 8 |
| Cold CSV preview and create | 16 | 8 | 11 | 35 |
| Warm FX preview, update, and refresh | 16 | 4 | 11 | 31 |
| Warm refund preview, update, and refresh | 16 | 6 | 11 | 33 |

The first session and CSV import together invoked analytics 43 times. The two warm corrections invoked analytics 64 times in total, including repeated preflights and fresh recipe verification. Preview and update each recalculated support during preflight even though refresh kept its existing head and receipt. Verification evaluated the saved report recipes against current inputs using the same tool implementations. The independent arithmetic check for both arms was the frozen oracle. The first table counts logical outputs and retained versions. The second counts ProofFlow function invocations. Use the two as work inventories with different units. [Per-request invocation ledger](../results/workflow-comparison-v1/attempt-001/operations.jsonl)

## Report handoff

Client A retained its previous report view. Client B accepted the next revision and published the corrected report afterward. Before and after the new reports were available, the ordinary workflow checked the old file’s embedded input revision against the latest shared revision and withheld the file as a current handoff. ProofFlow returned HTTP 409 without report content for the same four attempts. A fresh ProofFlow state read between update and refresh marked both reports stale and returned `null` for their current values. Client A’s requests still held the prior IDs. All seven ProofFlow export requests used `Cache-Control: no-store` and invoked zero calculation tools. [Handoff checks in the operation ledger](../results/workflow-comparison-v1/attempt-001/operations.jsonl)

Previously exported files remained byte-identical in both arms through three later checks per arm. The ordinary snapshot includes a calculation timestamp and the exact input revision digest. Its guard runs against the shared current input and published report. The ProofFlow snapshot includes the server check timestamp and separate report and claim artifact IDs, which can be followed through the owned workspace’s evidence. Both are static reports. [Ordinary FX snapshot](../results/workflow-comparison-v1/attempt-001/ordinary-fx-correction.txt) · [ProofFlow FX snapshot](../results/workflow-comparison-v1/attempt-001/proofflow-fx-correction.txt)

For this nine-row close, full recalculation with an explicit latest-version check produced the same amounts and enforced the same ordered handoff rule. A workflow that also needs the version-specific reason a claim went stale, which published work stayed valid, or the exact execution behind a retained result can use the receipts and paths ProofFlow returned. The measured evidence covers two authored corrections, one paired run, and two same-session API clients. Analyst time, relative compute cost, throughput, adoption, and independent business outcomes remain unmeasured. [Separate Chromium handoff acceptance](REPORT_HANDOFF_ACCEPTANCE.md)

## Run record and reproduction

The protocol and fixtures were hashed before running either arm. The full [freeze manifest](../fixtures/workflow_comparison/freeze.json) records source, runner, protocol, and fixture SHA-256 hashes. Its own SHA-256 is `9fb9d68b60bd32b9e594849fc5f4c88fab1bd06c80575674c74bb3cbb0e8c616`. The checked-out package was based on `57eacf744f88a9d1b31451f78f8a8c4ef5fa9c1f`. The only package diff added public static evidence routing. The test app used a temporary state directory and an absent static directory, leaving that route inactive. The [recorded diff](../results/workflow-comparison-v1/runtime-source.patch) applied to the base yields the exact API file hash in the freeze.

On 2026-11-15 UTC the single paired attempt passed both arms on macOS arm64 with Python 3.12.15 and pinned local HydraDB OSS 0.4.0. It made zero model calls. The expected 409 responses are retained with all successful requests. The seven focused tests passed, and the combined comparison, browser import API, and report handoff API test selection passed all 50 tests. [Attempt manifest](../results/workflow-comparison-v1/attempt-001/run.json)

From a checkout matching the frozen files, prepare the locked Python environment and start the local HydraDB service and token file if needed. Use a separate results directory to retain the original attempt.

```sh
uv sync --frozen --extra test
.venv/bin/python scripts/init_local.py
docker compose up -d hydradb
.venv/bin/python scripts/workflow_comparison.py run \
  --output "$(mktemp -d)" --reason "Replicate frozen small CSV comparison"
.venv/bin/python -m pytest -q tests/test_workflow_comparison.py
shasum -a 256 -c results/workflow-comparison-v1/SHA256SUMS
```
