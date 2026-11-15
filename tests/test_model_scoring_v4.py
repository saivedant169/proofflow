"""Pure score aggregation and fake-oracle tests; no Hydra, fixture, or model runs."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from proofflow.eval import model_scoring_v4 as scoring


def fixture():
    records = {
        "a-old": {"id": "a-old", "kind": "artifact", "logical_id": "artifact:a", "content_hash": "a-hash", "value": 1},
        "b-old": {"id": "b-old", "kind": "artifact", "logical_id": "artifact:b", "content_hash": "b-hash", "value": 2},
    }
    prior = {"records": deepcopy(records), "artifact_heads": {"artifact:a": "a-old", "artifact:b": "b-old"},
             "source_heads": {}, "tool_heads": {}}
    post = deepcopy(prior)
    execution = {"unexpected_refresh_error": False, "inspection_errors": [], "artifacts": [
        {"name": name, "head_id": f"{name}-old", "head_content_hash": f"{name}-hash",
         "state": "current", "actual_stored_value": value}
        for name, value in [("a", 1), ("b", 2)]], "reports_counts": {"fresh": 999}}
    audit = {"head_validation_pass": True, "immutable_anchor_provided": True, "immutable_anchor_pass": True,
             "immutable_anchor_records": len(records), "immutable_anchor_sha256": scoring._sha(scoring._canonical(records)),
             "artifacts": {name: {"head_id": f"{name}-old", "provenance_current": True, "reasons": []}
                           for name in ("a", "b")}}
    return {"execution": execution, "audit": audit, "post_snapshot": post, "prior_snapshot": prior,
            "candidate_names": {"a", "b"}, "expected_names": {"a"}, "expected_values": {"a": 1, "b": 2},
            "expected_errors": {}, "report_names": {"a", "b"}, "unavailable_source_names": set()}


def test_verified_counts_do_not_trust_raw_runtime_counts():
    data = fixture()
    before = deepcopy(data)
    result = scoring.aggregate_verified_outcome(**data)
    assert result["absolute_correct"] is True
    assert result["semantic_endstate_correct"] is True
    assert result["verified_reports_counts"] == {
        "total": 2, "eligible": 2, "fresh": 2, "eligible_affected": 1,
        "fresh_affected": 1, "unavailable": 0, "correctly_blocked": 0,
        "unaffected": 1, "unaffected_artifacts_preserved": 1, "incorrect_current": 0,
    }
    assert data == before


@pytest.mark.parametrize("key,value", [("head_validation_pass", False), ("immutable_anchor_provided", False),
                                      ("immutable_anchor_pass", None), ("immutable_anchor_records", 1),
                                      ("immutable_anchor_sha256", "different")])
def test_global_head_or_anchor_failure_cannot_pass(key, value):
    data = fixture()
    data["audit"][key] = value
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["fresh"] == 0
    assert result["verified_reports_counts"]["eligible_affected"] == 1


def test_empty_selection_unchanged_stale_state_keeps_all_denominators():
    data = fixture()
    data["execution"]["selected_aliases"] = []
    data["execution"]["artifacts"][0]["state"] = "stale"
    data["audit"]["artifacts"]["a"].update(provenance_current=False, reasons=["source_version_stale:source:orders"])
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["eligible"] == 2
    assert result["verified_reports_counts"]["eligible_affected"] == 1
    assert result["verified_reports_counts"]["fresh_affected"] == 0


@pytest.mark.parametrize("alteration", ["missing", "duplicate", "extra", "missing_audit"])
def test_incomplete_or_duplicate_inspection_does_not_shrink_declared_denominators(alteration):
    data = fixture()
    rows = data["execution"]["artifacts"]
    if alteration == "missing":
        rows.pop()
    elif alteration == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif alteration == "extra":
        rows.append({**rows[0], "name": "undeclared"})
    else:
        del data["audit"]["artifacts"]["b"]
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["total"] == 2
    assert result["verified_reports_counts"]["eligible"] == 2
    assert result["scoring_errors"]


@pytest.mark.parametrize("replacement", [True, 1.0, 3])
def test_numeric_equality_is_canonical_and_not_python_coercion(replacement):
    data = fixture()
    data["post_snapshot"]["records"]["a-old"]["value"] = replacement
    data["execution"]["artifacts"][0]["actual_stored_value"] = replacement
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["incorrect_current"] == 1


@pytest.mark.parametrize("field,value", [("head_id", "other"), ("head_content_hash", "other"),
                                        ("actual_stored_value", True)])
def test_runtime_observation_must_join_exactly_to_the_audited_snapshot(field, value):
    data = fixture()
    data["execution"]["artifacts"][0][field] = value
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["fresh_affected"] == 0


def unavailable_fixture():
    data = fixture()
    del data["expected_values"]["a"]
    data["expected_errors"]["a"] = "Unavailable inputs: source:fx"
    data["unavailable_source_names"] = {"fx"}
    data["execution"]["artifacts"][0]["state"] = "stale"
    data["audit"]["artifacts"]["a"].update(provenance_current=False, reasons=["source_unavailable:source:fx"])
    return data


def test_legitimate_unavailable_refusal_is_separate_from_fresh_success():
    data = unavailable_fixture()
    result = scoring.aggregate_verified_outcome(**data)
    assert result["absolute_correct"]
    assert result["verified_reports_counts"]["eligible_affected"] == 0
    assert result["verified_reports_counts"]["unavailable"] == 1
    assert result["verified_reports_counts"]["correctly_blocked"] == 1
    assert result["verified_reports_counts"]["fresh"] == 1


@pytest.mark.parametrize("reason", ["execution_receipt_mismatch:x", "receipt_cycle:x", "missing_artifact_head:a",
                                    "recipe_input_ports_mismatch:x", "content_hash_mismatch:x", "source_unavailable:source:unrelated"])
def test_unavailable_source_cannot_hide_unrelated_provenance_corruption(reason):
    data = unavailable_fixture()
    data["audit"]["artifacts"]["a"]["reasons"].append(reason)
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["correctly_blocked"] == 0


def test_unavailable_artifact_claimed_current_is_incorrect_even_with_old_valid_value():
    data = unavailable_fixture()
    data["execution"]["artifacts"][0]["state"] = "current"
    result = scoring.aggregate_verified_outcome(**data)
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["incorrect_current"] == 1


def test_unaffected_identity_must_be_preserved_even_if_replacement_is_correct():
    data = fixture()
    post = data["post_snapshot"]
    post["records"]["b-new"] = {**post["records"]["b-old"], "id": "b-new"}
    post["artifact_heads"]["artifact:b"] = "b-new"
    data["execution"]["artifacts"][1]["head_id"] = "b-new"
    data["audit"]["artifacts"]["b"]["head_id"] = "b-new"
    result = scoring.aggregate_verified_outcome(**data)
    assert result["verified_reports_counts"]["fresh"] == 2
    assert not result["absolute_correct"]
    assert result["verified_reports_counts"]["unaffected_artifacts_preserved"] == 0


def test_unexpected_refresh_error_is_not_erased_by_correct_endstate():
    data = fixture()
    data["execution"]["unexpected_refresh_error"] = True
    assert not scoring.aggregate_verified_outcome(**data)["absolute_correct"]


def test_anchor_validation_rejects_partial_and_changed_snapshots():
    data = fixture()
    anchor = data["prior_snapshot"]
    scoring._validate_anchor(anchor, deepcopy(anchor))
    partial = deepcopy(anchor)
    del partial["records"]["a-old"]
    with pytest.raises(ValueError, match="ID set"):
        scoring._validate_anchor(partial, anchor)
    changed = deepcopy(anchor)
    changed["artifact_heads"]["artifact:a"] = "b-old"
    with pytest.raises(ValueError, match="contents or heads"):
        scoring._validate_anchor(anchor, changed)
    with pytest.raises(ValueError, match="every immutable"):
        scoring._validate_anchor({"records": {}}, anchor)


def test_planned_denominators_use_independent_staging_without_runtime(monkeypatch):
    metadata = {"split": "fake", "recipes": [
        {"name": "a", "tool": "compose_report"}, {"name": "b", "tool": "compose_report"},
        {"name": "intermediate", "tool": "company_total"}],
        "candidate_names": ["a", "b", "intermediate"],
        "scenario": {"mutations": [{"operation": "remove", "source": "fx"}]}}
    monkeypatch.setattr(scoring, "fixture_sources", lambda split: {"fx": 1})
    monkeypatch.setattr(scoring, "stage_sources", lambda sources, mutations: {"fx": None})
    def compute(recipes, sources):
        assert sources == {"fx": None}
        return {"b": 2, "intermediate": 3}, {"a": "Unavailable"}
    def affected(recipes, sources, tools, candidates):
        assert sources == {"fx"} and tools == set()
        return {"a"}
    monkeypatch.setattr(scoring, "compute_values", compute)
    monkeypatch.setattr(scoring, "expected_affected_names", affected)
    monkeypatch.setattr(scoring, "ArtifactStore", lambda *args: pytest.fail("No runtime store for denominators"))
    monkeypatch.setattr(scoring, "HydraGraph", lambda *args, **kwargs: pytest.fail("No Hydra for denominators"))
    assert scoring.planned_report_counts(metadata) == {
        "reports": 2, "eligible_reports": 1, "eligible_affected_reports": 0,
        "unavailable_reports": 1, "unaffected_reports": 1,
    }


def test_changed_anchor_file_is_rejected_before_runtime_access(tmp_path, monkeypatch):
    path = tmp_path / "anchor.json"
    path.write_text('{"records": {}}')
    monkeypatch.setattr(scoring, "ArtifactStore", lambda *args: pytest.fail("Must reject hash before runtime"))
    with pytest.raises(ValueError, match="snapshot file hash"):
        scoring.score_selection({"initial_records_path": str(path), "initial_records_sha256": "wrong"}, [], tmp_path / "out")
