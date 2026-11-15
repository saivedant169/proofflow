"""One frozen Claude Code MCP-client integration attempt, with independent audit.

The client model chooses its plans from the server's discovered contracts. The
prompt contains source data and requested claims, never a tool recipe or expected
answers. Gold arithmetic appears only in the post-run read-only verifier. This
is a narrow integration demonstration, not an agent-performance benchmark.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-fable-5-2"
TOOLS = tuple(f"mcp__proofflow__{name}" for name in ("load_csv", "prepare", "execute_plan", "inspect", "refresh"))
CSV = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
       "a,NORTH,EUR,10000,1000,3\n"
       "b,SOUTH,USD,20000,0,1\n")
SYSTEM = """You are an analytics client using only the five explicitly available ProofFlow MCP tools.
Choose your own typed plans from contracts and handles returned by prepare. Do not
invent tools, IDs, numeric answers, data, paths, or executable code. Calculations
must come from server tools. Prefer suitable existing artifacts when asked to reuse
them. Inspect currentness before claiming a saved result is current. Historical
saved_value fields are not current claims. If any tool fails, stop and report that
failure; do not retry, switch tools to bypass it, or fabricate a successful outcome.
Keep your final response concise. Do not request any external tools or services.
"""


def prompt(workspace: str) -> str:
    return f"""Use workspace {workspace} for this entire task.

Load this CSV with the explicitly supplied EUR-to-USD rate 1.20 and selected region NORTH:
{CSV}
Create a company report containing total company net revenue in USD cents, NORTH
net revenue in USD cents, and NORTH support ticket count. Obtain the current typed
contracts with prepare, choose the calculation plan yourself, then execute it.

Next create a separate NORTH operations brief with NORTH net revenue in USD cents,
company net revenue as context, and NORTH support ticket count. Prepare again and
reuse suitable artifacts from the earlier run instead of recomputing them. Use
distinct run IDs for the two report compositions. Keep both saved report IDs.

Now load the exact same CSV again, changing only the EUR-to-USD rate to 1.30.
Inspect both original saved report IDs before refreshing and describe which numeric
claims remain current. Refresh both reports together, then inspect both replacement
report IDs to verify their currentness and tool-computed values. Do not load any
other data or change any other sources. Finish with a concise account of the two
reports, reuse, correction, and any failure. No expected answers or route is supplied.
"""


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def git_state() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"revision": git("rev-parse", "HEAD"),
            "tracked_changes": bool(git("status", "--porcelain", "--untracked-files=no"))}


def code_hashes() -> dict[str, str]:
    files = sorted((ROOT / "proofflow").glob("**/*.py"))
    files += [ROOT / "scripts/mcp_agent_probe.py", ROOT / "pyproject.toml", ROOT / "uv.lock"]
    return {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in files if path.is_file()}


def prepare(output: Path) -> dict[str, Any]:
    state = git_state()
    if state["tracked_changes"]:
        raise ValueError("Commit the reviewed MCP server and probe before freezing this attempt")
    # Untracked Python must not masquerade as a committed probe.
    subprocess.run(["git", "ls-files", "--error-unmatch", "scripts/mcp_agent_probe.py"],
                   cwd=ROOT, check=True, capture_output=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    nonce = uuid.uuid4().hex[:12]
    workspace = "client-" + nonce
    state_dir = ROOT / ".state" / ("mcp-agent-" + nonce)
    if state_dir.exists():
        raise ValueError("Probe state must be new; no seeded artifacts are allowed")
    token_file = ROOT / ".state/hydra-token"
    if not token_file.is_file():
        raise ValueError("Hydra token file is missing; contents are never copied into probe artifacts")
    server_env = {"PROOFFLOW_HYDRA_URL": "http://127.0.0.1:18443",
                  "PROOFFLOW_HYDRA_TOKEN_FILE": str(token_file),
                  "PROOFFLOW_MCP_STATE_DIR": str(state_dir)}
    config = {"mcpServers": {"proofflow": {"command": str(ROOT / ".venv/bin/python"),
               "args": ["-m", "proofflow.mcp_server"], "env": server_env}}}
    write_json(output / "mcp-config.json", config)
    (output / "prompt.txt").write_text(prompt(workspace))
    (output / "system-prompt.txt").write_text(SYSTEM)
    frozen = {"version": "mcp-agent-integration-v1", "code": state, "code_sha256": code_hashes(),
              "workspace": workspace, "state_dir": str(state_dir), "server_env": server_env,
              "model": MODEL, "effort": "high", "timeout_seconds": 600, "max_budget_usd": 4.0,
              "allowed_tools": list(TOOLS), "client_attempts": 1, "retries": 0, "fallback": False,
              "prepared_at": datetime.now(timezone.utc).isoformat(),
              "artifact_sha256": {name: sha((output / name).read_bytes()) for name in
                                   ("prompt.txt", "system-prompt.txt", "mcp-config.json")},
              "scope": "Single client-model integration demonstration over authored CSV; not a performance benchmark",
              "oracle_boundary": "Known arithmetic and required outcomes exist only in the post-run verifier, never in the prompt",
              "server_model_calls": 0}
    write_json(output / "prepared.json", frozen)
    return frozen


def command(directory: Path) -> list[str]:
    return ["claude", "-p", "--model", MODEL, "--effort", "high", "--safe-mode", "--tools", "",
            "--strict-mcp-config", "--mcp-config", str(directory / "mcp-config.json"),
            "--allowedTools", ",".join(TOOLS), "--permission-mode", "dontAsk",
            "--disable-slash-commands", "--no-session-persistence", "--no-chrome",
            "--output-format", "stream-json", "--verbose", "--max-budget-usd", "4",
            "--system-prompt", SYSTEM]


def decoded_body(value: Any) -> dict[str, Any] | None:
    """Decode explicit MCP JSON envelopes without extracting JSON from prose."""
    if isinstance(value, str):
        try:
            return decoded_body(json.loads(value))
        except (json.JSONDecodeError, RecursionError):
            return None
    if isinstance(value, list):
        for item in value:
            result = decoded_body(item)
            if result is not None:
                return result
    if isinstance(value, dict):
        if "workspace" in value and any(key in value for key in
                ("source_versions", "snapshot_token", "report_id", "artifacts", "planner")):
            return value
        for key in ("structuredContent", "structured_content", "content", "text"):
            if key in value:
                result = decoded_body(value[key])
                if result is not None:
                    return result
    return None


def parse_events(path: Path) -> dict[str, Any]:
    events, malformed, requests, responses = [], [], [], {}
    for index, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed.append({"line": index, "sha256": sha(line)})
            continue
        events.append(event)
        message = event.get("message", {}) if isinstance(event, dict) else {}
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []) if isinstance(message.get("content"), list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                requests.append({"id": block["id"], "name": block["name"], "input": block.get("input"),
                                 "event_index": len(events) - 1})
            elif block.get("type") == "tool_result":
                responses[block["tool_use_id"]] = {"is_error": bool(block.get("is_error")),
                    "body": decoded_body(block.get("content")), "raw": block,
                    "event_index": len(events) - 1}
    calls = [{**request, "response": responses.get(request["id"])} for request in requests]
    finals = [event for event in events if isinstance(event, dict) and event.get("type") == "result"]
    return {"event_count": len(events), "malformed_lines": malformed, "calls": calls,
            "final": finals[-1] if finals else None,
            "initialization": [event for event in events if isinstance(event, dict)
                               and event.get("type") == "system" and event.get("subtype") == "init"]}


def metric_values(claims: list[dict[str, Any]], *, historical: bool = False) -> dict[str, Any]:
    paths = {("usd_cents",): "company_usd_cents", ("regions", "NORTH", "usd_cents"): "north_usd_cents",
             ("regions", "NORTH", "tickets"): "north_tickets"}
    result = {}
    for claim in claims:
        key = paths.get(tuple(claim.get("path", [])))
        if key:
            if key in result:
                raise ValueError("Duplicate semantic claim in a report")
            result[key] = claim.get("saved_value" if historical else "value")
    return result


def csv_rows(text: Any) -> list[tuple[Any, ...]] | None:
    """Normalize serialization only; perform no tool calculations or writes."""
    fields = ("order_id", "region", "currency", "gross_cents", "refund_cents", "ticket_count")
    if not isinstance(text, str):
        return None
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None or len(reader.fieldnames) != len(fields) or set(reader.fieldnames) != set(fields):
            return None
        result = []
        for row in reader:
            if set(row) != set(fields) or any(value is None for value in row.values()):
                return None
            result.append(tuple(row[key].strip() if index < 3 else int(row[key].strip())
                                for index, key in enumerate(fields)))
        return sorted(result)
    except (ValueError, TypeError, csv.Error):
        return None


def rate_matches(rates: Any, expected_eur: str) -> bool:
    if not isinstance(rates, dict) or "EUR" not in rates or not set(rates) <= {"EUR", "USD"}:
        return False
    try:
        euro = Decimal(str(rates["EUR"]))
        usd = Decimal(str(rates.get("USD", "1")))
        return euro.is_finite() and usd.is_finite() and euro == Decimal(expected_eur) and usd == Decimal("1")
    except (InvalidOperation, ValueError):
        return False


def audit_state(frozen: dict[str, Any], transcript: dict[str, Any]) -> dict[str, Any]:
    """Read actual persisted state and native impact; never seed or repair it."""
    from proofflow.graph import HydraGraph
    from proofflow.mcp_server import ProofFlowMCP

    server_env = frozen["server_env"]
    os.environ.pop("PROOFFLOW_HYDRA_TOKEN", None)
    os.environ.update(server_env)
    facade = ProofFlowMCP(frozen["state_dir"])
    calls = transcript["calls"]
    successful = [call for call in calls if call.get("response") and not call["response"]["is_error"]
                  and call["response"]["body"] is not None]
    by_tool = lambda name: [call for call in successful if call["name"] == f"mcp__proofflow__{name}"]
    compositions, loads, refreshes, inspections = (by_tool(name) for name in ("execute_plan", "load_csv", "refresh", "inspect"))
    checks = {"only_five_allowed_client_tools": bool(calls) and all(call["name"] in TOOLS for call in calls),
              "all_tool_results_present_and_successful": len(successful) == len(calls),
              "one_workspace": all(call.get("input", {}).get("workspace") == frozen["workspace"] for call in calls),
              "two_client_chosen_compositions": len(compositions) == 2,
              "two_csv_loads": len(loads) == 2,
              "one_refresh_request": len(refreshes) == 1,
              "server_model_calls_zero": all(call["response"]["body"].get("planner", {}).get("model_calls") == 0 for call in compositions)}
    if len(compositions) != 2 or len(loads) != 2 or len(refreshes) != 1:
        return {"checks": checks, "passed": False, "error": "Expected task stages were not completed; state was not repaired"}
    originals = [call["response"]["body"]["report_id"] for call in compositions]
    run_ids = [call["input"].get("run_id") for call in compositions]
    checks["distinct_client_composition_runs"] = all(isinstance(value, str) and value.strip() for value in run_ids) and len(set(run_ids)) == 2
    initial = {"company_usd_cents": 30800, "north_usd_cents": 10800, "north_tickets": 3}
    updated = {"company_usd_cents": 31700, "north_usd_cents": 11700, "north_tickets": 3}
    checks["initial_tool_computed_values"] = all(metric_values(call["response"]["body"]["claims"]) == initial for call in compositions)
    checks["client_supplied_only_requested_csv_and_rates"] = (
        all(csv_rows(call["input"].get("csv_text")) == csv_rows(CSV)
            and call["response"]["body"].get("selected_region") == "NORTH" for call in loads)
        and all(rate_matches(call["input"].get("rates"), rate) for call, rate in zip(loads, ("1.20", "1.30"), strict=True)))
    checks["load_did_not_create_preset_reports"] = all(call["response"]["body"].get("executed_count") == 0 for call in loads)
    first_steps = compositions[0]["response"]["body"].get("steps", [])
    second = compositions[1]["response"]["body"]
    first_ids = {step["artifact_id"] for step in first_steps}
    checks["new_brief_reuses_earlier_artifacts"] = (
        second.get("executed_count") == 1 and len(second.get("steps", [])) == 1
        and bool(second["steps"][0]["inputs"])
        and set(second["steps"][0]["inputs"].values()) <= first_ids)
    changed = loads[1]["response"]["body"]
    checks["both_reports_in_native_change_response"] = set(originals) <= set(changed.get("affected_artifact_ids", []))
    checks["native_change_query_used"] = changed.get("hydra_queries", 0) > 0
    refresh = refreshes[0]
    checks["both_original_reports_selected_for_refresh"] = set(refresh["input"].get("artifact_ids", [])) == set(originals)
    stale_inspections = [call for call in inspections if loads[1]["event_index"] < call["event_index"] < refresh["event_index"]]
    stale_artifacts = [artifact for call in stale_inspections for artifact in call["response"]["body"].get("artifacts", [])]
    checks["client_inspected_stale_claims_before_refresh"] = set(originals) <= {row["id"] for row in stale_artifacts} and all(
        row["state"] == "stale" and row["value"] is None
        and metric_values(row["claims"]) == {"company_usd_cents": None, "north_usd_cents": None, "north_tickets": 3}
        for row in stale_artifacts if row["id"] in originals)
    refreshed = refresh["response"]["body"]
    replacements = refreshed.get("result", {}).get("replacements", {})
    new_ids = [replacements[key] for key in originals if key in replacements]
    checks["two_distinct_replacements"] = len(new_ids) == 2 and len(set(new_ids)) == 2 and not set(new_ids) & set(originals)
    final_inspections = [call for call in inspections if call["event_index"] > refresh["event_index"]]
    final_artifacts = [artifact for call in final_inspections for artifact in call["response"]["body"].get("artifacts", [])]
    checks["client_inspected_current_replacements"] = set(new_ids) <= {row["id"] for row in final_artifacts} and all(
        row["state"] == "current" and metric_values(row["claims"]) == updated
        for row in final_artifacts if row["id"] in new_ids)
    # New graph clients read durable state after the model and MCP process exit.
    original_state = facade.inspect(frozen["workspace"], originals)
    final_state = facade.inspect(frozen["workspace"], new_ids) if new_ids else {"artifacts": []}
    checks["independent_original_values_match_oracle"] = all(metric_values(row["claims"], historical=True) == initial for row in original_state["artifacts"])
    checks["independent_replacements_current_and_correct"] = len(final_state["artifacts"]) == 2 and all(
        row["state"] == "current" and metric_values(row["claims"]) == updated for row in final_state["artifacts"])
    with facade._runtime(frozen["workspace"]) as (runtime, _):
        native = runtime.affected(changed["changed_source_version_ids"], current_only=False)
        checks["only_fx_source_changed"] = len(changed["changed_source_version_ids"]) == 1 and all(
            runtime.store.get(key).metadata.get("name") == "fx" for key in changed["changed_source_version_ids"])
        native_ids = {record.id for record in native}
        checks["independent_native_impact_matches_change_response"] = native_ids == set(changed["affected_artifact_ids"])
        checks["four_native_affected_artifacts"] = len(native_ids) == 4 and set(originals) <= native_ids
        checks["native_queries_no_fallback"] = isinstance(runtime.graph, HydraGraph) and runtime.graph.queries > 0
        executed = refreshed.get("result", {}).get("executed", [])
        receipts = [runtime.store.read(runtime.store.get(key).metadata["receipt_id"]) for key in executed]
        checks["four_recorded_refresh_calculations"] = len(executed) == 4 and refreshed.get("executed_count") == 4 and len(refreshed.get("tool_calls", [])) == 4
        checks["refresh_preserved_support_artifact"] = all(call.get("tool") != "support_by_region" for call in refreshed.get("tool_calls", []))
    return {"passed": all(checks.values()), "checks": checks, "original_report_ids": originals,
            "refreshed_report_ids": new_ids, "independent_original_inspection": original_state,
            "independent_final_inspection": final_state, "native_affected_ids": sorted(native_ids),
            "independent_refresh_receipts": receipts,
            "recorded_runtime_calls": sum(call["response"]["body"].get("executed_count", 0) for call in successful),
            "csv_preflight_calculations": sum(call["response"]["body"].get("preflight_calculation_count", 0) for call in loads),
            "accounting_scope": "CSV preflight arithmetic is additional compute; recorded runtime counts do not include it"}


def run(directory: Path) -> dict[str, Any]:
    directory = directory.resolve()
    frozen = read_json(directory / "prepared.json")
    if git_state()["tracked_changes"] or frozen["code_sha256"] != code_hashes():
        raise ValueError("Code changed or is uncommitted; this frozen attempt cannot run")
    for name, digest in frozen["artifact_sha256"].items():
        if digest != sha((directory / name).read_bytes()):
            raise ValueError("Frozen prompt or MCP configuration changed")
    if Path(frozen["state_dir"]).exists():
        raise ValueError("Probe state already exists; refusing to reuse any prior data")
    with (directory / "started.json").open("x") as stream:
        json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "code": git_state()}, stream)
    env = dict(os.environ)
    env.pop("PROOFFLOW_HYDRA_TOKEN", None)
    started = time.monotonic()
    error, returncode = None, None
    with (directory / "client-events.jsonl").open("w") as stdout, (directory / "client-stderr.log").open("w") as stderr:
        try:
            process = subprocess.Popen(command(directory), cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                       stdout=stdout, stderr=stderr, text=True, start_new_session=True)
            try:
                process.communicate(input=(directory / "prompt.txt").read_text(), timeout=600)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                error = {"type": "TimeoutExpired", "message": "600 second bound reached; no retry", "usage_may_be_incomplete": True}
            returncode = process.returncode
        except OSError as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
    transcript = parse_events(directory / "client-events.jsonl")
    write_json(directory / "tool-transcript.json", transcript)
    final = transcript["final"] or {}
    model_usage = final.get("modelUsage") or {}
    actual_models = {value.get("canonicalModel", key) for key, value in model_usage.items() if isinstance(value, dict)}
    checks = {"client_process_succeeded": returncode == 0 and error is None,
              "stream_valid": not transcript["malformed_lines"],
              "successful_final_result": bool(final) and not final.get("is_error") and final.get("subtype") == "success",
              "actual_model_exactly_requested": actual_models == {MODEL},
              "model_usage_recorded": bool(model_usage)}
    try:
        audit = audit_state(frozen, transcript)
    except Exception as exc:
        audit = {"passed": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
    write_json(directory / "independent-audit.json", audit)
    summary = {"passed": all(checks.values()) and audit["passed"], "checks": checks,
               "audit_checks": audit.get("checks", {}), "error": error,
               "returncode": returncode, "elapsed_seconds": time.monotonic() - started,
               "client_model": MODEL, "actual_models": sorted(actual_models), "effort": "high",
               "model_usage": model_usage, "usage": final.get("usage"),
               "reported_cost_usd": final.get("total_cost_usd"), "usage_unknown": not bool(model_usage),
               "cli_num_turns": final.get("num_turns"), "client_tool_requests": len(transcript["calls"]),
               "server_model_calls": 0, "recorded_runtime_calls": audit.get("recorded_runtime_calls"),
               "csv_preflight_calculations": audit.get("csv_preflight_calculations"),
               "attempts": 1, "retries": 0, "fallback": False,
               "finished_at": datetime.now(timezone.utc).isoformat(), "code": frozen["code"],
               "scope": frozen["scope"], "accounting_scope": audit.get("accounting_scope"),
               "limitations": ["Authored two-row workflow and one model trajectory; not a general agent benchmark.",
                               "Server model_calls=0 describes the MCP server; the Claude client makes paid model calls.",
                               "Reported cost is provider list accounting, not a subscription billing statement."]}
    write_json(directory / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output) if args.command == "prepare" else run(args.prepared)
    keys = ("workspace", "model", "effort", "timeout_seconds", "max_budget_usd") if args.command == "prepare" else (
        "passed", "actual_models", "reported_cost_usd", "client_tool_requests", "recorded_runtime_calls", "server_model_calls")
    print(json.dumps({key: result.get(key) for key in keys}, indent=2))
    if args.command == "run" and not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
