"""Retail-v2: predeclared production closure and matched-information controls.

This is a deterministic evidence-selection/actual-refresh experiment, not an
LLM evaluation. All arms use the same Hydra-assisted safety executor. Existing
pilot-v1 algorithms are imported without modification. Test execution requires
a committed matching freeze, explicit --allow-test, and --expected-revision.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any, Iterable

from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime
from .retrieval import (BM25Index, DenseEncoder, DenseIndex, RetrievalQuery,
                        TokenCounter, canonical, corpus_digest, exact_seed,
                        iterative_hybrid, pack_records, rank_exact_closure,
                        read_affected, render_context, score_sets)
from .workload import Workload, clone_runtime, evidence_alias, export_evidence


ROOT = Path(__file__).resolve().parents[2]
SHARED_EXECUTOR = ("Every arm uses Hydra-assisted currentness and recursive refresh; "
                   "standalone BM25/vector safety and LLM task success are not evaluated.")
RETAIL_CONFIG = {
    "benchmark_version": "retail-v2",
    "tokenizer": "cl100k_base",
    "dense_model": "BAAI/bge-small-en-v1.5",
    "dense_chunk_tokens": 384,
    "dense_chunk_overlap": 64,
    "dense_document_score": "maximum cosine across all overlapping chunks",
    "bm25": {"k1": 1.5, "b": 0.75},
    "rrf_constant": 60,
    "iterative_rounds": "corpus_size",
    "iterative_round_width": 3,
    "exact_id_seeding": True,
    "fixed_budget": 2048,
    "production_arms": ["graph", "exact_flat", "full_context"],
    "retrieval_arms": ["bm25", "dense", "iterative_hybrid"],
    "fixed_budget_closure_controls": ["graph", "exact_flat"],
    "budget_conditions": ["graph_matched", "fixed_2048"],
    "graph_matched_budget": "measured serialized unlimited graph closure tokens for this case; may be zero; adaptive diagnostic",
    "primary_ratio": "sum(graph evidence tokens) / sum(full_context evidence tokens) over every planned case",
    "primary_token_ratio_maximum": 0.4,
    "primary_correctness": "all planned cases; graph, exact_flat and full_context oracle-correct and equal semantic endstates for every scoped artifact; unexpected errors/incomplete runs fail",
    "expected_refusal": "one unchanged batch refresh; exact MissingEvidenceError naming an actually removed source may pass only if every available artifact is fresh+oracle-equal and every unavailable artifact blocks; refusal remains visible",
    "primary_closure": "each production arm must also identify the exact independently declared affected set; recursive repair cannot hide omitted closure evidence",
    "semantic_endstate": "logical artifact name, currentness state, stored JSON value, original artifact preservation; raw UUIDs excluded",
    "record_serialization": "unchanged EvidenceRecord.render/v1",
    "evidence_aliases": "unchanged deterministic logical/content/recipe/input-version aliases from pilot-v1",
    "reader": "unchanged deterministic transitive reader restricted to returned evidence",
    "change_oracle": "independently compare canonical source values and declared tool versions; assert observed transitions match; then use initial IDs for shared query roots",
    "shared_executor": SHARED_EXECUTOR,
    "execution_order": "rotate the predeclared arm list by SHA256(case_id) modulo its length",
    "dense_cache": "clear encoder passage/query memo at each case; model weights loaded once",
    "scope": "candidate scope applied equally before packing; independent dependency oracle closes full declarations before filtering",
    "claim_scope": "authored mutations and compositions over a frozen subset of public retail transactions; not independent observed production incidents",
}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def append_json(path: Path, value: Any) -> None:
    with path.open("a") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()


def failure(exc: Exception) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def code_hashes(root: Path = ROOT) -> dict[str, str]:
    # Include all executable application/evaluation code, not only this runner.
    paths = set((root / "proofflow").rglob("*.py"))
    paths.update((root / "scripts").rglob("*.py"))
    for name in ("pyproject.toml", "requirements.lock", "uv.lock"):
        if (root / name).is_file():
            paths.add(root / name)
    return {str(path.relative_to(root)): sha_file(path) for path in sorted(paths)}


def git_state(root: Path = ROOT) -> dict[str, Any]:
    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise ValueError(f"Cannot verify git freeze: git {' '.join(args)} failed")
        return result.stdout.strip()
    return {"revision": git("rev-parse", "HEAD"),
            "status_porcelain": git("status", "--porcelain", "--untracked-files=all")}


def embedding_identity(encoder: DenseEncoder) -> dict[str, Any]:
    data = encoder.metadata()
    return {key: value for key, value in data.items() if key not in {"cache_dir", "model_directory"}}


def manifest_payload(encoder: DenseEncoder) -> dict[str, Any]:
    from .retail_data import fixture_file_hashes, manifest_data
    return {"fixture": manifest_data(), "configuration": RETAIL_CONFIG,
            "code_sha256": code_hashes(), "source_files": fixture_file_hashes(),
            "embedding": embedding_identity(encoder),
            "protocol_sha256": sha_file(ROOT / "docs/RETAIL_V2_SPEC.md")}


def verify_manifest(path: Path, encoder: DenseEncoder) -> str:
    actual = json.loads(path.read_text())
    expected = manifest_payload(encoder)
    if canonical(actual) != canonical(expected):
        changed = [key for key in expected if canonical(actual.get(key)) != canonical(expected[key])]
        raise ValueError(f"Retail freeze differs from current inputs: {changed}; freeze and review before execution")
    # Also verify each declared byte hash rather than trusting a manifest helper.
    for item in actual["source_files"]:
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT.resolve()) or sha_file(source) != item["sha256"]:
            raise ValueError(f"Source file no longer matches its frozen checksum: {item['path']}")
    return sha_file(path)


def validate_test_gate(split: str, allow_test: bool, expected_revision: str | None,
                       state: dict[str, Any], selected_cases: list[str] | None) -> None:
    if split != "test":
        return
    if not allow_test or not expected_revision:
        raise ValueError("Held-out run requires explicit --allow-test and --expected-revision after parent approval")
    if state["revision"] != expected_revision:
        raise ValueError("Held-out revision differs from the explicitly approved frozen commit")
    if state["status_porcelain"]:
        raise ValueError("Held-out execution requires a clean git tree, including staged and untracked files")
    if selected_cases:
        raise ValueError("Held-out execution must include every planned case; --case is development-only")


def reserve_output(path: Path) -> None:
    # A previously attempted directory, even empty, is evidence of a prior run.
    path.mkdir(parents=True, exist_ok=False)


def build_retail_workload(directory: Path, split: str, case_id: str) -> Workload:
    from .retail_data import fixture_sources, recipes
    store = ArtifactStore(directory)
    if store.heads():
        store.close()
        raise ValueError("Retail fixture must start from an empty manifest")
    namespace = f"retail-v2-{case_id}-{store.workspace}"
    graph = HydraGraph(namespace=namespace)
    runtime = ProofFlowRuntime(store, graph)
    source_values = fixture_sources(split)
    refs = {}
    declarations = recipes(split)
    try:
        for name, value in source_values.items():
            change = runtime.set_source(name, value, f"Retail source partition {name}; frozen public transaction subset and declared auxiliary inputs")
            refs[f"source:{name}"] = store.get(change.current_id)
        for recipe in declarations:
            refs[recipe.name] = runtime.execute(
                recipe.tool, {name: refs[key].id for name, key in recipe.inputs.items()}, recipe.params,
                logical_id=f"artifact:{recipe.name}", run_id=recipe.run, description=recipe.description)
        return Workload(runtime, source_values, declarations, refs, namespace)
    except Exception:
        store.close()
        graph.close()
        raise


def mutate_workload(workload: Workload, case: Any) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    from .retail_data import mutate_value
    sources = deepcopy(workload.sources)
    changed_ids = []
    audit = []
    for mutation in case.mutations:
        logical = f"tool:{mutation.tool}" if mutation.operation == "tool_version" else f"source:{mutation.source}"
        previous = workload.runtime.store.get_head(logical)
        if previous is None:
            raise ValueError(f"Mutation has no initial version: {logical}")
        if mutation.operation == "tool_version":
            before = workload.runtime.store.read(previous.id)
            after = {**before, "version": mutation.parameters["version"]}
            expected_changed = canonical(before) != canonical(after)
            change = workload.runtime.set_tool_version(mutation.tool, after["version"])
        else:
            before = deepcopy(sources[mutation.source])
            after = mutate_value(before, mutation)
            expected_changed = canonical(before) != canonical(after)
            sources[mutation.source] = after
            change = (workload.runtime.remove_source(mutation.source) if mutation.operation == "remove" else
                      workload.runtime.set_source(mutation.source, after, f"Declared retail correction: {case.description}"))
        if not expected_changed and not (case.category == "canonical_noop" and mutation.operation == "reorder"):
            raise ValueError(f"Unexpected no-op in authored mutation: {mutation}")
        if change.changed != expected_changed or change.previous_id != previous.id:
            raise AssertionError(f"Runtime version-change observation disagrees with independent value comparison for {logical}")
        current = workload.runtime.store.get_head(logical)
        if current is None or current.id != change.current_id or (current.id != previous.id) != expected_changed:
            raise AssertionError(f"Runtime head publication disagrees with independently expected version change for {logical}")
        if canonical(workload.runtime.store.read(current.id)) != canonical(after):
            raise AssertionError(f"Runtime source/tool content differs from the declared new value for {logical}")
        audit.append({"logical_id": logical, "kind": "tool" if mutation.operation == "tool_version" else "source",
                      "expected_changed": expected_changed, "observed_changed": change.changed,
                      "original_id": previous.id, "current_id": current.id,
                      "before_sha256": hashlib.sha256(canonical(before).encode()).hexdigest(),
                      "after_sha256": hashlib.sha256(canonical(after).encode()).hexdigest()})
        if expected_changed:
            changed_ids.append(previous.id)
    return changed_ids, sources, audit


def semantic_endstates(execution: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: {"state": item["state"], "stored_value": item["actual_stored_value"],
                            "original_artifact_preserved": item["preserved_original_artifact"]}
            for item in execution.get("artifacts", [])}


def execute_selection(workload: Workload, selected_aliases: Iterable[str],
                      alias_to_raw: dict[str, str], candidate_names: set[str],
                      expected_names: set[str], expected_values: dict[str, Any],
                      expected_errors: dict[str, str], directory: Path,
                      unavailable_source_names: Iterable[str] = ()) -> dict[str, Any]:
    """One real refresh in private mutable heads, then forensic all-artifact scoring."""
    selected = list(dict.fromkeys(selected_aliases))
    if set(selected) - alias_to_raw.keys():
        raise ValueError("A policy selected identifiers outside its exported evidence")
    if expected_values.keys() & expected_errors.keys():
        raise ValueError("Oracle supplied both a value and an error for one artifact")
    if candidate_names - (expected_values.keys() | expected_errors.keys()):
        raise ValueError("Oracle omitted a scoped artifact")
    started = time.perf_counter()
    runtime = clone_runtime(workload, directory)
    clone_ms = (time.perf_counter() - started) * 1000
    result = {"selected_aliases": selected, "clone_ms": clone_ms, "refresh_result": None,
              "refresh_error": None, "inspection_errors": [], "artifacts": [], "serving_policy": SHARED_EXECUTOR}
    try:
        before_queries = runtime.graph.queries
        before_mutations = runtime.graph.mutations
        refresh_started = time.perf_counter()
        try:
            result["refresh_result"] = runtime.refresh([alias_to_raw[key] for key in selected]).to_dict()
        except Exception as exc:
            result["refresh_error"] = failure(exc)
        result["refresh_ms"] = (time.perf_counter() - refresh_started) * 1000
        result["refresh_graph_queries"] = runtime.graph.queries - before_queries
        result["refresh_graph_mutations"] = runtime.graph.mutations - before_mutations
        inspection_started = time.perf_counter()
        before_queries = runtime.graph.queries
        for name in sorted(candidate_names):
            original = workload.refs[name]
            item = {"name": name, "logical_id": original.logical_id,
                    "original_id": original.id, "original_content_hash": original.content_hash,
                    "expected_revalidation": name in expected_names,
                    "is_report": original.metadata["tool"] == "compose_report",
                    "oracle_available": name in expected_values,
                    "expected_value": expected_values.get(name), "expected_error": expected_errors.get(name),
                    "state": "error", "head_id": None, "head_content_hash": None,
                    "actual_stored_value": None, "currentness_reasons": [],
                    "fresh_complete": False, "correctly_blocked": False,
                    "preserved_original_artifact": False, "preserved_original_content": False}
            try:
                head = runtime.store.get_head(original.logical_id)
                if head is None:
                    raise ValueError(f"Artifact head disappeared: {original.logical_id}")
                currentness = runtime.currentness(head.id)
                value = runtime.store.read(head.id)  # Forensic only, not a stale-serving API.
                item.update(state=currentness.state, head_id=head.id, head_content_hash=head.content_hash,
                            actual_stored_value=value, currentness_reasons=list(currentness.reasons),
                            fresh_complete=(name in expected_values and currentness.is_current and value == expected_values[name]),
                            correctly_blocked=(name in expected_errors and currentness.state in {"stale", "unknown"}),
                            preserved_original_artifact=(head.id == original.id),
                            preserved_original_content=(head.content_hash == original.content_hash))
            except Exception as exc:
                item["inspection_error"] = failure(exc)
                result["inspection_errors"].append({"name": name, **failure(exc)})
            result["artifacts"].append(item)
        result["inspection_ms"] = (time.perf_counter() - inspection_started) * 1000
        result["inspection_graph_queries"] = runtime.graph.queries - before_queries
        result["calls"] = deepcopy(runtime.calls)
        result["tool_calls"] = len(runtime.calls)
        result["successful_tool_calls"] = sum(call.get("status") == "success" for call in runtime.calls)
        result["failed_tool_calls"] = sum(call.get("status") == "failed" for call in runtime.calls)
        for label, items in (("artifacts", result["artifacts"]),
                             ("reports", [item for item in result["artifacts"] if item["is_report"]])):
            eligible = [item for item in items if item["oracle_available"]]
            affected = [item for item in eligible if item["expected_revalidation"]]
            unavailable = [item for item in items if not item["oracle_available"]]
            unaffected = [item for item in items if not item["expected_revalidation"]]
            result[f"{label}_counts"] = {
                "total": len(items), "eligible": len(eligible),
                "fresh": sum(item["fresh_complete"] for item in eligible),
                "eligible_affected": len(affected), "fresh_affected": sum(item["fresh_complete"] for item in affected),
                "unavailable": len(unavailable), "correctly_blocked": sum(item["correctly_blocked"] for item in unavailable),
                "unaffected": len(unaffected), "unaffected_artifacts_preserved": sum(item["preserved_original_artifact"] for item in unaffected),
                "incorrect_current": sum(item["state"] == "current" and not item["fresh_complete"] for item in items),
            }
        # Classify only after execution; no oracle controls refresh routing. A
        # source-deletion refusal is legitimate iff every semantic obligation
        # also holds. Other missing evidence or graph failures remain failures.
        error = result["refresh_error"]
        allowed_messages = {f"Source no longer available: source:{name.removeprefix('source:')}"
                            for name in unavailable_source_names}
        expected_refusal = bool(error and error["type"] == "MissingEvidenceError"
                                and error["message"] in allowed_messages and expected_errors)
        result["refresh_completed"] = error is None
        result["expected_source_unavailable_refusal"] = expected_refusal
        result["unexpected_refresh_error"] = bool(error and not expected_refusal)
        result["oracle_correct"] = bool(candidate_names) and not result["unexpected_refresh_error"] and not result["inspection_errors"] and all(
            item["fresh_complete"] if item["oracle_available"] else item["correctly_blocked"]
            for item in result["artifacts"])
        result["execution_total_ms"] = (time.perf_counter() - started) * 1000
        result["semantic_endstate_sha256"] = hashlib.sha256(canonical(semantic_endstates(result)).encode()).hexdigest()
        return result
    finally:
        runtime.store.close()
        runtime.graph.close()


def compare_case(case_id: str, rows: list[dict[str, Any]], executions: list[dict[str, Any]]) -> dict[str, Any]:
    contexts = {row["arm"]: row for row in rows if row["condition"] == "unlimited"}
    outcomes = {row["arm"]: row for row in executions if row["condition"] == "unlimited"}
    required = set(RETAIL_CONFIG["production_arms"])
    complete = required <= contexts.keys() and required <= outcomes.keys()
    parity = complete and all(semantic_endstates(outcomes[arm]) == semantic_endstates(outcomes["full_context"])
                              for arm in required)
    correct = complete and all(outcomes[arm].get("oracle_correct", False) for arm in required)
    exact_closure = complete and all(contexts[arm]["impact"]["exact_match"] and not contexts[arm].get("graph_discovery_error")
                                    for arm in required)
    graph_tokens = contexts.get("graph", {}).get("context_tokens")
    full_tokens = contexts.get("full_context", {}).get("context_tokens")
    ratio = graph_tokens / full_tokens if graph_tokens is not None and full_tokens else None
    return {"scenario": case_id, "complete": complete, "oracle_correct": bool(correct),
            "production_endstate_parity": bool(parity),
            "exact_production_closures": bool(exact_closure),
            "production_correctness_pass": bool(correct and parity and exact_closure),
            "expected_affected_count": (contexts["graph"]["impact"]["tp"] + contexts["graph"]["impact"]["fn"] if "graph" in contexts else None),
            "graph_context_tokens": graph_tokens, "full_context_tokens": full_tokens,
            "graph_full_context_ratio": ratio}


def summarize(planned_ids: list[str], case_results: list[dict[str, Any]], rows: list[dict[str, Any]],
              executions: list[dict[str, Any]], *, partial: bool, integrity_verified: bool = True) -> dict[str, Any]:
    by_case = {value["scenario"]: value for value in case_results}
    complete = (not partial and set(by_case) == set(planned_ids)
                and all(value.get("complete", False) for value in by_case.values()))
    correctness = complete and all(value.get("production_correctness_pass", False) for value in by_case.values())
    tokens_available = set(by_case) == set(planned_ids) and all(
        value.get("graph_context_tokens") is not None and value.get("full_context_tokens") is not None
        for value in by_case.values())
    graph_sum = sum(value["graph_context_tokens"] for value in by_case.values()) if tokens_available else None
    full_sum = sum(value["full_context_tokens"] for value in by_case.values()) if tokens_available else None
    ratio = graph_sum / full_sum if full_sum else None
    per_case = [value["graph_full_context_ratio"] for value in by_case.values()
                if value.get("graph_full_context_ratio") is not None]
    nonempty = [value for value in by_case.values() if (value.get("expected_affected_count") or 0) > 0]
    nonempty_full = sum(value.get("full_context_tokens") or 0 for value in nonempty)
    nonempty_graph = sum(value.get("graph_context_tokens") or 0 for value in nonempty)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["arm"], row["condition"])].append(row)
    aggregates = []
    for (arm, condition), values in sorted(grouped.items()):
        observed = [item for item in executions if item["arm"] == arm and item["condition"] == condition]
        aggregates.append({"arm": arm, "condition": condition, "planned_cases": len(planned_ids),
                           "observed_retrieval_cases": len(values), "observed_execution_cases": len(observed),
                           "exact_affected_sets": sum(value["impact"]["exact_match"] for value in values),
                           "oracle_correct_cases": sum(item.get("oracle_correct", False) for item in observed),
                           "mean_recall_observed": sum(value["impact"]["recall"] for value in values) / len(values),
                           "mean_context_tokens_observed": sum(value["context_tokens"] for value in values) / len(values),
                           "total_tool_calls_observed": sum(item.get("tool_calls", 0) for item in observed),
                           "expected_source_refusals": sum(item.get("expected_source_unavailable_refusal", False) for item in observed),
                           "failures": sum(bool(item.get("unexpected_refresh_error") or item.get("error") or item.get("inspection_errors")) for item in observed)})
    return {"experiment": "retail-v2 deterministic retrieval and actual refresh", "planned_cases": planned_ids,
            "partial_run": partial, "complete_run": bool(complete), "case_results": case_results,
            "primary": {"correctness_pass": bool(correctness), "graph_context_tokens_total": graph_sum,
                        "full_context_tokens_total": full_sum, "ratio_of_total_tokens": ratio,
                        "mean_per_case_token_ratio": sum(per_case) / len(per_case) if len(per_case) == len(planned_ids) else None,
                        "prospective_threshold": RETAIL_CONFIG["primary_token_ratio_maximum"],
                        "freeze_integrity_verified": integrity_verified,
                        "passed": bool(integrity_verified and correctness and ratio is not None and ratio <= RETAIL_CONFIG["primary_token_ratio_maximum"])},
            "nonempty_impact_diagnostic": {"cases": len(nonempty),
                                          "ratio_of_total_tokens": nonempty_graph / nonempty_full if tokens_available and nonempty_full else None,
                                          "mean_per_case_ratio": (sum(value["graph_full_context_ratio"] for value in nonempty) / len(nonempty)
                                                                  if tokens_available and nonempty and all(value.get("graph_full_context_ratio") is not None for value in nonempty) else None)},
            "arms": aggregates,
            "limitations": [SHARED_EXECUTOR, RETAIL_CONFIG["claim_scope"],
                            "Adaptive graph-matched budget is a diagnostic; fixed 2048 is reported separately.",
                            "Full-context retrieval uses the same affected-evidence reader; it does not force recomputation of unaffected artifacts.",
                            "Evidence token savings are not total API dollar-cost savings; there are no LLM calls.",
                            "Selected-evidence reachability makes predictions subsets of the true closure on valid receipts; incomplete coverage is the main failure mode, not false stale answers.",
                            "Shared original immutable graph and independent manifests; all selections are frozen before any refresh.",
                            "Raw timings are single local observations, not randomized repeated latency estimates."]}


def run_case(case: Any, output: Path, encoder: DenseEncoder, counter: TokenCounter,
             manifest_sha: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from dataclasses import asdict
    from .retail_data import candidate_names as scope_candidates
    from .retail_oracle import compute_values, expected_affected_names
    case_started = time.perf_counter()
    directory = output / case.id
    directory.mkdir()
    fixture_started = time.perf_counter()
    workload = build_retail_workload(directory / "initial", case.split, case.id)
    fixture_ms = (time.perf_counter() - fixture_started) * 1000
    try:
        fixture_graph_queries = workload.runtime.graph.queries
        fixture_graph_mutations = workload.runtime.graph.mutations
        mutation_started = time.perf_counter()
        changed_ids, current_sources, mutation_audit = mutate_workload(workload, case)
        mutation_ms = (time.perf_counter() - mutation_started) * 1000
        mutation_queries = workload.runtime.graph.queries - fixture_graph_queries
        if case.restart:
            workload.close()
            workload.runtime = ProofFlowRuntime(ArtifactStore(directory / "initial"), HydraGraph(namespace=workload.graph_namespace))
        export_started = time.perf_counter()
        all_records, alias_to_raw = export_evidence(workload)
        candidates = set(scope_candidates(case, workload.recipes))
        records = [record for record in all_records if record.logical_id.removeprefix("artifact:") in candidates]
        if not records:
            raise ValueError("Candidate corpus is empty; zero affected closure is supported but empty corpus is not this task")
        by_id = {record.id: record for record in records}
        raw_to_alias = {raw: alias for alias, raw in alias_to_raw.items()}
        query = RetrievalQuery(case.description + "\nIdentify saved calculations and reports requiring revalidation. Requested partitions: " + ", ".join(case.scope_partitions) + ".",
                               tuple(evidence_alias(workload.runtime.store.get(key), workload.runtime.store) for key in changed_ids))
        export_ms = (time.perf_counter() - export_started) * 1000
        oracle_started = time.perf_counter()
        expected_names = expected_affected_names(workload.recipes,
            [entry["logical_id"].removeprefix("source:") for entry in mutation_audit if entry["kind"] == "source" and entry["expected_changed"]],
            [entry["logical_id"].removeprefix("tool:") for entry in mutation_audit if entry["kind"] == "tool" and entry["expected_changed"]], candidate_names=candidates)
        expected_values, expected_errors = compute_values(workload.recipes, current_sources)
        name_to_alias = {record.logical_id.removeprefix("artifact:"): record.id for record in records}
        expected_ids = {name_to_alias[name] for name in expected_names}
        for recipe in workload.recipes:
            if workload.refs[recipe.name].metadata["inputs"] != {key: workload.refs[name].id for key, name in recipe.inputs.items()}:
                raise ValueError(f"Runtime receipt differs from authored recipe: {recipe.name}")
        oracle_ms = (time.perf_counter() - oracle_started) * 1000
        # Native membership is scored, not substituted with the oracle on failure.
        graph_started = time.perf_counter()
        graph_before = workload.runtime.graph.queries
        graph_error = None
        try:
            actual_graph = workload.runtime.affected(changed_ids)
            graph_ids = {raw_to_alias[item.id] for item in actual_graph if raw_to_alias.get(item.id) in by_id}
            graph_rank = list(dict.fromkeys([*rank_exact_closure([by_id[key] for key in graph_ids], query.changed_ids), *sorted(graph_ids)]))
        except Exception as exc:
            graph_error, graph_rank = failure(exc), []
        graph_ms = (time.perf_counter() - graph_started) * 1000
        graph_discovery_ms = graph_ms
        graph_calls = workload.runtime.graph.queries - graph_before
        pack_started = time.perf_counter()
        graph_pack = pack_records([by_id[key] for key in graph_rank], None, counter)
        graph_ms += (time.perf_counter() - pack_started) * 1000
        graph_budget = graph_pack.tokens
        encoder.memo.clear()
        index_started = time.perf_counter()
        bm25 = BM25Index(records, **RETAIL_CONFIG["bm25"])
        bm25_index_ms = (time.perf_counter() - index_started) * 1000
        index_started = time.perf_counter()
        dense = DenseIndex(records, encoder)
        dense_index_ms = (time.perf_counter() - index_started) * 1000
        corpus_tokens = counter(render_context(records))
        ranking_times = {}
        rankings = {}
        for name, index in (("bm25", bm25), ("dense", dense)):
            started = time.perf_counter()
            rankings[name] = exact_seed(index.rank(query.render()), records, query.changed_ids)
            ranking_times[name] = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        flat_rank = rank_exact_closure(records, query.changed_ids)
        flat_discovery_ms = (time.perf_counter() - started) * 1000
        flat_pack = pack_records([by_id[key] for key in flat_rank], None, counter)
        flat_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        full_pack = pack_records(records, None, counter)
        full_ms = (time.perf_counter() - started) * 1000
        packs = {("graph", "unlimited"): graph_pack,
                 ("exact_flat", "unlimited"): flat_pack,
                 ("full_context", "unlimited"): full_pack}
        latencies = {("graph", "unlimited"): graph_ms, ("exact_flat", "unlimited"): flat_ms,
                     ("full_context", "unlimited"): full_ms}
        budgets = {"graph_matched": graph_budget, "fixed_2048": RETAIL_CONFIG["fixed_budget"]}
        for condition, budget in budgets.items():
            for arm in RETAIL_CONFIG["retrieval_arms"]:
                started = time.perf_counter()
                if arm == "iterative_hybrid":
                    pack = iterative_hybrid(records, query, bm25, dense, budget, counter, rounds=None,
                                            round_width=RETAIL_CONFIG["iterative_round_width"], constant=RETAIL_CONFIG["rrf_constant"])
                    latency = (time.perf_counter() - started) * 1000
                else:
                    pack = pack_records([by_id[key] for key in rankings[arm]], budget, counter)
                    latency = ranking_times[arm] + (time.perf_counter() - started) * 1000
                packs[(arm, condition)] = pack
                latencies[(arm, condition)] = latency
        for arm, ranking, discovery_ms in (("graph", graph_rank, graph_discovery_ms),
                                            ("exact_flat", flat_rank, flat_discovery_ms)):
            started = time.perf_counter()
            packs[(arm, "fixed_2048")] = pack_records([by_id[key] for key in ranking], RETAIL_CONFIG["fixed_budget"], counter)
            latencies[(arm, "fixed_2048")] = discovery_ms + (time.perf_counter() - started) * 1000
        # All contexts/reader decisions are now fixed; no discovery follows refresh.
        rows, predictions = [], {}
        for (arm, condition), packed in packs.items():
            started = time.perf_counter()
            prediction = read_affected(packed.records, query.changed_ids)
            reader_ms = (time.perf_counter() - started) * 1000
            predictions[(arm, condition)] = list(prediction)
            context = render_context(packed.records)
            row = {"scenario": case.id, "split": case.split, "category": case.category,
                   "arm": arm, "condition": condition, "budget": budgets.get(condition),
                   "context_tokens": packed.tokens, "query_tokens": counter(query.render()),
                   "corpus_tokens": corpus_tokens, "corpus_records": len(records),
                   "retrieved_ids": [item.id for item in packed.records], "predicted_ids": list(prediction),
                   "skipped_ids": packed.skipped_ids, "impact": score_sets(expected_ids, prediction),
                   "retrieval_ms": latencies[(arm, condition)], "reader_ms": reader_ms,
                   "hydra_discovery_queries": graph_calls if arm == "graph" else 0,
                   "search_index_calls": packed.retrieval_calls if arm in RETAIL_CONFIG["retrieval_arms"] else 0,
                   "graph_discovery_error": graph_error if arm == "graph" else None,
                   "corpus_sha256": corpus_digest(records), "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                   "fixture_manifest_sha256": manifest_sha}
            rows.append(row)
            append_json(output / "retrieval.jsonl", row)
            (directory / f"context-{arm}-{condition}.jsonl").write_text(context + ("\n" if context else ""))
        info = {"scenario": asdict(case), "query": {"text": query.text, "changed_ids": query.changed_ids},
                "candidate_names": sorted(candidates), "evidence": [json.loads(item.render()) for item in records],
                "alias_to_raw": alias_to_raw, "corpus_sha256": corpus_digest(records),
                "corpus_tokens": corpus_tokens, "corpus_records": len(records), "graph_namespace": workload.graph_namespace,
                "expected_affected_names": sorted(expected_names), "expected_affected_ids": sorted(expected_ids),
                "numeric_oracle_values": expected_values, "numeric_oracle_errors": expected_errors,
                "costs": {"fixture_ms": fixture_ms, "fixture_graph_queries": fixture_graph_queries,
                          "fixture_graph_mutations": fixture_graph_mutations, "mutation_ms": mutation_ms,
                          "mutation_graph_queries": mutation_queries, "export_ms": export_ms, "oracle_ms": oracle_ms,
                          "bm25_index_ms": bm25_index_ms, "dense_index_ms": dense_index_ms,
                          "graph_discovery_ms": graph_discovery_ms, "graph_budget_determination_ms": graph_ms,
                          "ranking_reuse": "one immutable ranking per base arm reused across budget diagnostics; graph-matched budget is a shared diagnostic parameter"},
                "embedding": {"document_tokens_maximum": max(dense.document_model_token_lengths), "chunks": dense.chunk_count},
                "graph_matched_budget": graph_budget, "graph_discovery_error": graph_error,
                "mutation_audit": mutation_audit,
                "native_graph_ids": sorted(graph_ids) if graph_error is None else [],
                "native_graph_impact": score_sets(expected_ids, graph_ids) if graph_error is None else None}
        write_json(directory / "case.json", info)
        arms = list(packs)
        offset = int(hashlib.sha256(case.id.encode()).hexdigest()[:8], 16) % len(arms)
        arms = arms[offset:] + arms[:offset]
        executions = []
        for arm, condition in arms:
            print(f"[{case.id}] refresh {arm}/{condition}", flush=True)
            started = time.perf_counter()
            try:
                execution = execute_selection(workload, predictions[(arm, condition)], alias_to_raw, candidates,
                                              expected_names, expected_values, expected_errors,
                                              directory / f"execute-{arm}-{condition}",
                                              unavailable_source_names=[name for name, value in current_sources.items() if value is None])
            except Exception as exc:
                execution = {"error": failure(exc), "oracle_correct": False, "execution_total_ms": (time.perf_counter() - started) * 1000}
            execution.update(scenario=case.id, split=case.split, arm=arm, condition=condition,
                             fixture_manifest_sha256=manifest_sha)
            if arm == "graph" and graph_error:
                execution.update(graph_discovery_error=graph_error, oracle_correct=False)
            index_ms = (bm25_index_ms if arm == "bm25" else dense_index_ms if arm == "dense"
                        else bm25_index_ms + dense_index_ms if arm == "iterative_hybrid" else 0.0)
            retrieval = next(row for row in rows if row["arm"] == arm and row["condition"] == condition)
            execution["costs"] = {"index_build_ms": index_ms, "retrieval_ms": retrieval["retrieval_ms"],
                                  "reader_ms": retrieval["reader_ms"],
                                  "warm_pipeline_ms": retrieval["retrieval_ms"] + retrieval["reader_ms"] + execution.get("refresh_ms", 0.0),
                                  "cold_index_pipeline_ms": index_ms + retrieval["retrieval_ms"] + retrieval["reader_ms"] + execution.get("refresh_ms", 0.0),
                                  "common_fixture_costs": info["costs"],
                                  "evaluation_clone_and_inspection_included_in_execution_total_only": True,
                                  "llm_calls": 0, "llm_dollars": 0,
                                  "shared_executor": SHARED_EXECUTOR}
            executions.append(execution)
            append_json(output / "execution.jsonl", execution)
        comparison = compare_case(case.id, rows, executions)
        info["case_total_ms"] = (time.perf_counter() - case_started) * 1000
        info["execution_order"] = arms
        info["comparison"] = comparison
        write_json(directory / "case.json", info)
        return rows, executions, comparison
    finally:
        workload.close()


def run(args: argparse.Namespace) -> None:
    from .retail_data import scenarios
    started = time.perf_counter()
    state = git_state()
    validate_test_gate(args.split, args.allow_test, args.expected_revision, state, args.case)
    embedding_started = time.perf_counter()
    encoder = DenseEncoder(RETAIL_CONFIG["dense_model"], args.model_cache)
    embedding_setup_ms = (time.perf_counter() - embedding_started) * 1000
    if args.write_manifest:
        if args.manifest.exists():
            raise ValueError("Refusing to overwrite an existing freeze manifest; use a distinct reviewed version")
        write_json(args.manifest, manifest_payload(encoder))
        print(f"Wrote {args.manifest}; SHA256 {sha_file(args.manifest)}", flush=True)
        return
    manifest_sha = verify_manifest(args.manifest, encoder)
    planned = scenarios(args.split)
    selected = [case for case in planned if not args.case or case.id in args.case]
    if not selected or (args.case and set(args.case) - {case.id for case in planned}):
        raise ValueError("Unknown or empty case selection")
    if args.output is None:
        raise ValueError("--output is required for evaluation")
    reserve_output(args.output)
    metadata = {"started_at": datetime.now(timezone.utc).isoformat(), "split": args.split,
                "planned_cases": [case.id for case in planned], "selected_cases": [case.id for case in selected],
                "partial_run": bool(args.case), "fixture_manifest_sha256": manifest_sha,
                "code": state, "configuration": RETAIL_CONFIG, "embedding": encoder.metadata(),
                "embedding_setup_ms": embedding_setup_ms,
                "database": "HydraDB OSS native FLOW traversal; no fallback",
                "shared_executor": SHARED_EXECUTOR,
                "isolation": "private manifest heads/blobs, shared immutable original graph; all selections frozen before arm executions",
                "finished": False}
    write_json(args.output / "run_manifest.json", metadata)
    counter = TokenCounter(RETAIL_CONFIG["tokenizer"])
    rows, executions, comparisons = [], [], []
    for case in selected:
        print(f"[{case.id}] fresh retail fixture", flush=True)
        try:
            case_rows, case_executions, comparison = run_case(case, args.output, encoder, counter, manifest_sha)
            rows.extend(case_rows)
            executions.extend(case_executions)
        except Exception as exc:
            comparison = {"scenario": case.id, "complete": False, "production_correctness_pass": False, "error": failure(exc)}
            append_json(args.output / "failures.jsonl", comparison)
            print(f"[{case.id}] FAILED: {type(exc).__name__}: {exc}", flush=True)
        comparisons.append(comparison)
        write_json(args.output / "summary.json", summarize([case.id for case in planned], comparisons, rows, executions, partial=bool(args.case), integrity_verified=False))
    integrity_error = None
    try:
        if verify_manifest(args.manifest, encoder) != manifest_sha:
            raise ValueError("Freeze manifest itself changed during execution")
    except Exception as exc:
        integrity_error = failure(exc)
    metadata.update(finished=True, finished_at=datetime.now(timezone.utc).isoformat(),
                    elapsed_ms=(time.perf_counter() - started) * 1000,
                    end_code_sha256=code_hashes(), freeze_integrity_error=integrity_error)
    write_json(args.output / "run_manifest.json", metadata)
    summary = summarize([case.id for case in planned], comparisons, rows, executions, partial=bool(args.case), integrity_verified=integrity_error is None)
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary["primary"], indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/RETAIL_BENCHMARK_MANIFEST.json")
    parser.add_argument("--model-cache", type=Path, default=ROOT / ".cache/fastembed")
    parser.add_argument("--write-manifest", action="store_true", help="Write a NEW freeze file without running cases")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--expected-revision")
    parser.add_argument("--case", action="append", help="Development-only partial case selection")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
