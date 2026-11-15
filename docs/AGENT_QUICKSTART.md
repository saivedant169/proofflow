# Use ProofFlow from a local agent

For guided revenue reports through the public demo, use the downloadable CSV connector. It supports rate-only corrections using the last CSV confirmed in the same process and inspection of the recorded evidence behind a selected artifact. [Hosted connector setup](https://proofflow.arnavbule.in/agent/).

## Six hosted CSV tools

The hosted connector creates the same two fixed revenue reports as the browser. Its six tools are `create_csv_reports`, `inspect_reports`, `inspect_evidence`, `update_csv`, `refresh_reports` and `export_current_reports`. This connector is separate from the local typed planner below.

When an exchange-rate or refund correction withholds a report, call `inspect_evidence` with the `generation` returned by report inspection and the saved report or claim `artifact_id`. It returns the selected artifact's currentness, immutable identity and content fingerprint, its producing receipt's identity and fingerprint, the producing tool, typed input identities, and native dependency paths from recorded changed sources. Follow an input of kind `artifact` with another call to inspect its execution. Source inputs and the receipt's tool-version ID identify consumed versions; this tool does not open their contents.

```json
{
  "generation": "<observed workspace generation>",
  "artifact_id": "<observed report, claim, or artifact input ID>"
}
```

Keep a prior report ID to explain why that saved version became stale, even after a refresh creates its replacement. To inspect retained work, compare the artifact and producing receipt identities for the same unaffected calculation before and after a correction. Recorded changed sources accumulate across corrections; a returned path is not a claim that its source changed in the latest edit. The response includes at most three paths per recorded source, with a maximum depth of 15. An empty path list does not establish currentness; use the explicit artifact state.

`inspect_evidence` is read-only. It returns provenance without saved values, CSV rows, source contents, tool parameters, cookies or session credentials. Use `inspect_reports` for current amounts and `export_current_reports` for a server-checked snapshot. The selected generation must still be the connector's active imported workspace; replacing that workspace or starting a new connector process does not grant access to earlier workspaces.

The recorded [V2 guided model trial](HOSTED_CONNECTOR_MODEL_V2_RESULTS.md) used the earlier **five-tool** connector and completed seven prescribed stages. It did not exercise `inspect_evidence`. Its results and the earlier V1 partial result remain separate from the new inspection capability.

## Local typed planning setup

The stdio MCP server lets a host choose analytics plans over its own CSV data. ProofFlow executes the registered tools, records their consumed inputs in HydraDB, and checks whether saved results are still current. When a model is used, it runs in your MCP host; this server invokes no model and makes no paid model calls.

From the repository root, start the local HydraDB service and install the optional MCP dependency, pinned to `mcp==2.3.0`:

```sh
python3 scripts/init_local.py
docker compose up -d
uv sync --frozen --extra mcp
.venv/bin/python -m proofflow.mcp_server
```

The last command starts a stdio server and waits for a client. Normally the host starts that process. Adapt this generic host configuration, replacing every `/absolute/path/to/proofflow` with your checkout's absolute path:

```json
{
  "mcpServers": {
    "proofflow": {
      "command": "/absolute/path/to/proofflow/.venv/bin/python",
      "args": ["-m", "proofflow.mcp_server"],
      "env": {
        "PROOFFLOW_MCP_STATE_DIR": "/absolute/path/to/proofflow/.state/mcp",
        "PROOFFLOW_HYDRA_URL": "http://127.0.0.1:18443",
        "PROOFFLOW_HYDRA_TOKEN_FILE": "/absolute/path/to/proofflow/.state/hydra-token"
      }
    }
  }
}
```

The token file is created by local initialization; do not paste its contents into prompts or configuration examples. The existing checkout `.env` is also supported by the Hydra adapter. `PROOFFLOW_MCP_STATE_DIR` is optional and defaults to `.state/mcp` relative to the server's working directory; an absolute path keeps persistence predictable when a host launches the process elsewhere.

## Five local planning tools

| Tool | Input | Result |
|---|---|---|
| `load_csv` | `workspace`, `csv_text`, optional `rates` and `region` | Publishes source versions and returns actual affected artifact IDs. Does not create or refresh preset reports. |
| `prepare` | `workspace`, `task` | Returns current typed handles, tool contracts, plan schema, and a snapshot token. |
| `execute_plan` | `workspace`, `snapshot_token`, `plan`, `run_id` | Validates the host's plan and immutable bindings, then returns calculated claims, steps, and actual tool calls. |
| `inspect` | `workspace`, optional `artifact_ids` | Returns source versions, artifact currentness, values, and execution receipts. Omit IDs to inspect artifact heads. |
| `refresh` | `workspace`, `artifact_ids` | Recomputes affected prerequisites, rebinds downstream inputs, and returns replacement IDs and actual tool calls. |

A workspace name contains 1–48 lowercase letters, digits, or hyphens, starting with a letter or digit. Tool arguments never accept filesystem paths, credentials, arbitrary code, SQL, or new tool implementations. Workspaces use separate persistent stores and Hydra namespaces. They are not an authorization boundary between untrusted clients.

## Try your own data

Call `load_csv` with this small authored example, or replace the rows with your own:

```json
{
  "workspace": "my-orders",
  "csv_text": "order_id,region,currency,gross_cents,refund_cents,ticket_count\na,NORTH,EUR,10000,1000,3\nb,SOUTH,USD,20000,0,1\n",
  "rates": {"EUR": "1.20"},
  "region": "NORTH"
}
```

Required columns are `order_id,region,currency,gross_cents`; optional columns are `refund_cents,ticket_count`. Money is integer cents. USD, EUR, and GBP are supported, with explicit USD exchange rates for EUR and GBP. A region must use one currency. Imports are bounded to 1 MiB and 1,000 order rows; ticket counts expand into at most 10,000 synthetic counting rows, not original ticket records.

Then ask your host to:

1. Call `prepare` for a company net-revenue report with NORTH support workload. Choose a plan from the returned schema and submit it through `execute_plan`.
2. Prepare a second request for a NORTH revenue brief. Reuse suitable current artifacts from the first run, then execute the new report plan.
3. Call `load_csv` again with the same rows and EUR rate `1.30`. Inspect both saved reports before refreshing them.
4. Refresh the affected report IDs and inspect the returned replacement IDs and call receipts.

All numeric claims come from seven registered tools: regional gross revenue, refunds, net revenue, USD conversion, company total, support counts, and report composition. The host chooses their arrangement; report sections select supported USD-cent or ticket-count fields instead of supplying numeric constants. A second report can consume artifacts produced in an earlier run, so corrections propagate across those recorded dependencies.

Support claims currently require a region with actual ticket rows. `prepare` lists `supported_ticket_regions`; the seven-tool catalog cannot select a missing zero-count region. Such a support claim is rejected before publishing any tool outputs. Revenue reports still support rows whose ticket count is zero or omitted.

`value` is withheld when an artifact or claim is stale or unknown. `saved_value` is explicitly historical and must not be presented as current. Refresh reports actual tool executions; an unchanged reusable artifact retains its identity. Missing required evidence or an unavailable HydraDB produces an error rather than a fallback answer.

Execution counters count recorded runtime tool calls. Each **MCP `load_csv`** performs eight arithmetic preflight checks, reported separately as `preflight_calculation_count`; these publish no artifacts or execution receipts. MCP loading does not automatically perform report-recipe verification. A reordered equivalent CSV can therefore require zero recorded recomputation calls while still performing parsing and validation. The `planner.model_calls: 0` field describes this server only: the host may call its own model, whose identity, usage and cost are not verified by ProofFlow and must be recorded separately.

**Route-specific accounting correction:** earlier wording generalized these eight MCP preflight calculations to the CSV CLI. A successful two-report CLI invocation already performed **16 preflight calculations** (parse eight + public import eight) and **11 verification calculations**, in addition to its recorded runtime calls; its explicit counters now report that work. This does not change MCP `load_csv` or its saved two-load total of **16 preflight calculations**. Original raw evidence and benchmark results remain unchanged. Zero recorded refresh calls does not mean zero arithmetic validation or verification.

Plans contain at most 12 steps. Snapshot tokens expire after ten minutes, with at most 32 pending snapshots per workspace; consumed or stale snapshots require a new `prepare` call. Explicit artifact selections are limited to 16 distinct IDs. Source heads are individually durable: loading several source versions is not a distributed transaction, and a database failure must not be reported as a successful load.

## Try the same schema in the browser

For a guided calculation without an agent host, open the local app and select **Use your data**. Choose a UTF-8 CSV or paste its complete contents, supply EUR/GBP→USD rates if used, choose a region, then **Validate CSV → Create reports**. The preview does not persist a workspace. Creation saves two revenue reports: company total and the selected region. This browser route uses fixed recipes and no live model; the MCP host continues to choose its own typed plans.

**Update CSV → Validate CSV → Publish correction** changes source versions without recomputing reports. Inspect the stale values, then use **Refresh affected** and **Check values**. The guided demo and imported workspace stay independent. The selected region is fixed for an existing import; start another import to change it. After reload, resupply the complete CSV for an update; saved values and rates persist, but raw CSV text is not restored into the form. CSV data goes to the ProofFlow server; it is not sent to a model by this browser flow.

The browser uses the same bounded schema: at most 1 MiB, 1,000 rows and 10,000 expanded ticket counts; USD/EUR/GBP only; one currency per region; integer cents; caller-supplied rates. Revenue-only reports work for a zero-ticket region without fabricating a support claim. This does not remove the MCP tool catalog's documented restriction on explicitly selecting an absent support region.

One successful preview plus create performs **8 preview preflight + 8 create preflight + 8 recorded + 11 verification = 35 calculations**. The create operation itself reports 27. Browser updates perform eight preflight calculations; refresh adds its actual recorded calls plus eleven verification calculations. Each optional preview is separate. CLI remains sixteen preflight plus eleven verification plus recorded calls; MCP `load_csv` remains eight preflight per load. [Browser verification and screenshots](UI_FIDELITY.md#browser-csv-import-verification) document the interactive checks against Docker revision `a2eb61b`; these are functional cases, not a model benchmark.

## Evidence and verification status

The [stock-client process check](../results/mcp-v1/summary.json) passed **20 checks** through a separate stdio process. It verifies the five tools, caller-supplied composition, reuse, changed-source refresh, restart persistence, stale-plan refusal and unavailable-Hydra errors. It makes no model calls and does not demonstrate a model discovering its own plan.

The actual **Fable 5.2/high Claude Code client** demonstration is a separate experiment. Its corrected frozen trajectory passes **32 recorded checks**, with **9 MCP requests across 10 CLI turns**. The client loads the supplied two-row CSV, chooses two report plans, reuses earlier artifacts, corrects the FX input, inspects stale claims, refreshes both reports and inspects the current replacements. Recorded runtime calls are **7 initial + 1 composition + 4 refresh = 12**; the two CSV loads perform **16 additional arithmetic preflight checks**.

The [first attempt](../results/mcp-agent-v1/README.md) remains a **configuration failure**: `--safe-mode` suppressed the explicitly configured server, the model saw no tools, and zero ProofFlow tools ran. The corrected frozen attempt repairs launch configuration and keeps the same task, apart from a fresh workspace nonce. Across both paid attempts, provider list accounting totals **$0.847042** ($0.809898 corrected and $0.037144 failed). There was no automatic retry or fallback inside either attempt. This is one authored two-row integration, not a general agent benchmark or a subscription billing statement.

[Actual-client results and transcript audit](MCP_AGENT_RESULTS.md) preserve plans, receipts, provider usage and the failed attempt. The original [model composition experiment](COMPOSITION.md) used a different local bridge and is not substituted for this MCP verification. The server's zero model calls does not describe the external Claude client's model usage.

The [retail benchmark](RETAIL_V2_RESULTS.md) separately tests dependency retrieval and refresh with a deterministic reader: 38/38 recoverable affected reports and 4/4 unavailable reports blocked on the complete path, using 69.41% fewer evidence tokens than full context. It is not an MCP model benchmark. All arms share the same Hydra-assisted executor, exact-flat ties graph, and its fixed 2,048-token condition completes only 8/38 for graph. Keep those distinctions when presenting this integration.

## Reproduce the stock-client check

With HydraDB running, the stock-client smoke test launches the stdio server as a separate process and exercises tool discovery, source loading, caller-supplied plans, cross-run reuse, correction, stale-value withholding, refresh, and persistence:

```sh
uv run python scripts/mcp_smoke.py --output results/mcp-reproduction
```

Use a new output directory for each recording. This check makes no model calls: it verifies MCP interoperability and actual runtime behavior, not autonomous model planning or compatibility with every host. The separate [recorded model composition experiment](COMPOSITION.md) documents its own model, inputs, costs, and limitations.

This interface is for a trusted local host on one machine and currently uses POSIX file locking on macOS or Linux. It provides no public HTTP endpoint or shared-client authentication. Keep Hydra credentials local, and consider the host's model/data-sharing settings separately from the server's behavior.

The source repository remains private. The hosted CSV connector is documented separately above; this local stdio interface does not require a hosted app.
