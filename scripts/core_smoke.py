"""Reproduce ProofFlow's core correctness proof against a live HydraDB instance.

Run from the project checkout with the environment activated:
    python scripts/core_smoke.py

This creates a unique isolated workspace and never restarts or clears HydraDB.
The application-reopen check is distinct from the database restart proof in
scripts/hydra_smoke.py. Results are actual executions, not saved fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

# Allow a clean source checkout invocation without requiring an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from proofflow.analytics import DEMO_SOURCES
from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.models import MissingEvidenceError
from proofflow.runtime import ProofFlowRuntime


def build_fixture(runtime: ProofFlowRuntime):
    """Two actual report executions; B explicitly consumes A's intermediate."""
    sources = {name: runtime.set_source(name, data, f"Demo commerce {name}").current_id
               for name, data in DEMO_SOURCES.items()}
    nodes = {}
    nodes["gross"] = runtime.execute("gross_by_region", {"orders": sources["orders"]},
                                      logical_id="metric:gross", run_id="run-A")
    nodes["refunds"] = runtime.execute("refunds_by_region", {
        "orders": sources["orders"], "refunds": sources["refunds"]},
        logical_id="metric:refunds", run_id="run-A")
    nodes["net"] = runtime.execute("net_by_region", {
        "gross": nodes["gross"].id, "refunds": nodes["refunds"].id},
        logical_id="metric:net", run_id="run-A")
    nodes["regional"] = runtime.execute("convert_to_usd", {
        "net": nodes["net"].id, "fx": sources["fx"]},
        logical_id="metric:regional", run_id="run-A")
    nodes["company"] = runtime.execute("company_total", {"regional": nodes["regional"].id},
                                        logical_id="metric:company", run_id="run-A")
    nodes["support"] = runtime.execute("support_by_region", {"tickets": sources["tickets"]},
                                        logical_id="metric:support", run_id="run-A")
    shared_section = {"key": "eu_support", "label": "EU support tickets", "input": "support",
                      "path": ["regions", "EU", "tickets"], "unit": "tickets"}
    nodes["report_a"] = runtime.execute("compose_report", {
        "revenue": nodes["company"].id, "support": nodes["support"].id}, {
        "title": "Company weekly report", "sections": [
            {"key": "company_revenue", "label": "Company revenue", "input": "revenue",
             "path": ["usd_cents"], "unit": "USD cents"}, shared_section,
        ]}, logical_id="report:company", run_id="run-A")
    nodes["report_b"] = runtime.execute("compose_report", {
        "revenue": nodes["regional"].id, "support": nodes["support"].id}, {
        "title": "EU operations brief", "sections": [
            {"key": "eu_revenue", "label": "EU revenue", "input": "revenue",
             "path": ["regions", "EU", "usd_cents"], "unit": "USD cents"}, shared_section,
        ]}, logical_id="report:eu", run_id="run-B")
    return sources, nodes


def code_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((PROJECT_ROOT / "proofflow" / name).read_bytes()).hexdigest()
            for name in ["analytics.py", "artifacts.py", "graph.py", "models.py", "runtime.py"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="evidence/core_smoke.json")
    parser.add_argument("--state-root", default=".state")
    args = parser.parse_args()
    case_id = "core-smoke-" + uuid.uuid4().hex[:16]
    state_directory = Path(args.state_root) / case_id
    output = Path(args.output)
    started = time.monotonic()
    initial_code_hashes = code_hashes()
    checks: dict[str, bool] = {}
    stages: dict[str, dict] = {}
    details: dict = {}
    error = None
    store = None
    graph = None

    @contextmanager
    def stage(name: str, client: HydraGraph):
        before = client.queries, client.mutations, time.monotonic()
        try:
            yield
        finally:
            stages[name] = {"native_queries": client.queries - before[0],
                            "mutation_requests": client.mutations - before[1],
                            "elapsed_ms": round((time.monotonic() - before[2]) * 1000, 3)}

    try:
        store = ArtifactStore(state_directory)
        namespace = case_id + "-" + store.workspace
        graph = HydraGraph(namespace=namespace)
        runtime = ProofFlowRuntime(store, graph)
        details["namespace"] = namespace
        details["workspace"] = store.workspace
        with stage("fixture_setup", graph):
            sources, nodes = build_fixture(runtime)
            regional_before = store.read(nodes["regional"].id)
            company_before = store.read(nodes["company"].id)
            support_before = store.read(nodes["support"].id)
            # Independently known fixture arithmetic, not output-derived labels:
            # EU: (120000 + 80000 - 10000) * 1.10 = 209000 cents.
            # US: 180000 + 60000 - 5000 = 235000 cents.
            # UK: 90000 * 1.25 = 112500 cents; company = 556500.
            checks["known_initial_eu_cents"] = regional_before["regions"]["EU"]["usd_cents"] == 209000
            checks["known_initial_us_cents"] = regional_before["regions"]["US"]["usd_cents"] == 235000
            checks["known_initial_company_cents"] = company_before == {"usd_cents": 556500}
            checks["known_independent_support_count"] = support_before["regions"]["EU"]["tickets"] == 2
            checks["cross_run_input_reuse"] = (
                nodes["report_b"].metadata["run_id"] == "run-B"
                and nodes["regional"].metadata["run_id"] == "run-A"
                and nodes["report_b"].metadata["inputs"]["revenue"] == nodes["regional"].id
            )
            support_id = nodes["support"].id
            support_hash = nodes["support"].content_hash

        with stage("source_mutation", graph):
            change = runtime.set_source("fx", {**DEMO_SOURCES["fx"], "EUR": "1.20"})
            checks["new_source_version"] = change.changed and change.previous_id == sources["fx"]

        with stage("impact_and_claim_checks", graph):
            affected = sorted(node.logical_id for node in runtime.affected([change.previous_id]))
            checks["exact_expected_dependency_closure"] = affected == [
                "metric:company", "metric:regional", "report:company", "report:eu"]
            claims = {claim["key"]: claim for claim in runtime.report_claims(nodes["report_b"].id)}
            checks["stale_claim_value_withheld"] = (
                claims["eu_revenue"]["state"] == "stale"
                and claims["eu_revenue"]["value"] is None
                and claims["eu_revenue"]["saved_value"] == 209000
            )
            checks["independent_claim_still_current"] = (
                claims["eu_support"]["state"] == "current" and claims["eu_support"]["value"] == 2)
            expected = {key: runtime.full_recompute(nodes[key].id) for key in ["report_a", "report_b"]}
            call_start = len(runtime.calls)
            details["affected_logical_ids"] = affected

        with stage("selective_refresh", graph):
            refreshed = runtime.refresh([nodes["report_a"].id, nodes["report_b"].id], run_id="refresh-C")
        refresh_calls = runtime.calls[call_start:]
        details["refresh_calls"] = [{"tool": call["tool"], "status": call["status"],
                                      "elapsed_ms": round(call["elapsed_ms"], 3)} for call in refresh_calls]
        details["fresh_report_ids"] = {key: refreshed.replacements[nodes[key].id]
                                        for key in ["report_a", "report_b"]}
        with stage("post_refresh_verification", graph):
            checks["four_actual_tools_executed"] = len(refresh_calls) == 4 and all(call["status"] == "success" for call in refresh_calls)
            checks["no_support_reexecution"] = not any(call["tool"] == "support_by_region" for call in refresh_calls)
            checks["fresh_numeric_outputs_equal_full_recompute"] = all(
                store.read(refreshed.replacements[nodes[key].id]) == expected[key] for key in expected)
            checks["refreshed_reports_current"] = all(
                runtime.currentness(refreshed.replacements[nodes[key].id]).is_current for key in expected)
            new_regional_id = refreshed.replacements[nodes["regional"].id]
            new_report_b = store.get(refreshed.replacements[nodes["report_b"].id])
            checks["downstream_bound_to_new_intermediate"] = (
                new_regional_id != nodes["regional"].id
                and new_report_b.metadata["inputs"]["revenue"] == new_regional_id)
            checks["known_corrected_eu_cents"] = store.read(new_regional_id)["regions"]["EU"]["usd_cents"] == 228000
            checks["known_corrected_company_cents"] = store.read(refreshed.replacements[nodes["company"].id]) == {"usd_cents": 575500}
            checks["support_identity_and_hash_unchanged"] = (
                store.get_head("metric:support").id == support_id
                and store.get_head("metric:support").content_hash == support_hash
                and store.read(support_id) == support_before)

        original_workspace = store.workspace
        store.close()
        store = None
        graph.close()
        graph = None
        # A fresh SQLite connection, runtime and HTTP client reuse persisted data.
        store = ArtifactStore(state_directory)
        graph = HydraGraph(namespace=namespace)
        runtime = ProofFlowRuntime(store, graph)
        with stage("application_reopen_new_client", graph):
            checks["workspace_persisted"] = store.workspace == original_workspace
            checks["application_reopen_graph_and_content"] = all(
                runtime.currentness(details["fresh_report_ids"][key]).is_current
                and store.read(details["fresh_report_ids"][key]) == expected[key]
                for key in expected)
            checks["new_client_reads_existing_hydra_node"] = graph.get_node(new_report_b.id) is not None

        with stage("missing_source_refusal", graph):
            runtime.remove_source("fx")
            checks["removed_source_invalidates_saved_report"] = not runtime.currentness(new_report_b.id).is_current
            try:
                runtime.refresh([new_report_b.id])
            except MissingEvidenceError:
                checks["missing_source_refresh_refused"] = True
            else:
                checks["missing_source_refresh_refused"] = False
            try:
                runtime.full_recompute(new_report_b.id)
            except MissingEvidenceError:
                checks["missing_source_full_recompute_refused"] = True
            else:
                checks["missing_source_full_recompute_refused"] = False
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if store is not None:
            store.close()
        if graph is not None:
            graph.close()

    final_code_hashes = code_hashes()
    checks["runtime_code_unchanged_during_probe"] = initial_code_hashes == final_code_hashes
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend": "HydraDB OSS live; native graph traversal; no fallback",
        "case_id": case_id,
        "application_reopen_tested": "application_reopen_graph_and_content" in checks,
        "database_restart_requested": False,
        "graph_replayed_from_application": False,
        "data": "Authored commerce fixture; actual SQLite tools; staged EUR exchange-rate correction",
        "oracle_scope": "Fresh recipe execution independent of graph/cache, with separate known numeric fixture assertions",
        "state_directory": str(state_directory),
        "final_state": "fx source intentionally removed at the end to prove missing-source refusal",
        "code_hashes": initial_code_hashes,
        "checks": checks,
        "passed": bool(checks) and all(checks.values()) and error is None,
        "stages": stages,
        "native_queries_total": sum(item["native_queries"] for item in stages.values()),
        "mutation_requests_total": sum(item["mutation_requests"] for item in stages.values()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "details": details,
        "error": error,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks_passed": sum(checks.values()),
                      "checks_total": len(checks), "native_queries": result["native_queries_total"],
                      "refresh_queries": stages.get("selective_refresh", {}).get("native_queries"),
                      "evidence": str(output), "elapsed_seconds": result["elapsed_seconds"], "error": error}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
