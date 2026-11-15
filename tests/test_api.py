"""Browser API integration with real runtime/tools and an explicit graph test double.

These checks do not claim live Hydra integration. scripts/core_smoke.py provides
that proof separately. Each fake client shares persisted graph state by namespace
so reopening the application does not silently start with a fresh graph.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import quote

from fastapi.testclient import TestClient
import pytest

from proofflow.api import create_app
from proofflow.graph import GraphError


class TestGraphFactory:
    __test__ = False

    def __init__(self):
        self.spaces = {}
        self.clients = []
        self.available = True
        self.fail_next_path = False
        self.suppress_next_path = False

    def __call__(self, *, namespace):
        data = self.spaces.setdefault(namespace, {"nodes": {}, "edges": set()})
        client = TestGraphClient(namespace, data, self)
        self.clients.append(client)
        return client


class TestGraphClient:
    __test__ = False

    def __init__(self, namespace, data, factory):
        self.namespace = namespace
        self.data = data
        self.factory = factory
        self.queries = 0
        self.mutations = 0

    def _access(self, *, mutation=False):
        if not self.factory.available:
            raise GraphError("Injected graph outage; no fallback")
        self.queries += 1
        self.mutations += int(mutation)

    def vertex_id(self, key):
        return int(hashlib.sha256(f"{self.namespace}\0{key}".encode()).hexdigest()[:15], 16)

    def get_node(self, node_id):
        self._access()
        return copy.deepcopy(self.data["nodes"].get(node_id))

    def put_node(self, node_id, kind, properties):
        self._access(mutation=True)
        self.data["nodes"][node_id] = {"id": node_id, "kind": kind, "properties": copy.deepcopy(properties)}

    def put_edge(self, source_id, target_id, kind, properties=None):
        self._access(mutation=True)
        if source_id not in self.data["nodes"] or target_id not in self.data["nodes"]:
            raise GraphError("Missing graph endpoint")
        self.data["edges"].add((source_id, target_id, kind))

    def _walk(self, node_ids, reverse, max_depth):
        self._access()
        if any(node not in self.data["nodes"] for node in node_ids):
            raise GraphError("Cannot traverse absent graph node")
        seen = set(node_ids)
        frontier = set(node_ids)
        for _ in range(max_depth):
            found = {a if reverse else b for a, b, _ in self.data["edges"]
                     if (b if reverse else a) in frontier} - seen
            if not found:
                return sorted(seen - set(node_ids))
            seen.update(found)
            frontier = found
        raise GraphError("Bounded test graph traversal exceeded depth")

    def ancestors(self, node_ids, max_depth=15):
        return self._walk(node_ids, True, max_depth)

    def descendants(self, node_ids, max_depth=15):
        return self._walk(node_ids, False, max_depth)

    def paths(self, source_id, target_id, max_depth=15):
        self._access()
        if self.factory.fail_next_path:
            self.factory.fail_next_path = False
            raise GraphError("Injected first-state path failure")
        if self.factory.suppress_next_path:
            self.factory.suppress_next_path = False
            return []
        frontier = [(source_id, [])]
        found = []
        while frontier and len(found) < 3:
            node, edges = frontier.pop(0)
            if node == target_id:
                ids = [source_id] + [edge[1] for edge in edges]
                native_nodes = []
                for node_id in ids:
                    entry = self.data["nodes"][node_id]
                    native_nodes.append({
                        "id": self.vertex_id(node_id), "labels": ["ProofFlow"],
                        "properties": {
                            "key": {"String": node_id}, "kind": {"String": entry["kind"]},
                            "payload": {"String": json.dumps(entry["properties"])},
                            "workspace": {"String": self.namespace},
                        },
                    })
                found.append({"nodes": native_nodes, "relationships": [
                    {"id": None, "edge_type": "FLOW", "src": self.vertex_id(a), "dst": self.vertex_id(b),
                     "properties": {"kind": {"String": kind}, "payload": {"String": "{}"}}}
                    for a, b, kind in edges
                ]})
                continue
            if len(edges) >= max_depth:
                continue
            visited = {source_id} | {edge[1] for edge in edges}
            frontier.extend((b, edges + [(a, b, kind)]) for a, b, kind in sorted(self.data["edges"])
                            if a == node and b not in visited)
        return found

    def close(self):
        pass


@pytest.fixture
def factory():
    return TestGraphFactory()


@pytest.fixture
def app(tmp_path, factory):
    return create_app(state_dir=tmp_path / "sessions", graph_factory=factory,
                      max_sessions=16, static_dir=tmp_path / "no-static")


@pytest.fixture
def client(app):
    with TestClient(app) as instance:
        yield instance


def seed(client):
    response = client.post("/api/session")
    assert response.status_code == 200, response.text
    return response.json()


def reports(state):
    return {item["key"]: item for item in state["reports"]}


def claims(report):
    return {item["key"]: item for item in report["claims"]}


def assert_error(response, status):
    assert response.status_code == status, response.text
    assert isinstance(response.json()["error"]["code"], str)
    assert isinstance(response.json()["error"]["message"], str)


def test_session_runs_real_tools_and_returns_known_values(client):
    state = seed(client)
    values = reports(state)
    assert claims(values["company"])["company_revenue"]["value"] == 556500
    assert claims(values["eu"])["eu_revenue"]["value"] == 209000
    assert claims(values["eu"])["eu_support"]["value"] == 2
    assert all(report["state"] == "current" for report in values.values())
    assert state["mode"] == "guided_real_execution"
    assert state["backend"]["fallback"] is False
    assert len(state["executions"]) == 8
    assert state["graph"]["nodes"] and state["graph"]["edges"]
    cookie = client.cookies.get("proofflow_session")
    assert cookie
    assert client.post("/api/session").json()["session_id"] == state["session_id"]


def test_fx_change_withholds_stale_value_and_selective_refresh_is_exact(client):
    initial = seed(client)
    old_reports = [item["id"] for item in initial["reports"]]
    response = client.post("/api/change", json={"kind": "fx", "value": "1.20"})
    assert response.status_code == 200, response.text
    changed = response.json()
    eu = claims(reports(changed)["eu"])
    assert eu["eu_revenue"]["state"] == "stale"
    assert eu["eu_revenue"]["value"] is None
    assert eu["eu_revenue"]["saved_value"] == 209000
    assert eu["eu_support"]["state"] == "current"
    assert eu["eu_support"]["value"] == 2
    assert len(changed["impact"]["affected_artifacts"]) == 4
    refreshed_response = client.post("/api/refresh", json={})
    assert refreshed_response.status_code == 200, refreshed_response.text
    refreshed = refreshed_response.json()
    assert claims(reports(refreshed)["eu"])["eu_revenue"]["value"] == 228000
    assert claims(reports(refreshed)["company"])["company_revenue"]["value"] == 575500
    assert refreshed["last_refresh"]["executed_count"] == 4
    assert len(refreshed["last_refresh"]["tool_calls"]) == 4
    assert all(call["tool"] != "support_by_region" for call in refreshed["last_refresh"]["tool_calls"])
    assert refreshed["last_refresh"]["numeric_parity"] is True
    assert refreshed["last_refresh"]["unchanged_support"] is True
    # Reusing old handles must not claim new executions after the first refresh.
    again = client.post("/api/refresh", json={"report_ids": old_reports})
    assert again.status_code == 200, again.text
    assert again.json()["last_refresh"]["executed_count"] == 0
    assert again.json()["last_refresh"]["tool_calls"] == []
    verification = client.post("/api/verify", json={})
    assert verification.status_code == 200
    assert verification.json()["passed"] is True


def test_browser_sessions_are_isolated_and_foreign_artifact_is_rejected(app):
    with TestClient(app) as first, TestClient(app) as second:
        a, b = seed(first), seed(second)
        assert a["session_id"] != b["session_id"]
        first.post("/api/change", json={"kind": "fx", "value": "1.20"})
        untouched = second.get("/api/state").json()
        assert claims(reports(untouched)["eu"])["eu_revenue"]["value"] == 209000
        assert reports(untouched)["eu"]["state"] == "current"
        foreign_id = quote(a["reports"][0]["id"], safe="")
        assert_error(second.get(f"/api/evidence/{foreign_id}"), 404)
        foreign_refresh = second.post("/api/refresh", json={"report_ids": [a["reports"][0]["id"]]})
        assert foreign_refresh.status_code in {400, 404}, foreign_refresh.text
        assert "error" in foreign_refresh.json()
        assert claims(reports(second.get("/api/state").json())["eu"])["eu_revenue"]["value"] == 209000


def test_requests_without_session_fail_instead_of_creating_shared_state(client):
    assert_error(client.get("/api/state"), 401)
    assert_error(client.post("/api/change", json={"kind": "fx", "value": "1.20"}), 401)


@pytest.mark.parametrize("body", [
    {"kind": "unknown"},
    {"kind": []},
    {"kind": "fx", "value": "NaN"},
    {"kind": "refund", "delta_cents": 10**12},
    {"kind": "remove", "source": "../../private"},
    {"kind": "remove", "source": []},
    {"kind": "support", "count": 6},
])
def test_source_change_is_bounded_and_whitelisted(client, body):
    seed(client)
    assert_error(client.post("/api/change", json=body), 400)


def test_missing_source_blocks_refresh(client):
    seed(client)
    removed = client.post("/api/change", json={"kind": "remove", "source": "fx"})
    assert removed.status_code == 200, removed.text
    assert reports(removed.json())["eu"]["state"] != "current"
    assert_error(client.post("/api/refresh", json={}), 409)
    verification = client.post("/api/verify", json={})
    assert verification.status_code == 200, verification.text
    assert verification.json()["passed"] is False


def test_reset_uses_new_generation_and_restores_fixture(client):
    initial = seed(client)
    old_id = initial["reports"][0]["id"]
    client.post("/api/change", json={"kind": "fx", "value": "1.20"})
    reset = client.post("/api/reset", json={})
    assert reset.status_code == 200, reset.text
    state = reset.json()
    assert state["session_id"] == initial["session_id"]
    assert state["generation"] != initial["generation"]
    assert claims(reports(state)["eu"])["eu_revenue"]["value"] == 209000
    assert state["impact"]["change"] is None
    assert_error(client.get(f"/api/evidence/{quote(old_id, safe='')}"), 404)


def test_session_capacity_does_not_break_existing_session(tmp_path, factory):
    app = create_app(state_dir=tmp_path / "limited", graph_factory=factory,
                     max_sessions=1, static_dir=tmp_path / "missing")
    with TestClient(app) as first, TestClient(app) as second:
        initial = seed(first)
        assert_error(second.post("/api/session"), 503)
        assert first.get("/api/state").json()["session_id"] == initial["session_id"]
        assert first.post("/api/reset", json={}).status_code == 200


def test_reopening_application_restores_session_and_queries_existing_graph(tmp_path, factory):
    directory = tmp_path / "persistent"
    first_app = create_app(state_dir=directory, graph_factory=factory, static_dir=tmp_path / "missing")
    with TestClient(first_app) as first:
        initial = seed(first)
        first.post("/api/change", json={"kind": "fx", "value": "1.20"})
        first.post("/api/refresh", json={})
        cookie = first.cookies.get("proofflow_session")
    before_clients = len(factory.clients)
    second_app = create_app(state_dir=directory, graph_factory=factory, static_dir=tmp_path / "missing")
    with TestClient(second_app) as reopened:
        reopened.cookies.set("proofflow_session", cookie)
        response = reopened.get("/api/state")
        assert response.status_code == 200, response.text
        state = response.json()
        assert state["session_id"] == initial["session_id"]
        assert claims(reports(state)["eu"])["eu_revenue"]["value"] == 228000
        assert state["last_refresh"]["executed_count"] == 4
        assert len(factory.clients) > before_clients
        assert any(client.queries > 0 for client in factory.clients[before_clients:])


def test_unknown_api_routes_are_not_swallowed_by_spa(tmp_path, factory):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>ProofFlow fixture</title>")
    app = create_app(state_dir=tmp_path / "spa-sessions", graph_factory=factory, static_dir=static)
    with TestClient(app) as client:
        assert_error(client.get("/api/not-a-route"), 404)
        page = client.get("/nested/client/route")
        assert page.status_code == 200
        assert "ProofFlow fixture" in page.text


def test_graph_outage_is_a_real_failure_for_health_and_state(client, factory):
    seed(client)
    factory.available = False
    assert_error(client.get("/health"), 503)
    assert_error(client.get("/api/state"), 503)


def test_public_evidence_is_an_isolated_static_tree(tmp_path, factory):
    static = tmp_path / "static"
    evidence = static / "evidence"
    evidence.mkdir(parents=True)
    (static / "index.html").write_text("ProofFlow application")
    (static / "private-file.txt").write_text("not part of the evidence package")
    (evidence / "index.html").write_text("ProofFlow independently verifiable evidence")
    (evidence / "manifest.json").write_text('{"files": []}')
    (evidence / "outside.txt").symlink_to(static / "private-file.txt")
    app = create_app(state_dir=tmp_path / "sessions", graph_factory=factory, static_dir=static)
    with TestClient(app) as client:
        redirect = client.get("/evidence", follow_redirects=False)
        assert redirect.status_code in {307, 308}
        assert redirect.headers["location"].endswith("/evidence/")
        page = client.get("/evidence/")
        assert page.status_code == 200
        assert "independently verifiable evidence" in page.text
        assert client.get("/evidence/manifest.json").json() == {"files": []}
        assert_error(client.get("/evidence/missing.json"), 404)
        assert_error(client.get("/evidence/outside.txt"), 404)
        assert_error(client.get("/evidence/%2e%2e%2fprivate-file.txt"), 404)
        assert not client.cookies


def test_unbuilt_public_evidence_does_not_return_the_application(tmp_path, factory):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("ProofFlow application")
    app = create_app(state_dir=tmp_path / "sessions", graph_factory=factory, static_dir=static)
    with TestClient(app) as client:
        assert_error(client.get("/evidence/"), 404)
        assert_error(client.get("/evidence/not-built.zip"), 404)


def test_evidence_endpoint_returns_actual_record_and_path(client):
    initial = seed(client)
    target = reports(initial)["eu"]["id"]
    changed = client.post("/api/change", json={"kind": "fx", "value": "1.20"}).json()
    old_source = changed["impact"]["change"]["previous_source_id"]
    response = client.get(f"/api/evidence/{quote(target, safe='')}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["artifact"]["id"] == target
    assert payload["receipt"]["tool"] == "compose_report"
    assert payload["paths"]
    path = payload["paths"][0]
    assert path["source_id"] == old_source
    assert path["target_id"] == target
    assert path["nodes"][0]["id"] == old_source
    assert path["nodes"][-1]["id"] == target
    assert len(path["edges"]) >= 4


def test_other_supported_mutations_execute_and_refresh(client):
    seed(client)
    for body, expected_company, expected_support in [
        ({"kind": "order", "delta_cents": 10000}, 567500, 2),
        ({"kind": "refund", "delta_cents": 10000}, 556500, 2),
        ({"kind": "support", "count": 2}, 556500, 4),
    ]:
        changed = client.post("/api/change", json=body)
        assert changed.status_code == 200, changed.text
        refreshed = client.post("/api/refresh", json={})
        assert refreshed.status_code == 200, refreshed.text
        state = refreshed.json()
        assert claims(reports(state)["company"])["company_revenue"]["value"] == expected_company
        assert claims(reports(state)["eu"])["eu_support"]["value"] == expected_support


def test_expired_idle_session_capacity_is_reclaimed_after_restart(tmp_path, factory):
    directory = tmp_path / "ttl-sessions"
    first_app = create_app(state_dir=directory, graph_factory=factory, max_sessions=1,
                           static_dir=tmp_path / "missing", session_ttl_seconds=10)
    with TestClient(first_app) as first:
        original = seed(first)
    old_directory = directory / original["session_id"]
    metadata_path = old_directory / "session.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["last_seen_unix"] = time.time() - 100
    metadata_path.write_text(json.dumps(metadata))
    second_app = create_app(state_dir=directory, graph_factory=factory, max_sessions=1,
                            static_dir=tmp_path / "missing", session_ttl_seconds=10)
    with TestClient(second_app) as second:
        replacement = seed(second)
        assert replacement["session_id"] != original["session_id"]
        assert not old_directory.exists()
        assert (directory / replacement["session_id"] / "session.json").is_file()


def test_failed_first_state_render_does_not_consume_capacity(tmp_path, factory):
    directory = tmp_path / "failed-session"
    application = create_app(state_dir=directory, graph_factory=factory, max_sessions=1,
                             static_dir=tmp_path / "missing")
    with TestClient(application) as browser:
        # Seed succeeds and publishes ready metadata; its first graph-view path fails.
        factory.fail_next_path = True
        assert_error(browser.post("/api/session"), 503)
        restored = seed(browser)
        assert restored["session_id"]
        assert len(list(directory.glob("*/session.json"))) == 1


def test_missing_expected_forward_edge_fails_state_closed(client, factory):
    seed(client)
    # Ancestor traversal remains intact; only a direct forward-edge proof is absent.
    factory.suppress_next_path = True
    assert_error(client.get("/api/state"), 503)
    assert client.get("/api/state").status_code == 200


class ObservedLock:
    """Signal that a particular waiter reached the locked session, without sleeps."""

    def __init__(self, lock, waiter_attempt):
        self.lock = lock
        self.waiter_attempt = waiter_attempt

    def acquire(self, *args, **kwargs):
        if threading.current_thread().name == "same-session-waiter":
            self.waiter_attempt.set()
        return self.lock.acquire(*args, **kwargs)

    def release(self):
        return self.lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def test_waiting_same_session_does_not_block_another_browser(app, client):
    a = seed(client)["session_id"]
    client.cookies.clear()
    b = seed(client)["session_id"]
    manager = app.state.manager
    holder_ready = threading.Event()
    release_holder = threading.Event()
    waiter_attempt = threading.Event()
    waiter_entered = threading.Event()
    other_entered = threading.Event()
    failures = []
    with manager.session(a) as session_a:
        session_a.lock = ObservedLock(session_a.lock, waiter_attempt)

    def holder():
        try:
            with manager.session(a):
                holder_ready.set()
                if not release_holder.wait(5):
                    raise TimeoutError("test did not release session A")
        except BaseException as exc:
            failures.append(exc)

    def same_waiter():
        try:
            with manager.session(a):
                waiter_entered.set()
        except BaseException as exc:
            failures.append(exc)

    def other_browser():
        try:
            with manager.session(b):
                other_entered.set()
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=holder, name="session-holder", daemon=True),
               threading.Thread(target=same_waiter, name="same-session-waiter", daemon=True),
               threading.Thread(target=other_browser, name="other-browser", daemon=True)]
    try:
        threads[0].start()
        assert holder_ready.wait(1), "holder failed to enter session A"
        threads[1].start()
        assert waiter_attempt.wait(1), "same-session waiter did not reach session A's lock"
        threads[2].start()
        assert other_entered.wait(1), "session B was blocked behind session A's waiter"
        assert not waiter_entered.is_set(), "same-session lock did not serialize requests"
    finally:
        release_holder.set()
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=2)
    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    assert waiter_entered.is_set()


def test_active_session_is_not_expired_while_new_browser_checks_capacity(tmp_path, factory):
    directory = tmp_path / "active-ttl"
    application = create_app(state_dir=directory, graph_factory=factory, max_sessions=1,
                             static_dir=tmp_path / "missing", session_ttl_seconds=10)
    with TestClient(application) as existing:
        initial = seed(existing)
        manager = application.state.manager
        ready = threading.Event()
        release = threading.Event()
        creation_done = threading.Event()
        failures = []
        result = {}
        started = time.time()

        def holder():
            try:
                with manager.session(initial["session_id"]) as current:
                    current.metadata["last_seen_unix"] = time.time() - 100
                    current.save()
                    result["active"] = current
                    ready.set()
                    if not release.wait(5):
                        raise TimeoutError("test did not release active session")
                    # Expiry must not close the SQLite handle of an active request.
                    assert current.store.get_head("report:eu") is not None
            except BaseException as exc:
                failures.append(exc)

        other = TestClient(application)

        def create_new():
            try:
                result["response"] = other.post("/api/session")
            except BaseException as exc:
                failures.append(exc)
            finally:
                creation_done.set()

        workers = [threading.Thread(target=holder, name="active-holder", daemon=True),
                   threading.Thread(target=create_new, name="new-browser", daemon=True)]
        try:
            workers[0].start()
            assert ready.wait(1)
            workers[1].start()
            assert creation_done.wait(1), "capacity check waited for the active session instead of refusing"
            assert_error(result["response"], 503)
            assert (directory / initial["session_id"]).is_dir()
        finally:
            release.set()
            for worker in workers:
                if worker.ident is not None:
                    worker.join(timeout=2)
            other.close()
        assert not failures
        assert all(not worker.is_alive() for worker in workers)
        metadata = json.loads((directory / initial["session_id"] / "session.json").read_text())
        assert metadata["last_seen_unix"] >= started
        assert existing.get("/api/state").status_code == 200
