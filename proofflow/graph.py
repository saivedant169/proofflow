"""Small HydraDB HTTP adapter. Runtime paths execute in Hydra, without fallback.

The integer vertex ID is a deterministic mapping of a namespaced logical key.
Every write checks the stored key to detect a collision before mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Protocol

import httpx


class GraphError(RuntimeError):
    pass


class GraphPort(Protocol):
    def put_node(self, node_id: str, kind: str, properties: dict[str, Any]) -> None: ...
    def put_edge(self, source_id: str, target_id: str, kind: str,
                 properties: dict[str, Any] | None = None) -> None: ...
    def descendants(self, node_ids: list[str], max_depth: int = 15) -> list[str]: ...
    def ancestors(self, node_ids: list[str], max_depth: int = 15) -> list[str]: ...


def _local_settings() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / ".env"
    result: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                result[k] = v.strip().strip("\"'")
    return result


def _unwrap(cell: Any) -> Any:
    if isinstance(cell, dict) and "type" in cell:
        return cell.get("value")
    return cell


class HydraGraph:
    def __init__(self, url: str | None = None, token: str | None = None,
                 namespace: str = "proofflow", graph_id: str = "default",
                 cell_id: str = "cell-0", timeout: float = 30.0):
        settings = _local_settings()
        self.url = (url or os.environ.get("PROOFFLOW_HYDRA_URL") or
                    settings.get("PROOFFLOW_HYDRA_URL", "http://127.0.0.1:18443")).rstrip("/")
        token = token or os.environ.get("PROOFFLOW_HYDRA_TOKEN") or settings.get("PROOFFLOW_HYDRA_TOKEN")
        if not token:
            raise GraphError("HydraDB token is not configured; run scripts/init_local.py locally.")
        if not namespace or len(namespace) > 180:
            raise ValueError("A bounded, nonempty workspace namespace is required")
        self.namespace = namespace
        self.graph_id = graph_id
        self.cell_id = cell_id
        self.bookmark: str | None = None
        self.queries = 0
        self.mutations = 0
        self.client = httpx.Client(timeout=timeout, headers={
            "Authorization": f"Bearer {token}", "X-Graph-Namespace": "default",
            "Content-Type": "application/json",
        })

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "HydraGraph":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def vertex_id(self, key: str) -> int:
        return int(hashlib.sha256(f"{self.namespace}\0{key}".encode()).hexdigest()[:15], 16)

    def query(self, query: str, parameters: dict[str, Any] | None = None,
              *, mutation: bool = False) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"cell_id": self.cell_id, "query": query,
                                "parameters": parameters or {}, "page_size": 1024,
                                "query_id": "pf-" + uuid.uuid4().hex}
        if self.bookmark:
            body["bookmark"] = self.bookmark
        results: list[dict[str, Any]] = []
        for _ in range(100):
            self.queries += 1
            if mutation:
                self.mutations += 1
            try:
                response = self.client.post(f"{self.url}/v1/graphs/{self.graph_id}/query", json=body)
                data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                # Cursor fetches are consuming, so do not retry a timed-out page.
                raise GraphError(f"HydraDB request failed ({type(exc).__name__}); no fallback used") from exc
            if response.is_error or "error" in data or "rows" not in data:
                raise GraphError(f"HydraDB query failed: HTTP {response.status_code}: {data}")
            self.bookmark = data.get("bookmark") or self.bookmark
            columns = data.get("columns", [])
            results.extend(dict(zip(columns, (_unwrap(c) for c in row))) for row in data["rows"])
            if data.get("next_cursor") is None:
                return results
            body["cursor"] = data["next_cursor"]
            body["query_id"] = data["query_id"]
        raise GraphError("HydraDB response exceeded the bounded page count; refusing partial results")

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        rows = self.query("MATCH (n {id: $id}) RETURN n.key AS key, n.kind AS kind, n.payload AS payload",
                          {"id": self.vertex_id(node_id)})
        if not rows:
            return None
        row = rows[0]
        if row["key"] != node_id:
            raise GraphError("Vertex hash collision or foreign node detected")
        return {"id": node_id, "kind": row["kind"], "properties": json.loads(row["payload"] or "{}")}

    def put_node(self, node_id: str, kind: str, properties: dict[str, Any]) -> None:
        self.get_node(node_id)  # collision check, including after process restart
        payload = json.dumps(properties, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.query("UNWIND $rows AS row MERGE (n {id: row.id}) "
                   "SET n:ProofFlow, n.key = row.key, n.kind = row.kind, "
                   "n.workspace = row.workspace, n.payload = row.payload",
                   {"rows": [{"id": self.vertex_id(node_id), "key": node_id, "kind": kind,
                              "workspace": self.namespace, "payload": payload}]}, mutation=True)

    def put_edge(self, source_id: str, target_id: str, kind: str,
                 properties: dict[str, Any] | None = None) -> None:
        if source_id == target_id:
            raise GraphError("Self-dependencies are unsupported")
        if kind.upper() in {"SUPERSEDES", "REPLACES"}:
            raise GraphError("Version history must not be encoded as a FLOW dependency")
        for key in (source_id, target_id):
            if self.get_node(key) is None:
                raise GraphError(f"Cannot link absent graph node: {key}")
        payload = json.dumps(properties or {}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.query("MERGE (a {id: $src})-[:FLOW {kind: $kind, payload: $payload}]->(b {id: $dst})",
                   {"src": self.vertex_id(source_id), "dst": self.vertex_id(target_id),
                    "kind": kind, "payload": payload}, mutation=True)
        # v0.4.0's bounded MATCH requires a fixed outgoing source. Maintain an
        # explicit reverse index in Hydra so ancestry is still engine-executed.
        self.query("MERGE (a {id: $src})-[:REV_FLOW {kind: $kind, payload: $payload}]->(b {id: $dst})",
                   {"src": self.vertex_id(target_id), "dst": self.vertex_id(source_id),
                    "kind": kind, "payload": payload}, mutation=True)

    def _walk_at_depth(self, node_ids: list[str], depth: int, incoming: bool) -> set[str]:
        relation = "REV_FLOW" if incoming else "FLOW"
        edge = f"-[:{relation}*1..{depth}]->"
        found: set[str] = set()
        for key in sorted(set(node_ids)):
            if self.get_node(key) is None:
                raise GraphError(f"Cannot traverse absent graph node: {key}")
            rows = self.query(f"MATCH (a {{id: $id}}){edge}(b) RETURN b.key AS key, b.workspace AS workspace",
                              {"id": self.vertex_id(key)})
            for row in rows:
                if row["workspace"] != self.namespace or not row["key"]:
                    raise GraphError("Traversal crossed an unowned or unlabelled vertex")
                found.add(row["key"])
        return found - set(node_ids)

    def _walk(self, node_ids: list[str], max_depth: int, incoming: bool) -> list[str]:
        if not isinstance(max_depth, int) or not 1 <= max_depth <= 15:
            raise ValueError("max_depth must be an integer from 1 to 15")
        result = self._walk_at_depth(node_ids, max_depth, incoming)
        extended = self._walk_at_depth(node_ids, max_depth + 1, incoming)
        if extended - result:
            raise GraphError("Dependency graph exceeds traversal depth; refusing incomplete validity result")
        return sorted(result)

    def descendants(self, node_ids: list[str], max_depth: int = 15) -> list[str]:
        return self._walk(node_ids, max_depth, False)

    def ancestors(self, node_ids: list[str], max_depth: int = 15) -> list[str]:
        return self._walk(node_ids, max_depth, True)

    def paths(self, source_id: str, target_id: str, max_depth: int = 15) -> list[dict[str, Any]]:
        if not 1 <= max_depth <= 15:
            raise ValueError("Invalid path depth")
        rows = self.query("CALL algo.SPpaths({sourceNode: $src, targetNode: $dst, "
                          "relTypes: ['FLOW'], relDirection: 'outgoing', maxLen: $depth, pathCount: 3}) "
                          "YIELD path RETURN path", {"src": self.vertex_id(source_id),
                                                     "dst": self.vertex_id(target_id), "depth": max_depth})
        return [row["path"] for row in rows]
