# Fixed evidence-budget diagnostic protocol

This diagnostic asks how much of the saved March workload the existing deterministic evidence reader can refresh under two constant evidence limits. It reuses the same eight cases and 39 candidate artifacts per case from the [March model comparison](MODEL_COMPARISON_RESULTS.md). The March 1–4, 2011 fixture uses 4,681 eligible UCI Online Retail rows. The source coverage, schema, authored corrections, and attribution are in the [data specification](MODEL_COMPARISON_DATA_SPEC.md).

The two caps are **4,096 and 8,192 cl100k_base tokens of receipt evidence**. Both were chosen before any fixed-budget retrieval or refresh observation on these cases. Every capped policy receives exactly these limits, including the missing-source and no-op cases. These are maxima, so a policy may return less evidence. No case determines or changes its own allowance. The separate [retail experiment](RETAIL_V2_RESULTS.md) retains its fixed-2,048 findings, and the March model comparison retains its adaptive-budget findings. The earlier adaptive results were public when this diagnostic was designed.

## Inputs and policies

Reuse the committed March request inventory, eight task texts, changed-version aliases, full-v2 JSONL corpora, and initial records. The `freeze.json` inventory under `fixtures/fixed_budget_diagnostic/` binds the published March files and the code, inputs, environment, oracle expectations, and all 88 planned cells below. Commit the freeze and implementation before starting any measured cell. The runner verifies that the relevant files match the explicitly approved Git revision and the freeze, both before and after execution. The freeze builder only verifies saved inputs and constructs the independent oracle. It does not run a selector, reader, refresh, or embedding inference.

- **Graph** uses native HydraDB FLOW traversal from the frozen changed raw versions. Rebuild the frozen immutable artifact store and its source, tool, artifact, and execution nodes and receipt edges in a new local graph namespace. Verify that exported evidence matches the frozen corpus exactly and that freshly discovered graph membership equals the frozen native membership. Order native members by witnessed depth and alias, with any remaining native members sorted by alias, as in the March harness. A discovery or reconstruction failure remains a failure.
- **Exact flat** traverses the same direct dependencies in the complete flat corpus and orders the exact closure by witnessed depth and alias. This is the structural control.
- **BM25** uses the frozen lexical tokenizer, `k1=1.5`, `b=0.75`, and exact changed-ID seeding.
- **BGE** uses the same locally cached BGE-small-en-v1.5 ONNX model and model tokenizer. Freeze the model-file hashes from the March study. Use the same 384-token chunks with 64-token overlaps, max chunk cosine, and exact changed-ID seeding.
- **Iterative hybrid** uses the frozen reciprocal rank fusion constant of 60, three additions per round, and the corpus-size round ceiling. The search frontier uses only the reader's already witnessed paths. Run the policy separately for each cap.
- **Full context** supplies every corpus record in original alias order once per case. It is an uncapped reference.

For the five capped policies, use the existing whole-record packer, counting exactly the UTF-8 `EvidenceRecord.render()` JSONL text as encoded by the pinned cl100k_base tokenizer. Count a single LF between records and no terminal LF, including for the saved diagnostic contexts. Continue after an oversized record. No summary, truncation, or method-specific record field enters the evidence. Measure the shared query and changed-version notification text separately. The receipt cap excludes that text, the model prompt, the schema, and all provider overhead.

## Schedule and executor

There are **80 capped cells** across cases M01–M08, two limits, and five policies, plus **8 uncapped reference cells**. Use the original ascending case order and, within each case, rotate the original six-arm list left by the zero-based case index. For each capped arm process 4,096 then 8,192. The uncapped arm has one cell in its rotated slot. Use the same order for planning and execution. The first phase records all contexts and deterministic selections before any refresh begins.

The existing `read_affected` reader receives only packed evidence and the common changed-version aliases. It can follow a path only through presented records. Pass exactly the ordered aliases it returns to the existing shared refresh executor and v4 scorer. Every cell gets an independent writable manifest and a unique local HydraDB namespace reconstructed from the same frozen case snapshot. The graph discovery namespaces are separate from these execution namespaces. Refresh may recursively rebuild dependencies that the reader did not select. Distinguish evidence coverage and reader selection from post-refresh report completion.

Freeze expected affected artifacts and reports, unavailable reports, unaffected identities, and expected-value digests from the independently decoded March provenance, declared patches and arithmetic. The v4 scorer rederives these expectations, verifies the original immutable prestate and checks numeric values and current receipt chains for every candidate head. Oracle results are reserved for scoring. The denominator for each arm/condition is **32 recoverable affected reports**, split across M01–M06. The separate safety obligations are **4 unavailable reports** (M07) and **52 preserved unaffected report identities** (across all eight cases). M08 must yield an empty plan and preserve its original heads.

## Outcomes and failure handling

- Report retrieved affected-artifact coverage and the deterministic reader's affected-artifact true positives, false positives and false negatives. Publish exact packed JSONL, tokens used, retrieved and selected aliases, and context hashes for each cell.
- Primary outcome is independently verified fresh affected reports out of all 32 eligible across each arm/condition, with case-level counts. Also report whole-case success, verified unavailable blocks, observed missing-source refusal, verified unaffected identities and incorrect-current reports.
- A cell passes whole-case correctness only when all available artifacts (including reports) are current and independently numeric/provenance-correct, every unavailable artifact is blocked, unaffected artifact identities and every original immutable record are preserved, and there is no unexpected execution or inspection error. An empty M08 plan is required. For M07, distinguish an expected refresh refusal from a safe empty selection. Neither M07 nor M08 can add to the fresh affected report numerator.
- An arm/condition clears the absolute report gate only with all eight cells successfully scored, 32/32 fresh affected reports, all eight whole cases correct, 4/4 unavailable reports blocked, 52/52 unaffected report identities preserved, and zero incorrect-current reports. Diagnostic completion requires all 88 cells scored and freeze integrity verified. Report failures or unobserved cells explicitly and keep their planned obligations in the denominators. Track observed counts with their observation coverage.
- Each planned cell gets at most one planning attempt and one execution attempt, without fallback or automatic retries. Reserve a new output directory and persist attempt state before each step. Preserve partial contexts, rows, errors, and private executor artifacts. Record shared setup attempts and errors separately. Dependent cells remain unattempted with the setup error attached. A resource preflight failure fails the integrity gate even when the committed source files still match.

## Scope

The diagnostic repeats the March test inputs with a fixed receipt budget and a deterministic local reader. It compares the retrieval policies and shared refresh behavior under those conditions. All arms use HydraDB-assisted currentness and refresh. Exact flat can structurally tie native graph, and the uncapped reference is evaluated separately. There is no new held-out workload or provider invocation. Token counts measure serialized evidence size. They cannot establish model accuracy, provider input exposure, cost, or latency savings.

## Run the frozen diagnostic

Use the pinned loopback HydraDB service, the March benchmark dependency versions, the cached cl100k_base vocabulary and the cached BGE snapshot named in the freeze. The runner reconstructs execution state from the tracked initial records. The original March SQLite stores and graph history are unnecessary.

```sh
python -m scripts.fixed_budget_diagnostic run \
  --expected-revision FULL_FROZEN_COMMIT_SHA \
  --private-output /absolute/path/to/new/private-execution-directory
```

The default public result directory is `results/fixed-budget-diagnostic-v1/`. A reproduction can provide a new directory with `--output`. Each public cell records its exact context and per-artifact result ledger. Full post-refresh snapshots, SQLite stores, blobs and raw scoring traces go in the private directory. Snapshot and audit hashes link the public ledger to those artifacts. Fresh invocations generate new raw IDs and wall-clock values.
