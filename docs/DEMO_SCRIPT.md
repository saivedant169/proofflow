# ProofFlow: two-minute walkthrough

This script uses the verified application at **http://127.0.0.1:18080**, actual HydraDB traversal and real tool calculations. The comparative results and model composition are saved experiments with their own evidence. The [completed walkthrough](../video/proofflow-walkthrough.mp4) is 120 seconds at 1080p and is bundled into the Docker image at `/walkthrough.mp4`. The public hosting origin remains pending. The source repository stays private until the user explicitly directs release.

## Walkthrough narrative

Start from **New workspace**. The fixture begins with $5,565 company revenue, $2,090 EU revenue and two EU support tickets. Keep the authored-data label visible; stage the EUR correction rather than describing it as a customer event.

| Time | Action | Narration |
|---|---|---|
| 0:00–0:12 | Show the two report runs in Workspace. | “A report can be correct when an agent writes it and become outdated later. ProofFlow tracks which evidence is still usable across runs.” |
| 0:12–0:26 | Inspect the EU report or revenue artifact; show its recorded inputs and the separate support branch. | “This EU brief reuses calculations from the earlier company report. Every numeric claim points to the actual tools and input versions that produced it.” |
| 0:26–0:42 | **Change a source → Exchange rate → 1.20 → Apply correction**. | “Correct the euro exchange rate from 1.10 to 1.20. HydraDB follows the dependency paths across both runs. Revenue needs refresh; the independent support count stays current.” |
| 0:42–0:57 | Show the four affected artifacts, withheld revenue and native evidence path. | “The saved revenue is no longer presented as current. The graph records what this work consumed, so the correction reaches its downstream reports.” |
| 0:57–1:14 | Click **Refresh affected**, then show the updated reports and activity. | “Four actual tools run. EU revenue becomes $2,280 and company revenue becomes $5,755. The support artifact is reused unchanged.” |
| 1:14–1:25 | Click **Check values** and briefly inspect the evidence fingerprint. | “Independent recomputation matches. The updated report binds to the new intermediate result. Session and artifact identities also survive an application restart.” |
| 1:25–1:40 | Open **Benchmark**, primary 2,048-token budget; show execution results and exact dependency control. | “Across twelve authored held-out scenarios, this context refreshed sixteen of twenty-nine affected reports: BM25 refreshed six, dense retrieval one, and iterative hybrid nine. Exact dependency traversal ties.” |
| 1:40–1:53 | Show the saved model-results table, then expand **Recorded agent workflow**. | “A separate sixteen-call Fable pilot completed five of nine, versus one, zero and two. In two composition calls, the model built a seven-tool report, then reused three artifacts with one tool.” |
| 1:53–2:00 | Show the recorded-run disclosure and return to the updated report. | “The browser executes real calculations; its model panel is recorded. ProofFlow keeps recurring analytics connected to its evidence.” |

The model-result table is in [AGENT_RESULTS.md](AGENT_RESULTS.md); it is not a separate live-model benchmark control in the app. Use that saved table as an evidence insert rather than implying the browser just made sixteen calls. The final frame can use the hosted URL only once it exists and has been checked. Do not promise public repository access.

## Captions that preserve the comparison

Keep these readable on the relevant evidence shots:

- **Deterministic pilot:** “12 authored held-out scenarios · 2,048 evidence tokens · same Hydra-assisted validity and refresh executor · no LLM.”
- **Model pilot:** “4 prespecified cases × 4 arms · 16/16 attempts, no model failures or abstentions · Fable 5.2, high reasoning · same evidence budget and executor · one sample per condition.”
- **Composition:** “Recorded local model run · 2 calls · 17 checks passed · not a live hosted model.”

The fresh-report denominators count only affected reports with an available independent numeric oracle. Missing-source blocks are reported separately and never counted as completed calculations. Both pilots leave unresolved work at the finite evidence budget: ProofFlow completes 16/29 in the deterministic pilot and 5/9 in the model pilot.

All arms share safe currentness checks and recursive execution. Their zero incorrect-current reports are a shared safety result. The main graph run executes more tools because it completes more required work; these totals are not evidence of lower cost. Exact flat traversal ties the deterministic graph result. At unlimited evidence, all selectors recover the affected sets. These small authored pilots do not establish universal or statistical superiority.

## Verified functional facts

| Property | Observed result |
|---|---|
| Staged correction | EUR→USD 1.10 → 1.20 |
| EU revenue | $2,090 → $2,280 |
| Company revenue | $5,565 → $5,755 |
| EU support | 2, same identity and content hash |
| Affected saved outputs | Regional revenue, company revenue, company report, EU brief |
| Refresh | `convert_to_usd`, `company_total`, two `compose_report` calls |
| Numerical verification | Independent full recomputation matches |
| Missing source | Refresh refuses; no current revenue is served |
| Application deployment | 16/16 HTTP checks, including app-container restart |
| Model composition | First request: seven tools; second: one tool, three reused artifacts; 17 checks passed |

The browser's two initial reports are guided presets. The separate recorded composition evidence contains two actual model-chosen plans, including a new EU brief. Every numeric value in both modes comes from the registered tools, not a model-authored number. The planner selects typed tools and supplied handles; arbitrary SQL, code and hidden sources are outside its supported interface.

## Optional longer demonstration

After the main recording, **Change a source → Missing source → FX** demonstrates a refused refresh while support remains current. **New workspace** restores the original fixture. A restart clip can show the same session and artifact IDs returning after the app restarts; the database's separate restart evidence also verifies old native paths and a new write. Avoid making visitors wait through a service restart in the main two-minute flow.

The CSV CLI is an additional integration demonstration: repeat an import into the same workspace after a correction, then reorder the same rows and observe no new calculations. Its authored non-EU smoke is separate from the held-out retrieval benchmark.

## Evidence

- [Core execution](../evidence/core_smoke.json), [HydraDB restart](../evidence/hydra_smoke.json), and [packaged deployment](../evidence/deployment_smoke.json)
- [Deterministic pilot and raw-result links](BENCHMARK_RESULTS.md)
- [Actual model pilot and attempt accounting](AGENT_RESULTS.md)
- [Model-chosen composition](COMPOSITION.md) and [compact recorded evidence](../evidence/agent_composition.json)
- [Desktop/mobile browser verification](UI_FIDELITY.md)
- [Local CSV integration](../results/import-smoke-v1/verification.json)

Credentials, token files and provider login material stay off screen. A video made against the local application should identify that environment until the final HTTPS deployment is verified. Source links remain restricted by the repository's private visibility.
