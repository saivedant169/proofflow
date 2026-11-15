import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from proofflow.agent import AgentProviderError, ProviderResult
from proofflow.eval.cases import SCENARIOS
from proofflow.eval.retrieval import TokenCounter
from scripts import agent_compare as comparison


def frozen_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    case_dir = source / "D02"
    (case_dir / "initial").mkdir(parents=True)
    (case_dir / "initial/manifest.sqlite3").write_bytes(b"immutable fake store")
    record = {"id": "artifact:report@1", "inputs": ["source:fx@1"]}
    context = json.dumps(record, sort_keys=True, separators=(",", ":"))
    case = {
        "scenario": next(case.to_dict() for case in SCENARIOS if case.id == "D02"),
        "query": {"text": "Revalidate the report", "changed_ids": ["source:fx@1"]},
        "evidence": [record], "corpus_sha256": "corpus",
        "alias_to_raw": {record["id"]: "raw-report"},
        "expected_revalidation_ids": [record["id"]],
        "numeric_oracle_values": {"GOLD_SENTINEL_DO_NOT_PROMPT": 123456789},
        "numeric_oracle_errors": {},
    }
    comparison.write_json(case_dir / "case.json", case)
    comparison.write_json(source / "run_manifest.json", {
        "split": "dev", "finished_at": "frozen", "scenarios": ["D02"],
        "fixture_manifest_sha256": "fixture",
    })
    rows = []
    for arm in comparison.ARMS:
        (case_dir / f"context-{arm}-2048.jsonl").write_text(context + "\n")
        rows.append({"scenario": "D02", "arm": arm, "budget": 2048,
                     "context_sha256": comparison.sha(context), "retrieved_ids": [record["id"]],
                     "context_tokens": TokenCounter()(context), "corpus_sha256": "corpus",
                     "fixture_manifest_sha256": "fixture", "retrieval_ms": 1, "retrieval_calls": 1})
    (source / "retrieval.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return source


def test_prepare_exports_only_exact_context_and_query_without_gold(tmp_path):
    output = tmp_path / "prepared"
    manifest = comparison.prepare(frozen_source(tmp_path), output, "dev")
    assert manifest["maximum_planner_calls"] == 4
    assert manifest["configured_total_cost_cap_usd"] == 4
    for job in manifest["jobs"]:
        request = comparison.read_request(output / job["request_file"])
        assert "GOLD_SENTINEL" not in request.prompt()
        assert set(json.loads(request.prompt())) == {"task", "changed_ids", "evidence_jsonl"}
        assert request.context_text.endswith("\n")


def test_tampered_context_rejected_before_preparation(tmp_path):
    source = frozen_source(tmp_path)
    path = source / "D02/context-dense-2048.jsonl"
    path.write_text('{"id":"hidden-id","inputs":[]}\n')
    with pytest.raises(ValueError, match="hash mismatch"):
        comparison.prepare(source, tmp_path / "prepared", "dev")


def test_tampered_prepared_request_never_calls_provider(tmp_path, monkeypatch):
    output = tmp_path / "prepared"
    manifest = comparison.prepare(frozen_source(tmp_path), output, "dev")
    request_file = output / manifest["jobs"][0]["request_file"]
    request_file.write_text(request_file.read_text().replace("Revalidate", "Changed"))
    def forbidden(**kwargs):
        raise AssertionError("Provider must not be initialized")
    monkeypatch.setattr(comparison, "ClaudeCLIProvider", forbidden)
    with pytest.raises(ValueError, match="request changed"):
        comparison.run(output)
    assert not (output / "started.json").exists()


def test_all_model_plans_precede_execution_and_gold_stays_out(tmp_path, monkeypatch):
    output = tmp_path / "prepared"
    comparison.prepare(frozen_source(tmp_path), output, "dev")
    prompts, executions = [], []
    class Provider:
        def __init__(self, **kwargs):
            pass
        def generate(self, prompt, schema):
            prompts.append(prompt)
            assert "GOLD_SENTINEL" not in prompt
            return ProviderResult({"selected_ids": ["artifact:report@1"], "rationale": "Direct input", "abstain": False},
                                  reported_cost_usd=0.25, model="stub")
    monkeypatch.setattr(comparison, "ClaudeCLIProvider", Provider)
    monkeypatch.setattr(comparison, "reopen_workload", lambda *args: SimpleNamespace(
        runtime=SimpleNamespace(store=SimpleNamespace(get=lambda _: SimpleNamespace(kind="artifact"))),
        close=lambda: None))
    def refresh_check(workload, scenario, selected, mapping, values, errors, path):
        assert len(prompts) == 4
        assert mapping == {"artifact:report@1": "raw-report"}
        assert "GOLD_SENTINEL_DO_NOT_PROMPT" in values
        executions.append(path)
        return {"eligible_affected_reports": 1, "fresh_affected_reports": 1,
                "tool_calls": 1, "incorrect_current_reports": 0}
    monkeypatch.setattr("proofflow.eval.execution.run_refresh_check", refresh_check)
    summary = comparison.run(output)
    assert len(executions) == 4
    assert summary["arms"]["dense"]["reported_cost_usd_known"] == 0.25
    assert summary["arms"]["graph"]["fresh_affected_rate_among_scored"] == 1
    with pytest.raises(FileExistsError):
        comparison.run(output)
    assert len(prompts) == 4


def test_provider_failure_is_retained_without_retry_and_unknown_cost_is_not_zero():
    class Provider:
        calls = 0
        def generate(self, *args):
            self.calls += 1
            raise AgentProviderError("timeout", evidence={"usage_unknown": True})
    provider = Provider()
    request = comparison.request_from_evidence({"text": "Revalidate", "changed_ids": ["source@1"]},
                                               '{"id":"artifact@1","inputs":["source@1"]}\n')
    plan, row = comparison.run_plan(provider, request)
    assert plan is None and provider.calls == 1 and row["no_retry"]
    summary = comparison.summarize([{**row, "arm": "bm25", "execution": None}])
    assert summary["arms"]["bm25"]["model_failures"] == 1
    assert summary["arms"]["bm25"]["calls_with_unknown_cost"] == 1


def test_runtime_initialization_failure_preserves_all_paid_observations(tmp_path, monkeypatch):
    output = tmp_path / "prepared"
    comparison.prepare(frozen_source(tmp_path), output, "dev")
    class Provider:
        def __init__(self, **kwargs):
            pass
        def generate(self, *args):
            return ProviderResult({"selected_ids": [], "rationale": "No decision", "abstain": True},
                                  reported_cost_usd=0.25, model="stub")
    monkeypatch.setattr(comparison, "ClaudeCLIProvider", Provider)
    def unavailable(*args):
        raise OSError("Hydra unavailable")
    monkeypatch.setattr(comparison, "reopen_workload", unavailable)
    summary = comparison.run(output)
    assert len(summary["results"]) == 4
    assert all(row["execution_error"]["type"] == "OSError" for row in summary["results"])
    assert all(value["reported_cost_usd_known"] == 0.25 for value in summary["arms"].values())
    assert all(value["execution_failures"] == 1 for value in summary["arms"].values())


def test_heldout_gate_before_any_source_read(tmp_path):
    with pytest.raises(ValueError, match="explicit --allow-test"):
        comparison.prepare(tmp_path / "missing", tmp_path / "output", "test")
