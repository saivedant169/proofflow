# Browser CSV acceptance evidence

On 2026-11-15, six of six local Chromium acceptance tests passed against the built ProofFlow frontend and real HydraDB OSS. Playwright 1.56.1 used Chromium 141.0.7390.37 on macOS arm64, at 1536×1024 plus one 390×844 mobile context. The tests used new session state and graph namespaces. No fallback graph, hosted ProofFlow app, or production fault hook was used. There were zero retries, skipped tests, flaky tests, or unexpected results in the final positive run.

| Browser flow | Verified behavior |
| --- | --- |
| Upload → validate → create → reload | Validation did not publish anything; creation produced $308.00 company and $108.00 NORTH reports. Reload preserved the workspace generation and artifact IDs. |
| FX correction → reload → refresh → reorder | Only the FX source changed. The four exact affected artifacts withheld their current values; the native HydraDB path connected the prior FX source through execution to the regional artifact. Four recorded runs restored $317.00 / $117.00. Reordering required eight validation calculations and zero recorded runs, preserving canonical source, artifact, and execution IDs. |
| Two invalid replacements after valid previews | Malformed input returned HTTP 400. The browser rejected the file over 1 MiB without issuing a publish request. Both discarded readiness; existing reports and source IDs survived reload. |
| Two browser contexts | The same evidence artifact was readable by its owner (200) and unavailable to the other context (404). The independent APAC workspace retained $163.75 / $93.75 after the first context edited its data. No zero-support claim or horizontal overflow appeared in the mobile check. |
| Lost mutation and reconciliation responses | The browser lost the response after a real update committed, then lost the reconciliation read. It removed current figures; reload recovered stale state and a real refresh restored current reports. |
| Partial publication and repair | A test-only exception immediately followed a committed orders-source replacement. The fault event's old/new IDs and hash matched the before/after snapshots. Refunds, FX, and tickets remained unchanged. The UI withheld current amounts across reload; refresh refused with HTTP 409. Full resubmission published refunds, retained the committed orders head, and seven recorded refresh runs restored $336.50 / $136.50. |

The arithmetic control ran the **same FX browser test and unchanged expected values** against a disposable server whose conversion added one cent to NORTH at EUR 1.30. Chromium rendered $317.01 and $117.01 versus the expected $317.00 and $117.00. Playwright exited 1 with exactly the intended value assertion failure. The control command exited 0 after verifying both mismatches and ruling out unrelated errors. This was a deliberate test failure, not an application regression.

The suite and runner are on isolated commit `68f6848569ef5c12dd50e89d10ced7f1baef2db0` (tree `fb2226789df8bc284af9ff76b7bdf8ef9853bf7d`), based on `8f5b9dec7c162a617354775f3014fa3e9032e389`. The final positive run preceded the negative-only trace change and failure-only screenshot cleanup; the passing paths and assertions were unchanged. Independent review verified the revised isolation and exact FX lineage checks and found no remaining blocker in the documented workflow.

| Preserved run | Result | Raw Playwright report SHA-256 |
| --- | --- | --- |
| Positive draft | 5/6; an FX assertion used the wrong capitalization and text for the visible label. | `13d8feead4b3d6edf77cdd3653455488d0683cb76989be6cb2ac58e7ed741e2f` |
| Positive corrected | 6/6 after correcting the label check and linking partial publication to immediate pre-fault source IDs. | `1b99e354b55cfc501dde0bfb40c46d5d56d544f2ecd81bc4be919a9848110159` |
| Positive final | 6/6 after review; zero unexpected, skipped, flaky, or top-level errors. | `9e3f032309c217b7358cc8d61ab10f57a1d78f066beed7827df4d2b46adcad97` |
| Negative first | Same exact amount mismatch, plus a Playwright teardown timeout. The control command rejected this attempt. | `5511dcc0516cac093e018c2a5cc680e9a3e0cc51f9da48fad891637ec709e5ea` |
| Negative clean | One expected assertion failure and no other errors; control command passed. | `0c1500faa9af555b0dadb29177bca227dcf886d1a4001813b414e19eca162a88` |

Publishable assertion summary SHA-256: `985ca5449f9d1bdf8f2617047abd29007a71213b1b9164084b3a59d06c335b3f`. Publishable negative-control summary SHA-256: `84e6f4b993bf98bde798b9727a44ea37331fa998dd3c6e4da68c757fa6d9375b`. Frozen acceptance fixture manifest SHA-256: `a764314e455a99ddcd551f4e1dec226fb7fa393667a00d1107b2510a1fbed823`. Raw reports, traces, logs, and session state are preserved privately; the summaries omit credentials, cookies, and per-session IDs.

The seven test files were integrated unchanged in `5fd10ae`; their hashes and the curated evidence are in [the run manifest](../evidence/browser_e2e_v1/run_manifest.json). Inspect the [assertion ledger](../evidence/browser_e2e_v1/assertions.jsonl) and [negative-control result](../evidence/browser_e2e_v1/negative-control.json).

To reproduce on the Linux CI runner, run after installing the locked Python environment and starting the workflow's pinned HydraDB on loopback:

```sh
cd frontend
npm ci
npx playwright install --with-deps chromium
export PROOFFLOW_E2E_PYTHON="$GITHUB_WORKSPACE/.venv/bin/python"
export PROOFFLOW_HYDRA_TOKEN_FILE="$GITHUB_WORKSPACE/.state/hydra-token"
export PROOFFLOW_E2E_OUTPUT_DIR="$RUNNER_TEMP/proofflow-browser-e2e"
npm run test:e2e
npm run test:e2e:negative
```

For CI publication, allowlist `assertions.jsonl` and `negative-control.json` from the printed run directories. Linux CI, hosted ProofFlow, and other browser engines were not exercised in this verification. Concurrent load makes the local run durations unsuitable for performance comparisons.
