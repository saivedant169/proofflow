# Recovery v1: prospective process-interruption protocol

Status: protocol and fixtures prepared before any fault execution. This document specifies an experiment; it reports no observed result. The parent harness must freeze this file, the fixture manifest, both CSV files, and its harness in one private commit before running either arm. Preserve that commit ID and file hashes with every result.

## Scope and fixed inputs

The production code under test is commit `500f3aeaad373455ddb81c45962ecd82e882c1c0`. Work takes place only in the isolated `private/recovery-v1` worktree. The faulted and uninterrupted control arms use that same production build, fixture bytes, EUR→USD rate `1.25`, and selected region `RIVER`. Each arm receives its own browser cookie, local state directory, and Hydra namespace. Existing HydraDB remains running; neither the main application tree nor its sessions are modified. No model is called.

`fixtures/recovery_v1/manifest.json` freezes the SHA-256 of `base.csv` and `corrected.csv`. Both are UTF-8 with LF line endings and a trailing LF. The correction changes only RIVER gross cents from `42000` to `46000` and refund cents from `2000` to `3500`. HILL, FX, and support-count data remain identical.

These expected amounts are fixed by direct arithmetic, independently of the runtime's recomputation helper:

| State | RIVER net USD cents | Company net USD cents | Calculation |
|---|---:|---:|---|
| Baseline | 50000 | 80000 | `(42000 − 2000) × 1.25`; add HILL `31000 − 1000 = 30000` |
| Complete correction | 53125 | 83125 | `(46000 − 3500) × 1.25`; add `30000` |
| Mixed new orders / old refunds | 55000 | 85000 | `(46000 − 2000) × 1.25`; add `30000` |

The mixed values are diagnostic expectations only. The API must never serve them as current claims. Baseline saved values may remain visible only as explicitly historical values. Support counts are RIVER `2`, HILL `1` throughout.

## Arms and baseline gate

Create each arm through the real imported-workspace API using `base.csv`. Before any fault is enabled, require the independently known baseline amounts, current report claims, eight unique current artifact heads, and current support evidence. Retain the successful CSV metadata, source and artifact head IDs, content hashes, receipts, and native graph evidence. Compare all applicable baseline fields between arms after normalizing their independent IDs.

Stop without injecting a fault if the baseline differs from the fixed expectations. The uninterrupted control later submits the full corrected CSV and refreshes normally. It serves as a same-build recovery parity control, not a competing retrieval system or a database-transaction oracle.

## Deterministic interruption boundary

The fault harness launches a child API process. A test-only wrapper around `ProofFlowRuntime.set_source` calls the original method unchanged. On the corrected update's `csv:orders` publication only, the wrapper pauses immediately after the original call returns and before control reaches the next `csv:refunds` publication. The wrapper must not modify production code, change returned data, fabricate a database failure, or replace source publication with a mock.

Within a single 30-second monotonic deadline covering child launch, acknowledgment, storage/native observations and the decision to kill, the parent must independently establish the paused durable boundary. Individual native requests use a five-second timeout:

1. Open the child's SQLite manifest read-only and observe the corrected orders head with the baseline refunds head. Retain their immutable IDs and content hashes.
2. Read actual native Hydra evidence for the corrected orders version and baseline refunds version in the fault arm's namespace. Record the responses and the wrapper trace proving execution has not advanced to the next refunds publication.
3. Read the on-disk import metadata and observe `incomplete_update=true`; the last successful CSV metadata must still identify the baseline CSV, not the incomplete correction.

Only after those observations, the parent sends `SIGKILL` to that child process. Record the child's return code `-9`, process identity, timestamps, boundary trace, and parent observations before starting recovery. The paused request must not be represented as a successful HTTP update. If a stable boundary is not reached within 30 seconds, or any boundary observation disagrees, stop and retain the failed attempt without moving the hook or searching for a passing boundary in the same run.

This models abrupt termination of the API process after one source publication. It does not model OS power loss, host failure, filesystem corruption, a HydraDB crash, or an atomic transaction across SQLite and HydraDB.

The parent writes the actual baseline and boundary observations before checking their expected values. Timeout stdout/stderr and any available partial observations remain in the attempt directory. A timed-out or failed run is never overwritten.

## Reopen, refusal, and recovery gates

Launch a fresh child API process using the same fault-arm state, cookie, and Hydra namespace, without the fault wrapper. Obtain the imported-workspace state before submitting anything else. Require:

- `incomplete_update=true` after reopen, with baseline last-successful CSV metadata preserved.
- Both affected monetary reports and their monetary claims are stale, with current `value` fields withheld as `null`. Neither baseline nor mixed-state money may appear as a current claim.
- The support head has exactly the baseline identity and content hash and remains current.
- Refresh and verification each return HTTP `409` until the full corrected CSV is resubmitted. Retain both actual responses.

Resubmit the complete frozen `corrected.csv` with the same FX and region. Require publication to complete, clear the incomplete-update flag, and retain the original affected lineage even though orders were already published before interruption. Then refresh through the real API.

The final refreshed state must satisfy all of these gates:

- Exactly seven affected monetary artifact IDs: `import:metric:gross`, `import:metric:refunds`, `import:metric:net`, `import:metric:regional`, `import:metric:company`, `import:report:company`, and `import:report:region`.
- Exactly seven recorded runtime calls for refresh: one each for gross, refunds, net, conversion, and company total, plus two report compositions. The support tool is absent from that call trace.
- Current company value `83125` and current RIVER value `53125`, with unchanged support identity and content hash.
- Eight unique current artifact heads, one per logical artifact ID. Historical immutable versions are expected and are not duplicate current heads.
- Parity with the uninterrupted control for normalized output values, content hashes, tool names and parameters, and named consumed-dependency logical IDs. Compare logical identity and content across arms; independent workspace IDs, execution IDs, run timestamps, and source-version IDs are not required to match.

Preserve every observed failure before any fix. A changed production build, fixture, fault location, or detector requires a new versioned protocol and fresh output directory; it must not replace the original attempt.

## Accounting and detector sanity check

Count registered runtime calls separately from validation and fresh-recipe verification. The expected successful-operation accounting is:

| Operation | Input preflight calculations | Recorded runtime calls | Fresh-recipe verification calculations | Total |
|---|---:|---:|---:|---:|
| Initial baseline import | 8 | 8 | 11 | 27 |
| Full corrected CSV submission | 8 | 0 | 0 | 8 |
| Corrected-report refresh | 0 | 7 | 11 | 18 |
| Explicit verification, if requested | 0 | 0 | 11 | 11 |

The recovery claim's primary execution count is **seven recorded refresh calls**, not seven total calculations. The interrupted request has no successful accounting response; preserve completed preflight/boundary observations without inventing a success count. Refused incomplete-state refresh and verification do not count as successful executions. Record native Hydra requests and elapsed time separately.

Child-only observational wrappers record each successful analytics function call to fsynced JSONL without changing its arguments or return value. Calls through `importing.execute_tool` are preflight; calls through `runtime.execute_tool` are recorded execution only while inside the original `ProofFlowRuntime.execute`, otherwise verification. The `/api/session` prerequisite also executes eight authored-demo tools in its separate namespace and must be included as setup overhead. Expected complete phase counts are: control 16 preflight + 23 recorded + 22 verification; fault-arm setup 8 + 16 + 11; interrupted update 8 + 0 + 0; reopen/refusals 0 + 0 + 0; resubmit/refresh 8 + 7 + 11. The two full arm totals are 61 and 69 analytics calls respectively; the extra eight are the interrupted request's completed validation. These totals are not an efficiency comparison. Recorded refresh tool names/counts must match the fixture manifest's exact multiset.

After collecting the actual reopened incomplete-state response, copy that response in the detector process. Change exactly one monetary claim to `state="current"` with its old baseline `saved_value` exposed as `value`. The same freshness detector must reject this copy. Preserve both response copies and the detector verdict. This is a **response-detector sanity check**, not corruption of production state, an injected database inconsistency, or a second fault-recovery experiment.

## Required record and success wording

Retain the frozen commit and hashes; both arm identities; initial states; correction requests; wrapper/boundary trace; independent read-only SQLite and native Hydra observations; `SIGKILL` exit result; reopened state; both `409` responses; resubmission and refresh responses; actual receipts/call counts; normalized control comparison; the detector sanity check; and the complete pass/fail checklist. Never include credentials or raw cookies in shareable evidence.

Raw cookies and application state are retained only in the attempt's `private/` and `state/` directories, which are excluded from any shareable evidence selection. Exported JSON replaces session IDs with stable SHA-256 pseudonyms and redacts session-containing workspace paths. No Hydra credential value is copied into the experiment.

A passing run establishes only that this fixed workload detects an interrupted multi-source import, refuses unsafe refresh/verification, and converges to the same supported analytics outputs as an uninterrupted same-build control after complete resubmission. It does not establish transactional source publication, general crash safety, universal recovery, or resilience to failures not injected here. No broad test suite, production mutation, Hydra restart, or model run is part of this protocol.
