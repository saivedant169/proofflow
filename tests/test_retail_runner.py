"""Tests for benchmark validity gates, not claims about retrieval superiority."""
from types import SimpleNamespace

import pytest

from proofflow.models import ArtifactRecord, Currentness, MissingEvidenceError, RefreshResult, SourceChange
from proofflow.eval import retail_runner as runner
from proofflow.eval.retail_data import RetailCase, RetailMutation


def rows(case="R01", graph_tokens=20, full_tokens=100, exact=True):
    return [{"scenario": case, "arm": arm, "condition": "unlimited",
             "context_tokens": graph_tokens if arm != "full_context" else full_tokens,
             "impact": {"tp": int(exact), "fn": int(not exact), "exact_match": exact, "recall": float(exact)}}
            for arm in runner.RETAIL_CONFIG["production_arms"]]


def executions(correct=True, state="current", value=42):
    return [{"arm": arm, "condition": "unlimited", "oracle_correct": correct,
             "artifacts": [{"name": "month:report", "state": state, "actual_stored_value": value,
                            "preserved_original_artifact": False}]}
            for arm in runner.RETAIL_CONFIG["production_arms"]]


def test_equal_failed_endstates_do_not_pass():
    comparison = runner.compare_case("R01", rows(), executions(False, "stale"))
    assert comparison["production_endstate_parity"]
    assert not comparison["production_correctness_pass"]


def test_recursive_repair_cannot_hide_incomplete_closure():
    comparison = runner.compare_case("R01", rows(exact=False), executions())
    assert comparison["oracle_correct"]
    assert not comparison["exact_production_closures"]
    assert not comparison["production_correctness_pass"]


def test_all_artifact_states_must_match_not_only_numeric_values():
    outcomes = executions()
    outcomes[0]["artifacts"][0]["state"] = "stale"
    comparison = runner.compare_case("R01", rows(), outcomes)
    assert not comparison["production_endstate_parity"]


def test_primary_uses_ratio_of_totals_and_publishes_macro_ratio():
    one = runner.compare_case("R01", rows(graph_tokens=1, full_tokens=10), executions())
    two = runner.compare_case("R02", rows("R02", graph_tokens=90, full_tokens=100), executions())
    summary = runner.summarize(["R01", "R02"], [one, two], [], [], partial=False)
    assert summary["primary"]["ratio_of_total_tokens"] == pytest.approx(91 / 110)
    assert summary["primary"]["mean_per_case_token_ratio"] == pytest.approx(0.5)
    assert not summary["primary"]["passed"]


def test_missing_planned_case_cannot_vanish_from_denominator():
    one = runner.compare_case("R01", rows(), executions())
    summary = runner.summarize(["R01", "R02"], [one], [], [], partial=False)
    assert not summary["complete_run"]
    assert summary["primary"]["ratio_of_total_tokens"] is None
    assert not summary["primary"]["passed"]


def test_failed_case_kept_and_noop_nonempty_diagnostic_separated():
    zero_rows = rows("R00", graph_tokens=0, full_tokens=100)
    for row in zero_rows:
        row["impact"]["tp"] = 0
    noop = runner.compare_case("R00", zero_rows, executions())
    changed = runner.compare_case("R01", rows(graph_tokens=20, full_tokens=100), executions())
    summary = runner.summarize(["R00", "R01"], [noop, changed], [], [], partial=False)
    assert summary["primary"]["ratio_of_total_tokens"] == 0.1
    assert summary["nonempty_impact_diagnostic"]["ratio_of_total_tokens"] == 0.2
    assert summary["primary"]["passed"]
    failed = {"scenario": "R02", "complete": False, "expected_affected_count": None}
    summary = runner.summarize(["R00", "R01", "R02"], [noop, changed, failed], [], [], partial=False)
    assert not summary["primary"]["passed"]


def test_partial_or_unverified_runs_never_pass_primary():
    comparison = runner.compare_case("R01", rows(), executions())
    assert not runner.summarize(["R01"], [comparison], [], [], partial=True)["primary"]["passed"]
    assert not runner.summarize(["R01"], [comparison], [], [], partial=False, integrity_verified=False)["primary"]["passed"]


@pytest.mark.parametrize("allow,revision,status,cases", [
    (False, "abc", "", None), (True, None, "", None), (True, "wrong", "", None),
    (True, "abc", "?? untracked.py", None), (True, "abc", "", ["R01"]),
])
def test_test_gate_rejects_missing_approval_dirty_code_or_subset(allow, revision, status, cases):
    with pytest.raises(ValueError):
        runner.validate_test_gate("test", allow, revision, {"revision": "abc", "status_porcelain": status}, cases)


def test_test_gate_accepts_only_explicit_exact_clean_revision():
    runner.validate_test_gate("test", True, "abc", {"revision": "abc", "status_porcelain": ""}, None)


def test_zero_overwrite_rejects_even_empty_prior_run(tmp_path):
    output = tmp_path / "prior-run"
    output.mkdir()
    with pytest.raises(FileExistsError):
        runner.reserve_output(output)


class FakeStore:
    def __init__(self, record, value):
        self.record, self.value = record, value

    def get_head(self, _):
        return self.record

    def read(self, _):
        return self.value

    def close(self):
        pass


def fake_execution(monkeypatch, tmp_path, *, state="current", value=42, error=None,
                   expected_values=None, expected_errors=None, unavailable=()):
    record = ArtifactRecord("old", "artifact", "artifact:month:report", "hash", "now", {"tool": "compose_report"})
    graph = SimpleNamespace(queries=0, mutations=0, close=lambda: None)

    def refresh(_):
        if error:
            raise error
        return RefreshResult({}, (), (), 0.0)

    runtime = SimpleNamespace(store=FakeStore(record, value), graph=graph, calls=[], refresh=refresh,
                              currentness=lambda _: Currentness("old", state))
    monkeypatch.setattr(runner, "clone_runtime", lambda *_: runtime)
    workload = SimpleNamespace(refs={"month:report": record})
    return runner.execute_selection(workload, ["alias"], {"alias": "old"}, {"month:report"},
                                    {"month:report"}, expected_values or {}, expected_errors or {}, tmp_path / "clone",
                                    unavailable_source_names=unavailable)


def test_stale_equal_numeric_value_is_not_fresh(monkeypatch, tmp_path):
    result = fake_execution(monkeypatch, tmp_path, state="stale", expected_values={"month:report": 42})
    assert not result["oracle_correct"]
    assert result["reports_counts"]["fresh"] == 0


def test_exact_expected_source_refusal_is_visible_and_can_block_correctly(monkeypatch, tmp_path):
    result = fake_execution(monkeypatch, tmp_path, state="stale",
        error=MissingEvidenceError("Source no longer available: source:month:fx"),
        expected_errors={"month:report": "Unavailable source"}, unavailable=["month:fx"])
    assert result["oracle_correct"]
    assert result["expected_source_unavailable_refusal"]
    assert not result["refresh_completed"]
    assert result["refresh_error"]["type"] == "MissingEvidenceError"


@pytest.mark.parametrize("error", [MissingEvidenceError("Cannot refresh incomplete evidence: missing graph"),
                                  ConnectionError("Hydra unavailable"),
                                  MissingEvidenceError("Source no longer available: source:other:fx")])
def test_unexpected_errors_never_pass_as_expected_unavailability(monkeypatch, tmp_path, error):
    result = fake_execution(monkeypatch, tmp_path, state="stale", error=error,
                            expected_errors={"month:report": "Unavailable source"}, unavailable=["month:fx"])
    assert not result["oracle_correct"]
    assert result["unexpected_refresh_error"]


def test_refusal_cannot_pass_if_unavailable_artifact_is_served_current(monkeypatch, tmp_path):
    result = fake_execution(monkeypatch, tmp_path, state="current",
        error=MissingEvidenceError("Source no longer available: source:month:fx"),
        expected_errors={"month:report": "Unavailable source"}, unavailable=["month:fx"])
    assert not result["oracle_correct"]
    assert result["artifacts_counts"]["incorrect_current"] == 1


def test_independent_change_audit_rejects_runtime_false_negative():
    before = [{"order_id": "line", "gross_cents": 100}]
    record = ArtifactRecord("old", "source", "source:month:orders", "hash", "now", {})
    store = FakeStore(record, before)
    runtime = SimpleNamespace(store=store,
        set_source=lambda *_: SourceChange("source:month:orders", "old", "old", False))
    workload = SimpleNamespace(runtime=runtime, sources={"month:orders": before})
    case = RetailCase("RD01", "dev", "Correct line", (RetailMutation("month:orders", "unit_price_delta_pence",
                       {"order_id": "line", "delta_pence": 1, "quantity": 1}),), "correction", ("month",))
    with pytest.raises(AssertionError, match="independent value comparison"):
        runner.mutate_workload(workload, case)


def test_canonical_noop_has_no_independently_expected_changed_roots():
    before = [{"order_id": "a", "gross_cents": 100}, {"order_id": "b", "gross_cents": 200}]
    record = ArtifactRecord("old", "source", "source:month:orders", "hash", "now", {})
    runtime = SimpleNamespace(store=FakeStore(record, before),
        set_source=lambda *_: SourceChange("source:month:orders", "old", "old", False))
    workload = SimpleNamespace(runtime=runtime, sources={"month:orders": before})
    case = RetailCase("RD04", "dev", "Reorder", (RetailMutation("month:orders", "reorder"),), "canonical_noop", ("month",))
    changed, sources, audit = runner.mutate_workload(workload, case)
    assert changed == []
    assert sources["month:orders"] == before
    assert not audit[0]["expected_changed"]
    assert audit[0]["before_sha256"] == audit[0]["after_sha256"]
