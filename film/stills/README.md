# ProofFlow product stills

Captured by CAPTURE with `node tools/capture-stills.mjs` (headless Chrome via puppeteer-core) from the **restyled** app (`frontend/`, commit 35dd134: new tokens, ThemeSwitch, Anybody / Instrument Sans / JetBrains Mono; re-shot after merging main 50683c5, which removed the intro's "Watch walkthrough" link), **dark theme** (`proofflow-site-theme = dark` plus `prefers-color-scheme: dark`, the film's navy ground), reduced motion, no cursor, hover or focus ring.
The frontend ran under the Vite dev server with `/api` and `/health` proxied to the hosted backend `https://proofflow.arnavbule.in` (a temporary config outside the repo; the frontend is unchanged). Every figure comes from that real backend and HydraDB; nothing is mocked. One anonymous session on 2026-11-16.

Full frames: device scale 2 on a 1600 CSS px wide viewport (workspace frames grow to the document height; drawer frames are exactly 1600x1000). Crops `<id>.<name>@Nx.png` are re-rendered at scale 3 or 4 from the same live state (never upscaled). Mobile: 390x844, scale 3, mobile emulation. Boxes in `stills.json` are CSS px of each image; drawer frames name only drawer parts.

Data: the guided sample (EUR → USD 1.10 → 1.20) and the documented two-row CSV `fixtures/browser_csv_v1/valid_non_eu.csv` (NORTH EUR 10000/1000, SOUTH USD 20000/0), uploaded as `orders.csv`, region NORTH, EUR → USD **1.20 → 1.30** (`docs/DEMO_SCRIPT.md`, `fixtures/browser_csv_v1/acceptance_manifest.json`).

| still | state shown | on-screen figures | crops |
|---|---|---|---|
| `p01-workspace` | Guided sample, everything current | $5,565.00 company; EU revenue $2,090.00; EU support tickets 2; step 1 Change a source | `.report`@4x `.graph`@3x `.workflow`@4x `.headline`@3x |
| `p12-mobile` | Guided sample at 390 px | as p01 | `.phone-screen`@3x `.report`@4x |
| `p02-change-source` | Change a source drawer, Exchange rate, EUR → USD 1.20 entered (Current 1.10) | Apply correction not yet clicked | `.editor`@4x `.options`@3x `.fx-option`@4x |
| `p03-stale` | After the 1.20 correction | banner "EUR → USD corrected to 1.20 · 4 saved artifacts require revalidation."; Awaiting refresh (previously $5,565.00 / $2,090.00); support 2 current; affected graph path | `.banner`@4x `.report`@4x `.graph`@3x `.workflow`@4x |
| `p04-evidence` | Inspect evidence for the withheld EU revenue figure | native HydraDB path from the FX source | `.path`@4x `.header`@3x |
| `p05-refreshed` | After Refresh affected | "4 tool calls. The independent support result stayed unchanged. Fresh recomputation matches."; $5,755.00; EU $2,280.00 | `.banner`@4x `.report`@4x `.activity`@3x `.graph`@3x |
| `p06-csv-form` | Use your data, `orders.csv` uploaded, EUR → USD 1.20, region NORTH | the two CSV rows in the textarea | `.csv`@4x `.rates`@4x |
| `p06-csv-preview` | After Validate CSV | "Ready to create": Order rows 2, Regions 2, Report region NORTH, Currencies EUR, USD; "8 validation calculations · 0 recorded tool calls. This preview has not changed a workspace."; Create reports | `.preview`@4x `.preview-create`@3x |
| `p07-csv-created` | After Create reports | $308.00 Company net revenue; NORTH net revenue $108.00 Current; "CSV reports created" accounting | `.report`@4x `.accounting`@4x `.graph`@3x `.workflow`@4x |
| `p08-csv-update` | Update your CSV, EUR → USD 1.30, validated | "Ready to publish"; Publish correction | `.rates`@4x `.publish`@4x `.preview-publish`@3x |
| `p08-csv-stale` | After Publish correction | banner "CSV sources updated · 4 saved artifacts require revalidation."; Awaiting refresh (previously $308.00 / $108.00); support Current; "Explicit exchange rates" source and its descendants highlighted; "4 affected artifacts" | `.banner`@4x `.report`@4x `.graph`@3x (boxes `affected-path`, `changed-source`) `.accounting`@4x |
| `p08-csv-evidence` | Inspect evidence for the NORTH revenue brief | Explicit exchange rates → Execute convert_to_usd → Regional USD revenue → Execute compose_report → NORTH revenue brief; Needs refresh | `.path`@4x `.header`@3x |
| `p09-csv-refreshed-unchecked` | After Refresh affected, before Check values | $317.00; NORTH $117.00; refresh banner with Check values | `.banner`@4x `.report`@4x |
| `p09-csv-refreshed` | After Check values | "Verified: both report values match fresh recomputation and their evidence is current."; $317.00 / $117.00; Download current reports and Copy checked report enabled; "4 artifacts revalidated" | `.report`@4x `.handoff`@4x `.verification`@4x `.accounting`@4x `.graph`@3x `.activity`@3x |
| `p09-csv-copied` | After Copy checked report (server re-checked every figure current, then copied) | "Report copied. Snapshot checked at … UTC. This snapshot does not update automatically." | `.handoff`@4x `.receipt`@4x `.copy`@4x `.verified`@4x |
| `p10-benchmark` | Benchmark view (full page) | recorded model comparison, retail benchmark, original pilot | `.top`@3x `.model-comparison`@3x `.model-table`@4x `.retail`@3x `.execution-results`@4x |
| `p11-agent` | Benchmark view, recorded agent workflow expanded | two requests, execution checks | `.agent`@3x `.runs`@4x `.proof`@4x |

Notes: drawer frames show the app's own dimmed, softened backdrop behind the drawer (the app's scrim); crop the drawer, not the backdrop. The copy went to headless Chrome's clipboard only; Download current reports was not clicked (no file written).

To re-capture: run the frontend with an API (`cd frontend && npx vite --config <a config whose server.proxy sends /api and /health to the backend>`), then from `film/`: `node tools/capture-stills.mjs --base http://localhost:5188 --puppeteer <dir with node_modules/puppeteer-core>` (`--only <id prefix>` re-shoots some states into the existing manifest).
