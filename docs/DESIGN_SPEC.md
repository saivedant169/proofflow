# ProofFlow interface design

The complete primary screen concept is `frontend/design/workspace-concept.png` (1536×1024), generated with the built-in image-generation tool. `frontend/design/change-source-concept.png` supplies the source drawer and stale-claim state. These are design references, never rendered as the application.

## Visual system

The primary reference controls the shell: pure white background and report surface, near-black ink, cobalt primary actions, a very pale cool-gray evidence canvas, hairline cool-gray borders, and quiet green current markers. Amber denotes revalidation. No gradients, decorative illustrations, or raster logo. Text wordmark and functional outline icons are code-native.

Desktop uses a 64px header, a generous headline/action band, a 38/62 report-and-graph split, then an open execution list. Mobile stacks the report and graph, preserves a readable horizontally scrollable diagram, and uses a full-width source drawer. Typography is an Inter/system sans stack: 48px desktop headline, 28px report title, 46px primary amount, 18px section headers, 14px controls and 13px secondary labels. Borders have a 10px radius; primary controls use 7px. Spacing is based on 4/8/12/16/24/32px. Focus rings use cobalt. Motion is limited to drawer appearance and state change and respects reduced motion.

## Allowed primary copy

ProofFlow; Workspace; Benchmark; GitHub; New workspace; A change should travel.; Trace a correction through the work that depends on it.; Refresh what changed. Keep what did not.; Change a source; Refresh affected; The week, with its working attached.; Company revenue · USD; EU revenue; EU support tickets; Composed from two runs; Evidence, connected; Inputs actually consumed by your tools; Recent activity; Authored demo data. Real calculations and HydraDB lineage.; Inspect the benchmark.

Actual report titles, tool names, timestamps, graph labels, values, states, source summaries, errors, and execution counts always come from the API and are permitted dynamic content. New workspace resets the same isolated browser workspace; it does not create another person's workspace.

## Components and interactions

`App` owns server state, pending actions and the active view. Separate report, native-evidence graph, activity, source drawer, evidence inspector and benchmark components own rendering. API transport and data types are independent modules. Mutations await actual backend state and never manufacture optimistic numeric values. Unknown/stale claims show no current value; historical values are explicitly labeled. Source correction precedes refresh, and refresh exposes actual execution/reuse counts and independent value checking.

The benchmark view is a table in the same typography and container system, showing the frozen published results and all stated controls. It is not a new design direction. Evidence inspection uses the same drawer family with immutable receipts and native paths, because a readable inspection surface is necessary for the requested workflow.

## Intentional fidelity corrections

- The generated concept invented a support count of 12 and 2025 timestamps. The actual API values and timestamps replace these; the fixture starts with two EU tickets.
- The generated graph omitted intermediate calculations and invented shortcut edges. The implementation uses only actual receipt-derived dependencies, includes all supported calculation nodes and labels the diagram accordingly.
- The primary concept's underline navigation is authoritative; the second concept's selected pill is not adopted.
- Source-drawer controls use the primary screen's typography scale, which is smaller than the companion generated image. This intentional choice keeps one consistent readable application system rather than switching type scales inside the drawer.
- Main report copy is editorial, while actual report titles remain backend-derived. Currentness states may change the amount layout to prevent stale values appearing current.
- GitHub navigates to the user's private repository; the interface makes no promise of public source access.

Concept prompt: complete white/cobalt editorial analytics workspace, report at left, execution evidence at right, source correction and explicit stale-claim withholding, real activity below; exact primary copy as listed above, no invented product claims, no decorative art. The companion prompt requested the matching source drawer, five bounded correction choices, and current-versus-historical claim states.

## Functional refinements verified in browser

- Initial refresh is disabled until a report needs revalidation; the concept's always-enabled button is not copied into a false action state.
- Loading says “Opening your workspace…” and “Checking your reports and their execution evidence in HydraDB.” This is accurate for first use and resume after restart.
- Mobile graph includes “Scroll to explore”; the complete graph fits desktop without clipping report nodes, while narrow screens retain readable nodes inside a horizontal scroller.
- Long edges are routed around intervening nodes, preventing a visually implied relationship that was never recorded. Both report nodes share the final visual column; their dependency pairs remain unchanged.
- Activity displays human-readable run names and exact raw IDs in tooltips/inspection. Sub-tenth-millisecond executions display “<0.1 ms”, not a misleading zero.
- A recorded-agent disclosure after benchmark methodology shows two real local model plans, actual execution counts and results from `evidence/agent_composition.json`. It explicitly identifies recorded local execution rather than a hosted model endpoint. This is a required evidence surface in the same table/list/drawer design family.
