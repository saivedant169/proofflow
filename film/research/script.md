# ProofFlow film: narration script (v2, product-page framing)

The narrator reads these words exactly. Section ids (s1–s8) and line ids (in brackets) are the keys scenes use through `FILM.at()` and `FILM.line()`. The framing follows the product page (website/): full-context accuracy at vector-search cost, measured against today's approaches. Every claim is checked against the repository:

- Study: 8 frozen cases × 6 methods = 48 real model calls (Fable 5.2), same safe executor: docs/MODEL_COMPARISON_RESULTS.md.
- Full context 32/32, 219,145 input tokens, $3.7423680 list. ProofFlow graph 32/32, 77,071 tokens, $1.3772140 → 142,074 fewer tokens, 63% lower list cost. BGE vector 5/32 at $1.3776310; BM25 25/32; iterative hybrid 28/32: same file, provider accounting table.
- Retail v2: 38/38 at 69.41% fewer evidence tokens (39,375 vs 128,729); exact-flat ties: docs/RETAIL_V2_RESULTS.md.
- $5,565 → $5,755 company and $2,090 → $2,280 EU brief, four tools re-run, support reused: README.md guided sample, proofflow/demo.py.
- CSV preview → create → publish correction → refresh → checked copy only while current: README.md "Use your own CSV".
- Hosted connector: six MCP tools, one download: docs/AGENT_QUICKSTART.md, website facts.
- Runtime, hash-verified store, HydraDB native traversal, fail closed (503 / 409), typed tools, no arbitrary code: README.md "How it works", proofflow/runtime.py, artifacts.py, graph.py, api.py.
- Not claimed: speed/latency, learning uplift, customer adoption. List prices are provider list estimates, not invoices.

Pace: about 140 words a minute, calm, warm, confident, unhurried. Pause briefly at each line break.

## s1 — Two bad options (hook)

[1a] One input changes. Now your AI agent has to work out what that broke.
[1b] Today, it has two options.
[1c] Re-read everything. Accurate, but you pay for every token, every time.
[1d] Or search for what looks related. Cheap, but blind to what matters.

## s2 — Why search goes blind

[2a] Agents build reports on their own earlier work, so every number quietly depends on inputs underneath.
[2b] Correct one exchange rate, and some of those numbers are now wrong.
[2c] But a total can depend on that rate without ever mentioning it.
[2d] Similar words are not the same as real dependencies.

## s3 — The idea

[3a] ProofFlow is a context layer that follows structure instead of guessing.
[3b] Every number keeps its receipts: exactly which inputs, and which tool, made it.
[3c] So when something changes, the agent gets exactly what broke. Nothing more.

## s4 — How it works

[4a] An input, like the exchange rate, is saved as a version.
[4b] A tool reads it, and leaves a receipt.
[4c] The receipt points to its result, and each number in a report points to that result.
[4d] Now, correct the rate.
[4e] The change travels up those links. Both revenue figures are withheld, never shown stale.
[4f] Support never read the rate, so it stays current, and is reused.
[4g] Refresh re-runs only the affected steps.

## s5 — Live today

[5a] This is ProofFlow, live today.
[5b] Upload orders as a CSV, preview them, and create two reports.
[5c] Publish a corrected rate. Affected figures are withheld, and the graph shows exactly why.
[5d] Refresh brings them current. A checked report can only be copied while every figure is current.
[5e] Agents get the same workflow through MCP. Six tools, one download.

## s6 — Under the hood

[6a] Under the hood, it's small, and strict.
[6b] At the center is the runtime. Every tool run produces an immutable result, and a receipt.
[6c] Content goes into a store that verifies every hash.
[6d] Relationships go into HydraDB, as a lineage graph.
[6e] When a correction arrives, HydraDB walks that graph natively, to find everything downstream.
[6f] That walk becomes the agent's context. Traverse the structure. Skip the re-read.
[6g] The runtime re-runs stale steps in order, reuses what's current, and records new receipts.
[6h] If evidence is missing, it fails closed. No fallback. No guess.
[6i] Agents reach it through a browser app, a Python API, or an MCP server, choosing plans from typed tools, never arbitrary code.

(Then about six seconds with no voice: the finished system runs one correction end to end, then holds.)

## s7 — Against today's approaches

[7a] So how does it compare to today's approaches?
[7b] We froze one study. Forty-eight real model calls, the same task for every method.
[7c] Re-reading everything got all thirty-two reports right, for three dollars seventy-four.
[7d] ProofFlow also got thirty-two of thirty-two, with a hundred forty-two thousand fewer input tokens, for a dollar thirty-eight. Sixty-three percent less.
[7e] Vector search cost the same as ProofFlow, and got five right. Keyword search, twenty-five. Hybrid, twenty-eight.
[7f] On a separate retail benchmark, thirty-eight of thirty-eight, with sixty-nine percent fewer evidence tokens.
[7g] A plain dependency walk over the same links ties it. The win is recording the structure.

## s8 — Close

[8a] ProofFlow.
[8b] Full-context accuracy, at vector-search cost.
[8c] Try it live. Every number shown is in the public evidence.
