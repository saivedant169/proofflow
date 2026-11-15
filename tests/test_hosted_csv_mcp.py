"""Exercise the downloadable connector without publishing any live workspaces."""
import asyncio
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
TOOLS = {"create_csv_reports", "inspect_reports", "update_csv", "refresh_reports", "export_current_reports"}
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
            assert {tool.name for tool in (await client.list_tools()).tools} == TOOLS
            missing = await client.call_tool("inspect_reports")
            assert missing.is_error and "fresh hosted session" in missing.content[0].text
            assert not list((tmp_path / "sessions").iterdir())
            initial = await call(client, "create_csv_reports", OPTIONS)
            assert cents(initial) == {"company": 30800, "region": 10800}
            assert initial["last_operation"]["recorded_tool_call_count"] == 8
            before = selection(initial)
            updated = await call(client, "update_csv", {**OPTIONS, "rates": {"EUR": "1.30"}})
            assert cents(updated) == {"company": None, "region": None}
            assert "saved_value" not in json.dumps(updated)
            assert updated["last_operation"]["recorded_tool_call_count"] == 0
            assert set(before["report_ids"].values()) <= set(updated["affected_artifact_ids"])
            stale = await client.call_tool("export_current_reports", before)
            assert stale.is_error and stale.structured_content is None
            assert "409" in stale.content[0].text and "No export" in stale.content[0].text
            refreshed = await call(client, "refresh_reports")
            assert cents(refreshed) == {"company": 31700, "region": 11700}
            assert refreshed["last_refresh"]["executed_count"] == 4
            assert refreshed["last_refresh"]["numeric_parity"] and refreshed["last_refresh"]["unchanged_support"]
            assert selection(await call(client, "inspect_reports")) == selection(refreshed) != before
            assert (await client.call_tool("export_current_reports", before)).is_error
            exported = await call(client, "export_current_reports", selection(refreshed))
            assert "$317.00 USD" in exported["content"] and "$117.00 USD" in exported["content"]
            combined = json.dumps([initial, updated, refreshed, exported])
            assert all(name not in combined for name in (COOKIE, "session_id", "csv_text", "saved_value", CSV))

    asyncio.run(check())


def test_isolation_and_exact_large_cents(app):
    with TestClient(app, base_url=ORIGIN) as left_http, TestClient(app, base_url=ORIGIN) as right_http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](left_http)) as left, \
                       mcp.Client(CONNECTOR["build_server"](right_http)) as right:
                first = await call(left, "create_csv_reports", OPTIONS)
                assert (await right.call_tool("inspect_reports")).is_error and not right_http.cookies
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


def test_failures_do_not_retry_or_reopen_and_do_not_echo_response_body():
    calls = []

    def respond(request):
        calls.append(request.url.path)
        assert request.url.host == "proofflow.arnavbule.in"
        if request.url.path == "/api/session":
            assert "cookie" not in request.headers
            return httpx.Response(200, headers={"Set-Cookie": f"{COOKIE}=private-id; Secure; HttpOnly; Path=/"},
                                  json={"session_id": "private-id"})
        assert request.headers["cookie"] == f"{COOKIE}=private-id"
        if request.url.path == "/api/import/create":
            return httpx.Response(400, json={"error": {"message": "raw private-id error"}})
        if request.url.path == "/api/import/update":
            raise httpx.ReadTimeout("private-id transport detail")
        if request.url.path == "/api/import/refresh":
            return httpx.Response(307, headers={"Location": "https://other.example/"})
        return httpx.Response(401, json={"error": {"message": "raw private-id session"}})

    with httpx.Client(base_url=ORIGIN, transport=httpx.MockTransport(respond), follow_redirects=False) as http:
        async def check():
            async with mcp.Client(CONNECTOR["build_server"](http)) as client:
                for name, args in [("create_csv_reports", OPTIONS), ("update_csv", OPTIONS),
                                   ("refresh_reports", None), ("inspect_reports", None)]:
                    result = await client.call_tool(name, args)
                    assert result.is_error and "private-id" not in result.content[0].text

        asyncio.run(check())
    assert calls == ["/api/session", "/api/import/create", "/api/import/update",
                     "/api/import/refresh", "/api/import/state"]


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
