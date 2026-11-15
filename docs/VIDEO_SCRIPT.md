# ProofFlow CSV-first walkthrough script

The current two-minute film opens with browser CSV preview and report creation, then switches explicitly to a separate guided correction flow. Retail and actual MCP-client results appear as clearly labeled saved-evidence cards. Narration is generated locally with macOS Samantha. It is an edited walkthrough, not an uninterrupted live recording.

## 1. Start with your own CSV.

Time: 0.00–9.45 seconds. Visual: `../evidence/ui/csv-preview-desktop.jpg`, then `../evidence/ui/csv-created-desktop.jpg`.

Bring your own C S V. Preview your inputs and exchange rates, then create linked revenue reports. This C S V example has two rows.

## 2. Separate guided demo: changed revenue is withheld.

Time: 9.45–22.47 seconds. Visual: `../evidence/ui/source-drawer.jpg`, then `../evidence/ui/workspace-stale-final.jpg`.

In the separate guided demo, correct the euro exchange rate. Revenue becomes stale and is withheld. The independent support count stays current, while previous revenue remains clearly historical.

## 3. Native HydraDB queries explain the affected work.

Time: 22.47–29.94 seconds. Visual: `../evidence/ui/evidence-path-final.jpg`.

Hydra D B traces the inputs each tool actually consumed, linking this calculation to both reports.

## 4. Four tools refresh both dependent reports.

Time: 29.94–43.48 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`.

Four tools refresh the dependent work. Company revenue becomes five thousand seven hundred fifty-five dollars; E U revenue, two thousand two hundred eighty. Independent recomputation matches.

## 5. A separate experiment on public retail transactions.

Time: 43.48–58.90 seconds. Visual: `../evidence/ui/retail-v2-desktop.jpg`.

Now a separate retail experiment: six hundred forty public transaction lines, four dated partitions, and ten authored cases. Complete dependencies refresh thirty-eight recoverable reports and block four unavailable ones.

## 6. Equal per-case evidence allowances. Real tool refresh.

Time: 58.90–70.92 seconds. Visual: Saved-evidence card: matched.

With identical records and the graph's per-case allowance, B M twenty-five completes nineteen, dense eight, and iterative hybrid thirty-three. All methods share the same executor.

## 7. 69.41% fewer evidence tokens than full context.

Time: 70.92–81.61 seconds. Visual: Saved-evidence card: tokens.

Evidence uses sixty-nine point four one percent fewer tokens than full context. Exact dependency traversal ties. The calculations still run.

## 8. The constrained result and development failure stay visible.

Time: 81.61–93.02 seconds. Visual: Saved-evidence card: limits.

At a fixed two-thousand-forty-eight-token limit, graph completes only eight reports. The earlier development efficiency gate failed. Both limitations remain visible.

## 9. A real client uses ProofFlow through five MCP tools.

Time: 93.02–115.82 seconds. Visual: Saved-evidence card: mcp.

An actual Claude client uses five M C P tools to load data, choose plans, inspect and refresh. It reuses prior artifacts on authored two-row input. After a launch-configuration fix, one trajectory passed thirty-two checks, with nine requests and twelve recorded runtime calls. Its first configuration failure is retained.

## 10. ProofFlow — current evidence across agent runs.

Time: 115.82–120.00 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`.

ProofFlow: current evidence across agent runs.
## Evidence and production notes

- The opening shows actual browser CSV preview and created reports from an authored two-row input: company $308 and NORTH $108 at supplied EUR/USD 1.20. It does not show a CSV correction. [Browser evidence](../evidence/browser_csv_verification.json).
- The following correction sequence is explicitly labeled a separate guided demo, using the $5,565/$2,090 fixture. Retail is a separate public-data sample with authored changes, deterministic tools and no model calls.
- Complete graph and exact dependency traversal tie: 38/38 recoverable affected reports and 4/4 unavailable reports blocked. Retrieval comparators receive the full graph closure allowance before execution, 0–9,611 tokens, with the same records and shared Hydra-assisted executor.
- The 69.41% reduction is evidence tokens versus full context across ten cases, including one no-op. Excluding the no-op, graph uses 33.99% of full-context evidence. Complete graph, exact traversal and full context each execute 101 tools.
- The fixed 2,048-token graph condition completes 8/38. The development efficiency result is a retained failure: 60.79% against an unchanged ≤40% gate. Full details: [retail results](RETAIL_V2_RESULTS.md).
- The MCP segment shows one local Fable 5.2/high trajectory after a launch-configuration fix, on authored two-row input. The first configuration failure is retained. Nine requests produce 12 recorded runtime calls and 16 additional CSV arithmetic preflight calculations; 32 recorded checks pass. The external client calls the model; the server does not. Full details: [MCP results](MCP_AGENT_RESULTS.md).
- The video contains no deployment address. Hosting remains with the project owner and the source repository remains private.
- Rendered duration is exactly 120 seconds at 1920 × 1080 and 30 fps. Narration has 244 words. Captions are burned into the frames and also available as an embedded text track and SRT sidecar.
- Source hashes, timing and encoding data are recorded in `video/render_manifest.json`, `video/media_validation.json` and `video/quality_review.json`.
