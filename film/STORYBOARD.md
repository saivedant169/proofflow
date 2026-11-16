# ProofFlow film: storyboard

Durations come from the measured narration (timing.json). Every beat below is keyed to a line or word of `research/script.md` through `FILM.at` / `FILM.line`; "→" means "on that word". Numbers on screen must match the repository (sources in script.md). Keep on-screen text sparse; the voice explains.

---
## Frame s1 — Monday (hook) · `compositions/s1-monday.html` · status: outline
Rules: kinetic-type headline + single focal figure; one thread motif introduced.
- Open on the ground. Top-left, Anybody `.t-head`: **Monday.** stretches in (wdth 60→125) → "Monday".
- Right of centre: one report card (`.panel`, ~720×380): label "Company weekly report", small tag "Saved by your agent" (`.tag-current` styling is fine), figure **$5,565** counts from $0 → "five thousand" … lands as "dollars" ends.
- A single thin thread hangs from the figure down off-frame (the lineage we cannot see yet) — drawn on softly under 1b.
- 1c → "Tuesday": "Monday." is replaced by **Tuesday.** (old word narrows to wdth 50 and fades, new stretches in). A source chip enters bottom-right: `EUR→USD 1.10`; → "corrects": 1.10 is struck and **1.20** appears in `--stale`, chip border turns orange.
- 1d → "doesn't change": the figure stays exactly $5,565 (a tiny steady "Saved" tag remains) while the thread from it ends in a visible GAP above the chip — no link. → "wrong": the gap end blinks orange once (a single opacity hit, not a loop). Hold.
- End frame (match → s2): the card at its final position.

## Frame s2 — The problem · `compositions/s2-problem.html` · status: outline
Rules: pull-back reveal into a network; split comparison.
- First frame = s1's card. Camera pulls back (world scale 1 → ~0.42, card stays sharp because it is re-laid at smaller size — build the world at final size and start it scaled up ≤1.15 is NOT allowed for text; instead animate card width/height/position or crossfade to a small node). The card becomes one node among ~11 report and result nodes; beneath them a row of inputs (Orders, Refunds, EUR→USD, Tickets, a tool version). Hairline threads (`--hairline`) connect them; → "depends on inputs underneath": threads light bottom-up in `--thread`.
- 2b → "which numbers": the EUR→USD input turns orange. Headline top-left `.t-head-s`: **Which numbers are now wrong?** Nodes go dashed `--unknown` (uncertain), not "?" dots.
- 2c → "Re-reading everything": left half. Every node's text streams as lines into a "context" container that fills and overflows its top edge; label `Everything, every time` (muted). Small factual caption allowed: "Full context: 128,729 evidence tokens (retail benchmark)".
- 2d → "Searching": right half. A search field types `exchange rate`; a scan line passes over the network; only the 2 nodes whose text mentions the rate highlight; the company report (which depends on it silently) is NOT highlighted → "never mention it": it gets an orange outline with the label **Missed**.
- End: both halves hold side by side.

## Frame s3 — The idea · `compositions/s3-idea.html` · status: outline
Rules: wordmark reveal + receipt unfold. Music opens here (mark `name`).
- → "ProofFlow" (mark `name`): the wordmark **ProofFlow** (`.t-hero`) builds from a single thread that draws across the frame and resolves into the letters (letters stretch in wdth 50→132 in a quick stagger). The P's bowl is a thread loop in `--thread`; a small `--current` dot sits after it (as on the site's favicon).
- 3b → "Every number": wordmark slides up and shrinks to top-left (`.t-head-s` size, re-laid, not scaled up). The **$5,565** figure returns centre-left; → "receipts": a receipt panel unfolds beneath/right of it (`.panel`, tall, ticket-like with a perforated top edge drawn as dashes): lines appear one by one → "inputs": `orders · v1`, `refunds · v1`, `EUR→USD 1.10 · v1` (use plain words, e.g. "Orders, version 1"); → "calculation": `convert_to_usd`, `company_total` (`.t-mono`). Threads tie the figure to each receipt line.
- 3c → "hold back": tag **Withheld** (stale tag) appears left; → "redo": tag **Refresh** (current) right. Hold.

## Frame s4 — How it works · `compositions/s4-how.html` · status: outline
Rules: a chain diagram that builds node by node, then propagation and refresh. This is the beginner's core explanation; give it room and clarity.
Layout (world, left→right, vertically centred): `Exchange rate` source node (version chip "v1 · 1.10") → `Conversion` receipt node (pill; label "Execution receipt") → `Regional USD` artifact node ("Immutable result") → two report cards: **Company report** ($5,565) and **EU brief** ($2,090). Below: a `Support tickets` artifact node with threads to both reports (support count **2** shown in each).
- 4a → "exchange rate": source node draws in; caption under it "saved as a version".
- 4b → "tool": receipt pill appears, thread from source labelled `CONSUMED` (small mono label on the thread); → "receipt": a little receipt icon/slip pops from the pill.
- 4c → "result": artifact node, thread `PRODUCED`; → "each number": the two report cards with figures, threads from the artifact into each figure; support node + threads.
- 4d → "correct the rate" (mark `correction`): the source node gets a second version card sliding in front: "v2 · 1.20" in orange; v1 dims behind it.
- 4e → "travels": orange pulse(s) travel source → receipt → artifact → both reports (hop by hop); each node turns stale (hatched) as the pulse arrives; → "withheld": both revenue figures `FILM.withhold` + **Withheld** tags.
- 4f → "Support": the support node and its threads stay `--thread`/current; tag **Current** on support; its two "2" figures stay bright.
- 4g → "Refresh": mint pulses re-run the stale steps in order (receipt pill shows "re-ran"), figures restore and count: $5,565 → **$5,755**, $2,090 → **$2,280**; support shows **Reused**. A small line bottom-left: "4 tools ran. Support reused." Hold the completed, all-current diagram.

## Frame s5 — Working today · `compositions/s5-product.html` · status: outline
Rules: real product stills in a browser frame; one outline highlight per beat; camera glides between crops. Stills from `stills/stills.json` (see `node tools/sync.mjs --list`). Use the actual figures visible in the stills.
- 5a → "running today": a large `.window` with a slim bar showing `proofflow.arnavbule.in` slides in from the right; still `p01-workspace` (or the closest full frame). Headline top-left small: **Running today.**
- 5b → "CSV": cut inside the window to `p06-csv-preview` (outline the preview table); → "create": `p07-csv-created` (outline the report figures).
- 5c → "corrected rate": `p08-csv-stale` (or `p03-stale`): outline the stale banner in `--stale`, then the withheld figures; → "evidence path": crop of the evidence/graph (`p04-evidence` crop) with outline on the path.
- 5d → "Refresh": `p09-csv-refreshed` (or `p05-refreshed`): outline new values `fresh`; → "copied": outline the "Copy checked report" control; a small tag "Only while every figure is current".
- 5e → "Agents": the window slides left and shrinks (re-laid, not scaled up); on the right five mono chips appear in a column, each tied by a thread to a small "Agent" node: `load_csv`, `prepare`, `execute_plan`, `inspect`, `refresh`; caption "over MCP". Hold.

## Frame s6 — Under the hood · `compositions/s6-architecture.html` · status: outline
Rules: the architecture builds from nothing, one component per line, in a fixed final layout that is readable when paused; then runs once with no voice; then holds. The most technical frame — slow, layered, precise.
Final layout (1920×1080, safe area respected):
- Left column ("doors"): **Browser app** (React), **Python API** (`ProofFlowRuntime`), **MCP server** (5 typed tools). Browser connects through **FastAPI** (`api.py`) to the runtime.
- Centre: **Runtime** (`runtime.py`): receipts, currentness, refresh. Inside/next to it: **Registered tools** (`analytics.py`: 7 tools, SQLite + Decimal).
- Right top: **HydraDB** (`graph.py`) containing a small live lineage graph (6–8 nodes, edges `CONSUMED` / `USED_TOOL` / `PRODUCED`).
- Right bottom: **Artifact store** (`artifacts.py`): hash-verified blobs + SQLite manifest; shows a short hash like `sha256 9f3c…` with a check.
Beats:
- 6a → "Under the hood": title top-left `.t-head-s`; everything else empty.
- 6b → "runtime": Runtime box draws (border draws on, then label). → "tool run": a tool chip enters the runtime, produces two objects: an **immutable result** (a small solid node with a lock-like corner notch) and a **receipt** slip.
- 6c → "store": the result travels by thread into the Artifact store; → "hash": hash text types out and a mint check appears.
- 6d → "HydraDB": the receipt's relationships travel into HydraDB; the lineage graph assembles edge by edge with tiny mono edge labels.
- 6e → "correction": an orange pulse enters runtime; → "walks": inside HydraDB the traversal lights descendants hop by hop (orange); → "downstream": the found set outlines.
- 6f → "re-runs": numbered 1–4 mint steps tick in the runtime in order; → "reuses": the support node gets a **Reused** tag; → "receipts": new receipt slips stack.
- 6g → "missing": one node in HydraDB turns dashed `--unknown`; the runtime emits a blocked marker; mono text `409 evidence_unavailable` / `503 backend_unavailable`; → "No fallback": label **No fallback. No guess.**
- 6h → "browser app": the three doors draw in on the left with threads to FastAPI/runtime, one per spoken name.
- 6i → "typed tools": five tool names list on the MCP door; → "arbitrary code": a chip `arbitrary code` approaches the MCP door and is refused (struck through, falls away, `--unknown`).
- Run (mark `run`, no voice ≈ 6 s): one correction flows end to end: Browser → FastAPI → Runtime → HydraDB (descendants light) → Tools re-run → Store commit (hash check) → back to the Browser where a figure re-inks $5,755. Tiny hop labels. Then the final frame holds perfectly still (≥ 2 s) — a judge-readable pause frame.

## Frame s7 — Results · `compositions/s7-results.html` · status: outline
Rules: stat hits + honest comparison bars. Exact figures, sources in a small caption.
- 7a → "Does it work?": `.t-head` top-left.
- 7b → "thirty-two": giant **32/32** (`.t-hero` figure, counts up 0→32) with label "affected reports refreshed — frozen study, real model, 48 invocations". → "under forty percent": a proportional bar pair: Full context 100 % vs ProofFlow **39.33 %** of provider input exposure (label exactly "39.33% of full context's input").
- 7c → "Keyword search": horizontal bars out of 32: ProofFlow 32 (thread colour), BM25 **25**, Vector (BGE) **5** (muted). Exact-flat and iterative hybrid may be shown faint (32, 28).
- 7d → "retail benchmark": second stat **38/38** + "69.41% fewer evidence tokens" (39,375 vs 128,729).
- 7e → "plain dependency walk": a bar "Exact dependency walk 32/32 · 38/38" slides in level with ProofFlow's — tie made visible; → "recording dependencies": the two tied bars share one bracket labelled "Explicit dependencies". Caption bottom: `docs/MODEL_COMPARISON_RESULTS.md · docs/RETAIL_V2_RESULTS.md` (mono, small).

## Frame s8 — Close · `compositions/s8-close.html` · status: outline
Rules: converge and resolve; the one disclosure, once.
- Threads from all four edges converge to centre and resolve into the wordmark **ProofFlow** → "ProofFlow" (mark `finalName`) — designed differently from s3 (here: threads become the letters' baselines, then the wordmark settles; one mint dot lands).
- → "Saved reports": tagline beneath (`.t-sub`): **Saved reports that know when they're out of date.**
- `proofflow.arnavbule.in` in `.t-mono` below.
- → "authored": the disclosure in `.t-small` at the bottom: "Sample data is authored. Every result shown is in the public evidence." Hold to the end on the final chord; nothing moves for the last ~1.5 s.
