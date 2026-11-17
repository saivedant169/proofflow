# ProofFlow film: narration script

The narrator reads these words exactly. Section ids (s1–s8) and line ids (in brackets) are the keys scenes use through `FILM.at()` and `FILM.line()`. Every claim below is checked against the repository:

- $5,565 and the EUR correction: README.md guided-sample table.
- "re-runs only the affected steps" (four tools, support reused): README.md, proofflow/demo.py.
- CSV preview, publish correction, refresh, checked copy only while current: README.md "Use your own CSV".
- Five MCP tools; hosts choose plans; no arbitrary code: README.md "Connect an agent", docs/AGENT_QUICKSTART.md.
- Runtime, hash-verified store, HydraDB native traversal, fail closed: README.md "How it works", proofflow/runtime.py, artifacts.py, graph.py, api.py.
- 32/32 at 39.33% of full context's provider input exposure; BM25 25/32; BGE 5/32: docs/MODEL_COMPARISON_RESULTS.md.
- Retail 38/38, 69.41% fewer evidence tokens; exact-flat ties: docs/RETAIL_V2_RESULTS.md, README.md.

Pace: about 135 words a minute, calm, warm, credible, unhurried. Pause briefly at each line break.

## s1 — Monday (hook)

[1a] Monday. Your AI agent saves a report.
[1b] Company revenue: five thousand, five hundred sixty-five dollars.
[1c] Tuesday, someone corrects the euro exchange rate.
[1d] The report doesn't change. Nothing tells it that it's wrong.

## s2 — The problem

[2a] Agents build on their own saved work, so every number quietly depends on inputs underneath.
[2b] When one input changes, which numbers are now wrong?
[2c] Re-reading everything floods the model with context.
[2d] Searching for related text misses numbers that depend on the change but never mention it.

## s3 — The idea

[3a] ProofFlow takes a different path.
[3b] Every number keeps its receipts: exactly which inputs, and which calculation, made it.
[3c] So it knows what to hold back, and what to redo.

## s4 — How it works

[4a] An input, like the exchange rate, is saved as a version.
[4b] A tool reads it, and leaves a receipt.
[4c] The receipt points to its result, and each number in a report points to that result.
[4d] Now, correct the rate.
[4e] The change travels up those links. Both revenue figures are withheld, never shown stale.
[4f] Support never read the rate, so it stays.
[4g] Refresh re-runs only the affected steps.

## s5 — Working today

[5a] This is ProofFlow, running today.
[5b] Upload orders as a CSV, preview them, and create the reports.
[5c] Publish a corrected rate. Affected figures are withheld, and the evidence path shows why.
[5d] Refresh brings them current, and a checked report can only be copied while every figure is current.
[5e] Agents get the same power, through five MCP tools.

## s6 — Under the hood

[6a] Under the hood, it's small, and strict.
[6b] At the center is the runtime. Every tool run produces an immutable result, and a receipt.
[6c] Content goes into a store that verifies every hash.
[6d] Relationships go into HydraDB, as a lineage graph.
[6e] When a correction arrives, HydraDB walks that graph natively, to find everything downstream.
[6f] The runtime re-runs stale steps in order, reuses what's current, and records new receipts.
[6g] If evidence is missing, it fails closed. No fallback. No guess.
[6h] Around it: a browser app, a Python API, and an MCP server.
[6i] Agents choose plans from typed tools, but never run arbitrary code.

(Then about six seconds with no voice: the finished system runs one correction end to end, then holds.)

## s7 — Results

[7a] Does it work?
[7b] In a frozen study with a real model, ProofFlow refreshed all thirty-two affected reports, matching full context at under forty percent of its input.
[7c] Keyword search managed twenty-five. Vector search, five.
[7d] On a retail benchmark: thirty-eight of thirty-eight, with sixty-nine percent fewer evidence tokens.
[7e] A plain dependency walk ties it. The point is recording dependencies.

## s8 — Close

[8a] ProofFlow.
[8b] Saved reports that know when they're out of date.
[8c] The sample data is authored. Every result shown is in the public evidence.
