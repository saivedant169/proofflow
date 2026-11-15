# ProofFlow walkthrough script

The two-minute film opens with browser CSV preview and report creation, then switches explicitly to a separate guided correction flow. The audited model comparison and separate MCP client integration are labeled saved evidence. Narration uses macOS Samantha; the film is an edited walkthrough.

## 1. Start with your own CSV.

Time: 0.00–9.45 seconds. Visual: `../evidence/ui/csv-preview-desktop.jpg`, then `../evidence/ui/csv-created-desktop.jpg`

Bring your own C S V. Preview your inputs and exchange rates, then create linked revenue reports. This C S V example has two rows.

## 2. Separate guided demo: changed revenue is withheld.

Time: 9.45–22.47 seconds. Visual: `../evidence/ui/source-drawer.jpg`, then `../evidence/ui/workspace-stale-final.jpg`

In the separate guided demo, correct the euro exchange rate. Revenue becomes stale and is withheld. The independent support count stays current, while previous revenue remains clearly historical.

## 3. Native HydraDB queries explain the affected work.

Time: 22.47–29.94 seconds. Visual: `../evidence/ui/evidence-path-final.jpg`

Hydra D B traces the inputs each tool actually consumed, linking this calculation to both reports.

## 4. Four tools refresh both dependent reports.

Time: 29.94–43.48 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`

Four tools refresh the dependent work. Company revenue becomes five thousand seven hundred fifty-five dollars; E U revenue, two thousand two hundred eighty. Independent recomputation matches.

## 5. Saved-report refresh: a separate model experiment.

Time: 43.48–58.90 seconds. Visual: Saved-evidence card.

After a correction, an analyst needs to know which reports can still be used. We tested that on eight retail cases, with forty-eight Fable five point two runs. The model proposes a plan; the same tools handle every refresh.

## 6. Three methods refreshed every recoverable report.

Time: 58.90–70.92 seconds. Visual: Saved-evidence card.

Graph, exact traversal, and full context refreshed all thirty-two recoverable reports. Every method blocked all four unavailable reports. No incorrect report was marked current.

## 7. 60.67% fewer provider input tokens than full context.

Time: 70.92–81.61 seconds. Visual: Saved-evidence card.

Graph used sixty point six seven percent fewer input tokens than full context, excluding the no-op. Graph and exact traversal gave the model identical prompts.

## 8. Limits of this result and the earlier deterministic test.

Time: 81.61–93.02 seconds. Visual: Saved-evidence card.

The model test used one sample per case and method, with adaptive allowances. An earlier deterministic test fell short at a fixed cap and failed its development gate.

## 9. A real client uses ProofFlow through five MCP tools.

Time: 93.02–115.82 seconds. Visual: Saved-evidence card.

An actual Claude client uses five M C P tools to load data, choose plans, inspect and refresh. It reuses prior artifacts on authored two-row input. After a launch-configuration fix, one trajectory passed thirty-two checks, with nine requests and twelve recorded runtime calls. Its first configuration failure is retained.

## 10. ProofFlow — current evidence across agent runs.

Time: 115.82–120.00 seconds. Visual: `../evidence/ui/workspace-refreshed-final.jpg`

ProofFlow: current evidence across agent runs.

## Evidence and production notes

- The first 9.45 seconds show the authored two-row CSV preview and created reports: company $308 and NORTH $108 at supplied EUR/USD 1.20. The following shots explicitly switch to the separate guided $5,565 / $2,090 fixture, where the old revenue is withheld after an exchange-rate correction. [Browser evidence](../evidence/browser_csv_verification.json).
- The saved comparison runs Fable 5.2 at high effort on eight authored cases across six evidence methods (48 actual Claude Code invocations, 96 reported CLI turns). It uses 4,681 eligible UCI Online Retail rows from March 1–4, 2011. The case edits are authored; the video does not show a live model. [Audited results](MODEL_COMPARISON_RESULTS.md).
- The same Hydra-assisted executor runs for every method. Graph, exact traversal and full context each refresh 32/32 affected recoverable reports; BM25 25/32, dense BGE 5/32 and iterative hybrid 28/32. All six methods block all 4 unavailable reports, preserve all 52 unaffected report identities and mark zero incorrect reports current.
- Excluding the no-op, graph accounts for 75,422/191,774 provider input tokens, 39.33% of full context or 60.67% fewer. The accounting includes cache reads and writes. The receipt-only ratio is 35.47% for the same seven cases; that is a different metric. Neither ratio establishes latency or cost savings.
- There is one model sample per case and method. Five methods use each case’s graph closure as the evidence allowance (0–10,853 tokens); full context is uncapped. Graph and exact traversal give the model byte-identical prompts in every case, with the same recovered report count. The model test does not establish an engine advantage or a fixed-cap result.
- The earlier deterministic retail test is separate. It refreshes 8/38 with graph at a fixed 2,048-token cap and fails the development efficiency gate (60.79% against ≤40% of full-context evidence). These observations remain visible and are not pooled with the audited model experiment. [Earlier results](RETAIL_V2_RESULTS.md).
- The MCP segment is one local Fable 5.2/high trajectory on an authored two-row input. Nine requests produce 12 recorded runtime calls and 16 additional CSV arithmetic preflight calculations; 32 recorded checks pass. Its first launch-configuration failure is retained. The external client calls the model; the server does not. [MCP results](MCP_AGENT_RESULTS.md).
- No hosting URL is embedded. The file is exactly 120 seconds, 1920 × 1080 at 30 fps, with burned captions, an embedded text track and an SRT sidecar. Evidence hashes and encoding metadata are recorded under `video/`.
