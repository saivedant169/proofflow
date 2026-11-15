# Actual model comparison

This is a small authored retrieval-and-refresh pilot: one frozen model planning step chooses among presented artifact receipts, then a shared safe executor runs the selected calculations. It does not evaluate an autonomous agent inventing workflows or establish universal graph-database superiority.

Completed **16/16 prespecified attempts** on T02, T04, T07, T10. Model/planning failures: **0**; abstentions: **0**; scoring infrastructure failures: **0**. These counts remain visible even when a conditional report-rate denominator excludes failed executions.

Fresh affected reports after actual refresh: **BM25 1/9 (11.1%)**; **Dense 0/9 (0.0%)**; **Iterative hybrid 2/9 (22.2%)**; **Graph 5/9 (55.6%)**. Graph still left **4/9 recoverable affected reports unresolved**. The full per-case results below retain ties, omissions, and missing-source blocking.

## Frozen conditions

- Harness revision: `5f8782aa56c20aacc9ae583488cf788144ce4f45`; tracked changes at preparation: `false`.
- Requested model: `claude-fable-5-2`; reasoning effort: `high`. Provider-observed canonical model(s): `claude-fable-5-2`; usage trace available for 16/16 attempts.
- Evidence budget: **2048 cl100k_base tokens** per arm. Exact frozen JSONL records, schema, and system prompt are shared; only retrieved records differ. The allowed selection IDs are exactly those presented.
- BM25 and dense use the benchmark's exact-ID seeding; iterative hybrid is the stronger retrieval control. All arms see identical underlying receipts and source-change IDs. No gold labels or hidden candidate list enter the model prompt.
- All model plans finish before any refresh. Each execution has private manifest heads/blob storage and shares immutable Hydra graph history. Every arm uses the same Hydra-assisted currentness checks and recursive refresh executor.
- One sample per case/arm, no retry or model fallback. Fixed rotation determines arm order. Per-call timeout: 180 seconds; configured per-call budget: $1.00.
- Report recipes and arithmetic tools already exist. This tests context-driven selection and actual refresh, not model-created report composition.

## Affected report completion

The numerator counts affected reports that are both current and equal to an independent numeric oracle after refresh. The denominator counts affected reports with an available oracle in successfully scored executions. Missing-source cases have no recoverable oracle for the affected reports and appear separately below. Unaffected already-current reports do not inflate this primary rate.

| Arm | Attempts | Model failures / abstentions | Scored executions | Fresh affected reports | Exact artifact selections | Actual tool calls |
|---|---:|---:|---:|---:|---:|---:|
| BM25 | 4 | 0 / 0 | 4 | 1/9 (11.1%) | 0/4 | 6 |
| Dense | 4 | 0 / 0 | 4 | 0/9 (0.0%) | 0/4 | 8 |
| Iterative hybrid | 4 | 0 / 0 | 4 | 2/9 (22.2%) | 0/4 | 10 |
| Graph | 4 | 0 / 0 | 4 | 5/9 (55.6%) | 2/4 | 18 |

Exact artifact selection is a secondary metric: the chosen IDs must equal the complete expected revalidation set. Selecting a terminal report can recursively refresh its prerequisites through the common executor; artifact selection and report completion therefore measure different behavior.

## Every prespecified case and arm

| Case | Arm | Plan status | Evidence tokens | Artifact precision / recall | Fresh affected reports | All eligible reports fresh | Correctly blocked unavailable reports | Tool calls |
|---|---|---|---:|---:|---:|---:|---:|---:|
| T02 | BM25 | planned | 1984 | 1.000 / 0.167 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 1 |
| T02 | Dense | planned | 1869 | 1.000 / 0.333 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 2 |
| T02 | Iterative hybrid | planned | 1989 | 1.000 / 0.333 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 2 |
| T02 | Graph | planned | 2000 | 1.000 / 1.000 | 2/2 (100.0%) | 9/9 (100.0%) | 0/0 (not applicable) | 6 |
| T04 | BM25 | planned | 1998 | 1.000 / 0.286 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 2 |
| T04 | Dense | planned | 2030 | 1.000 / 0.429 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 3 |
| T04 | Iterative hybrid | planned | 2039 | 1.000 / 0.429 | 0/2 (0.0%) | 7/9 (77.8%) | 0/0 (not applicable) | 3 |
| T04 | Graph | planned | 1884 | 1.000 / 0.857 | 1/2 (50.0%) | 8/9 (88.9%) | 0/0 (not applicable) | 6 |
| T07 | BM25 | planned | 2030 | 1.000 / 0.300 | 1/5 (20.0%) | 5/9 (55.6%) | 0/0 (not applicable) | 3 |
| T07 | Dense | planned | 2039 | 1.000 / 0.300 | 0/5 (0.0%) | 4/9 (44.4%) | 0/0 (not applicable) | 3 |
| T07 | Iterative hybrid | planned | 2038 | 1.000 / 0.500 | 2/5 (40.0%) | 6/9 (66.7%) | 0/0 (not applicable) | 5 |
| T07 | Graph | planned | 2039 | 1.000 / 0.600 | 2/5 (40.0%) | 6/9 (66.7%) | 0/0 (not applicable) | 6 |
| T10 | BM25 | planned | 1959 | 1.000 / 0.500 | 0/0 (not applicable) | 7/7 (100.0%) | 2/2 (100.0%) | 0 |
| T10 | Dense | planned | 1913 | 1.000 / 0.250 | 0/0 (not applicable) | 7/7 (100.0%) | 2/2 (100.0%) | 0 |
| T10 | Iterative hybrid | planned | 1909 | 1.000 / 0.750 | 0/0 (not applicable) | 7/7 (100.0%) | 2/2 (100.0%) | 0 |
| T10 | Graph | planned | 1344 | 1.000 / 1.000 | 0/0 (not applicable) | 7/7 (100.0%) | 2/2 (100.0%) | 0 |

Across successfully scored executions, **0 incorrect-current reports** were observed. This safety result belongs to the shared Hydra-assisted executor. It is not evidence that standalone BM25 or vector systems are unsafe, nor that the graph planner uniquely handles missing sources.

## Provider usage and failures

Known provider-reported list cost: **$1.546328** across 16/16 attempts. 0 attempts have unknown cost; unknown usage is never treated as zero spend. These are provider list estimates, not a subscription billing statement.

| Arm | Known reported cost | Calls with unknown cost | Uncached input tokens | Cache-created input tokens | Cache-read input tokens | Output tokens | Thinking tokens (subset) | Model elapsed seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BM25 | $0.415128 | 0 | 8 | 17,891 | 3,840 | 3,201 | 1,305 | 38.67 |
| Dense | $0.354720 | 0 | 8 | 16,823 | 3,840 | 2,118 | 569 | 30.89 |
| Iterative hybrid | $0.407744 | 0 | 8 | 17,372 | 3,840 | 3,224 | 1,167 | 38.65 |
| Graph | $0.368736 | 0 | 8 | 15,954 | 3,840 | 2,816 | 662 | 34.80 |

Provider-accounted input totals: 32 uncached + 68,040 cache-created + 15,360 cache-read. Output totals: 11,359, including 3,703 reported thinking tokens. Thinking tokens are not added a second time.

The 2,048-token limit applies to retrieved evidence, not the entire Claude request. Provider counts include the system prompt, schema, CLI overhead, and caching; the saved cl100k prompt estimate is a separate tokenizer measurement. CLI-reported `num_turns` and full model/iteration usage remain in each observation; a single requested planning step need not equal the CLI's internal turn counter.

Cache warmth was not experimentally controlled, and only one fixed rotation was run. The development graph smoke also warmed its later development prompt. No cost or latency superiority claim should be made from these measurements. The heldout source remains the prespecified four-case subset; development observations are not pooled into it.

| Case | Arm | Failure location | Saved error |
|---|---|---|---|
| T10 | Graph | runtime refresh | {'message': 'Source no longer available: source:fx:2026-W46', 'type': 'MissingEvidenceError'} |
| T10 | BM25 | runtime refresh | {'message': 'Source no longer available: source:fx:2026-W46', 'type': 'MissingEvidenceError'} |
| T10 | Dense | runtime refresh | {'message': 'Source no longer available: source:fx:2026-W46', 'type': 'MissingEvidenceError'} |
| T10 | Iterative hybrid | runtime refresh | {'message': 'Source no longer available: source:fx:2026-W46', 'type': 'MissingEvidenceError'} |

A missing-source runtime refresh failure can be the correct fail-closed behavior; it remains recorded instead of being converted into a successful calculation.

## Interpretation and reproducibility

- These are authored workloads with known direct dependencies, a single model sample per condition, and a small prespecified subset. There is no statistical or universal agent-performance claim.
- Exact adjacency traversal over the same receipts can match native graph retrieval. This comparison tests retrieval against BM25/dense/iterative hybrid, not a unique correctness advantage of Hydra over every other dependency representation.
- Shared currentness checks, recursive execution, and refusal to serve stale/unknown values benefit every arm. Missing-source blocking is reported as a shared safety property.
- Failures and abstentions remain in the attempt counts. Conditional rates should always be displayed with those counts and explicit numerators/denominators.
- The local Claude Code bridge uses the existing authenticated CLI with external tools disabled. It is not a credential-distribution or public-service authentication design.

Source artifacts: `results/agent-test-v1/prepared.json`, `results/agent-test-v1/summary.json`, and each `<case>/<arm>/request.json`, `observation.json`, and `result.json`. Frozen request hashes, source-case hashes, code hashes, raw model usage, rationale, selected aliases, numeric-oracle comparisons, and actual tool receipts are retained there.

Regenerate this report without any model calls:

```bash
.venv/bin/python scripts/summarize_agent.py --input results/agent-test-v1 --output docs/AGENT_RESULTS.md
```

Comparison finished at `2026-11-15T09:59:14.477013+00:00`. This report describes the saved run; it does not rerun or alter the benchmark.
