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
import queue
import signal
import subprocess
import threading
import time
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL = "claude-fable-5-2"
TOOLS = tuple(f"mcp__proofflow__{name}" for name in ("load_csv", "prepare", "execute_plan", "inspect", "refresh"))
ISOLATION_SETTINGS = {"disableAllHooks": True, "claudeMdExcludes": ["**"],
                      "autoMemoryEnabled": False, "syncClaudeAiPlugins": False,
                      "syncClaudeAiSkills": False, "disableWorkflows": True}
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


def isolation_settings() -> dict[str, Any]:
    # Plugin registry metadata only; never read authentication files. Keep
    # plugin identifiers in the local run settings, not the published summary.
    registry = Path.home() / ".claude/plugins/installed_plugins.json"
    installed = read_json(registry).get("plugins", {}) if registry.is_file() else {}
    return {**ISOLATION_SETTINGS, "enabledPlugins": {
        name: False for name in installed if isinstance(name, str) and not name.endswith("@builtin")}}


def client_environment() -> dict[str, str]:
    env = dict(os.environ)
    # Safe mode suppresses even explicitly configured MCP. SIMPLE/bare also
    # suppresses OAuth/keychain auth. Restricted mode and explicit settings
    # provide the intended isolation while preserving managed policy.
    for key in ("CLAUDE_CODE_SAFE_MODE", "CLAUDE_CODE_SIMPLE", "PROOFFLOW_HYDRA_TOKEN"):
        env.pop(key, None)
    return env


def private_directory(directory: Path) -> Path:
    key = read_json(directory / "prepared.json")["local_config_key"]
    if not isinstance(key, str) or not key.startswith("mcp-agent-config-") or not key.replace("-", "").isalnum():
        raise ValueError("Invalid local configuration key")
    return ROOT / ".state" / key


def server_environment(frozen: dict[str, Any]) -> dict[str, str]:
    return {"PROOFFLOW_HYDRA_URL": "http://127.0.0.1:18443",
            "PROOFFLOW_HYDRA_TOKEN_FILE": str(ROOT / ".state/hydra-token"),
            "PROOFFLOW_MCP_STATE_DIR": str(ROOT / ".state" / frozen["local_state_key"])}


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
    state_key = "mcp-agent-" + nonce
    config_key = "mcp-agent-config-" + nonce
    private = ROOT / ".state" / config_key
    private.mkdir(parents=True, exist_ok=False)
    state_dir = ROOT / ".state" / state_key
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
    write_json(private / "mcp-config.json", config)
    settings = isolation_settings()
    write_json(private / "client-settings.json", settings)
    (output / "prompt.txt").write_text(prompt(workspace))
    (output / "system-prompt.txt").write_text(SYSTEM)
    failed_summary = ROOT / "results/mcp-agent-v1/summary.json"
    prior = read_json(failed_summary) if failed_summary.is_file() else {}
    frozen = {"version": "mcp-agent-integration-v2", "code": state, "code_sha256": code_hashes(),
              "workspace": workspace, "local_config_key": config_key, "local_state_key": state_key,
              "server_configuration": {"command": ".venv/bin/python (resolved locally)",
                  "args": ["-m", "proofflow.mcp_server"], "hydra_url": "http://127.0.0.1:18443",
                  "token_file": ".state/hydra-token", "state_directory": ".state/" + state_key},
              "settings_summary": {**ISOLATION_SETTINGS, "local_plugin_disable_count": len(settings["enabledPlugins"]),
                                   "managed_policy": "Preserved; no managed controls bypassed"},
              "model": MODEL, "effort": "high", "timeout_seconds": 600, "max_budget_usd": 4.0,
              "allowed_tools": list(TOOLS), "client_attempts": 1, "retries": 0, "fallback": False,
              "prepared_at": datetime.now(timezone.utc).isoformat(),
              "artifact_sha256": {name: sha((output / name).read_bytes()) for name in
                                   ("prompt.txt", "system-prompt.txt")},
              "private_config_sha256": {name: sha((private / name).read_bytes()) for name in
                                        ("mcp-config.json", "client-settings.json")},
              "infrastructure_correction": {
                  "previous_attempt": "results/mcp-agent-v1", "previous_passed": prior.get("passed"),
                  "previous_reported_cost_usd": prior.get("reported_cost_usd"),
                  "previous_summary_sha256": sha(failed_summary.read_bytes()) if failed_summary.is_file() else None,
                  "reason": "v1 --safe-mode suppressed explicit MCP servers; v2 uses restricted mode and frozen per-run settings",
                  "overall_attempt_number": 2, "task_prompt_changed": False},
              "isolation": "Empty builtin tools; only explicit local MCP; restricted mode; no user/project/local settings; per-run hooks/memory/plugin exclusions. Managed policy remains authoritative.",
              "scope": "Single client-model integration demonstration over authored CSV; not a performance benchmark",
              "oracle_boundary": "Known arithmetic and required outcomes exist only in the post-run verifier, never in the prompt",
              "server_model_calls": 0}
    write_json(output / "prepared.json", frozen)
    preflight(output)
    return frozen


def command(directory: Path) -> list[str]:
    private = private_directory(directory)
    return ["claude", "-p", "--model", MODEL, "--effort", "high", "--restricted", "--tools", "",
            "--setting-sources", "", "--settings", str(private / "client-settings.json"),
            "--strict-mcp-config", "--mcp-config", str(private / "mcp-config.json"),
            "--allowedTools", ",".join(TOOLS), "--permission-mode", "dontAsk",
            "--disable-slash-commands", "--no-session-persistence", "--no-chrome",
            "--output-format", "stream-json", "--verbose", "--max-budget-usd", "4",
            "--system-prompt", SYSTEM]


def preflight(directory: Path) -> dict[str, Any]:
    """Official SDK initialize/mcp_status controls only; send no user message.

    The control framing follows anthropics/claude-agent-sdk-python query.py.
    A separate empty state directory ensures health checks cannot seed the
    actual trajectory. Raw controls stay local; the summary contains no account
    or user-plugin metadata. Managed settings are never modified or bypassed.
    """
    private = private_directory(directory)
    config = read_json(private / "mcp-config.json")
    config["mcpServers"]["proofflow"]["env"]["PROOFFLOW_MCP_STATE_DIR"] = str(private / "preflight-state")
    write_json(private / "preflight-mcp-config.json", config)
    argv = command(directory)
    argv[argv.index("--mcp-config") + 1] = str(private / "preflight-mcp-config.json")
    argv += ["--input-format", "stream-json"]
    events: list[str] = []
    messages: queue.Queue = queue.Queue()
    responses, failure = {}, None
    with (private / "preflight-stderr.log").open("w") as stderr:
        process = subprocess.Popen(argv, cwd=ROOT, env=client_environment(), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=stderr, text=True, start_new_session=True)
        def read() -> None:
            for line in process.stdout:
                events.append(line)
                try:
                    messages.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        deadline = time.monotonic() + 30
        def control(identifier: str, request: dict[str, Any]) -> dict[str, Any]:
            process.stdin.write(json.dumps({"type": "control_request", "request_id": identifier, "request": request}) + "\n")
            process.stdin.flush()
            while time.monotonic() < deadline:
                event = messages.get(timeout=max(.01, deadline - time.monotonic()))
                if isinstance(event, dict) and event.get("type") == "control_response" and event.get("response", {}).get("request_id") == identifier:
                    responses[identifier] = event["response"]
                    return event["response"]
            raise TimeoutError("MCP initialization exceeded 30 seconds")
        servers = []
        try:
            initialized = control("preflight-init", {"subtype": "initialize", "hooks": None, "skills": []})
            if initialized.get("subtype") != "success":
                raise ValueError("CLI control initialization failed")
            for index in range(30):
                status = control(f"preflight-status-{index}", {"subtype": "mcp_status"})
                servers = status.get("response", {}).get("mcpServers", [])
                if servers and all(server.get("status") != "pending" for server in servers):
                    break
                time.sleep(.2)
        except Exception as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            reader.join(timeout=1)
    (private / "preflight-control-events.jsonl").write_text("".join(events))
    curated = [{"name": server.get("name"), "status": server.get("status"),
                "tools": sorted(tool["name"] for tool in server.get("tools", []))} for server in servers]
    passed = (failure is None and len(curated) == 1 and curated[0]["name"] == "proofflow"
              and curated[0]["status"] == "connected"
              and set(curated[0]["tools"]) == {tool.removeprefix("mcp__proofflow__") for tool in TOOLS})
    result = {"passed": passed, "servers": curated, "error": failure,
              "user_messages_sent": 0, "model_queries_sent": 0,
              "client_command_sha256": sha(json.dumps(command(directory))),
              "raw_control_sha256": sha("".join(events)),
              "raw_artifact_location": "Ignored .state local configuration directory; not for submission",
              "source": "https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/query.py",
              "finished_at": datetime.now(timezone.utc).isoformat()}
    write_json(directory / "preflight.json", result)
    if not passed:
        raise ValueError("MCP-only preflight failed; no paid model attempt is permitted")
    return result


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


def submission_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Keep tool/model evidence; exclude unrelated local/account initialization."""
    if event.get("type") in {"assistant", "user"}:
        return {"type": event["type"], "message": event.get("message", {})}
    if event.get("type") == "result":
        keys = ("type", "subtype", "is_error", "duration_ms", "duration_api_ms", "num_turns", "result",
                "total_cost_usd", "usage", "modelUsage", "permission_denials", "stop_reason")
        return {key: event[key] for key in keys if key in event}
    if event.get("type") == "system" and event.get("subtype") == "init":
        keys = ("type", "subtype", "model", "permissionMode", "tools", "claude_code_version")
        return {**{key: event[key] for key in keys if key in event},
                "mcp_servers": [{"name": server.get("name"), "status": server.get("status")}
                                for server in event.get("mcp_servers", [])]}
    return None


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

    server_env = server_environment(frozen)
    os.environ.pop("PROOFFLOW_HYDRA_TOKEN", None)
    os.environ.update(server_env)
    facade = ProofFlowMCP(server_env["PROOFFLOW_MCP_STATE_DIR"])
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
    private = private_directory(directory)
    if git_state()["tracked_changes"] or frozen["code_sha256"] != code_hashes():
        raise ValueError("Code changed or is uncommitted; this frozen attempt cannot run")
    for name, digest in frozen["artifact_sha256"].items():
        if digest != sha((directory / name).read_bytes()):
            raise ValueError("Frozen prompt or MCP configuration changed")
    for name, digest in frozen["private_config_sha256"].items():
        if digest != sha((private / name).read_bytes()):
            raise ValueError("Frozen private client settings or MCP configuration changed")
    connection = read_json(directory / "preflight.json")
    if not connection.get("passed") or connection.get("client_command_sha256") != sha(json.dumps(command(directory))):
        raise ValueError("The exact isolated client command has not passed a no-model MCP preflight")
    if Path(server_environment(frozen)["PROOFFLOW_MCP_STATE_DIR"]).exists():
        raise ValueError("Probe state already exists; refusing to reuse any prior data")
    with (directory / "started.json").open("x") as stream:
        json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "code": git_state()}, stream)
    env = client_environment()
    started = time.monotonic()
    error, returncode = None, None
    with (private / "client-events.jsonl").open("w") as stdout, (private / "client-stderr.log").open("w") as stderr:
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
    raw_events = private / "client-events.jsonl"
    transcript = parse_events(raw_events)
    write_json(private / "tool-transcript.json", transcript)
    public_transcript = {**transcript, "initialization": [submission_event(event) for event in transcript["initialization"]],
                         "final": submission_event(transcript["final"]) if transcript["final"] else None,
                         "privacy": "Initialization metadata redacted; original tool requests/responses retained; unmodified raw stream stays in ignored .state"}
    write_json(directory / "tool-transcript.json", public_transcript)
    submitted = []
    for line in raw_events.read_text().splitlines():
        try:
            event = json.loads(line)
            clean = submission_event(event) if isinstance(event, dict) else None
            if clean is not None:
                submitted.append(json.dumps(clean))
        except json.JSONDecodeError:
            pass
    (directory / "client-events.jsonl").write_text("\n".join(submitted) + "\n")
    final = transcript["final"] or {}
    model_usage = final.get("modelUsage") or {}
    actual_models = {value.get("canonicalModel", key) for key, value in model_usage.items() if isinstance(value, dict)}
    checks = {"client_process_succeeded": returncode == 0 and error is None,
              "stream_valid": not transcript["malformed_lines"],
              "successful_final_result": bool(final) and not final.get("is_error") and final.get("subtype") == "success",
              "actual_model_exactly_requested": actual_models == {MODEL},
              "model_usage_recorded": bool(model_usage)}
    checks["client_initialized_exactly_five_mcp_tools"] = any(
        set(event.get("tools", [])) == set(TOOLS)
        and {(server.get("name"), server.get("status")) for server in event.get("mcp_servers", [])} == {("proofflow", "connected")}
        for event in transcript["initialization"])
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
               "overall_attempt_number": 2,
               "infrastructure_correction": frozen.get("infrastructure_correction"),
               "attempt_count_scope": "One paid trajectory in v2; failed v1 is a separate retained paid attempt. No automatic retry inside either attempt.",
               "raw_client_events_sha256": sha(raw_events.read_bytes()),
               "submitted_client_events_sha256": sha((directory / "client-events.jsonl").read_bytes()),
               "artifact_privacy": "Raw streams, stderr, account/plugin initialization and environment-specific settings remain under ignored .state; submitted traces remove unrelated initialization metadata",
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
