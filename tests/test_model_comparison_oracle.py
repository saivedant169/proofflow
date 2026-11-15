"""Independent fixed snapshots; no runtime, graph or benchmark executions."""
from copy import deepcopy
import hashlib
import json

import pytest

from proofflow.eval.model_comparison_oracle import audit_provenance, stage_sources
from proofflow.eval.retail_oracle import OracleContractError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def record(kind, logical, value, metadata=None, identity=None, identifier=None):
    content_hash = digest(value)
    identifier = identifier or f"fixture:{kind}:" + digest({"logical_id": logical, "content_hash": content_hash, "identity": identity})
    return {"id": identifier, "kind": kind, "logical_id": logical,
            "content_hash": content_hash, "metadata": metadata or {}, "value": value}


def put_source(data, name, value):
    logical = "source:" + name
    item = record("source", logical, value, {"deleted": value is None}, {"deleted": True} if value is None else None)
    data["records"][item["id"]] = item
    data["source_heads"][logical] = item["id"]
    data["expected_sources"][logical] = value
    return item["id"]


def put_tool(data, name, version="1"):
    logical = "tool:" + name
    value = {"name": name, "version": version, "implementation_hash": "frozen-implementation-hash"}
    item = record("tool", logical, value)
    data["records"][item["id"]] = item
    data["tool_heads"][logical] = item["id"]
    data["expected_tools"][logical] = value
    return item["id"]


def put_artifact(data, recipe, inputs, value, suffix="1"):
    name, tool = recipe["name"], recipe["tool"]
    invocation = name + "-" + suffix
    metadata = {"tool": tool, "tool_version_id": data["tool_heads"]["tool:" + tool],
                "inputs": inputs, "params": recipe.get("params", {}), "run_id": "fixed-run"}
    item = record("artifact", "artifact:" + name, value, metadata, identity=invocation)
    identifier = item["id"]
    receipt_value = {key: metadata[key] for key in ("tool", "tool_version_id", "inputs", "params", "run_id")}
    receipt_value.update(output_id=identifier, output_hash=item["content_hash"], status="success")
    receipt = record("execution", "execution:" + invocation, receipt_value)
    receipt_id = receipt["id"]
    item["metadata"]["receipt_id"] = receipt_id
    data["records"].update({identifier: item, receipt_id: receipt})
    data["artifact_heads"][name] = identifier
    return identifier


def fixture():
    recipes = [
        {"name": "day:gross", "tool": "gross_by_region", "inputs": {"orders": "source:day:orders"}},
        {"name": "day:usd", "tool": "convert_to_usd", "inputs": {"net": "day:gross", "fx": "source:day:fx"}},
        {"name": "day:report", "tool": "compose_report", "inputs": {"amount": "day:usd"}, "params": {
            "title": "UK sales", "sections": [{"key": "gross", "label": "Gross USD", "input": "amount",
                "path": ["regions", "United Kingdom", "usd_cents"], "unit": "USD cents"}]}},
    ]
    data = {"recipes": recipes, "records": {}, "artifact_heads": {}, "source_heads": {}, "tool_heads": {},
            "expected_sources": {}, "expected_tools": {}}
    orders = [{"order_id": name, "region": "United Kingdom", "currency": "GBP", "gross_cents": 50} for name in ("a", "b")]
    order_id = put_source(data, "day:orders", orders)
    fx_id = put_source(data, "day:fx", {"GBP": "1.25"})
    for recipe in recipes:
        put_tool(data, recipe["tool"])
    gross = put_artifact(data, recipes[0], {"orders": order_id}, {"regions": {"United Kingdom": {"currency": "GBP", "amount_cents": 100}}})
    usd = put_artifact(data, recipes[1], {"net": gross, "fx": fx_id}, {"regions": {"United Kingdom": {"currency": "USD", "usd_cents": 125}}})
    put_artifact(data, recipes[2], {"amount": usd}, {"title": "UK sales", "claims": {"gross": {"value": 125, "unit": "USD cents", "label": "Gross USD"}}})
    return data


def current(result):
    return {name for name, row in result["artifacts"].items() if row["provenance_current"]}


def test_complete_receipt_chain_is_current_without_runtime_or_graph():
    result = audit_provenance(**fixture())
    assert result["head_validation_pass"] and result["all_provenance_current"]
    assert len(result["artifacts"]["day:report"]["checked_ids"]) == 11


def test_equal_aggregate_source_change_is_stale_everywhere_downstream():
    data = fixture()
    orders = deepcopy(data["expected_sources"]["source:day:orders"])
    orders[0]["gross_cents"], orders[1]["gross_cents"] = 49, 51
    put_source(data, "day:orders", orders)
    result = audit_provenance(**data)
    assert result["head_validation_pass"] and not current(result)
    assert "source_version_stale:source:day:orders" in result["artifacts"]["day:report"]["reasons"]


def test_same_arithmetic_new_tool_version_invalidates_descendants_only():
    data = fixture()
    put_tool(data, "convert_to_usd", "2")
    result = audit_provenance(**data)
    assert current(result) == {"day:gross"}
    assert "tool_version_stale:tool:convert_to_usd" in result["artifacts"]["day:report"]["reasons"]


@pytest.mark.parametrize("tombstone", [False, True])
def test_missing_source_blocks_only_dependent_provenance(tombstone):
    data = fixture()
    if tombstone:
        put_source(data, "day:fx", None)
    else:
        data["expected_sources"]["source:day:fx"] = None
        data["source_heads"]["source:day:fx"] = None
    result = audit_provenance(**data)
    assert result["head_validation_pass"]
    assert current(result) == {"day:gross"}
    assert "source_unavailable:source:day:fx" in result["artifacts"]["day:report"]["reasons"]


def test_restoration_requires_rebinding_receipts_to_new_live_version():
    data = fixture()
    put_source(data, "day:fx", None)
    fx_id = put_source(data, "day:fx", {"GBP": "1.31"})
    assert current(audit_provenance(**data)) == {"day:gross"}
    usd = put_artifact(data, data["recipes"][1], {"net": data["artifact_heads"]["day:gross"], "fx": fx_id},
                       {"regions": {"United Kingdom": {"currency": "USD", "usd_cents": 131}}}, "2")
    # The old report is stale even though the USD artifact head was refreshed.
    assert current(audit_provenance(**data)) == {"day:gross", "day:usd"}
    put_artifact(data, data["recipes"][2], {"amount": usd}, {"claims": {"gross": 131}}, "2")
    assert audit_provenance(**data)["all_provenance_current"]


def test_republished_identical_canonical_source_keeps_identity_current():
    data = fixture()
    original = data["source_heads"]["source:day:orders"]
    assert put_source(data, "day:orders", deepcopy(data["expected_sources"]["source:day:orders"])) == original
    assert audit_provenance(**data)["all_provenance_current"]


def test_old_consumed_artifact_can_remain_valid_after_equivalent_reexecution():
    data = fixture()
    old = data["records"][data["artifact_heads"]["day:gross"]]
    put_artifact(data, data["recipes"][0], old["metadata"]["inputs"], old["value"], "another")
    assert audit_provenance(**data)["all_provenance_current"]


@pytest.mark.parametrize("field,bad", [("status", "failed"), ("output_hash", "wrong"), ("tool_version_id", "wrong"), ("inputs", {})])
def test_receipt_signature_tampering_is_rejected_even_when_rehashed(field, bad):
    data = fixture()
    artifact = data["records"][data["artifact_heads"]["day:gross"]]
    receipt = data["records"][artifact["metadata"]["receipt_id"]]
    receipt["value"][field] = bad
    receipt["content_hash"] = digest(receipt["value"])
    assert not current(audit_provenance(**data))


def test_declared_head_values_are_verified_not_trusted_from_notifications():
    data = fixture()
    data["expected_sources"]["source:day:fx"] = {"GBP": "1.31"}
    result = audit_provenance(**data)
    assert not result["head_validation_pass"]
    assert current(result) == {"day:gross"}


def test_live_head_immutable_identity_is_independently_reconstructed():
    data = fixture()
    old = data["source_heads"]["source:day:orders"]
    new = "fixture:source:invented"
    data["records"][new] = {**data["records"][old], "id": new}
    data["source_heads"]["source:day:orders"] = new
    result = audit_provenance(**data)
    assert not result["head_validation_pass"]
    assert "head_immutable_identity_mismatch:source:day:orders" in result["head_errors"]["source:day:orders"]


@pytest.mark.parametrize("mutation", ["wrong_port", "wrong_logical", "wrong_params", "missing_receipt", "corrupt_blob"])
def test_metadata_or_content_corruption_cannot_be_claimed_current(mutation):
    data = fixture()
    item = data["records"][data["artifact_heads"]["day:gross"]]
    if mutation == "wrong_port":
        item["metadata"]["inputs"] = {"wrong": next(iter(item["metadata"]["inputs"].values()))}
    elif mutation == "wrong_logical":
        item["logical_id"] = "artifact:wrong"
    elif mutation == "wrong_params":
        item["metadata"]["params"] = {"unsupported": True}
    elif mutation == "missing_receipt":
        del data["records"][item["metadata"]["receipt_id"]]
    else:
        item["value"] = {"wrong": "unhashed"}
    assert not current(audit_provenance(**data))


def test_missing_artifact_head_is_scored_instead_of_dropped():
    data = fixture()
    del data["artifact_heads"]["day:report"]
    result = audit_provenance(**data)
    assert len(result["artifacts"]) == 3
    assert not result["artifacts"]["day:report"]["provenance_current"]


def test_incomplete_declared_current_state_is_an_oracle_contract_failure():
    data = fixture()
    del data["expected_tools"]["tool:convert_to_usd"]
    with pytest.raises(OracleContractError, match="incomplete"):
        audit_provenance(**data)


def test_numeric_truth_is_deliberately_separate_from_provenance_validity():
    data = fixture()
    # A correctly bound receipt can still contain the wrong calculation. The
    # caller must ALSO compare against retail_oracle's independent Decimal result.
    old = data["records"][data["artifact_heads"]["day:report"]]
    put_artifact(data, data["recipes"][2], old["metadata"]["inputs"], {"wrong_number": 999}, "wrong")
    assert audit_provenance(**data)["all_provenance_current"]


@pytest.mark.parametrize("binding", ["source", "tool"])
def test_equal_value_in_place_receipt_rebinding_cannot_fake_a_new_execution(binding):
    data = fixture()
    if binding == "source":
        orders = deepcopy(data["expected_sources"]["source:day:orders"])
        orders[0]["gross_cents"], orders[1]["gross_cents"] = 49, 51
        new_id = put_source(data, "day:orders", orders)
        item = data["records"][data["artifact_heads"]["day:gross"]]
        item["metadata"]["inputs"]["orders"] = new_id
    else:
        new_id = put_tool(data, "convert_to_usd", "2")
        item = data["records"][data["artifact_heads"]["day:usd"]]
        item["metadata"]["tool_version_id"] = new_id
    receipt = data["records"][item["metadata"]["receipt_id"]]
    receipt["value"]["inputs"] = deepcopy(item["metadata"]["inputs"])
    receipt["value"]["tool_version_id"] = item["metadata"]["tool_version_id"]
    receipt["content_hash"] = digest(receipt["value"])
    result = audit_provenance(**data)
    assert not result["artifacts"]["day:report"]["provenance_current"]
    assert any("execution_receipt_immutable_identity_mismatch" in r for r in result["artifacts"]["day:report"]["reasons"])


@pytest.mark.parametrize("malformed", ["source_metadata", "record", "tool_id", "receipt_id", "artifact_head"])
def test_malformed_snapshot_is_a_recorded_noncurrent_outcome(malformed):
    data = fixture()
    item = data["records"][data["artifact_heads"]["day:gross"]]
    if malformed == "source_metadata":
        data["records"][data["source_heads"]["source:day:orders"]]["metadata"] = None
    elif malformed == "record":
        data["records"][data["source_heads"]["source:day:orders"]] = []
    elif malformed == "tool_id":
        item["metadata"]["tool_version_id"] = []
    elif malformed == "receipt_id":
        item["metadata"]["receipt_id"] = {}
    else:
        data["artifact_heads"]["day:gross"] = []
    assert not audit_provenance(**data)["all_provenance_current"]


def test_scored_immutable_anchor_is_explicit_and_accepts_new_records():
    data = fixture()
    assert audit_provenance(**data)["immutable_anchor_pass"] is None
    prior = deepcopy(data["records"])
    old = data["records"][data["artifact_heads"]["day:gross"]]
    put_artifact(data, data["recipes"][0], old["metadata"]["inputs"], old["value"], "new")
    result = audit_provenance(**data, prior_records=prior)
    assert result["immutable_anchor_provided"] and result["immutable_anchor_pass"]
    assert result["all_provenance_current"]


def test_anchor_rejects_self_consistent_rebinding_of_an_old_immutable_artifact():
    data = fixture()
    prior = deepcopy(data["records"])
    orders = deepcopy(data["expected_sources"]["source:day:orders"])
    orders[0]["gross_cents"], orders[1]["gross_cents"] = 49, 51
    new_source = put_source(data, "day:orders", orders)
    item = data["records"][data["artifact_heads"]["day:gross"]]
    item["metadata"]["inputs"]["orders"] = new_source
    old_receipt = data["records"][item["metadata"]["receipt_id"]]
    value = {**deepcopy(old_receipt["value"]), "inputs": deepcopy(item["metadata"]["inputs"])}
    new_receipt = record("execution", old_receipt["logical_id"], value)
    data["records"][new_receipt["id"]] = new_receipt
    item["metadata"]["receipt_id"] = new_receipt["id"]
    # An internally consistent poststate is insufficient without old-record anchoring.
    assert audit_provenance(**data)["all_provenance_current"]
    result = audit_provenance(**data, prior_records=prior)
    assert not result["immutable_anchor_pass"] and not result["all_provenance_current"]
    assert not result["artifacts"]["day:report"]["provenance_current"]


def test_anchor_checks_unreferenced_old_records_and_missing_records():
    data = fixture()
    extra = record("source", "source:old:unused", [])
    data["records"][extra["id"]] = extra
    prior = deepcopy(data["records"])
    del data["records"][extra["id"]]
    result = audit_provenance(**data, prior_records=prior)
    assert not result["immutable_anchor_pass"]
    assert result["immutable_anchor_errors"][extra["id"]] == "previous_immutable_record_missing"
    assert all(v["provenance_current"] for v in result["artifacts"].values())
    assert not result["all_provenance_current"]


def test_empty_anchor_is_rejected_and_complete_anchor_exposes_digest():
    data = fixture()
    with pytest.raises(OracleContractError, match="nonempty complete"):
        audit_provenance(**data, prior_records={})
    result = audit_provenance(**data, prior_records=deepcopy(data["records"]))
    assert result["immutable_anchor_records"] == len(data["records"])
    assert result["immutable_anchor_sha256"] == digest(data["records"])


def staging_fixture():
    return {"day:orders": [{"order_id": "a", "region": "UK", "currency": "GBP", "gross_cents": 510},
                           {"order_id": "b", "region": "UK", "currency": "GBP", "gross_cents": 200}],
            "day:refunds": [], "day:fx": {"GBP": "1.25", "USD": "1"}}


def patch(source, operation, **parameters):
    return {"source": source, "operation": operation, "parameters": parameters}


def test_independent_quantity_fx_and_refund_staging_preserves_original():
    sources = staging_fixture()
    before = deepcopy(sources)
    mutations = [patch("day:orders", "quantity_delta", order_id="a", unit_price_gbp="2.55", raw_quantity=2,
                        delta_quantity=2, new_quantity=4, old_gross_cents=510, new_gross_cents=1020),
                 patch("day:fx", "fx_set", GBP="1.28"),
                 patch("day:refunds", "refund_add", order_id="b", refund_cents=20)]
    expected = deepcopy(before)
    expected["day:orders"][0]["gross_cents"] = 1020
    expected["day:fx"]["GBP"] = "1.28"
    expected["day:refunds"] = [{"order_id": "b", "refund_cents": 20}]
    assert stage_sources(sources, mutations) == expected
    assert sources == before


def test_independent_offset_preserves_aggregate_and_noop_preserves_canonical_rows():
    sources = staging_fixture()
    staged = stage_sources(sources, [patch("day:orders", "offset_gross", first="a", second="b", delta_cents=3,
                                         first_old_gross_cents=510, second_old_gross_cents=200)])
    assert [r["gross_cents"] for r in staged["day:orders"]] == [513, 197]
    assert stage_sources(sources, [patch("day:orders", "reorder")]) == sources


def test_independent_withdrawal_and_tool_notification():
    sources = staging_fixture()
    assert stage_sources(sources, [patch("day:fx", "remove")])["day:fx"] is None
    assert stage_sources(sources, [{"operation": "tool_version", "tool": "convert_to_usd", "parameters": {"version": "2"}}]) == sources


@pytest.mark.parametrize("bad", [
    patch("day:refunds", "refund_add", order_id="a", refund_cents=999),
    patch("day:orders", "quantity_delta", order_id="a", unit_price_gbp="2.55", raw_quantity=2,
          delta_quantity=2, new_quantity=4, old_gross_cents=510, new_gross_cents=1021),
    patch("day:orders", "offset_gross", first="a", second="a", delta_cents=3, first_old_gross_cents=510, second_old_gross_cents=510),
    patch("day:fx", "fx_set", GBP="NaN"),
    patch("day:orders", "invented_operation"),
])
def test_independent_staging_refuses_inconsistent_patch(bad):
    with pytest.raises(OracleContractError):
        stage_sources(staging_fixture(), [bad])
