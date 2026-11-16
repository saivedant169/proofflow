# ProofFlow product site: design plan

Audience: hackathon judges (HydraDB hackathon, Track 2 "agent context layer"). They are technical, time-boxed and skeptical. Primary job of the page: in ten seconds, show that **saved agent reports know when an input changed**; in two minutes, let them watch it happen, check the evidence and reach the live app and repository.

Rule zero: every number on the site comes from `docs/` or `evidence/` in this repository and carries a source link. No invented metrics, no invented customers, no "x faster" claims. Limits are shown as plainly as wins.

## Judge journey and information architecture

The page is itself a lineage chain. Each section is a node on a vertical thread (the "lineage rail") that runs down the left gutter, so the page structure reuses the product's own idea: later sections depend on earlier ones.

| # | Section id | Judge question it answers | Content |
|---|---|---|---|
| 1 | `top` | What is this, in one breath? | Headline, one-sentence promise, a live miniature report wired to its sources. One click corrects the EUR rate; the stale signal travels up the threads, revenue is withheld, then refreshed. Support stays reused. CTAs: open live app, watch walkthrough, repository. |
| 2 | `problem` | Why does it matter? | A saved report keeps serving $5,565 after the rate changed. Three short beats: silent staleness, full recompute wastes context, retrieval misses dependencies. |
| 3 | `how` | How does it work, conceptually? | Four record types in sequence: source version, execution receipt, immutable artifact, report claim. Currentness states: current, stale, unknown (fail closed). |
| 4 | `demo` | Can I see it work? | Full in-browser replay of the guided sample with the real fixture arithmetic: five corrections (FX, order, refund, support, remove a source), the dependency graph, affected list, refresh with executed vs reused count. Clearly labeled as a replay; the live app runs SQLite + HydraDB. |
| 5 | `results` | Is it real and better? | Actual-model study (32/32 at 39.33% input exposure), retail benchmark (38/38, 69.41% fewer evidence tokens), fixed-budget diagnostic, comparators, plus a "what we don't claim" panel (exact-flat ties, development efficiency gate failed, single sample). |
| 5b | `who` | Who wants this, and how do they adopt it? | Teams with recurring agent-produced numbers (finance close, revenue and FX reporting, commerce analytics); today's trade-off (full re-read: accurate, costly; vector search: missed 27 of 32); adoption via the hosted MCP connector or self-hosting with HydraDB OSS; next wedge labelled as roadmap. No customers, prices or adoption numbers. |
| 6 | `architecture` | Is it well built? | System diagram: browser / MCP host → FastAPI → runtime → registered tools (SQLite) + artifact store (hash-verified blobs, SQLite manifest) + HydraDB (lineage, native traversal). Five MCP tools. Runtime API snippet. Fail-closed rules. |
| 7 | `evaluation` | Can I trust the method? | The evaluation pipeline as a real sequence: frozen protocol → held-out runs from a clean committed tree → audit scripts → offline verifier ZIP → CI with real HydraDB and Chromium. Retained failures listed. |
| 8 | `try` | How do I try it now? | Live app, CSV MCP connector, run locally (two commands), evidence ZIP, walkthrough video, repository (judge access). |

Navigation: sticky top bar with wordmark, six anchor links (How it works, Demo, Results, Who it's for, Architecture, Evaluation) with the active section indicated, theme switch, primary button "Open live app". On wide screens the lineage rail also shows progress; each node is a jump link.

## Visual direction: "the thread"

The subject is provenance: numbers that remember where they came from. The one memorable device is **the thread**: thin ultramarine lineage lines that connect every figure to its sources. When a source changes, an orange pulse travels up the threads, affected figures become *withheld* (diagonal hatching over the number, never a silent stale value), and refresh re-inks them in mint. Everything around the thread stays quiet: generous whitespace, left-aligned text, few borders.

### Color tokens

| Token | Light ("vellum") | Dark ("night ledger") | Meaning |
|---|---|---|---|
| `--paper` | `#F2F4F8` cool vellum | `#0A0D24` ink navy | page |
| `--paper-raised` | `#FFFFFF` | `#11153A` | panels |
| `--ink` | `#12163A` indigo ink | `#E9ECFA` | text |
| `--ink-soft` | `#4A5072` | `#A6ADCF` | secondary text |
| `--rule` | `#D4D9E6` | `#262B55` | hairlines |
| `--thread` | `#3346FF` ultramarine | `#8090FF` | lineage, brand, links |
| `--current` | `#0A8F72` (text) / `#14B892` (fill) | `#34E3B6` | current, refreshed |
| `--stale` | `#B8410C` (text) / `#FF6B1F` (fill) | `#FF8F52` | stale, change signal |
| `--unknown` | `#6B7090` | `#8A90B4` | blocked, unknown |

State colors are information only: never decorative. Every state also has a text label and a pattern (hatching for withheld, dashed for blocked) so color is never the only cue.

### Type

- **Anybody** (variable, width 50–150, weight 100–900): display and all figures. Headlines set wide (wdth 125–140) and heavy; data labels set condensed. The width axis is an active device: a figure narrows when withheld and returns to full width when refreshed.
- **Instrument Sans** (variable): body and UI, 18px/1.6 body, measure ≤ 68ch.
- **JetBrains Mono**: only for real identifiers (artifact IDs, hashes, commands, code).
- Scale (Bringhurst): 13, 15, 18, 21, 24, 30, 36, 48, 64, 84, 112.
- Sentence case everywhere. No all-caps eyebrows, no single highlighted word in headlines, no arrows appended to button text, no middle-dot meta strings.

### Layout

```
┌ nav ──────────────────────────────────────────────────────────┐
│ ProofFlow   How it works  Demo  Results  Architecture  Eval  ◐ [Open live app] │
├─┬──────────────────────────────────────────────────────────────┤
│●│ Reports that notice      ┌ live miniature ──────────────┐    │
│ │ when their inputs        │ Company revenue   $5,565 ─┐  │    │
│ │ change.                  │ EU revenue        $2,090 ─┼──┼─ threads → EUR 1.10
│ │ one-sentence promise     │ EU support tickets     2 ─┘  │    │
│ │ [Open live app] [Watch]  │ [Correct EUR 1.10 → 1.20]    │    │
│●│                          └──────────────────────────────┘    │
│ │ problem: narrow text column + one wide figure               │
│●│ demo: full-bleed workbench (graph left, report right)       │
└─┴──────────────────────────────────────────────────────────────┘
```

Left-aligned 12-column grid, max width 1240px, 24px gutters (16px on phones). Sections alternate a narrow text column with one wide figure; no grids of identical cards. Radius encodes hierarchy: 999px chips, 14px panels, 6px figure frames, 0 on the rail.

### Motion

- One orchestrated load moment: the hero threads draw from sources up to the figures (≈1.2s).
- All other motion answers an action: correction pulse, withholding, refresh re-ink, diagram node focus, theme crossfade.
- Section content does not fade-and-slide on scroll. Diagrams may animate once when they first enter the viewport, only if they explain flow.
- `prefers-reduced-motion`: no travelling pulses; state changes switch instantly with the same labels.

## Quality floor

Responsive from 360px; visible focus rings (2px `--thread` outline, offset 3px); WCAG AA contrast in both themes; keyboard-operable demo; all colors from tokens; theme choice (system / light / dark) persisted in localStorage with try/catch; static build with no backend dependency; external links open the real hosted app, evidence and repository.
