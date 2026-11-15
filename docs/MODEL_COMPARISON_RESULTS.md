# Fresh actual-model comparison: saved-report refresh

Frozen revision `3fa9f850bbecdccf068bbda7e90cd0497e79b460`, CI run `43719694368`. Prepared manifest SHA-256 `7f5af0c2214e5d758787ae1bda216bf91c778e2daadc8901c72fe668da3f86c0`.

All 48 scheduled Fable 5.2/high invocations completed with known billing and were scored. The CLI reported 96 aggregate turns. Total reported provider list cost was $9.8783764 against the $10 soft stop, with no harness retries, fallback models, or provider infrastructure failures. Internal provider request counts are not inferred from CLI turns. The final prepared inventory matched all 801 frozen files.

The preregistered gate passed. Graph recovered 32/32 affected recoverable reports, blocked all 4 unavailable reports, and preserved all 52 unaffected report identities. Across M01–M07 its provider input exposure was 75,422/191,774, or 39.33% of full context, below the 50% threshold. Including the no-op the ratio was 35.17%. Receipt-only ratios were 35.47% and 31.04%, respectively.

## Outcomes by arm

| Arm | Fresh affected | Correction cases | Model task success | Unavailable blocked | Unaffected report IDs preserved | Incorrect-current reports |
|---|---:|---:|---:|---:|---:|---:|
| graph | 32/32 | 6/6 | 8/8 | 4/4 | 52/52 | 0 |
| exact_flat | 32/32 | 6/6 | 8/8 | 4/4 | 52/52 | 0 |
| bm25 | 25/32 | 3/6 | 5/8 | 4/4 | 52/52 | 0 |
| dense | 5/32 | 0/6 | 2/8 | 4/4 | 52/52 | 0 |
| iterative_hybrid | 28/32 | 3/6 | 5/8 | 4/4 | 52/52 | 0 |
| full_context | 32/32 | 6/6 | 8/8 | 4/4 | 52/52 | 0 |

M07 used valid non-abstaining plans and the expected missing-source execution refusal. M08 used valid empty, non-abstaining plans. Each arm retained all 39 immutable candidate histories per case and the audit additionally verified every pre-existing source, tool, and receipt record. Numerical equality in the conversion-tool and equal-value-edit cases still required current version lineage.

## Affected recoverable reports by case

| Case | Eligible affected | Numerically changed | Graph | Exact flat | BM25 | BGE | Iterative hybrid | Full context |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M01 | 4 | 4 | 4 | 4 | 4 | 0 | 2 | 4 |
| M02 | 3 | 3 | 3 | 3 | 1 | 0 | 2 | 3 |
| M03 | 4 | 4 | 4 | 4 | 1 | 0 | 4 | 4 |
| M04 | 6 | 5 | 6 | 6 | 4 | 0 | 6 | 6 |
| M05 | 11 | 0 | 11 | 11 | 11 | 5 | 11 | 11 |
| M06 | 4 | 0 | 4 | 4 | 4 | 0 | 3 | 4 |
| M07 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| M08 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Provider accounting

| Arm | CLI calls | Turns | Uncached input | Cache write | Cache read | Input exposure | Output | List cost (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph | 8 | 16 | 16 | 64,625 | 12,430 | 77,071 | 8,515 | 1.3772140 |
| exact_flat | 8 | 16 | 16 | 8,612 | 68,467 | 77,095 | 8,848 | 0.5055334 |
| bm25 | 8 | 16 | 16 | 67,688 | 7,995 | 75,699 | 8,570 | 1.4275350 |
| dense | 8 | 16 | 16 | 67,774 | 7,995 | 75,785 | 7,288 | 1.3776310 |
| iterative_hybrid | 8 | 16 | 16 | 68,163 | 7,995 | 76,174 | 8,894 | 1.4480950 |
| full_context | 8 | 16 | 16 | 211,449 | 7,680 | 219,145 | 8,938 | 3.7423680 |

## Verify and reproduce the accounting

The audit reconciled saved raw stdout and stderr against the CLI hashes, all 48 ledger reservations and settlements, and the frozen request and context bytes. Each raw modelUsage counter was added once. The declared test patches were applied to independently decoded raw-row provenance, the reports were recomputed using Decimal half-even conversion, and receipt chains were traced through source and tool versions for all saved candidate heads. The saved scoring outcomes and complete pre-execution records agreed. The audit read saved JSON and CSV artifacts and the committed Git blob.

Before any paid reservation, a separate launch stopped because a read-only WAL-mode SQLite audit generated 16 untracked journal sidecars. The sidecars were archived privately, and the exact 801-file frozen inventory was restored without changing any original hashes. The stopped preflight made zero paid calls and observed no plans.

## Scope and limitations

- One frozen case/arm sample with a shared Hydra-assisted refresh and currentness executor.
- Graph and exact-flat produced the same ordered prompt for each of eight cases. Separate model invocations and cache accounting do not establish an engine advantage.
- The five capped arms use each case's full graph closure as the matched receipt allowance. Full context is uncapped. This is an adaptive comparison.
- Claude Code reported two turns per invocation. Turn count is reported as an aggregate, with no inference about backend request count.
- Provider input exposure includes cache creation and read tokens. Reported list costs are separate from subscription charges and depend on cache treatment.
- Observed timings describe this sequential, cached local run. Input exposure cannot establish a latency or cost benefit.
- M07 tests safe missing-source refusal and M08 tests canonical no-op handling. Both have zero recoverable affected reports.
- Scorer inspects stale stored values for audit, while unavailable whole reports must be blocked. Partial claim-slot serving is outside scope.
- A prior independent audit checked fixture coverage against the original workbook. The endstate audit reconstructs arithmetic from the frozen provenance and CSV files.
- One unpaid June dry-run start covered both development cases. The frozen protocol permits up to two starts. Its reference to two retained starts does not match the saved ledger.
- Other experiments, including the stopped compact-receipt effort, contribute no observations to this study.

## Inspect the evidence

The [frozen protocol](MODEL_COMPARISON_PROTOCOL.md) and [data specification](MODEL_COMPARISON_DATA_SPEC.md) preceded the March contexts and paid calls. Code and fixtures were frozen at `2c24c57`; all 48 exact requests were then committed at `3fa9f85`. [Prepared request manifest](../results/model-v4-test-prepared/prepared.json) · [original final summary](../results/model-v4-test-run-1/summary.json).

The test contains **4,681 eligible positive-sales rows and 203 invoices from March 1–4, 2011**, drawn from UCI Online Retail under the accompanying attribution. June 1–2 supplied a separate no-model development check. Corrections and report compositions are authored interventions, not observed historical incidents. These larger benchmark fixtures use the runtime directly; they do not expand the browser's 1,000-row input limit.

Inspect the [48-cell independent audit](../results/model-v4-test-run-1/publication/audit.json), [provider counters and recorded selections](../results/model-v4-test-run-1/publication/provider_metrics.json), and [complete publication inventory](../results/model-v4-test-run-1/publication/publication_manifest.json). Every cell retains its original `result.json`, `execution/independent_audit.json`, and `execution/post_snapshot.json`; the [poststate manifest](../results/model-v4-test-run-1/publication/poststate_manifest.json) lists all 144 files and the already-tracked reconstruction inputs. For example, [M01 graph](../results/model-v4-test-run-1/M01/graph/result.json) and its [saved poststate](../results/model-v4-test-run-1/M01/graph/execution/post_snapshot.json) expose the full value and receipt evidence.

Original provider envelopes, terminal output, SQLite files and blobs remain in a private archive. Their [exact hashes](../results/model-v4-test-run-1/publication/raw_sha256.json) are preserved; published provider fields retain accounting and selection data while omitting provider session identifiers. The [prelaunch stop](../results/model-v4-test-run-1/publication/prelaunch_stop.json) and [resolution](../results/model-v4-test-run-1/publication/prelaunch_resolution.json) record the unpaid inventory failure. Root checks found no configured Hydra credential value or observed provider session identifier in the publication set. Some exact result files retain the original host-local paths; use the repository-relative manifest paths to locate the published evidence.

The frozen paid harness deliberately prevents resuming or retrying this observation. A new paid replication needs its own prospectively frozen study identity and spending ledger. Inspecting the supplied response and state evidence does not require a model account. Earlier deterministic, actual-model and compact-capacity experiments are preserved separately; this result does not repair or replace their failed gates.

### Recheck the published evidence without credentials

From the repository root, with Python 3.10 or later:

```sh
python3 scripts/audit_model_comparison_v4.py .
```

This standard-library verifier uses only the published JSON/CSV evidence: 152 hashed payload files plus their publication manifest. It reconstructs the 4,681 source rows and exact monetary calculations, follows receipt/source/tool versions, verifies immutable pre-execution anchors, and reconciles all 48 outcomes, provider counters, ledger charges and gates. Saved runtime inspections and refusal responses are observations checked against independently derived arithmetic and provenance; the verifier does not re-execute HydraDB. It imports no application runtime and requires neither HydraDB nor a model account. A relocated evidence-only copy passed. A disposable one-cent report change failed the independent arithmetic check even after its publication hash was updated. This audits the saved observation; it does not rerun the model or independently establish that a provider generated the recorded response.
