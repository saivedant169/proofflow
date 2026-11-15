import json
from decimal import Decimal

import pytest

from proofflow.eval.model_ledger_v4 import StudyLedger, StudyStopped


def test_known_costs_include_failed_plans_and_next_cap_uses_remaining(tmp_path):
    ledger = StudyLedger(tmp_path)
    for i in range(10):
        assert ledger.reserve(str(i), "run") == 1
        ledger.settle(str(i), 0.95, usage_known=True)
    assert Decimal(ledger.snapshot()["spent_known_usd"]) == Decimal("9.5")
    assert ledger.reserve("last", "run") == 0.5
    ledger.settle("last", 0.5, usage_known=True)
    with pytest.raises(StudyStopped):
        ledger.reserve("too-late", "run")


def test_persisted_pending_attempt_prevents_relaunch_after_crash(tmp_path):
    StudyLedger(tmp_path).reserve("one", "run")
    reopened = StudyLedger(tmp_path)
    with pytest.raises(StudyStopped, match="pending"):
        reopened.reserve("one", "run")
    with pytest.raises(StudyStopped, match="pending"):
        reopened.reserve("different", "run")


def test_unknown_usage_debits_known_charge_and_stops(tmp_path):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    state = ledger.settle("one", 0.2, usage_known=False)
    assert Decimal(state["spent_known_usd"]) == Decimal("0.2")
    assert state["stopped"]
    assert state["attempts"][0]["status"] == "unknown_accounting"
    with pytest.raises(StudyStopped):
        ledger.reserve("two", "run")


def test_unknown_charge_is_never_zero_filled(tmp_path):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    state = ledger.settle("one", None, usage_known=False)
    assert state["attempts"][0]["reported_cost_usd"] is None
    assert state["stopped"]


def test_overshoot_is_preserved_and_stops(tmp_path):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    state = ledger.settle("one", 1.25, usage_known=True)
    assert Decimal(state["spent_known_usd"]) == Decimal("1.25")
    assert state["attempts"][0]["configured_cap_overshoot"]
    assert state["stopped"]


def test_completed_cell_cannot_be_retried_or_double_debited(tmp_path):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    ledger.settle("one", 0.1, usage_known=True)
    with pytest.raises(StudyStopped, match="retries"):
        ledger.reserve("one", "run")
    with pytest.raises(StudyStopped):
        ledger.settle("one", 0.1, usage_known=True)
    assert Decimal(ledger.snapshot()["spent_known_usd"]) == Decimal("0.1")


def test_infra_error_stops_even_when_charge_is_known(tmp_path):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    assert ledger.settle("one", 0.0, usage_known=True, stop_reason="Provider unavailable")["stopped"]


@pytest.mark.parametrize("invalid", [True, -1, float("nan"), float("inf"), "0.1"])
def test_malformed_cost_cannot_settle_pending_attempt(tmp_path, invalid):
    ledger = StudyLedger(tmp_path)
    ledger.reserve("one", "run")
    with pytest.raises(ValueError):
        ledger.settle("one", invalid, usage_known=True)
    assert ledger.snapshot()["attempts"][0]["status"] == "pending"


def test_only_two_development_dry_runs_and_none_after_paid_reservation(tmp_path):
    ledger = StudyLedger(tmp_path)
    assert ledger.begin_dry_run("first") == 1
    assert ledger.begin_dry_run("second") == 2
    with pytest.raises(StudyStopped):
        ledger.begin_dry_run("third")
    ledger.reserve("one", "run")
    with pytest.raises(StudyStopped):
        ledger.begin_dry_run("after-attempt")


def test_fixed_budget_identity_cannot_silently_change(tmp_path):
    ledger = StudyLedger(tmp_path)
    state = ledger.snapshot()
    state["limit_usd"] = "100.00"
    ledger.path.write_text(json.dumps(state))
    with pytest.raises(StudyStopped):
        ledger.reserve("one", "run")
