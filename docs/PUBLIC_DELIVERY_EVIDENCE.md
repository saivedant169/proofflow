# ProofFlow delivery and recovery evidence

[Evidence page](https://proofflow.arnavbule.in/evidence/) · [Delivery evidence ZIP](https://proofflow.arnavbule.in/evidence/proofflow-delivery-evidence.zip) · [ZIP SHA-256](https://proofflow.arnavbule.in/evidence/proofflow-delivery-evidence.zip.sha256)

These saved observations span three historical hosted releases and separate local and Linux recovery runs. Each receipt records the revision it observed. The archive contains study inputs, sanitized receipts, and a Python standard-library verifier. It is available independently of the model-study download.

## Verify offline

Save the ZIP and the checksum side by side. On macOS use `shasum -a 256 -c proofflow-delivery-evidence.zip.sha256`. On Linux use `sha256sum -c proofflow-delivery-evidence.zip.sha256`.

Extract into a new directory and use Python 3.10 or later.

```sh
unzip proofflow-delivery-evidence.zip -d proofflow-delivery-evidence
cd proofflow-delivery-evidence
python3 verify_delivery_evidence.py
```

The verifier matches the exact file inventory and hashes, recomputes report amounts independently, and checks the relationships asserted by the saved receipts. It needs no network, browser, model account, or database. The checks concern recorded observations. A new deployment, database restart, service replay, or audit of the complete original retail workbook would require separate evidence.

## Results in the archive

| Saved observation | What the verifier checks |
| --- | --- |
| Hosted release `92da58c` | The receipt reports 11 Chrome steps and 13 guided HTTP checks, eight anonymous byte-matched downloads, and discovery of five connector tools with zero tool calls. |
| Hosted release `fdee9c9` | The previous release receipt reports 11 Chrome steps and 13 guided HTTP checks. |
| Hosted release `0535ba6` | The application restart passed 87 checks across 12 responses. The receipt retains both transient HTTP 502 responses alongside the restored reports. |
| January 2011 retail partition | Recomputes 642 eligible rows across 25 invoices from their numeric source cells. Both reports rose from $9,052.58 to $9,414.68 after the authored FX correction. The saved run on `92da58c` refused the old export with HTTP 409 and recorded four refresh executions and 11 verification calculations. |
| Paired small-file close | Recomputes all eight outputs for three phases. Whole-file recalculation and ProofFlow each rejected four stale handoffs and accepted three current handoffs. ProofFlow retained four published heads and receipts after the first correction and two after the second. Both warm corrections together took 64 registered analytics calls, including preflight and verification. |
| Interrupted multi-source update | Checks the saved mixed-source boundary, child-process exit, withheld values and refusals after reopen, amounts after full resubmission, and parity with the uninterrupted control. The recorded lifecycle used 69 calculations versus 61 for control. The 15-point check suite also passed on a Linux runner. |

## Fixed-budget diagnostic receipts

The archive also preserves the original incomplete summary, the independently reviewed recovery summary, and the original-file hash index. The original wrapper failed all 88 publication records after saving their scores. A separate read-only audit recovered 88 saved observations. This bundle checks those summary digests and aggregate relationships. The underlying cell snapshots and inputs remain outside this ZIP.

| Evidence cap | Graph | Exact-flat | BM25 | Dense BGE | Iterative hybrid |
| --- | ---: | ---: | ---: | ---: | ---: |
| 4,096 | 15/32 | 15/32 | 5/32 | 2/32 | 15/32 |
| 8,192 | 27/32 | 27/32 | 25/32 | 10/32 | 28/32 |

The uncapped deterministic reference completed 32/32. Every capped method fell short of that result. Graph and exact-flat packed identical evidence across all eight cases at both caps. The diagnostic ran without model calls and is separate from the model study.

The paired comparison is one authored workflow, and the hosted extract is one date and one country. The interrupted-update test killed the API child between committed source updates, while HydraDB remained running. The historical restart concerned the application container. These observations measure functional behavior and artifact reuse. Human adoption, relative compute cost, production load, and uninterrupted availability were outside the runs.

The manifest records hashes and lengths for the complete allowlist. For affected receipts it also records the original digests and the exact fields removed or replaced. Redactions cover direct IP references, session and workspace identifiers, local workspace references, and private workflow URLs. Runtime code, cookies, original execution archives, and screenshots are outside the ZIP. The public Online Retail data has [attribution and extraction notes](fixtures/real_partition_v1/DATASET_NOTICE.md).
