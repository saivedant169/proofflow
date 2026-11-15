# ProofFlow held-out pilot results

Complete `pilot-v1` run: **12 authored held-out scenarios**, finished 2026-11-15T09:50:00.093139+00:00. This measures a deterministic evidence reader followed by actual analytics-tool refresh. No LLM participates in these results.

All methods receive the same evidence records, direct dependency IDs, scope filtering, exact-ID seeding facility, and token budgets. Every refresh arm uses the same **Hydra-assisted currentness and recursive refresh executor**. This compares retrieval selectors within that executor; it does not compare standalone vector-versus-graph safety.

## Main comparison: 2,048 evidence tokens

Fresh affected reports count only reports that require revalidation and have an available independent numeric oracle. The all-fresh scenario column covers all oracle-available reports, including unaffected reports. A blocked report with a missing source is excluded from both fresh-report denominators and reported separately below.

| Method | Exact affected sets | Mean precision | Mean recall | Fresh affected reports | Scenarios with all eligible reports fresh | Mean context tokens | Actual tool calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| BM25 | 1/12 | 100.0% | 41.4% | 6/29 | 2/12 | 1974 | 23 |
| Dense BGE | 1/12 | 100.0% | 37.5% | 1/29 | 2/12 | 1950 | 22 |
| Hybrid RRF | 1/12 | 100.0% | 38.4% | 4/29 | 2/12 | 1970 | 22 |
| Iterative hybrid | 2/12 | 100.0% | 63.9% | 9/29 | 3/12 | 1980 | 38 |
| ProofFlow / HydraDB | 6/12 | 100.0% | 87.2% | 16/29 | 6/12 | 1564 | 54 |
| Exact flat traversal | 6/12 | 100.0% | 87.2% | 16/29 | 6/12 | 1564 | 54 |

Precision and recall score the affected-artifact set identified by the common deterministic reader from the selected records; they are not raw top-k document-relevance scores. The reader follows only explicit paths present in its context.

The exact flat dependency-traversal control ties ProofFlow on these selection and execution metrics. Explicit dependency structure is the intervention; this pilot does not establish an exclusive advantage of the HydraDB storage engine.

Tool-call totals include recursively refreshed prerequisites. Fewer calls are not better when required reports remain unresolved. Unselected stale/unknown reports are withheld by the common executor, not counted as incorrect answers served.

## Full evidence-budget ladder

Each cell is **exact affected sets / scenarios; mean recall; mean context tokens**. “All” removes the evidence-token limit. Direct-ID and Hydra-direct conditions are ablations and do not have separate refresh experiments.

| Method | 512 tokens | 1,024 tokens | 2,048 tokens | Unlimited evidence budget |
|---|---:|---:|---:|---:|
| BM25 | 1/12; 26.4%; 403 | 1/12; 34.3%; 954 | 1/12; 41.4%; 1974 | 12/12; 100.0%; 8035 |
| Dense BGE | 1/12; 26.4%; 402 | 1/12; 35.6%; 976 | 1/12; 37.5%; 1950 | 12/12; 100.0%; 8035 |
| Hybrid RRF | 1/12; 26.4%; 402 | 1/12; 32.2%; 951 | 1/12; 38.4%; 1970 | 12/12; 100.0%; 8035 |
| Iterative hybrid | 1/12; 26.4%; 404 | 1/12; 32.2%; 957 | 2/12; 63.9%; 1980 | 12/12; 100.0%; 8035 |
| ProofFlow / HydraDB | 1/12; 26.4%; 336 | 1/12; 56.4%; 860 | 6/12; 87.2%; 1564 | 12/12; 100.0%; 2038 |
| Exact flat traversal | 1/12; 26.4%; 336 | 1/12; 56.4%; 860 | 6/12; 87.2%; 1564 | 12/12; 100.0%; 2038 |
| Direct ID | 1/12; 24.3%; 267 | 1/12; 30.1%; 419 | 1/12; 30.1%; 419 | 1/12; 30.1%; 419 |
| Hydra direct only | 1/12; 24.3%; 267 | 1/12; 30.1%; 419 | 1/12; 30.1%; 419 | 1/12; 30.1%; 419 |
| All-record context | — | — | — | 12/12; 100.0%; 8035 |

The all-record control uses 8035 mean evidence tokens, refreshes 29/29 eligible affected reports in 68 tool calls, and reaches all eligible reports fresh in 12/12 scenarios.

## Failures, blocking, and preserved work

| Method | Correctly blocked / unavailable reports | Incorrect current reports | Unaffected report artifacts preserved | Refresh errors |
|---|---:|---:|---:|---:|
| BM25 | 2/2 | 0 | 72/72 | 1 |
| Dense BGE | 2/2 | 0 | 72/72 | 1 |
| Hybrid RRF | 2/2 | 0 | 72/72 | 1 |
| Iterative hybrid | 2/2 | 0 | 72/72 | 1 |
| ProofFlow / HydraDB | 2/2 | 0 | 72/72 | 1 |
| Exact flat traversal | 2/2 | 0 | 72/72 | 1 |
| All-record context | 2/2 | 0 | 72/72 | 1 |

Missing-source errors are preserved in the raw execution rows. Correct blocking is a safety outcome, not a successfully completed report. Inspection failures, if any, are separately recorded in the JSON summary.

## Every held-out case

Cells show **selected true affected / expected affected artifacts; fresh affected / eligible affected reports** at 2,048 tokens. A 0/0 fresh-report entry means no affected report has an available oracle; consult the blocking table.

| Case | BM25 | Dense BGE | Iterative hybrid | ProofFlow |
|---|---:|---:|---:|---:|
| T01 | 2/7; 0/2 | 2/7; 0/2 | 3/7; 0/2 | 6/7; 1/2 |
| T02 | 1/6; 0/2 | 2/6; 0/2 | 2/6; 0/2 | 6/6; 2/2 |
| T03 | 1/4; 0/2 | 1/4; 0/2 | 3/4; 1/2 | 4/4; 2/2 |
| T04 | 2/7; 0/2 | 3/7; 0/2 | 3/7; 0/2 | 6/7; 1/2 |
| T05 | 3/4; 2/3 | 2/4; 1/3 | 4/4; 3/3 | 4/4; 3/3 |
| T06 | 0/0; 0/0 | 0/0; 0/0 | 0/0; 0/0 | 0/0; 0/0 |
| T07 | 3/10; 1/5 | 3/10; 0/5 | 5/10; 2/5 | 6/10; 2/5 |
| T08 | 2/7; 0/2 | 2/7; 0/2 | 4/7; 0/2 | 6/7; 1/2 |
| T09 | 6/12; 2/6 | 4/12; 0/6 | 7/12; 1/6 | 7/12; 1/6 |
| T10 | 2/4; 0/0 | 1/4; 0/0 | 3/4; 0/0 | 4/4; 0/0 |
| T11 | 2/4; 1/2 | 1/4; 0/2 | 3/4; 1/2 | 4/4; 2/2 |
| T12 | 1/7; 0/3 | 2/7; 0/3 | 4/7; 1/3 | 5/7; 1/3 |

## Reproduce and inspect

- Frozen code: [`b03123b`](https://github.com/saivedant169/proofflow/tree/b03123b16d98ac776bca2c049894630dfe19fb9a).
- Case/configuration manifest SHA-256: `21fb48da354beac55dc0a0fbfd40068a52fce4656165aba0ea991449290d1269`.
- Dense model: `BAAI/bge-small-en-v1.5`, real FastEmbed ONNX embeddings, overlapping tokenizer-aware chunks; hashes are in the run manifest.
- [Raw run manifest](../results/test-v1/run_manifest.json), [retrieval rows](../results/test-v1/retrieval.jsonl), [execution rows](../results/test-v1/execution.jsonl).
- [Machine-readable summary](../evidence/benchmark_summary.json) and [methodology](BENCHMARK_SPEC.md).

```sh
uv run python -m proofflow.eval.runner --split test --allow-test --output results/test-reproduction
uv run python scripts/summarize_benchmark.py --input results/test-reproduction
```

A reproduction needs the local HydraDB service and benchmark dependencies. The runner refuses to overwrite an existing run and refuses held-out execution with tracked/staged changes. The report generator refuses unfinished or partial runs.

These twelve scenarios reuse an authored commerce workload and staged mutations. They do not establish statistical or universal superiority across domains. Results separate potential revalidation from actual numeric value changes. T12 uses a declared new composition and is not evidence that an agent independently discovered that composition. Application-reopen and database-container restart evidence are reported separately. Latencies are descriptive measurements on a shared development machine with concurrent work and include different index/query work; they are not a production throughput benchmark.
