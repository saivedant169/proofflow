"""Verify ProofFlow through a stock MCP client and separate stdio server process.

No model is called. The client supplies plans and known arithmetic assertions.
Results are an interoperability proof, not an autonomous-planning benchmark.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from mcp import Client
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parents[1]
CSV = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
       "n1,NORTH,EUR,10000,1000,3\n"
       "s1,SOUTH,USD,20000,0,1\n")
REORDERED = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
             "s1,SOUTH,USD,20000,0,1\n"
             "n1,NORTH,EUR,10000,1000,3\n")
WORKSPACE = "external-client"


def step(name, tool, inputs, sections=None, title=None):
    return {"id": name, "tool": tool,
            "inputs": [{"name": key, "ref": value} for key, value in inputs.items()],
            "title": title, "sections": sections or []}


def section(key, input_name, path, unit="USD cents"):
    return {"key": key, "label": key.replace("_", " "), "input": input_name,
            "path": path, "unit": unit}


def plan(steps):
    return {"steps": steps, "output": steps[-1]["id"], "abstain": False,
            "rationale": "External SDK interoperability client selects registered tools and immutable handles."}


def first_plan():
    return plan([
        step("gross", "gross_by_region", {"orders": "source:orders"}),
        step("refunds", "refunds_by_region", {"orders": "source:orders", "refunds": "source:refunds"}),
        step("net", "net_by_region", {"gross": "gross", "refunds": "refunds"}),
        step("usd", "convert_to_usd", {"net": "net", "fx": "source:fx"}),
        step("company", "company_total", {"regional": "usd"}),
        step("support", "support_by_region", {"tickets": "source:tickets"}),
        step("report", "compose_report", {"revenue": "company", "support": "support"}, [
            section("company_revenue", "revenue", ["usd_cents"]),
            section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")],
            "Client company report"),
    ])


def second_plan(prepared):
    handles = {row["producing_tool"]: row["handle"] for row in prepared["request"]["available"]
               if row["kind"] == "artifact"}
    return plan([step("brief", "compose_report", {
        "regional": handles["convert_to_usd"], "company": handles["company_total"],
        "support": handles["support_by_region"]}, [
            section("north_revenue", "regional", ["regions", "NORTH", "usd_cents"]),
            section("company_context", "company", ["usd_cents"]),
            section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")],
        "Client NORTH operations brief")])


def values(claims):
    return {claim["key"]: claim["value"] for claim in claims}


async def run(directory: Path):
    directory.mkdir(parents=True, exist_ok=False)
    state_dir = directory / "state"
    env = dict(os.environ)
    env["PROOFFLOW_MCP_STATE_DIR"] = str(state_dir.resolve())
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "proofflow.mcp_server"],
                                       env=env, cwd=str(ROOT))
    transcript = []
    checks = {}
    started = time.monotonic()
    original_ids = []
    refreshed_ids = []

    async def call(client, tool, arguments, *, expect_error=False):
        result = await client.call_tool(tool, arguments)
        transcript.append({"tool": tool, "arguments": arguments,
                           "result": result.model_dump(mode="json")})
        if expect_error:
            assert result.is_error, f"{tool} unexpectedly accepted invalid input"
            return result
        assert not result.is_error, f"{tool} failed: {result.content}"
        data = result.structured_content
        assert isinstance(data, dict), f"{tool} did not return structured content"
        return data

    error = None
    try:
        async with Client(parameters) as client:
            listed = await client.list_tools()
            transcript.append({"list_tools": listed.model_dump(mode="json")})
            checks["stock_client_discovered_five_tools"] = {tool.name for tool in listed.tools} == {
                "load_csv", "prepare", "execute_plan", "inspect", "refresh"}
            loaded = await call(client, "load_csv", {"workspace": WORKSPACE, "csv_text": CSV,
                                                      "rates": {"EUR": "1.20"}, "region": "NORTH"})
            checks["caller_csv_four_sources_zero_recorded_runtime_calls"] = len(loaded["source_versions"]) == 4 and loaded["executed_count"] == 0 and loaded["preflight_calculation_count"] == 8
            empty = await call(client, "inspect", {"workspace": WORKSPACE})
            checks["no_preset_reports_created"] = empty["artifacts"] == []
            prepared = await call(client, "prepare", {"workspace": WORKSPACE,
                "task": "Create company USD net revenue and NORTH support workload from my CSV."})
            first = await call(client, "execute_plan", {"workspace": WORKSPACE,
                "snapshot_token": prepared["snapshot_token"], "plan": first_plan(), "run_id": "external-A"})
            checks["company_arithmetic_known"] = values(first["claims"]) == {"company_revenue": 30800, "north_support": 3}
            checks["first_plan_seven_actual_tools"] = first["executed_count"] == 7
            prepared = await call(client, "prepare", {"workspace": WORKSPACE,
                "task": "Create a NORTH brief with USD revenue, company context and support count, reusing prior artifacts."})
            second = await call(client, "execute_plan", {"workspace": WORKSPACE,
                "snapshot_token": prepared["snapshot_token"], "plan": second_plan(prepared), "run_id": "external-B"})
            checks["second_request_reuses_prior_run"] = second["executed_count"] == 1 and values(second["claims"]) == {
                "north_revenue": 10800, "company_context": 30800, "north_support": 3}
            original_ids = [first["report_id"], second["report_id"]]
            before = await call(client, "inspect", {"workspace": WORKSPACE})
            support_id = next(row["id"] for row in before["artifacts"] if row["metadata"]["tool"] == "support_by_region")
            stale_snapshot = await call(client, "prepare", {"workspace": WORKSPACE, "task": "Another NORTH brief"})
            stale_plan = second_plan(stale_snapshot)
            changed = await call(client, "load_csv", {"workspace": WORKSPACE, "csv_text": CSV,
                "rates": {"EUR": "1.30"}, "region": "NORTH"})
            checks["fx_change_native_impact_exactly_four"] = len(changed["affected_artifact_ids"]) == 4 and set(original_ids) <= set(changed["affected_artifact_ids"])
            await call(client, "execute_plan", {"workspace": WORKSPACE,
                "snapshot_token": stale_snapshot["snapshot_token"], "plan": stale_plan,
                "run_id": "must-not-execute"}, expect_error=True)
            checks["stale_snapshot_refused"] = True
            stale = await call(client, "inspect", {"workspace": WORKSPACE, "artifact_ids": original_ids})
            checks["stale_values_withheld"] = all(row["state"] == "stale" and row["value"] is None
                and all(claim["value"] is None for claim in row["claims"] if claim["unit"] == "USD cents")
                for row in stale["artifacts"])
            refreshed = await call(client, "refresh", {"workspace": WORKSPACE, "artifact_ids": original_ids})
            refreshed_ids = [row["id"] for row in refreshed["artifacts"]]
            checks["four_actual_refresh_calls"] = refreshed["executed_count"] == 4
            checks["updated_arithmetic_known"] = [values(row["claims"]) for row in refreshed["artifacts"]] == [
                {"company_revenue": 31700, "north_support": 3},
                {"north_revenue": 11700, "company_context": 31700, "north_support": 3}]
            after = await call(client, "inspect", {"workspace": WORKSPACE})
            checks["support_reused_unchanged"] = any(row["id"] == support_id for row in after["artifacts"]) and all(
                call["tool"] != "support_by_region" for call in refreshed["tool_calls"])
            repeated = await call(client, "refresh", {"workspace": WORKSPACE, "artifact_ids": original_ids})
            checks["original_handles_repeat_zero_calls"] = repeated["executed_count"] == 0
            reordered = await call(client, "load_csv", {"workspace": WORKSPACE, "csv_text": REORDERED,
                "rates": {"EUR": "1.30"}, "region": "NORTH"})
            checks["reordered_csv_zero_changes"] = reordered["changed_source_version_ids"] == [] and reordered["affected_artifact_ids"] == []
            unchanged = await call(client, "refresh", {"workspace": WORKSPACE, "artifact_ids": original_ids})
            checks["reordered_csv_zero_calls"] = unchanged["executed_count"] == 0
            await call(client, "inspect", {"workspace": "../outside"}, expect_error=True)
            checks["filesystem_path_refused"] = True
            await call(client, "inspect", {"workspace": WORKSPACE, "artifact_ids": ["unknown-foreign-id"]}, expect_error=True)
            checks["unknown_handles_refused"] = True
        # New server process: neither request objects nor graph clients survive.
        async with Client(parameters) as restarted:
            reopened = await call(restarted, "inspect", {"workspace": WORKSPACE, "artifact_ids": refreshed_ids})
            checks["restarted_server_reads_durable_current_reports"] = all(row["state"] == "current" for row in reopened["artifacts"])
            prepared = await call(restarted, "prepare", {"workspace": WORKSPACE, "task": "Invalid tool check"})
            invalid = second_plan(prepared)
            invalid["steps"][0]["tool"] = "run_shell"
            await call(restarted, "execute_plan", {"workspace": WORKSPACE,
                "snapshot_token": prepared["snapshot_token"], "plan": invalid, "run_id": "invalid"}, expect_error=True)
            checks["unregistered_operation_refused"] = True
        outage_env = {**env, "PROOFFLOW_HYDRA_URL": "http://127.0.0.1:9"}
        outage = StdioServerParameters(command=sys.executable, args=["-m", "proofflow.mcp_server"],
                                      env=outage_env, cwd=str(ROOT))
        async with Client(outage) as unavailable:
            refused = await call(unavailable, "inspect", {"workspace": WORKSPACE, "artifact_ids": refreshed_ids}, expect_error=True)
            checks["hydra_failure_has_no_answer"] = refused.structured_content is None and any(
                "no fallback" in getattr(block, "text", "") for block in refused.content)
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    summary = {"passed": error is None and bool(checks) and all(checks.values()), "checks": checks,
               "error": error, "model_calls": 0, "transport": "stdio", "sdk": "mcp==2.3.0",
               "client_boundary": "Official SDK Client launches separate ProofFlow server processes; no direct server imports",
               "elapsed_seconds": time.monotonic() - started, "finished_at": datetime.now(timezone.utc).isoformat(),
               "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                               for name in ["proofflow/mcp_server.py", "scripts/mcp_smoke.py"]},
               "scope": "Caller-supplied CSV and client-supplied plans; proves interoperability and execution, not autonomous planning"}
    successful = [row["result"]["structured_content"] for row in transcript
                  if "result" in row and row["result"].get("structured_content") is not None]
    summary["csv_preflight_calculations"] = sum(row.get("preflight_calculation_count", 0) for row in successful)
    summary["recorded_runtime_tool_calls"] = sum(row.get("executed_count", 0) for row in successful)
    summary["accounting_scope"] = "Every CSV load performs eight unrecorded preflight tool calculations. The correction cycle uses 8 preflight + 4 recorded refresh calls; equivalent-row reorder uses 8 preflight + 0 recorded refresh calls. No zero-total-compute claim."
    (directory / "transcript.json").write_text(json.dumps(transcript, indent=2, allow_nan=False))
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    print(json.dumps(summary, indent=2))
    return summary["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New local evidence directory; never overwritten")
    args = parser.parse_args()
    if not asyncio.run(run(args.output.resolve())):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
