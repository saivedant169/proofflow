"""Prepare, freeze and run the separately authorized single-shot model study.

No command contacts a model except `run-paid`, which requires a committed
matching prepared study, an explicit paid-run flag and the approved revision.
Development runs use a named deterministic harness proxy, never a model.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

from proofflow.agent import (AgentProtocolError, AgentRequest, PLAN_SCHEMA, SYSTEM_PROMPT,
                            ProviderResult, plan_refresh)
from .model_contexts_v4 import ARMS, RETRIEVAL_CONFIG, prepare_case
from .model_ledger_v4 import StudyLedger, StudyStopped
from .model_usage_v4 import UsageAccountingError, known_cost_usd, normalize_usage
from .retrieval import DenseEncoder, EvidenceRecord, TokenCounter, canonical, read_affected


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STUDY_STATE = Path("/Users/saivedanthava/Desktop/HydraDB/private_experiments/model_comparison_v4/study_state")
PROTOCOL = {
    "version": "model-comparison-v4", "model": "claude-fable-5-2", "effort": "high",
    "arms": list(ARMS), "test_cases": [f"M{i:02}" for i in range(1, 9)],
    "dev_cases": ["MD01", "MD02"], "no_op_case": "M08", "planned_invocations": 48,
    "arm_order": "rotate fixed six-arm list left by case index modulo six",
    "timeout_seconds": 90, "reported_cost_soft_stop_usd": 10.0, "per_invocation_cap_usd": 1.0,
    "harness_attempts_per_cell": 1, "harness_retries": 0, "model_fallback": False,
    "maximum_no_model_dev_runs": 2,
    "study_state_directory": str(DEFAULT_STUDY_STATE),
    "study_identity": "proofflow-model-comparison-v4-2026-11-15",
    "input_exposure": "modelUsage inputTokens + cacheCreationInputTokens + cacheReadInputTokens; top-level usage is not added",
    "primary_ratio_cases": "all non-no-op planned cases; including-no-op ratio is secondary",
    "primary_input_ratio_maximum": 0.5,
    "absolute_reliability": "Schema-valid graph plans; non-abstaining complete recovery when recoverable affected reports exist; valid empty non-abstaining no-op; missing-only explicit abstention or expected execution refusal; independent numeric/provenance-current, zero incorrect-current and immutable originals preserved",
    "complete_study": "all 48 planned cells attempted once, usage/billing known and scored; missing cells are not zero-filled",
    "shared_executor": "Every arm uses the same frozen Hydra-assisted currentness and recursive refresh executor; standalone vector safety not evaluated",
    "invocation_scope": "one harness invocation may contain multiple CLI/provider turns; num_turns and aggregate usage retained",
    "retrieval": RETRIEVAL_CONFIG,
}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def failure(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def git_state() -> dict[str, Any]:
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"revision": git("rev-parse", "HEAD"), "status": git("status", "--porcelain", "--untracked-files=all")}


def code_hashes() -> dict[str, str]:
    paths = [*(ROOT / "proofflow").rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]
    paths += [ROOT / "pyproject.toml", ROOT / "uv.lock",
              ROOT / "docs/MODEL_COMPARISON_PROTOCOL.md", ROOT / "docs/MODEL_COMPARISON_DATA_SPEC.md"]
    return {str(path.relative_to(ROOT)): sha_file(path) for path in sorted(paths) if path.is_file()}


def cli_identity() -> dict[str, str]:
    executable = shutil.which("claude")
    if executable is None:
        raise ValueError("Claude CLI is not installed; do not substitute another provider")
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=20, check=True)
    return {"version": result.stdout.strip(), "executable_sha256": sha_file(Path(executable).resolve())}


def freeze_payload(encoder: DenseEncoder) -> dict[str, Any]:
    from .model_comparison_data import fixture_file_hashes, manifest_data
    model = encoder.metadata()
    return {"protocol": PROTOCOL, "code_sha256": code_hashes(),
            "fixtures": {split: manifest_data(split) for split in ("dev", "test")},
            "fixture_files": {split: fixture_file_hashes(split) for split in ("dev", "test")},
            "embedding": {key: value for key, value in model.items() if key not in {"cache_dir", "model_directory"}},
            "environment": {"python": sys.version, "packages": {
                name: importlib.metadata.version(name) for name in
                ("tiktoken", "rank-bm25", "fastembed", "numpy", "onnxruntime", "tokenizers", "httpx")}},
            "cli": cli_identity(), "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
            "plan_schema_sha256": hashlib.sha256(canonical(PLAN_SCHEMA).encode()).hexdigest()}


def verify_freeze(path: Path, encoder: DenseEncoder) -> str:
    actual = read_json(path)
    expected = freeze_payload(encoder)
    if canonical(actual) != canonical(expected):
        changed = [key for key in expected if canonical(actual.get(key)) != canonical(expected[key])]
        raise ValueError(f"Frozen model-study inputs changed: {changed}")
    return sha_file(path)


def require_clean_revision(expected: str | None, explicit: bool) -> dict[str, Any]:
    if not explicit or not expected:
        raise ValueError("Explicit root authorization and an exact approved revision are required")
    state = git_state()
    if state["revision"] != expected or state["status"]:
        raise ValueError("The study must use the approved exact revision and a clean committed tree")
    return state


def require_study_state(path: Path) -> Path:
    if path.resolve() != DEFAULT_STUDY_STATE.resolve():
        raise ValueError("The fixed study ledger cannot be replaced to reset spending or attempts")
    return DEFAULT_STUDY_STATE


def require_committed_preparation(directory: Path, revision: str) -> str:
    path = (directory / "prepared.json").resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Prepared manifest must belong to the approved repository")
    relative = str(path.relative_to(ROOT.resolve()))
    blob = subprocess.run(["git", "show", f"{revision}:{relative}"], cwd=ROOT,
                          capture_output=True, check=False)
    if blob.returncode != 0 or blob.stdout != path.read_bytes():
        raise ValueError("Prepared manifest bytes must match a tracked blob at the approved revision")
    return hashlib.sha256(blob.stdout).hexdigest()


def request_from_data(data: dict[str, Any]) -> AgentRequest:
    if set(data) != {"task", "changed_ids", "context_text", "allowed_artifact_ids"}:
        raise ValueError("Unexpected field in label-free model request")
    request = AgentRequest(data["task"], tuple(data["changed_ids"]), data["context_text"], tuple(data["allowed_artifact_ids"]))
    request.validate()
    return request


def read_request(path: Path) -> AgentRequest:
    return request_from_data(read_json(path))


def verified_request(job: dict[str, Any]) -> AgentRequest:
    raw = Path(job["request_path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != job["request_file_sha256"]:
        raise ValueError("Prepared request file changed")
    request = request_from_data(json.loads(raw))
    if (hashlib.sha256(request.prompt().encode()).hexdigest() != job["request_sha256"]
            or hashlib.sha256(request.context_text.encode()).hexdigest() != job["context_sha256"]):
        raise ValueError("Prepared prompt or evidence changed")
    return request


def schedule(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs = []
    for index, case in enumerate(cases):
        offset = index % len(ARMS)
        for arm in (*ARMS[offset:], *ARMS[:offset]):
            info = case["requests_by_arm"][arm]
            jobs.append({"job_id": f"{case['case_id']}:{arm}", "case_id": case["case_id"], "arm": arm,
                         "case_path": case["case_path"], "request_path": info["request_path"],
                         "request_file_sha256": info["request_file_sha256"],
                         "request_sha256": info["request_sha256"], "context_sha256": info["context_sha256"],
                         "evidence_tokens": info["evidence_tokens"], "evidence_budget": info["evidence_budget"]})
    return jobs


def prepare(output: Path, split: str, encoder: DenseEncoder, *, freeze_path: Path | None = None) -> dict[str, Any]:
    from .model_comparison_data import scenarios
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = scenarios(split)
    if [case.id for case in cases] != PROTOCOL[f"{split}_cases"]:
        raise ValueError("Case order/list differs from the preregistered model study")
    started = time.perf_counter()
    manifest = {"protocol": PROTOCOL, "split": split, "prepared_at": datetime.now(timezone.utc).isoformat(),
                "code_sha256": code_hashes(), "cases": [], "jobs": [], "complete": False,
                "freeze_path": str(freeze_path.resolve()) if freeze_path else None,
                "freeze_sha256": sha_file(freeze_path) if freeze_path else None,
                "provider_calls": 0, "model_outcomes_observed": False}
    write_json(output / "prepared.json", manifest)
    try:
        counter = TokenCounter(PROTOCOL["retrieval"]["tokenizer"])
        for case in cases:
            print(f"[{case.id}] prepare identical-information contexts, no model", flush=True)
            manifest["cases"].append(prepare_case(output / case.id, case, encoder, counter))
        manifest["jobs"] = schedule(manifest["cases"])
        manifest["artifact_sha256"] = {str(path.relative_to(output)): sha_file(path)
                                       for path in sorted(output.rglob("*"))
                                       if path.is_file() and path != output / "prepared.json"}
        manifest["complete"] = True
    except Exception as exc:
        manifest["preparation_error"] = failure(exc)
        raise
    finally:
        manifest["elapsed_ms"] = (time.perf_counter() - started) * 1000
        write_json(output / "prepared.json", manifest)
    return manifest


def dry_run(args: argparse.Namespace) -> dict[str, Any]:
    from .model_scoring_v4 import score_selection
    if args.output.exists():
        raise ValueError("Preserve every prior dry-run directory; choose a new path")
    ledger = StudyLedger(require_study_state(args.study_state))
    number = ledger.begin_dry_run(str(args.output.resolve()))
    args.output.mkdir(parents=True, exist_ok=False)
    started, rows = time.perf_counter(), []
    manifest = {"dry_run_number": number, "model_calls": 0, "kind": "no-model development harness check",
                "code_sha256": code_hashes(), "finished": False, "results": rows}
    write_json(args.output / "dry_run.json", manifest)
    try:
        encoder = DenseEncoder(PROTOCOL["retrieval"]["dense_model"], args.model_cache)
        prepared = prepare(args.output / "prepared", "dev", encoder)
        by_case = {case["case_id"]: case for case in prepared["cases"]}
        for job in prepared["jobs"]:
            request = verified_request(job)
            records = [EvidenceRecord(**json.loads(line)) for line in request.context_text.splitlines() if line]
            selected = list(read_affected(records, request.changed_ids))
            print(f"[{job['job_id']}] deterministic executor/oracle smoke check, no model", flush=True)
            row = {**job, "selection_source": "deterministic selected-evidence harness proxy, not a model plan",
                   "proxy_selected_ids": selected,
                   "score": score_selection(by_case[job["case_id"]], selected,
                                            args.output / "execution" / job["case_id"] / job["arm"])}
            rows.append(row)
            write_json(args.output / "dry_run.json", manifest)
        validate_artifacts(args.output / "prepared", prepared)
        manifest["finished"] = True
    except Exception as exc:
        manifest["error"] = failure(exc)
        raise
    finally:
        manifest["elapsed_ms"] = (time.perf_counter() - started) * 1000
        manifest["end_code_sha256"] = code_hashes()
        manifest["code_unchanged"] = manifest["code_sha256"] == manifest["end_code_sha256"]
        write_json(args.output / "dry_run.json", manifest)
    return manifest


def validate_artifacts(directory: Path, manifest: dict[str, Any]) -> None:
    """Bind every selector/scorer path to the exact saved evidence inventory."""
    directory = directory.resolve()
    observed = {str(path.relative_to(directory)) for path in directory.rglob("*")
                if path.is_file() and path != directory / "prepared.json"}
    if observed != set(manifest["artifact_sha256"]):
        raise ValueError("Prepared artifact inventory changed")
    for name, expected in manifest["artifact_sha256"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or sha_file(path) != expected:
            raise ValueError(f"Prepared artifact hash mismatch: {name}")
    for case in manifest["cases"]:
        case_directory = directory / case["case_id"]
        path = Path(case["case_path"]).resolve()
        if path != case_directory / "case.json" or canonical(case) != canonical(read_json(path)):
            raise ValueError("Embedded case differs from its frozen case file/path")
        for key, suffix in (("initial_store_path", "initial"), ("source_values_path", "current_sources.json"),
                            ("initial_records_path", "initial_records.json"), ("corpus_path", "corpus.jsonl")):
            if Path(case[key]).resolve() != case_directory / suffix:
                raise ValueError(f"Case path escapes its frozen artifact location: {key}")
        for arm in ARMS:
            info = case["requests_by_arm"][arm]
            for key, name in (("request_path", "request.json"), ("context_path", "context.jsonl"), ("prompt_path", "prompt.txt")):
                if Path(info[key]).resolve() != case_directory / "requests" / arm / name:
                    raise ValueError(f"Arm path escapes its frozen artifact location: {key}")


def validate_prepared(directory: Path, manifest: dict[str, Any]) -> None:
    if (manifest.get("split") != "test" or not manifest.get("complete") or
            manifest.get("protocol") != PROTOCOL or len(manifest.get("jobs", [])) != 48):
        raise ValueError("Paid calls require the complete fixed 48-cell test preparation")
    if [case["case_id"] for case in manifest.get("cases", [])] != PROTOCOL["test_cases"]:
        raise ValueError("Prepared cases differ from the eight fixed planned cases")
    if len({job["job_id"] for job in manifest["jobs"]}) != 48:
        raise ValueError("Prepared cells are not unique")
    if manifest["code_sha256"] != code_hashes():
        raise ValueError("Code changed after request preparation")
    validate_artifacts(directory, manifest)
    if schedule(manifest["cases"]) != manifest["jobs"]:
        raise ValueError("Prepared arm schedule changed")
    for job in manifest["jobs"]:
        verified_request(job)


def decode_plan(envelope: dict[str, Any], request: AgentRequest, usage: dict[str, Any], elapsed_seconds: float):
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate plan field")
            result[key] = value
        return result

    payload = envelope.get("structured_output")
    if payload is None:
        try:
            payload = json.loads(envelope["result"], object_pairs_hook=unique_fields) if isinstance(envelope.get("result"), str) else None
        except (json.JSONDecodeError, ValueError):
            payload = None
    if not isinstance(payload, dict):
        raise AgentProtocolError("Provider returned no complete JSON plan")

    class RecordedProvider:
        def generate(self, _prompt, _schema):
            return ProviderResult(payload, envelope["modelUsage"], envelope.get("usage", {}), usage["cost_usd"],
                                  "Claude Code CLI", PROTOCOL["model"], elapsed_seconds,
                                  {"effort": PROTOCOL["effort"], "num_turns": usage["num_turns"]})
    return plan_refresh(RecordedProvider(), request)


def model_task_outcome(row: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    """Distinguish a valid model decision from a merely safe unchanged state."""
    score, plan = row.get("score") or {}, row.get("plan")
    valid = (row.get("status") in {"planned", "abstained"} and isinstance(plan, dict)
             and not row.get("model_error") and not row.get("infrastructure_error")
             and not row.get("accounting_error") and not row.get("scoring_error"))
    semantic = score.get("semantic_endstate_correct") is True
    selected = plan.get("selected_ids", []) if isinstance(plan, dict) else []
    abstain = plan.get("abstain") if isinstance(plan, dict) else None
    missing_only = counts["eligible_affected_reports"] == 0 and counts["unavailable_reports"] > 0
    safe_abstention = bool(valid and semantic and missing_only and abstain is True and not selected)
    safe_refusal = bool(valid and semantic and missing_only and abstain is False and selected
                        and score.get("raw_execution", {}).get("expected_source_unavailable_refusal") is True)
    if row["case_id"] == PROTOCOL["no_op_case"]:
        decision_ok = valid and abstain is False and not selected
    elif missing_only:
        decision_ok = safe_abstention or safe_refusal
    else:
        decision_ok = valid and abstain is False and bool(selected) and counts["eligible_affected_reports"] > 0
    return {"schema_valid_plan": bool(valid), "semantic_endstate_correct": semantic,
            "model_task_success": bool(decision_ok and semantic),
            "safe_explicit_abstention": safe_abstention, "safe_execution_refusal": safe_refusal}


def summarize(prepared: dict[str, Any], rows: list[dict[str, Any]], *, integrity: bool,
              ledger: dict[str, Any], planned_counts: dict[str, Any]) -> dict[str, Any]:
    planned = prepared["jobs"]
    by_job = {row["job_id"]: row for row in rows}
    cells = []
    for job in planned:
        row = by_job.get(job["job_id"], {**job, "status": "unattempted", "usage": None, "score": None})
        cells.append({**row, "model_task": model_task_outcome(row, planned_counts[job["case_id"]])})
    complete = (len(planned) == 48 and len(by_job) == 48 and len(rows) == 48 and integrity
                and all(row.get("usage") is not None and row.get("score") is not None for row in cells)
                and not any(row.get("infrastructure_error") or row.get("accounting_error") or row.get("scoring_error") for row in cells))
    graph = [row for row in cells if row["arm"] == "graph"]
    graph_reliable = len(graph) == 8 and all(row["model_task"]["model_task_success"] for row in graph)

    def input_ratio(include_noop: bool):
        chosen = [row for row in cells if include_noop or row["case_id"] != PROTOCOL["no_op_case"]]
        groups = {arm: [row for row in chosen if row["arm"] == arm] for arm in ("graph", "full_context")}
        if not complete or any(not values or any(row.get("usage") is None for row in values) for values in groups.values()):
            return None
        sums = {arm: sum(row["usage"]["provider_input_exposure"] for row in values) for arm, values in groups.items()}
        return sums["graph"] / sums["full_context"] if sums["full_context"] else None

    def evidence_ratio(include_noop: bool):
        chosen = [job for job in planned if include_noop or job["case_id"] != PROTOCOL["no_op_case"]]
        sums = {arm: sum(job["evidence_tokens"] for job in chosen if job["arm"] == arm) for arm in ("graph", "full_context")}
        return sums["graph"] / sums["full_context"] if sums["full_context"] else None

    aggregates = []
    for arm in ARMS:
        group = [row for row in cells if row["arm"] == arm]
        known = [row for row in group if row.get("usage") is not None]
        scored = [row for row in group if row.get("score") is not None]
        observed = [row["score"]["verified_reports_counts"] for row in scored]
        aggregates.append({"arm": arm, "planned_cells": len(group), "attempted_cells": sum(row["status"] != "unattempted" for row in group),
                           "usage_known_cells": len(known), "scored_cells": len(scored),
                           "planned_report_counts": {key: sum(value[key] for value in planned_counts.values()) for key in
                               ("reports", "eligible_reports", "eligible_affected_reports", "unavailable_reports", "unaffected_reports")},
                           "fresh_affected_reports_observed": sum(value["fresh_affected"] for value in observed),
                           "absolute_correct_cases": sum(row["score"]["absolute_correct"] for row in scored),
                           "model_task_success_cases": sum(row["model_task"]["model_task_success"] for row in group),
                           "safe_explicit_abstentions": sum(row["model_task"]["safe_explicit_abstention"] for row in group),
                           "safe_execution_refusals": sum(row["model_task"]["safe_execution_refusal"] for row in group),
                           "incorrect_current_reports_observed": sum(value["incorrect_current"] for value in observed),
                           "provider_input_exposure_known": sum(row["usage"]["provider_input_exposure"] for row in known),
                           "uncached_input_tokens_known": sum(row["usage"]["input_tokens"] for row in known),
                           "cache_creation_tokens_known": sum(row["usage"]["cache_creation_input_tokens"] for row in known),
                           "cache_read_tokens_known": sum(row["usage"]["cache_read_input_tokens"] for row in known),
                           "output_tokens_known": sum(row["usage"]["output_tokens"] for row in known),
                           "cli_turns_known": sum(row["usage"]["num_turns"] for row in known),
                           "reported_cost_usd_known": sum(row.get("known_cost_usd") or 0 for row in group)})
    ratio = input_ratio(False)
    fresh_by_arm = {row["arm"]: row["fresh_affected_reports_observed"] for row in aggregates}
    return {"protocol": PROTOCOL, "complete_study": complete, "integrity_verified": integrity,
            "primary": {"absolute_graph_reliability": graph_reliable, "non_noop_provider_input_ratio": ratio,
                        "maximum_ratio": 0.5, "passed": bool(complete and graph_reliable and ratio is not None and ratio <= 0.5)},
            "secondary": {"including_noop_provider_input_ratio": input_ratio(True),
                          "graph_fresh_at_least_full_context": (fresh_by_arm["graph"] >= fresh_by_arm["full_context"] if complete else None),
                          "non_noop_receipt_only_ratio": evidence_ratio(False),
                          "including_noop_receipt_only_ratio": evidence_ratio(True)},
            "arms": aggregates, "cells": cells, "ledger": ledger,
            "limits": [PROTOCOL["shared_executor"], PROTOCOL["invocation_scope"],
                       "One independent sample per cell; no statistical or graph-engine superiority claim.",
                       "Graph and exact-flat matching prompt hashes identify structural twins.",
                       "Receipt tokens and total provider input exposure are distinct; no latency/dollar saving inferred from tokens.",
                       "Unknown and unattempted cells are explicit; an incomplete study cannot pass."]}


def run_paid(args: argparse.Namespace) -> dict[str, Any]:
    from .model_cli_v4 import invoke_cli
    from .model_scoring_v4 import planned_report_counts, score_selection
    state = require_clean_revision(args.expected_revision, args.allow_paid)
    prepared_path = args.prepared.resolve()
    identity = require_committed_preparation(prepared_path, state["revision"])
    manifest = read_json(prepared_path / "prepared.json")
    validate_prepared(prepared_path, manifest)
    encoder = DenseEncoder(PROTOCOL["retrieval"]["dense_model"], args.model_cache)
    freeze_path = Path(manifest["freeze_path"])
    if verify_freeze(freeze_path, encoder) != manifest["freeze_sha256"]:
        raise ValueError("Prepared freeze manifest changed")
    args.output.mkdir(parents=True, exist_ok=False)
    ledger = StudyLedger(require_study_state(args.study_state))
    with (args.output / "started.json").open("x") as stream:
        json.dump({"started_at": datetime.now(timezone.utc).isoformat(), "revision": state["revision"],
                   "prepared_sha256": identity, "planned_cells": 48}, stream)
    rows = []
    by_case = {case["case_id"]: case for case in manifest["cases"]}
    stop_reason = None
    # No oracle is loaded into requests and no execution starts during planning.
    for job in manifest["jobs"]:
        row = {**job, "status": "reserved", "usage": None, "score": None, "known_cost_usd": None}
        try:
            request = verified_request(job)
        except Exception as exc:
            stop_reason = f"Prepared request changed before invocation: {exc}"
            ledger.stop(stop_reason)
            break
        try:
            cap = ledger.reserve(job["job_id"], identity)
        except StudyStopped as exc:
            stop_reason = str(exc)
            break
        rows.append(row)
        attempt = args.output / job["case_id"] / job["arm"]
        print(f"[{job['job_id']}] one authorized planner invocation; configured soft cap ${cap}", flush=True)
        try:
            raw = invoke_cli(request, attempt / "cli", cap, PROTOCOL["timeout_seconds"])
            row["process"] = {key: value for key, value in raw.items() if key != "envelope"}
            envelope = raw.get("envelope")
            row["known_cost_usd"] = known_cost_usd(envelope)
            try:
                row["usage"] = normalize_usage(envelope, PROTOCOL["model"])
            except UsageAccountingError as exc:
                row["accounting_error"] = failure(exc)
            if (raw.get("timed_out") or not raw.get("process_started") or raw.get("returncode") != 0
                    or raw.get("error") or raw.get("parse_error") or not isinstance(envelope, dict)
                    or envelope.get("is_error")):
                row["infrastructure_error"] = {"message": "Provider/process failed; no retry or fallback"}
            if row["usage"] is not None and not row.get("infrastructure_error"):
                try:
                    plan = decode_plan(envelope, request, row["usage"], raw["elapsed_seconds"])
                    row.update(status="abstained" if plan.abstain else "planned", plan=plan.to_dict())
                except AgentProtocolError as exc:
                    row.update(status="invalid_plan", model_error=failure(exc))
            else:
                row["status"] = "provider_failed"
            reason = ("Unknown provider accounting" if row.get("accounting_error") else
                      "Provider/process infrastructure failure" if row.get("infrastructure_error") else None)
            settled = ledger.settle(job["job_id"], row["known_cost_usd"], usage_known=row["usage"] is not None, stop_reason=reason)
            if settled["stopped"]:
                stop_reason = settled["stop_reason"]
        except Exception as exc:
            row.update(status="harness_failed", infrastructure_error=failure(exc))
            ledger.stop("Harness failure with a possibly charged pending attempt; no further invocation")
            stop_reason = str(exc)
        write_json(attempt / "observation.json", row)
        write_json(args.output / "planning_progress.json", {"rows": rows, "stop_reason": stop_reason,
                                                           "ledger": ledger.snapshot()})
        if stop_reason:
            break
    # Scoring is separately authorized local work; no model sees these values.
    planned_counts = {case_id: planned_report_counts(case) for case_id, case in by_case.items()}
    for row in rows:
        selected = list(row.get("plan", {}).get("selected_ids", []))
        try:
            row["score"] = score_selection(by_case[row["case_id"]], selected,
                                            args.output / row["case_id"] / row["arm"] / "execution")
        except Exception as exc:
            row["scoring_error"] = failure(exc)
        write_json(args.output / row["case_id"] / row["arm"] / "result.json", row)
    integrity_error = None
    try:
        if sha_file(prepared_path / "prepared.json") != identity:
            raise ValueError("Prepared study manifest changed during model study")
        validate_prepared(prepared_path, manifest)
        if verify_freeze(freeze_path, encoder) != manifest["freeze_sha256"]:
            raise ValueError("Freeze manifest changed during model study")
    except Exception as exc:
        integrity_error = failure(exc)
    summary = summarize(manifest, rows, integrity=integrity_error is None, ledger=ledger.snapshot(), planned_counts=planned_counts)
    summary.update(stop_reason=stop_reason, integrity_error=integrity_error,
                   finished_at=datetime.now(timezone.utc).isoformat())
    write_json(args.output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-cache", type=Path, default=ROOT / ".cache/fastembed")
    parser.add_argument("--study-state", type=Path, default=DEFAULT_STUDY_STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run")
    dry.add_argument("--output", type=Path, required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--manifest", type=Path, required=True)
    prep = commands.add_parser("prepare-test")
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--manifest", type=Path, required=True)
    prep.add_argument("--expected-revision", required=True)
    prep.add_argument("--allow-test-prepare", action="store_true")
    paid = commands.add_parser("run-paid")
    paid.add_argument("--prepared", type=Path, required=True)
    paid.add_argument("--output", type=Path, required=True)
    paid.add_argument("--expected-revision", required=True)
    paid.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    if args.command == "dry-run":
        result = dry_run(args)
        print(json.dumps({key: result[key] for key in ("dry_run_number", "model_calls", "finished", "code_unchanged")}, indent=2))
    elif args.command == "freeze":
        if args.manifest.exists():
            raise ValueError("Refusing to overwrite a prior model-study freeze")
        encoder = DenseEncoder(PROTOCOL["retrieval"]["dense_model"], args.model_cache)
        write_json(args.manifest, freeze_payload(encoder))
        print(sha_file(args.manifest))
    elif args.command == "prepare-test":
        require_clean_revision(args.expected_revision, args.allow_test_prepare)
        encoder = DenseEncoder(PROTOCOL["retrieval"]["dense_model"], args.model_cache)
        verify_freeze(args.manifest, encoder)
        prepare(args.output, "test", encoder, freeze_path=args.manifest)
    else:
        result = run_paid(args)
        print(json.dumps({"complete_study": result["complete_study"], "primary": result["primary"]}, indent=2))


if __name__ == "__main__":
    main()
