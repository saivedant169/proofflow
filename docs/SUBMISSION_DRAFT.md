# ProofFlow submission draft

The application, audited retail benchmark, earlier pilots, local container deployment and 120-second functional walkthrough are complete. Hosting is on hold and will be handled by the project owner; the organizer's form is not open. This document is not a submission receipt. The [source repository](https://github.com/saivedant169/proofflow) is **private until the user explicitly directs release**.

## Project name and track

**ProofFlow — Track 2: agent context layer.** Final field wording depends on the organizer's submission form. This submission demonstrates cross-run reuse and correction propagation; it does not claim a measured learning curve.

## Short description

ProofFlow gives analytics agents current, traceable context across runs. It records the data and intermediate results actually consumed by tools, follows dependency paths in HydraDB when inputs change, and refreshes affected outputs while preserving unrelated work.

In the audited retail test, the complete dependency path refreshed **38/38 recoverable affected reports** and correctly blocked **4/4 unavailable reports**, with **69.41% fewer evidence tokens than full context**. At the same per-case evidence allowance, BM25 refreshed 19/38, dense BGE 8/38 and iterative hybrid 33/38. Exact-flat traversal ties ProofFlow, and all arms use the same Hydra-assisted executor.

## Problem

An agent's saved report can be relevant and still be out of date. A source correction or missing input can invalidate calculations reused across later runs. Similarity retrieval can find related receipts, but a recurring analytics agent also needs the complete dependency chain and evidence that a reused value is still current.

ProofFlow serves the engineer operating that agent and the analyst relying on its numbers. Its central question is: **which evidence from an earlier run is still usable now?**

## What we built

ProofFlow combines a typed analytics runtime, a persistent dependency graph and a browser workspace. Registered tools perform SQLite aggregations and Decimal currency calculations. Immutable source, tool and artifact versions capture exact consumed inputs, computed content and execution receipts. HydraDB-native traversal finds affected descendants and checks upstream evidence. Refresh executes dependencies in order and binds downstream reports to the new intermediate artifacts.

A five-tool stdio MCP interface lets an external host load its own CSV, prepare typed evidence, execute a client-selected plan, inspect currentness and refresh affected artifacts. It accepts no arbitrary code, SQL or file paths. The server runs no model; the client chooses the plan.

The React/Vite/TypeScript interface shows two report runs, real graph evidence and tool activity. Visitors can correct an exchange rate, order, refund or support count; remove an input; refresh affected work; verify values against independent recomputation; and reset their isolated session. Stale monetary claims are withheld while independent current claims stay visible. The FastAPI application and built frontend run together with persistent state, and the Docker deployment passed sixteen HTTP checks including application restart.

A local CSV CLI accepts bounded user-supplied transaction rows, executes the same tools and refreshes a persisted workspace after changes. Its authored non-EU integration verified correction propagation, preservation of unrelated support, and no new recorded refresh calls after row reordering. Each successful two-report CLI invocation also performs **16 arithmetic preflight calculations** and **11 report-verification calculations**, separately from its recorded runtime calls. Zero recorded refresh calls on reordered input therefore still includes 27 validation/verification calculations. The browser also accepts the same bounded CSV schema through **Use your data → Validate CSV → Create reports**, producing two revenue-only reports for the company and a chosen region. **Update CSV → Publish correction** changes sources and leaves affected claims stale; **Refresh affected** recalculates them. The guided demonstration and imported workspace remain independent. This is a fixed-recipe flow, not an arbitrary query or live model endpoint.

Interactive browser checks against Docker revision `a2eb61b` verified NORTH company/region values **$308/$108 → $317/$117** after EUR 1.20→1.30, with four refresh calls, preserved no-op artifact identities, and persistence after app restart. A zero-support APAC case produced **$163.75/$93.75** in revenue-only reports. Malformed and >1 MiB input were rejected, including after preview; desktop and 390px mobile views were inspected. These authored checks are separate from the retail benchmark.

Browser accounting remains explicit: **8 preview preflight + 8 create preflight + 8 recorded calls + 11 verification = 35 calculations** for one preview-and-create path, with 27 reported by creation alone. Bounds are 1 MiB, 1,000 rows, 10,000 total ticket counts, USD/EUR/GBP and one currency per region. Rates are caller-supplied, money is integer cents, and the imported region stays fixed until a new workspace is created. CSV contents are sent to the ProofFlow server; no live model receives them through this flow.

**CLI accounting correction:** earlier documentation generalized the MCP route's eight preflight calculations to every CSV load. The CLI already performed eight during parsing, eight at its public import boundary and eleven during report verification; the counters now disclose that existing work. MCP remains eight per load, including the recorded experiment's sixteen across two loads. Original raw captures and all benchmark/MCP results are retained unchanged.

## Why HydraDB matters

HydraDB OSS v0.4.0, pinned by container digest, stores the direct inputs consumed by executions and the produced artifacts. The runtime follows these relationships across run boundaries to determine currentness and change impact. A failed graph query is visible; the app does not silently fall back to an in-memory graph. Artifact content and manifests have separate persistent storage.

Explicit dependencies are the demonstrated advantage. A correct recursive flat dependency implementation can produce the same answer, and our representation control does. The comparison does not claim that only a graph database can compute dependency closure.

## Demonstration

The company report and EU brief reuse intermediate calculations across runs. Correcting EUR→USD from 1.10 to 1.20 reaches four saved outputs through native Hydra paths. Revenue claims become unavailable as current evidence until refreshed; the separate support count remains current.

Four actual tool calls update EU revenue from **$2,090 to $2,280** and company revenue from **$5,565 to $5,755**. The support count stays **2** with the same artifact identity and content hash. Independent recomputation matches the updated report values. Removing the FX source instead makes refresh refuse the unavailable calculation.

## Primary evidence: retail v2

The frozen retail test uses **640 externally sourced UCI positive-sales lines across four dated partitions**, ten authored interventions and declared report compositions. It is deterministic: registered tools calculate results and a common reader selects from the returned evidence; no LLM participates. Every case exposes 39 artifacts, including 11 reports. All methods share serialized records, dependency identifiers, scope, exact-ID access and the same Hydra-assisted currentness and recursive refresh executor.

The complete graph path, exact-flat traversal and full context match on all scoped artifact states and values. Each refreshes **38/38 recoverable affected reports** and blocks **4/4 unavailable reports**. The **10/10 correct endstates include the missing-source refusal and a no-op**, not ten newly calculated answers.

Graph evidence totals **39,375/128,729 full-context tokens**, or **30.59%**: **69.41% fewer evidence tokens**. This passes the unchanged aggregate ≤40% gate. Excluding the no-op, the ratio is 33.99%; two individual cases exceed 40%. All three complete conditions execute 101 tools, so this is not a tool-call reduction or measured LLM-dollar saving.

The following baselines receive each case's complete graph-closure token allowance, established before comparator execution. Allowances vary from **0 to 9,611 tokens**; whole-record packing may leave unused space.

| Evidence selector | Fresh affected reports | Correct endstate cases |
|---|---:|---:|
| ProofFlow / HydraDB | 38/38 | 10/10 |
| Exact flat traversal | 38/38 | 10/10 |
| BM25 | 19/38 | 3/10 |
| Dense BGE | 8/38 | 2/10 |
| Iterative hybrid | 33/38 | 6/10 |

The separate **fixed 2,048-token diagnostic** completes only **8/38** for graph/exact-flat, **1/38** for BM25, **0/38** for dense and **4/38** for iterative hybrid. Every fixed-budget arm has **2/10 correct endstates: R07's expected refusal and R09's no-op**. Neither is a successfully refreshed affected-report case. The complete graph result must not be attributed to this constrained budget.

The development efficiency gate remains a recorded **failure**: **60.79%** graph/full-context token ratio exceeded the unchanged 40% threshold, or 81.07% excluding the no-op. Development correctness passed, but it was not pooled with held-out test. The [retail report](RETAIL_V2_RESULTS.md), [frozen protocol](RETAIL_V2_SPEC.md) and [audited summary](../evidence/retail_v2_summary.json) retain every condition, refusal, failure and raw record. Dataset prices are GBP; FX, refunds and corrections are staged assumptions rather than historical incidents. See [dataset attribution and modifications](../fixtures/retail_v2/DATASET_NOTICE.md).

## Earlier pilots, reported separately

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

## Actual MCP-client integration

A real Claude Code client using **Fable 5.2 at high reasoning** completed one corrected trajectory through the five-tool stdio server: two source loads, two client-chosen compositions, stale inspection, refresh and inspection of the replacements. The recorded run passes **32 checks**. It made **9 MCP requests across 10 CLI turns**, with seven initial tool executions, one composition reusing earlier artifacts, and four refresh executions: **12 recorded runtime calls**. The two CSV loads also performed **16 arithmetic preflight checks**, counted separately.

The first attempt is retained as a configuration failure: safe mode suppressed MCP discovery and zero ProofFlow tools ran. The corrected attempt repaired launch isolation and used the same task, apart from a fresh workspace nonce. Provider list accounting was **$0.809898** for the corrected trajectory plus **$0.037144** for the failed first attempt: **two attempts, $0.847042 total**. These figures are not subscription billing or a cost benchmark.

This is one authored two-row integration, separate from retail v2 and the original model pilot. The MCP server itself makes zero model calls; the Claude client makes the model calls. [Client results and transcript audit](MCP_AGENT_RESULTS.md) retain the failed attempt, plans, receipts, usage and scope.

## Engineering and product direction

The initial integration point is a recurring analytics assistant that already calls stable tools and saves intermediate outputs. The five MCP tools make the context layer accessible from an existing local agent host, while the CSV adapter supplies a bounded path for caller data. Capturing those execution receipts makes provenance and selective refresh possible without requiring an analyst to maintain a second manual dependency graph. The local CSV adapter demonstrates reuse beyond the browser fixture.

A useful customer pilot would connect one recurring reporting workflow, introduce real source corrections, and measure complete report refresh, withheld stale claims, preserved artifacts and total operational cost. Those customer outcomes have not been measured yet. The current contribution is a working context layer with inspectable comparative evidence and a clear integration boundary.

## Technology and verification

Python 3.12, FastAPI, SQLite manifests and aggregations, Decimal monetary arithmetic, HydraDB OSS, React, Vite, TypeScript and Docker Compose. BM25 and real BGE embeddings provide retrieval baselines; local Claude Code provides the recorded Fable planning calls. No model or Hydra credential reaches the browser.

- [Core execution checks](../evidence/core_smoke.json): cross-run dependency propagation, actual selective refresh, independent numerical parity and refusal on missing evidence.
- [HydraDB checks](../evidence/hydra_smoke.json): native path traversal, persisted reads and a new write after database restart.
- [Container deployment checks](../evidence/deployment_smoke.json): 16/16, including compiled assets, real HTTP mutations, preserved browser session/artifact IDs after app restart, refusal and reset.
- [Browser verification](UI_FIDELITY.md) and [13 observed CSV checks](../evidence/browser_csv_verification.json): guided demo plus CSV preview, creation, correction, no-op replay, malformed/oversized rejection, zero-support revenue reports, restart recovery and desktop/mobile inspection. These are interactive browser observations, not an automated end-to-end suite.
- [CSV integration](../results/import-smoke-v1/verification.json): authored input through actual HydraDB, preserved support and order-insensitive no-op replay.
- [Stock MCP process check](../results/mcp-v1/summary.json): 20 checks without a model.
- [Actual MCP-client run](../results/mcp-agent-v2/summary.json): 32 recorded checks, with the first configuration failure retained separately.

## Limitations

Retail v2 is a bounded external positive-sales sample with authored changes, not a production customer study. Its complete dependency path succeeds, while a fixed 2,048-token budget leaves recoverable reports unresolved. Exact-flat traversal ties graph. The 69.41% reduction concerns serialized evidence against full context; no learned policy, model-dollar savings, controlled latency advantage or statistical superiority is established.

All retrieval methods share Hydra-backed safety and recursive execution. Missing-source blocking and zero incorrect-current artifacts are shared properties. Lower tool-call totals can reflect unfinished work. The failed development efficiency gate and constrained-budget results remain visible.

The original model comparison uses one sample per case and condition; cache warmth was not controlled. The MCP result is one corrected client trajectory over two authored rows, with its failed first attempt retained. Model composition supports registered typed tools, not arbitrary SQL or code. The browser uses guided execution and recorded model evidence. The app supports one worker/replica and sixteen active sessions by default; historical Hydra namespaces are retained without garbage collection.

## Delivery fields

- **Source:** https://github.com/saivedant169/proofflow — private; access for judges is not presumed.
- **Local working app:** http://127.0.0.1:18080. This is not a judge-accessible hosted URL.
- **Hosted app:** on hold; deployment will be handled by the project owner. No public URL is claimed.
- **Video:** [completed 120-second 1080p walkthrough](../video/proofflow-walkthrough.mp4) briefly shows CSV preview and report creation, then a separately labeled guided correction flow, retail v2 results and actual MCP-client evidence. The application packages video at `/walkthrough.mp4`; [previous-version delivery verification](../evidence/video_delivery_v2.json) is retained as historical evidence for the earlier film. The full CSV correction remains a longer live demonstration. A public URL is not yet claimed.
- **Event:** [HydraDB Hackathon, November 14–16](https://luma.com/bqwllms4).
- **Submission form:** not live according to the project owner's latest update. Final fields and team/contact details await that form.
- **Delivery deadline:** 16 November 2026, 09:00 IST. No submission receipt has been issued.
