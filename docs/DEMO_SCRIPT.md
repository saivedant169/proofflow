# ProofFlow: retail v2 demo narrative

The current [120-second walkthrough](../video/proofflow-walkthrough.mp4) combines the verified browser workflow, retail v2 results and the actual five-tool MCP-client integration. It is an edited sequence of real application captures and clearly labeled saved-evidence cards, with local narration. The application image exposes the video at `/walkthrough.mp4`. Hosting is on hold and will be handled by the project owner; the repository remains private.

## Two-minute sequence

The browser fixture uses authored commerce data, separate from the external retail transactions in the benchmark. The table follows the actual encoded film; times are rounded to hundredths of a second.

| Time | Visual | Narration |
|---|---|---|
| 0:00.00–0:10.47 | Company report and EU brief, composed from two runs. | “Agents reuse prior work. When an input changes, which saved numbers can they still trust? ProofFlow keeps the dependencies attached across runs.” |
| 0:10.47–0:21.75 | Source correction drawer, then withheld revenue and unchanged support. | “Correct the euro exchange rate. Revenue becomes stale and is withheld. The independent support count stays current, while previous revenue remains clearly historical.” |
| 0:21.75–0:29.27 | Actual HydraDB evidence drawer and consumed-input path. | “HydraDB traces the inputs each tool actually consumed, linking this calculation to both reports.” |
| 0:29.27–0:42.92 | Revalidated company and EU values; support remains unchanged. | “Four tools refresh the dependent work. Company revenue becomes five thousand seven hundred fifty-five dollars; EU revenue, two thousand two hundred eighty. Independent recomputation matches.” |
| 0:42.92–0:58.45 | Actual retail v2 application summary, with data and experiment scope. | “Now a separate retail experiment: six hundred forty public transaction lines, four dated partitions, and ten authored cases. Complete dependencies refresh thirty-eight recoverable reports and block four unavailable ones.” |
| 0:58.45–1:10.56 | Saved-evidence card: complete closure and graph-matched retrieval baselines. | “With identical records and the graph's per-case allowance, BM25 completes nineteen, dense eight, and iterative hybrid thirty-three. All methods share the same executor.” |
| 1:10.56–1:21.32 | Saved-evidence card: evidence-token reduction, equal calculation counts and scope. | “Evidence uses sixty-nine point four one percent fewer tokens than full context. Exact dependency traversal ties. The calculations still run.” |
| 1:21.32–1:32.82 | Saved-evidence card: fixed 2,048-token shortfall and failed development gate. | “At a fixed two-thousand-forty-eight-token limit, graph completes only eight reports. The earlier development efficiency gate failed. Both limitations remain visible.” |
| 1:32.82–1:55.79 | Saved actual-client evidence: five tools, 32 checks, 9 requests and 12 runtime calls. | “An actual Claude client uses five MCP tools to load data, choose plans, inspect and refresh. It reuses prior artifacts on authored two-row input. After a launch-configuration fix, one trajectory passed thirty-two checks, with nine requests and twelve recorded runtime calls. Its first configuration failure is retained.” |
| 1:55.79–1:60.00 | Return to the verified report. | “ProofFlow: current evidence across agent runs.” |

The benchmark and client cards display saved evidence; the browser does not run a model or benchmark on demand. The film has no deployment URL. For a live demonstration, use the verified local app at **http://127.0.0.1:18080** and start from **New workspace**. The complete narration and source references are in [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md).

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
