"""Freeze six information-equivalent v4 requests without model or refresh calls.

The parent harness owns split/revision authorization and the two-development-run
limit. This module performs work only when prepare_case is explicitly called.
It uses production execution to seed a fixture, but never refreshes a selection
or imports a numeric/provenance oracle.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Iterable, Sequence

from proofflow.agent import AgentRequest, PLAN_SCHEMA, SYSTEM_PROMPT
from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime
from .config import DEFAULT_CONFIG
from .retrieval import (BM25Index, DenseEncoder, DenseIndex, EvidenceRecord,
                        RetrievalQuery, TokenCounter, canonical, corpus_digest,
                        exact_seed, iterative_hybrid, pack_records,
                        rank_exact_closure, render_context)
from .workload import Workload, evidence_alias, export_evidence


ARMS = ("graph", "exact_flat", "bm25", "dense", "iterative_hybrid", "full_context")
RETRIEVAL_CONFIG = {
    "record_serialization": DEFAULT_CONFIG["record_serialization"],
    "tokenizer": DEFAULT_CONFIG["tokenizer"],
    "dense_model": DEFAULT_CONFIG["dense_model"],
    "dense_chunk_tokens": DEFAULT_CONFIG["dense_chunk_tokens"],
    "dense_chunk_overlap": DEFAULT_CONFIG["dense_chunk_overlap"],
    "dense_document_score": DEFAULT_CONFIG["dense_document_score"],
    "bm25": dict(DEFAULT_CONFIG["bm25"]),
    "rrf_constant": DEFAULT_CONFIG["rrf_constant"],
    "iterative_rounds": DEFAULT_CONFIG["iterative_rounds"],
    "iterative_round_width": DEFAULT_CONFIG["iterative_round_width"],
    "exact_id_seeding": True,
    "evidence_budget": "complete native graph closure token count shared by five capped arms; full context uncapped",
}


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _build_workload(directory: Path, case: Any) -> Workload:
    from .model_comparison_data import fixture_sources, recipes

    store = ArtifactStore(directory)
    graph = None
    try:
        if store.heads():
            raise ValueError("A v4 fixture must start from an empty artifact store")
        namespace = f"model-v4-{case.id}-{store.workspace}"
        graph = HydraGraph(namespace=namespace)
        runtime = ProofFlowRuntime(store, graph)
        sources, declarations, refs = fixture_sources(case.split), recipes(case.split), {}
        for name, value in sources.items():
            change = runtime.set_source(name, value, f"Declared complete daily input: {name}")
            refs[f"source:{name}"] = store.get(change.current_id)
        for recipe in declarations:
            refs[recipe.name] = runtime.execute(
                recipe.tool, {port: refs[name].id for port, name in recipe.inputs.items()},
                recipe.params, logical_id=f"artifact:{recipe.name}", run_id=recipe.run,
                description=recipe.description)
        return Workload(runtime, sources, declarations, refs, namespace)
    except Exception:
        store.close()
        if graph is not None:
            graph.close()
        raise


def audit_and_apply_mutations(workload: Workload, case: Any) -> tuple[list[str], dict[str, Any], list[dict[str, Any]]]:
    """Independently predict value transitions before observing runtime flags."""
    from .model_comparison_data import mutate_value

    sources, roots, audit = deepcopy(workload.sources), [], []
    for mutation in case.mutations:
        is_tool = mutation.operation == "tool_version"
        logical = f"tool:{mutation.tool}" if is_tool else f"source:{mutation.source}"
        previous = workload.runtime.store.get_head(logical)
        if previous is None:
            raise ValueError(f"Mutation has no existing source/tool head: {logical}")
        if is_tool:
            before = workload.runtime.store.read(previous.id)
            after = {**before, "version": mutation.parameters["version"]}
        else:
            before = deepcopy(sources[mutation.source])
            after = mutate_value(before, mutation)
        expected_changed = canonical(before) != canonical(after)
        if not expected_changed and not (case.category == "canonical_noop" and mutation.operation == "reorder"):
            raise ValueError("An undeclared no-op cannot become an empty impact label")

        if is_tool:
            change = workload.runtime.set_tool_version(mutation.tool, after["version"])
        elif mutation.operation == "remove":
            change = workload.runtime.remove_source(mutation.source)
        else:
            change = workload.runtime.set_source(mutation.source, after, case.description)
        if not is_tool:
            sources[mutation.source] = after

        current = workload.runtime.store.get_head(logical)
        if (change.changed != expected_changed or change.previous_id != previous.id or
                current is None or current.id != change.current_id or
                (current.id != previous.id) != expected_changed):
            raise AssertionError(f"Runtime transition disagrees with independent canonical comparison: {logical}")
        if canonical(workload.runtime.store.read(current.id)) != canonical(after):
            raise AssertionError(f"Published input differs from the declared mutation: {logical}")
        audit.append({"logical_id": logical, "kind": "tool" if is_tool else "source",
                      "expected_changed": expected_changed, "observed_changed": change.changed,
                      "original_id": previous.id, "current_id": current.id,
                      "deleted": bool(current.metadata.get("deleted")),
                      "before_sha256": _sha(canonical(before)), "after_sha256": _sha(canonical(after))})
        if expected_changed:
            roots.append(previous.id)
    return list(dict.fromkeys(roots)), sources, audit


def _snapshot_records(store: ArtifactStore) -> dict[str, Any]:
    """Observed pre-execution anchor; this scorer-only sidecar never enters a request."""
    records = {record.id: {**record.to_dict(), "value": store.read(record.id)}
               for record in store.list_records()}
    return {"records": records,
            **{f"{kind}_heads": {record.logical_id: record.id for record in store.heads(kind)}
               for kind in ("artifact", "source", "tool")}}


def prepare_evidence_requests(
    records: Sequence[EvidenceRecord], query: RetrievalQuery, native_graph_ids: Iterable[str],
    encoder: DenseEncoder, counter: TokenCounter,
) -> tuple[dict[str, AgentRequest], dict[str, Any]]:
    """Pure corpus/index preparation: no model, runtime, output score or oracle."""
    records = sorted(records, key=lambda record: record.id)
    if not records:
        raise ValueError("An empty affected closure is valid, but this study requires a nonempty candidate corpus")
    by_id = {record.id: record for record in records}
    if len(by_id) != len(records):
        raise ValueError("Duplicate candidate artifact IDs")
    native = set(native_graph_ids)
    if native - by_id.keys():
        raise ValueError("Native graph returned an artifact outside the common candidate scope")

    started = time.perf_counter()
    graph_rank = list(dict.fromkeys([
        *rank_exact_closure([by_id[key] for key in native], query.changed_ids), *sorted(native)]))
    graph_pack = pack_records([by_id[key] for key in graph_rank], None, counter)
    graph_order_pack_ms = (time.perf_counter() - started) * 1000
    budget = graph_pack.tokens

    # No cross-case document/query memo advantage is hidden in indexing time.
    encoder.memo.clear()
    started = time.perf_counter()
    bm25 = BM25Index(records, **RETRIEVAL_CONFIG["bm25"])
    bm25_index_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    dense = DenseIndex(records, encoder)
    dense_index_ms = (time.perf_counter() - started) * 1000
    packs, elapsed = {"graph": graph_pack}, {"graph": graph_order_pack_ms}

    started = time.perf_counter()
    flat_rank = rank_exact_closure(records, query.changed_ids)
    packs["exact_flat"] = pack_records([by_id[key] for key in flat_rank], budget, counter)
    elapsed["exact_flat"] = (time.perf_counter() - started) * 1000
    for arm, index in (("bm25", bm25), ("dense", dense)):
        started = time.perf_counter()
        ranking = exact_seed(index.rank(query.render()), records, query.changed_ids)
        packs[arm] = pack_records([by_id[key] for key in ranking], budget, counter)
        elapsed[arm] = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    packs["iterative_hybrid"] = iterative_hybrid(
        records, query, bm25, dense, budget, counter, rounds=None,
        round_width=RETRIEVAL_CONFIG["iterative_round_width"], constant=RETRIEVAL_CONFIG["rrf_constant"])
    elapsed["iterative_hybrid"] = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    packs["full_context"] = pack_records(records, None, counter)
    elapsed["full_context"] = (time.perf_counter() - started) * 1000

    requests, summaries = {}, {}
    for arm in ARMS:
        packed = packs[arm]
        context = render_context(packed.records)
        if counter(context) != packed.tokens or (arm != "full_context" and packed.tokens > budget):
            raise AssertionError("Shared evidence packing violated its exact token allowance")
        request = AgentRequest(query.text, query.changed_ids, context, tuple(record.id for record in packed.records))
        request.validate()
        requests[arm] = request
        summaries[arm] = {"arm": arm, "evidence_budget": None if arm == "full_context" else budget,
                          "evidence_tokens": packed.tokens, "record_count": len(packed.records),
                          "retrieved_ids": list(request.allowed_artifact_ids), "skipped_ids": packed.skipped_ids,
                          "context_sha256": _sha(context), "request_sha256": _sha(request.prompt()),
                          "request_text_tokens_cl100k": counter(request.prompt()),
                          "known_prompt_components_tokens_cl100k": counter(SYSTEM_PROMPT + "\n" + canonical(PLAN_SCHEMA) + "\n" + request.prompt()),
                          "retrieval_ms_excluding_native_discovery": elapsed[arm],
                          "search_index_calls": packed.retrieval_calls if arm in {"bm25", "dense", "iterative_hybrid"} else 0}
    metadata = {"configuration": RETRIEVAL_CONFIG, "evidence_allowance": budget,
                "corpus_records": len(records), "corpus_tokens": counter(render_context(records)),
                "corpus_sha256": corpus_digest(records), "query_text_tokens_cl100k": counter(query.render()),
                "native_graph_ids": sorted(native), "exact_flat_ids": flat_rank,
                "native_flat_membership_equal": native == set(flat_rank),
                "graph_exact_flat_prompt_hashes_match": summaries["graph"]["request_sha256"] == summaries["exact_flat"]["request_sha256"],
                "index_metrics": {"bm25_build_ms": bm25_index_ms, "dense_build_ms": dense_index_ms,
                                  "dense_document_tokens_maximum": max(dense.document_model_token_lengths),
                                  "dense_chunks": dense.chunk_count, "dense_memo_cleared_before_case": True},
                "requests_by_arm": summaries,
                "token_accounting": "Evidence allowance counts original JSONL only; request/schema/system estimates are separate and are not provider usage."}
    return requests, metadata


def prepare_case(directory: str | Path, case: Any, encoder: DenseEncoder, counter: TokenCounter) -> dict[str, Any]:
    """Seed, mutate and freeze six requests; caller must authorize the split first."""
    from .model_comparison_data import candidate_names, manifest_data

    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    _write_json(directory / "preparation_started.json", {"case": case.id, "split": case.split,
                                                       "started_at": datetime.now(timezone.utc).isoformat()})
    workload = None
    try:
        fixture = manifest_data(case.split)
        query_text = fixture["queries_by_case"][case.id]
        if query_text != case.description:
            raise ValueError("Case description differs from its frozen query text")
        before = time.perf_counter()
        workload = _build_workload(directory / "initial", case)
        fixture_ms = (time.perf_counter() - before) * 1000
        fixture_graph_queries = workload.runtime.graph.queries
        fixture_graph_mutations = workload.runtime.graph.mutations
        before = time.perf_counter()
        changed_raw, current_sources, mutation_audit = audit_and_apply_mutations(workload, case)
        mutation_ms = (time.perf_counter() - before) * 1000
        mutation_graph_queries = workload.runtime.graph.queries - fixture_graph_queries
        all_records, alias_to_raw = export_evidence(workload)
        candidates = set(candidate_names(case, workload.recipes))
        records = [record for record in all_records if record.logical_id.removeprefix("artifact:") in candidates]
        observed_candidates = {record.logical_id.removeprefix("artifact:") for record in records}
        if observed_candidates != candidates:
            raise ValueError("Saved candidate heads differ from the declared common scope")
        raw_to_alias = {raw: alias for alias, raw in alias_to_raw.items()}
        query = RetrievalQuery(query_text, tuple(evidence_alias(workload.runtime.store.get(key), workload.runtime.store)
                                                 for key in changed_raw))
        before, queries_before = time.perf_counter(), workload.runtime.graph.queries
        # Propagate native failures to the parent. Never replace an unavailable
        # graph with a gold set, flat traversal, or an empty synthetic closure.
        native_records = workload.runtime.affected(changed_raw)
        native_ms = (time.perf_counter() - before) * 1000
        native_queries = workload.runtime.graph.queries - queries_before
        native_ids = {raw_to_alias[record.id] for record in native_records
                      if record.logical_id.removeprefix("artifact:") in candidates}
        requests, retrieval = prepare_evidence_requests(records, query, native_ids, encoder, counter)

        _write_json(directory / "current_sources.json", current_sources)
        _write_json(directory / "initial_records.json", _snapshot_records(workload.runtime.store))
        corpus = render_context(records)
        (directory / "corpus.jsonl").write_text(corpus + "\n")
        for arm, request in requests.items():
            arm_directory = directory / "requests" / arm
            request_path = arm_directory / "request.json"
            _write_json(request_path, asdict(request))
            context_path = arm_directory / "context.jsonl"
            context_path.write_text(request.context_text + ("\n" if request.context_text else ""))
            prompt_path = arm_directory / "prompt.txt"
            prompt_path.write_text(request.prompt())
            retrieval["requests_by_arm"][arm].update(
                request_path=str(request_path), request_file_sha256=_sha(request_path.read_bytes()),
                context_path=str(context_path), context_file_sha256=_sha(context_path.read_bytes()),
                prompt_path=str(prompt_path), prompt_file_sha256=_sha(prompt_path.read_bytes()),
                native_discovery_queries=native_queries if arm == "graph" else 0,
                retrieval_ms=(retrieval["requests_by_arm"][arm]["retrieval_ms_excluding_native_discovery"]
                              + (native_ms if arm == "graph" else 0.0)))
        recipes = [asdict(recipe) for recipe in workload.recipes]
        graph_namespace = workload.graph_namespace
        seed_tool_calls = len(workload.runtime.calls)
        workload.close()
        workload = None
        metadata = {"version": "model-contexts-v4", "scenario": asdict(case), "case_id": case.id,
                    "split": case.split, "category": case.category, "case_path": str(directory / "case.json"),
                    "analytics_sha256": _sha((Path(__file__).resolve().parents[1] / "analytics.py").read_bytes()),
                    "initial_store_path": str(directory / "initial"), "graph_namespace": graph_namespace,
                    "source_values_path": str(directory / "current_sources.json"),
                    "initial_records_path": str(directory / "initial_records.json"),
                    "initial_records_sha256": _sha((directory / "initial_records.json").read_bytes()),
                    "source_values_sha256": _sha((directory / "current_sources.json").read_bytes()),
                    "manifest_sqlite_sha256": _sha((directory / "initial/manifest.sqlite3").read_bytes()),
                    "corpus_path": str(directory / "corpus.jsonl"),
                    "recipes": recipes, "candidate_names": sorted(candidates), "alias_to_raw": alias_to_raw,
                    "query": {"text": query.text, "changed_ids": list(query.changed_ids)},
                    "changed_raw_ids": changed_raw, "mutation_audit": mutation_audit,
                    "fixture_sha256": _sha(canonical(fixture)),
                    "costs": {"fixture_ms": fixture_ms, "fixture_graph_queries": fixture_graph_queries,
                              "fixture_graph_mutations": fixture_graph_mutations, "seed_tool_calls": seed_tool_calls,
                              "mutation_ms": mutation_ms, "mutation_graph_queries": mutation_graph_queries,
                              "native_discovery_ms": native_ms, "native_discovery_queries": native_queries,
                              "total_prepare_ms": (time.perf_counter() - started) * 1000},
                    **retrieval,
                    "provider_calls": 0, "refresh_calls": 0,
                    "selection_boundary": "Request files contain task, observed changed aliases, selected full-v2 evidence and locally validated allowed IDs only; no oracle outputs or plans."}
        _write_json(directory / "case.json", metadata)
        return metadata
    except Exception as exc:
        _write_json(directory / "preparation_error.json", {"type": type(exc).__name__, "message": str(exc),
                                                         "elapsed_ms": (time.perf_counter() - started) * 1000})
        raise
    finally:
        if workload is not None:
            workload.close()
