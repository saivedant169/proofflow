"""Exercise the downloadable connector without publishing any live workspaces."""
import asyncio
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import runpy
import sys

from fastapi.testclient import TestClient
import httpx
import pytest

from proofflow.api import create_app
from test_api import TestGraphFactory


mcp = pytest.importorskip("mcp")
from mcp.client.stdio import StdioServerParameters


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend/public"
ENTRY = PUBLIC / "agent/proofflow_csv_mcp.py"
CONNECTOR = runpy.run_path(str(ENTRY))
ORIGIN = "https://proofflow.arnavbule.in"
COOKIE = "proofflow_session"
TOOLS = {"create_csv_reports", "inspect_reports", "update_csv", "refresh_reports", "export_current_reports", "inspect_evidence"}
CSV = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
       "n1,NORTH,EUR,10000,1000,3\ns1,SOUTH,USD,20000,0,1\n")
OPTIONS = {"csv_text": CSV, "rates": {"EUR": "1.20"}, "region": "NORTH"}


async def call(client, tool, arguments=None):
    result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content
    return result.structured_content


def cents(state):
    return {item["key"]: item["claims"][0]["value"] for item in state["reports"]}


def selection(state):
    return {"generation": state["generation"], "report_ids": {item["key"]: item["id"] for item in state["reports"]}}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("PROOFFLOW_COOKIE_SECURE", "true")
    return create_app(tmp_path / "sessions", graph_factory=TestGraphFactory(), static_dir=PUBLIC)


def test_download_and_checksum(app):
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as http:
        redirect = http.get("/agent")
        page = http.get("/agent/")
        download = http.get("/agent/proofflow_csv_mcp.py")
        digest = http.get("/agent/proofflow_csv_mcp.py.sha256")
        absent = http.get("/agent/absent")
    assert redirect.status_code == 308 and redirect.headers["Location"] == "/agent/"
    assert all(response.status_code == 200 for response in (page, download, digest))
    assert absent.status_code == 404
    assert "proofflow_csv_mcp.py" in page.text
    assert download.content == ENTRY.read_bytes()
    assert digest.text.split() == [hashlib.sha256(download.content).hexdigest(), ENTRY.name]
    assert not any(COOKIE in response.cookies for response in (redirect, page, download, digest, absent))


def test_connector_mount_cannot_read_outside_its_directory(tmp_path):
    static = tmp_path / "static"
    agent = static / "agent"
    agent.mkdir(parents=True)
    (static / "index.html").write_text("application shell")
    secret = tmp_path / "outside.txt"
    secret.write_text("private sentinel")
    (agent / "outside.txt").symlink_to(secret)
    app = create_app(tmp_path / "sessions", graph_factory=TestGraphFactory(), static_dir=static)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as http:
        escaped = http.get("/agent/outside.txt")
        traversal = http.get("/agent/%2e%2e/outside.txt")
        assert escaped.status_code == traversal.status_code == 404
        assert "private sentinel" not in escaped.text + traversal.text
        assert not any(COOKIE in response.cookies for response in (escaped, traversal))

    no_agent = tmp_path / "no-agent"
    no_agent.mkdir()
    (no_agent / "index.html").write_text("application shell")
    app = create_app(tmp_path / "other-sessions", graph_factory=TestGraphFactory(), static_dir=no_agent)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as http:
        assert http.get("/").text == "application shell"
        assert http.get("/agent/").json()["error"]["code"] == "not_found"


def test_stock_stdio_client_guided_csv_roundtrip(tmp_path):
    # Run the same distributable tool server over real stdio. This test injects
    # FastAPI's test transport into the factory, leaving the production CLI fixed.
    child = """
import os, runpy, sys
from fastapi.testclient import TestClient
from proofflow.api import create_app
from test_api import TestGraphFactory
os.environ['PROOFFLOW_COOKIE_SECURE'] = 'true'
connector = runpy.run_path(sys.argv[1])
app = create_app(sys.argv[2], graph_factory=TestGraphFactory(), static_dir=sys.argv[3])
with TestClient(app, base_url=connector['ORIGIN']) as http:
    connector['build_server'](http).run(transport='stdio')
"""
    params = StdioServerParameters(command=sys.executable, args=["-B", "-c", child, str(ENTRY),
        str(tmp_path / "sessions"), str(tmp_path / "no-static")], cwd=tmp_path,
        env={"PYTHONPATH": f"{ROOT}:{ROOT / 'tests'}", "PROOFFLOW_STATE_DIR": str(tmp_path / "app-default")})

    async def check():
        async with mcp.Client(params) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == TOOLS
            assert "csv_text" in tools["create_csv_reports"].input_schema["required"]
            assert "csv_text" not in tools["update_csv"].input_schema.get("required", [])
            missing = await client.call_tool("inspect_reports")
            assert missing.is_error and "fresh hosted session" in missing.content[0].text
            assert not list((tmp_path / "sessions").iterdir())
            initial = await call(client, "create_csv_reports", OPTIONS)
            assert cents(initial) == {"company": 30800, "region": 10800}
            assert initial["last_operation"]["recorded_tool_call_count"] == 8
            before = selection(initial)
            chosen = {"generation": initial["generation"], "artifact_id": before["report_ids"]["company"]}
            initial_evidence = await call(client, "inspect_evidence", chosen)
            assert initial_evidence["artifact"]["state"] == "current"
            assert initial_evidence["receipt"]["tool"] == "compose_report"
            assert initial_evidence["receipt"]["output_id"] == chosen["artifact_id"]
            assert initial_evidence["inputs"][0]["inspectable"] is True
            updated = await call(client, "update_csv", {**OPTIONS, "rates": {"EUR": "1.30"}})
            assert cents(updated) == {"company": None, "region": None}
            assert "saved_value" not in json.dumps(updated)
            assert updated["last_operation"]["recorded_tool_call_count"] == 0
            assert set(before["report_ids"].values()) <= set(updated["affected_artifact_ids"])
            stale_evidence = await call(client, "inspect_evidence", chosen)
            assert stale_evidence["artifact"]["state"] == "stale"
            assert stale_evidence["receipt"] == initial_evidence["receipt"]
            assert stale_evidence["recorded_changed_source_paths"]
            assert all(path["target_id"] == chosen["artifact_id"] for path in stale_evidence["recorded_changed_source_paths"])
            stale = await client.call_tool("export_current_reports", before)
            assert stale.is_error and stale.structured_content is None
            assert "409" in stale.content[0].text and "No export" in stale.content[0].text
            refreshed = await call(client, "refresh_reports")
            assert cents(refreshed) == {"company": 31700, "region": 11700}
            assert refreshed["last_refresh"]["executed_count"] == 4
            assert refreshed["last_refresh"]["numeric_parity"] and refreshed["last_refresh"]["unchanged_support"]
            assert selection(await call(client, "inspect_reports")) == selection(refreshed) != before
            old_evidence = await call(client, "inspect_evidence", chosen)
            assert old_evidence["artifact"]["state"] == "stale"
            assert old_evidence["artifact"]["current_head_id"] == selection(refreshed)["report_ids"]["company"]
            replacement = await call(client, "inspect_evidence", {**chosen, "artifact_id": old_evidence["artifact"]["current_head_id"]})
            assert replacement["artifact"]["state"] == "current"
            assert replacement["receipt"]["id"] != old_evidence["receipt"]["id"]
            assert (await client.call_tool("export_current_reports", before)).is_error
            exported = await call(client, "export_current_reports", selection(refreshed))
            assert "$317.00 USD" in exported["content"] and "$117.00 USD" in exported["content"]
            combined = json.dumps([initial, updated, refreshed, exported, initial_evidence, stale_evidence, old_evidence, replacement])
            assert all(name not in combined for name in (COOKIE, "session_id", "csv_text", "saved_value", CSV))

    asyncio.run(check())


def test_isolation_and_exact_large_cents(app):
    with TestClient(app, base_url=ORIGIN) as left_http, TestClient(app, base_url=ORIGIN) as right_http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](left_http)) as left, \
                       mcp.Client(CONNECTOR["build_server"](right_http)) as right:
                first = await call(left, "create_csv_reports", OPTIONS)
                assert (await right.call_tool("inspect_reports")).is_error and not right_http.cookies
                missing_csv = await right.call_tool("update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                assert missing_csv.is_error and "No confirmed CSV" in missing_csv.content[0].text
                assert not right_http.cookies
                large = await call(right, "create_csv_reports", {
                    "csv_text": ("order_id,region,currency,gross_cents\n" + "".join(
                        f"l{index},NORTH,EUR,1000000000000\n" for index in range(10))),
                    "rates": {"EUR": "1000"}, "region": "NORTH",
                })
                assert cents(large) == {"company": "10000000000000000", "region": "10000000000000000"}
                assert first["generation"] != large["generation"]
                assert left_http.cookies[COOKIE] != right_http.cookies[COOKIE]
                denied = await right.call_tool("export_current_reports", selection(first))
                assert denied.is_error and denied.structured_content is None
                assert "409" in denied.content[0].text
                assert cents(await call(left, "inspect_reports")) == {"company": 30800, "region": 10800}

        asyncio.run(check())


def test_incomplete_update_withholds_even_current_underlying_values(app):
    with TestClient(app, base_url=ORIGIN) as http:
        assert http.post("/api/session").status_code == 200
        raw = http.post("/api/import/create", json=OPTIONS).json()
    assert cents(raw) == {"company": 30800, "region": 10800}
    raw["incomplete_update"] = True
    projected = CONNECTOR["report_state"](raw)
    assert cents(projected) == {"company": None, "region": None}
    for report in projected["reports"]:
        claim = report["claims"][0]
        assert report["state"] == claim["state"] == "unknown"
        assert {"reason": "incomplete_update", "id": report["id"]} in claim["reasons"]
        assert "saved_value" not in claim


def test_invalid_inputs_suppress_sdk_errors_and_send_no_request():
    def reject(request):
        pytest.fail(f"Malformed input contacted the API at {request.url.path}")

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(reject)) as http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                for arguments in (
                    {"csv_text": {"example": "private-input"}},
                    {"csv_text": "é" * (512 * 1024 + 1)},
                    {"csv_text": CSV, "rates": {"CAD": "1"}},
                    {"csv_text": CSV, "url": "https://other.example/private-input"},
                    {"csv_text": CSV, "region": "N" * 65},
                ):
                    result = await client.call_tool("create_csv_reports", arguments)
                    assert result.is_error and "private-input" not in result.content[0].text
                result = await client.call_tool("export_current_reports", {"generation": "g", "report_ids": {"company": "a"}})
                assert result.is_error and "both observed report IDs" in result.content[0].text

        asyncio.run(check())


def instrument(http, monkeypatch, fault=None, reject=None):
    original = http.stream
    calls = []

    @contextmanager
    def stream(method, path, json=None):
        calls.append((method, path, json))
        if reject and (status := reject(path, json)):
            yield httpx.Response(status, json={"error": {"message": "private-row request refused"}})
            return
        with original(method, path, json=json) as response:
            yield fault(path, response) if fault else response

    monkeypatch.setattr(http, "stream", stream)
    return calls


def test_rate_only_reuses_exact_last_confirmed_bytes(app, monkeypatch):
    exact = "\ufeff" + CSV.replace("\n", "\r\n")
    rates = {"rates": {"EUR": "1.30"}, "region": "NORTH"}
    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                initial = await call(client, "create_csv_reports", {**OPTIONS, "csv_text": exact})
                assert initial["dataset"]["source_csv_sha256"] == hashlib.sha256(exact.encode()).hexdigest()

                before_validation = len(calls)
                for arguments in (
                    {"rates": rates["rates"]}, {"region": "NORTH"}, {**rates, "region": "SOUTH"},
                    {**rates, "csv_text": ""},
                ):
                    refused = await client.call_tool("update_csv", arguments)
                    assert refused.is_error and refused.structured_content is None
                assert len(calls) == before_validation

                updated = await call(client, "update_csv", rates)
                assert cents(updated) == {"company": None, "region": None}
                assert updated["dataset"]["source_csv_sha256"] == initial["dataset"]["source_csv_sha256"]
                assert calls[-2:] == [("GET", "/api/import/state", None),
                                      ("POST", "/api/import/update", {**rates, "csv_text": exact})]
                refreshed = await call(client, "refresh_reports")
                assert cents(refreshed) == {"company": 31700, "region": 11700}
                assert refreshed["last_refresh"]["executed_count"] == 4

                replacement = CSV.replace("10000,1000", "15000,1000")
                replaced = await call(client, "update_csv", {**rates, "csv_text": replacement})
                assert replaced["dataset"]["source_csv_sha256"] == hashlib.sha256(replacement.encode()).hexdigest()
                rate_again = {"rates": {"EUR": "1.40"}, "region": "NORTH"}
                await call(client, "update_csv", rate_again)
                assert calls[-1] == ("POST", "/api/import/update", {**rate_again, "csv_text": replacement})
                assert cents(await call(client, "refresh_reports")) == {"company": 39600, "region": 19600}

        asyncio.run(check())


def test_pre_dispatch_refusal_does_not_replace_confirmed_csv(app, monkeypatch):
    create_rejected = False

    def reject(path, payload):
        nonlocal create_rejected
        if path == "/api/import/create" and not create_rejected:
            create_rejected = True
            return 429
        if path == "/api/import/update" and "private-row" in payload["csv_text"]:
            return 413
        return None

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, reject=reject)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                # A rejected first create leaves no cache and no active import. A
                # subsequent valid manual create may still use the opened session.
                assert (await client.call_tool("create_csv_reports", OPTIONS)).is_error
                assert (await client.call_tool("inspect_reports")).is_error
                assert (await client.call_tool("update_csv", {"rates": OPTIONS["rates"], "region": "NORTH"})).is_error
                await call(client, "create_csv_reports", OPTIONS)

                refused = await client.call_tool("update_csv", {**OPTIONS, "csv_text": CSV + "private-row\n"})
                assert refused.is_error and "private-row" not in refused.content[0].text
                await call(client, "update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                assert calls[-1][2]["csv_text"] == CSV
                assert cents(await call(client, "refresh_reports")) == {"company": 31700, "region": 11700}

        asyncio.run(check())
    assert [path for _, path, _ in calls].count("/api/session") == 1


@pytest.mark.parametrize("defect", ["pending", "digest", "generation", "region", "session", "cookie"])
def test_rate_only_preflight_blocks_mismatched_workspace(app, monkeypatch, defect):
    def mutate(path, response):
        if path != "/api/import/state":
            return response
        state = json.loads(response.read())
        if defect == "pending":
            state["incomplete_update"] = True
        elif defect == "digest":
            state["dataset"]["source_csv_sha256"] = "0" * 64
        elif defect == "generation":
            state["generation"] = "different-generation"
        elif defect == "region":
            state["dataset"]["selected_region"] = "SOUTH"
        elif defect == "session":
            state["session_id"] = "different-private-session"
        else:
            http.cookies.set(COOKIE, "different-private-session", domain=http.base_url.host)
        return httpx.Response(200, json=state)

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, mutate)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                initial = await call(client, "create_csv_reports", OPTIONS)
                refused = await client.call_tool("update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                assert refused.is_error and "Restart the connector" in refused.content[0].text
                assert "different-private-session" not in refused.content[0].text
                assert (await client.call_tool("update_csv", OPTIONS)).is_error
                assert (await client.call_tool("refresh_reports")).is_error
                assert (await client.call_tool("export_current_reports", selection(initial))).is_error

        asyncio.run(check())
    assert [path for _, path, _ in calls] == ["/api/session", "/api/import/create", "/api/import/state"]


@pytest.mark.parametrize("defect", ["timeout", "digest", "malformed", "pending", "generic_400"])
def test_uncertain_update_does_not_retry_or_accept_later_mutation(app, monkeypatch, defect):
    def interrupt(path, response):
        if path != "/api/import/update":
            return response
        state = json.loads(response.read())
        if defect == "timeout":
            raise httpx.ReadTimeout("private-id transport detail")
        if defect == "malformed":
            return httpx.Response(200, content=b"private-row payload")
        if defect == "generic_400":
            return httpx.Response(400, json={"error": {"message": "private-row error after dispatch"}})
        if defect == "pending":
            state["incomplete_update"] = True
        else:
            state["dataset"]["source_csv_sha256"] = "0" * 64
        return httpx.Response(200, json=state)

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, interrupt)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                initial = await call(client, "create_csv_reports", OPTIONS)
                replacement = CSV.replace("10000,1000", "15000,1000")
                failed = await client.call_tool("update_csv", {**OPTIONS, "csv_text": replacement})
                assert failed.is_error and failed.structured_content is None
                assert "Restart the connector" in failed.content[0].text
                assert all(secret not in failed.content[0].text for secret in ("private-id", "private-row", CSV, replacement))
                # The hosted app actually accepted the replacement. A later
                # inspection cannot make an uncertain result cacheable.
                observed = await call(client, "inspect_reports")
                assert observed["dataset"]["source_csv_sha256"] == hashlib.sha256(replacement.encode()).hexdigest()
                for tool, arguments in (
                    ("update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"}),
                    ("update_csv", OPTIONS), ("create_csv_reports", OPTIONS),
                    ("refresh_reports", None), ("export_current_reports", selection(initial)),
                ):
                    refused = await client.call_tool(tool, arguments)
                    assert refused.is_error and "Restart the connector" in refused.content[0].text

        asyncio.run(check())
    assert [path for _, path, _ in calls] == ["/api/session", "/api/import/create", "/api/import/update", "/api/import/state"]


def test_mismatched_create_digest_leaves_no_cache(app, monkeypatch):
    def mismatch(path, response):
        if path != "/api/import/create":
            return response
        raw = json.loads(response.read())
        raw["dataset"]["source_csv_sha256"] = "0" * 64
        return httpx.Response(200, json=raw)

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, mismatch)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                assert (await client.call_tool("create_csv_reports", OPTIONS)).is_error
                refused = await client.call_tool("update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                assert refused.is_error and "Restart the connector" in refused.content[0].text

        asyncio.run(check())
    assert [path for _, path, _ in calls] == ["/api/session", "/api/import/create"]


def test_expired_session_never_reopens_automatically(app, monkeypatch):
    def expire(path, response):
        if path == "/api/import/state":
            return httpx.Response(401, json={"error": {"message": "opaque-private-session"}})
        return response

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, expire)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                await call(client, "create_csv_reports", OPTIONS)
                refused = await client.call_tool("update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                assert refused.is_error and "expired" in refused.content[0].text
                assert "opaque-private-session" not in refused.content[0].text
                assert (await client.call_tool("create_csv_reports", OPTIONS)).is_error
                assert (await client.call_tool("inspect_reports")).is_error

        asyncio.run(check())
    assert [path for _, path, _ in calls] == ["/api/session", "/api/import/create", "/api/import/state"]


def test_uncertain_session_open_rejects_later_calls_without_contact():
    calls = []

    def timeout(request):
        calls.append(request.url.path)
        raise httpx.ReadTimeout("Session response lost")

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(timeout)) as http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                assert (await client.call_tool("create_csv_reports", OPTIONS)).is_error
                again = await client.call_tool("create_csv_reports", OPTIONS)
                assert again.is_error and "Restart the connector" in again.content[0].text

        asyncio.run(check())
    assert calls == ["/api/session"]


def test_refresh_rejects_a_state_that_does_not_confirm_refresh(app, monkeypatch):
    def replay(path, response):
        if path != "/api/import/refresh":
            return response
        state = json.loads(response.read())
        state["last_operation"]["kind"] = "update"
        state["last_refresh"] = None
        return httpx.Response(200, json=state)

    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch, replay)

        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                initial = await call(client, "create_csv_reports", OPTIONS)
                await call(client, "update_csv", {"rates": {"EUR": "1.30"}, "region": "NORTH"})
                refused = await client.call_tool("refresh_reports")
                assert refused.is_error and "could not confirm the hosted write" in refused.content[0].text
                assert (await client.call_tool("export_current_reports", selection(initial))).is_error

        asyncio.run(check())
    assert [path for _, path, _ in calls] == [
        "/api/session", "/api/import/create", "/api/import/state", "/api/import/update", "/api/import/refresh",
    ]


def test_evidence_uses_one_atomic_read_and_keeps_checked_export_unchanged(app, monkeypatch):
    monkeypatch.setattr("proofflow.browser_import.now", lambda: "2026-11-16T00:00:00+00:00")
    with TestClient(app, base_url=ORIGIN) as http:
        calls = instrument(http, monkeypatch)
        api = CONNECTOR["HostedCsvAPI"](http)
        initial = api.publish_csv("/api/import/create", **OPTIONS)
        chosen = selection(initial)
        before = api.call("POST", "/api/import/export", chosen)
        start = len(calls)
        evidence = api.inspect_evidence(initial["generation"], chosen["report_ids"]["company"])
        assert len(calls) == start + 1
        assert calls[-1] == ("GET", f"/api/import/evidence/{chosen['report_ids']['company']}?generation={initial['generation']}", None)
        assert evidence["artifact"]["state"] == "current"
        assert api.call("POST", "/api/import/export", chosen) == before
        assert api.call("GET", "/api/import/state")["last_operation"] == initial["last_operation"]


def test_evidence_invalid_arguments_make_no_request():
    def reject(request):
        pytest.fail(f"Invalid evidence input contacted API at {request.url.path}")

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(reject)) as http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                for arguments in (
                    {"generation": "private-row", "artifact_id": "../private-row"},
                    {"generation": "a" * 32, "artifact_id": "b" * 32 + ":source:" + "c" * 64},
                    {"generation": "a" * 32, "artifact_id": "b" * 32 + ":execution:" + "c" * 64},
                    {"generation": "a" * 32, "artifact_id": "b" * 32 + ":artifact:" + "c" * 64, "url": "private-row"},
                ):
                    result = await client.call_tool("inspect_evidence", arguments)
                    assert result.is_error and result.structured_content is None
                    assert "private-row" not in result.content[0].text

        asyncio.run(check())


def test_evidence_wrong_selection_does_not_destroy_confirmed_csv(app):
    with TestClient(app, base_url=ORIGIN) as left_http, TestClient(app, base_url=ORIGIN) as right_http:
        left = CONNECTOR["HostedCsvAPI"](left_http)
        right = CONNECTOR["HostedCsvAPI"](right_http)
        first = left.publish_csv("/api/import/create", **OPTIONS)
        second = right.publish_csv("/api/import/create", **OPTIONS)
        artifact_id = selection(first)["report_ids"]["company"]
        confirmed = right.confirmed_csv
        for generation, selected in (
            (first["generation"], selection(second)["report_ids"]["company"]),
            (second["generation"], artifact_id),
            (second["generation"], artifact_id.split(":")[0] + ":artifact:" + "0" * 64),
        ):
            with pytest.raises(CONNECTOR["ToolError"]):
                right.inspect_evidence(generation, selected)
            assert right.confirmed_csv is confirmed and right.writes_blocked is False
        corrected = right.publish_csv("/api/import/update", None, {"EUR": "1.30"}, "NORTH")
        assert corrected["last_operation"]["changed_source_count"] == 1


def test_evidence_read_after_uncertain_write_does_not_restore_writes(app, monkeypatch):
    def interrupt(path, response):
        if path == "/api/import/update":
            response.read()
            raise httpx.ReadTimeout("private-row interrupted write")
        return response

    with TestClient(app, base_url=ORIGIN) as http:
        instrument(http, monkeypatch, interrupt)
        api = CONNECTOR["HostedCsvAPI"](http)
        initial = api.publish_csv("/api/import/create", **OPTIONS)
        with pytest.raises(CONNECTOR["ToolError"]):
            api.publish_csv("/api/import/update", None, {"EUR": "1.30"}, "NORTH")
        assert api.writes_blocked and api.confirmed_csv is None
        evidence = api.inspect_evidence(initial["generation"], selection(initial)["report_ids"]["company"])
        assert evidence["artifact"]["state"] == "stale"
        assert api.writes_blocked and api.confirmed_csv is None
        with pytest.raises(CONNECTOR["ToolError"], match="Restart the connector"):
            api.call("POST", "/api/import/export", selection(initial))
        with pytest.raises(CONNECTOR["ToolError"], match="Restart the connector"):
            api.publish_csv("/api/import/update", CSV, {"EUR": "1.30"}, "NORTH")


def test_evidence_projection_drops_unadvertised_payloads(app):
    with TestClient(app, base_url=ORIGIN) as http:
        api = CONNECTOR["HostedCsvAPI"](http)
        initial = api.publish_csv("/api/import/create", **OPTIONS)
        chosen = selection(initial)["report_ids"]["company"]
        api.publish_csv("/api/import/update", None, {"EUR": "1.30"}, "NORTH")
        raw = http.get(f"/api/import/evidence/{chosen}", params={"generation": initial["generation"]}).json()
        assert raw["recorded_changed_source_paths"]
        sentinel = "private-row-secret"
        raw.update(session_id=sentinel, csv_text=sentinel, path_scope=sentinel)
        raw["artifact"].update(saved_value=sentinel, value=sentinel, metadata={"private": sentinel})
        raw["receipt"].update(params={"private": sentinel}, title=sentinel)
        raw["backend"]["credentials"] = sentinel
        raw["inputs"][0]["value"] = sentinel
        raw["artifact"]["reasons"][0]["detail"] = sentinel
        raw["recorded_changed_source_paths"][0]["nodes"][0]["label"] = sentinel
        projected = CONNECTOR["evidence_state"](raw, initial["generation"], chosen)
        encoded = json.dumps(projected)
        assert sentinel not in encoded
        for key in ("saved_value", "csv_text", "session_id", "params", "metadata", "label", "value"):
            assert f'"{key}"' not in encoded
        assert projected["path_scope"] == CONNECTOR["PATH_SCOPE"]


@pytest.mark.parametrize("defect", ["generation", "incomplete", "fallback", "unknown", "receipt_id", "receipt_identity", "receipt_hash", "input_kind", "input_followable", "path_target", "terminal_logical", "path_direction", "path_kind", "path_repeated", "foreign_node", "query_count", "reason"])
def test_evidence_projection_rejects_malformed_envelopes(app, defect):
    with TestClient(app, base_url=ORIGIN) as http:
        api = CONNECTOR["HostedCsvAPI"](http)
        initial = api.publish_csv("/api/import/create", **OPTIONS)
        chosen = selection(initial)["report_ids"]["company"]
        api.publish_csv("/api/import/update", None, {"EUR": "1.30"}, "NORTH")
        raw = http.get(f"/api/import/evidence/{chosen}", params={"generation": initial["generation"]}).json()
        path = raw["recorded_changed_source_paths"][0]
        if defect == "generation": raw["generation"] = "0" * 32
        elif defect == "incomplete": raw["incomplete_update"] = True
        elif defect == "fallback": raw["backend"]["fallback"] = True
        elif defect == "unknown": raw["artifact"]["state"] = "unknown"
        elif defect == "receipt_id": raw["receipt"]["output_id"] = "private-row"
        elif defect == "receipt_identity": raw["receipt"]["id"] = chosen.split(":")[0] + ":execution:" + "0" * 64
        elif defect == "receipt_hash": raw["receipt"]["output_hash"] = "0" * 64
        elif defect == "input_kind": raw["inputs"][0]["kind"] = "execution"
        elif defect == "input_followable": raw["inputs"][0]["inspectable"] = False
        elif defect == "path_target": path["target_id"] = "private-row"
        elif defect == "terminal_logical": path["nodes"][-1]["logical_id"] = "import:metric:gross"
        elif defect == "path_direction": path["edges"][0]["source"] = path["edges"][0]["target"]
        elif defect == "path_kind": path["edges"][0]["kind"] = "FLOW"
        elif defect == "path_repeated": raw["recorded_changed_source_paths"] = [copy.deepcopy(path)] * 4
        elif defect == "foreign_node": path["nodes"][0]["id"] = "0" * 32 + path["nodes"][0]["id"][32:]
        elif defect == "query_count": raw["backend"]["native_queries"] = True
        elif defect == "reason": raw["artifact"]["reasons"][0]["reason"] = "missing_manifest_record"
        with pytest.raises(CONNECTOR["ToolError"], match="No evidence was returned") as error:
            CONNECTOR["evidence_state"](raw, initial["generation"], chosen)
        assert "private-row" not in str(error.value)
