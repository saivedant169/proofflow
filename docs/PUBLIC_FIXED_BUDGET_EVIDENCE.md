# ProofFlow fixed-budget evidence

[Evidence page](https://proofflow.arnavbule.in/evidence/) · [Per-cell verification ZIP](https://proofflow.arnavbule.in/evidence/proofflow-fixed-budget-evidence.zip) · [ZIP SHA-256](https://proofflow.arnavbule.in/evidence/proofflow-fixed-budget-evidence.zip.sha256)

This archive covers one deterministic diagnostic on eight saved March cases. It includes the exact contexts, original attempts and recovered observations for 80 capped cells and eight uncapped reference cells.

The attempt froze at revision `4f43dd497a05078edf226de62070778b17d91498`. The original publication wrapper recorded 88 execution errors and `complete: false` after writing the scores. A subsequent read-only audit verified the retained outcomes as a separate result. Both records are included. The adaptive model study is a separate experiment.

## Verify all 88 cells offline

Save the ZIP and its checksum side by side. On macOS, run `shasum -a 256 -c proofflow-fixed-budget-evidence.zip.sha256`. On Linux, run `sha256sum -c proofflow-fixed-budget-evidence.zip.sha256`.

Extract into an empty directory. Use Python 3.10 or later and run the following command from that directory.

```sh
python3 scripts/verify_fixed_budget_evidence.py
```

The verifier checks the file inventory and original attempt digests, independently decodes 4,681 source rows, recomputes report values with Decimal arithmetic, and recounts exact ASCII cl100k_base tokens from the bundled vocabulary. It checks the original context bytes, cap and deterministic reader selection for each cell. It reconstructs each full poststate byte for byte from its initial snapshot and new records, verifies original snapshot hashes, and independently traces the source, tool and receipt versions behind every artifact. The JSON output reports outcome counts for each cell and all 11 conditions. It verifies 16 pairs of byte-identical graph and exact-flat contexts.

[Recovered per-cell ledger](../results/fixed-budget-diagnostic-v1/publication/recovered_cells.jsonl) records each report and artifact outcome alongside the original attempt identity. Original context JSONL is under `results/fixed-budget-diagnostic-v1/<case>/<condition>/<arm>/`. The [witness file](../evidence/fixed_budget_witnesses_v1.jsonl) contains the archived inspections, scorer and audit evidence, and the exact records added during refresh. Each witness records original byte lengths and SHA-256 values. The two private file paths in each scorer document were removed. The manifest records the original and distributed digests and changed fields for the redacted public metadata.

The verifier checks saved retrieval outputs and independently rebuilds context-only reader reachability and the graph/exact-flat whole-record pack. Reproducing BM25, BGE and hybrid rankings or the shared HydraDB-assisted executor requires a new run. The audit uses saved runtime inspections plus independently computed arithmetic and receipt checks. The diagnostic has no new generative model observations. Token counts describe serialized evidence size. This study supplies no latency, cost, or provider exposure measurements.

| Evidence cap | Graph | Exact-flat | BM25 | Dense BGE | Iterative hybrid |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4,096 | 15/32 | 15/32 | 5/32 | 2/32 | 15/32 |
| 8,192 | 27/32 | 27/32 | 25/32 | 10/32 | 28/32 |

The uncapped deterministic reference finished 32/32. Every condition blocked 4/4 unavailable reports, preserved 52/52 unaffected report identities and recorded zero incorrect-current reports.

[Source data attribution](../fixtures/model_comparison_v4/test/DATASET_NOTICE.md) · [Tokenizer registration and vocabulary](https://github.com/openai/tiktoken/blob/0.14.0/tiktoken_ext/openai_public.py) · [Tokenizer license](../fixtures/fixed_budget_diagnostic/TIKTOKEN_LICENSE)
