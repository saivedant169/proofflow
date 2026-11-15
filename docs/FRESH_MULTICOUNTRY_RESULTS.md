# Multi-country CSV correction: guarded recalculation and ProofFlow

**Both methods passed the first and only paired attempt.** Ordinary full
recalculation with a latest-version guard and ProofFlow each matched all 16
scheduled semantic outputs, refused both stale handoffs without content, and
accepted both current handoffs. ProofFlow additionally retained four unaffected
artifact heads and their producing receipts, with native dependency paths
explaining the stale reports. Full recalculation covered the amounts and ordered
handoff requirement on this small file. [Protocol](FRESH_MULTICOUNTRY_PROTOCOL.md)
· [Sanitized receipt](../results/fresh-multicountry-v1/receipt.json).

The prospective selection found all 933 eligible positive-sale lines from April
10, 2011: 907 UK lines and 26 Belgian lines across 32 invoices. The CSV remained
byte-identical through an authored GBP/USD correction from 1.25 to 1.30. Both
methods agreed with the independent original-cell oracle:

| Stage | United Kingdom | Belgium | Company |
| --- | ---: | ---: | ---: |
| Initial, GBP/USD 1.25 | $11,796.86 | $595.61 | $12,392.47 |
| Corrected, GBP/USD 1.30 | $12,268.74 | $619.44 | $12,888.18 |

The UK report and company report differ. Country subtotals are converted and
rounded separately before the company sum. The resulting company value is one
cent below a combined-total conversion initially and one cent above it after
correction. This distinction was found **after** selection and was not used to
choose the date. [Raw-cell reconciliation](../fixtures/fresh_multicountry_v1/oracle-audit.json)
· [Frozen expected outputs](../fixtures/fresh_multicountry_v1/cases.json).

All source prices are GBP. Refund/support observations are absent; empty sources
provide modeled zero contribution, not evidence of actual zero refunds or
tickets. These amounts describe a positive-sales extract, not complete merchant
revenue. [Dataset attribution and transformations](../fixtures/fresh_multicountry_v1/DATASET_NOTICE.md).

## What remained valid, and what ran

Each ordinary phase validated all 933 rows in one scan, recalculated eight logical
outputs together and passed four reconciliation controls. Its shared input
revision and exact-file guard rejected the old working copy before and after
publication of corrected reports.

ProofFlow initially recorded eight imported outputs. The FX refresh created four
new outputs and matching receipts: regional USD conversion, company total and
both reports. Gross GBP, refunds, net GBP and support retained exact artifact
**and producing receipt** identities. Only the FX source version changed. While
stale, both current claim values were null; native paths connected the old FX
source to each old report. The two old-identity export requests returned HTTP
409 without content, and the two current exports succeeded. All four exports
used no-store and invoked zero calculation tools. Both initial exported files
remained byte-identical after correction.

| ProofFlow operation group | Preflight calls | Recorded calls | Fresh verification calls | Total |
| --- | ---: | ---: | ---: | ---: |
| Guided session bootstrap | 0 | 8 | 0 | 8 |
| Cold preview and create | 16 | 8 | 11 | 35 |
| Warm FX preview, update and refresh | 16 | 4 | 11 | 31 |
| Total including bootstrap | 32 | 20 | 22 | 74 |

These observed registered-function invocations reconcile with per-request
accounting. Ordinary logical outputs can be computed together in one loop; the
units differ. Four retained heads do not establish compute, latency or cost
savings. Independent fixture/oracle preparation and offline audits are separate
work, not included in this product invocation table.

The independent private post-run audit passed 44 checks, verifying all 51 frozen
files and 17 retained attempt payload hashes, arithmetic, receipt bindings, path
edges, guard outcomes and call counts. Its two corrected auditor assumptions are
retained: the one-cent differences have opposite signs; and the saved update
visualization contains seven initial executions, omitting support. No experiment
rerun or evidence change occurred. Complete execution-list equality at update
relies on the frozen runner's live assertion. Offline evidence directly confirms
no new displayed executions or heads and zero recorded update calls.

## Reproduce the arithmetic and inspect the projection

The checked-in verifier uses only Python's standard library and makes no network,
model or application calls:

```sh
python3 scripts/verify_fresh_multicountry.py
python3 scripts/verify_fresh_multicountry.py --workbook '/path/to/Online Retail.xlsx'
```

The first command checks the [package manifest](../results/fresh-multicountry-v1/manifest.json),
reconstructs all uploaded amounts from original numeric cells, checks both stages'
exact cents, and checks normalized receipt consistency. The optional original
workbook must match the pinned SHA-256; it enables an independent full-workbook
selection, completeness and original-cell audit. Obtain it from the attributed
UCI record above. Neither command reruns the measured workflow.

The receipt is a **sanitized observation projection**: original session, workspace,
artifact and receipt IDs become consistent semantic aliases, and private paths
are omitted. Original private evidence hashes are commitments to retained bytes;
they do not make those bytes available. The public-file verifier cannot by itself
attest native service execution or authenticate private snapshots. It establishes
reproducible arithmetic and internal consistency of the supplied projection.

## Scope

Execution used unchanged source `c2c19c1397026e136bf7648ddb0604a4d2ea6d7f`, native
local HydraDB OSS 0.4.0 and one ordered paired attempt. The study freeze is
`855e22cec6cc68afd80cb0b2f4c98749e06cdaaf76b1551cb50c6241204d2cdd`; independent
post-run audit SHA-256 is
`96615fa0204248d030f6e15b4c6ee77970dd5a4ceedcf7050c3147e74ec79bdc`.
Run timestamps are retained for chronology, not comparative performance.

This is one previously unprepared multi-country day from the same known public
dataset, outside months with retained eligibility profiles. It is not an unseen
or sealed holdout: prior scans inspected workbook-wide eligibility/invoice
relationships, and prior unexecuted proposals named April. This local API trial
does not add a hosted/browser result, generative-model result, customer outcome,
learning claim or broad-generalization estimate. Missing-source and negative-value
cases were not scored; synthetic omission/zero checks remain separate.

The measured distinction is preserved artifact-level work and stale-reason
evidence, with equal guarded-handoff protection in this ordered single-writer
sequence. A competent versioned full recalculation is sufficient when correct
amounts and ordered current-handoff checks are the only requirements.
[Earlier synthetic paired comparison](WORKFLOW_COMPARISON_RESULTS.md)
· [Earlier single-country hosted acceptance](REAL_PARTITION_RESULTS.md).
