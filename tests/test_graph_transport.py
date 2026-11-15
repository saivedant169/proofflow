import httpx
import pytest

from proofflow.graph import HydraGraph, GraphError


def test_consuming_cursor_preserves_request_and_does_not_skip_last_page():
    bodies = []
    import json
    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        n = len(bodies)
        return httpx.Response(200, json={"query_id": "same-query", "columns": ["key"],
            "rows": [[{"type": "string", "value": str(n)}]],
            "next_cursor": "same-consuming-cursor" if n < 3 else None})
    with HydraGraph(token="test-only") as g:
        g.client.close()
        g.client = httpx.Client(transport=httpx.MockTransport(respond))
        assert g.query("example", {"src": 7}) == [{"key": "1"}, {"key": "2"}, {"key": "3"}]
    assert all(b["parameters"] == {"src": 7} and b["page_size"] == 1024 for b in bodies)
    assert bodies[1]["cursor"] == bodies[2]["cursor"]


def test_http_failure_cannot_turn_into_empty_graph_success():
    with HydraGraph(token="test-only") as g:
        g.client.close()
        g.client = httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(429, json={"error": {"code": "resource_exhausted"}})))
        with pytest.raises(GraphError):
            g.query("query")


def test_detects_collision_before_mutating():
    with HydraGraph(token="test-only") as g:
        g.query = lambda *a, **kw: [{"key": "someone-elses-key", "kind": "source", "payload": "{}"}]
        with pytest.raises(GraphError, match="collision"):
            g.put_node("my-key", "source", {})
