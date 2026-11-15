"""Frozen browser CSV acceptance cases, real tools, and an explicit graph double.

No live database/model is used here. Independent canonical imports verify recipe
semantics; wrapped arithmetic calls verify disclosed operation accounting.
"""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest

from proofflow import importing, runtime as runtime_module
from proofflow.api import create_app
from proofflow.artifacts import ArtifactStore
from proofflow.browser_import import active_import
from proofflow.graph import GraphError
from proofflow.runtime import ProofFlowRuntime
from test_api import TestGraphFactory, assert_error, seed


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "browser_csv_v1"
MANIFEST = json.loads((FIXTURES / "acceptance_manifest.json").read_text())
CASES = {case["file"]: case for case in MANIFEST["cases"]}


def csv_body(name="valid_non_eu.csv", *, rate=None):
    data = (FIXTURES / name).read_bytes()
    frozen = MANIFEST["files"][name]
    assert len(data) == frozen["bytes"]
    assert hashlib.sha256(data).hexdigest() == frozen["sha256"]
    case = CASES[name]
    rates = dict(case["rates"])
    if rate is not None:
        rates["EUR"] = rate
    return {"csv_text": data.decode(), "rates": rates, "region": case["region"]}


class ImportGraphFactory(TestGraphFactory):
    def __init__(self):
        super().__init__()
        self.fail_after_nodes = None

    def __call__(self, *, namespace):
        graph = super().__call__(namespace=namespace)
        original = graph.put_node

        def put_node(*args, **kwargs):
            if self.fail_after_nodes is not None:
                if self.fail_after_nodes == 0:
                    self.fail_after_nodes = None
                    raise GraphError("Injected partial source publication failure")
                self.fail_after_nodes -= 1
            return original(*args, **kwargs)

        graph.put_node = put_node
        return graph

    @property
    def mutation_count(self):
        return sum(graph.mutations for graph in self.clients)


@pytest.fixture
def graph_factory():
    return ImportGraphFactory()


@pytest.fixture
def app(tmp_path, graph_factory):
    return create_app(state_dir=tmp_path / "sessions", graph_factory=graph_factory,
                      static_dir=tmp_path / "no-static")


@pytest.fixture
def browser(app):
    with TestClient(app) as client:
        seed(client)
        yield client


def post(browser, operation, body=None):
    response = browser.post(f"/api/import/{operation}", json={} if body is None else body)
    assert response.status_code == 200, response.text
    return response.json()


def state(browser):
    response = browser.get("/api/import/state")
    assert response.status_code == 200, response.text
    return response.json()


def report_values(value):
    return {report["key"]: report["claims"][0]["value"] for report in value["reports"]}


def artifact_nodes(value):
    return {node["logical_id"]: node for node in value["graph"]["nodes"]
            if node["kind"] == "artifact" and node["current_head"]}


def evidence(browser, artifact_id):
    response = browser.get(f"/api/import/evidence/{quote(artifact_id, safe='')}")
    assert response.status_code == 200, response.text
    return response.json()


def assert_accounting(accounting, preflight, recorded, verification):
    assert accounting["preflight_calculation_count"] == preflight
    assert accounting["recorded_tool_call_count"] == recorded
    assert accounting["verification_calculation_count"] == verification
    assert accounting["total_calculation_count"] == preflight + recorded + verification


def signature(record, value, logical_ids):
    metadata = record["metadata"]
    return {"content_hash": record["content_hash"], "value": value,
            "tool": metadata["tool"], "params": metadata["params"],
            "inputs": {name: logical_ids[node_id] for name, node_id in metadata["inputs"].items()}}


def test_preview_executes_eight_preflight_calculations_without_publication(browser, graph_factory):
    before = graph_factory.mutation_count
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as preflight, \
            patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as runtime_calc:
        result = post(browser, "preview", csv_body())
    assert result["valid"] is True and result["persisted"] is False
    assert result["content_sha256"] == MANIFEST["files"]["valid_non_eu.csv"]["sha256"]
    assert result["row_count"] == 2 and result["selected_region"] == "NORTH"
    assert result["regions"] == ["NORTH", "SOUTH"]
    assert result["supported_ticket_regions"] == ["NORTH", "SOUTH"]
    assert preflight.call_count == 8 and runtime_calc.call_count == 0
    assert_accounting(result["accounting"], 8, 0, 0)
    assert result["recorded_tool_calls"] == 0
    assert graph_factory.mutation_count == before
    assert_error(browser.get("/api/import/state"), 404)


@pytest.mark.parametrize("fixture_name", ["valid_non_eu.csv", "valid_zero_support.csv"])
def test_create_matches_canonical_cli_recipe_and_actual_accounting(browser, tmp_path, graph_factory, fixture_name):
    body = csv_body(fixture_name)
    expected = CASES[fixture_name]
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as preflight, \
            patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as runtime_calc:
        created = post(browser, "create", body)
    assert created["mode"] == "guided_csv_import"
    assert created["incomplete_update"] is False
    assert created["dataset"]["source_csv_sha256"] == MANIFEST["files"][fixture_name]["sha256"]
    assert report_values(created) == {"company": expected["expected_company_usd_cents"],
                                      "region": expected["expected_region_usd_cents"]}
    assert all(len(report["claims"]) == 1 and report["state"] == "current" for report in created["reports"])
    assert preflight.call_count == 8 and runtime_calc.call_count == 8 + 11
    assert_accounting(created["last_operation"], 8, 8, 11)
    assert len(created["last_operation"]["tool_calls"]) == 8
    assert len(created["executions"]) == 8
    assert {source["name"] for source in created["dataset"]["sources"]} == {"orders", "refunds", "tickets", "fx"}

    # A second isolated runtime follows the public canonical CLI import path.
    store = ArtifactStore(tmp_path / "canonical-cli")
    graph = graph_factory(namespace=f"canonical-{store.workspace}")
    try:
        runtime = ProofFlowRuntime(store, graph)
        dataset = importing.parse_csv(body["csv_text"].encode(), rates=body["rates"], region=body["region"])
        importing.apply_import(runtime, dataset)
        cli_records = store.heads("artifact")
        cli_ids = {record.id: record.logical_id for record in store.heads()}
        cli_signatures = {record.logical_id: signature(record.to_dict(), store.read(record.id), cli_ids)
                          for record in cli_records}
        browser_ids = {node["id"]: node["logical_id"] for node in created["graph"]["nodes"]}
        browser_signatures = {}
        for logical_id, node in artifact_nodes(created).items():
            item = evidence(browser, node["id"])
            browser_signatures[logical_id] = signature(item["artifact"], item["artifact"]["saved_value"], browser_ids)
            assert item["receipt"]["tool"] == item["artifact"]["metadata"]["tool"]
        assert browser_signatures == cli_signatures
        assert len(browser_signatures) == 8
        assert set(node["id"] for node in artifact_nodes(created).values()).isdisjoint(record.id for record in cli_records)
        if fixture_name == "valid_zero_support.csv":
            assert browser_signatures[importing.SUPPORT_ARTIFACT]["value"]["regions"] == {}
            assert all(claim["unit"] == "USD cents" for report in created["reports"] for claim in report["claims"])
    finally:
        store.close()
        graph.close()


def test_fx_source_only_update_withholds_stale_claims_and_refreshes_four(browser):
    initial = post(browser, "create", csv_body())
    support = artifact_nodes(initial)[importing.SUPPORT_ARTIFACT]["id"]
    support_hash = evidence(browser, support)["artifact"]["content_hash"]
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as preflight, \
            patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as calculations:
        changed = post(browser, "update", csv_body(rate="1.30"))
    assert preflight.call_count == 8 and calculations.call_count == 0
    assert_accounting(changed["last_operation"], 8, 0, 0)
    assert changed["last_operation"]["changed_source_count"] == 1
    assert len(changed["impact"]["affected_artifacts"]) == 4
    assert report_values(changed) == {"company": None, "region": None}
    assert all(report["state"] == "stale" for report in changed["reports"])
    assert {report["key"]: report["claims"][0]["saved_value"] for report in changed["reports"]} == {
        "company": 30800, "region": 10800}
    proof = evidence(browser, initial["reports"][0]["id"])
    assert proof["artifact"]["state"] == "stale" and proof["paths"]
    assert proof["paths"][0]["target_id"] == initial["reports"][0]["id"]

    with patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as calculations:
        refreshed = post(browser, "refresh")
    assert calculations.call_count == 4 + 11
    assert_accounting(refreshed["last_operation"], 0, 4, 11)
    assert refreshed["last_refresh"]["executed_count"] == 4
    assert report_values(refreshed) == {"company": 31700, "region": 11700}
    assert artifact_nodes(refreshed)[importing.SUPPORT_ARTIFACT]["id"] == support
    assert evidence(browser, support)["artifact"]["content_hash"] == support_hash
    assert all(call["tool"] != "support_by_region" for call in refreshed["last_operation"]["tool_calls"])
    verified = post(browser, "verify")
    assert verified["passed"] is True
    assert_accounting(verified["accounting"], 0, 0, 11)


def test_equivalent_reorder_changes_raw_hash_but_preserves_sources_artifacts_and_receipts(browser):
    initial = post(browser, "create", csv_body())
    changed = post(browser, "update", csv_body("reordered_non_eu.csv"))
    assert changed["dataset"]["source_csv_sha256"] == MANIFEST["files"]["reordered_non_eu.csv"]["sha256"]
    assert changed["dataset"]["source_csv_sha256"] != initial["dataset"]["source_csv_sha256"]
    assert {item["name"]: item["id"] for item in changed["dataset"]["sources"]} == {
        item["name"]: item["id"] for item in initial["dataset"]["sources"]}
    assert artifact_nodes(changed) == artifact_nodes(initial)
    assert {item["id"] for item in changed["executions"]} == {item["id"] for item in initial["executions"]}
    assert changed["impact"]["affected_artifacts"] == []
    assert changed["last_operation"]["changed_source_count"] == 0
    assert changed["last_operation"]["noop"] is True
    assert_accounting(changed["last_operation"], 8, 0, 0)
    with patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as calculations:
        refreshed = post(browser, "refresh")
    assert calculations.call_count == 11
    assert_accounting(refreshed["last_operation"], 0, 0, 11)
    assert refreshed["last_refresh"]["executed_count"] == 0
    assert artifact_nodes(refreshed) == artifact_nodes(initial)


@pytest.mark.parametrize("fixture_name", ["malformed.csv", "oversized.csv"])
def test_invalid_csv_is_rejected_before_writes_and_preserves_import(browser, graph_factory, fixture_name):
    initial = post(browser, "create", csv_body())
    before = graph_factory.mutation_count
    for operation in ("preview", "create", "update"):
        assert_error(browser.post(f"/api/import/{operation}", json=csv_body(fixture_name)), 400)
    assert graph_factory.mutation_count == before
    remaining = state(browser)
    assert remaining["generation"] == initial["generation"]
    assert remaining["dataset"] == initial["dataset"]
    assert artifact_nodes(remaining) == artifact_nodes(initial)
    assert report_values(remaining) == {"company": 30800, "region": 10800}


def test_import_cookie_isolation_and_foreign_evidence_refusal(app, browser):
    first = post(browser, "create", csv_body())
    with TestClient(app) as other:
        assert_error(other.get("/api/import/state"), 401)
        assert_error(other.post("/api/import/preview", json=csv_body()), 401)
        seed(other)
        assert_error(other.get("/api/import/state"), 404)
        second = post(other, "create", csv_body("valid_zero_support.csv"))
        assert first["session_id"] != second["session_id"]
        assert_error(other.get(f"/api/import/evidence/{quote(first['reports'][0]['id'], safe='')}"), 404)
        post(browser, "update", csv_body(rate="1.30"))
        assert report_values(state(other)) == {"company": 16375, "region": 9375}


def test_import_state_reopens_durably_and_can_refresh(tmp_path, graph_factory):
    directory = tmp_path / "persistent-import"
    first_app = create_app(state_dir=directory, graph_factory=graph_factory, static_dir=tmp_path / "none")
    with TestClient(first_app) as first:
        seed(first)
        original = post(first, "create", csv_body())
        post(first, "update", csv_body(rate="1.30"))
        cookie = first.cookies.get("proofflow_session")
    new_app = create_app(state_dir=directory, graph_factory=graph_factory, static_dir=tmp_path / "none")
    with TestClient(new_app) as second:
        second.cookies.set("proofflow_session", cookie)
        restored = state(second)
        assert restored["session_id"] == original["session_id"]
        assert restored["generation"] == original["generation"]
        assert report_values(restored) == {"company": None, "region": None}
        refreshed = post(second, "refresh")
        assert report_values(refreshed) == {"company": 31700, "region": 11700}
        assert_accounting(refreshed["last_operation"], 0, 4, 11)


def test_create_revalidates_changed_input_after_preview(browser, graph_factory):
    post(browser, "preview", csv_body())
    before = graph_factory.mutation_count
    assert_error(browser.post("/api/import/create", json=csv_body("malformed.csv")), 400)
    assert graph_factory.mutation_count == before
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as preflight:
        created = post(browser, "create", csv_body(rate="1.30"))
    assert preflight.call_count == 8
    assert report_values(created) == {"company": 31700, "region": 11700}
    assert_accounting(created["last_operation"], 8, 8, 11)


def test_guided_demo_reset_preserves_the_separate_imported_workspace(browser):
    original = post(browser, "create", csv_body())
    changed = post(browser, "update", csv_body(rate="1.30"))
    demo_generation = browser.get("/api/state").json()["generation"]
    reset = browser.post("/api/reset", json={})
    assert reset.status_code == 200, reset.text
    assert reset.json()["generation"] != demo_generation
    imported = state(browser)
    assert imported["generation"] == original["generation"]
    assert imported["dataset"] == changed["dataset"]
    assert report_values(imported) == {"company": None, "region": None}
    assert report_values(post(browser, "refresh")) == {"company": 31700, "region": 11700}


def test_update_rejects_region_switch_and_caller_workspace_before_writes(browser, graph_factory):
    original = post(browser, "create", csv_body())
    switched = {**csv_body(), "region": "SOUTH"}
    injected = {**csv_body(), "workspace_id": "../caller-chosen-path"}
    before = graph_factory.mutation_count
    assert_error(browser.post("/api/import/update", json=switched), 400)
    assert_error(browser.post("/api/import/create", json=injected), 400)
    assert graph_factory.mutation_count == before
    preserved = state(browser)
    assert preserved["generation"] == original["generation"]
    assert preserved["dataset"] == original["dataset"]


def test_partial_source_failure_blocks_refresh_until_successful_resubmission(browser, graph_factory):
    original = post(browser, "create", csv_body())
    corrected = copy.deepcopy(csv_body())
    corrected["csv_text"] = corrected["csv_text"].replace("10000,1000,3", "12000,1500,3")
    assert corrected["csv_text"] != csv_body()["csv_text"]
    graph_factory.fail_after_nodes = 1
    assert_error(browser.post("/api/import/update", json=corrected), 503)
    partial = state(browser)
    assert partial["incomplete_update"] is True
    assert partial["dataset"]["source_csv_sha256"] == original["dataset"]["source_csv_sha256"]
    assert_error(browser.post("/api/import/refresh", json={}), 409)
    recovered = post(browser, "update", corrected)
    assert recovered["incomplete_update"] is False
    assert recovered["dataset"]["source_csv_sha256"] == hashlib.sha256(corrected["csv_text"].encode()).hexdigest()
    assert report_values(post(browser, "refresh")) == {"company": 32600, "region": 12600}


def test_transport_limit_rejects_declared_and_actual_chunked_oversize_before_writes(app, browser, graph_factory):
    original = post(browser, "create", csv_body())
    before = graph_factory.mutation_count
    cookie = browser.cookies.get("proofflow_session")
    limit = 8 * 1024 * 1024

    async def request(headers, chunks):
        scope = {"type": "http", "http_version": "1.1", "method": "POST",
                 "scheme": "http", "path": "/api/import/create", "raw_path": b"/api/import/create",
                 "root_path": "", "query_string": b"", "server": ("testserver", 80),
                 "client": ("testclient", 50000), "headers": [
                     (b"content-type", b"application/json"),
                     (b"cookie", f"proofflow_session={cookie}".encode()), *headers]}
        messages = []
        received = 0

        async def receive():
            nonlocal received
            index = received
            received += 1
            return {"type": "http.request", "body": chunks[index], "more_body": index < len(chunks) - 1}

        async def send(message):
            messages.append(message)

        await app(scope, receive, send)
        response = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
        assert response["status"] == 413
        assert json.loads(body)["error"]["code"] == "invalid_input"
        return received

    # A declared oversized body is refused without reading it at all.
    assert asyncio.run(request([(b"content-length", str(limit + 1).encode())], [])) == 0
    # No Content-Length: enforce the cumulative actual ASGI chunks, not a header.
    chunk = b" " * (1024 * 1024)
    assert asyncio.run(request([(b"transfer-encoding", b"chunked")], [chunk] * 8 + [b" "])) == 9
    assert graph_factory.mutation_count == before
    assert state(browser)["generation"] == original["generation"]

    # JSON escaping is allowed; the decoded UTF-8 CSV has its separate 1 MiB cap.
    unicode_csv = {"csv_text": "order_id,region,currency,gross_cents\norder1,北,USD,100\n", "region": "北"}
    encoded = json.dumps(unicode_csv, ensure_ascii=True).encode()
    assert b"\\u5317" in encoded
    preview = browser.post("/api/import/preview", content=encoded, headers={"content-type": "application/json"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["selected_region"] == "北"
    assert graph_factory.mutation_count == before


def test_incomplete_verification_returns_error_without_fabricated_accounting(app, browser, graph_factory):
    original = post(browser, "create", csv_body())
    with app.state.manager.session(browser.cookies.get("proofflow_session")) as owner:
        with active_import(owner, graph_factory) as imported:
            imported.runtime.remove_source("csv:refunds")
    with patch("proofflow.runtime.execute_tool", wraps=runtime_module.execute_tool) as calculations:
        failed = browser.post("/api/import/verify", json={})
    assert_error(failed, 409)
    assert "accounting" not in failed.json()
    assert calculations.call_count > 0, "The fixture must fail after actual prerequisite arithmetic"
    assert state(browser)["last_operation"] == original["last_operation"]
