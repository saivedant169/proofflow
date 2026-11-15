"""Study protocol checks with synthetic requests; no Hydra or paid calls."""
from argparse import Namespace
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from proofflow.agent import AgentProtocolError, AgentRequest
from proofflow.eval import model_cli_v4, model_scoring_v4, model_study_v4 as study


def counts(case):
    return {"reports": 11, "eligible_reports": 7 if case == "M07" else 11,
            "eligible_affected_reports": 0 if case in {"M07", "M08"} else 3,
            "unavailable_reports": 4 if case == "M07" else 0,
            "unaffected_reports": 7 if case == "M07" else 11 if case == "M08" else 8}


def observed(job):
    case = job["case_id"]
    return {**job, "status": "abstained" if case == "M07" else "planned",
            "plan": {"selected_ids": [] if case in {"M07", "M08"} else ["artifact"],
                     "abstain": case == "M07", "rationale": "Synthetic unit test"},
            "score": {"absolute_correct": True, "semantic_endstate_correct": True,
                      "scoring_errors": [], "raw_execution": {},
                      "verified_reports_counts": {"fresh_affected": counts(case)["eligible_affected_reports"],
                                                  "incorrect_current": 0}},
            "usage": {"provider_input_exposure": 100 if job["arm"] == "graph" else 400,
                      "input_tokens": 10, "cache_creation_input_tokens": 20,
                      "cache_read_input_tokens": 70, "output_tokens": 5,
                      "num_turns": 2}, "known_cost_usd": 0.01}


def fixture():
    cases = []
    for case in study.PROTOCOL["test_cases"]:
        cases.append({"case_id": case, "case_path": case + ".json", "requests_by_arm": {
            arm: {"request_path": case + arm, "request_file_sha256": "file",
                  "request_sha256": "prompt", "context_sha256": "context",
                  "evidence_tokens": 100 if arm == "graph" else 400,
                  "evidence_budget": None if arm == "full_context" else 100} for arm in study.ARMS}})
    prepared = {"cases": cases, "jobs": study.schedule(cases)}
    return prepared, [observed(job) for job in prepared["jobs"]]


def summarize(prepared, rows, **kwargs):
    return study.summarize(prepared, rows, integrity=kwargs.get("integrity", True), ledger={},
                           planned_counts={case: counts(case) for case in study.PROTOCOL["test_cases"]})


def test_rotation_is_fixed_complete_and_uses_evidence_budget():
    prepared, _ = fixture()
    assert len({job["job_id"] for job in prepared["jobs"]}) == 48
    for index, case in enumerate(study.PROTOCOL["test_cases"]):
        jobs = [job for job in prepared["jobs"] if job["case_id"] == case]
        offset = index % 6
        assert [job["arm"] for job in jobs] == [*study.ARMS[offset:], *study.ARMS[:offset]]
        assert next(job for job in jobs if job["arm"] == "full_context")["evidence_budget"] is None


def test_complete_absolute_reliability_with_missing_abstention_and_noop():
    prepared, rows = fixture()
    result = summarize(prepared, rows)
    assert result["complete_study"] and result["primary"]["passed"]
    assert result["primary"]["non_noop_provider_input_ratio"] == 0.25
    graph = next(row for row in result["arms"] if row["arm"] == "graph")
    assert graph["model_task_success_cases"] == 8
    assert graph["safe_explicit_abstentions"] == 1
    assert graph["fresh_affected_reports_observed"] == 18


@pytest.mark.parametrize("case", ["M01", "M07", "M08"])
def test_invalid_plan_never_passes_safe_unchanged_state(case):
    prepared, rows = fixture()
    row = next(row for row in rows if row["case_id"] == case and row["arm"] == "graph")
    row.update(status="invalid_plan", model_error={"message": "Bad JSON"})
    row.pop("plan")
    result = summarize(prepared, rows)
    assert result["complete_study"]  # A known, scored bad answer is an observation.
    assert not result["primary"]["passed"]
    assert not result["primary"]["absolute_graph_reliability"]


@pytest.mark.parametrize("case,selected,abstain,expected_refusal,wanted", [
    ("M01", [], False, False, False), ("M01", [], True, False, False),
    ("M01", ["artifact"], False, False, True),
    ("M07", [], True, False, True), ("M07", [], False, False, False),
    ("M07", ["artifact"], False, False, False),
    ("M07", ["artifact"], False, True, True),
    ("M08", [], False, False, True), ("M08", [], True, False, False),
    ("M08", ["artifact"], False, False, False),
])
def test_explicit_decision_gate(case, selected, abstain, expected_refusal, wanted):
    row = observed({"case_id": case, "arm": "graph"})
    row.update(status="abstained" if abstain else "planned")
    row["plan"].update(selected_ids=selected, abstain=abstain)
    row["score"]["raw_execution"]["expected_source_unavailable_refusal"] = expected_refusal
    assert study.model_task_outcome(row, counts(case))["model_task_success"] is wanted


def test_non_noop_ratio_cannot_be_improved_by_free_noop_input():
    prepared, rows = fixture()
    for row in rows:
        row["usage"]["provider_input_exposure"] = (0 if row["arm"] == "graph" else 100000) if row["case_id"] == "M08" else 100
    result = summarize(prepared, rows)
    assert result["primary"]["non_noop_provider_input_ratio"] == 1
    assert result["secondary"]["including_noop_provider_input_ratio"] < 0.01
    assert not result["primary"]["passed"]


@pytest.mark.parametrize("problem", ["absent", "unknown_usage", "unscored", "infra", "duplicate", "integrity"])
def test_incomplete_study_preserves_planned_denominators_and_unknown_cells(problem):
    prepared, rows = fixture()
    if problem == "absent": rows.pop()
    if problem == "unknown_usage": rows[0]["usage"] = None
    if problem == "unscored": rows[0]["score"] = None
    if problem == "infra": rows[0]["infrastructure_error"] = {"message": "timeout"}
    if problem == "duplicate": rows.append(deepcopy(rows[0]))
    result = summarize(prepared, rows, integrity=problem != "integrity")
    assert not result["complete_study"]
    assert not result["primary"]["passed"]
    assert result["primary"]["non_noop_provider_input_ratio"] is None
    assert len(result["cells"]) == 48
    assert all(row["planned_report_counts"]["reports"] == 88 for row in result["arms"])
    if problem == "absent":
        assert result["cells"][-1]["usage"] is None
        assert result["cells"][-1]["score"] is None


def envelope():
    return {"total_cost_usd": 0.02, "num_turns": 2, "is_error": False,
            "modelUsage": {"claude-fable-5-2": {"inputTokens": 10, "cacheCreationInputTokens": 20,
                "cacheReadInputTokens": 70, "outputTokens": 5, "costUSD": 0.02}},
            "structured_output": {"selected_ids": [], "rationale": "No records supplied", "abstain": False}}


def test_decode_plan_is_bound_to_exact_evidence_and_rejects_hidden_ids():
    request = AgentRequest("Check", (), "", ())
    data = envelope()
    usage = study.normalize_usage(data)
    plan = study.decode_plan(data, request, usage, 1)
    assert plan.request_sha256 == hashlib.sha256(request.prompt().encode()).hexdigest()
    data["structured_output"]["selected_ids"] = ["hidden"]
    with pytest.raises(AgentProtocolError): study.decode_plan(data, request, usage, 1)


def test_inner_json_duplicate_schema_fields_are_invalid():
    data = envelope()
    data.pop("structured_output")
    data["result"] = '{"selected_ids":[],"rationale":"x","abstain":true,"abstain":false}'
    with pytest.raises(AgentProtocolError):
        study.decode_plan(data, AgentRequest("Check", (), "", ()), study.normalize_usage(data), 1)


@pytest.mark.parametrize("field", ["request_file_sha256", "request_sha256", "context_sha256"])
def test_per_cell_request_checks_every_hash(tmp_path, field):
    request = AgentRequest("Check", (), "", ())
    path = tmp_path / "request.json"
    study.write_json(path, {"task": "Check", "changed_ids": [], "context_text": "", "allowed_artifact_ids": []})
    job = {"request_path": str(path), "request_file_sha256": study.sha_file(path),
           "request_sha256": hashlib.sha256(request.prompt().encode()).hexdigest(),
           "context_sha256": hashlib.sha256(b"").hexdigest()}
    assert study.verified_request(job) == request
    job[field] = "modified"
    with pytest.raises(ValueError): study.verified_request(job)


def test_study_ledger_location_cannot_reset_allowance(tmp_path):
    assert study.require_study_state(study.DEFAULT_STUDY_STATE) == study.DEFAULT_STUDY_STATE
    with pytest.raises(ValueError): study.require_study_state(tmp_path / "fresh_ledger")


@pytest.mark.parametrize("problem", ["external", "untracked", "changed", "none"])
def test_preparation_is_bound_to_approved_commit_bytes(tmp_path, monkeypatch, problem):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(study, "ROOT", root)
    path = (tmp_path if problem == "external" else root) / "prepared"
    path.mkdir()
    (path / "prepared.json").write_text('{"frozen":true}\n')
    blob = b'changed' if problem == "changed" else (path / "prepared.json").read_bytes()
    monkeypatch.setattr(study.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=1 if problem == "untracked" else 0, stdout=blob))
    if problem == "none":
        assert study.require_committed_preparation(path, "approved") == hashlib.sha256(blob).hexdigest()
    else:
        with pytest.raises(ValueError): study.require_committed_preparation(path, "approved")


def artifact_fixture(directory):
    case_dir = directory / "M01"
    case = {"case_id": "M01", "case_path": str(case_dir / "case.json"), "requests_by_arm": {}}
    for key, suffix in (("initial_store_path", "initial"), ("source_values_path", "current_sources.json"),
                        ("initial_records_path", "initial_records.json"), ("corpus_path", "corpus.jsonl")):
        case[key] = str(case_dir / suffix)
        if key == "initial_store_path": (case_dir / suffix).mkdir(parents=True)
        else: (case_dir / suffix).write_text("{}")
    for arm in study.ARMS:
        info = case["requests_by_arm"][arm] = {}
        for key, name in (("request_path", "request.json"), ("context_path", "context.jsonl"), ("prompt_path", "prompt.txt")):
            path = case_dir / "requests" / arm / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            info[key] = str(path)
    study.write_json(case_dir / "case.json", case)
    manifest = {"cases": [case], "artifact_sha256": {str(p.relative_to(directory)): study.sha_file(p)
                for p in directory.rglob("*") if p.is_file()}}
    study.write_json(directory / "prepared.json", manifest)
    return manifest


@pytest.mark.parametrize("problem", ["extra", "removed", "changed", "embedded_case", "external_source", "external_request"])
def test_prepared_inventory_and_all_scored_paths_are_anchored(tmp_path, problem):
    directory = tmp_path / "prepared"
    manifest = artifact_fixture(directory)
    study.validate_artifacts(directory, manifest)
    case = manifest["cases"][0]
    if problem == "extra": (directory / "extra.txt").write_text("new")
    if problem == "removed": (directory / "M01/corpus.jsonl").unlink()
    if problem == "changed": (directory / "M01/corpus.jsonl").write_text("modified")
    if problem == "embedded_case": case["extra"] = "unhashed metadata"
    if problem in {"external_source", "external_request"}:
        outside = tmp_path / "outside.json"
        outside.write_text("{}")
        if problem == "external_source": case["source_values_path"] = str(outside)
        else: case["requests_by_arm"]["graph"]["request_path"] = str(outside)
        study.write_json(directory / "M01/case.json", case)
        manifest["artifact_sha256"]["M01/case.json"] = study.sha_file(directory / "M01/case.json")
    with pytest.raises(ValueError): study.validate_artifacts(directory, manifest)


@pytest.mark.parametrize("problem", ["unknown_usage", "unknown_billing", "timeout", "overshoot"])
def test_paid_loop_stops_after_one_failed_fake_call_and_keeps_cost(tmp_path, monkeypatch, problem):
    prepared, _ = fixture()
    directory = tmp_path / "prepared"
    directory.mkdir()
    request = AgentRequest("Synthetic orchestration check", (), "", ())
    request_path = directory / "request.json"
    study.write_json(request_path, {"task": request.task, "changed_ids": [], "context_text": "", "allowed_artifact_ids": []})
    for job in prepared["jobs"]:
        job.update(request_path=str(request_path), request_file_sha256=study.sha_file(request_path),
                   request_sha256=hashlib.sha256(request.prompt().encode()).hexdigest(),
                   context_sha256=hashlib.sha256(request.context_text.encode()).hexdigest())
    prepared["freeze_path"], prepared["freeze_sha256"] = str(tmp_path / "freeze.json"), "freeze"
    study.write_json(directory / "prepared.json", prepared)
    monkeypatch.setattr(study, "require_clean_revision", lambda *a: {"revision": "frozen"})
    monkeypatch.setattr(study, "require_committed_preparation", lambda *a: study.sha_file(directory / "prepared.json"))
    monkeypatch.setattr(study, "require_study_state", lambda p: p)
    monkeypatch.setattr(study, "validate_prepared", lambda *a: None)
    monkeypatch.setattr(study, "verify_freeze", lambda *a: "freeze")
    monkeypatch.setattr(study, "DenseEncoder", lambda *a: None)
    monkeypatch.setattr(model_scoring_v4, "planned_report_counts", lambda case: counts(case["case_id"]))
    monkeypatch.setattr(model_scoring_v4, "score_selection", lambda *a: observed({"case_id": "M01", "arm": "graph"})["score"])
    calls = []
    def fake_invoke(*args):
        calls.append(args)
        data = envelope()
        if problem == "unknown_usage": del data["modelUsage"]["claude-fable-5-2"]["inputTokens"]
        if problem == "unknown_billing": del data["total_cost_usd"]
        if problem == "overshoot":
            data["total_cost_usd"] = data["modelUsage"]["claude-fable-5-2"]["costUSD"] = 1.01
        return {"envelope": data, "process_started": True, "returncode": 0,
                "timed_out": problem == "timeout", "elapsed_seconds": 1}
    monkeypatch.setattr(model_cli_v4, "invoke_cli", fake_invoke)
    args = Namespace(expected_revision="frozen", allow_paid=True, prepared=directory,
                     output=tmp_path / "result", study_state=tmp_path / "ledger", model_cache=tmp_path)
    result = study.run_paid(args)
    assert len(calls) == 1
    assert not result["complete_study"]
    assert result["ledger"]["stopped"]
    assert result["ledger"]["spent_known_usd"] == ("0" if problem == "unknown_billing" else "1.01" if problem == "overshoot" else "0.02")
    assert sum(row["status"] == "unattempted" for row in result["cells"]) == 47
