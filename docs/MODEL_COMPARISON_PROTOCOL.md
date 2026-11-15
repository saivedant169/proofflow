# Prospective v4: model planning with full-context and exact-flat controls

Status: preparation only. No paid model invocation or fresh test outcome is authorized yet. Development used an isolated worktree at `500f3aeaad373455ddb81c45962ecd82e882c1c0`; the new evaluation files are integrated onto `8f5b9dec7c162a617354775f3014fa3e9032e389`. The separate source-publication recovery probe passed its 15 checks locally and in Linux CI. Production code and earlier studies remain unchanged. The stopped compact-receipt experiment is not part of this study.

## Question and fixed scope

Can one Fable 5.2/high planning invocation select enough real saved artifacts for safe refresh with less provider input exposure than full context? This is a small deterministic-workflow/model-selection study, not workflow invention, learning, independent vector safety or a database-engine comparison.

The data specification owns eight single-stage March 2011 cases, using all eligible positive whole-pence rows from its first four eligible trading dates. June's first two dates supply development only. No earlier fixture rows are reused. Four-date reports produce 39 authentic artifact records, including cross-date reports; there are no filler records. Cases cover local refund/FX corrections, overlapping and multi-date changes, global tool replacement, equal-value input changes, missing source and no-op. Exact cases, row patches, query text and output expectations freeze before any test method observation.

## Six retrieval arms, identical planning and execution

1. Native Hydra complete affected closure (`graph`).
2. Exact flat traversal of the same recorded direct metadata (`exact_flat`).
3. BM25 with frozen v2 parameters and exact-ID seeding (`bm25`).
4. Actual pinned BGE embeddings/chunking with identical exact-ID seeding (`dense`).
5. Frozen iterative BM25/BGE hybrid (`iterative_hybrid`).
6. Every candidate record (`full_context`).

Use unchanged full-v2 `EvidenceRecord` serialization and deterministic aliases for every arm. All see the same candidate corpus, source/tool version notifications and scope. Refresh the semantic indexes after each mutation. Graph membership must come from native Hydra, with local ordering cost reported. Exact-flat is expected to produce the same ordered evidence as graph; publish their matching prompt hashes as independently sampled structural twins, not an engine advantage.

The serialized complete graph closure determines that case's evidence allowance, including zero for a no-op. Graph, exact-flat, BM25, BGE and iterative hybrid use that same allowance and unchanged whole-record packing. Full context is uncapped and its true size is published. This is an adaptive matched-evidence comparison, not a fixed-context experiment. It is separate from full model input exposure: task/schema/system/CLI and caching overhead are measured from provider counters.

Each model request contains only the common task, observed changed-version aliases and selected JSONL evidence. The allowed-ID set validates the response locally and is not separately enumerated in the prompt/schema. No oracle values, gold routes, correct plans, hidden corpus list or other arm's answer enters the request. Prompt, schema, model/effort settings and validation are identical. External tools, MCP, memory/project instructions and session persistence are disabled for planning.

Every arm uses the same existing Hydra-assisted currentness and recursive refresh executor. A model failure, malformed plan or abstention performs no refresh; inspect the unchanged state and retain its outcome. Valid selected IDs are bound to the exact request/context hash and mapped only to presented artifact IDs. Expected missing-source refusal stays visible and is correct only if all available outputs are fresh/correct and every unavailable report is withheld. Unaffected immutable identities must remain preserved. The independent numeric and receipt-chain provenance oracle is scorer-only; runtime-claimed currentness is recorded separately.

The scorer also verifies a complete, hashed common pre-execution snapshot against the actual initial store, then requires every existing immutable record's metadata and value to remain byte-equivalent in the poststate. A self-consistent rewritten receipt cannot satisfy this anchor. Independent canonical mutation staging supplies the oracle's expected sources; observed runtime changes cannot set its gold denominator.

## Attempts, scheduling and isolation

There are exactly **48 planned cells: eight cases × six arms**. Each cell receives at most one harness invocation, no harness retry and no fallback model. Rotate the six-arm order by the preregistered case index. The case order and rotation are fixed before observations. Plan all cells before applying any model's refresh selection; private manifests isolate execution and the original immutable graph supplies the common starting state.

“One invocation” does not guarantee one backend inference request. Claude Code may perform internal structured-output turns or retries that the harness cannot disable. Record actual `num_turns`, raw envelopes and aggregate usage, and describe the study as single-shot planning at the harness level. No follow-up request or model-visible correction is supplied by the harness.

Each invocation has a 90-second timeout and a new isolated process group. Preserve stdout/stderr and partial output, terminate the process group on timeout, and stop launching cells. Local cancellation does not prove remote generation or billing stopped. A persisted started-attempt marker prevents automatic resumption or rerunning a possibly charged invocation.

## Cost and provider-token accounting

The study has a **$10 aggregate soft stop** based on reported provider list-cost estimates. Before each invocation persist its reservation and configure `max_budget_usd = min(1.00, remaining reported budget)`. All attempts—including malformed plans, abstentions and provider errors—consume this same allowance. There are no separately exempt paid developer checks. Local `--help`/version checks are not model invocations.

This one study has the fixed identity `proofflow-model-comparison-v4-2026-11-15` and the single ledger directory `/Users/saivedanthava/Desktop/HydraDB/private_experiments/model_comparison_v4/study_state`. Changing the command-line ledger path is rejected; the ledger also retains the two development-run starts. This location remains the same when the new study files are integrated into the main repository. A new path is not a way to restart this experiment's quota or spending allowance.

The CLI cap is not a demonstrated hard bound on in-flight spending. Record actual overshoot without clipping, and stop before the next invocation. Unknown/malformed billing, usage, provider identity or an infrastructure error stops further launches immediately. An interrupted or pending attempt is an unknown charge, not zero and not an invitation to retry. Known cost is retained even if another usage field is invalid.

Use one validated authoritative aggregate view, `modelUsage`, and preserve raw top-level `usage` for audit without adding it again. Require all counters explicitly; no silent zero defaults:

- `inputTokens`: uncached input.
- `cacheCreationInputTokens`: cache-write input.
- `cacheReadInputTokens`: cache-read input.
- `provider_input_exposure = inputTokens + cacheCreationInputTokens + cacheReadInputTokens`.
- `outputTokens` separately; thinking tokens are not added again.

Validate every model entry, not just recognized entries. Token counters must be finite nonnegative integers, excluding booleans; all canonical models must match the requested Fable version. Cache lifetime subdivisions must not be added on top of cache creation. Preserve every provider turn's aggregate counters even when the plan is rejected.

Require finite nonnegative reported costs excluding booleans. Reconcile top-level `total_cost_usd` with summed model `costUSD` using a preregistered absolute tolerance of $0.000001 plus relative tolerance of 1e-9. Missing, malformed or inconsistent fields mean unknown accounting and stop. These are reported list estimates, not verified subscription charges or a promise of a bill reduction.

## Prospective outcomes and nonvacuous gates

All 48 planned cells remain in the table. Record attempted, failed, abstained, unattempted and unscored states explicitly. A stopped/incomplete study cannot pass the overall gate; do not fill unknown outcomes or charges with zeros. All planned recoverable affected reports form the report denominator, including model failures. No rate over successful executions alone may be presented as the primary result.

The **absolute graph reliability gate** requires every recoverable affected graph-arm report to be current and independently numeric/provenance-correct, every unavailable report blocked, and zero incorrect-current reports across all eight graph cells. All relevant artifacts and unaffected identities are also audited. Graph fresh-report count at least full-context count is a descriptive relative comparison, not a sufficient gate: both methods returning no useful work must not pass.

Every graph cell must also have a schema-valid model response. Recoverable cases require a non-abstaining executable selection and absolute complete recovery. The no-op requires an empty selection with `abstain=false`. The frozen missing-only case permits either an explicit valid abstention with an empty selection, when the independent oracle confirms no recoverable affected reports, or a valid selected plan that produces the expected missing-source refusal. Invalid JSON and unknown IDs fail model-task success even if unchanged state is safe. Publish model-task success, safe abstention/refusal and semantic endstate separately; unavailable and no-op reports do not count as fresh affected completions.

The **primary efficiency gate** is total provider input exposure for graph divided by total provider input exposure for full context, summed over all planned **non-no-op** cases, at most 0.50. Publish the ratio including the no-op separately. Both ratios require complete known usage for their planned cells; the overall gate requires all 48 cells billing/usage-known and scored, plus the absolute reliability gate. Report receipt-only ratios separately. Do not infer latency or dollar savings from token exposure alone.

For every arm and case publish fresh affected/eligible reports, whole-case success, refusal/abstention, incorrect-current claims, preserved unaffected IDs, planned versus actual calls, input/cache/output counters, provider cost, retrieval/index/model/refresh/inspection times and errors. Full-context and exact-flat losses are first-class outcomes. One sample per cell cannot support statistical generalization or unique graph-engine superiority.

## Preparation, freeze and authorization

1. Prepare code/spec/fixtures and independently audit aliases, version transitions, arithmetic and provenance. Production selectors remain unchanged.
2. Perform at most two **no-model June dry runs**. They may validate context creation, prompt hashes, spend/usage parsing with local test doubles and the common executor/oracle. Any deterministic proxy selections are labeled harness checks, never model outcomes. No paid development request is authorized.
3. After the separate recovery audit, integrate and commit the final code/spec/fixtures/configuration, dependency and model-file hashes, prompt/schema/CLI flags, cases/order and output paths. The first commit freezes the integrated code before any March method preparation.
4. Root may explicitly authorize preparing frozen March requests after that code freeze. Save exact corpus/context/request hashes and independent original manifests before any paid invocation. No test outcome may drive a method change.
5. Root commits the final prepared manifest and explicitly authorizes the paid run. Require the approved exact revision, matching code/data/model/request hashes and a clean tree before its first invocation. Start/end integrity checks invalidate a changed run. Use new output directories; preserve every failure.

The paid-run guard verifies that `prepared.json` belongs to this repository and its exact bytes match the tracked Git blob at the approved revision. It checks every prepared artifact's inventory, path and hash; binds embedded case metadata to the hashed case file; validates request bytes, prompt and context before each reservation; and repeats the prepared-manifest/artifact and code/data/model checks after execution.

No production merge, deployment, paid call or automatic continuation after a spend/infrastructure stop is authorized by this document. Estimated preparation is 60–90 minutes; the 48 sequential timeout bounds alone allow up to 72 minutes, plus preparation/scoring, if a later paid run is approved.
