"""Browser report snapshots with the existing native graph test double."""

import csv
from datetime import datetime, timedelta, timezone
import io
import time
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from proofflow.api import COOKIE, REPORT_EXPORT_PATH
from proofflow.artifacts import ArtifactStore
from proofflow.browser_import import BrowserImport, active_import
from proofflow.graph import GraphError
from proofflow.importing import REGION_REPORT
from proofflow.runtime import ProofFlowRuntime
from test_api import TestGraphClient, assert_error, seed
from test_browser_import import app, browser, csv_body, graph_factory, post, state


def export_request(import_state):
    return {"generation": import_state["generation"],
            "report_ids": {report["key"]: report["id"] for report in import_state["reports"]}}


def assert_export_error(response, status):
    assert_error(response, status)
    assert response.headers["Cache-Control"] == "no-store"
    assert set(response.json()) == {"error"}
    assert all(amount not in response.text for amount in (
        "30800", "10800", "31700", "11700", "$308.00", "$108.00", "$317.00", "$117.00",
    ))


def test_snapshot_exports_only_current_claims_and_proof_ids_without_writes(browser, graph_factory, tmp_path):
    initial = post(browser, "create", csv_body())
    mutations = graph_factory.mutation_count
    queries = sum(graph.queries for graph in graph_factory.clients)
    started = datetime.now(timezone.utc)
    with (
        patch("proofflow.importing.execute_tool") as preflight,
        patch("proofflow.runtime.execute_tool") as calculations,
        patch.object(ProofFlowRuntime, "refresh") as refresh,
        patch.object(ArtifactStore, "commit") as store_writes,
    ):
        result = browser.post(REPORT_EXPORT_PATH, json=export_request(initial))
    finished = datetime.now(timezone.utc)
    assert result.status_code == 200, result.text
    assert result.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in result.headers
    snapshot = result.json()
    assert set(snapshot) == {"filename", "media_type", "checked_at", "content"}
    assert snapshot["filename"] == "proofflow-current-reports.txt"
    assert snapshot["media_type"] == "text/plain;charset=utf-8"
    checked = datetime.fromisoformat(snapshot["checked_at"])
    assert checked.utcoffset() == timedelta(0)
    assert started <= checked <= finished

    content = snapshot["content"]
    assert content.encode("utf-8").decode("utf-8") == content
    lines = content.splitlines()
    assert f"Checked at (UTC): {snapshot['checked_at']}" in lines
    assert "Company net revenue: $308.00 USD" in lines
    assert "Regional net revenue ('NORTH'): $108.00 USD" in lines
    assert "Snapshot only. Both reports and their revenue claims were current at the check time." in lines
    assert "This file will not update after subsequent changes." in lines
    for report in initial["reports"]:
        assert f"Report artifact ID: {report['id']}" in lines
        assert f"Claim artifact ID: {report['claims'][0]['artifact_id']}" in lines
    for private in (initial["session_id"], initial["generation"], browser.cookies.get(COOKIE), str(tmp_path),
                    initial["dataset"]["source_csv_sha256"], "order_id", "n1,NORTH,EUR", "s1,SOUTH,USD",
                    "proofflow_session", "http://", "https://",
                    *(source["id"] for source in initial["dataset"]["sources"])):
        assert private not in result.text

    assert sum(graph.queries for graph in graph_factory.clients) > queries
    assert graph_factory.mutation_count == mutations
    preflight.assert_not_called()
    calculations.assert_not_called()
    refresh.assert_not_called()
    store_writes.assert_not_called()
    remaining = state(browser)
    for field in ("generation", "dataset", "reports", "executions", "impact", "last_operation", "last_refresh"):
        assert remaining[field] == initial[field]


def test_stale_reports_and_individually_mismatched_heads_are_rejected(app, browser, graph_factory):
    initial = post(browser, "create", csv_body())
    initial_request = export_request(initial)
    changed = post(browser, "update", csv_body(rate="1.30"))
    assert {report["state"] for report in changed["reports"]} == {"stale"}
    mutations = graph_factory.mutation_count
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=initial_request), 409)
    assert graph_factory.mutation_count == mutations
    assert state(browser)["reports"] == changed["reports"]

    second_tab = TestClient(app)
    second_tab.cookies.set(COOKIE, browser.cookies.get(COOKIE))
    refreshed = post(second_tab, "refresh")
    refreshed_request = export_request(refreshed)
    assert {report["state"] for report in refreshed["reports"]} == {"current"}
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=initial_request), 409)
    for key in ("company", "region"):
        mixed_ids = {**refreshed_request["report_ids"], key: initial_request["report_ids"][key]}
        assert_export_error(browser.post(REPORT_EXPORT_PATH,
                             json={**refreshed_request, "report_ids": mixed_ids}), 409)

    result = browser.post(REPORT_EXPORT_PATH, json=refreshed_request)
    assert result.status_code == 200, result.text
    assert "Company net revenue: $317.00 USD" in result.json()["content"]
    assert "Regional net revenue ('NORTH'): $117.00 USD" in result.json()["content"]


def test_incomplete_update_blocks_export_even_if_heads_are_still_current(browser, graph_factory):
    initial = post(browser, "create", csv_body())
    corrected = csv_body()
    corrected["csv_text"] = corrected["csv_text"].replace("10000,1000,3", "12000,1500,3")
    graph_factory.fail_after_nodes = 0
    assert_error(browser.post("/api/import/update", json=corrected), 503)
    incomplete = state(browser)
    assert incomplete["incomplete_update"]
    assert incomplete["reports"] == initial["reports"]
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=export_request(initial)), 409)


def test_unknown_lineage_and_missing_head_block_export(app, browser, graph_factory):
    initial = post(browser, "create", csv_body())
    payload = export_request(initial)
    company_id = payload["report_ids"]["company"]
    with app.state.manager.session(browser.cookies.get(COOKIE)) as owner:
        with active_import(owner, graph_factory) as imported:
            edges = imported.graph.data["edges"]
            incoming = {edge for edge in edges if edge[1] == company_id}
            edges.difference_update(incoming)
            assert imported.runtime.currentness(company_id).state == "unknown"
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=payload), 409)

    with app.state.manager.session(browser.cookies.get(COOKIE)) as owner:
        with active_import(owner, graph_factory) as imported:
            imported.graph.data["edges"].update(incoming)
            assert imported.runtime.currentness(company_id).is_current
            with imported.store.db:
                imported.store.db.execute("DELETE FROM heads WHERE logical_id = ?", (REGION_REPORT,))
            assert imported.store.get_head(REGION_REPORT) is None
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=payload), 409)


def test_generation_and_session_isolation(app, browser):
    initial = post(browser, "create", csv_body())
    payload = export_request(initial)
    wrong_generation = {**payload, "generation": "untrusted-generation-should-not-be-echoed"}
    wrong = browser.post(REPORT_EXPORT_PATH, json=wrong_generation)
    assert_export_error(wrong, 409)
    assert wrong_generation["generation"] not in wrong.text

    other = TestClient(app)
    assert_export_error(other.post(REPORT_EXPORT_PATH, json=payload), 401)
    seed(other)
    assert_export_error(other.post(REPORT_EXPORT_PATH, json=payload), 404)
    other_import = post(other, "create", csv_body("valid_zero_support.csv"))
    assert_export_error(other.post(REPORT_EXPORT_PATH, json=payload), 409)
    assert_export_error(other.post(REPORT_EXPORT_PATH,
                        json={**payload, "generation": other_import["generation"]}), 409)

    replacement = post(browser, "create", csv_body())
    assert replacement["generation"] != initial["generation"]
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=payload), 409)
    assert_export_error(browser.post(REPORT_EXPORT_PATH,
                        json={**export_request(replacement), "generation": initial["generation"]}), 409)


@pytest.mark.parametrize("invalid_json", [
    b"",
    b"{",
    b"[]",
    b'{"report_ids":{"company":"a","region":"b"}}',
    b'{"generation":5,"report_ids":{"company":"a","region":"b"}}',
    b'{"generation":"","report_ids":{"company":"a","region":"b"}}',
    b'{"generation":"a","report_ids":{"company":"b"}}',
    b'{"generation":"a","report_ids":{"company":"b","region":true}}',
    b'{"generation":"a","report_ids":{"company":"b","region":"c","unexpected":"d"}}',
    b'{"generation":"a","report_ids":{"company":"b","region":"c"},"unexpected":"d"}',
])
def test_export_request_rejects_malformed_json(browser, invalid_json):
    response = browser.post(REPORT_EXPORT_PATH, content=invalid_json,
                            headers={"Content-Type": "application/json"})
    assert_export_error(response, 400)


@pytest.mark.parametrize("changes", [
    {"key": "another_claim"},
    {"state": "stale"},
    {"state": "unknown"},
    {"value": None},
    {"value": True},
    {"value": 10800.0},
    {"unit": "EUR cents"},
    {"artifact_id": None},
])
def test_individual_revenue_claim_must_be_current_integer_usd_cents(browser, monkeypatch, changes):
    initial = post(browser, "create", csv_body())
    payload = export_request(initial)
    original = ProofFlowRuntime.report_claims

    def report_claims(runtime, report_id):
        claims = original(runtime, report_id)
        if report_id == payload["report_ids"]["region"]:
            return [{**claims[0], **changes}]
        return claims

    monkeypatch.setattr(ProofFlowRuntime, "report_claims", report_claims)
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=payload), 409)


def test_hydra_failure_withholds_both_amounts(browser, monkeypatch):
    initial = post(browser, "create", csv_body())
    payload = export_request(initial)
    checked_ids = []
    original = TestGraphClient.ancestors

    def ancestors(graph, node_ids, max_depth=15):
        if payload["report_ids"]["region"] in node_ids:
            raise GraphError("Hydra query failed on a private path containing $108.00")
        checked_ids.extend(node_ids)
        return original(graph, node_ids, max_depth)

    monkeypatch.setattr(TestGraphClient, "ancestors", ancestors)
    response = browser.post(REPORT_EXPORT_PATH, json=payload)
    assert_export_error(response, 503)
    assert payload["report_ids"]["company"] in checked_ids
    assert "private path" not in response.text


def test_export_is_rate_limited_and_does_not_cache_errors(app, browser, monkeypatch):
    initial = post(browser, "create", csv_body())
    payload = export_request(initial)
    with app.state.manager.session(browser.cookies.get(COOKIE)) as owner:
        owner.recent_actions = [time.monotonic()] * 30
    assert_export_error(browser.post(REPORT_EXPORT_PATH, json=payload), 429)
    with app.state.manager.session(browser.cookies.get(COOKIE)) as owner:
        owner.recent_actions = []

    def broken_export(*_):
        raise RuntimeError("Private detail must stay out of the response")

    monkeypatch.setattr(BrowserImport, "export_reports", broken_export)
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(COOKIE, browser.cookies.get(COOKIE))
    broken = client.post(REPORT_EXPORT_PATH, json=payload)
    assert_export_error(broken, 500)
    assert "Private detail" not in broken.text
    assert "Cache-Control" not in client.get("/api/import/state").headers


def test_export_preserves_large_integer_cents_and_escapes_region_controls(browser):
    region = '北\u2028ProofFlow\u202e\u0085" West'
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(("order_id", "region", "currency", "gross_cents"))
    writer.writerows((f"private-order-{index}", region, "EUR", 10**12) for index in range(10))
    writer.writerow(("private-cent", "SOUTH", "USD", 1))
    initial = post(browser, "create", {"csv_text": buffer.getvalue(), "region": region, "rates": {"EUR": "1000"}})
    result = browser.post(REPORT_EXPORT_PATH, json=export_request(initial))
    assert result.status_code == 200, result.text
    content = result.json()["content"]
    assert "Company net revenue: $100,000,000,000,000.01 USD" in content.splitlines()
    assert f"Regional net revenue ({region!r}): $100,000,000,000,000.00 USD" in content.splitlines()
    assert all(control not in content for control in ("\u2028", "\u202e", "\u0085"))
    assert "private-order-" not in content
    assert "private-cent" not in content
