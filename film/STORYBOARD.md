# ProofFlow film: storyboard (v2: framed against today's baselines)

Durations come from the measured narration (timing.json). Every beat below is keyed to a line or word of `research/script.md` through `FILM.at` / `FILM.line`; "→" means "on that word". Numbers on screen must match the repository (sources in script.md). Keep on-screen text sparse; the voice explains.

---
## Frame s1 — Two bad options (hook) · `compositions/s1-monday.html` · status: built (v2)
Rules: kinetic type, one input, a fork into two lanes ("Today's fixes are heavy or blind", as on the product page). No exact numbers yet; they are saved for s7.
- 1a: chip **EUR→USD 1.10** stretches in at centre; → "changes": flips to **1.20** in `--stale`. → "Now": it glides into the input row of an unlabelled network; **AI agent** arrives right; dashed sight lines on "work out"; → "what that broke": one orange hop, every node goes dashed `--unknown`.
- 1b: the agent glides to top centre; → "two": fork threads, two lane rules and a divider draw.
- 1c (left lane, **Re-read everything**): document lines stream from a stack into an **Agent context** window and overflow it; **Accurate** tag; token meter fills on "pay for every token"; cost ticks one $ per beat; → "every time": the window empties and floods again.
- 1d (right lane, **Search what looks related**): `exchange rate` types into a search pill; a beam lights only the decoys that share the word ("Response rate", "Rate review"); meters show a sliver; → "blind": Company total ($5,565) outlined orange; → "matters": **Missed**.
- End frame = s2's first frame.

## Frame s2 — Why search goes blind · `compositions/s2-problem.html` · status: built (v2)
- First frame = s1's last (shared drawing code between `/*@@SHARED…@@*/` markers; regenerate s2's copy if s1's drawing changes).
- 2a: lanes fade; the right lane's nodes glide into a 14-node network built bottom-up; threads light from inputs up on "depends on inputs underneath".
- 2b: → "exchange rate": 1.10 → 1.20, orange outline; → "some … numbers": Regional USD, Company, EU brief, Board deck, Weekly recap go dashed `--unknown`.
- 2c: all dims except rate → Regional → Company; a callout shows the report's own text ("Revenue this week: $5,565, net of refunds.") while the hidden thread draws orange; → "mentioning": "~~rate~~ never mentioned".
- 2d: headline **Similar words ≠ real dependencies**; word-match marker on the decoys while the real dependency threads complete.

## Frame s3 — The idea · `compositions/s3-idea.html` · status: built (v2)
- 3a (mark `name`): thread-to-wordmark build of **ProofFlow**; a **context layer** pill reveals word by word.
- 3b: mark to top-left; **Company total $5,565** returns; → "receipts": a receipt unfolds (Orders v1, Refunds v1, EUR→USD 1.10 v1; tool `convert_to_usd`, `company_total`) tied by threads.
- 3c: → "changes": 1.10 struck, 1.20, pulse; → "the agent": s2's network returns dimmed with the affected slice outlined; → "exactly what broke": the slice lifts into an **Agent context** window; → "Nothing more": the rest darkens, the window closes. Hard cut to s4's empty ground.

## Frame s4 — How it works · `compositions/s4-how.html` · status: built (v2: 4f lands **Current** on "current" and **Reused** on "reused")
Rules: a chain diagram that builds node by node, then propagation and refresh. This is the beginner's core explanation; give it room and clarity.
Layout (world, left→right, vertically centred): `Exchange rate` source node (version chip "v1 · 1.10") → `Conversion` receipt node (pill; label "Execution receipt") → `Regional USD` artifact node ("Immutable result") → two report cards: **Company report** ($5,565) and **EU brief** ($2,090). Below: a `Support tickets` artifact node with threads to both reports (support count **2** shown in each).
- 4a → "exchange rate": source node draws in; caption under it "saved as a version".
- 4b → "tool": receipt pill appears, thread from source labelled `CONSUMED` (small mono label on the thread); → "receipt": a little receipt icon/slip pops from the pill.
- 4c → "result": artifact node, thread `PRODUCED`; → "each number": the two report cards with figures, threads from the artifact into each figure; support node + threads.
- 4d → "correct the rate" (mark `correction`): the source node gets a second version card sliding in front: "v2 · 1.20" in orange; v1 dims behind it.
- 4e → "travels": orange pulse(s) travel source → receipt → artifact → both reports (hop by hop); each node turns stale (hatched) as the pulse arrives; → "withheld": both revenue figures `FILM.withhold` + **Withheld** tags.
- 4f → "Support": the support node and its threads stay `--thread`/current; tag **Current** on support; its two "2" figures stay bright.
- 4g → "Refresh": mint pulses re-run the stale steps in order (receipt pill shows "re-ran"), figures restore and count: $5,565 → **$5,755**, $2,090 → **$2,280**; support shows **Reused**. A small line bottom-left: "4 tools ran. Support reused." Hold the completed, all-current diagram.

## Frame s5 — Live today · `compositions/s5-product.html` · status: built (v2)
Real stills from the restyled app (dark theme) against the hosted backend; see `stills/README.md` and `tools/capture-stills.mjs`. One outline per beat inside a `.window` with the `proofflow.arnavbule.in` bar.
- 5a: window slides in on `p01-workspace`; title **ProofFlow, live today.** word by word.
- 5b: "upload" CSV form; "preview" preview card (green); "create" saved reports $308 / NORTH $108 (outline on "two").
- 5c: "publish" update drawer → 1.30 field outlined orange on "rate"; "affected" withheld figures; "graph" the affected path with the corrected rate source outlined on "shows".
- 5d: "refresh" $317 / $117 outlined green on "current"; "checked" the verified line, then **Copy checked report** outlined on "copied".
- 5e: window shrinks left; an **Agent** node threads to six chips: `create_csv_reports`, `inspect_reports`, `inspect_evidence`, `update_csv`, `refresh_reports`, `export_current_reports`; "over MCP · one download".

## Frame s6 — Under the hood · `compositions/s6-architecture.html` · status: built (v2)
v2 changes: new 6f — on "walk" a ghosted **Full re-read** block appears; the found descendants lift out of HydraDB into a compact **Agent context** panel (about a third of its area); "Skip the re-read" strikes and collapses the ghost. Old 6f/6g are now 6g/6h; old 6h+6i merged into 6i (doors draw on "browser", "Python", "MCP"; typed tools; "arbitrary code" refused).
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

## Frame s7 — Against today's approaches · `compositions/s7-results.html` · status: built (v2)
One chart that builds method by method: reports right (of 32) vs input tokens for the whole study, plus a list-price ledger. Sources: docs/MODEL_COMPARISON_RESULTS.md · docs/RETAIL_V2_RESULTS.md. No speed claim; costs labelled "List price, whole study".
- 7a title **How does it compare?**; 7b caption "Frozen study · 48 real model calls · same task for every method", axes draw on "Forty-eight".
- 7c Full context: 219,145 tokens, 32/32, ledger $3.74.
- 7d ProofFlow: 77,071 tokens, 32/32; the rest of full context's band hollows out as **142,074 fewer input tokens**; ledger $1.38, **−63%**.
- 7e Vector 5/32 at the same price, bracket **6.4× more right than vector search, at the same list price**; Keyword 25/32 ($1.43), Hybrid 28/32 ($1.45).
- 7f Separate retail benchmark **38/38 · −69% evidence tokens**.
- 7g "Exact dependency walk · ties · 32/32 · 38/38" ringed on ProofFlow's mark; bracket **The structure is the win.**

## Frame s8 — Close · `compositions/s8-close.html` · status: built (v2)
- 8a (mark `finalName`): threads converge into the **ProofFlow** wordmark.
- 8b: **Full‑context accuracy at vector‑search cost.** word by word.
- 8c (go-to-market): chips on their words: Finance close · Revenue & FX reporting · Commerce analytics; → "MCP": "Any agent → MCP connector (one download)".
- 8d: `proofflow.arnavbule.in` writes on at "Try"; "Every number shown is in the public evidence."; hold still ≥ 1.5 s.
