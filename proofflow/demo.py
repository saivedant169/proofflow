"""Isolated persistent sessions for the authored, actually executed browser demo."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any, Callable
import uuid

from .analytics import DEMO_SOURCES
from .artifacts import ArtifactStore
from .graph import GraphError, HydraGraph
from .models import InvalidInputError, MissingEvidenceError
from .runtime import ProofFlowRuntime


class SessionMissing(Exception):
    pass


class SessionCapacity(Exception):
    pass


class ActionLimit(Exception):
    pass


ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
LABELS = {
    "metric:gross": "Gross regional revenue", "metric:refunds": "Regional refunds",
    "metric:net": "Net regional revenue", "metric:regional": "Regional USD revenue",
    "metric:company": "Company revenue", "metric:support": "Support tickets",
    "report:company": "Company weekly report", "report:eu": "EU operations brief",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def unwrap_native(value: Any) -> Any:
    if isinstance(value, dict):
        if "String" in value:
            return value["String"]
        if "value" in value:
            return value["value"]
    return value


class DemoSession:
    def __init__(self, directory: Path, metadata: dict, graph_factory: Callable[..., Any]):
        self.directory = directory
        self.metadata = metadata
        self.id = metadata["session_id"]
        self.generation = metadata["generation"]
        if not ID_PATTERN.fullmatch(self.id) or not ID_PATTERN.fullmatch(self.generation):
            raise SessionMissing("Invalid session identity")
        self.lock = threading.RLock()
        self.store = ArtifactStore(directory / "generations" / self.generation)
        self.graph = graph_factory(namespace=f"demo-{self.id}-{self.generation}")
        self.runtime = ProofFlowRuntime(self.store, self.graph)
        self.recent_actions: list[float] = []
        # Reservations include requests waiting for this session's lock. They
        # protect the same object from idle reclamation without a global convoy.
        self.active_requests = 0

    def save(self) -> None:
        atomic_json(self.directory / "session.json", self.metadata)

    def touch(self) -> None:
        self.metadata["last_seen_unix"] = time.time()
        self.save()

    def rate_limit(self) -> None:
        cutoff = time.monotonic() - 60
        self.recent_actions = [value for value in self.recent_actions if value >= cutoff]
        if len(self.recent_actions) >= 30:
            raise ActionLimit("Please wait before running more demo actions")
        self.recent_actions.append(time.monotonic())

    def seed(self) -> None:
        runtime = self.runtime
        src = {name: runtime.set_source(name, deepcopy(value), f"Authored commerce {name}").current_id
               for name, value in DEMO_SOURCES.items()}
        gross = runtime.execute("gross_by_region", {"orders": src["orders"]}, logical_id="metric:gross", run_id="run-A")
        refunds = runtime.execute("refunds_by_region", {"orders": src["orders"], "refunds": src["refunds"]}, logical_id="metric:refunds", run_id="run-A")
        net = runtime.execute("net_by_region", {"gross": gross.id, "refunds": refunds.id}, logical_id="metric:net", run_id="run-A")
        regional = runtime.execute("convert_to_usd", {"net": net.id, "fx": src["fx"]}, logical_id="metric:regional", run_id="run-A")
        company = runtime.execute("company_total", {"regional": regional.id}, logical_id="metric:company", run_id="run-A")
        support = runtime.execute("support_by_region", {"tickets": src["tickets"]}, logical_id="metric:support", run_id="run-A")
        section = {"key": "eu_support", "label": "EU support tickets", "input": "support",
                   "path": ["regions", "EU", "tickets"], "unit": "tickets"}
        runtime.execute("compose_report", {"revenue": company.id, "support": support.id}, {
            "title": "Company weekly report", "sections": [
                {"key": "company_revenue", "label": "Company revenue", "input": "revenue",
                 "path": ["usd_cents"], "unit": "USD cents"}, section]},
            logical_id="report:company", run_id="run-A")
        runtime.execute("compose_report", {"revenue": regional.id, "support": support.id}, {
            "title": "EU operations brief", "sections": [
                {"key": "eu_revenue", "label": "EU revenue", "input": "revenue",
                 "path": ["regions", "EU", "usd_cents"], "unit": "USD cents"}, section]},
            logical_id="report:eu", run_id="run-B")
        self.metadata.update(ready=True, change=None, changed_source_ids=[], affected_artifacts=[], last_refresh=None)
        self.save()

    def reports(self):
        return [(key, self.store.get_head(f"report:{key}")) for key in ("company", "eu")]

    @staticmethod
    def label(record) -> str:
        return LABELS.get(record.logical_id, record.metadata.get("title", record.logical_id))

    def _graph_state(self, statuses: dict[str, str]) -> dict:
        heads = self.store.heads()
        head_ids = {record.id for record in heads}
        selected = set(head_ids)
        for _, report in self.reports():
            selected.update(self.graph.ancestors([report.id], max_depth=15))
        records = {record.id: record for record in self.store.list_records() if record.id in selected}
        nodes = []
        for node_id, record in sorted(records.items()):
            if self.graph.get_node(node_id) is None:
                raise GraphError("Persisted demo evidence is missing from HydraDB; no fallback used")
            if record.kind == "execution":
                output_id = self.store.read(node_id)["output_id"]
                state = statuses.get(output_id) or self.runtime.currentness(output_id).state
            else:
                state = statuses.get(node_id) or self.runtime.currentness(node_id).state
            statuses[node_id] = state
            nodes.append({"id": node_id, "label": self.label(record), "kind": record.kind,
                          "logical_id": record.logical_id, "state": state, "current_head": node_id in head_ids})
        edges = []
        expected = set()
        for record in records.values():
            if record.kind != "artifact":
                continue
            receipt = record.metadata["receipt_id"]
            expected.add((receipt, record.id, "PRODUCED"))
            expected.add((record.metadata["tool_version_id"], receipt, "USED_TOOL"))
            expected.update((node_id, receipt, "CONSUMED") for node_id in record.metadata["inputs"].values())
        for source, target, kind in sorted(expected):
            if source not in records or target not in records:
                continue
            # Display only an edge whose direct native path actually exists.
            native = self.graph.paths(source, target, max_depth=1)
            if not any(len(path.get("relationships", [])) == 1 for path in native):
                raise GraphError("Expected native lineage edge is missing; refusing incomplete demo evidence")
            edges.append({"source": source, "target": target, "kind": kind})
        return {"nodes": nodes, "edges": edges, "projection_hint": "collapse_execution_nodes"}

    def state(self) -> dict:
        statuses = {}
        reports = []
        for key, record in self.reports():
            if record is None:
                raise MissingEvidenceError("Demo report was not created successfully")
            validity = self.runtime.currentness(record.id)
            statuses[record.id] = validity.state
            reports.append({"key": key, "id": record.id, "title": self.label(record),
                            "run_id": record.metadata["run_id"], "state": validity.state,
                            "claims": self.runtime.report_claims(record.id)})
        sources = []
        for record in self.store.heads("source"):
            value = self.store.read(record.id)
            summary = {"rows": len(value)} if isinstance(value, list) else value
            sources.append({"name": record.metadata["name"], "id": record.id,
                            "content_hash": record.content_hash,
                            "removed": bool(record.metadata.get("deleted")), "summary": summary})
        executions = [{"id": record.id, **self.store.read(record.id)}
                      for record in self.store.list_records("execution")]
        graph_state = self._graph_state(statuses)
        return {
            "session_id": self.id, "generation": self.generation,
            "created_at": self.metadata["created_at"], "mode": "guided_real_execution",
            "backend": {"engine": "HydraDB OSS", "native_queries": self.graph.queries, "fallback": False},
            "dataset": {"label": "Fictional commerce dataset", "sources": sources},
            "reports": reports,
            "impact": {"change": self.metadata.get("change"),
                       "affected_artifacts": self.metadata.get("affected_artifacts", []),
                       "changed_source_ids": self.metadata.get("changed_source_ids", [])},
            "graph": graph_state, "executions": executions,
            "last_refresh": self.metadata.get("last_refresh"),
            "notices": ["Authored demo data; actual SQLite calculations and HydraDB traversal.",
                        "Source-level dependencies conservatively identify results requiring revalidation.",
                        "Guided report recipes; the hosted demo does not invoke an external language model."],
        }

    def change(self, payload: dict) -> dict:
        self.rate_limit()
        kind = payload.get("kind")
        if not isinstance(kind, str):
            raise InvalidInputError("Correction kind must be a string")
        if kind == "fx":
            if set(payload) != {"kind", "value"}:
                raise InvalidInputError("FX correction requires kind and value")
            try:
                rate = Decimal(str(payload["value"]))
            except (InvalidOperation, ValueError):
                raise InvalidInputError("Exchange rate must be a decimal between 0.10 and 5.00")
            if not rate.is_finite() or not Decimal("0.10") <= rate <= Decimal("5.00"):
                raise InvalidInputError("Exchange rate must be between 0.10 and 5.00")
            source = "fx"
            value = self._source(source)
            value["EUR"] = str(rate)
            label = f"EUR → USD corrected to {rate}"
        elif kind in {"order", "refund"}:
            if set(payload) != {"kind", "delta_cents"} or type(payload["delta_cents"]) is not int or not -50000 <= payload["delta_cents"] <= 50000:
                raise InvalidInputError("A correction needs integer delta_cents between -50000 and 50000")
            source = "orders" if kind == "order" else "refunds"
            value = self._source(source)
            field = "gross_cents" if kind == "order" else "refund_cents"
            value[0][field] += payload["delta_cents"]
            if value[0][field] < 0:
                raise InvalidInputError("Correction would make the source amount negative")
            label = f"EU {kind} corrected by {payload['delta_cents']} cents"
        elif kind == "support":
            if set(payload) != {"kind", "count"} or type(payload["count"]) is not int or not 1 <= payload["count"] <= 5:
                raise InvalidInputError("Support correction needs an integer count from 1 to 5")
            source = "tickets"
            value = self._source(source)
            value.extend({"ticket_id": f"demo-{uuid.uuid4().hex}", "region": "EU", "status": "open"}
                         for _ in range(payload["count"]))
            label = f"Added {payload['count']} EU support tickets"
        elif kind == "remove":
            if (set(payload) != {"kind", "source"} or not isinstance(payload["source"], str)
                    or payload["source"] not in DEMO_SOURCES):
                raise InvalidInputError("Only orders, refunds, fx or tickets can be removed")
            source = payload["source"]
            value = None
            label = f"Removed {source} source"
        else:
            raise InvalidInputError("Unknown staged correction")
        change = (self.runtime.remove_source(source) if kind == "remove"
                  else self.runtime.set_source(source, value, f"Authored commerce {source}"))
        roots = list(self.metadata.get("changed_source_ids", []))
        if change.changed and change.previous_id and change.previous_id not in roots:
            roots.append(change.previous_id)
        affected = self.runtime.affected(roots) if roots else []
        self.metadata.update(
            change={"kind": kind, "label": label, "previous_source_id": change.previous_id,
                    "current_source_id": change.current_id, "timestamp": now()},
            changed_source_ids=roots,
            affected_artifacts=[{"id": item.id, "logical_id": item.logical_id,
                                 "title": self.label(item), "kind": item.kind} for item in affected],
            last_refresh=None,
        )
        self.save()
        return self.state()

    def _source(self, name: str):
        record = self.store.get_head(f"source:{name}")
        if record is None or record.metadata.get("deleted"):
            raise MissingEvidenceError("This source is unavailable; reset the demo to restore it")
        return self.store.read(record.id)

    def refresh(self, report_ids: list[str] | None = None) -> dict:
        self.rate_limit()
        targets = report_ids if report_ids is not None else [record.id for _, record in self.reports()]
        if not isinstance(targets, list) or not 1 <= len(targets) <= 2 or not all(isinstance(x, str) for x in targets):
            raise InvalidInputError("Select one or two report artifact IDs")
        for target in targets:
            record = self.store.get(target, required=False)
            if record is None or record.kind != "artifact" or record.metadata.get("tool") != "compose_report":
                raise SessionMissing("Unknown report in this session")
        support_before = self.store.get_head("metric:support")
        count_before, queries_before = len(self.runtime.calls), self.graph.queries
        result = self.runtime.refresh(targets)
        calls = self.runtime.calls[count_before:]
        support_after = self.store.get_head("metric:support")
        verification = self.verify()
        self.metadata["last_refresh"] = {
            "executed_count": len(calls), "reused_count": len(set(result.reused)),
            "executed_artifact_ids": list(result.executed), "reused_artifact_ids": list(dict.fromkeys(result.reused)),
            "elapsed_ms": result.elapsed_ms,
            "tool_calls": [{key: call.get(key) for key in ("tool", "status", "elapsed_ms", "output_id")} for call in calls],
            "numeric_parity": verification["passed"],
            "unchanged_support": support_before.id == support_after.id and support_before.content_hash == support_after.content_hash,
            "graph_queries": self.graph.queries - queries_before,
        }
        self.save()
        return self.state()

    def verify(self) -> dict:
        results = []
        for _, record in self.reports():
            status = self.runtime.currentness(record.id)
            try:
                expected = self.runtime.full_recompute(record.id)
                same = self.store.read(record.id) == expected
                error = None
            except MissingEvidenceError as exc:
                same, error = False, str(exc)
            results.append({"id": record.id, "title": self.label(record), "state": status.state,
                            "numeric_match": same, "error": error})
        return {"passed": all(row["numeric_match"] and row["state"] == "current" for row in results),
                "reports": results,
                "scope": "Fresh recipe evaluation independent of Hydra traversal and cached intermediate values; same tool arithmetic."}

    def evidence(self, artifact_id: str) -> dict:
        record = self.store.get(artifact_id, required=False)
        if record is None or record.kind != "artifact":
            raise SessionMissing("Unknown artifact in this session")
        validity = self.runtime.currentness(record.id)
        receipt_id = record.metadata["receipt_id"]
        paths = []
        for root in self.metadata.get("changed_source_ids", []):
            for native in self.graph.paths(root, record.id, max_depth=15):
                node_map = {}
                nodes = []
                for item in native.get("nodes", []):
                    key = unwrap_native(item.get("properties", {}).get("key"))
                    stored = self.store.get(key, required=False) if isinstance(key, str) else None
                    if stored is None:
                        raise GraphError("Native evidence path contains an unknown session vertex")
                    node_map[item["id"]] = key
                    nodes.append({"id": key, "label": self.label(stored), "kind": stored.kind})
                edges = [{"source": node_map[item["src"]], "target": node_map[item["dst"]],
                          "kind": unwrap_native(item.get("properties", {}).get("kind")) or "FLOW"}
                         for item in native.get("relationships", [])]
                paths.append({"source_id": root, "target_id": record.id, "nodes": nodes, "edges": edges})
        return {"artifact": {**record.to_dict(), "state": validity.state, "saved_value": self.store.read(record.id)},
                "receipt": {"id": receipt_id, **self.store.read(receipt_id)}, "paths": paths}

    def close(self) -> None:
        self.store.close()
        self.graph.close()


class SessionManager:
    def __init__(self, state_dir: str | Path, graph_factory: Callable[..., Any] = HydraGraph,
                 max_sessions: int = 16, session_ttl_seconds: float = 3600):
        if max_sessions < 1 or not math.isfinite(session_ttl_seconds) or session_ttl_seconds <= 0:
            raise ValueError("Session capacity and idle TTL must be positive")
        self.directory = Path(state_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.graph_factory = graph_factory
        self.max_sessions = max_sessions
        self.session_ttl_seconds = session_ttl_seconds
        self.lock = threading.RLock()
        self.sessions: dict[str, DemoSession] = {}
        self.pending: set[str] = set()

    @staticmethod
    def _last_seen(metadata: dict) -> float:
        value = metadata.get("last_seen_unix")
        if type(value) in (int, float) and math.isfinite(value):
            return float(value)
        try:
            return datetime.fromisoformat(metadata["created_at"]).timestamp()
        except (KeyError, TypeError, ValueError):
            return 0.0

    def _expired(self, metadata: dict) -> bool:
        return time.time() - self._last_seen(metadata) >= self.session_ttl_seconds

    def _owned_metadata(self) -> dict[str, dict]:
        """Only directories bearing this application's generated identity count."""
        found = {}
        for directory in self.directory.iterdir():
            if directory.is_symlink() or not directory.is_dir() or not ID_PATTERN.fullmatch(directory.name):
                continue
            path = directory / "session.json"
            try:
                metadata = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            if (metadata.get("session_id") == directory.name and metadata.get("ready")
                    and isinstance(metadata.get("generation"), str)
                    and ID_PATTERN.fullmatch(metadata["generation"])):
                found[directory.name] = metadata
        return found

    def _remove_directory(self, session_id: str) -> None:
        directory = self.directory / session_id
        # Callers pass generated IDs, never paths from request JSON. Symlinks are
        # not followed even if an operator has modified the local state folder.
        if not ID_PATTERN.fullmatch(session_id) or directory.is_symlink():
            raise SessionMissing("Invalid session directory")
        if directory.exists():
            shutil.rmtree(directory)

    def _prune_expired(self) -> None:
        """Called under the manager lock; never wait for or prune active work."""
        for session_id, persisted in self._owned_metadata().items():
            if session_id in self.pending:
                continue
            cached = self.sessions.get(session_id)
            metadata = cached.metadata if cached is not None else persisted
            if not self._expired(metadata) or (cached is not None and cached.active_requests):
                continue
            acquired = cached.lock.acquire(blocking=False) if cached is not None else True
            if not acquired:
                continue
            try:
                if cached is not None:
                    cached.close()
                    self.sessions.pop(session_id, None)
                self._remove_directory(session_id)
            finally:
                if cached is not None:
                    cached.lock.release()

    def _load(self, session_id: str | None) -> DemoSession:
        if not isinstance(session_id, str) or not ID_PATTERN.fullmatch(session_id):
            raise SessionMissing("No active browser session")
        if session_id in self.pending:
            raise SessionMissing("Session initialization is still running")
        if session_id in self.sessions:
            cached = self.sessions[session_id]
            if self._expired(cached.metadata) and not cached.active_requests:
                self._prune_expired()
                raise SessionMissing("Browser session expired; start a new demo")
            return cached
        path = self.directory / session_id / "session.json"
        if not path.is_file():
            raise SessionMissing("No active browser session")
        metadata = json.loads(path.read_text())
        if metadata.get("session_id") != session_id or not metadata.get("ready"):
            raise SessionMissing("Session initialization is incomplete")
        if self._expired(metadata):
            self._prune_expired()
            raise SessionMissing("Browser session expired; start a new demo")
        session = DemoSession(path.parent, metadata, self.graph_factory)
        self.sessions[session_id] = session
        return session

    @contextmanager
    def session(self, session_id: str | None):
        with self.lock:
            session = self._load(session_id)
            session.active_requests += 1
        # Do not hold the global lock while an earlier request in A is busy;
        # otherwise another request waiting for A also blocks independent B.
        session.lock.acquire()
        try:
            session.touch()
            yield session
        finally:
            try:
                session.touch()
            finally:
                session.lock.release()
                with self.lock:
                    session.active_requests -= 1

    def create_or_resume(self, session_id: str | None) -> tuple[str, dict]:
        if session_id:
            try:
                with self.session(session_id) as existing:
                    return existing.id, existing.state()
            except SessionMissing:
                pass
        with self.lock:
            self._prune_expired()
            if len(set(self._owned_metadata()) | self.pending) >= self.max_sessions:
                raise SessionCapacity("Demo session capacity reached; existing sessions can still resume or reset")
            new_id = uuid.uuid4().hex
            self.pending.add(new_id)
        session = None
        try:
            metadata = {"session_id": new_id, "generation": uuid.uuid4().hex,
                        "created_at": now(), "last_seen_unix": time.time(), "ready": False}
            session = DemoSession(self.directory / new_id, metadata, self.graph_factory)
            session.seed()
            state = session.state()
            session.touch()
            with self.lock:
                self.sessions[new_id] = session
                self.pending.remove(new_id)
            return new_id, state
        except Exception:
            if session is not None:
                session.close()
            with self.lock:
                self.pending.discard(new_id)
                self._remove_directory(new_id)
            raise

    def reset(self, session_id: str | None) -> dict:
        with self.session(session_id) as old:
            old.rate_limit()
            metadata = {"session_id": old.id, "generation": uuid.uuid4().hex,
                        "created_at": now(), "last_seen_unix": time.time(), "ready": False}
            fresh = DemoSession(old.directory, metadata, self.graph_factory)
            try:
                fresh.seed()
                state = fresh.state()
            except Exception:
                fresh.close()
                old.save()
                raise
            # Keep the reserved object/lock stable. Requests already waiting for
            # this session acquire it later and see the new generation safely.
            previous_store, previous_graph = old.store, old.graph
            old.store, old.graph, old.runtime = fresh.store, fresh.graph, fresh.runtime
            old.metadata, old.generation = fresh.metadata, fresh.generation
            previous_store.close()
            previous_graph.close()
            return state

    def close(self) -> None:
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            with session.lock:
                session.close()
