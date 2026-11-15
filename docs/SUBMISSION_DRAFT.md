# ProofFlow submission draft

The application, comparative pilots, local container deployment and 120-second walkthrough are complete. Public hosting and the organizer's form remain pending; this document is not a submission receipt. The [source repository](https://github.com/saivedant169/proofflow) is **private until the user explicitly directs release**.

## Project name and track

**ProofFlow — Track 2: agent context layer.** Final field wording depends on the organizer's submission form. This submission demonstrates cross-run reuse and correction propagation; it does not claim a measured learning curve.

## Short description

ProofFlow gives analytics agents current, traceable context across runs. It records the data and intermediate results actually consumed by tools, follows dependency paths in HydraDB when inputs change, and refreshes affected outputs while preserving unrelated work.

## Problem

An agent's saved report can be relevant and still be out of date. A source correction or missing input can invalidate calculations reused across later runs. Similarity retrieval can find related receipts, but a recurring analytics agent also needs the complete dependency chain and evidence that a reused value is still current.

ProofFlow serves the engineer operating that agent and the analyst relying on its numbers. Its central question is: **which evidence from an earlier run is still usable now?**

## What we built

ProofFlow combines a typed analytics runtime, a persistent dependency graph and a browser workspace. Registered tools perform SQLite aggregations and Decimal currency calculations. Immutable source, tool and artifact versions capture exact consumed inputs, computed content and execution receipts. HydraDB-native traversal finds affected descendants and checks upstream evidence. Refresh executes dependencies in order and binds downstream reports to the new intermediate artifacts.

The React/Vite/TypeScript interface shows two report runs, real graph evidence and tool activity. Visitors can correct an exchange rate, order, refund or support count; remove an input; refresh affected work; verify values against independent recomputation; and reset their isolated session. Stale monetary claims are withheld while independent current claims stay visible. The FastAPI application and built frontend run together with persistent state, and the Docker deployment passed sixteen HTTP checks including application restart.

A local CSV CLI accepts bounded user-supplied transaction rows, executes the same tools and refreshes a persisted workspace after changes. Its authored non-EU integration verified correction propagation, preservation of unrelated support, and no new calculations after row reordering. The browser demonstration uses the labeled authored fixture rather than a CSV upload interface.

## Why HydraDB matters

HydraDB OSS v0.4.0, pinned by container digest, stores the direct inputs consumed by executions and the produced artifacts. The runtime follows these relationships across run boundaries to determine currentness and change impact. A failed graph query is visible; the app does not silently fall back to an in-memory graph. Artifact content and manifests have separate persistent storage.

Explicit dependencies are the demonstrated advantage. A correct recursive flat dependency implementation can produce the same answer, and our representation control does. The comparison does not claim that only a graph database can compute dependency closure.

## Demonstration

The company report and EU brief reuse intermediate calculations across runs. Correcting EUR→USD from 1.10 to 1.20 reaches four saved outputs through native Hydra paths. Revenue claims become unavailable as current evidence until refreshed; the separate support count remains current.

Four actual tool calls update EU revenue from **$2,090 to $2,280** and company revenue from **$5,565 to $5,755**. The support count stays **2** with the same artifact identity and content hash. Independent recomputation matches the updated report values. Removing the FX source instead makes refresh refuse the unavailable calculation.

## Comparative evidence

The twelve-scenario held-out pilot uses authored workloads, real dense embeddings and a common deterministic evidence reader. Every arm receives the same records, dependency IDs, scope filtering, exact-ID seeding and **2,048-token evidence budget**. Every arm also uses the same Hydra-assisted currentness checks and recursive refresh executor. The intervention is the retrieved context.

| Retrieval method | Mean affected-artifact recall | Fresh affected reports after actual refresh |
|---|---:|---:|
| BM25 | 41.4% | 6/29 |
| Dense BGE | 37.5% | 1/29 |
| Hybrid RRF | 38.4% | 4/29 |
| Iterative hybrid | 63.9% | 9/29 |
| ProofFlow / HydraDB | 87.2% | 16/29 |
| Exact flat dependency traversal | 87.2% | 16/29 |

The denominator counts affected reports with an available independent numeric oracle. Two unavailable reports are blocked and reported separately. No LLM participates in this table. Dense retrieval uses actual FastEmbed ONNX embeddings from `BAAI/bge-small-en-v1.5`, with tokenizer-aware chunking. The [complete report](BENCHMARK_RESULTS.md) includes every case, the 512/1,024/2,048/unlimited budget ladder, frozen hashes and raw results.

We then ran a separate **16-call model pilot**: four prespecified cases × four retrieval arms, using **Claude Fable 5.2 at high reasoning**, one planning step per attempt, no retries or fallback, and the same evidence budget and executor. All sixteen model attempts completed; none failed or abstained.

| Model context | Fresh affected reports |
|---|---:|
| BM25 | 1/9 |
| Dense BGE | 0/9 |
| Iterative hybrid | 2/9 |
| ProofFlow / HydraDB | 5/9 |

ProofFlow still left **4/9 recoverable affected reports unresolved** in this small model pilot. Missing-source blocking is shared executor behavior, and every arm served zero incorrect-current reports. [Full model results](AGENT_RESULTS.md) retain all cases, omissions, failures, prompts, plans and provider usage. Neither pilot establishes broad or statistical superiority across domains.

## Model-chosen composition and reuse

In a separate two-call local run, Fable 5.2 at high reasoning chose a seven-step workflow for a company report. For the next request, it chose **one `compose_report` step reusing three earlier artifacts** to create a new EU brief. It received tool contracts and current handles, without an example workflow, gold plan or expected numbers. The registered tools computed every numeric value.

After the FX correction, native Hydra traversal reached both model-created reports. Four tools refreshed the dependent work, the EU brief rebound to the new upstream versions, and support retained its identity. All **17 composition checks passed**. The [composition evidence](COMPOSITION.md) contains both model plans and actual tool receipts. The browser labels this **Recorded agent workflow**; it is not a live hosted model endpoint or a learning-curve measurement.

## Engineering and product direction

The initial integration point is a recurring analytics assistant that already calls stable tools and saves intermediate outputs. Capturing those execution receipts makes provenance and selective refresh possible without requiring an analyst to maintain a second manual dependency graph. The local CSV adapter demonstrates reuse beyond the browser fixture.

A useful customer pilot would connect one recurring reporting workflow, introduce real source corrections, and measure complete report refresh, withheld stale claims, preserved artifacts and total operational cost. Those customer outcomes have not been measured yet. The current contribution is a working context layer with inspectable comparative evidence and a clear integration boundary.

## Technology and verification

Python 3.12, FastAPI, SQLite manifests and aggregations, Decimal monetary arithmetic, HydraDB OSS, React, Vite, TypeScript and Docker Compose. BM25 and real BGE embeddings provide retrieval baselines; local Claude Code provides the recorded Fable planning calls. No model or Hydra credential reaches the browser.

- [Core execution checks](../evidence/core_smoke.json): cross-run dependency propagation, actual selective refresh, independent numerical parity and refusal on missing evidence.
- [HydraDB checks](../evidence/hydra_smoke.json): native path traversal, persisted reads and a new write after database restart.
- [Container deployment checks](../evidence/deployment_smoke.json): 16/16, including compiled assets, real HTTP mutations, preserved browser session/artifact IDs after app restart, refusal and reset.
- [Browser verification](UI_FIDELITY.md): desktop and mobile, FX correction, evidence inspection, refresh, restart recovery, missing source and reset.
- [CSV integration](../results/import-smoke-v1/verification.json): authored input through actual HydraDB, preserved support and order-insensitive no-op replay.

## Limitations

The workloads are authored and small. The finite-budget graph misses some dependencies, and exact flat traversal ties it. With all evidence available, all retrieval selectors recover the exact affected sets; full context refreshes 29/29 eligible affected reports. ProofFlow's main-budget run makes more tool calls than BM25 because it completes more required work, so the table is not a cost-saving claim.

The model comparison is one sample per case and condition; cache warmth was not controlled, so no model-cost or latency advantage is claimed. Model composition supports registered typed tools, not arbitrary SQL or code. The browser uses guided real execution and recorded model evidence. The app supports one worker/replica and sixteen active sessions by default; historical Hydra namespaces are retained without garbage collection.

## Delivery fields

- **Source:** https://github.com/saivedant169/proofflow — private; access for judges is not presumed.
- **Local working app:** http://127.0.0.1:18080. This is not a judge-accessible hosted URL.
- **Hosted app:** pending the existing hosting target and final HTTPS deployment.
- **Video:** [completed 120-second 1080p walkthrough](../video/proofflow-walkthrough.mp4), included in the Docker image at `/walkthrough.mp4`. Its shareable URL will use the final HTTPS origin.
- **Event:** [HydraDB Hackathon, November 14–16](https://luma.com/bqwllms4).
- **Submission form:** not live according to the project owner's latest update. Final fields and team/contact details await that form.
- **Delivery deadline:** 16 November 2026, 09:00 IST. No submission receipt has been issued.
