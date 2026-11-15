# ProofFlow: retail v2 demo narrative

This two-minute narrative combines the verified browser workflow with the audited retail evidence and five-tool MCP integration. The [existing 120-second functional walkthrough](../video/proofflow-walkthrough.mp4) was recorded before retail v2 and remains available at `/walkthrough.mp4` in the application image. Its benchmark shots are from the original pilot; the updated narrative below is distinct from that recording. Hosting is on hold and will be handled by the project owner. The repository remains private.

## Two-minute sequence

Use the verified local app at **http://127.0.0.1:18080**, starting from **New workspace**. This browser fixture is authored commerce data, separate from the external retail transactions used in the benchmark.

| Time | Action | Narration |
|---|---|---|
| 0:00–0:10 | Show the company report and EU brief, with two recorded runs. | “Agents reuse prior work. But when an input changes, which saved numbers can they still trust? ProofFlow keeps the dependencies attached.” |
| 0:10–0:25 | Inspect EU revenue, then **Change a source → Exchange rate → 1.20 → Apply correction**. | “This brief reuses a calculation from another run. Correct the euro rate: HydraDB follows the actual consumed inputs across both reports.” |
| 0:25–0:39 | Show four affected artifacts, withheld revenue and unchanged support. | “Revenue is withheld until revalidated. The independent support count stays current. These paths come from native Hydra queries.” |
| 0:39–0:55 | Click **Refresh affected**, then show updated claims and activity. | “Four real tools refresh the dependent work. Company revenue becomes $5,755; EU revenue becomes $2,280. Support keeps the same artifact.” |
| 0:55–1:06 | Click **Check values**; show current claims and evidence. | “Independent recomputation matches. New reports bind to new intermediate versions. Missing evidence blocks the calculation instead of becoming a guessed answer.” |
| 1:06–1:27 | Open the Retail v2 benchmark and show the complete-path result, graph-matched table and token total. | “On ten held-out retail cases, complete dependencies refresh all thirty-eight recoverable affected reports and block four unavailable ones. With the same per-case allowance, BM25 completes nineteen, dense eight, iterative hybrid thirty-three. Evidence uses sixty-nine percent fewer tokens than full context.” |
| 1:27–1:41 | Show exact-flat tie, fixed-2,048 diagnostic and development result. | “Exact dependency traversal ties. At two thousand forty-eight tokens, graph completes only eight reports. We retain that shortfall and the failed development efficiency gate.” |
| 1:41–1:56 | Show the five-tool MCP quickstart and saved actual-client evidence. | “An existing agent can load data, choose typed plans, inspect and refresh. One real Claude client reused prior artifacts and corrected both reports. That is a separate integration, not this benchmark.” |
| 1:56–2:00 | Return to the verified report. | “ProofFlow: current evidence across agent runs.” |

Use actual application views or clearly labeled saved evidence for the benchmark and client shots. The updated Retail v2 panel has been checked on desktop and mobile; its numbers come from the audited summary. Do not imply the browser runs a model or benchmark on demand. The final frame can carry a hosted URL only after the owner deploys and verifies it.

## Required evidence captions

Keep these captions legible on their associated shots:

- **Retail scope:** “640 UCI retail lines · 4 dated partitions · 10 authored changes/compositions · deterministic tools, no LLM.”
- **Complete path:** “38/38 recoverable affected reports · 4/4 unavailable blocked · 10/10 correct endstates includes refusal and no-op.”
- **Matched comparison:** “Same records and Hydra-assisted executor · per-case allowance set by full graph closure before comparator runs · 0–9,611 tokens.”
- **Evidence reduction:** “39,375 vs 128,729 evidence tokens · 69.41% fewer · exact-flat ties · not model-cost savings.”
- **Constrained diagnostic:** “Fixed 2,048 tokens: graph 8/38, BM25 1/38, dense 0/38, iterative 4/38 · 2/10 endstates are refusal + no-op for every arm.”
- **Development:** “Correctness passed; efficiency failed: 60.79% of full context vs unchanged ≤40% gate.”
- **MCP:** “One corrected Fable 5.2/high trajectory · authored two-row input · first configuration failure retained · server makes no model calls.”

The complete-path token ratio is 30.59%, or 33.99% excluding the no-op. The ≤40% gate is aggregate; two test cases exceed it individually. The failed development ratio rises to 81.07% when its no-op is excluded. Do not count an unavailable report as a fresh answer or attach the complete-path result to the fixed 2,048-token condition.

All retrieval arms share currentness checks and recursive refresh. Their missing-source blocking and zero incorrect-current artifacts are shared safety outcomes. Complete graph, exact-flat and full context each use 101 tool calls; the token reduction does not mean fewer calculations. The benchmark uses a bounded positive-sales sample with staged FX, refunds and corrections, not observed historical incidents. It is not a learning-curve or customer-outcome result.

## Browser and agent facts

| Property | Observed result |
|---|---|
| Browser correction | EUR→USD 1.10 → 1.20 |
| EU revenue | $2,090 → $2,280 |
| Company revenue | $5,565 → $5,755 |
| EU support | 2, same identity and content hash |
| Refresh | `convert_to_usd`, `company_total`, two `compose_report` calls |
| Verification | Independent recomputation matches; stale/unknown current values withheld |
| App deployment | 16/16 original HTTP checks, including application-container restart |
| MCP stock client | 20 checks through an external stdio process, no model calls |
| Actual Claude MCP client | 32 recorded checks; 9 MCP requests; 7 initial + 1 reuse + 4 refresh runtime calls |

The browser's initial reports are guided presets. The separate actual MCP-client experiment lets Fable 5.2 choose both plans through the five exposed tools. Its two loads perform **16 CSV arithmetic preflight checks in addition to 12 recorded runtime calls**. One corrected trajectory does not establish general agent reliability. The first launch failed before tool discovery, and that failure remains in the evidence. The server's `model_calls: 0` excludes model activity in the external Claude client.

The earlier local composition bridge is also preserved: two Fable calls, a seven-tool report followed by a one-tool composition reusing three artifacts, and seventeen checks. The browser labels those plans **Recorded agent workflow**. They are separate from the actual MCP-client run and retail benchmark. Numeric values always come from registered tools; arbitrary SQL and code execution are outside the interface.

## Earlier pilots and longer demonstrations

The original twelve-case deterministic pilot remains **16/29 graph, 6/29 BM25, 1/29 dense and 9/29 iterative**, at 2,048 evidence tokens. Its separate sixteen-call model pilot remains **5/9, 1/9, 0/9 and 2/9**, respectively. They are not pooled with retail v2 or counted as MCP-client trajectories.

For a longer live walkthrough, remove FX to show refused refresh with current support, then reset to restore the fixture. A restart clip can show preserved session and artifact IDs; database restart evidence separately verifies persisted paths and a new write. The CSV CLI can show correction propagation and row-order replay with zero new recorded refresh calls; each load still performs eight arithmetic preflight checks.

## Evidence

- [Retail v2 results](RETAIL_V2_RESULTS.md), [frozen protocol](RETAIL_V2_SPEC.md), [audited summary](../evidence/retail_v2_summary.json), and [dataset attribution](../fixtures/retail_v2/DATASET_NOTICE.md)
- [Five-tool agent quickstart](AGENT_QUICKSTART.md), [stock-client check](../results/mcp-v1/summary.json), and [actual-client results](MCP_AGENT_RESULTS.md)
- [Original deterministic pilot](BENCHMARK_RESULTS.md), [original model pilot](AGENT_RESULTS.md), and [recorded composition](COMPOSITION.md)
- [Core execution](../evidence/core_smoke.json), [HydraDB restart](../evidence/hydra_smoke.json), [packaged deployment](../evidence/deployment_smoke.json), and [browser verification](UI_FIDELITY.md)

Credentials and provider login material stay off screen. Local execution is labeled local; repository links remain restricted by its private visibility.
