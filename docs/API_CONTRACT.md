# ProofFlow browser API contract

Same-origin JSON API. Browser session is an opaque HTTP-only cookie `proofflow_session`; fetch with normal same-origin credentials. No API/model/Hydra keys go to the browser. Tools execute on the server: the demo uses an authored dataset, while the separate import workflow uses supplied CSV rows. Both are guided workflows without a browser model call.

## Routes

- `POST /api/session` — create and execute the two initial report runs, or resume the browser's existing session. Empty body. Returns the full **State** object below and sets the cookie.
- `GET /api/state` — current State; `401` if no session. Reopening the server loads persisted session data and queries Hydra again.
- `POST /api/change` — apply one bounded staged source correction and return State.
- `POST /api/refresh` — body `{}` refreshes both report heads; optional `{"report_ids":["immutable report ID"]}` refreshes selected report(s) within this session. Returns State with `last_refresh`.
- `POST /api/verify` — body `{}`; compare both saved report values with fresh recipe evaluation. Returns `{passed, reports:[{id,title,state,numeric_match,error}], scope}`. A stale report can have numerically equal values; state and equality are separate fields.
- `POST /api/reset` — body `{}`; starts a new isolated generation of the same browser session and returns State.
- `GET /api/evidence/{artifact_id}` — URL-encode the immutable artifact ID. Returns `{artifact,receipt,paths}`; native Hydra paths are returned for current source-change roots to this artifact. `paths` entries have `{source_id,target_id,nodes:[{id,label,kind}],edges:[{source,target,kind}]}`. Empty paths are valid for unaffected artifacts.
- `GET /health` — real Hydra read; `{status:"ok",backend:"HydraDB OSS"}` or 503. No silent memory fallback.
- `GET /api/benchmark` — published immutable `evidence/benchmark_summary.json`, no browser session required. Server-only `PROOFFLOW_EVIDENCE_DIR` overrides the directory; callers cannot choose a file path. Returns 404 until evidence exists.

Supported `POST /api/change` bodies (no arbitrary source JSON accepted):

```json
{"kind":"fx","value":"1.20"}
{"kind":"order","delta_cents":10000}
{"kind":"refund","delta_cents":10000}
{"kind":"support","count":1}
{"kind":"remove","source":"fx"}
```

FX changes EUR→USD only. Order change adjusts the first EU order. Refund change adjusts that order's refund. Support adds 1–5 EU tickets. Remove accepts only `orders`, `refunds`, `fx`, or `tickets`. Reset restores the authored fixture. Values are bounded and validated server-side.

## State

```json
{
  "session_id":"opaque UUID",
  "generation":"opaque UUID",
  "created_at":"ISO timestamp",
  "mode":"guided_real_execution",
  "backend":{"engine":"HydraDB OSS","native_queries":123,"fallback":false},
  "dataset":{"label":"Fictional commerce dataset","sources":[
    {"name":"fx","id":"immutable ID","content_hash":"sha256","removed":false,"summary":{"EUR":"1.10","USD":"1.00","GBP":"1.25"}}
  ]},
  "reports":[
    {"key":"company","id":"immutable ID","title":"Company weekly report","run_id":"run-A","state":"current","claims":[
      {"key":"company_revenue","label":"Company revenue","unit":"USD cents","value":556500,"saved_value":556500,"state":"current","artifact_id":"metric ID","path":["usd_cents"],"reasons":[]},
      {"key":"eu_support","label":"EU support tickets","unit":"tickets","value":2,"saved_value":2,"state":"current","artifact_id":"metric ID","path":["regions","EU","tickets"],"reasons":[]}
    ]},
    {"key":"eu","id":"immutable ID","title":"EU operations brief","run_id":"run-B","state":"current","claims":[
      {"key":"eu_revenue","label":"EU revenue","unit":"USD cents","value":209000,"saved_value":209000,"state":"current","artifact_id":"metric ID","path":["regions","EU","usd_cents"],"reasons":[]}
    ]}
  ],
  "impact":{"change":null,"affected_artifacts":[],"changed_source_ids":[]},
  "graph":{"nodes":[{"id":"immutable ID","label":"Regional USD revenue","kind":"artifact","logical_id":"metric:regional","state":"current","current_head":true}],"edges":[{"source":"ID","target":"ID","kind":"CONSUMED"}]},
  "executions":[{"id":"receipt ID","tool":"convert_to_usd","run_id":"run-A","status":"success","elapsed_ms":1.2,"inputs":{"net":"ID","fx":"ID"},"output_id":"ID"}],
  "last_refresh":null,
  "notices":["Authored demo data; actual SQLite calculations and HydraDB traversal."]
}
```

The example is illustrative; actual counters, IDs, state and values always come from execution. The EU report also includes the same independent support claim.

After a change, `impact.change` is `{kind,label,previous_source_id,current_source_id,timestamp}` and `affected_artifacts` contains `{id,logical_id,title,kind}`. Graph IDs and receipt relationships come from persisted records and are verified against native Hydra; no synthetic diagram edges.

After refresh, `last_refresh` is `{executed_count,reused_count,executed_artifact_ids,reused_artifact_ids,elapsed_ms,tool_calls:[{tool,status,elapsed_ms,output_id}],numeric_parity,unchanged_support,graph_queries}`. Counts use **actual tool calls**, including when an old handle resolves to an already-refreshed head. `numeric_parity` is `null` if verification cannot complete; never render it as success then.

`state` is `current`, `stale`, or `unknown`. A stale/unknown claim's `value` is **null**; `saved_value` is historical display only and must be clearly labeled. Monetary values use integer cents; format their integer quotient and remainder without floating-point division. Imported large amounts use the decimal-string representation described below. Source-change effects are conservative source-level revalidation, not a claim that every dependent number changed.

## Errors and limits

Error responses are `{error:{code,message}}`; validation errors use the same envelope. 400 invalid input; 401 missing session; 404 unknown evidence; 409 incomplete/missing evidence; 429 session action limit; 503 Hydra unavailable or session capacity. Never replace a failed state request with optimistic mock data.

Default persistent session limit is 16, configurable through `PROOFFLOW_MAX_SESSIONS`. The application runs as one worker; each session mutation is locked. Static files are served from `PROOFFLOW_STATIC_DIR` (default `frontend/dist`) only after frontend exists. Unknown `/api/*` paths remain API errors rather than SPA routes.

The limit bounds live sessions, not lifetime visitors. Idle sessions expire after `PROOFFLOW_SESSION_TTL_SECONDS` (default 3600); expired owned session directories are reclaimed when capacity is checked. In-flight requests and requests waiting for the same session are protected from reclamation. Persisted last-seen timestamps preserve this behavior across application restarts. Failed initializations release their reserved capacity. Expired browsers receive 401 on state and can start a new demo with `POST /api/session`.

## Browser CSV workspace

The separate `/api/import/*` workflow uses the same opaque session cookie and session lock. It leaves guided-demo routes unchanged. The server generates the import workspace identity; requests never supply filesystem paths or workspace IDs. Missing active import returns 404, missing cookie returns 401. Creating a new import replaces the active imported workspace, while update preserves its immutable history. The workflow is guided execution, without a browser model call.

CSV request body for preview/create/update:

```json
{"csv_text":"order_id,region,currency,gross_cents,refund_cents,ticket_count\na,NORTH,EUR,10000,1000,3\nb,SOUTH,USD,20000,0,1\n","rates":{"EUR":"1.20"},"region":"NORTH"}
```

`csv_text` is required. `rates` defaults to `{}`; EUR/GBP require explicit positive USD-rate strings. USD is 1. `region` is optional for preview/create and defaults to the first sorted actual region. On update it must resolve to the workspace's existing selected region. Limits: 1 MiB UTF-8 CSV, 1,000 rows, 10,000 expanded ticket-count rows. Required fields: `order_id,region,currency,gross_cents`; optional `refund_cents,ticket_count`. Rates, counts and CSV structure use the existing strict CLI parser. Money is integer cents. No default or inferred non-USD exchange rate is supplied.

| Method/path | Input | Output |
|---|---|---|
| POST `/api/import/preview` | CSV request | Validated preview, no import/graph publication |
| POST `/api/import/create` | CSV request | New imported workspace state with two guided money reports |
| GET `/api/import/state` | none | Active persisted imported workspace state |
| POST `/api/import/update` | CSV request | Source-only publication, affected artifacts and stale claims; no automatic refresh |
| POST `/api/import/refresh` | `{}` | Refresh both reports plus independent support artifact, returning imported state |
| POST `/api/import/verify` | `{}` | Existing verification shape plus `accounting` for this operation |
| POST `/api/import/export` | `{generation, report_ids:{company,region}}` | Server-checked plain-text snapshot in a JSON envelope; no recalculation |
| GET `/api/import/evidence/{artifact_id}` | owned immutable artifact ID | Existing evidence shape, using this import workspace only |
| GET `/api/import/evidence/{artifact_id}?generation={generation}` | owned immutable artifact ID and observed import generation | Restricted agent evidence shape below; no saved values or source contents |

Preview shape:

```ts
{
  valid:true, persisted:false, content_sha256:string, row_count:number,
  regions:string[], currencies:string[], selected_region:string,
  rates:Record<string,string>, supported_ticket_regions:string[],
  preflight_calculation_count:8, recorded_tool_calls:0,
  accounting:{preflight_calculation_count:8,recorded_tool_call_count:0,
              verification_calculation_count:0,total_calculation_count:8}
}
```

Imported state retains the demo's `session_id`, `generation`, `created_at`, `backend`, `reports`, `graph`, `executions`, `impact`, `last_refresh`, and `notices` shapes, with these differences/additions:

```ts
{
  mode:"guided_csv_import",
  dataset:{label:"Imported CSV",selected_region:string,regions:string[],
    currencies:string[],row_count:number,source_csv_sha256:string,
    sources:SourceState[]}, // source names: orders/refunds/fx/tickets
  reports:Array<Report & {key:"company"|"region"}>,
  incomplete_update:boolean,
  last_operation:{kind:"create"|"update"|"refresh"|"verify",
    preflight_calculation_count:number,recorded_tool_call_count:number,
    verification_calculation_count:number,total_calculation_count:number,
    changed_source_count:number,noop:boolean,elapsed_ms:number,
    tool_calls:ToolCall[]}
}
```

Each imported report contains one USD-cent claim: company total or selected region. Support remains a separate actual artifact; no zero-ticket claim is fabricated. All graph nodes/edges and receipts derive from executed work. `incomplete_update` marks a failed multi-source publication; refresh refuses until the same corrected CSV is successfully resubmitted. `source_csv_sha256` describes the last successful load, not a failed partial update.

Imported monetary claim `value` and `saved_value` are JSON integers within JavaScript's safe integer range and canonical base-10 strings outside it; a stale current `value` remains null. Parse either exact form as an integer before formatting currency. Imported evidence can include a top-level `display_saved_value` projection for a large monetary scalar. This projection is for display only: `artifact.saved_value`, its content hash, and the receipt retain their canonical contents.

Export requires the visible import generation and exactly both report-head IDs. Under the session lock it verifies those identities and native currentness for both complete reports and their USD claims. Success returns `{filename:"proofflow-current-reports.txt",media_type:"text/plain;charset=utf-8",checked_at:"UTC ISO timestamp",content:"…"}`. The text contains both amounts, report/claim IDs, and the check time; it is a static file that later corrections can supersede. A mismatch, stale or incomplete report returns 409; unavailable evidence returns 503. Missing session/import and malformed body retain the usual 401/404/400 errors. Success and failure responses set `Cache-Control: no-store`. No revenue recalculation, source publication, artifact/receipt commit or graph write occurs; normal session-access and rate-limit bookkeeping still applies. The browser must download the server's content and reconcile state after refusal, never export cached amounts. [Acceptance evidence](REPORT_HANDOFF_ACCEPTANCE.md).

### Generation-bound evidence inspection

Adding the `generation` query parameter to the existing imported-evidence GET selects the restricted response used by the hosted connector's `inspect_evidence` tool. URL-encode both the artifact ID and generation. Without this parameter, the existing browser evidence response is unchanged. The server checks the active generation, update completeness, selected artifact, producing receipt and native relationships under the owning session lock; a concurrent workspace replacement cannot interleave with this read.

```ts
{
  schema_version:1, generation:string, incomplete_update:false,
  backend:{engine:"HydraDB OSS",native_queries:number,fallback:false},
  artifact:{id:string,kind:"artifact",logical_id:string,content_hash:string,
    state:"current"|"stale",current_head_id:string,
    reasons:Array<{id:string,reason:"version_changed"|"implementation_changed",current_id?:string|null}>},
  receipt:{id:string,content_hash:string,tool:string,tool_version_id:string,
    status:"success",output_id:string,output_hash:string},
  inputs:Array<{name:string,id:string,kind:"source"|"artifact",logical_id:string,
    content_hash:string,inspectable:boolean}>,
  recorded_changed_source_paths:Array<{source_id:string,target_id:string,
    nodes:Array<{id:string,kind:string,logical_id:string}>,
    edges:Array<{source:string,target:string,kind:"CONSUMED"|"PRODUCED"}>}>,
  path_scope:string
}
```

Only artifacts are inspectable, including earlier report or calculation versions in the active imported workspace. Follow inputs marked `inspectable:true`; source IDs and the receipt's tool-version ID identify consumed versions but cannot be inspected through this mode. The response omits saved values, raw source contents, CSV rows, tool parameters, cookies and session credentials. It performs no calculation, source publication or artifact/receipt write; ordinary session-access bookkeeping still applies.

`recorded_changed_source_paths` contains native witnesses from accumulated recorded changed-source versions, including earlier corrections, with at most three paths per source and depth at most 15. It is not the artifact's complete lineage or a list limited to the latest edit. An empty path list is not a currentness verdict; use `artifact.state` and `artifact.reasons`.

A wrong generation or incomplete update returns 409, as does unknown currentness or an incomplete producing receipt. Unknown IDs, IDs from another workspace, and non-artifact IDs return 404. Missing session/import and unavailable native evidence retain the usual 401/404/503 errors. Successful responses set `Cache-Control: no-store`. A failed read must not be replaced with a previously successful envelope or described as a current check.

Counters count registered analytics invocations, not total CPU work. Preview performs 8 preflight calculations. Create independently revalidates (8), executes the guided recipe (8 recorded calls), and verifies the two report recipes (11 unrecorded calculations). Thus a preview followed by create performs both sets of validation. Update performs 8 preflight calculations and 0 recorded calls; it leaves affected reports stale. Refresh records only actual changed tool executions, plus 11 separate verification calculations. Verification alone performs 11 recipe calculations. A no-op update/reorder still validates; it is not a zero-total-compute claim. `total_calculation_count` sums the three disclosed categories for that operation only.

Failures use the existing error envelope, with no assumed counters. Do not display a failed operation as zero work or substitute optimistic state. Re-fetch state after recovery; a backend failure remains an error. Five acceptance inputs and expected numeric/identity semantics are frozen in `fixtures/browser_csv_v1/acceptance_manifest.json` before implementation/testing.

Import POST bodies also have an 8 MiB JSON transport cap (413), allowing JSON escaping overhead while bounding buffering. The stricter decoded CSV limit remains 1 MiB (400). Interrupted verification returns 409 without accounting because a partially evaluated recipe's count is not reported as zero. The local CLI retains its public constructed-dataset validation boundary: parsing plus `apply_import` perform 16 preflight calculations there, reported explicitly alongside recorded and verification calls. Browser create safely avoids that repeated pass by passing only its direct parsed result to the internal publication helper; output semantics remain the same.

Set server-only `PROOFFLOW_COOKIE_SECURE=true` for HTTPS hosting. Cookie security does not rely on unverified forwarded headers. Local HTTP defaults to a non-Secure cookie; both modes retain HttpOnly and SameSite=Strict.
