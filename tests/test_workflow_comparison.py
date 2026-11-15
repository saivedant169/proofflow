import pytest

from scripts.workflow_comparison import InputRevision, SharedReports, check_outputs, ordinary_full_recalculate


HEADER = b"order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
ORDERS = HEADER + b"e1,NORTH,EUR,12,0,3\ne2,NORTH,EUR,13,0,0\ns1,SOUTH,USD,50,1,2\n"


def test_full_recalculation_uses_regional_rounding_and_counts_its_checks():
    revision = InputRevision(ORDERS, {"EUR": "1.02"}, "NORTH")

    results, accounting = ordinary_full_recalculate(revision)

    assert results == {
        "gross": {"NORTH": 25, "SOUTH": 50}, "refunds": {"SOUTH": 1},
        "net": {"NORTH": 25, "SOUTH": 49}, "regional": {"NORTH": 26, "SOUTH": 49},
        "support": {"NORTH": 3, "SOUTH": 2}, "company": 75,
        "company_report": 75, "region_report": 26,
    }
    assert accounting["full_csv_scans"] == 1
    assert accounting["validated_rows"] == 3
    assert accounting["fresh_logical_outputs"] == sorted(results)
    assert accounting["input_validation_passed"]
    assert len(accounting["reconciliation_controls"]) == 4
    assert all(accounting["reconciliation_controls"].values())


@pytest.mark.parametrize(("orders", "rates", "message"), [
    (ORDERS + b"e1,NORTH,EUR,15,0,0\n", {"EUR": "1.02"}, "duplicate order ID"),
    (ORDERS + b"e3,NORTH,USD,15,0,0\n", {"EUR": "1.02"}, "Mixed region currency"),
    (ORDERS + b"e3,NORTH,EUR,15,16,0\n", {"EUR": "1.02"}, "Refund or ticket limit"),
    (ORDERS, {}, "Missing or unsupported currency rate"),
])
def test_ordinary_validation_precedes_publication(tmp_path, orders, rates, message):
    shared = SharedReports(tmp_path / "shared")
    shared.set_source(InputRevision(orders, rates, "NORTH"))

    with pytest.raises(ValueError, match=message):
        shared.full_recalculate_and_publish()

    assert not list(shared.reports.iterdir())


def test_shared_guard_rejects_old_and_relabeled_copies(tmp_path):
    shared = SharedReports(tmp_path / "shared")
    initial = InputRevision(ORDERS, {"EUR": "1.02"}, "NORTH")
    corrected = InputRevision(ORDERS, {"EUR": "1.06"}, "NORTH")
    shared.set_source(initial)
    old_report, _, _ = shared.full_recalculate_and_publish()
    assert shared.check_handoff(old_report)["content"] == old_report

    shared.set_source(corrected)
    assert "content" not in shared.check_handoff(old_report)
    assert "content" not in shared.check_handoff(old_report.replace(initial.digest, corrected.digest))
    current_report, _, _ = shared.full_recalculate_and_publish()

    assert shared.check_handoff(old_report)["reason"] == "working_copy_input_revision_mismatch"
    assert shared.check_handoff(old_report.replace(initial.digest, corrected.digest))["reason"] == (
        "current_published_snapshot_not_matched"
    )
    assert shared.check_handoff(current_report)["content"] == current_report
    assert (shared.reports / f"{initial.digest}.txt").read_text() == old_report


def test_shared_oracle_detects_a_wrong_output():
    with pytest.raises(ValueError, match="region_report"):
        check_outputs({"company_report": 75, "region_report": 25},
                      {"company_report": 75, "region_report": 26}, "Example arm")
