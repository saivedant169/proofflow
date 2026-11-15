from copy import deepcopy

import pytest

from proofflow.artifacts import ArtifactStore
from proofflow.importing import (CSVImportError, ImportedDataset, MAX_BYTES, apply_import, parse_csv)
from proofflow.runtime import ProofFlowRuntime
from test_runtime import UnitTestGraph


CSV = b"order_id,region,currency,gross_cents,refund_cents,ticket_count\na,APAC,USD,10000,1000,0\nb,EMEA,EUR,20000,2000,2\n"


def test_user_regions_and_exact_cents_with_explicit_rates(tmp_path):
    dataset = parse_csv(CSV, rates={"EUR": "1.10"}, region="EMEA")
    store = ArtifactStore(tmp_path)
    graph = UnitTestGraph()
    runtime = ProofFlowRuntime(store, graph)
    try:
        first = apply_import(runtime, dataset)
        assert first["tool_call_count"] == 8
        assert [report["claims"][0]["value"] for report in first["reports"]] == [28800, 19800]
        support_id = first["support"]["id"]
        second = apply_import(runtime, parse_csv(CSV, rates={"EUR": "1.20"}, region="EMEA"))
        assert second["tool_call_count"] == 4
        assert [report["claims"][0]["value"] for report in second["reports"]] == [30600, 21600]
        assert second["support"]["id"] == support_id
        assert {item["logical_id"] for item in second["affected_artifacts"]} == {
            "import:metric:regional", "import:metric:company", "import:report:company", "import:report:region"}
        assert all(report["state"] == "current" and report["recomputation_parity"] for report in second["reports"])
    finally:
        store.close()


def test_row_order_only_import_is_noop_and_zero_support_is_valid(tmp_path):
    store = ArtifactStore(tmp_path)
    runtime = ProofFlowRuntime(store, UnitTestGraph())
    try:
        first = apply_import(runtime, parse_csv(CSV, rates={"EUR": "1.10"}, region="EMEA"))
        lines = CSV.splitlines()
        reordered = b"\n".join([lines[0], lines[2], lines[1]]) + b"\n"
        same = apply_import(runtime, parse_csv(reordered, rates={"EUR": "1.1"}, region="EMEA"))
        assert same["changed_source_version_ids"] == []
        assert same["tool_call_count"] == 0
        assert [r["id"] for r in same["reports"]] == [r["id"] for r in first["reports"]]
        zero = apply_import(runtime, parse_csv(CSV.replace(b"2000,2", b"2000,0"), rates={"EUR": "1.1"}, region="EMEA"))
        assert zero["support"]["value"] == {"regions": {}}
        assert zero["tool_call_count"] == 1
        assert [r["id"] for r in zero["reports"]] == [r["id"] for r in first["reports"]]
    finally:
        store.close()


@pytest.mark.parametrize("payload,rates,region", [
    (CSV, {}, "EMEA"),
    (CSV, {"EUR": "NaN"}, "EMEA"),
    (CSV, {"EUR": "1.1", "USD": "2"}, "EMEA"),
    (CSV, {"EUR": "1.1"}, "EU"),
    (CSV.replace(b"b,EMEA", b"a,EMEA"), {"EUR": "1.1"}, "EMEA"),
    (CSV.replace(b"20000,2000", b"20000,20001"), {"EUR": "1.1"}, "EMEA"),
    (CSV.replace(b"10000,1000", b"100.00,1000"), {"EUR": "1.1"}, "EMEA"),
    (CSV.replace(b"a,APAC,USD", b"a,EMEA,USD"), {"EUR": "1.1"}, "EMEA"),
    (CSV.replace(b"2000,2", b"2000,10001"), {"EUR": "1.1"}, "EMEA"),
    (b"order_id,order_id,region,currency,gross_cents\na,b,APAC,USD,10", {}, "APAC"),
    (b"order_id,region,currency,gross_cents\na,APAC,USD,10,extra", {}, "APAC"),
    (b"x" * (MAX_BYTES + 1), {}, None),
])
def test_bad_input_rejected(payload, rates, region):
    with pytest.raises(CSVImportError):
        parse_csv(payload, rates=rates, region=region)


def test_region_change_and_bad_arithmetic_are_refused_before_writes(tmp_path):
    store = ArtifactStore(tmp_path)
    graph = UnitTestGraph()
    runtime = ProofFlowRuntime(store, graph)
    try:
        dataset = parse_csv(CSV, rates={"EUR": "1.1"}, region="EMEA")
        apply_import(runtime, dataset)
        original_heads = {row.logical_id: row.id for row in store.heads()}
        with pytest.raises(CSVImportError, match="existing selected region"):
            apply_import(runtime, parse_csv(CSV, rates={"EUR": "1.2"}, region="APAC"))
        altered = deepcopy(dataset.sources)
        altered["fx"]["EUR"] = "NaN"
        with pytest.raises(ValueError):
            apply_import(runtime, ImportedDataset(altered, dataset.region, dataset.row_count, dataset.content_sha256))
        assert {row.logical_id: row.id for row in store.heads()} == original_heads
    finally:
        store.close()


def test_row_and_aggregate_ticket_limits_apply_before_execution():
    header = "order_id,region,currency,gross_cents,ticket_count\n"
    too_many_rows = (header + "\n".join(f"o{i},APAC,USD,10,0" for i in range(1001))).encode()
    with pytest.raises(CSVImportError, match="1000 order rows"):
        parse_csv(too_many_rows)
    expanded = (header + "a,APAC,USD,10,6000\nb,APAC,USD,10,5000\n").encode()
    with pytest.raises(CSVImportError, match="expanded counting rows"):
        parse_csv(expanded)
