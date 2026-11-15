# ProofFlow pilot benchmark specification

Status: **predeclared design; no results yet**. Version: `pilot-v1`. Prepared 15 November 2026 before executing comparisons. Freeze the final case manifest, model revision, token budgets, baseline parameters, and code revision before opening the test results. This file is a methodological contract, not a promise that ProofFlow will win.

## Claim and boundaries

Test whether traversing recorded execution dependencies supplies more complete and precise current evidence than BM25 and dense retrieval alone for a small changing-data analytics workload. Test downstream numeric correctness separately by executing refreshes and comparing with an independent clean recomputation.

The workload is authored commerce data and staged mutations. Tools perform actual local calculations; this is not production customer evidence. Report at most twelve independent test scenarios initially, not repeated seeds as additional tasks. A graph algorithm reproduced with a flat adjacency list or recursive SQL is expected to tie on correctness; this is an explicit control, not an embarrassing omission.

No user interface work depends on a claimed victory. The gate is measured useful advantage over both a strong lexical and a real embedding baseline, with correct outputs and transparent failures.

## Supported execution model

Source versions, tool versions, executions, artifact versions, and report sections have scoped stable identities. Executions record direct consumed inputs and produced outputs. Reports may consume artifacts from earlier runs. Mutations create new source/tool versions rather than editing historical evidence. Refresh rebinding replaces stale upstream artifact handles before downstream executions run.

Use six to eight real typed analytics functions and two guided reports. Add held-out report compositions through the same production tool interface. Do not insert test scenario labels, expected affected IDs, or gold routes into the production request.

## Separate two ground truths

1. **Potential revalidation set:** the captured dependency descendants of the changed source/tool versions, restricted to the scenario's candidate artifacts/report scope. Author each case's expected direct-input facts independently of the production graph functions. Compute the oracle closure from that specification using a separate small implementation. Every expected direct edge must agree with actual execution receipts; disagreement is a dataset/instrumentation failure, not a retrieval miss to hide.
2. **Value-change set and final values:** rerun the supported calculations from current sources in a clean workspace, without the lineage retrieval function. Compare normalized numeric outputs and artifact values. A source may change while an aggregate stays numerically equal; that result still belongs in the revalidation set.

Never use the full-recompute hash diff as the sole oracle for dependency affectedness. Never use the Hydra traversal under test to generate its own gold labels.

## Shared information envelope

Every arm receives the same artifact and receipt records: human-readable title, description, producing function/SQL description, scope (region/period/entity), source/artifact/tool version IDs, parameters, direct input IDs, and output IDs. Dense embeddings are computed from this same text, not a shorter sanitized description. BM25 indexes the same text. Current source/version metadata is updated for all indexes after each mutation.

The query includes the requested report scope, natural-language change description, exact changed IDs, and old/new version identity. Exact ID lookup is available to all arms. Do not anonymize only baseline IDs or remove relationships from baseline documents. Do not privilege ProofFlow with resolved scope while forcing baselines to infer it from prose.

An ingestion/export checksum proves each arm consumed the same record set. Retrieval may not inspect gold labels or clean-recompute outputs.

## Conditions

| Condition | Purpose |
|---|---|
| `bm25` | Strong lexical retrieval over complete records; standard ID-aware tokenization, tunable BM25 parameters on development only |
| `dense` | Real local sentence embedding model over the identical records; normalized dot-product ranking |
| `hybrid` | Reciprocal-rank fusion of BM25 and dense; fusion constant and any threshold selected on development only |
| `direct_id` | Direct dependency/source-ID matching; strong simple baseline for one-hop cases |
| `iterative_hybrid` | Budgeted iterative retrieval with the same exact-ID facility, expanding query evidence from retrieved records; no gold routes |
| `graph_direct` | Hydra direct dependencies only; transitive-structure ablation |
| `graph` | Actual Hydra multi-hop dependency traversal on the runtime path |
| `exact_flat` | Correct recursive traversal over the same direct records; representation-equivalence control |
| `full_recompute` | Independent numeric correctness oracle and execution-work ceiling |

The initial implementation may stage deterministic selection/refresh results before integrating an LLM. Label those results **retrieval-and-execution**, not end-to-end agent success. A later agent comparison must call the same model, system prompt, executor, retries, context budget, and task interface for BM25, dense/hybrid, and graph.

Do not silently relabel TF-IDF, random embeddings, or bag-of-words vectors as the dense/vector condition. If the embedding model cannot be downloaded or executed, the vector gate is incomplete.

## Budgets and parameter selection

Use a predeclared context-token ladder rather than selecting a top-k after viewing test labels. Initial ladder: **512, 1,024, and 2,048 context tokens**, plus an all-record diagnostic. Count rendered record text and provenance headers using one real tokenizer, pinned in the run manifest. If the entire corpus fits within a budget, report that; do not add irrelevant records merely to force a failure.

Use deterministic whole-record packing, identical serialization and tie-breaks. Skip an oversized record and continue packing smaller ranked records, rather than stopping at the first oversized item. A record that cannot fit any budget is a manifest warning; do not silently give only the graph a compact summary.

The same record may support several paths; deduplicate it consistently. Graph path explanations count toward its context. Report selected records, selected token count, full available corpus tokens, and coverage at every budget. Graph over-budget omissions count as misses.

Tune lexical parameters, embedding choice (if more than one is tried), fusion and inclusion thresholds only on the six development scenarios. Select the main budget using a documented application constraint, not whichever budget maximizes the graph's test advantage. Publish the entire ladder regardless of the main-budget result.

When evaluating iterative retrieval, cap total evidence returned across all rounds using the same context budget, and report retrieval calls separately. Exact lookups and repeated evidence are counted according to a fixed documented rule; neither arm gets free hidden context.

## Development scenarios (six)

These establish ordinary behavior and select parameters, not headline results.

| ID | Change | Required property |
|---|---|---|
| D01 | Correct an order amount in one region/period | Direct affected calculation |
| D02 | Correct an exchange rate | Multi-hop converted revenue |
| D03 | Add a refund | Shared intermediate used by two reports |
| D04 | Change support volume only | Unrelated revenue branch remains reusable |
| D05 | Change a source row without changing the aggregate | Revalidation and numeric-change labels differ |
| D06 | Replace a metric implementation version | Tool-version dependency is respected |

## Evaluation scenarios (twelve)

Exact values, IDs, dataset snapshots and expected direct edges must be finalized in a hashed case manifest before the first evaluation run. Each case starts from a clean independent state; no test feedback updates retrieval settings or learned policy.

| ID | Held-out scenario | Main stress |
|---|---|---|
| T01 | Order correction in a different scope from development | Correct entity/period binding; one-hop baseline should be competitive |
| T02 | Refund correction propagating into a cross-run report composition | Transitive reuse across executions |
| T03 | Exchange-rate correction affecting several downstream metrics | Shared multi-hop closure |
| T04 | Company summary reusing independently created regional artifacts | Fan-in and replacement binding |
| T05 | Support-only correction with semantically similar revenue text elsewhere | Precision and unrelated branches |
| T06 | Change in an older or other-region partition | Same names, different scope |
| T07 | Two source corrections in one scenario | Union of closures and deduplication |
| T08 | Source correction whose final metric stays numerically equal | Conservative validity versus changed-value oracle |
| T09 | Tool-version change used by more than one report | Non-data prerequisite |
| T10 | Missing required source or failed calculation | Abstain/block rather than reuse stale output |
| T11 | Application restart between mutation and refresh | Evidence/artifact reconstruction; graph state route reported |
| T12 | New composition assembled through the production agent/tool interface | Composition generalization; no injected gold route |

T12 can initially run through an independently declared executable request only for the deterministic pilot. It cannot be counted as an agent-composition success until the actual production agent chooses the operations. The manifest must preserve that distinction.

No-op source changes and unaffected cases remain in the report even when they favor baselines. Case replacement after seeing results requires a new version and fresh held-out cases; preserve and report the original failed run.

## Metrics

**Retrieval:** potential-revalidation precision/recall/F1, exact affected-set match, complete-path coverage, selected tokens, returned records, and retrieval latency/calls. Handle empty gold sets explicitly: exact-match success requires selecting nothing; show false-positive count rather than hiding empty cases in averages. Break out one-hop, multi-hop, and cross-run cases.

**Execution:** full normalized numeric equality with the independent oracle, stale results served, blocked/unknown answers, actual tool executions, unnecessary executions, unchanged artifacts preserved, and end-to-end time. A correct abstention is not a completed report; present both separately.

**Agent experiment:** fresh complete answers and actual provider token usage, with identical model and generation/execution budgets. Do not grade by substring occurrence or a matching number in unrelated prose. Structured metric slots must match the expected value, unit and scope.

**Durability:** application restart and database restart are separate checks. If graph state is reconstructed from a journal, label journal durability and replay explicitly; do not call that database persistence.

Do not claim a broad statistical result from twelve scenarios. Report paired counts, task-level differences, raw cases and uncertainty/limited scope. Repeated runs measure stochastic sensitivity, not additional independent cases.

## Required raw record and manifest fields

Manifest: benchmark/spec version and SHA, case manifest SHA, code revision, source fixture SHA, record serialization version, engine version and storage mode, database namespace, embedding model ID/revision, tokenizer, corpus checksum, dev tuning history, selected parameters, budgets, execution caps, graph path implementation and fallback policy.

Per result: scenario/split/arm/budget, query, changed source/tool IDs, returned record IDs and evidence tokens, expected revalidation IDs, predicted revalidation IDs, gold value changes, new numeric outputs, output equality checks, executed tool calls and arguments, source/graph versions, latency, errors, abstention reason and model usage where applicable.

## Decision gate

Before UI work, actual Hydra-backed graph execution must match the full-recompute oracle on supported scenarios and show useful performance versus **both** BM25 and a real dense retriever. A gain may be complete fresh answers under the same context/work budget or less repeated work at comparable correctness. A top-k recall win without downstream correctness is insufficient.

If graph and fair retrieval tie, report the tie. If an exact flat cache ties, report that expected result and distinguish structural value from storage-engine exclusivity. If the corpus is too small to need selective context, do not manufacture filler; narrow the claim or reconsider the workload with a newly frozen evaluation version.

## Core adapter requested from implementation

The harness needs a resettable scenario factory, executed report generation, complete record export, source/tool mutation, graph-affected query, selection-driven refresh returning actual calls/values, independent full recompute, and restart support. Gold dependency specifications remain in evaluation data and never enter the runtime graph query.

No results are asserted by this document.
