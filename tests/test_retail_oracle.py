"""Fixed-answer tests for the independent external-retail oracle.

No production arithmetic, runtime, graph double, or benchmark fixtures produce
the expected answers in these tests.
"""
from copy import deepcopy
from decimal import localcontext

import pytest

from proofflow.eval.retail_oracle import (
    OracleContractError, OracleUnavailable, compute_values,
    expected_affected_names, raw_line_amount_pence, verify_raw_orders,
)


def recipe(name, tool, inputs, params=None):
    return {"name": name, "tool": tool, "inputs": inputs, "params": params or {}}


def report(name, inputs, sections):
    return recipe(name, "compose_report", inputs, {"title": name, "sections": sections})


def section(key, port, path):
    return {"key": key, "label": key, "input": port, "path": path, "unit": "USD cents"}


def fixture():
    sources = {
        "2011-01:orders": [
            {"order_id": "a", "region": "France", "currency": "GBP", "gross_cents": 250},
            {"order_id": "b", "region": "United Kingdom", "currency": "GBP", "gross_cents": 225},
        ],
        "2011-01:refunds": [{"order_id": "a", "refund_cents": 50}],
        "2011-01:fx": {"GBP": "1.25"},
        "2011-02:orders": [{"order_id": "c", "region": "France", "currency": "GBP", "gross_cents": 100}],
        "2011-02:fx": {"GBP": "1.50"},
    }
    contracts = [
        recipe("jan:gross", "gross_by_region", {"orders": "source:2011-01:orders"}),
        recipe("jan:refunds", "refunds_by_region", {"orders": "source:2011-01:orders", "refunds": "source:2011-01:refunds"}),
        recipe("jan:net", "net_by_region", {"gross": "jan:gross", "refunds": "jan:refunds"}),
        recipe("jan:gross_usd", "convert_to_usd", {"net": "jan:gross", "fx": "source:2011-01:fx"}),
        recipe("jan:net_usd", "convert_to_usd", {"net": "jan:net", "fx": "source:2011-01:fx"}),
        recipe("jan:company", "company_total", {"regional": "jan:net_usd"}),
        recipe("feb:gross", "gross_by_region", {"orders": "source:2011-02:orders"}),
        recipe("feb:usd", "convert_to_usd", {"net": "feb:gross", "fx": "source:2011-02:fx"}),
        report("cross:review", {"prior": "jan:net_usd", "now": "feb:usd", "company": "jan:company"}, [
            section("France prior", "prior", ["regions", "France", "usd_cents"]),
            section("France current", "now", ["regions", "France", "usd_cents"]),
            section("January all countries", "company", ["usd_cents"]),
        ]),
    ]
    return contracts, sources


def test_raw_line_reconstruction_does_not_round_unit_price_first():
    assert raw_line_amount_pence(2, "0.005") == 1
    assert raw_line_amount_pence(1000, "2.35") == 235000
    with pytest.raises(OracleUnavailable, match="fractional pence"):
        raw_line_amount_pence(3, "0.005")


@pytest.mark.parametrize("quantity,price", [(0, "1"), (-1, "1"), (True, "1"), (1, "0"), (1, "NaN"), (1, 1.25)])
def test_raw_positive_sales_subset_refuses_unsupported_rows(quantity, price):
    with pytest.raises(OracleUnavailable):
        raw_line_amount_pence(quantity, price)


def test_external_country_does_not_change_gbp_currency():
    raw = [{"invoice_no": "50001", "source_row": 12, "region": "France", "quantity": 2, "unit_price_gbp": "1.25"}]
    normalized = [{"order_id": "uci:50001:row:12", "region": "France", "currency": "GBP", "gross_cents": 250}]
    verify_raw_orders(raw, normalized)
    for key, wrong in [("currency", "EUR"), ("gross_cents", 251), ("region", "United Kingdom")]:
        altered = deepcopy(normalized)
        altered[0][key] = wrong
        with pytest.raises(OracleContractError):
            verify_raw_orders(raw, altered)


def test_raw_identity_and_duplicate_rows_are_checked():
    raw = [{"invoice_no": "50001", "source_row": 12, "region": "France", "quantity": 2, "unit_price_gbp": "1.25"}]
    with pytest.raises(OracleContractError, match="Duplicate"):
        verify_raw_orders(raw + raw, [])
    raw[0]["invoice_no"] = "C50001"
    with pytest.raises(OracleContractError):
        verify_raw_orders(raw, [])


def test_retained_xlsx_numeric_strings_are_independently_verified():
    raw = [{"invoice_no": "50002", "source_row": 13, "region": "France", "quantity": 2,
            "quantity_raw_xml": "2", "unit_price_gbp": "2.55", "unit_price_raw_xml": "2.5499999999999998"}]
    normalized = [{"order_id": "uci:50002:row:13", "region": "France", "currency": "GBP", "gross_cents": 510}]
    verify_raw_orders(raw, normalized)
    wrong = deepcopy(raw)
    wrong[0]["unit_price_gbp"] = "2.56"
    with pytest.raises(OracleContractError, match="binary64"):
        verify_raw_orders(wrong, normalized)
    wrong = deepcopy(raw)
    wrong[0]["quantity_raw_xml"] = "3"
    with pytest.raises(OracleContractError, match="quantity"):
        verify_raw_orders(wrong, normalized)


def test_independent_values_cross_partition_and_half_even_rounding():
    contracts, sources = fixture()
    with localcontext() as context:
        context.prec = 2  # The caller's Decimal precision must not alter totals.
        values, errors = compute_values(reversed(contracts), sources)
    assert errors == {}
    assert values["jan:gross_usd"] == {"regions": {"France": {"usd_cents": 312}, "United Kingdom": {"usd_cents": 281}}}
    assert values["jan:company"] == {"usd_cents": 531}
    assert [item["value"] for item in values["cross:review"]["sections"]] == [250, 150, 531]


def test_refund_change_has_no_path_into_gross_only_branch():
    contracts, sources = fixture()
    affected = expected_affected_names(contracts, ["2011-01:refunds"])
    assert affected == {"jan:refunds", "jan:net", "jan:net_usd", "jan:company", "cross:review"}
    sources["2011-01:refunds"][0]["refund_cents"] = 70
    values, errors = compute_values(contracts, sources)
    assert not errors
    assert values["jan:company"] == {"usd_cents": 506}
    assert values["jan:gross_usd"]["regions"]["France"]["usd_cents"] == 312


def test_candidate_scope_is_applied_after_cross_partition_closure():
    contracts, _ = fixture()
    assert expected_affected_names(contracts, ["2011-01:refunds"], candidate_names={"cross:review", "feb:usd"}) == {"cross:review"}


def test_tool_version_closure_is_independent_of_unchanged_arithmetic():
    contracts, sources = fixture()
    before, _ = compute_values(contracts, sources)
    affected = expected_affected_names(contracts, [], ["convert_to_usd"])
    assert affected == {"jan:gross_usd", "jan:net_usd", "jan:company", "feb:usd", "cross:review"}
    after, _ = compute_values(contracts, sources)
    assert before == after


def test_provenance_change_can_leave_numeric_outputs_equal():
    contracts, sources = fixture()
    sources["2011-01:orders"].append({"order_id": "d", "region": "France", "currency": "GBP", "gross_cents": 100})
    before, _ = compute_values(contracts, sources)
    sources["2011-01:orders"][0]["gross_cents"] += 10
    sources["2011-01:orders"][2]["gross_cents"] -= 10
    after, _ = compute_values(contracts, sources)
    assert before == after
    assert "cross:review" in expected_affected_names(contracts, ["2011-01:orders"])


def test_missing_source_only_blocks_dependent_contracts():
    contracts, sources = fixture()
    sources["2011-01:fx"] = None
    values, errors = compute_values(contracts, sources)
    assert set(errors) == {"jan:gross_usd", "jan:net_usd", "jan:company", "cross:review"}
    assert values["feb:usd"] == {"regions": {"France": {"usd_cents": 150}}}
    assert values["jan:gross"]["regions"]["France"]["amount_cents"] == 250


def test_mislabelled_claim_unit_cannot_pass_as_numeric_success():
    contracts, sources = fixture()
    contracts[-1]["params"]["sections"][0]["unit"] = "GBP pence"
    values, errors = compute_values(contracts, sources)
    assert "cross:review" not in values
    assert "path/unit" in errors["cross:review"]


def test_typo_and_cycle_are_oracle_contract_errors_not_missing_source_success():
    contracts, sources = fixture()
    contracts[-1]["inputs"]["now"] = "feb:typo"
    with pytest.raises(OracleContractError, match="Unknown"):
        compute_values(contracts, sources)
    cyclic = [recipe("a", "company_total", {"regional": "b"}), recipe("b", "company_total", {"regional": "a"})]
    with pytest.raises(OracleContractError, match="Cycle"):
        compute_values(cyclic, {})


def test_mixed_currency_and_unknown_refund_fail_independently():
    contracts, sources = fixture()
    sources["2011-01:orders"].append({"order_id": "d", "region": "France", "currency": "EUR", "gross_cents": 100})
    _, errors = compute_values(contracts, sources)
    assert "jan:gross" in errors and "cross:review" in errors
    contracts, sources = fixture()
    sources["2011-01:refunds"][0]["order_id"] = "not-in-orders"
    _, errors = compute_values(contracts, sources)
    assert "jan:refunds" in errors and "jan:gross_usd" not in errors


def test_duplicate_prefixed_source_does_not_hide_missing_source():
    with pytest.raises(OracleContractError, match="Duplicate logical source"):
        compute_values([], {"month:fx": None, "source:month:fx": {"GBP": "1.2"}})
