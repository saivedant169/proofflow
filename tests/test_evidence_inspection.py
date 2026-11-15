"""Generation-bound evidence reads: real recipes, explicit native graph double.

These checks cover the API's selected-artifact envelope and refusal behavior.
They do not substitute for the separate real HydraDB acceptance run.
"""
from __future__ import annotations

import copy
import json
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest

from proofflow import importing, runtime as runtime_module
from proofflow.artifacts import canonical_json, digest
from proofflow.browser_import import active_import
from test_api import TestGraphClient, seed
from test_browser_import import (
    app, artifact_nodes, browser, csv_body, evidence, graph_factory, post,
)


FORBIDDEN_KEYS = {
    "value", "saved_value", "display_saved_value", "metadata", "params",
    "csv_text", "session_id", "rates", "summary",
}


def inspect_response(client, generation, artifact_id):
    return client.get(
        f"/api/import/evidence/{quote(artifact_id, safe='')}",
        params={"generation": generation},
    )


def inspect(client, generation, artifact_id):
    response = inspect_response(client, generation, artifact_id)
    assert response.status_code == 200, response.text
    assert response.headers.get("Cache-Control") == "no-store"
    return response.json()


def report_id(state, key="company"):
    return next(report["id"] for report in state["reports"] if report["key"] == key)


def assert_no_payload(value):
    if isinstance(value, dict):
        assert not FORBIDDEN_KEYS.intersection(value)
        for child in value.values():
            assert_no_payload(child)
    elif isinstance(value, list):
        for child in value:
            assert_no_payload(child)


def assert_refused(response, status):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert "artifact" not in body and "receipt" not in body
    assert_no_payload(body)


def test_selected_envelope_binds_generation_and_receipt_without_payload(browser):
    created = post(browser, "create", csv_body())
    target = report_id(created)
    original = evidence(browser, target)
    result = inspect(browser, created["generation"], target)

    assert result["schema_version"] == 1
    assert result["generation"] == created["generation"]
    assert result["incomplete_update"] is False
    assert result["backend"]["engine"] == "HydraDB OSS"
    assert result["backend"]["fallback"] is False
    assert type(result["backend"]["native_queries"]) is int
    assert result["backend"]["native_queries"] > 0
    artifact = result["artifact"]
    assert artifact["id"] == artifact["current_head_id"] == target
    assert artifact["kind"] == "artifact" and artifact["state"] == "current"
    assert artifact["reasons"] == []
    assert artifact["content_hash"] == original["artifact"]["content_hash"]
    assert artifact["logical_id"] == original["artifact"]["logical_id"]
    receipt = result["receipt"]
    assert receipt["id"] == original["receipt"]["id"]
    assert receipt["content_hash"] == digest({
        key: value for key, value in original["receipt"].items() if key != "id"
    })
    assert receipt["tool"] == "compose_report" and receipt["status"] == "success"
    assert receipt["output_id"] == target
    assert receipt["output_hash"] == artifact["content_hash"]
    assert receipt["tool_version_id"] == original["receipt"]["tool_version_id"]
    assert {item["name"]: item["id"] for item in result["inputs"]} == original["receipt"]["inputs"]
    assert all(item["kind"] == "artifact" and item["inspectable"] is True for item in result["inputs"])
    assert result["recorded_changed_source_paths"] == []
    assert isinstance(result["path_scope"], str) and result["path_scope"]
    assert_no_payload(result)
    assert csv_body()["csv_text"] not in json.dumps(result)
    # The existing browser endpoint still supplies the unchanged full inspector.
    assert evidence(browser, target) == original


def test_selected_inputs_are_followable_artifacts_or_noninspectable_sources(browser):
    created = post(browser, "create", csv_body())
    nodes = artifact_nodes(created)
    gross = inspect(browser, created["generation"], nodes["import:metric:gross"]["id"])
    assert len(gross["inputs"]) == 1
    source = gross["inputs"][0]
    assert source["kind"] == "source" and source["inspectable"] is False
    assert source["logical_id"] == "source:csv:orders"
    assert source["content_hash"] == next(
        item["content_hash"] for item in created["dataset"]["sources"] if item["name"] == "orders"
    )
    company = inspect(browser, created["generation"], report_id(created))
    followed = inspect(browser, created["generation"], company["inputs"][0]["id"])
    assert followed["receipt"]["tool"] == "company_total"
    assert_no_payload(gross)
    assert_no_payload(followed)


def test_fx_path_and_retained_receipt_remain_inspectable_after_refresh(browser):
    created = post(browser, "create", csv_body())
    generation = created["generation"]
    old_company = report_id(created)
    support_id = artifact_nodes(created)["import:metric:support"]["id"]
    support_before = inspect(browser, generation, support_id)
    original = inspect(browser, generation, old_company)
    fx_id = next(source["id"] for source in created["dataset"]["sources"] if source["name"] == "fx")

    updated = post(browser, "update", csv_body(rate="1.30"))
    stale = inspect(browser, generation, old_company)
    assert stale["artifact"]["state"] == "stale"
    assert stale["artifact"]["reasons"] == [{
        "id": fx_id, "reason": "version_changed", "current_id": next(
            source["id"] for source in updated["dataset"]["sources"] if source["name"] == "fx"
        ),
    }]
    assert stale["receipt"] == original["receipt"]
    paths = stale["recorded_changed_source_paths"]
    assert paths and all(path["target_id"] == old_company for path in paths)
    assert any(path["source_id"] == fx_id for path in paths)
    assert any(node["logical_id"] == "import:metric:regional" for path in paths for node in path["nodes"])
    assert any(node["logical_id"] == "import:metric:company" for path in paths for node in path["nodes"])
    for path in paths:
        assert path["nodes"][0]["id"] == path["source_id"]
        assert path["nodes"][-1]["id"] == old_company
        assert path["edges"]
        assert all(edge["kind"] in {"CONSUMED", "PRODUCED", "USED_TOOL"} for edge in path["edges"])
    support_stale_phase = inspect(browser, generation, support_id)
    assert support_stale_phase["artifact"]["state"] == "current"
    assert support_stale_phase["receipt"] == support_before["receipt"]
    assert support_stale_phase["recorded_changed_source_paths"] == []

    refreshed = post(browser, "refresh")
    assert refreshed["generation"] == updated["generation"] == generation
    replacement = report_id(refreshed)
    assert replacement != old_company
    old_after = inspect(browser, generation, old_company)
    new_after = inspect(browser, generation, replacement)
    assert old_after["artifact"]["state"] == "stale"
    assert old_after["artifact"]["current_head_id"] == replacement
    assert old_after["receipt"] == original["receipt"]
    assert old_after["recorded_changed_source_paths"] == paths
    assert new_after["artifact"]["state"] == "current"
    assert new_after["artifact"]["current_head_id"] == replacement
    assert new_after["receipt"]["id"] != original["receipt"]["id"]
    assert new_after["recorded_changed_source_paths"] == []
    assert inspect(browser, generation, support_id)["receipt"] == support_before["receipt"]
    for result in (stale, support_stale_phase, old_after, new_after):
        assert_no_payload(result)


def test_reads_do_not_recalculate_mutate_graph_or_change_operation(browser, graph_factory):
    created = post(browser, "create", csv_body())
    mutations = graph_factory.mutation_count
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as preflight, \
            patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as recorded:
        for report in created["reports"]:
            inspect(browser, created["generation"], report["id"])
    assert preflight.call_count == recorded.call_count == 0
    assert graph_factory.mutation_count == mutations
    latest = browser.get("/api/import/state").json()
    assert latest["last_operation"] == created["last_operation"]
    assert latest["executions"] == created["executions"]


def test_wrong_generation_and_replaced_workspace_are_refused(browser):
    first = post(browser, "create", csv_body())
    assert_refused(inspect_response(browser, "0" * 32, report_id(first)), 409)
    second = post(browser, "create", csv_body())
    assert second["generation"] != first["generation"]
    assert_refused(inspect_response(browser, first["generation"], report_id(first)), 409)
    assert_refused(inspect_response(browser, second["generation"], report_id(first)), 404)


def test_foreign_unknown_source_and_execution_ids_are_refused(app, browser):
    created = post(browser, "create", csv_body())
    generation = created["generation"]
    target = report_id(created)
    unknown = target.rsplit(":", 1)[0] + ":" + "0" * 64
    assert_refused(inspect_response(browser, generation, unknown), 404)
    assert_refused(inspect_response(browser, generation, created["dataset"]["sources"][0]["id"]), 404)
    assert_refused(inspect_response(browser, generation, created["executions"][0]["id"]), 404)
    with TestClient(app) as other:
        seed(other)
        foreign = post(other, "create", csv_body())
        assert_refused(inspect_response(other, foreign["generation"], target), 404)
        assert_refused(inspect_response(browser, generation, report_id(foreign)), 404)


def test_incomplete_update_is_refused_atomically(app, browser, graph_factory):
    created = post(browser, "create", csv_body())
    with app.state.manager.session(browser.cookies["proofflow_session"]) as owner:
        with active_import(owner, graph_factory) as imported:
            imported.metadata["incomplete_update"] = True
            imported.save()
    assert_refused(inspect_response(browser, created["generation"], report_id(created)), 409)


@pytest.mark.parametrize("damage", [
    "graph_outage", "missing_node", "missing_edge", "missing_path_witness", "corrupt_receipt",
])
def test_missing_native_or_stored_evidence_never_returns_a_positive_envelope(
        app, browser, graph_factory, damage):
    created = post(browser, "create", csv_body())
    target = report_id(created)
    raw = evidence(browser, target)
    with app.state.manager.session(browser.cookies["proofflow_session"]) as owner:
        with active_import(owner, graph_factory) as imported:
            if damage == "graph_outage":
                graph_factory.available = False
            elif damage == "missing_node":
                imported.graph.data["nodes"].pop(target)
            elif damage == "missing_edge":
                imported.graph.data["edges"].remove((raw["receipt"]["id"], target, "PRODUCED"))
            elif damage == "missing_path_witness":
                graph_factory.suppress_next_path = True
            else:
                receipt = imported.store.get(raw["receipt"]["id"])
                (imported.store.blobs / f"{receipt.content_hash}.json").write_text("corrupt receipt")
    response = inspect_response(browser, created["generation"], target)
    assert response.status_code in {409, 503}, response.text
    assert set(response.json()) == {"error"}
    assert_no_payload(response.json())


@pytest.mark.parametrize("damage", [
    "vertex_id", "unknown_record", "kind", "workspace", "disconnected_edge", "edge_kind",
    "payload_content_hash", "payload_logical_id", "payload_metadata",
])
def test_malformed_native_witness_never_returns_selected_evidence(browser, damage):
    created = post(browser, "create", csv_body())
    original_paths = TestGraphClient.paths

    def malformed(client, *args, **kwargs):
        paths = copy.deepcopy(original_paths(client, *args, **kwargs))
        if not paths:
            return paths
        path = paths[0]
        if damage == "vertex_id":
            path["nodes"][0]["id"] += 1
        elif damage == "unknown_record":
            path["nodes"][0]["properties"]["key"] = {"String": "unowned-sentinel"}
        elif damage == "kind":
            path["nodes"][0]["properties"]["kind"] = {"String": "forged-kind"}
        elif damage == "workspace":
            path["nodes"][0]["properties"]["workspace"] = {"String": "foreign-workspace"}
        elif damage == "disconnected_edge":
            path["relationships"][0]["dst"] += 1
        elif damage.startswith("payload_"):
            # Retain valid native IDs, manifest keys, kinds, workspace and edges.
            # Only the stored native payload disagrees with immutable records.
            for node in path["nodes"]:
                payload = json.loads(node["properties"]["payload"]["String"])
                if damage == "payload_content_hash":
                    payload["content_hash"] = "0" * 64
                elif damage == "payload_logical_id":
                    payload["logical_id"] = "forged-logical-id"
                else:
                    payload["title"] = "forged-private-metadata"
                node["properties"]["payload"] = {"String": json.dumps(payload)}
        else:
            path["relationships"][0]["properties"]["kind"] = {"String": "FORGED_EDGE"}
        return paths

    with patch.object(TestGraphClient, "paths", malformed):
        response = inspect_response(browser, created["generation"], report_id(created))
    assert_refused(response, 503)
    assert "unowned-sentinel" not in response.text


@pytest.mark.parametrize("field", [
    "output_id", "output_hash", "tool", "tool_version_id", "inputs", "status", "params",
])
def test_rehashed_receipt_must_still_match_the_selected_artifact(
        app, browser, graph_factory, field):
    created = post(browser, "create", csv_body())
    target = report_id(created)
    with app.state.manager.session(browser.cookies["proofflow_session"]) as owner:
        with active_import(owner, graph_factory) as imported:
            artifact = imported.store.get(target)
            receipt_id = artifact.metadata["receipt_id"]
            receipt = imported.store.read(receipt_id)
            replacements = {
                "output_id": report_id(created, "region"),
                "output_hash": "0" * 64,
                "tool": "company_total",
                "tool_version_id": imported.store.get_head("tool:company_total").id,
                "inputs": {},
                "status": "failed",
                "params": {"forged_parameter": True},
            }
            receipt[field] = replacements[field]
            # Deliberately reseal the altered blob and manifest hash. The check
            # must reject inconsistent provenance, not just detect broken bytes.
            replacement_hash = digest(receipt)
            (imported.store.blobs / f"{replacement_hash}.json").write_text(canonical_json(receipt))
            with imported.store.db:
                imported.store.db.execute(
                    "UPDATE records SET content_hash = ? WHERE id = ?", (replacement_hash, receipt_id),
                )
            assert imported.store.read(receipt_id) == receipt
    assert_refused(inspect_response(browser, created["generation"], target), 409)


def test_suppressed_upstream_forward_edge_is_refused_with_reverse_ancestry_intact(
        app, browser, graph_factory):
    created = post(browser, "create", csv_body())
    target = report_id(created)
    regional = artifact_nodes(created)["import:metric:regional"]["id"]
    regional_evidence = evidence(browser, regional)
    net_id = regional_evidence["receipt"]["inputs"]["net"]
    receipt_id = regional_evidence["receipt"]["id"]
    assert created["impact"]["changed_source_ids"] == []
    with app.state.manager.session(browser.cookies["proofflow_session"]) as owner:
        with active_import(owner, graph_factory) as imported:
            ancestors = imported.graph.ancestors([target], max_depth=15)
            assert {net_id, receipt_id, regional} <= set(ancestors)
            assert imported.runtime.currentness(target).state == "current"
    original_paths = TestGraphClient.paths
    suppressed = []

    def missing_forward(client, source_id, target_id, max_depth=15):
        if (source_id, target_id, max_depth) == (net_id, receipt_id, 1):
            suppressed.append((source_id, target_id))
            return []
        return original_paths(client, source_id, target_id, max_depth=max_depth)

    with patch.object(TestGraphClient, "paths", missing_forward):
        response = inspect_response(browser, created["generation"], target)
    assert suppressed == [(net_id, receipt_id)]
    assert_refused(response, 503)


@pytest.mark.parametrize("field", ["status", "params"])
def test_rehashed_intermediate_receipt_is_refused_before_forward_queries(
        app, browser, graph_factory, field):
    created = post(browser, "create", csv_body())
    target = report_id(created)
    regional = artifact_nodes(created)["import:metric:regional"]["id"]
    with app.state.manager.session(browser.cookies["proofflow_session"]) as owner:
        with active_import(owner, graph_factory) as imported:
            artifact = imported.store.get(regional)
            receipt_id = artifact.metadata["receipt_id"]
            receipt = imported.store.read(receipt_id)
            receipt[field] = "failed" if field == "status" else {"forged_parameter": True}
            replacement_hash = digest(receipt)
            (imported.store.blobs / f"{replacement_hash}.json").write_text(canonical_json(receipt))
            with imported.store.db:
                imported.store.db.execute(
                    "UPDATE records SET content_hash = ? WHERE id = ?", (replacement_hash, receipt_id),
                )
            assert imported.store.read(receipt_id) == receipt
            # Reverse traversal and hash integrity alone still deem the final
            # report current; its ancestor's semantic receipt must be checked.
            assert imported.runtime.currentness(target).state == "current"
    with patch.object(TestGraphClient, "paths", side_effect=AssertionError("Forward queries must not start")):
        response = inspect_response(browser, created["generation"], target)
    assert_refused(response, 409)
