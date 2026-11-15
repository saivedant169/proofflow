# Model-chosen report composition

ProofFlow executed two reports whose tool plans were chosen by **Claude Fable 5.2 at high reasoning**. The model received the seven supported tool contracts and the current source/artifact handles. It received no example workflow, gold route, expected numbers, tool execution access, or benchmark labels. All report values came from the registered calculation tools.

This is a recorded local model run on two authored requests, separate from the [retrieval comparison](BENCHMARK_RESULTS.md). It is not a hosted model endpoint, a broad composition benchmark, or a learning-curve result.

## Observed behavior

The first request asked for company net revenue in USD and EU support workload. The model selected seven operations: gross orders, refunds, net revenue, USD conversion, company total, support aggregation, and report composition. Actual execution produced **$5,565 company revenue and 2 EU tickets**.

The second request asked for an EU operations brief with company revenue for context. The model selected **one `compose_report` operation**, directly consuming three artifacts from the earlier run. Its new report contained **$2,090 EU revenue, 2 EU tickets, and $5,565 company revenue**. This composition was selected by the model; it was not one of the two guided browser presets.

After an EUR→USD correction from 1.10 to 1.20, native HydraDB traversal reached both model-created reports. The runtime withheld stale monetary claims, refreshed four actual tools, and rebound the new EU report to updated upstream artifacts. The reports then contained **$2,280 EU revenue and $5,755 company revenue**. The independent support artifact retained its identity and was not executed again.

All **17 recorded checks passed**. A separate inspection of the saved native-path responses confirmed nonempty paths to both reports. The two calls completed without retries or fallback models, with **$0.172214 total provider-reported list cost**. Token usage, cache usage, canonical model, CLI turn counts, prompts and plans are retained in the raw files; this cost is not a claim about a subscription charge.

## Execution boundaries

The planner can select at most twelve registered tool steps. Inputs must refer to current supplied handles or earlier steps, and input types must match their contracts. Report sections can select supported USD-cent or ticket-count fields; they cannot inject numeric constants, arbitrary SQL, code, paths or tools. All structure is validated before the first tool runs. The execution request binds the exact immutable input IDs as well as the visible prompt, and descriptor identity, type and content hashes are checked again before execution.

The local CLI has external tools and MCP disabled. It uses the existing authenticated local process without reading or copying login material. Each call has a $1 and 180-second ceiling. A failed or malformed model answer is preserved rather than replaced by a preset plan.

## Inspect or reproduce

- [Compact composition evidence](../evidence/agent_composition.json)
- [Frozen prompt, schema and task preparation](../results/composition-v1/prepared.json)
- [First model plan](../results/composition-v1/plan-1.json) and [actual execution](../results/composition-v1/execution-1.json)
- [Second model plan](../results/composition-v1/plan-2.json) and [actual execution](../results/composition-v1/execution-2.json)
- [FX refresh, native paths and rebinding](../results/composition-v1/refresh.json)
- [Actual execution receipts](../results/composition-v1/receipts.json) and [check summary](../results/composition-v1/summary.json)

With local HydraDB and an authenticated Claude Code CLI:

```sh
uv run python scripts/composition_probe.py --output results/composition-reproduction
# Inspect prepared.json and request-1.json, then explicitly enable the two calls:
uv run python scripts/composition_probe.py --output results/composition-reproduction --run-paid
```

The run refuses to overwrite an existing attempt, requires the composition harness to be committed, and refuses code/task changes after preparation. A reproduction may produce another valid workflow or a failure; the model result is not forced to match this recording.
