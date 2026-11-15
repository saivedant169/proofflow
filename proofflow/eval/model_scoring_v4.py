"""Scorer-only independent endstate checks for the v4 model comparison."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

from proofflow import analytics
from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime
from .model_comparison_data import fixture_sources
from .model_comparison_oracle import (
    audit_provenance, compute_values, expected_affected_names, stage_sources,
)
from .retail_runner import execute_selection
from .workload import Workload


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")


def _snapshot(store: Any) -> dict[str, Any]:
    return {
        "records": {record.id: {**record.to_dict(), "value": store.read(record.id)}
                    for record in store.list_records()},
        **{f"{kind}_heads": {record.logical_id: record.id for record in store.heads(kind)}
           for kind in ("artifact", "source", "tool")},
    }


def _validate_anchor(anchor: dict[str, Any], observed: dict[str, Any]) -> None:
    records = anchor.get("records")
    if not isinstance(records, dict) or not records:
        raise ValueError("Frozen pre-execution anchor must contain every immutable record")
    if set(records) != set(observed["records"]):
        raise ValueError("Frozen pre-execution anchor record ID set differs from initial store")
    if _canonical(anchor) != _canonical(observed):
        raise ValueError("Frozen pre-execution anchor contents or heads differ from initial store")


def planned_report_counts(case_metadata: dict[str, Any]) -> dict[str, int]:
    """Derive fixed denominators even for unattempted cells, without a runtime."""
    declarations = [SimpleNamespace(**recipe) for recipe in case_metadata["recipes"]]
    sources = fixture_sources(case_metadata["split"])
    versions = {recipe.tool: "1" for recipe in declarations}
    changed_sources, changed_tools = set(), set()
    for mutation in case_metadata["scenario"]["mutations"]:
        staged = stage_sources(sources, [mutation])
        if mutation["operation"] == "tool_version":
            name, version = mutation["tool"], mutation["parameters"]["version"]
            if versions[name] != version:
                changed_tools.add(name)
            versions[name] = version
        elif _canonical(sources[mutation["source"]]) != _canonical(staged[mutation["source"]]):
            changed_sources.add(mutation["source"])
        sources = staged
    candidates = set(case_metadata["candidate_names"])
    if candidates != {recipe.name for recipe in declarations}:
        raise ValueError("Denominator scope differs from declared recipes")
    values, unavailable = compute_values(declarations, sources)
    affected = expected_affected_names(declarations, changed_sources, changed_tools, candidates)
    reports = {recipe.name for recipe in declarations if recipe.tool == "compose_report"}
    return {"reports": len(reports), "eligible_reports": len(reports & values.keys()),
            "eligible_affected_reports": len(reports & values.keys() & affected),
            "unavailable_reports": len(reports & unavailable.keys()),
            "unaffected_reports": len(reports - affected)}


def _expected_inputs(metadata: dict[str, Any], declarations: list[Any], anchor: dict[str, Any],
                     implementation_hash: str) -> tuple[dict, dict, set[str], set[str]]:
    """Derive changes from independent source staging, never native impact IDs."""
    sources = fixture_sources(metadata["split"])
    tools = {name: {"name": name, "version": "1", "implementation_hash": implementation_hash}
             for name in {recipe.tool for recipe in declarations}}
    mutations = metadata["scenario"]["mutations"]
    observations = metadata["mutation_audit"]
    if len(mutations) != len(observations):
        raise ValueError("Observed mutation history is incomplete")
    changed_sources, changed_tools, roots = set(), set(), []
    for mutation, observation in zip(mutations, observations, strict=True):
        is_tool = mutation["operation"] == "tool_version"
        name = mutation["tool"] if is_tool else mutation["source"]
        logical = ("tool:" if is_tool else "source:") + name
        before = deepcopy(tools[name] if is_tool else sources[name])
        # The independent implementation also validates tool declarations.
        staged = stage_sources(sources, [mutation])
        if is_tool:
            after = {**before, "version": mutation["parameters"]["version"]}
            tools[name] = after
        else:
            after = staged[name]
        sources = staged
        changed = _canonical(before) != _canonical(after)
        if not changed and not (metadata["category"] == "canonical_noop" and mutation["operation"] == "reorder"):
            raise ValueError("Unexpected no-op cannot alter the independent impact denominator")
        wanted = {"logical_id": logical, "kind": "tool" if is_tool else "source",
                  "expected_changed": changed, "observed_changed": changed,
                  "before_sha256": _sha(_canonical(before)), "after_sha256": _sha(_canonical(after)),
                  "deleted": not is_tool and after is None}
        if any(observation.get(key) != value for key, value in wanted.items()):
            raise ValueError("Observed mutation differs from the independently staged transition")
        old_id, new_id = observation["original_id"], observation["current_id"]
        if (old_id != new_id) != changed:
            raise ValueError("Observed mutation identity change differs from canonical value change")
        for identifier, expected_value in ((old_id, before), (new_id, after)):
            record = anchor["records"].get(identifier)
            if (not record or record.get("logical_id") != logical or record.get("kind") != wanted["kind"]
                    or _canonical(record.get("value")) != _canonical(expected_value)):
                raise ValueError("Mutation root does not resolve to the independently expected publication")
        if changed:
            roots.append(old_id)
            (changed_tools if is_tool else changed_sources).add(name)
    roots = list(dict.fromkeys(roots))
    if metadata["changed_raw_ids"] != roots:
        raise ValueError("Published changed roots differ from independent canonical transitions")
    aliases = metadata["alias_to_raw"]
    if [aliases.get(alias) for alias in metadata["query"]["changed_ids"]] != roots:
        raise ValueError("Model-visible change notifications differ from independent transition roots")
    return sources, tools, changed_sources, changed_tools


def aggregate_verified_outcome(
    execution: dict[str, Any], audit: dict[str, Any], post_snapshot: dict[str, Any],
    prior_snapshot: dict[str, Any], candidate_names: set[str], expected_names: set[str],
    expected_values: dict[str, Any], expected_errors: dict[str, str], report_names: set[str],
    unavailable_source_names: set[str],
) -> dict[str, Any]:
    """Pure full-scope aggregation; runtime claims alone never establish freshness."""
    if (not candidate_names or expected_values.keys() & expected_errors.keys()
            or candidate_names - (expected_values.keys() | expected_errors.keys())
            or not expected_names <= candidate_names or not report_names <= candidate_names):
        raise ValueError("Independent oracle and declared candidate scope are incomplete or inconsistent")
    errors = []
    anchor = prior_snapshot.get("records", {})
    global_valid = (audit.get("head_validation_pass") is True
                    and audit.get("immutable_anchor_provided") is True
                    and audit.get("immutable_anchor_pass") is True
                    and bool(anchor)
                    and audit.get("immutable_anchor_records") == len(anchor)
                    and audit.get("immutable_anchor_sha256") == _sha(_canonical(anchor)))
    if not global_valid:
        errors.append("Independent head or complete immutable-anchor validation failed")
    raw_items = execution.get("artifacts", [])
    items_by_name = {item["name"]: item for item in raw_items}
    if len(items_by_name) != len(raw_items) or set(items_by_name) != candidate_names:
        errors.append("Runtime inspection does not contain exactly the full candidate scope")
    if set(audit.get("artifacts", {})) != candidate_names:
        errors.append("Independent provenance audit does not contain exactly the full candidate scope")
    verified = []
    missing_reasons = {f"source_unavailable:source:{name.removeprefix('source:')}"
                       for name in unavailable_source_names}
    for name in sorted(candidate_names):
        runtime = items_by_name.get(name, {})
        provenance = audit.get("artifacts", {}).get(name, {})
        logical = f"artifact:{name}"
        head_id = post_snapshot.get("artifact_heads", {}).get(logical)
        record = post_snapshot.get("records", {}).get(head_id, {})
        original_id = prior_snapshot.get("artifact_heads", {}).get(logical)
        inspection_matches = (bool(head_id) and record.get("id") == head_id
                              and record.get("kind") == "artifact" and record.get("logical_id") == logical
                              and runtime.get("head_id") == provenance.get("head_id") == head_id
                              and runtime.get("head_content_hash") == record.get("content_hash")
                              and _canonical(runtime.get("actual_stored_value")) == _canonical(record.get("value"))
                              and "value" in record and "inspection_error" not in runtime)
        available = name in expected_values
        numeric_match = available and _canonical(record.get("value")) == _canonical(expected_values[name]) and "value" in record
        fresh = (global_valid and inspection_matches and available and numeric_match
                 and runtime.get("state") == "current" and provenance.get("provenance_current") is True)
        reasons = provenance.get("reasons", [])
        # Missing-source refusal may retain old valid receipts, but malformed
        # hashes/identities/ports/cycles/missing receipts must never pass as a block.
        permissible_missing_chain = (isinstance(reasons, list) and all(isinstance(reason, str) for reason in reasons)
            and bool(set(reasons) & missing_reasons)
            and all(reason in missing_reasons or reason.startswith(("source_version_stale:", "tool_version_stale:"))
                    for reason in reasons))
        blocked = (global_valid and inspection_matches and not available
                   and runtime.get("state") in {"stale", "unknown"}
                   and provenance.get("provenance_current") is False and permissible_missing_chain)
        preserved = bool(original_id) and head_id == original_id
        verified.append({"name": name, "is_report": name in report_names,
                         "expected_revalidation": name in expected_names, "oracle_available": available,
                         "head_id": head_id, "original_id": original_id,
                         "runtime_state": runtime.get("state", "uninspected"),
                         "numeric_match": numeric_match, "provenance_current": provenance.get("provenance_current"),
                         "provenance_reasons": reasons, "inspection_matches_snapshot": inspection_matches,
                         "fresh_complete": bool(fresh), "correctly_blocked": bool(blocked),
                         "preserved_original_artifact": preserved,
                         "incorrect_current": runtime.get("state") == "current" and not fresh})
    counts = {}
    for label, items in (("artifacts", verified), ("reports", [item for item in verified if item["is_report"]])):
        counts[f"verified_{label}_counts"] = {
            "total": len(items), "eligible": sum(item["oracle_available"] for item in items),
            "fresh": sum(item["fresh_complete"] for item in items),
            "eligible_affected": sum(item["oracle_available"] and item["expected_revalidation"] for item in items),
            "fresh_affected": sum(item["fresh_complete"] and item["expected_revalidation"] for item in items),
            "unavailable": sum(not item["oracle_available"] for item in items),
            "correctly_blocked": sum(item["correctly_blocked"] for item in items),
            "unaffected": sum(not item["expected_revalidation"] for item in items),
            "unaffected_artifacts_preserved": sum(not item["expected_revalidation"] and item["preserved_original_artifact"] for item in items),
            "incorrect_current": sum(item["incorrect_current"] for item in items),
        }
    execution_ok = not execution.get("unexpected_refresh_error", True) and not execution.get("inspection_errors", [])
    if not execution_ok:
        errors.append("Refresh or runtime inspection has an unexpected error")
    absolute = (global_valid and execution_ok and not errors
                and all(item["fresh_complete"] if item["oracle_available"] else item["correctly_blocked"] for item in verified)
                and all(item["preserved_original_artifact"] for item in verified if not item["expected_revalidation"]))
    return {**counts, "verified_artifacts": verified, "absolute_correct": bool(absolute),
            "semantic_endstate_correct": bool(absolute),
            "scoring_errors": errors, "independent_global_validation": global_valid}


def score_selection(case_metadata: dict[str, Any], selected_aliases: list[str],
                    output_directory: Path) -> dict[str, Any]:
    """Refresh in a private clone, then reopen and independently audit all heads."""
    started = time.perf_counter()
    output_directory = Path(output_directory)
    anchor_bytes = Path(case_metadata["initial_records_path"]).read_bytes()
    if _sha(anchor_bytes) != case_metadata["initial_records_sha256"]:
        raise ValueError("Frozen pre-execution snapshot file hash changed")
    anchor = json.loads(anchor_bytes)
    analytics_sha = _sha(Path(analytics.__file__).read_bytes())
    if analytics_sha != case_metadata["analytics_sha256"]:
        raise ValueError("Analytics implementation differs from the frozen tool contract")
    declarations = [SimpleNamespace(**recipe) for recipe in case_metadata["recipes"]]
    candidates = set(case_metadata["candidate_names"])
    if len(candidates) != len(case_metadata["candidate_names"]) or candidates != {recipe.name for recipe in declarations}:
        raise ValueError("Scoring scope must contain every declared artifact exactly once")
    sources, tools, changed_sources, changed_tools = _expected_inputs(case_metadata, declarations, anchor, analytics_sha)
    values, unavailable = compute_values(declarations, sources)
    affected = expected_affected_names(declarations, changed_sources, changed_tools, candidates)
    unavailable_sources = {name for name, value in sources.items() if value is None}
    store, graph = None, None
    try:
        if not (Path(case_metadata["initial_store_path"]) / "manifest.sqlite3").is_file():
            raise ValueError("Frozen initial store is missing")
        store = ArtifactStore(case_metadata["initial_store_path"])
        _validate_anchor(anchor, _snapshot(store))
        refs = {record.logical_id.removeprefix("artifact:"): record for record in store.heads("artifact")}
        if set(refs) != candidates:
            raise ValueError("Initial artifact heads differ from declared candidate scope")
        aliases = case_metadata["alias_to_raw"]
        if len(selected_aliases) != len(set(selected_aliases)):
            raise ValueError("Duplicate selected artifact aliases")
        for alias in selected_aliases:
            if alias not in aliases or aliases[alias] not in {record.id for record in refs.values()}:
                raise ValueError("Selected alias is not an initial candidate artifact")
        graph = HydraGraph(namespace=case_metadata["graph_namespace"])
        workload = Workload(ProofFlowRuntime(store, graph), sources, declarations, refs,
                            case_metadata["graph_namespace"])
        before_execution_ms = (time.perf_counter() - started) * 1000
        execution = execute_selection(workload, selected_aliases, aliases, candidates, affected,
                                      values, unavailable, output_directory,
                                      unavailable_source_names=unavailable_sources)
    finally:
        if store is not None:
            store.close()
        if graph is not None:
            graph.close()
    inspection_started = time.perf_counter()
    post_store = ArtifactStore(output_directory)
    try:
        post = _snapshot(post_store)
    finally:
        post_store.close()
    _write_json(output_directory / "post_snapshot.json", post)
    audit = audit_provenance(declarations, post["records"], post["artifact_heads"],
                             post["source_heads"], post["tool_heads"], sources, tools,
                             prior_records=deepcopy(anchor["records"]))
    _write_json(output_directory / "independent_audit.json", audit)
    result = aggregate_verified_outcome(execution, audit, post, anchor, candidates, affected,
                                        values, unavailable,
                                        {recipe.name for recipe in declarations if recipe.tool == "compose_report"},
                                        unavailable_sources)
    result.update(raw_execution=execution, expected_affected_names=sorted(affected),
                  post_snapshot_path=str(output_directory / "post_snapshot.json"),
                  independent_audit_path=str(output_directory / "independent_audit.json"),
                  post_snapshot_sha256=_sha((output_directory / "post_snapshot.json").read_bytes()),
                  independent_audit_sha256=_sha((output_directory / "independent_audit.json").read_bytes()),
                  before_execution_ms=before_execution_ms,
                  postinspection_ms=(time.perf_counter() - inspection_started) * 1000,
                  scoring_total_ms=(time.perf_counter() - started) * 1000)
    return result
