# ProofFlow submission draft

The application, benchmark evidence and local walkthrough are built. The owner will deploy the app; hosted verification, approved judge source access and the organizer's form remain pending. The repository stays private. This document is not a submission receipt.

## Project and track

**ProofFlow — Track 2: agent context layer.** Final field wording depends on the organizer's form. The project demonstrates cross-run reuse and correction propagation; it claims no measured learning uplift.

## Short description

**Keep saved agent reports current when an input changes.** ProofFlow records the inputs behind each supported number, follows their dependencies in HydraDB, withholds outdated claims and refreshes affected calculations while preserving valid work. Analysts can try company and regional revenue with a compatible orders CSV; local MCP clients can compose reports from typed tools and reuse earlier results.

In a frozen 48-invocation actual-model study, ProofFlow refreshed **32/32 affected reports**, matching full context at **39.33% of its provider input exposure**, excluding the no-op case. At matched per-case evidence allowances, BM25 refreshed 25/32, BGE vector retrieval 5/32 and iterative hybrid 28/32. Exact-flat traversal also achieved 32/32. All methods share the same safe executor. [Results and limits](MODEL_COMPARISON_RESULTS.md).

## Problem and first user

A saved agent report can be relevant and still be out of date. When an exchange rate, refund or tool changes, later reports may reuse calculations made from earlier inputs. The analyst needs to know which figures are still usable, which require repair, and why.

In a recurring commerce revenue handoff, an analyst may need to correct an input after saving company and regional figures. ProofFlow checks those figures against their recorded dependencies when reading or downloading the reports. The analyst supplies the underlying business data. Customer demand and time savings have not yet been measured.

## What works

Seven registered tools perform SQLite aggregations, Decimal currency calculations and typed report composition. Immutable source, tool and artifact versions record exact consumed inputs and execution receipts. HydraDB-native traversal finds affected descendants and upstream evidence. Refresh recalculates prerequisites and rebinds downstream reports to current intermediate results.

The browser accepts a bounded CSV, previews it without publishing, and creates two revenue-only reports for the company and selected region. Publishing a correction changes sources and withholds affected monetary values. Refresh brings recoverable reports up to date; independent support remains reusable. The guided sample and imported workspace are separate.

**Download current reports** in the CSV workspace creates a static, UTC-timestamped text file with the two USD figures, their labels, and immutable report and claim artifact IDs. The server checks that the displayed workspace generation and both report IDs still match, and that both reports and their claims are current. A stale claim, incomplete source publication, unavailable evidence, or a newer workspace or report version in another tab blocks the download.

Five local stdio MCP tools expose source loading, preparation, client-selected plan execution, currentness inspection and refresh. The external model chooses a bounded plan; registered tools compute the numbers. The server makes no model calls and accepts no arbitrary code or SQL. A recorded Fable 5.2/high MCP client completed one corrected trajectory with 32 checks, cross-run composition and reuse; its first launch-configuration failure is retained. [Agent quickstart](AGENT_QUICKSTART.md) · [Client evidence](MCP_AGENT_RESULTS.md).

## Live demonstration

1. Upload the authored two-row NORTH/SOUTH CSV with EUR→USD at 1.20. The current company and NORTH reports are **$308 / $108**.
2. Publish the same CSV with the corrected rate 1.30. Four artifacts become stale, current monetary values are withheld, and native graph evidence explains the impact. Support remains current.
3. Refresh the affected work. Four recorded tool calls produce **$317 / $117**, verified against independent arithmetic. Validation and verification calculations are counted separately; four recorded calls are not the complete computation cost. Choose **Download current reports** to capture the refreshed figures and their artifact IDs for the handoff.

The 120-second film shows this CSV preview/creation briefly, then explicitly switches to a separate guided fixture, the audited 48-invocation model comparison and recorded MCP evidence. Earlier deterministic failures remain visible in a separate limits card. Those fixtures and experiments are not pooled. [Video](../video/proofflow-walkthrough.mp4) · [Narration](VIDEO_SCRIPT.md).

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

- [Native persistence](../evidence/hydra_smoke.json): database restart, persisted traversal and a new write.
- [Packaged application](../evidence/deployment_smoke.json): 16 HTTP checks, including application restart and session/artifact preservation.
- [Interrupted update](RECOVERY_V1_RESULTS.md): 15/15 checks locally and in Linux CI after actual SIGKILL between committed source publications; stale values withheld, then full resubmission matched all eight uninterrupted artifact lineages.
- [Automated browser acceptance](BROWSER_ACCEPTANCE_RESULTS.md): six Chromium workflows, including session isolation, lost responses and partial publication. The same FX assertion detects a deliberately injected one-cent error. Earlier failed test/control attempts are retained.
- [Expanded local acceptance](REPORT_HANDOFF_ACCEPTANCE.md): nine Chromium workflows, adding checked downloads, refusal from a stale tab, handled export/reconciliation failures and exact large amounts. The integrated arithmetic control still detects both one-cent errors.
- [Earlier manual browser checks](UI_FIDELITY.md): desktop/mobile inspection and the distinct guided and CSV workflows.

The browser supports two fixed reports, at most 1 MiB/1,000 rows, USD/EUR/GBP and explicit rates. The larger benchmark uses the runtime directly. The app uses one worker/replica and defaults to sixteen active sessions; historical graph namespaces are retained. Browser execution is guided, with separately labeled recorded model evidence. No production reliability, broad model generalization, controlled latency improvement, learning uplift or customer adoption is established.

## Delivery fields

- **Private source:** [saivedant169/proofflow](https://github.com/saivedant169/proofflow). Judge access must be confirmed; privacy is not changed by app deployment.
- **Local app:** http://127.0.0.1:18080. This is not a hosted judge URL.
- **Hosted app:** owner deployment on hold; no public URL or hosted verification claimed.
- **Video:** [local 120-second walkthrough](../video/proofflow-walkthrough.mp4), packaged at `/walkthrough.mp4`; [updated-film local delivery](../evidence/video_delivery_v4.json) passed exact-hash, MIME and HTTP range checks. Public delivery remains pending.
- **Event:** [HydraDB Hackathon](https://luma.com/bqwllms4). The organizer's form and final required fields remain unverified.
- **Deadline:** 16 November 2026, 09:00 IST. No submission receipt exists.
