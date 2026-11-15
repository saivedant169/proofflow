# Recovery after one interrupted CSV update

The first prospective attempt passed all **15 checks**, with no production change. The [protocol](RECOVERY_V1_PROTOCOL.md), two authored CSVs and harness were frozen in `b47fbbf` before execution against unchanged production code `500f3ae`. Two independent reviews then checked the storage/response evidence and calculation ledger.

The fault occurred **between two fully committed source updates**. A parent process independently read SQLite and native Hydra evidence showing corrected orders but baseline refunds, with the incomplete-update marker already durable. It sent actual SIGKILL to the paused API child, which exited `-9`. This did not restart HydraDB or the main application.

After a fresh API process reopened the workspace, both affected monetary claims remained stale and their current values were withheld. The support artifact retained its identity, value and content hash and stayed current. Refresh and verification returned 409 until the complete corrected CSV was resubmitted. That resubmission preserved the original affected dependency roots. Seven recorded refresh calls then produced company revenue **83,125 cents** and RIVER revenue **53,125 cents**, matching independently known arithmetic and the uninterrupted control. All eight current artifact values, hashes and normalized consumed-input lineages matched; there were 19 unique logical current heads.

| Complete arm lifecycle | Preflight | Recorded calls | Verification | Total |
|---|---:|---:|---:|---:|
| Uninterrupted control | 16 | 23 | 22 | 61 |
| Interrupted and recovered | 24 | 23 | 22 | 69 |

Both totals include eight guided-demo bootstrap calls needed to create the browser session. The interrupted request completed eight validation calculations before death. The final refresh itself used **7 recorded + 11 verification** calls. These totals are not an efficiency comparison.

The unchanged detector rejected a copied response with one stale claim changed to current and its old saved value exposed. This checks the response detector; it is not another production-state fault.

Inspect the [check summary](../results/recovery-v1/summary.json), [frozen hashes](../results/recovery-v1/run-manifest.json), [parent boundary observation](../results/recovery-v1/parent-observed-boundary.json), [SIGKILL result](../results/recovery-v1/kill-result.json), [reopened response](../results/recovery-v1/reopened-state.json), [refusal responses](../results/recovery-v1/blocked-recovery-actions.json), and [full accounting](../results/recovery-v1/lifecycle-accounting.json). The control and recovered `*-semantic-lineage.json` files match. The complete successful-calculation traces are retained as `arithmetic-*.jsonl`.

This establishes detection and recovery for this fixed multi-source workload after full resubmission. It does not establish within-write atomicity, transactional publication, OS/power-loss recovery or general crash safety. Private cookies and application state are excluded from the curated evidence; exported session identifiers are pseudonymized. The curated files passed a value-based check against the actual configured Hydra token and both raw experiment session cookies.
