# Interface verification ledger

Design references: `frontend/design/workspace-concept.png` and `frontend/design/change-source-concept.png`, both generated using the built-in image-generation tool. Implementation: React 19.3.1 and Vite 8.3.8. `npm run build` passes TypeScript and the production build.

Browser verification used the built-in IAB, controlled by the parent agent to avoid concurrent browser operations. The frontend agent used `view_image` on both accepted concepts and the latest implementation screenshots in the same QA pass. Desktop was checked at the concept's 1536×1024 CSS viewport and mobile at 390px wide. An initial IAB screenshot was scaled to 1298px despite the 1536px DOM viewport; later final captures preserve the full width. No Playwright fallback was needed.

Final reference captures in `evidence/ui/` are `workspace-final.jpg`, `source-drawer.jpg`, `workspace-stale-final.jpg`, `workspace-refreshed-final.jpg`, `evidence-path-final.jpg`, `mobile-workspace.jpg`, `mobile-missing-source.jpg`, `benchmark-primary.jpg`, `benchmark-agent.jpg`, and `packaged-app.jpg`. The final stale, refreshed, and evidence-path captures share one workspace generation and the latest graph routing. These are retained submission evidence, not temporary frontend assets; superseded captures are archived outside Git.

## Comparison checklist

| Point | Reference | Implementation decision | Browser status |
|---|---|---|---|
| Palette | White report/shell, cool-gray graph, cobalt action | Explicit white and cool-gray tokens; no gradients | Verified in final desktop and drawer captures |
| Header | Text wordmark, underline navigation, simple actions | Code-native matching header, private GitHub destination | Verified; mobile icon button now has explicit accessible name |
| Typography | Strong compact editorial headline and numeric amount | Inter/system sans, intentional heading/control/label scales | Verified across desktop, drawer and mobile |
| Panel layout | Report left, graph right, activity below | 38/62 desktop split; stacks on narrow screens | Verified; primary panels and final report nodes are fully visible |
| Currentness | Current markers and withheld stale amounts | API current values only; previous values explicitly labeled | Verified FX and missing-source states; independent support stays current |
| Graph | Sources, calculations, reports with precise edges | Actual consumed/produced projection, full intermediates and horizontal exploration | Fixed desktop clipping with measured-width layout; long edges avoid intermediate nodes |
| Drawer | Five bounded change choices, editor and apply action | Matching component family, keyboard radios, focus trap, error states | Verified against companion concept and source-drawer capture |
| Responsive | Preserve readable content and controls | Stacked panels, full-width drawer, scrollable graph/table | Verified at 390px; no page-level horizontal overflow |

## Intentional changes from generated imagery

Invented support count and dates were replaced by actual backend values. Graph shortcuts were replaced by real recorded dependencies, which require a wider scrollable canvas. Dynamic native evidence and failure states add content required by the product workflow. The optional benchmark view uses the same visual system and an actual frozen results table, without fabricated success metrics. The supplemental concept's selected navigation pill is ignored in favor of the primary concept's underline.

## Functional checks before browser QA

- TypeScript plus production Vite build passed.
- A live API request against HydraDB returned company revenue 556500 cents, EU revenue 209000 cents and two EU support tickets, matching UI unit handling.
- Native graph contained 27 nodes and 29 relationships, including consumed/produced receipt edges supported by the projection.
- API response validation refuses stale/unknown claims that incorrectly contain a current value. A lost mutation response triggers state reconciliation, and the old current display is hidden if reconciliation fails.

No temporary QA screenshot files are shipped in the frontend bundle. The retained concept images are project design references rather than rendered UI assets.

## Final verification

The above-the-fold copy comparison passes with the documented functional/data corrections in `DESIGN_SPEC.md`: no invented metric, timestamp, or graph edge from the generated concepts is shown as real. The exact headline, supporting copy, primary actions, report heading and evidence heading remain consistent. Additional currentness/error notices and mobile scrolling guidance are deliberate functional copy.

The parent exercised the real FX correction, withheld-claim state, native-path inspection, four-call selective refresh, fresh-value check and persisted workspace after backend restart. The refreshed values are $5,755.00 company revenue, $2,280.00 EU revenue and two unchanged support tickets. Missing-source refresh was refused without serving stale numbers, and reset restored the initial fixture. The budget selector and recorded-agent expansion display the actual saved evidence with their scope disclosures.

The packaged application was also verified in IAB at `http://127.0.0.1:18080`, with the built frontend and native HydraDB health check. Its capture is `evidence/ui/packaged-app.jpg`.

The source drawer intentionally uses the primary screen's smaller consistent control typography rather than the companion image's larger isolated type scale. This is recorded in the design specification and was inspected at full width and on mobile.

The final implementation is faithfully verified against the accepted visual design with the documented data and functional deviations. The material graph clipping and activity-ID presentation issues were fixed. No material visual mismatch remains in the inspected desktop, drawer, mobile, and benchmark surfaces.

## Retail evaluation update

The compiled Docker application at revision `7f110c6` was checked again in IAB on 15 November. The new retail section reads the audited `evidence/retail_v2_summary.json`; it separates complete production closure, per-case graph-matched allowances, and the fixed 2,048-token diagnostic. All three tables were expanded and inspected. The 38/38 fresh reports and 4/4 unavailable blocks have separate columns. The exact-flat tie, shared executor, fixed-budget 2/10 refusal/no-op result, and failed development efficiency gate remain visible.

Changing the original pilot selector to 512 and back to 2,048 changed only its own recall table; retail metrics remained unchanged. At 390×844, page width and scroll width were both 390px. The comparison table scrolled horizontally within its container to expose all numeric columns. Desktop and mobile captures are `evidence/ui/retail-v2-desktop.jpg` and `evidence/ui/retail-v2-mobile.jpg`. The temporary viewport override was reset, and the original working workspace was verified after returning from Benchmark. No remote deployment was performed.


## Browser CSV import verification

The builder completed an **interactive CUA/IAB browser check** against the actual Docker application at revision **`a2eb61b`** on 15 November 2026. The [machine-readable ledger](../evidence/browser_csv_verification.json) records thirteen observed checks and the screenshot hashes. These are interactive observations, not automated end-to-end tests. They are not additional retrieval benchmark cases. Screenshots retain selected states; rows without a dedicated capture are explicitly identified as session observations.

The input cases were authored and frozen in [the browser CSV acceptance manifest](../fixtures/browser_csv_v1/acceptance_manifest.json) before implementation. The flow is **Use your data → Validate CSV → Create reports**, then **Update CSV → Validate CSV → Publish correction → Refresh affected**. It creates two guided revenue reports and makes no live model call.

| Interactive check | Browser-observed outcome | Retained capture |
|---|---|---|
| NORTH preview | Valid EUR 1.20 input showed the chosen region and non-persisting preview, with eight validation calculations and zero recorded tool calls | [Preview](../evidence/ui/csv-preview-desktop.jpg) |
| NORTH creation | Company revenue **$308**, NORTH revenue **$108**; both reports current | [Created reports](../evidence/ui/csv-created-desktop.jpg) |
| Source-only correction | Publishing EUR 1.30 withheld affected current revenue before refresh | [Stale reports](../evidence/ui/csv-stale-desktop.jpg) |
| Native path inspection | NORTH evidence connected the supplied FX source through `convert_to_usd` to the regional artifact | Observed during the browser session; no dedicated path screenshot retained |
| Selective refresh | Four recorded calls produced **$317 company / $117 NORTH**; current values verified and support preserved | [Refreshed reports](../evidence/ui/csv-refreshed-desktop.jpg) |
| Browser reload | Current NORTH values and rate 1.30 returned after reload; CSV text was not repopulated in the upload form | Observed during the browser session; no dedicated reload screenshot retained |
| Canonical row reordering | Equivalent reordered CSV made no source change and recorded zero refresh calls; existing artifact identities were preserved | Observed during the browser session; no dedicated screenshot retained |
| Invalid input | Malformed and >1 MiB CSV were rejected, including invalid input supplied after a previously valid preview | Observed during the browser session; no dedicated screenshot retained |
| Zero-support input | APAC input produced revenue-only reports **$163.75 company / $93.75 APAC**, without inventing a support claim | [APAC wide workspace](../evidence/ui/csv-workspace-wide.jpg) |
| Application restart | Imported workspace and current results remained available after the application container restarted | Observed during the browser session; no dedicated restart screenshot retained |
| Workspace separation | Switching between Guided demo and Open your CSV preserved their independent state | Observed during the browser session |
| Mobile workspace and correction | The workspace and update drawer were inspected and legible at **390px** width | [Mobile workspace](../evidence/ui/csv-mobile-workspace.jpg), [mobile update](../evidence/ui/csv-mobile-update.jpg) |
| Wide desktop | Imported reports, graph and controls were inspected and legible at **1536px** width | [Wide workspace](../evidence/ui/csv-workspace-wide.jpg) |

The UI separates the last operation's validation, recorded execution and verification counts. A first preview-and-create path performs **8 preview preflight + 8 create preflight + 8 recorded tool calls + 11 verification calculations = 35**. Creation alone reports **27** because preview is a separate operation. A source-only update validates but does not refresh; a no-op update still validates. These are registered arithmetic invocations, not a claim to count all parsing, graph-query or storage work.

Route counts remain distinct: the CLI performs **16 preflight + 11 verification + recorded calls** for a successful two-report import; MCP `load_csv` performs **8 preflight** calculations per load. The prior CLI accounting correction and original benchmark/MCP recordings are retained. No old raw result was rewritten to imply the newer explicit counters were present at recording time.

The browser boundary is one UTF-8 CSV up to **1 MiB and 1,000 order rows**, at most **10,000 total ticket counts**, USD/EUR/GBP, caller-supplied rates, unique order IDs and one currency per region. Both reports contain revenue only; support remains a separate artifact. An existing imported workspace keeps its selected region. This verification establishes the listed local functional behavior, not production scale, customer use, arbitrary-query support or a live hosted model. Hosting remains on hold, and repository visibility remains private.
