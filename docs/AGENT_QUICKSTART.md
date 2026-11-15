# Use ProofFlow from a local agent

The stdio MCP server lets a host choose analytics plans over its own CSV data. ProofFlow executes the registered tools, records their consumed inputs in HydraDB, and checks whether saved results are still current. When a model is used, it runs in your MCP host; this server invokes no model and makes no paid model calls.

From the repository root, start the local HydraDB service and install the optional MCP dependency, pinned to `mcp==2.3.0`:

```sh
python3 scripts/init_local.py
docker compose up -d
uv sync --extra mcp
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

## Five tools

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

Execution counters count recorded runtime tool calls. Every CSV load also performs eight arithmetic preflight checks, reported separately as `preflight_calculation_count`; these publish no artifacts or execution receipts. A reordered equivalent CSV can therefore require zero recorded recomputation calls while still performing parsing and validation. The `planner.model_calls: 0` field describes this server only: the host may call its own model, whose identity, usage and cost are not verified by ProofFlow and must be recorded separately.

Plans contain at most 12 steps. Snapshot tokens expire after ten minutes, with at most 32 pending snapshots per workspace; consumed or stale snapshots require a new `prepare` call. Explicit artifact selections are limited to 16 distinct IDs. Source heads are individually durable: loading several source versions is not a distributed transaction, and a database failure must not be reported as a successful load.

## Verify the external interface

With HydraDB running, the stock-client smoke test launches the stdio server as a separate process and exercises tool discovery, source loading, caller-supplied plans, cross-run reuse, correction, stale-value withholding, refresh, and persistence:

```sh
uv run python scripts/mcp_smoke.py --output results/mcp-reproduction
```

Use a new output directory for each recording. This check makes no model calls: it verifies MCP interoperability and actual runtime behavior, not autonomous model planning or compatibility with every host. The separate [recorded model composition experiment](COMPOSITION.md) documents its own model, inputs, costs, and limitations.

This interface is for a trusted local host on one machine and currently uses POSIX file locking on macOS or Linux. It provides no public HTTP endpoint or shared-client authentication. Keep Hydra credentials local, and consider the host's model/data-sharing settings separately from the server's behavior.
