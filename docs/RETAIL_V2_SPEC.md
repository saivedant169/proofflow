# Retail v2: external transactions and complete dependency execution

Status: preparation protocol, **no scored results at authoring**. Protocol version `retail-v2-1`. The original pilot, its fixtures, production runtime and retrieval implementations remain unchanged. This is a new evaluation, not a revised score for v1. No model calls or deployment are part of this protocol.

## Question and prespecified gates

Test whether the existing complete Hydra dependency closure supplies enough evidence to finish supported refreshes on externally sourced transaction values and new workflow compositions. The primary condition uses the production closure without a 2,048-token truncation. Completion must equal the full-context control on every report with available inputs, with unavailable outputs correctly blocked. The **aspirational efficiency gate** is `sum(graph evidence tokens) / sum(full-context evidence tokens) <= 0.40`, equivalently mean graph tokens at most 40% of mean full-context tokens over the same cases. Both gates must be reported as pass/fail, never assumed or used to remove inconvenient cases.

Publish the primary ratio of total tokens and, as a separate diagnostic, the mean individual per-case context fraction, including all ten cases. Also report both separately for nonempty revalidation cases so a no-op cannot conceal high context use. Report every case, execution error, incomplete report and fixed-budget miss. A correct exact flat dependency implementation should tie the graph's correctness. This experiment cannot establish database-engine exclusivity, statistical superiority, or improved performance from learning.

## Source and transformation

The source is Daqing Chen's **Online Retail** dataset, [UCI record](https://archive.ics.uci.edu/dataset/352/online%2Bretail), [DOI](https://doi.org/10.24432/C5BW33), distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The official workbook contains 541,909 transaction lines, with prices denominated in sterling. Source ZIP and workbook SHA-256 values are pinned in `proofflow/eval/retail_data.py` and the fixture. Raw files remain in ignored `.cache/retail_v2`; committed CSVs/provenance omit CustomerID and product descriptions. `fixtures/retail_v2/DATASET_NOTICE.md` supplies attribution and change disclosure.

Interpret numeric XLSX cells through finite IEEE binary64 and their shortest round-trip decimal string, as normal workbook readers do. Preserve original quantity and price XML strings. Require positive integral quantities, positive prices, valid countries, and `Decimal(quantity) × Decimal(normalized price) × 100` to be exactly integral and within the existing CSV amount bound. There is **no monetary rounding**. This is a frozen source-decoding policy, not verification of historical prices. An independent reviewer verifies examples including `2.5499999999999998 → 2.55` and all selected line totals without importing the normalization function.

Cancellation invoices and nonpositive/invalid rows are excluded. Retain all eligible lines of selected invoice groups; do not imply that excluded lines are part of a complete invoice ledger. Select groups in SHA-256 order with the fixed salt in the fixture, skipping groups that would exceed 160 selected lines per partition. Record eligibility/drop counts and selected original row numbers. This is a positive-sales sample, not complete merchant net revenue or a representative customer sample. Empty initial refund and ticket sources mean no such observations were supplied; do not fabricate support activity. GBP-to-USD rates and later corrections are explicitly staged assumptions.

## Split and workflow declarations

- Development partition: December 2010; four cases `RD01`–`RD04`.
- Held-out partitions: February, May, August and November 2011; ten cases `R01`–`R10`.
- Invoice IDs must not overlap selected partitions. Region selection is deterministic among present countries, not chosen for a retrieval outcome.
- Each dated partition creates separate gross/refund/net artifacts, **parallel gross and net USD conversion branches**, totals, and two briefs reusing earlier-run artifacts.
- Three later reports each consume three artifacts across adjacent selected snapshots: prior net total, current gross total and current country net value. These cross-partition compositions are absent from development.

The existing `convert_to_usd` function accepts a monetary-region value through its port named `net`; the new gross branch passes a valid gross monetary value and labels all outputs as gross. It does not relabel gross as observed net revenue. All recipes are declared requests and executed by the existing typed tools. This is not evidence that an LLM discovered these workflows.

## Frozen held-out cases

| Case | Staged intervention | Required distinction |
|---|---|---|
| R01 | Increase one February line's quantity | Both monetary branches and cross-run descendants |
| R02 | Increase one May line's unit price by one penny | Quantity-sensitive line subtotal |
| R03 | Add a staged August refund | Net descendants change; gross branch remains reusable |
| R04 | Replace November's illustrative GBP conversion rate | Partition-specific conversion dependencies |
| R05 | Offset two February same-country line amounts by one penny | Revalidation without aggregate value change |
| R06 | May refund plus November quantity correction | Union of distinct closures and shared-work deduplication |
| R07 | Remove August's FX source | Block affected outputs; preserve other snapshots |
| R08 | Replace the conversion tool version, same arithmetic | Broad non-data invalidation; no hidden exclusion if expensive |
| R09 | Reorder identical May rows before canonicalization | Identical source versions and zero recorded runtime tool calls |
| R10 | Correct November quantity, then reopen application | Persistent evidence and replacement binding |

All reports and metrics from the four held-out partitions remain in candidate scope. The change description, exact changed source/tool version identifiers, scope and indexed receipt records are shared across all arms. The common executor accesses the same underlying source inputs; raw source tables are not an extra uncounted context channel. Only returned serialized evidence counts as retrieval context. No expected affected IDs, correct outputs or labeled routes enter inference. The independent direct-input closure oracle operates on declarations; the value oracle uses separate Decimal arithmetic over current sources. Mutations are controlled experiments, not historical incident observations.

Determine expected change roots independently: compare canonical source values before and after each declared intervention, including deletion, and separately compare declared tool-version identity changes. **Assert that actual runtime version transitions match this independently expected set** before mapping their previous immutable IDs to the closure oracle. Do not let a missed runtime transition or an unnecessary no-op transition define its own gold labels. R09 canonicalizes reordered rows to the original input and therefore must produce no changed versions and an empty revalidation set. Its zero-work assertion concerns recorded runtime tool calls, not hidden preprocessing or validation work. R07 removes only its FX source: all dependent conversions/consumers are unavailable, while independent artifacts remain available. Preserve one ordinary `runtime.refresh` batch per arm. An R07 refusal is acceptable only as the exact expected `MissingEvidenceError` for `Source no longer available: source:2011-08:fx`, with every available artifact current and numerically correct and every unavailable artifact withheld. Record that refusal explicitly; unexpected errors or unfinished available work fail the primary correctness gate.

## Conditions and budgets

1. **Production graph closure:** every artifact returned by actual native Hydra traversal; no evidence-budget truncation.
2. **BM25, dense BGE and iterative hybrid:** same records and exact-ID facility, each evaluated at (a) that case's actual graph-context token count, and (b) fixed 2,048 tokens. A zero graph budget is a disclosed no-op case, not an omitted denominator.
3. **Exact flat closure:** same direct records and information; unbounded and, if the runner publishes budgeted controls, the identical packing rule.
4. **All-record/full-recompute control:** complete evidence and independent fresh numeric evaluation. Include an all-record retrieval diagnostic for every baseline if inexpensive; it should remove context incompleteness.

Freeze the existing BGE model/files, tokenizer, BM25 parameters, iterative query policy, record serialization, tie-breaking and packing. Every arm receives identical full records; no graph-only compact rendering. Token counts include complete rendered evidence and headers. Graph selection may use local ordering only on members returned by Hydra, and its time includes that ordering. Baseline indexes are refreshed after each mutation. Do not introduce filler records to force retrieval failure.

All arms use the same **Hydra-assisted currentness and recursive refresh executor**. Isolate evidence-selection effects from shared safety behavior; publish refresh and inspection graph-query counts separately. Execute actual tool calls and verify amount, currency, country and period, currentness, missing-source refusal, replacement binding, immutable unrelated outputs and no-op behavior. Unresolved reports are failures of completion, not answers served. Smaller work counts are not a gain when completion is lower. No deterministic result is labeled agent success.

## Freeze, run and reporting

The preparation command may validate workbook integrity, source decoding, fixture schemas and the four development cases. It must never score held-out conditions. Keep production algorithms frozen; any preparation defect corrected before freeze is recorded. The root agent must commit the reviewed protocol, source hashes, transformed files, case declarations, independent oracle, runner, immutable configuration, code/file hashes and actual model-weight hashes **before the first scored held-out execution**. Use a clean committed revision and a new output directory; retain original failures.

Run the ten held-out cases once with no feedback updates and no post-result tuning. A transport failure remains visible. A necessary infrastructure repair receives a new revision and explicit rerun disclosure, not silent replacement. Freeze per-case graph budgets before running comparator execution; the graph cannot change its budget after seeing a baseline result. Compare every planned case; an aborted case fails the primary completion gate rather than disappearing from its denominator.

Keep raw evidence contexts, selections, source versions, calls, output checks, token usage and failures. Report the positive-sales sampling limitation, staged corrections, deterministic recipes, no-op denominator, exact-flat tie, shared executor, and absence of production-customer validation. The fixed 2,048-token diagnostic is separate from the variable graph-matched budget experiment.

Time box: approximately 2–3 hours for preparation, independent review, development verification, freeze, one scored run and report. If integration cannot finish within the bound, preserve the existing submission and label v2 incomplete. Public deployment remains on hold for the user.
