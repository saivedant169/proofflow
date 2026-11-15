"""Prepare, then run two real model-selected compositions and a live FX refresh.

Preparation is free. --run-paid explicitly launches at most two local Claude
CLI calls, each capped at $1 and 180 seconds, with no automatic retries.
This is a small composition demonstration, not a comparative benchmark.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proofflow.analytics import DEMO_SOURCES
from proofflow.artifacts import ArtifactStore
from proofflow.composition import (COMPOSITION_SCHEMA, COMPOSITION_SYSTEM_PROMPT,
                                   CompositionCLIProvider, CompositionError, canonical,
                                   execute_composition, make_request, plan_composition, sha)
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime

TASKS = (
    "Create a company revenue report in USD including EU support workload. Revenue means order amounts less refunds. Include the EU ticket count in the report.",
    "Create an EU operations brief from the existing outputs, reusing prior results where possible. Include EU net revenue in USD, EU ticket count, and the company revenue total for context.",
)


def write(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def revision():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def hashes():
    paths = ["proofflow/composition.py", "scripts/composition_probe.py", "proofflow/runtime.py",
             "proofflow/analytics.py", "proofflow/graph.py", "proofflow/artifacts.py"]
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def claims_by_path(runtime, report_id):
    """The independent check keys numeric values by actual producing path/unit."""
    record = runtime.store.get(report_id)
    sections = record.metadata["params"]["sections"]
    value = runtime.store.read(report_id)
    result = {}
    for spec, result_section in zip(sections, value["sections"], strict=True):
        result[(tuple(spec["path"]), spec["unit"])] = result_section["value"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-paid", action="store_true")
    args = parser.parse_args()
    directory = args.output
    prepared = directory / "prepared.json"
    if not args.run_paid:
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("Refusing to overwrite a composition preparation")
        directory.mkdir(parents=True, exist_ok=True)
        store = ArtifactStore(directory / "state")
        graph = HydraGraph(namespace=f"composition-{store.workspace}")
        runtime = ProofFlowRuntime(store, graph)
        try:
            for name, value in DEMO_SOURCES.items():
                runtime.set_source(name, value, f"Authored commerce source {name}")
            request = make_request(runtime, TASKS[0])
            write(directory / "request-1.json", {"prompt": json.loads(request.prompt()),
                                                "prompt_sha256": sha(request.prompt()), "handle_map": request.handles})
            write(prepared, {"prepared_at": datetime.now(timezone.utc).isoformat(),
                             "namespace": graph.namespace, "revision": revision(), "code_sha256": hashes(),
                             "system_prompt": COMPOSITION_SYSTEM_PROMPT,
                             "system_prompt_sha256": sha(COMPOSITION_SYSTEM_PROMPT),
                             "schema": COMPOSITION_SCHEMA, "schema_sha256": sha(canonical(COMPOSITION_SCHEMA)),
                             "tasks": TASKS, "calls": 2, "max_cost_usd_per_call": 1,
                             "max_seconds_per_call": 180, "model": "claude-fable-5-2", "effort": "high",
                             "limitations": "Two authored tasks; live local tools and Hydra, not a held-out comparison or learning curve."})
        finally:
            store.close()
            graph.close()
        print(json.dumps({"prepared": str(prepared), "live_model_calls": 0,
                          "system_prompt_sha256": sha(COMPOSITION_SYSTEM_PROMPT),
                          "schema_sha256": sha(canonical(COMPOSITION_SCHEMA))}))
        return
    metadata = json.loads(prepared.read_text())
    if metadata["code_sha256"] != hashes() or metadata["tasks"] != list(TASKS):
        raise ValueError("Prepared code/task hashes changed; preserve this preparation and create a new one")
    if (directory / "started.json").exists():
        raise ValueError("Composition run already started; no automatic retry or overwrite")
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", "proofflow/composition.py", "scripts/composition_probe.py"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    untracked = subprocess.run(["git", "ls-files", "--error-unmatch", "proofflow/composition.py", "scripts/composition_probe.py"],
                               cwd=ROOT, capture_output=True, text=True).returncode
    if changed or untracked:
        raise ValueError("Commit the reviewed composition harness before live model calls")
    write(directory / "started.json", {"started_at": datetime.now(timezone.utc).isoformat(), "revision": revision(), "code_sha256": hashes()})
    store = ArtifactStore(directory / "state")
    graph = HydraGraph(namespace=metadata["namespace"])
    runtime = ProofFlowRuntime(store, graph)
    provider = CompositionCLIProvider(cwd=directory.resolve())
    started = time.monotonic()
    checks = {}
    executions = []
    plans = []
    error = None
    try:
        for index, task in enumerate(TASKS, 1):
            request = make_request(runtime, task)
            request_file = directory / f"request-{index}.json"
            value = {"prompt": json.loads(request.prompt()), "prompt_sha256": sha(request.prompt()), "handle_map": request.handles}
            if request_file.exists() and json.loads(request_file.read_text()) != value:
                raise ValueError("Prepared request differs from current source snapshot")
            write(request_file, value)
            try:
                plan = plan_composition(provider, request)
            except Exception as exc:
                failure = {"error_type": type(exc).__name__, "message": str(exc),
                           "provider_evidence": getattr(exc, "evidence", None)}
                if getattr(exc, "provider_result", None):
                    failure["provider_result"] = asdict(exc.provider_result)
                write(directory / f"plan-{index}-failure.json", failure)
                raise
            write(directory / f"plan-{index}.json", plan.to_dict())
            plans.append(plan.to_dict())
            result = execute_composition(runtime, request, plan, run_id=f"model-composition-{index}")
            write(directory / f"execution-{index}.json", result)
            executions.append(result)
            if result["status"] != "executed":
                raise CompositionError("Model abstained; no fabricated fallback report")
        a, b = (item["report_id"] for item in executions)
        first_values = claims_by_path(runtime, a)
        second_values = claims_by_path(runtime, b)
        checks["company_value_independently_known"] = first_values.get((("usd_cents",), "USD cents")) == 556500
        checks["first_report_eu_support_independently_known"] = first_values.get((("regions", "EU", "tickets"), "tickets")) == 2
        checks["eu_value_independently_known"] = second_values.get((("regions", "EU", "usd_cents"), "USD cents")) == 209000
        checks["second_report_eu_support_independently_known"] = second_values.get((("regions", "EU", "tickets"), "tickets")) == 2
        checks["second_report_company_context_independently_known"] = second_values.get((("usd_cents",), "USD cents")) == 556500
        a_outputs = {item["artifact_id"] for item in executions[0]["steps"]}
        b_inputs = set(store.get(b).metadata["inputs"].values())
        reused = sorted(a_outputs & b_inputs)
        checks["second_report_consumes_first_run_artifacts"] = bool(reused)
        checks["different_report_compositions"] = store.get(a).metadata["params"] != store.get(b).metadata["params"]
        checks["both_model_reports_current"] = runtime.currentness(a).is_current and runtime.currentness(b).is_current
        support = [record for record in store.heads("artifact") if record.metadata.get("tool") == "support_by_region"]
        support_before = {record.logical_id: record.id for record in support}
        fx = store.get_head("source:fx")
        rates = dict(store.read(fx.id))
        rates["EUR"] = "1.20"
        change = runtime.set_source("fx", rates, "Authored exchange-rate correction")
        affected = runtime.affected([change.previous_id])
        checks["native_impact_reaches_both_model_reports"] = {a, b} <= {record.id for record in affected}
        checks["stale_claims_withheld"] = all(claim["value"] is None for rid in (a, b) for claim in runtime.report_claims(rid) if claim["unit"] == "USD cents")
        paths = {rid: graph.paths(change.previous_id, rid) for rid in (a, b)}
        calls_before = len(runtime.calls)
        refreshed = runtime.refresh([a, b], run_id="model-composition-refresh")
        new_a, new_b = refreshed.replacements[a], refreshed.replacements[b]
        checks["company_updated_independently_known"] = claims_by_path(runtime, new_a).get((("usd_cents",), "USD cents")) == 575500
        checks["eu_updated_independently_known"] = claims_by_path(runtime, new_b).get((("regions", "EU", "usd_cents"), "USD cents")) == 228000
        checks["model_reports_match_full_recompute"] = all(store.read(rid) == runtime.full_recompute(rid) for rid in (new_a, new_b))
        checks["new_reports_current"] = all(runtime.currentness(rid).is_current for rid in (new_a, new_b))
        checks["unrelated_support_identity_preserved"] = all(store.get_head(key).id == value for key, value in support_before.items())
        checks["support_not_reexecuted"] = all(call["tool"] != "support_by_region" for call in runtime.calls[calls_before:])
        old_shared = [key for key in reused if store.get(key).metadata.get("tool") != "support_by_region"]
        new_b_inputs = set(store.get(new_b).metadata["inputs"].values())
        checks["old_shared_handles_rebound"] = bool(old_shared) and all(key not in new_b_inputs and refreshed.replacements.get(key) in new_b_inputs for key in old_shared)
        write(directory / "refresh.json", {"source_change": asdict(change), "affected_ids": [record.id for record in affected],
                                           "native_paths": paths, "result": refreshed.to_dict(), "calls": runtime.calls[calls_before:],
                                           "reports": [store.read(new_a), store.read(new_b)], "cross_run_reused_ids": reused})
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        write(directory / "receipts.json", [store.read(record.id) for record in store.list_records("execution")])
        summary = {"passed": error is None and bool(checks) and all(checks.values()), "checks": checks, "error": error,
                   "model_calls_completed": len(plans), "plans": [f"plan-{i+1}.json" for i in range(len(plans))],
                   "reported_cost_usd": sum(plan["provider_result"].get("reported_cost_usd") or 0 for plan in plans),
                   "elapsed_seconds": time.monotonic() - started, "native_graph_queries": graph.queries,
                   "native_graph_mutations": graph.mutations, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "limitations": metadata["limitations"]}
        write(directory / "summary.json", summary)
        store.close()
        graph.close()
    print(json.dumps(summary, indent=2))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
