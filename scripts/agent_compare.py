"""Frozen, local Claude CLI comparison over already-produced retrieval contexts.

prepare writes label-free requests without contacting a model or HydraDB. run
makes one model planning call per request, saves every observation, then scores
validated plans with the same Hydra-assisted safe executor used by every arm.
This is a small authored retrieval/planning pilot, not general agent autonomy.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from proofflow.agent import (AgentPlan, AgentRequest, ClaudeCLIProvider, PLAN_SCHEMA,
                            SYSTEM_PROMPT, plan_refresh)


ROOT = Path(__file__).resolve().parents[1]
ARMS = ("bm25", "dense", "iterative_hybrid", "graph")
CASE_IDS = {"dev": ("D02",), "test": ("T02", "T04", "T07", "T10")}
PROTOCOL = {
    "version": "agent-pilot-v1",
    "model": "claude-fable-5-2", "effort": "high",
    "arms": list(ARMS), "cases": {key: list(value) for key, value in CASE_IDS.items()},
    "context_budget": 2048, "tokenizer": "cl100k_base",
    "max_budget_usd_per_call": 1.0, "timeout_seconds": 180,
    "planner_steps": 1, "retries": 0, "model_fallback": False,
    "arm_order": "fixed rotation by case index; all plans frozen before any refresh",
    "primary_metric": "fresh affected reports after actual tool refresh; per-case outcomes retained",
    "secondary_metrics": ["selected artifact precision/recall", "actual tool calls", "latency", "provider usage"],
    "executor": "Every arm uses the same Hydra-assisted currentness and recursive refresh executor.",
    "scope": "Small authored retrieval/planning pilot. Report composition is predefined, not invented by the model.",
    "token_accounting": "Retrieval budget counts canonical JSONL without file terminator. Provider usage includes CLI/schema/system/cache overhead; cl100k estimates are separate.",
    "blocking_interpretation": "Missing-source blocking comes from the shared executor and does not establish a planning advantage.",
}
CODE_PATHS = (
    "proofflow/agent.py", "scripts/agent_compare.py", "proofflow/eval/cases.py",
    "proofflow/eval/execution.py", "proofflow/eval/workload.py", "proofflow/eval/retrieval.py",
    "proofflow/artifacts.py", "proofflow/runtime.py", "proofflow/analytics.py",
    "proofflow/graph.py", "proofflow/models.py", "docs/BENCHMARK_MANIFEST.json",
)


def sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def code_hashes() -> dict[str, str]:
    return {name: sha((ROOT / name).read_bytes()) for name in CODE_PATHS}


def git_state() -> dict[str, Any]:
    def command(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return {"revision": command("rev-parse", "HEAD"),
            "tracked_changes": bool(command("status", "--porcelain", "--untracked-files=no"))}


def guard_test(split: str, allow_test: bool) -> None:
    if split == "test":
        if not allow_test:
            raise ValueError("Heldout preparation/run requires explicit --allow-test after harness review")
        if git_state()["tracked_changes"]:
            raise ValueError("Commit the reviewed harness before heldout model calls")


def request_from_evidence(query: dict[str, Any], context: str) -> AgentRequest:
    """Only these three data channels reach the model; no case labels pass here."""
    if set(query) != {"text", "changed_ids"}:
        raise ValueError("Unexpected query fields")
    ids = tuple(json.loads(line)["id"] for line in context.splitlines() if line.strip())
    request = AgentRequest(query["text"], tuple(query["changed_ids"]), context, ids)
    request.validate()
    return request


def verify_context(context: str, row: dict[str, Any], counter: Any) -> list[str]:
    # Runner writes exactly one file newline after its hashed serialization.
    serialized = context.removesuffix("\n")
    if sha(serialized) != row["context_sha256"]:
        raise ValueError("Frozen retrieval context hash mismatch")
    ids = [json.loads(line)["id"] for line in context.splitlines() if line.strip()]
    if ids != row["retrieved_ids"]:
        raise ValueError("Frozen retrieval context IDs/order mismatch")
    if counter(serialized) != row["context_tokens"] or row["context_tokens"] > PROTOCOL["context_budget"]:
        raise ValueError("Frozen retrieval context token accounting mismatch")
    return ids


def prepare(source: Path, output: Path, split: str, *, allow_test: bool = False) -> dict[str, Any]:
    from proofflow.eval.cases import SCENARIOS
    from proofflow.eval.retrieval import TokenCounter

    guard_test(split, allow_test)
    source, output = source.resolve(), output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Refusing to overwrite a prepared comparison")
    run = read_json(source / "run_manifest.json")
    if run.get("split") != split or not run.get("finished_at"):
        raise ValueError("Source must be a completed frozen retrieval run of the requested split")
    if not set(CASE_IDS[split]) <= set(run.get("scenarios", [])):
        raise ValueError("Source run does not contain every prespecified comparison case")
    rows = [json.loads(line) for line in (source / "retrieval.jsonl").read_text().splitlines() if line.strip()]
    counter = TokenCounter(PROTOCOL["tokenizer"])
    scenarios = {scenario.id: scenario for scenario in SCENARIOS}
    jobs, case_hashes, store_hashes = [], {}, {}
    for case_index, case_id in enumerate(CASE_IDS[split]):
        directory = source / case_id
        case = read_json(directory / "case.json")
        # JSON round-trip normalizes the scenario's tuple declarations to lists.
        if case["scenario"] != json.loads(json.dumps(scenarios[case_id].to_dict())):
            raise ValueError("Scenario definitions differ from the frozen source")
        if not (directory / "initial" / "manifest.sqlite3").is_file():
            raise ValueError("Missing original mutated runtime store")
        case_hashes[case_id] = sha((directory / "case.json").read_bytes())
        store_hashes[case_id] = sha((directory / "initial" / "manifest.sqlite3").read_bytes())
        evidence = {record["id"]: record for record in case["evidence"]}
        order = ARMS[case_index % len(ARMS):] + ARMS[:case_index % len(ARMS)]
        for arm in order:
            matches = [row for row in rows if row["scenario"] == case_id and row["arm"] == arm
                       and row["budget"] == PROTOCOL["context_budget"]]
            if len(matches) != 1:
                raise ValueError("Missing or duplicate frozen retrieval condition")
            row = matches[0]
            context = (directory / f"context-{arm}-{PROTOCOL['context_budget']}.jsonl").read_text()
            ids = verify_context(context, row, counter)
            if row["corpus_sha256"] != case["corpus_sha256"]:
                raise ValueError("Context corpus differs from its source case")
            if row["fixture_manifest_sha256"] != run["fixture_manifest_sha256"]:
                raise ValueError("Context fixture differs from source run")
            for line in context.splitlines():
                if line.strip():
                    record = json.loads(line)
                    if record != evidence.get(record["id"]):
                        raise ValueError("Presented record differs from the common frozen evidence corpus")
            request = request_from_evidence(case["query"], context)
            relative = f"{case_id}/{arm}/request.json"
            write_json(output / relative, asdict(request))
            jobs.append({"scenario": case_id, "category": scenarios[case_id].category, "arm": arm,
                         "request_file": relative, "request_file_sha256": sha((output / relative).read_bytes()),
                         "context_sha256": sha(context), "retrieval_context_sha256": row["context_sha256"],
                         "context_tokens_budgeted": row["context_tokens"], "presented_context_tokens": counter(context),
                         "prompt_tokens_cl100k_estimate": counter(request.prompt()),
                         "presented_records": len(ids), "corpus_sha256": row["corpus_sha256"],
                         "retrieval_ms": row["retrieval_ms"], "retrieval_calls": row["retrieval_calls"]})
    manifest = {"protocol": PROTOCOL, "split": split, "source": str(source), "jobs": jobs,
                "prepared_at": datetime.now(timezone.utc).isoformat(), "code": git_state(),
                "code_sha256": code_hashes(), "system_prompt_sha256": sha(SYSTEM_PROMPT),
                "schema_sha256": sha(json.dumps(PLAN_SCHEMA, sort_keys=True)),
                "source_manifest_sha256": sha((source / "run_manifest.json").read_bytes()),
                "case_sha256": case_hashes, "initial_store_sha256": store_hashes,
                "maximum_planner_calls": len(jobs),
                "configured_total_cost_cap_usd": len(jobs) * PROTOCOL["max_budget_usd_per_call"]}
    write_json(output / "prepared.json", manifest)
    return manifest


def read_request(path: Path) -> AgentRequest:
    data = read_json(path)
    if set(data) != {"task", "changed_ids", "context_text", "allowed_artifact_ids"}:
        raise ValueError("Unexpected fields in prepared label-free request")
    request = AgentRequest(data["task"], tuple(data["changed_ids"]), data["context_text"],
                           tuple(data["allowed_artifact_ids"]))
    request.validate()
    return request


def run_plan(provider: Any, request: AgentRequest) -> tuple[AgentPlan | None, dict[str, Any]]:
    """Retain paid failures and abstentions without retrying or inventing success."""
    try:
        plan = plan_refresh(provider, request)
        return plan, {"status": "abstained" if plan.abstain else "planned", "plan": plan.to_dict()}
    except Exception as exc:
        result = getattr(exc, "provider_result", None)
        return None, {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                      "provider_result": asdict(result) if result is not None else None,
                      "provider_evidence": getattr(exc, "evidence", {}), "no_retry": True}


def reopen_workload(directory: Path, case: dict[str, Any], scenario: Any) -> Any:
    from proofflow.artifacts import ArtifactStore
    from proofflow.graph import HydraGraph
    from proofflow.runtime import ProofFlowRuntime
    from proofflow.eval.cases import PERIODS, heldout_recipe, recipes
    from proofflow.eval.workload import Workload

    store = ArtifactStore(directory / "initial")
    try:
        graph = HydraGraph(namespace=case["graph_namespace"])
    except Exception:
        store.close()
        raise
    declarations = [recipe for period in PERIODS for recipe in recipes(period)]
    if scenario.additional_composition:
        declarations.append(heldout_recipe())
    refs = {record.logical_id.removeprefix("artifact:"): record for record in store.heads()}
    return Workload(ProofFlowRuntime(store, graph), {}, declarations, refs, case["graph_namespace"])


def run(prepared: Path, *, allow_test: bool = False) -> dict[str, Any]:
    from proofflow.eval.cases import SCENARIOS
    from proofflow.eval.execution import run_refresh_check
    from proofflow.eval.retrieval import score_sets

    prepared = prepared.resolve()
    manifest = read_json(prepared / "prepared.json")
    guard_test(manifest["split"], allow_test)
    if manifest["protocol"] != PROTOCOL or manifest["code_sha256"] != code_hashes():
        raise ValueError("Comparison protocol/code changed after preparation; do not reuse frozen requests")
    source = Path(manifest["source"])
    if manifest["source_manifest_sha256"] != sha((source / "run_manifest.json").read_bytes()):
        raise ValueError("Source retrieval manifest changed after preparation")
    for case_id, digest in manifest["case_sha256"].items():
        if digest != sha((source / case_id / "case.json").read_bytes()):
            raise ValueError("Source case changed after preparation")
        if manifest["initial_store_sha256"][case_id] != sha((source / case_id / "initial/manifest.sqlite3").read_bytes()):
            raise ValueError("Original runtime store changed after preparation")
    requests = []
    for job in manifest["jobs"]:
        path = prepared / job["request_file"]
        if job["request_file_sha256"] != sha(path.read_bytes()):
            raise ValueError("Prepared model request changed")
        requests.append(read_request(path))
    # A start marker prevents an interrupted run from silently retrying paid calls.
    with (prepared / "started.json").open("x") as stream:
        json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "code": git_state()}, stream)
    provider = ClaudeCLIProvider(model=PROTOCOL["model"], effort=PROTOCOL["effort"],
                                 timeout_seconds=PROTOCOL["timeout_seconds"],
                                 max_budget_usd=PROTOCOL["max_budget_usd_per_call"], cwd=ROOT)
    observations = []
    # All planning finishes before any arm gets to execute. The provider has
    # only a request; this loop does not load gold labels or runtime state.
    for job, request in zip(manifest["jobs"], requests, strict=True):
        path = prepared / job["scenario"] / job["arm"]
        write_json(path / "attempt.json", {"started_at": datetime.now(timezone.utc).isoformat(), **job})
        print(f"[{job['scenario']}] model plan: {job['arm']}", flush=True)
        plan, observation = run_plan(provider, request)
        observation.update(job)
        write_json(path / "observation.json", observation)
        observations.append((job, request, plan, observation))
    scenarios = {scenario.id: scenario for scenario in SCENARIOS}
    rows = []
    for job, request, plan, observation in observations:
        row = {**observation, "execution": None, "impact": None}
        if plan is not None:
            workload = None
            try:
                case = read_json(source / job["scenario"] / "case.json")
                scenario = scenarios[job["scenario"]]
                workload = reopen_workload(source / scenario.id, case, scenario)
                # plan_refresh rejects any ID not presented to this arm. Validate
                # every alias/type before the shared evaluator dispatches refresh.
                mapping = {alias: case["alias_to_raw"][alias] for alias in request.allowed_artifact_ids}
                if len(set(mapping.values())) != len(mapping):
                    raise ValueError("Evidence aliases are not one-to-one")
                if any(workload.runtime.store.get(raw).kind != "artifact" for raw in mapping.values()):
                    raise ValueError("Presented selection maps to a non-artifact")
                row["impact"] = score_sets(case["expected_revalidation_ids"], plan.selected_ids)
                row["execution"] = run_refresh_check(
                    workload, scenario, plan.selected_ids, mapping, case["numeric_oracle_values"],
                    case["numeric_oracle_errors"], prepared / scenario.id / job["arm"] / "execution")
            except Exception as exc:
                row["execution_error"] = {"type": type(exc).__name__, "message": str(exc)}
            finally:
                if workload is not None:
                    try:
                        workload.close()
                    except Exception as exc:
                        row["cleanup_error"] = {"type": type(exc).__name__, "message": str(exc)}
        write_json(prepared / job["scenario"] / job["arm"] / "result.json", row)
        rows.append(row)
    summary = summarize(rows)
    write_json(prepared / "summary.json", summary)
    return summary


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    arms = {}
    for arm in ARMS:
        selected = [row for row in rows if row["arm"] == arm]
        executions = [row["execution"] for row in selected if row.get("execution") is not None]
        costs, usage_unknown = [], 0
        for row in selected:
            provider = row.get("plan", {}).get("provider_result") or row.get("provider_result") or {}
            cost = provider.get("reported_cost_usd")
            if cost is None:
                cost = row.get("provider_evidence", {}).get("total_cost_usd")
            if isinstance(cost, (int, float)):
                costs.append(cost)
            else:
                usage_unknown += 1
        eligible = sum(row["eligible_affected_reports"] for row in executions)
        fresh = sum(row["fresh_affected_reports"] for row in executions)
        arms[arm] = {"attempts": len(selected), "model_failures": sum(row["status"] == "failed" for row in selected),
                     "abstentions": sum(row["status"] == "abstained" for row in selected),
                     "scored_executions": len(executions), "fresh_affected_reports": fresh,
                     "eligible_affected_reports": eligible,
                     "fresh_affected_rate_among_scored": fresh / eligible if eligible else None,
                     "execution_failures": sum("execution_error" in row for row in selected),
                     "runtime_refresh_errors": sum(row.get("refresh_completed") is False for row in executions),
                     "tool_calls": sum(row["tool_calls"] for row in executions),
                     "incorrect_current_reports": sum(row["incorrect_current_reports"] for row in executions),
                     "reported_cost_usd_known": sum(costs), "calls_with_unknown_cost": usage_unknown}
    return {"experiment": "Actual local Claude CLI planning followed by shared Hydra-assisted execution",
            "protocol": PROTOCOL, "arms": arms, "results": rows,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "limitations": ["One sample per case/arm; no statistical generalization claimed.",
                            "Failure counts remain in the attempt denominator; scored report rates are explicitly conditional.",
                            "Every arm shares Hydra-assisted safety/recursive refresh; blocking is not a baseline safety comparison.",
                            "Provider costs are reported list estimates, not a claim about subscription billing.",
                            "Exact flat traversal can tie graph correctness; this does not prove a unique database advantage."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--source", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--split", choices=["dev", "test"], required=True)
    prep.add_argument("--allow-test", action="store_true")
    execute = commands.add_parser("run")
    execute.add_argument("--prepared", type=Path, required=True)
    execute.add_argument("--allow-test", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.source, args.output, args.split, allow_test=args.allow_test)
        print(json.dumps({key: result[key] for key in ("split", "maximum_planner_calls", "configured_total_cost_cap_usd")}, indent=2))
    else:
        result = run(args.prepared, allow_test=args.allow_test)
        print(json.dumps(result["arms"], indent=2))


if __name__ == "__main__":
    main()
