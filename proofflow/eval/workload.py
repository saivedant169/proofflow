"""Real runtime fixtures and information-equivalent evidence export."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3
from typing import Any

from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.models import ArtifactRecord
from proofflow.runtime import ProofFlowRuntime
from .cases import PERIODS, Recipe, Scenario, fixture_sources, heldout_recipe, mutate_value, recipes
from .retrieval import EvidenceRecord, RetrievalQuery


@dataclass
class Workload:
    runtime: ProofFlowRuntime
    sources: dict[str, Any]
    recipes: list[Recipe]
    refs: dict[str, ArtifactRecord]
    graph_namespace: str

    def close(self) -> None:
        self.runtime.store.close()
        self.runtime.graph.close()


def build_workload(directory: Path, *, additional_composition: bool = False, namespace_prefix: str = "pilot") -> Workload:
    store = ArtifactStore(directory)
    if store.heads():
        raise ValueError(f"A benchmark fixture must start with an empty store: {directory}")
    namespace = f"{namespace_prefix}-{store.workspace}"
    graph = HydraGraph(namespace=namespace)
    runtime = ProofFlowRuntime(store, graph)
    source_values = fixture_sources()
    refs = {}
    for name, value in source_values.items():
        change = runtime.set_source(name, value, f"Actual {name.split(':')[0]} input data for {name.split(':')[1]}")
        refs[f"source:{name}"] = store.get(change.current_id)
    declarations = [recipe for period in PERIODS for recipe in recipes(period)]
    if additional_composition:
        declarations.append(heldout_recipe())
    for recipe in declarations:
        refs[recipe.name] = runtime.execute(recipe.tool, {name: refs[key].id for name, key in recipe.inputs.items()},
                                            recipe.params, logical_id=f"artifact:{recipe.name}",
                                            run_id=f"{recipe.run}:{recipe.name.split(':')[0]}",
                                            description=recipe.description)
    return Workload(runtime, source_values, declarations, refs, namespace)


def apply_mutation(workload: Workload, scenario: Scenario) -> tuple[list[str], dict[str, Any]]:
    current_sources = deepcopy(workload.sources)
    changed = []
    for mutation in scenario.mutations:
        if mutation.operation == "tool_version":
            change = workload.runtime.set_tool_version(mutation.tool, f"pilot-{scenario.id}-2")
        elif mutation.operation == "remove":
            current_sources[mutation.source] = None
            change = workload.runtime.remove_source(mutation.source)
        else:
            value = mutate_value(current_sources[mutation.source], mutation)
            current_sources[mutation.source] = value
            change = workload.runtime.set_source(mutation.source, value,
                                                 f"Updated actual {mutation.source} source data")
        if not change.changed or change.previous_id is None:
            raise AssertionError(f"Scenario {scenario.id} did not change an existing version")
        changed.append(change.previous_id)
    return changed, current_sources


def evidence_alias(record: ArtifactRecord, store: ArtifactStore, memo: dict[str, str] | None = None) -> str:
    # Human-readable scope/name plus immutable suffix: all conditions see this
    # same alias. Raw IDs are retained outside context for exact execution.
    memo = {} if memo is None else memo
    if record.id in memo:
        return memo[record.id]
    signature: dict[str, Any] = {"logical_id": record.logical_id, "kind": record.kind,
                                 "content_hash": record.content_hash}
    if record.kind == "artifact":
        signature["inputs"] = {name: evidence_alias(store.get(key), store, memo)
                               for name, key in sorted(record.metadata["inputs"].items())}
        signature["tool"] = evidence_alias(store.get(record.metadata["tool_version_id"]), store, memo)
        signature["params"] = record.metadata["params"]
    encoded = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    alias = f"{record.logical_id}@{hashlib.sha256(encoded.encode()).hexdigest()[:12]}"
    memo[record.id] = alias
    return alias


def export_evidence(workload: Workload) -> tuple[list[EvidenceRecord], dict[str, str]]:
    store = workload.runtime.store
    aliases: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for record in store.list_records():
        if record.kind not in {"source", "tool", "artifact"}:
            continue
        alias = evidence_alias(record, store, aliases)
        if alias in reverse and reverse[alias] != record.id:
            raise ValueError("Evidence alias collision; benchmark refuses ambiguous IDs")
        aliases[record.id] = alias
        reverse[alias] = record.id
    documents = []
    for record in store.heads("artifact"):
        metadata = record.metadata
        direct_ids = list(metadata["inputs"].values())
        labels, versions = {}, {}
        for input_id in direct_ids:
            item = store.get(input_id)
            labels[aliases[input_id]] = item.logical_id
            head = store.get_head(item.logical_id)
            versions[aliases[input_id]] = aliases[head.id] if head else "unavailable"
        tool_id = metadata["tool_version_id"]
        tool = store.get(tool_id)
        tool_head = store.get_head(tool.logical_id)
        versions[aliases[tool_id]] = aliases[tool_head.id] if tool_head else "unavailable"
        documents.append(EvidenceRecord(
            id=aliases[record.id], title=metadata["title"], logical_id=record.logical_id,
            tool=metadata["tool"], inputs=tuple(aliases[key] for key in direct_ids),
            description=metadata["description"], tool_version_id=aliases[tool_id],
            parameters=metadata["params"], input_labels=labels,
            current_direct_versions=versions, result=store.read(record.id),
        ))
    return sorted(documents, key=lambda record: record.id), reverse


def scenario_query(workload: Workload, scenario: Scenario, changed_ids: list[str]) -> RetrievalQuery:
    roots = tuple(evidence_alias(workload.runtime.store.get(key), workload.runtime.store) for key in changed_ids)
    text = (scenario.description + "\nTask: identify saved calculation and report artifacts requiring revalidation. "
            "Requested periods: " + ", ".join(scenario.scope_periods) + ".")
    return RetrievalQuery(text, roots)


def in_scope(logical_id: str, scenario: Scenario) -> bool:
    return logical_id.startswith(tuple(f"artifact:{period}:" for period in scenario.scope_periods)) or logical_id.startswith("artifact:cross_period:")


def clone_runtime(workload: Workload, directory: Path) -> ProofFlowRuntime:
    """Copy local mutable heads; share only immutable graph history.

    All policies are ranked before any arm executes. Each clone has independent
    source/tool/artifact heads and new executions use unique immutable IDs.
    Currentness reads only ancestors, so another arm's appended descendants
    cannot enter this arm's evidence. No graph-discovery query is rerun after
    arms begin executing. This protocol avoids repeated fixture construction.
    """
    directory.mkdir(parents=True, exist_ok=False)
    shutil.copytree(workload.runtime.store.blobs, directory / "blobs")
    connection = sqlite3.connect(directory / "manifest.sqlite3")
    try:
        workload.runtime.store.db.backup(connection)
    finally:
        connection.close()
    return ProofFlowRuntime(ArtifactStore(directory), HydraGraph(namespace=workload.graph_namespace))
