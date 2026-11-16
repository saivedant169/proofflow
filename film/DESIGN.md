# ProofFlow film: design

**Concept angle.** Every figure on screen is tied by a visible thread to what made it. The film follows those threads: from one saved number, down into its receipts, out to the system that keeps them, so the story is one dependency graph that keeps growing until it is the architecture.

Audience: complete beginners first (a judge who has never heard of lineage), engineers second. Spoken narration carries the explanation; the screen carries few, big words and clear diagrams. The user's standing preferences: fresh, elegant, modern, vibrant but professional; very easy to visualize; little on-screen text; razor sharp; architecture explained from the beginning, slowly, until fully built, then shown running.

## Palette (film.css tokens; the website's dark "night ledger" theme)

| Token | Hex | Use |
|---|---|---|
| `--ground` | #0A0D24 | the one flat ground for the whole film |
| `--panel` / `--panel-2` | #11153A / #171C4A | cards, nodes, panels |
| `--hairline` / `--rule` | #262B55 / #3A4078 | structure lines, frames |
| `--ink` / `--muted` / `--faint` | #E9ECFA / #A6ADCF / #767DA6 | text |
| `--thread` / `--thread-strong` | #8090FF / #A5B0FF | lineage threads, brand, highlights |
| `--current` | #34E3B6 | current, refreshed (state only) |
| `--stale` | #FF8F52 | stale, the change signal, withheld (state only) |
| `--unknown` | #A0A6C8 | blocked, fail closed (dashed) |

State colours mean state only; never decorate with them. Withheld always = orange hatch + narrowed figure, never a silently stale value.

## Type

- **Anybody** (variable width 50–150) for headlines and every figure. Headlines heavy and wide (`.t-hero` 168, `.t-head` 112, `.t-head-s` 80). The width axis is the signature type move: words and figures *stretch in* (wdth 60 → final) and a withheld figure narrows (125 → 82).
- **Instrument Sans** for subtitles, labels and small text (`.t-body` 40, `.t-label` 30, `.t-small` 26).
- **JetBrains Mono** only for real technical names: file names, tool names, HTTP codes (`.t-mono`).
- Sentence case. Top-left anchored headlines. Never more than ~8 words of on-screen text at once outside diagrams.

## Motion vocabulary

- Threads draw on (`FILM.drawThread`), 0.6–1.0 s, `power2.inOut`.
- A change is an orange pulse travelling the threads (`FILM.pulseAlong`), hop by hop in dependency order (~0.35–0.45 s per hop).
- Refresh is a mint pulse going back up, then figures re-ink (`FILM.restore`) and count (`FILM.countTo`).
- Entrances: 0.5–0.9 s ease-out then **hold still**. Vary direction and ease (power3.out, expo.out, back.out(1.4) for small nodes only). No generic fade-up on everything.
- Camera: within a section, a "world" wrapper (`#sN-world`) may pan/zoom slowly (x/y/scale ≤ 1.15, only on vector content — never zoom text or stills past their size). Moves follow the action, not decoration.
- Hard cuts between sections on the same ground; match frames where STORYBOARD says so.
- Allowed ambient: one very slow drift of the world layer or structure rules per scene. Not allowed: glow, blur, grain, vignette, scrims, darkening overlays, gradients across the ground, bouncing loops, watermarks.

## Frame craft

- Safe area: 120 px left/right, 96 px top/bottom.
- Two focal points per frame; anchor content to edges; diagrams fill 60–85 % of width.
- Borders on video are 3 px (nodes), panels 2 px. Corner radius: nodes 14, panels 18, chips 999.
- Product stills sit in `.window` frames, shown at or below native pixels, highlighted with `FILM.outline`.
- Diagram text is ≥ 24 px; a paused frame of the architecture must be readable at 1080p.

## Do not repeat from the user's previous film

Pale ground with indigo dashed underline wordmark; headline-plus-one-card frames over and over; a numbered step strip with progress dots; a four-column architecture board with a ledger strip; slips snapping into an underline; a 64-dot grid; "Every X, traced." taglines; "?" dot clusters; a dark-to-bright turn.
