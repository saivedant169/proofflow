# ProofFlow submission draft

The hosted app runs revision `b13f23892405efb856c8d4ca0e6abc94a1eca77c`. External checks verified report handoff by clipboard and file, both evidence downloads and CSV connector discovery. Approved judge access to the private repository and the organizer’s form remain pending. [Live app](https://proofflow.arnavbule.in) · [Two-minute walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4) · [Hosted verification](HOSTED_DELIVERY.md).

## Project and track

**ProofFlow — Track 2: agent context layer.** Final field wording depends on the organizer's form. The project demonstrates cross-run reuse and correction propagation; it claims no measured learning uplift.

## Short description

**Keep saved agent reports current when an input changes.** ProofFlow records the inputs behind each supported number, follows their dependencies in HydraDB, withholds outdated claims and refreshes affected calculations while preserving valid work. Analysts can try company and regional revenue with a compatible orders CSV; local MCP clients can compose reports from typed tools and reuse earlier results.

In a frozen 48-invocation actual-model study, ProofFlow refreshed **32/32 affected reports**, matching full context at **39.33% of its provider input exposure**, excluding the no-op case. At matched per-case evidence allowances, BM25 refreshed 25/32, BGE vector retrieval 5/32 and iterative hybrid 28/32. Exact-flat traversal also achieved 32/32. All methods share the same safe executor. [Results and limits](MODEL_COMPARISON_RESULTS.md).

The separate deterministic diagnostic reused the eight March cases. At **4,096 → 8,192 receipt tokens**, fresh reports out of 32 were graph and exact-flat **15 → 27**, iterative hybrid **15 → 28**, BM25 **5 → 25**, and BGE **2 → 10**. The uncapped reference refreshed **32/32**. Every capped method missed reports at both limits. The audited results preserve the original wrapper failures and the independently recovered scores. [Fixed-budget results](FIXED_BUDGET_DIAGNOSTIC_RESULTS.md).

## Problem and first user

A saved agent report can be relevant and still be out of date. When an exchange rate, refund or tool changes, later reports may reuse calculations made from earlier inputs. The analyst needs to know which figures are still usable, which require repair, and why.

In a recurring commerce revenue handoff, an analyst may need to correct an input after saving company and regional figures. ProofFlow checks those figures against their recorded dependencies when reading, copying or downloading the reports. The analyst supplies the underlying business data. Customer demand and time savings have not yet been measured.

A prospective comparison against a competent full-recalculation workflow found a correctness and stale-handoff tie on a small three-currency close. ProofFlow's additional result was preserving unaffected artifact heads and receipts and returning exact dependency paths from each corrected source to the prior reports. The full validation and verification work is reported separately from recorded refresh calls. [Comparison and limits](WORKFLOW_COMPARISON_RESULTS.md).

## What works

Seven registered tools perform SQLite aggregations, Decimal currency calculations and typed report composition. Immutable source, tool and artifact versions record exact consumed inputs and execution receipts. HydraDB-native traversal finds affected descendants and upstream evidence. Refresh recalculates prerequisites and rebinds downstream reports to current intermediate results.

The browser accepts a bounded CSV, previews it without publishing, and creates two revenue-only reports for the company and selected region. Publishing a correction changes sources and withholds affected monetary values. Refresh brings recoverable reports up to date; independent support remains reusable. The guided sample and imported workspace are separate.

**Copy checked report** puts the two current USD figures and their immutable report and claim IDs on the clipboard as a timestamped text snapshot. **Download current reports** saves the same format to a text file. For either action, the server checks that the displayed workspace generation and both report IDs match and that both reports and claims are current. A stale claim, incomplete source publication or unavailable evidence blocks the handoff. The snapshot records the UTC check time and stays fixed after copying or download.

Five local stdio MCP tools expose source loading, preparation, client-selected plan execution, currentness inspection and refresh. The external model chooses a bounded plan; registered tools compute the numbers. The server makes no model calls and accepts no arbitrary code or SQL. A recorded Fable 5.2/high MCP client completed one corrected trajectory with 32 checks, cross-run composition and reuse; its first launch-configuration failure is retained. [Agent quickstart](AGENT_QUICKSTART.md) · [Client evidence](MCP_AGENT_RESULTS.md).

The downloadable CSV connector lets a local MCP host create and inspect the browser’s fixed revenue reports, publish a correction, refresh affected work and return a checked text snapshot. A fresh external stock client downloaded the script and discovered all five tools without invoking them. An earlier stock-client run exercised the same script against the previous hosted CSV API with synthetic data and passed 21 checks. [Public connector setup](https://proofflow.arnavbule.in/agent/) · [Check scopes](HOSTED_DELIVERY.md).

## Live demonstration

1. Upload the authored two-row NORTH/SOUTH CSV with EUR→USD at 1.20. The current company and NORTH reports are **$308 / $108**.
2. Publish the same CSV with the corrected rate 1.30. Four artifacts become stale, current monetary values are withheld, and native graph evidence explains the impact. Support remains current.
3. Refresh the affected work. Four recorded tool calls produce **$317 / $117**, verified against independent arithmetic. Validation and verification calculations add to the four recorded calls. Choose **Copy checked report** and paste the snapshot, or **Download current reports** to save the refreshed figures, artifact IDs and UTC check time.

The 120-second film shows this CSV preview/creation briefly, then explicitly switches to a separate guided fixture, the audited 48-invocation model comparison and recorded MCP evidence. Earlier deterministic failures remain visible in a separate limits card. Those fixtures and experiments are not pooled. [Watch the hosted video](https://proofflow.arnavbule.in/walkthrough.mp4) · [Narration](VIDEO_SCRIPT.md).

## Fresh actual-model evidence

The code, fixtures, case order and protocol were frozen before test preparation. The 48 exact requests were committed before paid calls: **eight fresh March cases × six methods**, Fable 5.2/high, one harness attempt per cell and no harness retries or fallback. The 4,681 UCI Online Retail rows come from March 1–4, 2011; corrections are authored interventions. June supplied a separate no-model development check.

| Evidence method | Correct fresh affected reports | Complete correction cases |
|---|---:|---:|
| ProofFlow / HydraDB | **32/32** | **6/6** |
| Exact-flat traversal | 32/32 | 6/6 |
| Full context | 32/32 | 6/6 |
| Iterative hybrid | 28/32 | 3/6 |
| BM25 | 25/32 | 3/6 |
| BGE vector retrieval | 5/32 | 0/6 |

Every arm also blocked **4/4 unavailable reports**, preserved **52/52 unaffected report IDs**, and produced zero incorrect-current claims. Missing-source refusal and no-op handling are the other two cases; neither adds a fresh completion.

Across the seven non-no-op cases, graph provider input exposure was **75,422/191,774 = 39.33%** of full context, passing the frozen ≤50% gate alongside complete graph correctness. Exposure includes uncached, cache-write and cache-read input exactly once. Receipt-only context was 35.47% of full context; it is a different measure. All 48 invocations completed with 96 reported CLI turns and **$9.8783764** in provider list estimates. That is not a verified subscription charge or a general cost-saving claim.

Graph and exact-flat had identical ordered prompts in all eight cases and tied on correctness. The five capped methods received the graph's varying per-case closure allowance; full context was uncapped. This is not a fixed 2,048-token experiment. One sample per case/method supports a bounded descriptive result. [Frozen protocol](MODEL_COMPARISON_PROTOCOL.md) · [Full per-case outcomes, usage and poststates](MODEL_COMPARISON_RESULTS.md).

## Earlier evidence remains separate

The deterministic retail v2 test refreshed **38/38** affected reports with **69.41% fewer evidence tokens** than full context. At graph-matched allowances BM25 achieved 19/38, BGE 8/38 and iterative hybrid 33/38; exact-flat tied. Its fixed 2,048-token graph condition achieved only **8/38**, and the development efficiency gate failed. [All conditions](RETAIL_V2_RESULTS.md).

The original four-case actual-model pilot achieved **5/9** graph refreshes; four recoverable reports stayed unresolved. [Original model results](AGENT_RESULTS.md). A separate two-request model-composition example passed 17 execution checks. [Composition evidence](COMPOSITION.md). These observations are neither replaced nor pooled with the fresh study.

## Why HydraDB

HydraDB OSS v0.4.0 stores the native dependency relationships between consumed inputs, executions and artifacts. The application uses it for cross-run impact traversal, currentness and path explanation, with persistent storage and no silent in-memory graph fallback. Content blobs and SQLite manifests are persisted separately.

The evidence supports explicit dependency context over relevance ranking for this workload. The exact-flat control shows that a correct recursive flat representation can reproduce the outcomes; we do not claim storage-engine-exclusive correctness.

## Verification and scope

The original public model package includes saved study inputs, poststates, provider counters, earlier failures, an explicit publication manifest and an offline Python verifier. The ZIP retained its bytes. The verifier ran in an isolated Linux network namespace and checked 346 bundle files, including 152 model payloads and all 48 scored cells. [Public model ZIP and verification instructions](PUBLIC_EVIDENCE.md).

The separate 52-payload delivery archive covers the saved `0535ba6`, `fdee9c9` and `92da58c` releases and the recorded retail CSV, paired recalculation, interrupted update and fixed-budget checks. It verifies those saved observations. Current browser acceptance uses its own hosted receipt. [Delivery archive and verification instructions](PUBLIC_DELIVERY_EVIDENCE.md).

- **Current hosted release.** The external runner passed 11 Chrome steps and 13 guided HTTP checks. Chrome verified the exact server snapshot on the clipboard and observed that the stale copy refusal preserved its existing contents. Ten public download responses matched the checkout. The application-only replacement passed 21 read-only host checks. [Hosted verification](HOSTED_DELIVERY.md).
- **Hosted retail CSV.** One external Chrome run on `92da58c` uploaded 642 UCI Online Retail positive-sales lines from January 16, 2011. After a staged GBP rate correction, the old export was refused and both checked reports matched the independent oracle at $9,414.68. All eligible rows were from the United Kingdom. [Observed workflow and scope](REAL_PARTITION_RESULTS.md).
- **Current release CI.** The first attempt passed 488 Python tests and nine default Chromium workflows across 23 successful job steps. The one-cent control detected both arithmetic differences. [Linux CI run, private repository access required](https://github.com/saivedant169/proofflow/actions/runs/43761386190).
- **Earlier hosted acceptance.** The `fdee9c9` release passed 11 external Chrome steps and 13 guided HTTP checks, including the CSV correction and checked download. [V2 receipt](../evidence/hosted_delivery_v2.json).
- **Earlier hosted restart.** The `0535ba6` app restart passed 87 checks across 12 HTTP responses, restoring saved CSV reports before a new correction and refresh. [Historical receipt](../evidence/hosted_delivery_v1.json).
- [Native persistence](../evidence/hydra_smoke.json): database restart, persisted traversal and a new write.
- [Packaged application](../evidence/deployment_smoke.json): 16 HTTP checks, including application restart and session/artifact preservation.
- [Interrupted update](RECOVERY_V1_RESULTS.md): 15/15 checks locally and in Linux CI after actual SIGKILL between committed source publications; stale values withheld, then full resubmission matched all eight uninterrupted artifact lineages.
- [Automated browser acceptance](BROWSER_ACCEPTANCE_RESULTS.md): six Chromium workflows, including session isolation, lost responses and partial publication. The same FX assertion detects a deliberately injected one-cent error. Earlier failed test/control attempts are retained.
- [Expanded local acceptance](REPORT_HANDOFF_ACCEPTANCE.md): nine Chromium workflows, adding checked downloads, refusal from a stale tab, handled export/reconciliation failures and exact large amounts. The integrated arithmetic control still detects both one-cent errors.
- [Earlier manual browser checks](UI_FIDELITY.md): desktop/mobile inspection and the distinct guided and CSV workflows.

The browser supports two fixed reports, at most 1 MiB/1,000 rows, USD/EUR/GBP and explicit rates. The larger benchmark uses the runtime directly. The app uses one worker/replica and defaults to sixteen active sessions; historical graph namespaces are retained. Browser execution is guided, with separately labeled recorded model evidence. No production reliability, broad model generalization, controlled latency improvement, learning uplift or customer adoption is established.

## Delivery fields

- **Private source.** Approved judge access remains pending. [saivedant169/proofflow](https://github.com/saivedant169/proofflow).
- **Hosted app.** The running release was verified at revision `b13f23892405efb856c8d4ca0e6abc94a1eca77c`. [ProofFlow](https://proofflow.arnavbule.in) · [Hosted verification receipt](../evidence/hosted_delivery_v4.json).
- **Video.** The served file matched the packaged film, the server returned the expected byte range, and external Chrome checked playback and seeking. [120-second walkthrough](https://proofflow.arnavbule.in/walkthrough.mp4).
- **CSV connector.** The setup page, downloadable script and checksum were verified over public HTTPS. [Connector setup](https://proofflow.arnavbule.in/agent/).
- **Public evidence.** The model and delivery ZIPs each include an offline verifier. [Evidence page](https://proofflow.arnavbule.in/evidence/).
- **Event.** The organizer’s form and final required fields remain unverified. The recorded deadline is 16 November 2026, 09:00 IST. Submission receipt pending. [HydraDB Hackathon](https://luma.com/bqwllms4).
