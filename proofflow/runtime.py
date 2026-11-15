"""Execute typed tools, retain their actual lineage, and refresh current evidence.

The runtime has no fallback graph. The injected graph is consulted to validate
artifact reuse and discover affected descendants. Local metadata resolves the
content and recipes returned by that graph; it is not a replacement traversal.
"""
from __future__ import annotations

import hashlib
import threading
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, TYPE_CHECKING

from . import analytics
from .analytics import TOOL_SPECS, execute_tool
from .artifacts import ArtifactStore, digest
from .models import (ArtifactRecord, Currentness, DependencyCycleError,
                     InvalidInputError, MissingEvidenceError, RefreshResult, SourceChange)

if TYPE_CHECKING:
    from .graph import GraphPort


class ProofFlowRuntime:
    def __init__(self, store: ArtifactStore, graph: GraphPort):
        self.store = store
        self.graph = graph
        self._lock = threading.RLock()
        self.calls: list[dict[str, Any]] = []
        self._implementation_hash = hashlib.sha256(Path(analytics.__file__).read_bytes()).hexdigest()

    def _write_node(self, record: ArtifactRecord) -> None:
        self.graph.put_node(record.id, record.kind, {
            "logical_id": record.logical_id,
            "content_hash": record.content_hash,
            "created_at": record.created_at,
            **record.metadata,
        })

    def set_source(self, name: str, value: Any, description: str = "") -> SourceChange:
        if not isinstance(name, str) or not name.strip():
            raise InvalidInputError("A source must have a nonempty logical name")
        with self._lock:
            logical = f"source:{name}"
            previous = self.store.get_head(logical)
            record = self.store.prepare("source", logical, value, {
                "name": name, "title": name, "description": description or f"Source {name}",
                "deleted": False,
            })
            self._write_node(record)
            self.store.commit(record, value, head=True)
            return SourceChange(logical, previous.id if previous else None, record.id,
                                previous is None or previous.id != record.id)

    def remove_source(self, name: str) -> SourceChange:
        with self._lock:
            logical = f"source:{name}"
            previous = self.store.get_head(logical)
            if previous is None:
                raise MissingEvidenceError(f"Unknown source {name}")
            record = self.store.prepare("source", logical, None, {
                "name": name, "title": name, "description": f"Removed source {name}",
                "deleted": True,
            }, identity={"deleted": True})
            self._write_node(record)
            self.store.commit(record, None, head=True)
            return SourceChange(logical, previous.id, record.id, previous.id != record.id)

    def set_tool_version(self, tool: str, version: str) -> SourceChange:
        if tool not in TOOL_SPECS or not isinstance(version, str) or not version.strip():
            raise InvalidInputError("Expected a registered tool and nonempty version")
        with self._lock:
            logical = f"tool:{tool}"
            previous = self.store.get_head(logical)
            value = {"name": tool, "version": version, "implementation_hash": self._implementation_hash}
            record = self.store.prepare("tool", logical, value, {
                "name": tool, "title": tool, "version": version,
                "description": TOOL_SPECS[tool].description,
            })
            self._write_node(record)
            self.store.commit(record, value, head=True)
            return SourceChange(logical, previous.id if previous else None, record.id,
                                previous is None or previous.id != record.id)

    def _tool(self, tool: str) -> ArtifactRecord:
        if tool not in TOOL_SPECS:
            raise InvalidInputError(f"Unknown tool {tool!r}")
        record = self.store.get_head(f"tool:{tool}")
        if record is None:
            change = self.set_tool_version(tool, TOOL_SPECS[tool].version)
            return self.store.get(change.current_id)
        value = self.store.read(record.id)
        if value["implementation_hash"] != self._implementation_hash:
            change = self.set_tool_version(tool, value["version"])
            return self.store.get(change.current_id)
        return record

    def currentness(self, artifact_id: str) -> Currentness:
        """Validate graph-discovered dependencies, including missing receipt/blob checks."""
        with self._lock:
            record = self.store.get(artifact_id)
            ancestors = (self.graph.ancestors([artifact_id], max_depth=15)
                         if record.kind == "artifact" else [])
            discovered = set(ancestors) | {artifact_id}
            stale: list[dict[str, Any]] = []
            unknown: list[dict[str, Any]] = []
            for node_id in sorted(discovered):
                node = self.store.get(node_id, required=False)
                if node is None:
                    unknown.append({"id": node_id, "reason": "missing_manifest_record"})
                    continue
                stored_value = None
                try:
                    stored_value = self.store.read(node_id)
                except MissingEvidenceError as exc:
                    unknown.append({"id": node_id, "reason": "missing_or_corrupt_content", "detail": str(exc)})
                if node.kind in {"source", "tool"}:
                    head = self.store.get_head(node.logical_id)
                    if head is None or head.id != node.id:
                        stale.append({"id": node.id, "logical_id": node.logical_id,
                                      "current_id": head.id if head else None, "reason": "version_changed"})
                    if node.metadata.get("deleted"):
                        unknown.append({"id": node.id, "reason": "source_removed"})
                    if (node.kind == "tool" and isinstance(stored_value, dict)
                            and stored_value.get("implementation_hash") != self._implementation_hash):
                        stale.append({"id": node.id, "logical_id": node.logical_id,
                                      "reason": "implementation_changed"})
                if node.kind == "artifact":
                    expected = set(node.metadata["inputs"].values()) | {
                        node.metadata["receipt_id"], node.metadata["tool_version_id"]
                    }
                    missing = expected - discovered
                    if missing:
                        unknown.append({"id": node.id, "reason": "incomplete_graph_lineage",
                                        "missing": sorted(missing)})
            state = "unknown" if unknown else "stale" if stale else "current"
            return Currentness(artifact_id, state, tuple(unknown + stale))

    def _input_value(self, node_id: str) -> Any:
        record = self.store.get(node_id)
        if record.kind not in {"source", "artifact"}:
            raise InvalidInputError(f"A tool input must be a source or artifact, got {record.kind}")
        status = self.currentness(node_id)
        if not status.is_current:
            raise MissingEvidenceError(f"Input is {status.state}, refresh it first: {node_id}")
        return self.store.read(node_id)

    def execute(self, tool: str, inputs: dict[str, str], params: dict[str, Any] | None = None,
                *, logical_id: str | None = None, run_id: str | None = None,
                reuse: bool = True, description: str = "") -> ArtifactRecord:
        if not isinstance(inputs, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                   for k, v in inputs.items()):
            raise InvalidInputError("Tool inputs must map names to immutable record IDs")
        params = {} if params is None else params
        if not isinstance(params, dict):
            raise InvalidInputError("Tool parameters must be an object")
        with self._lock:
            tool_record = self._tool(tool)
            signature = {"tool_version_id": tool_record.id, "inputs": inputs, "params": params}
            logical = logical_id or f"artifact:{tool}:{digest(signature)[:20]}"
            if not isinstance(logical, str) or not logical.strip() or logical.startswith(("source:", "tool:", "execution:")):
                raise InvalidInputError("Artifact logical IDs must not use source, tool, or execution namespaces")
            head = self.store.get_head(logical)
            if head is not None and head.kind != "artifact":
                raise InvalidInputError("Artifact publication would replace a different kind of record")
            if reuse and head is not None and all(head.metadata.get(k) == v for k, v in signature.items()):
                if self.currentness(head.id).is_current:
                    return head
            values = {name: self._input_value(node_id) for name, node_id in inputs.items()}
            invocation_id = uuid.uuid4().hex
            run_id = run_id or f"run-{uuid.uuid4().hex}"
            started = time.perf_counter()
            call = {"tool": tool, "inputs": dict(inputs), "params": params, "run_id": run_id,
                    "invocation_id": invocation_id, "status": "running"}
            self.calls.append(call)
            try:
                result = execute_tool(tool, values, params)
            except Exception as exc:
                call.update(status="failed", error=str(exc), elapsed_ms=(time.perf_counter() - started) * 1000)
                raise
            elapsed_ms = (time.perf_counter() - started) * 1000
            output = self.store.prepare("artifact", logical, result, identity=invocation_id)
            receipt_value = {"tool": tool, "tool_version_id": tool_record.id,
                             "inputs": dict(inputs), "params": params, "run_id": run_id,
                             "output_id": output.id, "output_hash": output.content_hash,
                             "status": "success", "elapsed_ms": elapsed_ms}
            receipt = self.store.prepare("execution", f"execution:{invocation_id}", receipt_value, {
                "tool": tool, "title": f"Execute {tool}", "run_id": run_id,
                "description": TOOL_SPECS[tool].description,
            })
            output = replace(output, metadata={
                **signature, "tool": tool, "run_id": run_id, "receipt_id": receipt.id,
                "title": params.get("title", logical),
                "description": description or TOOL_SPECS[tool].description,
            })
            try:
                self._write_node(receipt)
                self._write_node(output)
                for node_id in sorted(set(inputs.values())):
                    self.graph.put_edge(node_id, receipt.id, "CONSUMED")
                self.graph.put_edge(tool_record.id, receipt.id, "USED_TOOL")
                self.graph.put_edge(receipt.id, output.id, "PRODUCED")
                self.store.commit(receipt, receipt_value)
                self.store.commit(output, result, head=True)
            except Exception as exc:
                call.update(status="unpublished", error=str(exc), elapsed_ms=elapsed_ms)
                raise
            call.update(status="success", output_id=output.id, elapsed_ms=elapsed_ms)
            return output

    def affected(self, changed_version_ids: list[str], *, current_only: bool = True) -> list[ArtifactRecord]:
        with self._lock:
            descendants = set(self.graph.descendants(changed_version_ids, max_depth=15))
            candidates = self.store.heads("artifact") if current_only else self.store.list_records("artifact")
            return sorted((record for record in candidates if record.id in descendants), key=lambda x: x.logical_id)

    def refresh(self, target_ids: list[str], *, run_id: str | None = None) -> RefreshResult:
        """Topological refresh with old→new input rebinding and shared-work deduplication."""
        with self._lock:
            started = time.perf_counter()
            run_id = run_id or f"refresh-{uuid.uuid4().hex}"
            replacements: dict[str, str] = {}
            executed: list[str] = []
            reused: list[str] = []
            visiting: set[str] = set()

            def visit(node_id: str) -> str:
                if node_id in replacements:
                    return replacements[node_id]
                if node_id in visiting:
                    raise DependencyCycleError(f"Dependency cycle at {node_id}")
                visiting.add(node_id)
                record = self.store.get(node_id)
                if record.kind == "source":
                    head = self.store.get_head(record.logical_id)
                    if head is None or head.metadata.get("deleted"):
                        raise MissingEvidenceError(f"Source no longer available: {record.logical_id}")
                    self.store.read(head.id)
                    replacements[node_id] = head.id
                elif record.kind == "artifact":
                    status = self.currentness(node_id)
                    if status.state == "unknown":
                        raise MissingEvidenceError(f"Cannot refresh incomplete evidence for {node_id}: {status.reasons}")
                    if status.is_current:
                        replacements[node_id] = node_id
                        reused.append(node_id)
                    else:
                        receipt = self.store.read(record.metadata["receipt_id"])
                        rebound = {name: visit(input_id) for name, input_id in receipt["inputs"].items()}
                        calls_before = len(self.calls)
                        output = self.execute(receipt["tool"], rebound, receipt["params"],
                                              logical_id=record.logical_id, run_id=run_id, reuse=True,
                                              description=record.metadata.get("description", ""))
                        replacements[node_id] = output.id
                        # Old handles remain stale after a prior refresh. execute()
                        # may resolve them to an already-current head without a
                        # tool call; report reuse rather than a fictitious rerun.
                        if len(self.calls) > calls_before:
                            executed.append(output.id)
                        else:
                            reused.append(output.id)
                else:
                    raise InvalidInputError(f"Cannot refresh a {record.kind} record")
                visiting.remove(node_id)
                return replacements[node_id]

            for target in target_ids:
                visit(target)
            return RefreshResult(replacements, tuple(executed), tuple(reused),
                                 (time.perf_counter() - started) * 1000)

    def full_recompute(self, target_id: str) -> Any:
        """Fresh recipe evaluation with no graph query and no cached intermediate values.

        This provides a workflow freshness oracle. It reuses the tool arithmetic;
        separate arithmetic tests or a second SQL calculation verify those tools.
        """
        with self._lock:
            visiting: set[str] = set()

            def compute(node_id: str) -> Any:
                if node_id in visiting:
                    raise DependencyCycleError(f"Dependency cycle at {node_id}")
                visiting.add(node_id)
                record = self.store.get(node_id)
                if record.kind == "source":
                    head = self.store.get_head(record.logical_id)
                    if head is None or head.metadata.get("deleted"):
                        raise MissingEvidenceError(f"Source no longer available: {record.logical_id}")
                    result = self.store.read(head.id)
                elif record.kind == "artifact":
                    receipt = self.store.read(record.metadata["receipt_id"])
                    values = {name: compute(child) for name, child in receipt["inputs"].items()}
                    result = execute_tool(receipt["tool"], values, receipt["params"])
                else:
                    raise InvalidInputError(f"Cannot recompute a {record.kind} record")
                visiting.remove(node_id)
                return result

            return compute(target_id)

    def context(self, target_ids: list[str]) -> dict[str, Any]:
        """Return current artifacts and explicit revalidation reasons for an agent."""
        with self._lock:
            items = []
            for target in target_ids:
                record = self.store.get(target)
                status = self.currentness(target)
                items.append({"artifact": record.to_dict(), "state": status.state,
                              "reasons": list(status.reasons),
                              "value": self.store.read(target) if status.is_current else None})
            return {"workspace": self.store.workspace, "items": items}

    def report_claims(self, report_id: str) -> list[dict[str, Any]]:
        """Inspect numeric slots separately, without serving a stale slot as current.

        A report can require refresh while its independent support section is
        still valid. The producing tool version is checked for every slot too.
        """
        with self._lock:
            record = self.store.get(report_id)
            if record.kind != "artifact" or record.metadata.get("tool") != "compose_report":
                raise InvalidInputError("Expected a structured report artifact")
            saved = self.store.read(report_id)
            by_key = {section["key"]: section for section in saved["sections"]}
            report_validation = self.currentness(report_id)
            formatting = self.currentness(record.metadata["tool_version_id"])
            claims = []
            for definition in record.metadata["params"]["sections"]:
                input_id = record.metadata["inputs"][definition["input"]]
                evidence = self.currentness(input_id)
                states = {evidence.state, formatting.state}
                if report_validation.state == "unknown":
                    states.add("unknown")
                state = "unknown" if "unknown" in states else "stale" if "stale" in states else "current"
                section = by_key[definition["key"]]
                claims.append({**section, "saved_value": section["value"],
                               "value": section["value"] if state == "current" else None,
                               "state": state, "artifact_id": input_id,
                               "path": definition["path"],
                               "reasons": list(evidence.reasons + formatting.reasons +
                                               (report_validation.reasons if report_validation.state == "unknown" else ()))})
            return claims
