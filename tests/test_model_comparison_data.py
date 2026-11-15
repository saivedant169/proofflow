"""Fresh source and patch checks only: no model, selector or runtime calls."""
from __future__ import annotations

import csv
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest

from proofflow.eval.model_comparison_data import (DATES_PER_SPLIT, FIXTURE_DIR, MONTHS, ROOT,
    candidate_names, fixture_sources, manifest_data, mutate_value, normalize_row,
    patch_audit, prepare_fixture, recipes, scenarios)
from proofflow.eval.retail_data import RetailMutation, canonical, sha_file
from proofflow.eval.retail_oracle import verify_raw_orders


def raw_row(**updates):
    serial = (datetime(2011, 6, 1) - datetime(1899, 12, 30)).days
    row = {"InvoiceDate": str(serial), "InvoiceNo": "123456", "Country": "United Kingdom",
           "Quantity": "2", "UnitPrice": "2.5499999999999998", "StockCode": "A"}
    row.update(updates)
    return row


def test_raw_numeric_policy_and_eligibility():
    date, row, reason = normalize_row(2, raw_row(), "2011-06")
    assert (date, reason, row["unit_price_gbp"], row["gross_cents"]) == ("2011-06-01", "eligible", "2.55", 510)
    assert row["unit_price_raw_xml"] == "2.5499999999999998"
    assert row["quantity_raw_xml"] == "2"
    for updates, expected in [
        ({"Quantity": "1", "UnitPrice": ".001"}, "fractional_line_pence"),
        ({"Quantity": "1.5"}, "nonpositive_or_noninteger_quantity"),
        ({"Quantity": "1000000001"}, "quantity_bound"),
        ({"UnitPrice": "inf"}, "nonpositive_or_invalid_price"),
        ({"UnitPrice": "100000000000"}, "amount_bound"),
        ({"InvoiceNo": "C123456"}, "cancellation_invoice"),
        ({"InvoiceNo": ""}, "invalid_identifier_or_country"),
        ({"Country": "__bad"}, "invalid_identifier_or_country"),
        ({"InvoiceDate": "nan"}, "invalid_date"),
    ]:
        assert normalize_row(2, raw_row(**updates), "2011-06")[2] == expected


def test_before_after_patch_guard_and_noop():
    orders = [{"order_id": "a", "gross_cents": 10}, {"order_id": "b", "gross_cents": 9}]
    original = deepcopy(orders)
    assert mutate_value(orders, RetailMutation(operation="reorder")) == original
    with pytest.raises(ValueError, match="before-value"):
        mutate_value(orders, RetailMutation(operation="quantity_delta", parameters={
            "order_id": "a", "unit_price_gbp": ".01", "delta_quantity": 1,
            "old_gross_cents": 999, "new_gross_cents": 1000}))
    assert orders == original


def test_refuse_fixture_overwrite(tmp_path):
    (tmp_path / "fixture.json").write_text("preserve")
    with pytest.raises(ValueError, match="overwrite"):
        prepare_fixture(Path("missing.xlsx"), "dev", tmp_path)


@pytest.mark.parametrize("split", ["dev", "test"])
def test_prepared_complete_date_fixture_and_patches(split):
    base = FIXTURE_DIR / split
    if not (base / "fixture.json").exists():
        pytest.skip("Source split is not prepared yet")
    fixture, sources, declarations, cases = manifest_data(split), fixture_sources(split), recipes(split), scenarios(split)
    n = DATES_PER_SPLIT[split]
    assert len(fixture["dates"]) == n
    assert len(declarations) == 10 * n - 1
    assert sum(r.tool == "compose_report" for r in declarations) == 3 * n - 1
    assert len(cases) == (2 if split == "dev" else 8)
    assert len(sources) == 3 * n and not any(k.endswith(":tickets") for k in sources)
    assert candidate_names(cases[0], declarations) == {r.name for r in declarations}
    assert fixture["queries_by_case"] == {c.id: c.description for c in cases}
    all_ids, invoice_dates = set(), {}
    for date, entry in fixture["files"].items():
        assert date[:7] == MONTHS[split]
        raw_rows = json.loads((base / entry["provenance"]).read_text())
        assert len(raw_rows) == entry["rows"]
        assert sha_file(base / entry["csv"]) == entry["csv_sha256"]
        assert sha_file(base / entry["provenance"]) == entry["provenance_sha256"]
        assert all("unit_price_raw_xml" in r and "quantity_raw_xml" in r for r in raw_rows)
        assert all(r["invoice_date"][:10] == date for r in raw_rows)
        assert all(not {"CustomerID", "Description", "customer_id", "description"} & r.keys() for r in raw_rows)
        orders = sources[f"{date}:orders"]
        verify_raw_orders(raw_rows, orders)
        with (base / entry["csv"]).open(newline="") as stream:
            csv_rows = [{**r, "gross_cents": int(r["gross_cents"])} for r in csv.DictReader(stream)]
        assert csv_rows == orders == sorted(orders, key=lambda r: r["order_id"])
        for row in raw_rows:
            assert row["order_id"] not in all_ids
            all_ids.add(row["order_id"])
            assert row["invoice_no"] not in invoice_dates or invoice_dates[row["invoice_no"]] == date
            invoice_dates[row["invoice_no"]] = date
    assert len(all_ids) == fixture["profile"]["selected_rows"]
    assert len(invoice_dates) == fixture["profile"]["selected_invoices"]
    assert patch_audit(sources, cases) == fixture["concrete_patch_audit"]
    for case in cases:
        values = deepcopy(sources)
        before = canonical(values)
        for mutation in case.mutations:
            if mutation.operation != "tool_version":
                values[mutation.source] = mutate_value(values[mutation.source], mutation)
        if case.category == "canonical_noop":
            assert before == canonical(values)
        for name, value in values.items():
            if name.endswith(":orders") and value is not None:
                assert all(0 < row["gross_cents"] <= 10**12 for row in value)


def _identities(paths):
    rows = [row for path in paths for row in json.loads(path.read_text())]
    return {r["source_row"] for r in rows}, {r["invoice_no"] for r in rows}


def test_split_and_prior_fixture_overlap():
    if not all((FIXTURE_DIR / split / "fixture.json").exists() for split in MONTHS):
        pytest.skip("Both splits must be prepared")
    dev = _identities(sorted((FIXTURE_DIR / "dev").glob("*.provenance.json")))
    test = _identities(sorted((FIXTURE_DIR / "test").glob("*.provenance.json")))
    assert dev[0].isdisjoint(test[0]) and dev[1].isdisjoint(test[1])
    prior_v2 = list((ROOT / "fixtures" / "retail_v2").glob("*.provenance.json"))
    assert prior_v2, "Frozen v2 fixtures must remain present"
    previous = _identities(prior_v2)
    assert (dev[0] | test[0]).isdisjoint(previous[0])
    assert (dev[1] | test[1]).isdisjoint(previous[1])
    # The stopped v3 archive is outside this repository. Its independent raw
    # overlap audit remains required even when reproducing this test elsewhere.
    archive = ROOT.parent.parent / "v3" / "worktree" / "fixtures" / "compact_v3"
    if archive.exists():
        previous = _identities(sorted(archive.rglob("*.provenance.json")))
        assert previous[0] and previous[1]
        assert (dev[0] | test[0]).isdisjoint(previous[0])
        assert (dev[1] | test[1]).isdisjoint(previous[1])
