# Fixed evidence-budget diagnostic results

The retained scores cover all 88 cells planned in [the frozen protocol](FIXED_BUDGET_DIAGNOSTIC_PROTOCOL.md). The diagnostic reuses the eight saved March cases and runs the existing deterministic reader and shared HydraDB-assisted executor. At **4,096 receipt tokens**, native graph, exact flat, and iterative hybrid each refreshed **15 of 32** eligible affected reports. At **8,192**, graph and exact flat refreshed **27 of 32**, and iterative hybrid refreshed **28 of 32**. The uncapped reference refreshed **32 of 32**. Every capped policy missed at least one recoverable report at each cap. [Recovered summary](../results/fixed-budget-diagnostic-v1/publication/recovered_summary.json)

## Original attempt and verification

The experiment ran once from revision `4f43dd497a05078edf226de62070778b17d91498` with freeze SHA-256 `cd609ff71f8f74162fb2ae911e8f7cae6d1429db347debff79a1e69fd857f92f`. All 88 exact JSONL contexts and selections were recorded before refresh began. All 88 execution attempts produced retained scorer results, poststate snapshots, and provenance audits. The publication wrapper then raised the same `KeyError` in every cell because it expected singular count-field names and the scorer returned plural names. The original summary records **88 execution failures and an incomplete wrapper outcome**. Source and resource integrity both verified. [Original run manifest](../results/fixed-budget-diagnostic-v1/run_manifest.json) · [Original summary](../results/fixed-budget-diagnostic-v1/summary.json)

After the run, a separate read-only parser verified the retained scores. It checked exact contexts and token counts, tied each saved reader selection to the selection consumed by refresh, verified snapshot and audit hashes, independently traced receipt chains, and reapplied the original aggregate rules. The recovered rows retain each original failure status and its record hash. The parser made no new ranking, embedding, graph, refresh, or provider requests. [Recovery parser](../results/fixed-budget-diagnostic-v1/recover_retained_scores.py) · [Original evidence hashes](../results/fixed-budget-diagnostic-v1/publication/original_evidence_sha256.json) · [Recovered cell and artifact ledgers](../results/fixed-budget-diagnostic-v1/publication/recovered_cells.jsonl)

## Outcomes by policy

Evidence coverage counts affected artifact records present in the context. Reader coverage counts affected artifacts connected to a changed-version alias by a path in that context. Fresh reports require independent value and provenance checks after execution. Whole-case checks also cover calculations, blocked outputs and unchanged identities.

| Cap | Policy | Fresh affected reports / 32 | Whole cases / 8 | Affected evidence / 89 | Reader coverage / 89 | Receipt tokens used |
|---:|---|---:|---:|---:|---:|---:|
| 4,096 | Native graph | 15 | 4 | 65 | 65 | 25,771 |
| 4,096 | Exact flat | 15 | 4 | 65 | 65 | 25,771 |
| 4,096 | BM25 | 5 | 2 | 48 | 30 | 32,004 |
| 4,096 | BGE | 2 | 2 | 30 | 28 | 31,875 |
| 4,096 | Iterative hybrid | 15 | 3 | 63 | 63 | 31,836 |
| 8,192 | Native graph | 27 | 7 | 84 | 84 | 34,293 |
| 8,192 | Exact flat | 27 | 7 | 84 | 84 | 34,293 |
| 8,192 | BM25 | 25 | 6 | 79 | 75 | 64,923 |
| 8,192 | BGE | 10 | 2 | 58 | 54 | 64,884 |
| 8,192 | Iterative hybrid | 28 | 7 | 84 | 84 | 64,716 |
| Uncapped reference | Full context | 32 | 8 | 89 | 89 | 119,445 |

Native graph and exact flat produced byte-identical contexts in all eight cases at each cap. At 8,192, both covered all eligible reports outside the global tool-version case M05. Iterative hybrid also covered all other cases and refreshed one additional M05 report. All observed reader selections had zero false positives.

Every policy and cap preserved **52 of 52** unaffected report identities, blocked **4 of 4** unavailable reports, and had zero incorrect-current reports. M07 reached the expected missing-source refusal in all 11 cells. M08 returned an empty deterministic selection and preserved original heads in all 11 cells. Both cases had zero eligible affected reports.

## Fresh affected reports by case

Capped entries show counts at **4,096 → 8,192**. The uncapped reference ran once per case.

| Case | Eligible | Graph and exact flat | BM25 | BGE | Iterative hybrid | Uncapped reference |
|---|---:|---:|---:|---:|---:|---:|
| M01 | 4 | 4 → 4 | 2 → 4 | 0 → 2 | 3 → 4 | 4 |
| M02 | 3 | 3 → 3 | 1 → 3 | 0 → 1 | 3 → 3 | 3 |
| M03 | 4 | 3 → 4 | 0 → 2 | 0 → 1 | 3 → 4 | 4 |
| M04 | 6 | 1 → 6 | 0 → 6 | 0 → 2 | 1 → 6 | 6 |
| M05 | 11 | 1 → 6 | 2 → 6 | 2 → 4 | 3 → 7 | 11 |
| M06 | 4 | 3 → 4 | 0 → 4 | 0 → 0 | 2 → 4 | 4 |
| M07 | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |
| M08 | 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 |

## Scope and reproduction

The caps apply to exact serialized receipt bytes as counted by the frozen cl100k_base tokenizer. Query text is accounted for separately. All policies use the same HydraDB-assisted currentness and recursive refresh, so reader coverage and final report recovery can differ. These are repeat observations on saved cases with an algorithmic reader. The [adaptive model comparison](MODEL_COMPARISON_RESULTS.md) and the [separate 2,048-token retail diagnostic](RETAIL_V2_RESULTS.md) retain their original settings and outcomes. The fixed-budget diagnostic supplies no new generative-model accuracy, provider exposure, cost, latency, or graph-engine superiority result.

To reproduce, follow the [frozen protocol's run instructions](FIXED_BUDGET_DIAGNOSTIC_PROTOCOL.md#run-the-frozen-diagnostic) with the exact revision above and new public and private directories. The original wrapper is expected to return status 1 after recording its count-field error. Record that reproduction's manifest and summary SHA-256 values, then pass them to the read-only parser with a separate publication directory.

```sh
python results/fixed-budget-diagnostic-v1/recover_retained_scores.py \
  --original /absolute/path/to/reproduced-original-run \
  --private-execution /absolute/path/to/reproduced-private-execution \
  --publication /absolute/path/to/new-publication \
  --original-manifest-sha256 RECORDED_MANIFEST_SHA256 \
  --original-summary-sha256 RECORDED_SUMMARY_SHA256
```

The [public per-cell bundle](PUBLIC_FIXED_BUDGET_EVIDENCE.md) contains every exact context and the recovered ledger. Its standard-library verifier independently recounts tokens, reconstructs all 88 original poststates from their initial records and deltas, and rechecks arithmetic, receipt chains and outcomes. Original path-bearing scorer files, stores and private execution directories remain in the retained run archive.
