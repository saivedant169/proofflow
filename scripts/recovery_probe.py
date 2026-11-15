"""Prospective SIGKILL recovery experiment; fault injection exists only here.

Run from this isolated worktree after protocol, inputs and harness are committed.
The production application and database process are never patched or restarted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from proofflow.api import create_app
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime
import proofflow.importing as importing_module
import proofflow.runtime as runtime_module


FIXTURES = ROOT / "fixtures/recovery_v1"
PRODUCTION_FILES = [f"proofflow/{name}.py" for name in (
    "api", "browser_import", "demo", "importing", "runtime", "artifacts", "graph", "analytics", "models")]
READY = "RECOVERY_BOUNDARY_READY "
TRACE_PATH = None
CURRENT_OPERATION = "initialization"
EXECUTION_CONTEXT = threading.local()


def instrument_arithmetic(path):
    """Observational child-only wrappers; original tool arguments/results unchanged."""
    global TRACE_PATH
    TRACE_PATH = path
    path.write_text("")
    real_import_tool = importing_module.execute_tool
    real_runtime_tool = runtime_module.execute_tool
    real_execute = ProofFlowRuntime.execute

    def append(tool, category):
        with path.open("a") as handle:
            handle.write(json.dumps({"operation": CURRENT_OPERATION, "tool": tool, "category": category,
                                     "status": "success", "pid": os.getpid()}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def importing_tool(tool, *args, **kwargs):
        result = real_import_tool(tool, *args, **kwargs)
        append(tool, "preflight")
        return result

    def runtime_tool(tool, *args, **kwargs):
        result = real_runtime_tool(tool, *args, **kwargs)
        append(tool, "recorded" if getattr(EXECUTION_CONTEXT, "recorded", False) else "verification")
        return result

    def execute(runtime, *args, **kwargs):
        previous = getattr(EXECUTION_CONTEXT, "recorded", False)
        EXECUTION_CONTEXT.recorded = True
        try:
            return real_execute(runtime, *args, **kwargs)
        finally:
            EXECUTION_CONTEXT.recorded = previous

    importing_module.execute_tool = importing_tool
    runtime_module.execute_tool = runtime_tool
    ProofFlowRuntime.execute = execute


def write(path: Path, value, *, private=False):
    def redact(item):
        if isinstance(item, list):
            return [redact(value) for value in item]
        if isinstance(item, dict):
            output = {}
            for key, value in item.items():
                if key in {"session_id", "cookie"} and isinstance(value, str):
                    output[key] = value if value.startswith("sha256:") else "sha256:" + hashlib.sha256(value.encode()).hexdigest()
                elif key == "workspace_directory":
                    output[key] = f"<private-state>/<redacted-session>/imports/{Path(value).name}"
                else:
                    output[key] = redact(value)
            return output
        return item

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        json.dump(value if private else redact(value), handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if private:
        path.chmod(0o600)


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in PRODUCTION_FILES + ["scripts/recovery_probe.py", "docs/RECOVERY_V1_PROTOCOL.md",
                                            "fixtures/recovery_v1/manifest.json",
                                            "fixtures/recovery_v1/base.csv", "fixtures/recovery_v1/corrected.csv"]}


def payload(corrected=False):
    return {"csv_text": (FIXTURES / ("corrected.csv" if corrected else "base.csv")).read_text(),
            "rates": {"EUR": "1.25"}, "region": "RIVER"}


def values(state):
    return [report["claims"][0]["value"] for report in state["reports"]]


def support(state):
    return next(node for node in state["graph"]["nodes"] if node["logical_id"] == "import:metric:support")


def response(client, method, route, expected=200, **kwargs):
    global CURRENT_OPERATION
    CURRENT_OPERATION = f"{method.upper()} {route}"
    result = getattr(client, method)(route, **kwargs)
    assert result.status_code == expected, (route, result.status_code, result.text)
    return {"http_status": result.status_code, "body": result.json()}


def locations(output: Path, label: str):
    state = output / "state" / label
    cookie = json.loads((output / "private" / f"{label}-cookie.json").read_text())["cookie"]
    metadata = json.loads((state / cookie / "session.json").read_text())
    workspace = state / cookie / "imports" / metadata["import"]["workspace_id"]
    return state, cookie, metadata, workspace


def read_manifest(output: Path, label: str):
    _, _, metadata, workspace = locations(output, label)
    connection = sqlite3.connect(f"file:{workspace / 'manifest.sqlite3'}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        records = {row["id"]: dict(row) for row in connection.execute("SELECT * FROM records")}
        heads = [dict(row) for row in connection.execute("SELECT logical_id, record_id FROM heads ORDER BY logical_id")]
        workspace_id = connection.execute("SELECT value FROM settings WHERE key='workspace'").fetchone()[0]
        journal = connection.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        connection.close()
    for record in records.values():
        record["metadata"] = json.loads(record["metadata"])
    result = {}
    for head in heads:
        record = records[head["record_id"]]
        value = json.loads((workspace / "blobs" / f"{record['content_hash']}.json").read_text())
        result[head["logical_id"]] = {**record, "value": value}
    return {"metadata": metadata["import"], "workspace_directory": str(workspace),
            "namespace": f"browser-import-{workspace_id}", "journal_mode": journal,
            "head_count": len(heads), "distinct_logical_head_count": len({row["logical_id"] for row in heads}),
            "heads": result, "records": records}


def semantic_lineage(snapshot):
    result = {}
    for logical, record in snapshot["heads"].items():
        if record["kind"] != "artifact":
            continue
        metadata = record["metadata"]
        inputs = {name: {"logical_id": snapshot["records"][key]["logical_id"],
                         "content_hash": snapshot["records"][key]["content_hash"]}
                  for name, key in metadata["inputs"].items()}
        result[logical] = {"content_hash": record["content_hash"], "value": record["value"],
                           "tool": metadata["tool"], "params": metadata["params"], "inputs": inputs}
    return result


def assert_interrupted(state, baseline):
    assert state["incomplete_update"] is True, "incomplete publication marker was lost"
    assert state["dataset"]["source_csv_sha256"] == baseline["dataset"]["source_csv_sha256"], "last-successful CSV metadata changed"
    assert all(report["state"] == "stale" for report in state["reports"]), "affected report incorrectly current"
    assert all(claim["value"] is None and claim["state"] == "stale"
               for report in state["reports"] for claim in report["claims"]), "stale monetary value was served"
    assert support(state)["id"] == support(baseline)["id"] and support(state)["state"] == "current", "unaffected support lost currentness"


def child(output: Path, phase: str):
    global CURRENT_OPERATION
    instrument_arithmetic(output / f"arithmetic-{phase}.jsonl")
    label = "control" if phase == "control" else "interrupted"
    state_dir = output / "state" / label
    app = create_app(state_dir=state_dir, static_dir=output / "no-static")
    with TestClient(app) as client:
        if phase in {"control", "setup"}:
            response(client, "post", "/api/session")
            write(output / "private" / f"{label}-cookie.json", {"cookie": client.cookies.get("proofflow_session")}, private=True)
            initial = response(client, "post", "/api/import/create", json=payload())["body"]
            write(output / f"{label}-initial.json", initial)
            initial_manifest = read_manifest(output, label)
            write(output / f"{label}-initial-manifest.json", initial_manifest)
            assert values(initial) == [80000, 50000], "independent baseline arithmetic failed"
            assert all(report["state"] == "current" and all(claim["state"] == "current" for claim in report["claims"])
                       for report in initial["reports"])
            assert len(semantic_lineage(initial_manifest)) == 8
            assert support(initial)["state"] == "current"
            if phase == "setup":
                return
        else:
            _, cookie, _, _ = locations(output, label)
            client.cookies.set("proofflow_session", cookie)
        if phase == "fault":
            original = ProofFlowRuntime.set_source

            def boundary(runtime, name, value, description=""):
                changed = original(runtime, name, value, description)
                if name == "csv:orders" and changed.changed:
                    # This pause is between fully committed source updates.
                    # Parent independently verifies storage, then SIGKILLs us.
                    event = {"pid": os.getpid(), "old_order_id": changed.previous_id,
                             "new_order_id": changed.current_id,
                             "at": "after orders set_source returned; before refunds set_source",
                             "time": datetime.now(timezone.utc).isoformat()}
                    write(output / "child-boundary-ready.json", event)
                    print(READY + json.dumps(event), flush=True)
                    threading.Event().wait(45)
                    os._exit(97)  # Parent failed to kill at the controlled boundary.
                return changed

            ProofFlowRuntime.set_source = boundary
            CURRENT_OPERATION = "POST /api/import/update"
            client.post("/api/import/update", json=payload(True))
            raise AssertionError("Fault child unexpectedly continued beyond the boundary")
        if phase == "reopen":
            baseline = json.loads((output / "interrupted-initial.json").read_text())
            state = response(client, "get", "/api/import/state")["body"]
            write(output / "reopened-state.json", state)
            assert_interrupted(state, baseline)
            blocked = {name: response(client, "post", f"/api/import/{name}", expected=409, json={})
                       for name in ("refresh", "verify")}
            write(output / "blocked-recovery-actions.json", blocked)
            write(output / "reopened-manifest.json", read_manifest(output, label))
            return
        updated = response(client, "post", "/api/import/update", json=payload(True))["body"]
        write(output / f"{label}-updated.json", updated)
        assert len(updated["impact"]["affected_artifacts"]) == 7, "original affected roots were not retained"
        assert all(report["claims"][0]["value"] is None for report in updated["reports"])
        final = response(client, "post", "/api/import/refresh", json={})["body"]
        write(output / f"{label}-final.json", final)
        assert values(final) == [83125, 53125], "independent corrected arithmetic failed"
        assert final["last_refresh"]["executed_count"] == 7, "wrong selective refresh count"
        baseline = json.loads((output / f"{label}-initial.json").read_text())
        assert support(final)["id"] == support(baseline)["id"] and support(final)["state"] == "current"
        assert all(call["tool"] != "support_by_region" for call in final["last_refresh"]["tool_calls"])
        snapshot = read_manifest(output, label)
        write(output / f"{label}-final-manifest.json", snapshot)
        write(output / f"{label}-semantic-lineage.json", semantic_lineage(snapshot))


def run(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain", "--", *hashes()], cwd=ROOT, text=True)
    assert not status, "Commit protocol, fixtures, harness and production source before executing"
    frozen = hashes()
    write(output / "run-manifest.json", {"revision": revision, "production_base": "500f3ae",
        "started_at": datetime.now(timezone.utc).isoformat(), "sha256": frozen,
        "scope": "Process SIGKILL between two fully committed source updates; not an OS/power-loss or within-write atomicity test"})
    write(output / "requests.json", {"baseline": payload(), "correction_and_resubmission": payload(True)})
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT)
    environment.setdefault("PROOFFLOW_HYDRA_URL", "http://127.0.0.1:18443")
    # The operator supplies an existing token-file path; never read/copy it here.
    assert environment.get("PROOFFLOW_HYDRA_TOKEN_FILE") or environment.get("PROOFFLOW_HYDRA_TOKEN"), "Configure existing local Hydra credentials in environment"
    checks = {}
    failure = None
    process = None

    def phase(name):
        assert hashes() == frozen, "Code or inputs changed during experiment"
        command = [sys.executable, str(Path(__file__).resolve()), "--phase", name, "--output", str(output)]
        started = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired as exc:
            write(output / f"phase-{name}.json", {"timeout": True, "stdout": str(exc.stdout or ""),
                "stderr": str(exc.stderr or ""), "elapsed_seconds": time.monotonic() - started})
            raise
        write(output / f"phase-{name}.json", {"returncode": completed.returncode, "stdout": completed.stdout,
                                             "stderr": completed.stderr, "elapsed_seconds": time.monotonic() - started})
        assert completed.returncode == 0, f"Phase {name} failed; preserved stderr in phase-{name}.json"

    try:
        phase("control")
        checks["uninterrupted_control_known_values"] = True
        phase("setup")
        initial_control = json.loads((output / "control-initial-manifest.json").read_text())
        initial_interrupted = json.loads((output / "interrupted-initial-manifest.json").read_text())
        assert semantic_lineage(initial_control) == semantic_lineage(initial_interrupted)
        checks["initial_arms_have_matching_current_artifact_lineage"] = True
        command = [sys.executable, str(Path(__file__).resolve()), "--phase", "fault", "--output", str(output)]
        with (output / "fault-stderr.txt").open("w") as stderr:
            boundary_started = time.monotonic()
            boundary_deadline = boundary_started + 30
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                                       stderr=stderr, text=True, bufsize=1)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=max(0, boundary_deadline - time.monotonic())), "No stable boundary acknowledgment within 30 seconds"
            line = process.stdout.readline()
            (output / "fault-stdout.txt").write_text(line)
            selector.close()
            assert line.startswith(READY), f"Unexpected boundary response: {line!r}"
            event = json.loads(line[len(READY):])
            baseline = json.loads((output / "interrupted-initial-manifest.json").read_text())
            observed = read_manifest(output, "interrupted")
            write(output / "parent-readonly-manifest-before-kill.json", observed)
            orders = observed["heads"]["source:csv:orders"]
            refunds = observed["heads"]["source:csv:refunds"]
            graph = HydraGraph(namespace=observed["namespace"], timeout=5)
            try:
                native_orders = graph.get_node(orders["id"])
                native_refunds = graph.get_node(refunds["id"])
            finally:
                graph.close()
            write(output / "parent-observed-boundary.json", {"child_pid": event["pid"],
                "native_order_node": native_orders, "native_refund_node": native_refunds,
                "native_queries": graph.queries, "manifest": observed,
                "elapsed_seconds": time.monotonic() - boundary_started,
                "observation": "Parent read-only SQLite connection and independent Hydra client; before SIGKILL"})
            assert orders["id"] == event["new_order_id"] != baseline["heads"]["source:csv:orders"]["id"]
            assert refunds["id"] == baseline["heads"]["source:csv:refunds"]["id"]
            assert next(row for row in orders["value"] if row["order_id"] == "river-a")["gross_cents"] == 46000
            assert next(row for row in refunds["value"] if row["order_id"] == "river-a")["refund_cents"] == 2000
            assert observed["metadata"]["incomplete_update"] is True
            assert observed["metadata"]["dataset"] == baseline["metadata"]["dataset"]
            assert {baseline["heads"][name]["id"] for name in ("source:csv:orders", "source:csv:refunds")} <= set(observed["metadata"]["pending_roots"])
            assert native_orders is not None and native_refunds is not None, "Parent could not observe both committed native source vertices"
            assert time.monotonic() <= boundary_deadline, "Complete durable-boundary observation exceeded 30 seconds"
            assert process.poll() is None, "Child exited before controlled SIGKILL"
            os.kill(process.pid, signal.SIGKILL)
            returncode = process.wait(timeout=10)
            write(output / "kill-result.json", {"signal": "SIGKILL", "returncode": returncode,
                "child_pid": process.pid, "parent_verified_storage_before_kill": True})
            assert returncode == -signal.SIGKILL
            checks["parent_observed_mixed_durable_heads_and_native_vertex"] = True
            checks["actual_sigkill_without_application_cleanup"] = True
        phase("reopen")
        checks["reopen_marker_stale_withheld_support_current"] = True
        checks["refresh_and_verify_refused_until_resubmission"] = True
        observed = json.loads((output / "reopened-state.json").read_text())
        baseline = json.loads((output / "interrupted-initial.json").read_text())
        corrupted = deepcopy(observed)
        corrupted["reports"][0]["claims"][0]["state"] = "current"
        corrupted["reports"][0]["claims"][0]["value"] = corrupted["reports"][0]["claims"][0]["saved_value"]
        try:
            assert_interrupted(corrupted, baseline)
        except AssertionError as detected:
            write(output / "negative-control.json", {"detected": True, "reason": str(detected),
                "scope": "Counterfactual API response corruption only; no production database or detector monkeypatch",
                "mutated_response": corrupted})
        else:
            raise AssertionError("Detector missed injected stale-current response corruption")
        checks["negative_response_control_detected"] = True
        phase("recover")
        checks["resubmit_retains_all_original_affected_roots"] = True
        checks["recovered_known_values_and_seven_calls"] = True
        control = json.loads((output / "control-semantic-lineage.json").read_text())
        recovered = json.loads((output / "interrupted-semantic-lineage.json").read_text())
        assert control == recovered, "Recovered values/hashes/recipe lineage differ from uninterrupted control"
        assert len(recovered) == 8
        snapshot = json.loads((output / "interrupted-final-manifest.json").read_text())
        assert snapshot["head_count"] == snapshot["distinct_logical_head_count"] == 19
        assert snapshot["metadata"]["incomplete_update"] is False
        assert snapshot["metadata"]["dataset"]["source_csv_sha256"] == hashlib.sha256((FIXTURES / "corrected.csv").read_bytes()).hexdigest()
        checks["control_parity_for_all_eight_artifact_lineages"] = True
        checks["no_duplicate_current_heads"] = True
        checks["successful_source_metadata_reconciled"] = True
        expected_totals = {"control": {"preflight": 16, "recorded": 23, "verification": 22},
                           "setup": {"preflight": 8, "recorded": 16, "verification": 11},
                           "fault": {"preflight": 8, "recorded": 0, "verification": 0},
                           "reopen": {"preflight": 0, "recorded": 0, "verification": 0},
                           "recover": {"preflight": 8, "recorded": 7, "verification": 11}}
        expected_refresh_tools = json.loads((FIXTURES / "manifest.json").read_text())["refresh_recorded_tool_counts"]
        expected_refresh_tools = {key: value for key, value in expected_refresh_tools.items() if value}
        accounting = {}
        for phase_name, expected in expected_totals.items():
            rows = [json.loads(line) for line in (output / f"arithmetic-{phase_name}.jsonl").read_text().splitlines()]
            counts = Counter(row["category"] for row in rows)
            observed_counts = {key: counts[key] for key in expected}
            accounting[phase_name] = {"observed": observed_counts, "expected": expected,
                                     "total": sum(counts.values()), "operations": sorted({row["operation"] for row in rows})}
            write(output / "lifecycle-accounting.json", accounting)
            assert observed_counts == expected, f"Unexpected full lifecycle arithmetic in {phase_name}"
            if phase_name in {"control", "recover"}:
                refresh_tools = Counter(row["tool"] for row in rows
                    if row["operation"] == "POST /api/import/refresh" and row["category"] == "recorded")
                assert dict(refresh_tools) == expected_refresh_tools, "Refresh tool multiset differs from manifest"
        write(output / "lifecycle-accounting.json", accounting)
        checks["full_lifecycle_accounting_including_bootstrap_and_interruption"] = True
        checks["exact_refresh_tool_multisets_match_manifest"] = True
        assert hashes() == frozen
        checks["frozen_inputs_and_implementation_unchanged"] = True
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    summary = {"passed": failure is None and bool(checks) and all(checks.values()),
        "checks": checks, "error": failure, "revision": revision,
        "finished_at": datetime.now(timezone.utc).isoformat(), "model_calls": 0,
        "production_change": False,
        "scope": "One prospective SIGKILL at the boundary between committed orders and pending refunds updates. No main-app/Hydra restart; no claim about OS/power-loss or within-write crash atomicity."}
    write(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["control", "setup", "fault", "reopen", "recover"])
    arguments = parser.parse_args()
    if arguments.phase:
        child(arguments.output.resolve(), arguments.phase)
    elif not run(arguments.output.resolve()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
