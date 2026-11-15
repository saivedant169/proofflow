# ProofFlow model study evidence

[Open the evidence page](https://proofflow.arnavbule.in/evidence/) · [Download the evidence ZIP](https://proofflow.arnavbule.in/evidence/proofflow-model-evidence.zip) · [ZIP SHA-256](https://proofflow.arnavbule.in/evidence/proofflow-model-evidence.zip.sha256)

This results bundle covers the model comparison recorded on 15 November 2026. Its study revision is `3fa9f850bbecdccf068bbda7e90cd0497e79b460`, which froze the 48 requests. The hosted application may run at a later revision.

## Verify offline

Download the ZIP and its SHA-256 file to the same directory. On macOS use `shasum -a 256 -c proofflow-model-evidence.zip.sha256` to match the ZIP to the published digest. On Linux use `sha256sum -c proofflow-model-evidence.zip.sha256`.

Extract the ZIP and run the verifier with Python 3.10 or later.

```sh
unzip proofflow-model-evidence.zip -d proofflow-model-evidence
cd proofflow-model-evidence
python3 scripts/verify_public_evidence.py
```

It checks the bundle inventory and file digests, then audits 48 saved case-and-method cells and 152 model-study payloads. It reconstructs the 4,681 source rows, recalculates reports with Decimal half-even rounding, traces the saved receipts through exact source and tool versions, and reconciles the provider counters and ledger. It also adds the saved per-case counts and token totals for the earlier deterministic studies. Verification runs offline with the Python standard library.

The study records one model invocation per cell. Across M01–M07, graph used 75,422 of the 191,774 input tokens seen by full context (39.33%), counting uncached input, cache writes and cache reads. M08 was a canonical no-op and is outside this primary ratio. Graph, exact-flat traversal and full context each refreshed 32/32 recoverable affected reports. BM25 refreshed 25/32, dense BGE 5/32 and iterative hybrid 28/32. Every arm blocked 4/4 unavailable reports.

The five capped methods use each case’s graph closure to set its evidence allowance. Full context receives the complete corpus. Graph and exact-flat traversal received byte-identical prompts in all eight cases. All arms shared the Hydra-assisted refresh and currentness executor. These conditions limit conclusions to the saved sample. The offline audit checks reported provider observations and saved endstates. Provider attestation, database execution and model replication require separate evidence.

Earlier deterministic studies used a fixed 2,048-token budget and recovered 16/29 graph reports in the authored pilot and 8/38 in the retail test. The separate retail development run used 6,752 of 11,107 full-context evidence tokens and missed its 40% maximum (60.79%). The bundle retains those per-case measurements in `historical-results.json`.

## Files and provenance

- `manifest.json` inventories every payload in the ZIP. Transformed copies list changed fields and the original byte length and SHA-256 alongside the new ones.
- `results/model-v4-test-run-1/` contains the 48 saved result records, their independently scored observations and poststates, normalized provider counters, and the publication inventory. The raw log index contains hashes. Original logs and provider envelopes stay private.
- `results/model-v4-test-prepared/` and `fixtures/model_comparison_v4/` contain the frozen reconstruction inputs, including prompt bytes and the selected public dataset’s CSV rows, numeric provenance, and [attribution](fixtures/model_comparison_v4/test/DATASET_NOTICE.md).
- `scripts/` contains the two standard-library verifier files. The public v4 verifier pins the redacted preparation manifest’s digest. Its arithmetic, provenance and scoring logic is unchanged.

The archive uses an explicit allowlist. It replaces host-local references with bundle-relative paths or withheld markers, limits the preparation inventory to bundled inputs, and omits private code inventory and internal audit metadata. It updates the affected digest bindings to match the public copies. The source rows, requests, prompts, report values, receipts and recorded provider counts retain their saved values. The hash inventory records the distribution bytes. The archive contains the minimal verifier and results artifacts derived from synthetic scenarios and CC BY 4.0 retail data.
