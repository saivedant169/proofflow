# Retail v2 results

The complete Hydra dependency path reached correct endstates in **10/10 held-out cases**, matching exact-flat traversal and full context on every scoped artifact. It refreshed **38/38 recoverable affected reports** and correctly withheld **4/4 unavailable reports**. The missing-source refusal is not a freshly completed answer.

Graph evidence used **39,375/128,729 tokens (30.59%)** of full context: **69.41% fewer evidence tokens** across all cases. The prospective ≤40% ratio gate **passed**. Excluding the no-op, the ratio is **33.99%**, still below 40%.

This uses 640 externally sourced UCI retail lines in four dated partitions, with ten authored changes and new declared report compositions. It is a deterministic retrieval/refresh experiment with real tools and HydraDB, **not an LLM-agent or learning-curve result**. All arms use the same Hydra-assisted currentness and recursive refresh executor.

## Complete production path and full-context control

Every case exposes 39 artifacts, including 11 reports. Correctness checks exact impact closure plus independent numeric oracle, currentness, original-artifact preservation and per-artifact endstate equality. Raw immutable IDs are excluded from semantic parity.

| Method | Exact closures | Correct endstate cases | Fresh affected artifacts | Fresh affected reports | Mean evidence tokens | Tool calls |
|---|---:|---:|---:|---:|---:|---:|
| ProofFlow / HydraDB | 10/10 | 10/10 | 101/101 | 38/38 | 3,937.5 | 101 |
| Exact flat traversal | 10/10 | 10/10 | 101/101 | 38/38 | 3,937.5 | 101 |
| Full context | 10/10 | 10/10 | 101/101 | 38/38 | 12,872.9 | 101 |

Exact flat traversal ties graph per case, including semantic artifact states and values. Explicit dependencies explain the result; this is not an exclusive correctness advantage of the storage engine. Full context uses the same affected-evidence reader, so it does not force recalculation of unaffected work.

## Baselines with the same per-case graph evidence allowance

The complete graph closure determines each case's allowance **before comparator execution**. BM25, dense BGE and iterative hybrid receive the identical allowance and serialized records. The allowance varies from 0 to 9,611 tokens; whole-record packing can leave unused space. Graph/exact-flat rows below are the complete-closure conditions that define/match this allowance.

| Method | Exact affected sets | Mean recall | Fresh affected reports | Correct endstate cases | Mean tokens | Tool calls |
|---|---:|---:|---:|---:|---:|---:|
| ProofFlow / HydraDB | 10/10 | 100.00% | 38/38 | 10/10 | 3,937.5 | 101 |
| Exact flat traversal | 10/10 | 100.00% | 38/38 | 10/10 | 3,937.5 | 101 |
| BM25 | 2/10 | 53.78% | 19/38 | 3/10 | 3,854.3 | 63 |
| Dense BGE | 1/10 | 43.77% | 8/38 | 2/10 | 3,866.5 | 48 |
| Iterative hybrid | 5/10 | 92.91% | 33/38 | 6/10 | 3,891.0 | 96 |

## Fixed 2,048-token diagnostic

This is a separate constrained condition. It does not inherit the complete graph path's perfect result. The stronger iterative baseline remains visible, and fewer tool calls can simply mean unfinished work.

| Method | Exact affected sets | Mean recall | Fresh affected reports | Correct endstate cases | Mean tokens | Tool calls |
|---|---:|---:|---:|---:|---:|---:|
| ProofFlow / HydraDB | 1/10 | 63.51% | 8/38 | 2/10 | 1,774.4 | 54 |
| Exact flat traversal | 1/10 | 63.51% | 8/38 | 2/10 | 1,774.4 | 54 |
| BM25 | 1/10 | 31.99% | 1/38 | 2/10 | 1,941.5 | 23 |
| Dense BGE | 1/10 | 28.31% | 0/38 | 2/10 | 1,972.0 | 20 |
| Iterative hybrid | 1/10 | 51.26% | 4/38 | 2/10 | 1,991.4 | 42 |

Every fixed-budget arm's two correct endstate cases are **R07 (expected refusal)** and **R09 (no-op)**. They are not two successfully refreshed affected-report cases. Precision is 100% for every reader condition because it predicts only explicitly connected artifacts; irrelevant retrieved records can still consume the context budget. These are affected-set scores, not raw document-relevance precision.

## Every held-out case

Complete graph, exact-flat and full-context conditions have exact closure and semantic parity in all ten cases. The 40% efficiency threshold is an aggregate gate; R06 and R08 exceed it individually and remain in the results.

| Case | Intervention | Affected artifacts | Graph / full tokens | Token ratio | Fresh affected reports | Blocked unavailable reports |
|---|---|---:|---:|---:|---:|---:|
| R01 | parallel quantity | 10 | 3,329 / 12,870 | 25.87% | 3/3 | 0/0 |
| R02 | price | 11 | 3,998 / 12,870 | 31.06% | 4/4 | 0/0 |
| R03 | gross net divergence | 8 | 3,225 / 12,873 | 25.05% | 4/4 | 0/0 |
| R04 | fx partition | 7 | 2,590 / 12,868 | 20.13% | 3/3 | 0/0 |
| R05 | same value revalidation | 10 | 3,331 / 12,872 | 25.88% | 3/3 | 0/0 |
| R06 | multiple partitions | 18 | 6,684 / 12,872 | 51.93% | 7/7 | 0/0 |
| R07 | missing source | 8 | 3,166 / 12,872 | 24.60% | 0/0 | 4/4 |
| R08 | global tool version | 27 | 9,611 / 12,894 | 74.54% | 11/11 | 0/0 |
| R09 | canonical noop | 0 | 0 / 12,870 | 0.00% | 0/0 | 0/0 |
| R10 | restart after change | 10 | 3,441 / 12,868 | 26.74% | 3/3 | 0/0 |

## Failure and preservation accounting

All 110 execution conditions have **zero unexpected execution or inspection errors**, **zero incorrectly current artifacts**, and preserve all **281/281 unaffected artifact identities** per arm across the ten cases. R07 produces the recorded `MissingEvidenceError: Source no longer available: source:2011-08:fx` in all eleven conditions. Each blocks 8/8 unavailable artifacts, including 4/4 reports. Their saved historic values are not counted as current answers. R09 performs zero tool calls and preserves current identities in every condition.

## Development gate remains a failure

The four development cases passed correctness, but graph/full evidence was **6,752/11,107 (60.79%)**, above the unchanged 40% gate: **FAIL**. Excluding its no-op gives **81.07%**. These results are retained in `results/retail-dev-v1`; development was not pooled with test, and no cases, production algorithms, baseline settings or threshold were changed after these outcomes.

## Scope, timing and reproduction

Frozen revision [`4bff48f`](https://github.com/saivedant169/proofflow/tree/4bff48ff0276a52678c23ec62652aa2f46a3894b); manifest SHA-256 `2502b8d70e29c9992fd5c852a62cdb7c2fefb39972c22fa27513287812d000d4`. The test run finished `2026-11-15T11:14:48.180566+00:00` after 346.67 seconds. Its clean initial tree and end-of-run source/code/model/spec integrity were verified. All 110 retrieval rows and 110 execution rows were independently audited against saved case oracles and per-artifact observations.

The actual vector baseline is BAAI/bge-small-en-v1.5 via FastEmbed ONNX, with exact cosine scoring, complete tokenizer-aware chunks and unchanged v1 parameters. Indexes, exact-ID access, scope, reader, serialization and packing are shared. Dataset prices are GBP regardless of country. The 640 test lines are a bounded positive-sales sample, not the full 541,909-line ledger; FX, refunds and corrections are staged assumptions. No customer deployment, historical incident accuracy, policy learning, LLM dollar savings, statistical superiority, or controlled latency speedup is established.

- [Protocol](RETAIL_V2_SPEC.md) and [dataset attribution/modifications](../fixtures/retail_v2/DATASET_NOTICE.md).
- [Machine-readable audited summary](../evidence/retail_v2_summary.json).
- [Raw test manifest](../results/retail-test-v1/run_manifest.json), [retrieval](../results/retail-test-v1/retrieval.jsonl), [execution](../results/retail-test-v1/execution.jsonl).
- [Saved development result](../results/retail-dev-v1/summary.json).

Regenerate the report from saved evidence, without database or model calls:

```sh
uv run python scripts/summarize_retail.py
```
