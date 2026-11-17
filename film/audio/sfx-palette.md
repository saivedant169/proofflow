# SFX palette (ProofFlow)

All files are in `audio/sfx-library/`. The `cc0-*` files are CC0, with credits in `research/prior-sfx-credits.txt`. The three `gen-*` files were synthesized for this film by `tools/sfx-gen.mjs` (pure tones and noise, no samples, no licence needed).

The levels below are starting points relative to the narration (the narration sits at -16 LUFS). Keep effects under the voice.

| Event | First choice | Alternatives | Notes |
|---|---|---|---|
| Thread draws / link forms (soft tick) | `cc0-tick.ogg` (20 ms) | `cc0-kenney-interface-select-001.ogg`, `cc0-fs384187.ogg` | About -26 dB. Vary the level ±2 dB on repeats so they don't sound like a machine gun. |
| Stale pulse travels (subtle rising swish) | `gen-rise-swish.wav` (0.75 s, rises into its end) | `cc0-fs810485.ogg`, or `cc0-riser.ogg` cut short | Line up the end of the swish with the moment the pulse arrives. About -24 dB. |
| Value withheld (muted low thud) | `cc0-fs524817.ogg` (oil-drum soft impact; low-pass it at about 900 Hz) | `cc0-impact.ogg`, `cc0-kenney-interface-drop-002.ogg` | About -22 dB. One thud per figure, or one for both revenue figures together. |
| Refresh re-ink (bright confirmation) | `cc0-kenney-interface-confirmation-001.ogg` | `cc0-kenney-interface-confirmation-002.ogg`, `cc0-kenney-interface-glass-001.ogg` | About -22 dB. Place it on the re-ink frame. |
| Node appears (soft pop) | `cc0-fs-824189-pop-in-sfx.ogg` | `cc0-pop.ogg`, `cc0-kenney-interface-pluck-002.ogg` | About -26 dB. Stagger them when several nodes appear. |
| HydraDB graph traversal (quick run of ticks) | `gen-tick-run.wav` (7 ticks in 0.4 s, rising slightly in pitch) | `cc0-kenney-interface-scroll-001.ogg` | About -26 dB. Start it as the walk begins. |
| Fail-closed (dull bong) | `gen-dull-bong.wav` (damped G3, low-passed) | `cc0-kenney-interface-bong-001.ogg` (brighter, shorter) | About -20 dB. It should say "stop", not sound like an alarm. |
| Close title (gentle chime) | `cc0-fs-571513-soft-notifications-bell-ding-d.ogg` | `cc0-kenney-interface-glass-001.ogg` | About -22 dB. The score ends on a D major chord, so check that the chime sits well over it. |

Sounds I'd avoid here: `cc0-whoosh.ogg`, `cc0-fs-683101-quick-woosh.ogg` and `cc0-fs-702773-swipe-wav.ogg`. They are too "transition-y" for this calm film; use them only for a section change if one is needed.
