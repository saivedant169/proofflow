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
