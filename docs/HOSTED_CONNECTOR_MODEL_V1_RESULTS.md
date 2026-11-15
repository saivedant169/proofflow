# Hosted CSV connector model trial

**Two of seven planned steps were verified in one guided Claude Code run.** Fable 5.2 created both reports with the exact 642-row CSV and then separately inspected the saved reports. Company and United Kingdom revenue each showed **$9,052.58**, with both claims current and the same workspace generation, report IDs and claim IDs. Creation performed **8 preflight calculations, 8 recorded executions and 11 verification calculations**. The independent audit checked the original tool calls and runtime observations. [Sanitized machine-readable receipt](../evidence/hosted_connector_model_v1.json).

The model stopped before the correction because it estimated that repeating the full CSV and finishing the remaining calls would exceed the **$2 CLI estimate setting**. Claude Code returned `success` with `end_turn`, exit code 0 and no CLI budget-limit error. The end-to-end trial did not pass. The remaining work was unattempted, and its cost is unknown. The CLI reported a **$1.3265222 list-cost estimate** for three turns. Billing was unobserved. The observed input counts were 6 ordinary, 35,726 cache-write and 52,691 cache-read tokens, plus 18,608 output tokens. [Accounting and terminal state](../evidence/hosted_connector_model_v1.json).

| Prescribed step | Observed outcome |
| --- | --- |
| 1. Create company and UK reports at GBP/USD 1.25 | Verified on the hosted service using the exact CSV bytes. Both reports returned 905,258 USD cents. |
| 2. Inspect the persisted reports separately | Verified. The values and identities matched the creation response. |
| 3. Publish the same CSV at GBP/USD 1.30 | Unattempted. |
| 4. Inspect the stale values before refresh | Unattempted. |
| 5. Request export with the original report selection | Unattempted. |
| 6. Refresh the affected reports | Unattempted. |
| 7. Request a checked export with the refreshed selection | Unattempted. |

This checks a model issuing guided connector calls on one previously browser-tested retail partition. The hosted app calculates the fixed company and regional recipes. The user task prescribed the operation sequence. The [hosted browser trial](REAL_PARTITION_RESULTS.md) completed the rate correction on the same partition through a separate client. The [local typed MCP experiment](MCP_AGENT_RESULTS.md) tested model-selected report composition, and [hosted delivery checks](HOSTED_DELIVERY.md) report scripted prototype and cold-launch coverage separately.

## Frozen setup and verification procedure

At `2026-11-15T21:45:24.920905Z`, the operator froze the fixture, instructions, guard, launcher settings and preflight results. The independent receipt records the original protocol and packet digests. The trial used Claude Code `2.1.325` with `claude-fable-5-2`, requested `high` effort and one fresh local stdio connector process. A dummy request confirmed the requested effort, the 20,000 output-token limit and exactly five tool descriptors. Both actual tool messages identified Fable 5.2. Prior dummy and separate loopback provisioning failures remain in the receipt. [Freeze and tool provenance](../evidence/hosted_connector_model_v1.json).

To reconstruct the trial inputs, use the [tracked January 16 CSV](../fixtures/real_partition_v1/orders.csv) and the connector from release `b13f23892405efb856c8d4ca0e6abc94a1eca77c`. The release and image are bound to the [verified deployment](../evidence/hosted_delivery_v4.json). The CSV is 28,429 bytes with SHA-256 `7b45308e83161fa41aace37b1bd9f7f6390566b65a45bb2a0dd9aaf0b8ae69b8`. The 11,532-byte [release-pinned script](https://github.com/saivedant169/proofflow/blob/b13f23892405efb856c8d4ca0e6abc94a1eca77c/frontend/public/agent/proofflow_csv_mcp.py) has SHA-256 `59e9db0ca368aaeecaac3819b32dacc3f1cf77e589a2d55a71a2c4c21900ef11`. The GitHub link requires repository access. The public download may change as the app is updated. [Dataset attribution and independent arithmetic](REAL_PARTITION_RESULTS.md).

The original launcher restricted the client to the five shipped MCP tools, an empty built-in tool set, no session persistence and no browser integration. The limits were one operator launch, one workspace, up to ten client turns, a 900-second watchdog, a 20,000 output-token limit per request and a $2 client estimate setting against a $3 planning allowance. The guard checked the requested step and arguments against the protocol and the preceding live output. It forwarded valid calls and the connector’s responses byte for byte and could block invalid calls. The run had zero harness retries, and provider-internal transport retries are unobserved.

The prespecified checks were two current values of 905,258 cents on creation and stable IDs on inspection, four affected heads and zero recorded executions on correction, and null current values before refresh. The old selection had to return HTTP 409. Refresh had to produce both reports at 941,468 cents in four recorded executions and 11 verification calculations while preserving support. Export had to match those refreshed amounts and heads with a UTC check time. The last five of these stages are expectations from the protocol only.

<details>
<summary>Exact task and system instruction</summary>

The user message begins with the following UTF-8 bytes, using LF line endings and including the newline after the opening `csv` fence. Append the full tracked CSV with its final newline, then three backticks and one newline. The resulting SHA-256 is `1fca9dd2cc54de701ff2a0ed7e57dd0f8d702d975bd7d7a02a331423b9d5d279`.

````text
Create both saved revenue reports from the CSV below for United Kingdom, with GBP to USD at 1.25. Read the saved reports in a separate action and retain their generation and both report IDs. Publish the full, byte-identical CSV again for United Kingdom with only the GBP to USD rate changed to 1.30. The CSV includes the final newline. Read persisted report state again before recalculating and check whether your original saved selection can still be exported. After that check, refresh affected work once and fetch the server-checked export using the refreshed selection. Tell me what changed, both starting and current report amounts, whether the original export was allowed, and how many calculations were recorded during refresh. Do not add extra operations.

The following fenced block contains the complete CSV, including the newline immediately before the closing fence.

```csv
````

The system message is the following single line without a trailing newline. Its SHA-256 is `32f4d96e0a6cc6964eeb20b56ba6c8b35188c88a6bca14a1d126b2ace571a0e9`.

```text
Use only the five available ProofFlow tools to complete the user's report task. Numeric answers must come from actual connector results. Keep immutable selections from the tool outputs and withhold any claim whose current value is null. Only the explicit request to check the previous export may fail. Stop if any other tool fails. Do not repeat an action or try to bypass an error. The final response should be concise.
```

</details>

The public record contains the audit verdict, test inputs and evidence digests. The underlying provider stream, guard ledger, launcher settings and session details remain private. The pinned inputs support reconstruction of the test setup. A new model run can produce different actions or costs.
