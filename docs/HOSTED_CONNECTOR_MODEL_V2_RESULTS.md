# Hosted CSV connector model trial V2

**All seven prescribed stages completed in one guided Claude Code run.** Fable 5.2 created and inspected company and United Kingdom reports from the same 642-row retail CSV used in V1. With a rate-only correction, the model omitted `csv_text`. The connector reused the exact CSV already confirmed in its process and sent it to the hosted API. The source CSV digest and workspace generation matched before and after the correction. [Sanitized receipt](../evidence/hosted_connector_model_v2.json).

| Stage | Verified observation |
| --- | --- |
| 1. Create reports at GBP/USD 1.25 | The hosted service matched the exact CSV SHA-256 and returned **$9,052.58** for both company and UK. The operation recorded 8 preflight calculations, 8 executions and 11 verification calculations. |
| 2. Inspect the saved reports | The separate inspection returned the same current values, workspace generation and report and claim identities. |
| 3. Publish GBP/USD 1.30 | The model omitted the CSV argument. The service retained the confirmed source digest, changed only FX and identified four affected artifacts. It performed 8 preflight calculations and zero recorded executions or verification calculations. |
| 4. Inspect before refresh | Both original report heads remained. Their current revenue values were withheld as `null`. |
| 5. Export the original selection | The real hosted request returned **HTTP 409** and no snapshot. This was the expected tool refusal. |
| 6. Refresh affected work | Both replacement reports returned **$9,414.68**. The refresh recorded **4 executions and 11 verification calculations**, reused two artifacts and preserved support. Both values matched the independent oracle. |
| 7. Export the refreshed selection | The checked text matched both corrected values and the new report and claim identities and included a UTC check time. |

The five-tool connector still runs the browser’s fixed report recipes. It retains confirmed CSV bytes in memory in the same process. For a rate-only correction, provide the existing region and all required rates and omit `csv_text`. The connector checks the live workspace, region and source digest before reusing the bytes. Initial creation and row changes still require the complete CSV. [Connector setup](https://proofflow.arnavbule.in/agent/).

## Both attempts

| Attempt | Verified stages | CLI outcome | CLI list-cost estimate |
| --- | ---: | --- | ---: |
| V1, full CSV required at correction | 2/7 | Normal `end_turn`. The model cited its budget estimate and left five steps unattempted. | $1.3265222 |
| V2, confirmed CSV reused at correction | 7/7 | Normal `success` with `end_turn`. Eight CLI turns in 139.448 seconds. | $1.4368254 |

V2 recorded 16 ordinary input tokens, 41,447 one-hour cache-write tokens, 243,727 cache-read tokens and 18,120 output tokens. Billing was unobserved. V1 stopped before attempting the correction, so the costs do not measure savings from the change. Neither client reported a budget-limit error. The audit found no repeated calls, guard blocks or unexpected tool errors in V2. [V1 partial result](HOSTED_CONNECTOR_MODEL_V1_RESULTS.md) · [V2 accounting](../evidence/hosted_connector_model_v2.json).

These are individual guided demonstrations using the same previously browser-tested partition, an authored rate correction and different connector versions and task instructions. They support executing the guided hosted workflow and reusing the confirmed CSV within one process. Continual learning, model-selected computation plans, performance on new datasets and human use were outside the trial. The [browser run](REAL_PARTITION_RESULTS.md) and [local typed planning run](MCP_AGENT_RESULTS.md) have separate evidence.

## Frozen setup and verification

The one-launch trial pinned deployed source `c2c19c1397026e136bf7648ddb0604a4d2ea6d7f`, Linux AMD64 image `sha256:9973b5414c4f23b3ded11a7357a494f89fb568c5e049119c363a58163377b39f` and the 18,841-byte [release connector](https://github.com/saivedant169/proofflow/blob/c2c19c1397026e136bf7648ddb0604a4d2ea6d7f/frontend/public/agent/proofflow_csv_mcp.py), SHA-256 `758f0f20b115e239741fd239b2c826104b0681399c21aea106d4bec0b505e996`. The deployment and connector fingerprints were checked before launch. The GitHub link requires repository access. The public download may change with future releases.

The task used the [tracked CSV](../fixtures/real_partition_v1/orders.csv), SHA-256 `7b45308e83161fa41aace37b1bd9f7f6390566b65a45bb2a0dd9aaf0b8ae69b8`, with 642 positive UK lines from January 16, 2011. The source subtotal is £7,242.06. GBP/USD 1.25 and 1.30 give 905,258 and 941,468 USD cents per report after cent rounding. The prompt supplied the CSV, region, rates and sequence, and the values were reserved for verification. [Dataset attribution and oracle](REAL_PARTITION_RESULTS.md).

Claude Code `2.1.325` requested Fable 5.2 at high effort. A dummy request checked the five-tool schema, optional CSV on correction and requested effort before launch. Both trials used the same $2 CLI estimate setting, $3 planning allowance, ten-turn limit, 20,000 output-token limit per request and 900-second watchdog. The client launched with an empty built-in tool set and no session persistence or browser integration. The guard checked each action against the prescribed sequence and the preceding response, then forwarded allowed requests and actual connector replies. The harness made no retries or fallback launches. Provider-internal transport retries are unobserved. [Freeze and audit bindings](../evidence/hosted_connector_model_v2.json).

<details>
<summary>Exact task message</summary>

Use the following UTF-8 prefix with LF line endings, including the newline after the opening `csv` fence. Append the full tracked CSV with its final newline, then three backticks and one newline. Its SHA-256 is `22536fe2403bbe279b74ef79af4d6037c9c8f567b3a29ea20c8d3d3cd2c8576a`. The system instruction in the [V1 exact task and system instruction section](HOSTED_CONNECTOR_MODEL_V1_RESULTS.md) retained the V1 hash `32f4d96e0a6cc6964eeb20b56ba6c8b35188c88a6bca14a1d126b2ace571a0e9`.

````text
Create both saved revenue reports from the CSV below for United Kingdom, with GBP to USD at 1.25. The CSV includes the final newline. Read the saved reports in a separate action and retain their generation and both report IDs. For United Kingdom, publish only a GBP to USD rate change to 1.30 using the uploaded CSV already confirmed in this connector process. Omit the CSV text from the correction request. Read persisted report state again before recalculating and check whether your original saved selection can still be exported. After that check, refresh affected work once and fetch the server-checked export using the refreshed selection. Tell me what changed, both starting and current report amounts, whether the original export was allowed, and how many calculations were recorded during refresh. Do not add extra operations.

The following fenced block contains the complete CSV, including the newline immediately before the closing fence.

```csv
````

</details>

The sanitized receipt records the audit and the frozen input hashes. Original provider and transport traces, raw identifiers, CSV arguments and session data remain private.
