"""Local MCP access to actual imported sources and bounded analytics plans.

The MCP host chooses the plan. This process runs no model and accepts no paths,
code, SQL, credentials, or unregistered tools through its tool arguments.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable
import uuid

from .agent import ProviderResult
from .artifacts import ArtifactStore
from .composition import (COMPOSITION_SCHEMA, CompositionError, CompositionPlan,
                          CompositionRequest, execute_composition, make_request, validate_plan)
from .demo import atomic_json
from .graph import GraphError, HydraGraph
from .importing import MAX_BYTES, parse_csv
from .models import ProofFlowError
from .runtime import ProofFlowRuntime


WORKSPACE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
SNAPSHOT_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SNAPSHOT_TTL_SECONDS = 600
MAX_SNAPSHOTS = 32
MAX_SELECTED_ARTIFACTS = 16


class MCPInputError(ValueError):
    pass


class ProofFlowMCP:
    """Transport-independent bounded operations, all serialized per workspace."""

    def __init__(self, state_dir: str | Path, graph_factory: Callable[..., Any] = HydraGraph):
        self.directory = Path(state_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.graph_factory = graph_factory

    def _directory(self, workspace: str, *, create: bool = False) -> Path:
        if not isinstance(workspace, str) or not WORKSPACE_PATTERN.fullmatch(workspace):
            raise MCPInputError("Workspace must be 1–48 lowercase letters, digits or hyphens")
        directory = self.directory / workspace
        if directory.is_symlink():
            raise MCPInputError("Workspace cannot be a filesystem link")
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        elif not (directory / "manifest.sqlite3").is_file():
            raise MCPInputError("Unknown workspace; load a CSV first")
        return directory

    @contextmanager
    def _runtime(self, workspace: str, *, create: bool = False):
        directory = self._directory(workspace, create=create)
        with (directory / ".workspace.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise MCPInputError("Workspace is busy; retry after the current operation completes") from exc
            store = ArtifactStore(directory)
            try:
                with self.graph_factory(namespace=f"mcp-{store.workspace}") as graph:
                    yield ProofFlowRuntime(store, graph), directory
            finally:
                store.close()

    @staticmethod
    def _selected(runtime: ProofFlowRuntime, artifact_ids: list[str]) -> list[str]:
        if (not isinstance(artifact_ids, list) or not 1 <= len(artifact_ids) <= MAX_SELECTED_ARTIFACTS
                or not all(isinstance(value, str) and len(value) <= 300 for value in artifact_ids)
                or len(set(artifact_ids)) != len(artifact_ids)):
            raise MCPInputError("Select 1–16 distinct artifact IDs from this workspace")
        for artifact_id in artifact_ids:
            record = runtime.store.get(artifact_id, required=False)
            if record is None or record.kind != "artifact":
                raise MCPInputError("Unknown artifact in this workspace")
        return artifact_ids

    @staticmethod
    def _artifact(runtime: ProofFlowRuntime, artifact_id: str) -> dict[str, Any]:
        record = runtime.store.get(artifact_id)
        status = runtime.currentness(artifact_id)
        saved = runtime.store.read(artifact_id)
        return {**record.to_dict(), "state": status.state, "reasons": list(status.reasons),
                "value": saved if status.is_current else None, "saved_value": saved,
                "claims": runtime.report_claims(artifact_id)
                if record.metadata.get("tool") == "compose_report" else [],
                "receipt": runtime.store.read(record.metadata["receipt_id"])}

    @staticmethod
    def _sources(runtime: ProofFlowRuntime) -> list[dict[str, Any]]:
        return [{"id": record.id, "name": record.metadata["name"],
                 "content_sha256": record.content_hash,
                 "state": runtime.currentness(record.id).state}
                for record in runtime.store.heads("source")]

    @staticmethod
    def _support_regions(runtime: ProofFlowRuntime, request: CompositionRequest) -> dict[str, set[str]]:
        regions = {}
        for descriptor in request.descriptors:
            if descriptor["type"] not in {"tickets", "support_counts"}:
                continue
            value = runtime.store.read(request.handles[descriptor["handle"]])
            regions[descriptor["handle"]] = ({row["region"] for row in value}
                                              if descriptor["type"] == "tickets" else set(value["regions"]))
        return regions

    @classmethod
    def _validate_support_paths(cls, runtime: ProofFlowRuntime, request: CompositionRequest, plan: dict) -> None:
        # The seven-tool catalog aggregates existing ticket rows. It has no
        # known-region input with which to manufacture absent zero-count rows.
        # Reject that unsupported path before publishing any partial workflow.
        validate_plan(plan, request)
        regions = cls._support_regions(runtime, request)
        for step in plan["steps"]:
            bindings = {item["name"]: item["ref"] for item in step["inputs"]}
            if step["tool"] == "support_by_region":
                regions[step["id"]] = regions[bindings["tickets"]]
            elif step["tool"] == "compose_report":
                for section in step["sections"]:
                    if (section["unit"] == "tickets"
                            and section["path"][1] not in regions[bindings[section["input"]]]):
                        raise CompositionError("The current catalog cannot report an absent zero-ticket region; omit that support claim")

    def load_csv(self, workspace: str, csv_text: str, rates: dict[str, str] | None = None,
                 region: str | None = None) -> dict[str, Any]:
        """Publish caller-supplied CSV source versions; do not compose or refresh reports."""
        if not isinstance(csv_text, str) or len(csv_text) > MAX_BYTES:
            raise MCPInputError("CSV text must be at most 1 MiB of UTF-8")
        dataset = parse_csv(csv_text.encode("utf-8"), rates=rates, region=region)
        with self._runtime(workspace, create=True) as (runtime, _):
            changed = []
            for name, value in dataset.sources.items():
                change = runtime.set_source(name, value, "Caller-supplied CSV; FX explicitly supplied; ticket counts expanded")
                if change.changed and change.previous_id:
                    changed.append(change.previous_id)
            affected = runtime.affected(changed) if changed else []
            return {"workspace": workspace, "row_count": dataset.row_count,
                    "source_csv_sha256": dataset.content_sha256, "selected_region": dataset.region,
                    "source_versions": self._sources(runtime),
                    "changed_source_version_ids": changed,
                    "affected_artifact_ids": [record.id for record in affected],
                    "executed_count": 0, "hydra_queries": runtime.graph.queries,
                    "preflight_calculation_count": 8,
                    "execution_count_scope": "Recorded runtime tool calls; excludes eight CSV arithmetic validation calculations",
                    "ticket_semantics": "Counts expanded into synthetic counting rows, not original ticket IDs",
                    "atomicity": "Source heads publish individually; a database error is not a successful load"}

    def prepare(self, workspace: str, task: str) -> dict[str, Any]:
        """Read current typed handles and capture a snapshot for a client-chosen plan."""
        with self._runtime(workspace) as (runtime, directory):
            request = make_request(runtime, task)
            snapshots = directory / "snapshots"
            snapshots.mkdir(exist_ok=True)
            for path in snapshots.glob("*.json"):
                if path.is_symlink():
                    continue
                if time.time() - path.stat().st_mtime > SNAPSHOT_TTL_SECONDS:
                    path.unlink()
            if len(list(snapshots.glob("*.json"))) >= MAX_SNAPSHOTS:
                raise MCPInputError("Too many pending snapshots; execute one or wait ten minutes")
            token = uuid.uuid4().hex
            atomic_json(snapshots / f"{token}.json", {"created_unix": time.time(),
                        "request": asdict(request), "request_sha256": request.execution_sha256()})
            return {"workspace": workspace, "snapshot_token": token,
                    "request_sha256": request.execution_sha256(),
                    "request": json.loads(request.prompt()), "schema": COMPOSITION_SCHEMA,
                    "expires_in_seconds": SNAPSHOT_TTL_SECONDS,
                    "supported_ticket_regions": sorted(set().union(*self._support_regions(runtime, request).values())),
                    "support_limit": "Only regions with actual ticket rows have selectable support counts; absent zero-count regions are unsupported",
                    "planner": "External client chooses the plan; this server invokes no model"}

    def execute_plan(self, workspace: str, snapshot_token: str, plan: dict[str, Any],
                     run_id: str) -> dict[str, Any]:
        """Execute a complete 1–12-step plan using a captured immutable snapshot."""
        if not isinstance(snapshot_token, str) or not SNAPSHOT_PATTERN.fullmatch(snapshot_token):
            raise MCPInputError("Invalid snapshot token")
        if len(json.dumps(plan, allow_nan=False)) > 65536:
            raise MCPInputError("Plan exceeds 64 KiB")
        with self._runtime(workspace) as (runtime, directory):
            path = directory / "snapshots" / f"{snapshot_token}.json"
            if not path.is_file() or path.is_symlink():
                raise MCPInputError("Unknown or consumed snapshot; prepare again")
            saved = json.loads(path.read_text())
            if time.time() - saved["created_unix"] >= SNAPSHOT_TTL_SECONDS:
                path.unlink()
                raise MCPInputError("Snapshot expired; prepare again")
            data = saved["request"]
            request = CompositionRequest(data["task"], data["handles"], tuple(data["descriptors"]), tuple(data["regions"]))
            self._validate_support_paths(runtime, request, plan)
            wrapped = CompositionPlan(plan, saved["request_sha256"], ProviderResult(
                payload=plan, provider="external-mcp-client", model="unreported",
                metadata={"provenance": "Client-supplied plan; no model identity or usage verified by this server"}))
            result = execute_composition(runtime, request, wrapped, run_id=run_id)
            path.unlink()
            result.update(workspace=workspace, executed_count=len(runtime.calls),
                          hydra_queries=runtime.graph.queries,
                          planner={"provider": "external-mcp-client", "model": "unreported", "model_calls": 0})
            return result

    def inspect(self, workspace: str, artifact_ids: list[str] | None = None) -> dict[str, Any]:
        """Read actual source versions and evidence; stale current values are withheld."""
        with self._runtime(workspace) as (runtime, _):
            targets = (self._selected(runtime, artifact_ids) if artifact_ids is not None
                       else [record.id for record in runtime.store.heads("artifact")])
            return {"workspace": workspace, "sources": self._sources(runtime),
                    "artifacts": [self._artifact(runtime, artifact_id) for artifact_id in targets],
                    "hydra_queries": runtime.graph.queries, "fallback": False}

    def refresh(self, workspace: str, artifact_ids: list[str]) -> dict[str, Any]:
        """Refresh selected saved artifacts through native dependency evidence."""
        with self._runtime(workspace) as (runtime, _):
            self._selected(runtime, artifact_ids)
            result = runtime.refresh(artifact_ids)
            targets = list(dict.fromkeys(result.replacements[value] for value in artifact_ids))
            return {"workspace": workspace, "result": result.to_dict(),
                    "executed_count": len(runtime.calls), "tool_calls": runtime.calls,
                    "artifacts": [self._artifact(runtime, target) for target in targets],
                    "hydra_queries": runtime.graph.queries, "fallback": False}


def build_server(state_dir: str | Path | None = None):
    # Optional dependency: the ordinary API and benchmark do not require MCP.
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    facade = ProofFlowMCP(state_dir or os.environ.get("PROOFFLOW_MCP_STATE_DIR", ".state/mcp"))
    server = MCPServer("ProofFlow", log_level="WARNING", instructions=(
        "Use load_csv for actual data, prepare for typed contracts and a snapshot, then choose your own plan. "
        "execute_plan runs only registered analytics. inspect withholds stale current values; refresh revalidates. "
        "This local server invokes no model. Values marked saved_value are historical, not current claims. "
        "CSV loading performs eight arithmetic preflight checks; execution counters count recorded runtime tool calls."))

    def invoke(operation, *args):
        try:
            return operation(*args)
        except GraphError as exc:
            raise ToolError("HydraDB is unavailable or its evidence is incomplete; no fallback answer was served") from exc
        except (ValueError, ProofFlowError) as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    def load_csv(workspace: str, csv_text: str, rates: dict[str, str] | None = None,
                 region: str | None = None) -> dict[str, Any]:
        """Load a bounded CSV as sources without preset reports. Fields: order_id,region,currency,gross_cents; optional refund_cents,ticket_count. Rates map EUR/GBP to positive USD decimal strings. Workspace: 1–48 lowercase letters/digits/hyphens. Returns changed versions and native affected artifacts."""
        return invoke(facade.load_csv, workspace, csv_text, rates, region)

    @server.tool()
    def prepare(workspace: str, task: str) -> dict[str, Any]:
        """Return current typed handles, tool contracts and plan JSON schema for an analytics request; retain an immutable snapshot token for ten minutes. The caller chooses the plan."""
        return invoke(facade.prepare, workspace, task)

    @server.tool()
    def execute_plan(workspace: str, snapshot_token: str, plan: dict[str, Any], run_id: str) -> dict[str, Any]:
        """Validate and execute the client's bounded analytics plan against its snapshot; return calculated report claims, actual calls and provenance. Never accepts code or SQL."""
        return invoke(facade.execute_plan, workspace, snapshot_token, plan, run_id)

    @server.tool()
    def inspect(workspace: str, artifact_ids: list[str] | None = None) -> dict[str, Any]:
        """Read source versions and selected artifact receipts/currentness. Omit artifact_ids to list current artifact heads. Stale values are withheld from value; saved_value is historical."""
        return invoke(facade.inspect, workspace, artifact_ids)

    @server.tool()
    def refresh(workspace: str, artifact_ids: list[str]) -> dict[str, Any]:
        """Refresh 1–16 saved artifact IDs through actual Hydra dependencies; returns replacement IDs, receipts and actual tool-call count. No model, fallback retrieval or arbitrary execution."""
        return invoke(facade.refresh, workspace, artifact_ids)

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
