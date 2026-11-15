# ProofFlow retail v2 walkthrough script

The current two-minute film combines actual application captures with clearly labeled cards derived from saved retail and MCP execution evidence. Narration is generated locally with macOS Samantha. It is an edited walkthrough, not an uninterrupted live recording.

## 1. Which saved numbers can an agent still trust?

Time: 0.00–10.47 seconds. Visual: `../evidence/ui/workspace-final.jpg`.

Agents reuse prior work. When an input changes, which saved numbers can they still trust? ProofFlow keeps the dependencies attached across runs.

## 2. Changed revenue is withheld. Current support is preserved.

Time: 10.47–21.75 seconds. Visual: `../evidence/ui/workspace-stale-final.jpg`.

Correct the euro exchange rate. Revenue becomes stale and is withheld. The independent support count stays current, while previous revenue remains clearly historical.

## 3. Native HydraDB queries explain the affected work.

Time: 21.75–29.27 seconds. Visual: `../evidence/ui/evidence-path-final.jpg`.

Hydra D B traces the inputs each tool actually consumed, linking this calculation to both reports.

## 4. Four tools refresh both dependent reports.

Time: 29.27–42.92 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`.

Four tools refresh the dependent work. Company revenue becomes five thousand seven hundred fifty-five dollars; E U revenue, two thousand two hundred eighty. Independent recomputation matches.

## 5. A separate experiment on public retail transactions.

Time: 42.92–58.45 seconds. Visual: `../evidence/ui/retail-v2-desktop.jpg`.

Now a separate retail experiment: six hundred forty public transaction lines, four dated partitions, and ten authored cases. Complete dependencies refresh thirty-eight recoverable reports and block four unavailable ones.

## 6. Equal per-case evidence allowances. Real tool refresh.

Time: 58.45–70.56 seconds. Visual: Saved-evidence card: matched.

With identical records and the graph's per-case allowance, B M twenty-five completes nineteen, dense eight, and iterative hybrid thirty-three. All methods share the same executor.

## 7. 69.41% fewer evidence tokens than full context.

Time: 70.56–81.32 seconds. Visual: Saved-evidence card: tokens.

Evidence uses sixty-nine point four one percent fewer tokens than full context. Exact dependency traversal ties. The calculations still run.

## 8. The constrained result and development failure stay visible.

Time: 81.32–92.82 seconds. Visual: Saved-evidence card: limits.

At a fixed two-thousand-forty-eight-token limit, graph completes only eight reports. The earlier development efficiency gate failed. Both limitations remain visible.

## 9. A real client uses ProofFlow through five MCP tools.

Time: 92.82–115.79 seconds. Visual: Saved-evidence card: mcp.

An actual Claude client uses five M C P tools to load data, choose plans, inspect and refresh. It reuses prior artifacts on authored two-row input. After a launch-configuration fix, one trajectory passed thirty-two checks, with nine requests and twelve recorded runtime calls. Its first configuration failure is retained.

## 10. ProofFlow — current evidence across agent runs.

Time: 115.79–120.00 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`.

ProofFlow: current evidence across agent runs.

## Evidence and production notes

- Browser correction uses the authored guided fixture; retail is a separate public-data sample with authored changes, deterministic tools and no model calls.
- Complete graph and exact dependency traversal tie: 38/38 recoverable affected reports and 4/4 unavailable reports blocked. Retrieval comparators receive the full graph closure allowance before execution, 0–9,611 tokens, with the same records and shared Hydra-assisted executor.
- The 69.41% reduction is evidence tokens versus full context across ten cases, including one no-op. Excluding the no-op, graph uses 33.99% of full-context evidence. Complete graph, exact traversal and full context each execute 101 tools.
- The fixed 2,048-token graph condition completes 8/38. The development efficiency result is a retained failure: 60.79% against an unchanged ≤40% gate. Full details: [retail results](RETAIL_V2_RESULTS.md).
- The MCP segment shows one local Fable 5.2/high trajectory after a launch-configuration fix, on authored two-row input. The first configuration failure is retained. Nine requests produce 12 recorded runtime calls and 16 additional CSV arithmetic preflight calculations; 32 recorded checks pass. The external client calls the model; the server does not. Full details: [MCP results](MCP_AGENT_RESULTS.md).
- The video contains no deployment address. Hosting remains with the project owner and the source repository remains private.
- Rendered duration is exactly 120 seconds at 1920 × 1080 and 30 fps. Narration has 236 words. Captions are burned into the frames and also available as an embedded text track and SRT sidecar.
- Source hashes, timing and encoding data are recorded in `video/render_manifest.json`, `video/media_validation.json` and `video/quality_review.json`.
