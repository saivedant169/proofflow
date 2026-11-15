# ProofFlow browser API contract

Same-origin JSON API. Browser session is an opaque HTTP-only cookie `proofflow_session`; fetch with normal same-origin credentials. No API/model/Hydra keys go to the browser. All demonstrated tools execute locally against the authored dataset. This is a guided workflow, not a hosted LLM endpoint.

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

`state` is `current`, `stale`, or `unknown`. A stale/unknown claim's `value` is **null**; `saved_value` is historical display only and must be clearly labeled. Monetary values use integer cents; divide by 100 for display. Source-change effects are conservative source-level revalidation, not a claim that every dependent number changed.

## Errors and limits

Error responses are `{error:{code,message}}`; validation errors use the same envelope. 400 invalid input; 401 missing session; 404 unknown evidence; 409 incomplete/missing evidence; 429 session action limit; 503 Hydra unavailable or session capacity. Never replace a failed state request with optimistic mock data.

Default persistent session limit is 16, configurable through `PROOFFLOW_MAX_SESSIONS`. The application runs as one worker; each session mutation is locked. Static files are served from `PROOFFLOW_STATIC_DIR` (default `frontend/dist`) only after frontend exists. Unknown `/api/*` paths remain API errors rather than SPA routes.

The limit bounds live sessions, not lifetime visitors. Idle sessions expire after `PROOFFLOW_SESSION_TTL_SECONDS` (default 3600); expired owned session directories are reclaimed when capacity is checked. In-flight requests and requests waiting for the same session are protected from reclamation. Persisted last-seen timestamps preserve this behavior across application restarts. Failed initializations release their reserved capacity. Expired browsers receive 401 on state and can start a new demo with `POST /api/session`.

Set server-only `PROOFFLOW_COOKIE_SECURE=true` for HTTPS hosting. Cookie security does not rely on unverified forwarded headers. Local HTTP defaults to a non-Secure cookie; both modes retain HttpOnly and SameSite=Strict.
