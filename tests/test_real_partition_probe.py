import json
import shutil
from types import SimpleNamespace

import pytest

from scripts.real_partition_probe import (
    FIXTURES,
    ORIGIN,
    CheckFailure,
    check_fixture,
    eligible_line,
    guard_browser_writes,
    money_oracle,
)


def test_frozen_fixture_retains_selected_day_and_expected_raw_cell_amounts():
    fixture, csv_content = check_fixture(FIXTURES)
    assert fixture["selected_date"] == "2011-01-16"
    assert fixture["rows"] == 642
    assert fixture["invoices"] == 25
    assert fixture["invoice_overlap_with_reserved_partitions"] == 0
    assert fixture["rows_by_region"] == {"United Kingdom": 642}
    assert [day["counts"]["eligible"] for day in fixture["candidate_profiles_through_selected_date"]] == [
        1951, 1395, 1783, 1433, 1493, 642,
    ]
    assert len(csv_content) == 28429
    assert fixture["oracle"]["gross_gbp_by_region"] == {"United Kingdom": "7242.06"}
    assert fixture["oracle"]["initial"]["company_usd_cents"] == 905258
    assert fixture["oracle"]["corrected"]["company_usd_cents"] == 941468


def test_oracle_rounds_each_country_to_even_before_adding():
    def raw_price(country, price):
        return {"country": country, "quantity_raw_xml": "1", "unit_price_raw_xml": price}

    amounts = money_oracle([raw_price("A", "0.02"), raw_price("B", "0.02")], "B")
    assert amounts["initial"] == {"by_region_usd_cents": {"A": 2, "B": 2}, "company_usd_cents": 4, "region_usd_cents": 2}
    assert money_oracle([raw_price("B", "0.06")], "B")["initial"]["region_usd_cents"] == 8


def test_selection_filters_fractional_line_pence_and_preserves_original_quantity_and_price():
    fields = {"InvoiceNo": "536365", "InvoiceDate": "40559.5", "Country": "United Kingdom", "Quantity": "3"}
    assert eligible_line(211, {**fields, "UnitPrice": "0.005"}) == (None, "fractional_line_pence")
    line, reason = eligible_line(211, {**fields, "UnitPrice": "2.5499999999999998"})
    assert reason == "eligible"
    assert line[0]["unit_price_raw_xml"] == "2.5499999999999998"
    assert line[1]["gross_cents"] == 765


def test_audit_rejects_modified_source_hash_and_oracle(tmp_path):
    for name in ("orders.csv", "source_cells.csv", "fixture.json"):
        shutil.copyfile(FIXTURES / name, tmp_path / name)
    source = tmp_path / "source_cells.csv"
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(CheckFailure, match="Fixture hash or size mismatch"):
        check_fixture(tmp_path)
    shutil.copyfile(FIXTURES / source.name, source)
    manifest_path = tmp_path / "fixture.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["oracle"]["initial"]["company_usd_cents"] += 1
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(CheckFailure, match="Independent oracle differs"):
        check_fixture(tmp_path)


def test_write_guard_records_and_blocks_duplicates_and_further_writes():
    guard_callbacks = []
    context = SimpleNamespace(route=lambda _, callback: guard_callbacks.append(callback))
    receipt = {"write_request_attempts": []}
    guard_browser_writes(context, receipt)
    actions = []

    def send(path):
        guard_callbacks[0](SimpleNamespace(
            request=SimpleNamespace(method="POST", url=f"{ORIGIN}{path}"),
            continue_=lambda: actions.append("sent"), abort=lambda: actions.append("blocked"),
        ))

    send("/api/session")
    send("/api/session")
    send("/api/import/create")
    assert actions == ["sent", "blocked", "blocked"]
    assert [item["allowed"] for item in receipt["write_request_attempts"]] == [True, False, False]
