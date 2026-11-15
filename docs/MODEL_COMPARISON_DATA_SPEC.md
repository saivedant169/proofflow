# Model comparison v4: data and independent outcomes

Status: preparation only; no test selections, model calls or scored execution before the final immutable freeze. This experiment is separate from all earlier experiments. The stopped compact-receipt artifacts remain untouched. Production code is not modified.

## Data and supported workload

Use Chen (2015), [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online%2Bretail), [DOI 10.24432/C5BW33](https://doi.org/10.24432/C5BW33), under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The unmodified raw workbook SHA-256 is `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`. UnitPrice is sterling for every country. Keep the raw workbook private/ignored and export no CustomerID or product descriptions.

Test data comprises **every eligible positive transaction line on the first four distinct eligible dates of March 2011**. Development uses the first two such dates of June 2011. Do not sample rows or replace dates after observing any method output. Eligibility and numeric decoding remain frozen: finite binary64 numeric-cell interpretation, shortest-roundtrip decimal text, positive integral quantity ≤ 1e9, positive price, and exact integer line pence ≤ 1e12; no money rounding. Exclude cancellation-prefixed invoices, blank invoice/country, invalid dates/numerics, countries longer than 64 characters or with prohibited control/reserved prefixes, and values outside supported bounds. Reconcile all month/date exclusion counts and assert selected table sums fit SQLite int64.

Preserve raw XML quantity/price strings, normalized decimal strings, invoice/row identity, country and original timestamp in provenance files. Runtime order tables contain only order_id, region, GBP currency and gross_cents. Refund and FX inputs are explicitly staged; initial refunds are empty and GBP/USD is 1.25. This is not the complete merchant ledger or a claim that these authored corrections occurred historically. Full-day tables use the source/runtime interface, not a claim about the public CSV importer's row limit.

Each date has gross, refunds, net, gross USD, net USD, gross total and net total calculations. Two saved reports give all-country gross/net totals and UK gross/net values. Each adjacent-date pair adds a three-input report containing previous total net, current total gross and current UK net. These are stated values, not an uncomputed percentage/difference. No unused source, dummy report or duplicate payload is added. The test corpus has **39 artifacts / 11 saved reports**; development has **19 / 5**. Date/logical names, useful descriptions, report sections and exact units are fixed before scoring. Require UK rows on each declared date; a preparation prerequisite failure stops the design rather than silently selecting an easier date.

Assert zero source-row and invoice overlap with retail v2 and compact v3, and between the two new splits. Check actual identities, not only distinct month names. The independent audit scans the original workbook, verifies the complete selected-row sets, values and all exclusions, and confirms exported CSV/provenance/manifest agreement.

## Eight single-stage test cases

Let D1–D4 be the selected March dates. Choose exact mutation targets using stable original source-row order and declared bounds, never a method result. Freeze exact IDs, before/after amounts and query text in the fixture manifest. Each case starts from its own fresh baseline workspace. No staged recovery or inherited reader state is included.

| ID | Intervention | Frozen query meaning |
|---|---|---|
| M01 | Add one staged partial refund on D2. | Refresh affected saved reports after the reported refund; preserve reusable evidence. |
| M02 | Change D1 GBP/USD from 1.25 to 1.29. | Refresh affected saved reports after a dated FX correction. |
| M03 | Increase one D3 order quantity by two and change that date's GBP/USD to 1.28. The chosen unit price has exact integer pence. | An order quantity and FX rate were corrected on the same date. |
| M04 | Add a staged partial refund on D1 and increase an exact-pence-priced quantity on D4 by one. | Two distinct dated inputs changed; refresh affected reports across saved runs. |
| M05 | Change the global conversion tool's declared version, keeping its implementation/arithmetic unchanged. | Reassess saved evidence after the conversion-tool version update. |
| M06 | Add three pence to one D2 line total and subtract three from another same-country line, with both positive after correction. | Two source corrections preserve aggregate values; reassess evidence validity. |
| M07 | Withdraw D3 FX only, with no independently stale available branch. | Serve only current evidence and identify reports that cannot be safely refreshed. |
| M08 | Republish all four order sources with reversed row order but identical canonical contents. | Determine whether republishing changed any evidence that needs refresh. |

Refunds are exact integer-pence amounts fixed from the selected row before freeze and bounded by its gross amount. Equal-aggregate patches are authored line-total adjustments, not changes falsely attributed to the raw historical price cells. Queries contain observed events and the user request, not gold affected report IDs or oracle answers. Every method receives the same current input/version facts and report scope.

Two **development-only, no-model** cases use June: MD01 changes a first-date order quantity and FX together; MD02 withdraws second-date FX only. They exercise source/version handling, shared execution, expected refusal and independent truth without paid calls. Development checks do not turn into new scored cases. Fresh dates and patches do not mean unseen task families: source changes, versions, equal values, missing inputs and no-ops intentionally test supported behavior.

## Representation, model budget and controls

Six arms: native graph, exact-flat, BM25, real pinned BGE, iterative hybrid, and full context. Use the original full retail-v2 receipt representation unchanged; no compact encoding, selective description shortening or method-private lookup field. Freeze the shared capped-arm evidence allowance and full-context accounting in the harness protocol before test selection. The graph-derived allowance, if selected, must be stated as adaptive and distinguished from any fixed 2,048-token result. Full context is uncapped and its full provider-billed input must be reported. Exact-flat may tie the graph; no graph-engine superiority follows.

The harness will request one model completion for each of eight cases × six arms: **48 planned calls**, with an aggregate **$10 stop limit** subject to the final approved protocol. No test calls occur before the owner-approved code/data/prompt/model/configuration freeze. No retry-until-success, fallback model, hidden repair completion or dropped failed call is allowed. Preserve provider failures, refusals, actual token/cost usage and any unrun cells after the cap. An overall gate requires all 48 planned cells with known billing. A budget/timeout stop makes the study incomplete: retain unrun cells as missing, without zero-filling a success or accuracy denominator. Do not imply the estimate guarantees completion.

Use identical model/effort/output contract across arms. Isolate each case/arm state. Keep actual safe refresh execution and tool arithmetic common and frozen. This isolates context selection plus model choice; it does not independently prove that semantic retrieval enforces freshness. The missing case has only a missing changed source, preserving the existing batch-refusal boundary without hiding unfinished independent work. Numeric outputs and report states are verified after model-selected actions, not graded from model prose alone.

## Independent truth, primary outcome and freeze

An independent numeric oracle computes current values and availability from raw-validated source data, explicit patches and recipe semantics, never cached outputs or production calculation functions. Independently compare canonical before/after source values to validate observed version transitions. Use a separate receipt-chain provenance audit against current source/tool identities; numerically equal outputs do not establish current lineage. Keep oracle values and affected IDs inaccessible to rankers, prompts and model-facing aliases.

Primary per-cell result: every available saved report is numerically correct and current, all unavailable whole reports are withheld, and no incorrect-current report is presented. Also report fresh affected reports, dependency coverage, model choices, tool calls, unaffected identities, token sizes, actual billed usage, timing and every failure. A report requiring any unavailable input is incomplete; partial claim-slot behavior is outside the whole-report completion metric. Report missing/no-op cases separately so they do not hide correction failures. Distinguish dependency-affected counts from numerically changed counts.

The graph reliability gate is absolute: every recoverable affected report must be fresh and independently numeric/provenance-correct, every unavailable report blocked, and no incorrect-current report. Graph-versus-full-context fresh-report counts are a descriptive comparison, not a substitute for that gate. The primary input-exposure gate is graph at most 50% of the summed actual provider input-token exposure of full context across M01–M07; exclude M08 no-op from the primary ratio and include it only in a secondary ratio. Count provider model-usage totals exactly once and retain actual CLI turn counts; do not fabricate a per-turn breakdown from an aggregate. Graph/exact-flat identical prompt hashes are explicitly reported as paired identical inputs, not an engine advantage. No model may enumerate candidate metadata outside its supplied context.

Before any test selection or model call, freeze the concrete dates, all selected rows, exclusions, raw/transformed hashes, supported recipe declarations, exact patches and query text, source/tool/receipt schema, algorithm configuration, model and tokenizer versions, prompt/output contract, budget policy, arm order, stop conditions and output paths. An independent audit must approve fixture completeness, oracle isolation, same-information context and cost accounting. Preserve all prior experiments untouched. No production edits, model calls or deployment are authorized by data preparation.

## Reproducible preparation

Use `python -m scripts.prepare_model_comparison_v4 --workbook PATH --split dev` and the corresponding `--split test`. Preparation refuses to overwrite an existing split, validates the original workbook hash, and executes no selector, runtime or model. Each split manifest includes exact source and output file hashes, all queries and mutations, and before/after source-patch hashes and changed-row values. Source provenance is immutable; authored corrections remain a separate declared layer.
