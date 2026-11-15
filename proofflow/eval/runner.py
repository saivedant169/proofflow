"""Run the predeclared pilot with real HydraDB and real dense embeddings.

Usage: python -m proofflow.eval.runner --split dev --output results/pilot-dev
Held-out execution additionally requires --allow-test and a matching committed
manifest. The default experiment is deterministic retrieval plus real refresh;
it does not claim end-to-end LLM-agent success.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.runtime import ProofFlowRuntime
from .cases import SCENARIOS, expected_affected_names, manifest_data
from .config import DEFAULT_CONFIG
from .oracle import compute_values
from .retrieval import (BM25Index, DenseEncoder, DenseIndex, PackedContext, TokenCounter,
                        canonical, corpus_digest, direct_ids, exact_seed, iterative_hybrid,
                        pack_records, rank_exact_closure, read_affected,
                        reciprocal_rank_fusion, render_context, score_sets)
from .workload import (apply_mutation, build_workload, evidence_alias, export_evidence,
                       in_scope, scenario_query)


ROOT = Path(__file__).resolve().parents[2]


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(path: Path) -> tuple[dict[str, Any], str]:
    encoded = path.read_bytes()
    data = json.loads(encoded)
    expected = {"fixture": manifest_data(), "configuration": DEFAULT_CONFIG}
    if canonical(data) != canonical(expected):
        raise ValueError("Manifest differs from the declared fixtures/configuration; freeze a new version before running")
    return data, hashlib.sha256(encoded).hexdigest()


def git_state() -> dict[str, Any]:
    def run(*args):
        return subprocess.run(["git", *args], cwd=ROOT, check=False, capture_output=True, text=True).stdout.strip()
    return {"revision": run("rev-parse", "HEAD"), "tracked_diff": bool(run("diff", "--name-only")),
            "staged_diff": bool(run("diff", "--cached", "--name-only"))}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def _append(path: Path, value: Any) -> None:
    with path.open("a") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["arm"], str(row["budget"]))].append(row)
    output = []
    for (arm, budget), values in sorted(groups.items()):
        output.append({
            "arm": arm, "budget": budget, "n_scenarios": len(values),
            "exact_affected_sets": sum(value["impact"]["exact_match"] for value in values),
            "mean_precision": sum(value["impact"]["precision"] for value in values) / len(values),
            "mean_recall": sum(value["impact"]["recall"] for value in values) / len(values),
            "mean_f1": sum(value["impact"]["f1"] for value in values) / len(values),
            "mean_context_tokens": sum(value["context_tokens"] for value in values) / len(values),
            "mean_retrieval_ms": sum(value["retrieval_ms"] for value in values) / len(values),
        })
    return {"experiment": "authored deterministic retrieval-and-refresh pilot", "retrieval": output,
            "limitations": ["Not end-to-end agent success; no LLM participates in this reader.",
                            "Shared semantic metadata and exact direct-ID seeds; full context is an explicit ceiling.",
                            "Every refresh arm uses the same Hydra-assisted currentness and recursive executor; standalone baseline safety is not evaluated.",
                            "The exact flat traversal is expected to tie the graph on correctness."]}


def run(args: argparse.Namespace) -> None:
    _, manifest_sha = verify_manifest(args.manifest)
    state = git_state()
    if args.split == "test" and not args.allow_test:
        raise ValueError("Held-out execution requires explicit --allow-test after the parent freezes and reviews the harness")
    if args.split == "test" and (state["tracked_diff"] or state["staged_diff"]):
        raise ValueError("Held-out execution refuses tracked or staged code changes; commit the reviewed harness first")
    output: Path = args.output
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Refusing to overwrite a prior benchmark run: {output}")
    output.mkdir(parents=True, exist_ok=True)
    config = DEFAULT_CONFIG
    counter = TokenCounter(config["tokenizer"])
    encoder = DenseEncoder(config["dense_model"], args.model_cache)
    run_metadata = {"started_at": datetime.now(timezone.utc).isoformat(), "split": args.split,
                    "fixture_manifest_sha256": manifest_sha, "spec_sha256": sha_file(ROOT / "docs/BENCHMARK_SPEC.md"),
                    "configuration": config, "code": state, "embedding": encoder.metadata(),
                    "experiment": "deterministic selected-evidence reader followed by actual tool refresh",
                    "database": "HydraDB OSS; native bounded FLOW traversals; no memory fallback",
                    "execution_isolation": "Independent SQLite/blob heads, immutable original graph; all rankings frozen before any refresh",
                    "shared_executor": "Hydra-assisted currentness and recursive refresh for every arm; standalone baseline safety not evaluated",
                    "numeric_oracle": "Independent Python arithmetic over authored recipes and current fixture data; no runtime arithmetic/graph/cache"}
    write_json(output / "run_manifest.json", run_metadata)
    results = []
    executions = []
    scenarios = [case for case in SCENARIOS if case.split == args.split and (not args.case or case.id in args.case)]
    if not scenarios:
        raise ValueError("No scenarios selected")
    for scenario in scenarios:
        print(f"[{scenario.id}] executing fresh fixture", flush=True)
        directory = output / scenario.id
        workload = build_workload(directory / "initial", additional_composition=scenario.additional_composition,
                                  namespace_prefix=f"pilot-{scenario.id}")
        try:
            changed_ids, current_sources = apply_mutation(workload, scenario)
            if scenario.restart:
                workload.runtime.store.close()
                workload.runtime.graph.close()
                workload.runtime = ProofFlowRuntime(ArtifactStore(directory / "initial"),
                                                    HydraGraph(namespace=workload.graph_namespace))
            all_records, alias_to_raw = export_evidence(workload)
            records = [record for record in all_records if in_scope(record.logical_id, scenario)]
            by_id = {record.id: record for record in records}
            query = scenario_query(workload, scenario, changed_ids)
            expected_names = expected_affected_names(scenario, workload.recipes)
            name_to_alias = {record.logical_id.removeprefix("artifact:"): record.id for record in records}
            expected = {name_to_alias[name] for name in expected_names}
            expected_values, expected_errors = compute_values(workload.recipes, current_sources)
            # Independently check receipt declarations before scoring retrieval.
            for recipe in workload.recipes:
                record = workload.refs[recipe.name]
                expected_inputs = {key: workload.refs[name].id for key, name in recipe.inputs.items()}
                if record.metadata["inputs"] != expected_inputs:
                    raise AssertionError(f"Recorded input mismatch for authored recipe {recipe.name}")
            raw_to_alias = {value: key for key, value in alias_to_raw.items()}
            graph_start = time.perf_counter()
            graph_queries_before = workload.runtime.graph.queries
            actual_graph = workload.runtime.affected(changed_ids)
            graph_ms = (time.perf_counter() - graph_start) * 1000
            graph_calls = workload.runtime.graph.queries - graph_queries_before
            graph_ids = {raw_to_alias[record.id] for record in actual_graph if raw_to_alias[record.id] in by_id}
            if graph_ids != expected:
                raise AssertionError(f"Hydra impact mismatch {scenario.id}: missing={sorted(expected-graph_ids)}, extra={sorted(graph_ids-expected)}")
            # A second numeric oracle verifies the core freshness evaluator.
            for recipe in workload.recipes:
                if recipe.name in expected_values:
                    actual = workload.runtime.full_recompute(workload.refs[recipe.name].id)
                    if actual != expected_values[recipe.name]:
                        raise AssertionError(f"Independent numeric oracle mismatch for {recipe.name}")
            index_start = time.perf_counter()
            bm25 = BM25Index(records, **config["bm25"])
            dense = DenseIndex(records, encoder)
            index_ms = (time.perf_counter() - index_start) * 1000
            corpus_tokens = counter(render_context(records))
            write_json(directory / "case.json", {
                "scenario": scenario.to_dict(), "query": {"text": query.text, "changed_ids": query.changed_ids},
                "evidence": [json.loads(record.render()) for record in records], "alias_to_raw": alias_to_raw,
                "corpus_sha256": corpus_digest(records), "corpus_records": len(records), "corpus_tokens": corpus_tokens,
                "index_build_ms": index_ms, "max_dense_document_tokens": max(dense.document_model_token_lengths),
                "dense_chunks": dense.chunk_count, "expected_revalidation_ids": sorted(expected),
                "numeric_oracle_values": expected_values, "numeric_oracle_errors": expected_errors,
                "graph_namespace": workload.graph_namespace,
            })
            base_rankings = {}
            ranking_ms = {}
            for arm, index in (("bm25", bm25), ("dense", dense)):
                start = time.perf_counter()
                base_rankings[arm] = exact_seed(index.rank(query.render()), records, query.changed_ids)
                ranking_ms[arm] = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            base_rankings["hybrid"] = exact_seed(reciprocal_rank_fusion(
                [base_rankings["bm25"], base_rankings["dense"]], constant=config["rrf_constant"]), records, query.changed_ids)
            ranking_ms["hybrid"] = (time.perf_counter() - start) * 1000 + ranking_ms["bm25"] + ranking_ms["dense"]
            start = time.perf_counter()
            exact_ranking = rank_exact_closure(records, query.changed_ids)
            ranking_ms["exact_flat"] = (time.perf_counter() - start) * 1000
            base_rankings["exact_flat"] = exact_ranking
            graph_order_start = time.perf_counter()
            # Membership comes from Hydra. Local depth ordering sees only the
            # native query's returned records, never adds omitted candidates,
            # and its CPU time is included rather than hidden in the flat arm.
            base_rankings["graph"] = rank_exact_closure([by_id[key] for key in graph_ids], query.changed_ids)
            ranking_ms["graph"] = graph_ms + (time.perf_counter() - graph_order_start) * 1000
            base_rankings["direct_id"] = direct_ids(records, query.changed_ids)
            ranking_ms["direct_id"] = 0.0
            # Intentional two-edge root→execution→artifact ablation, not a
            # complete-closure query with a dangerously shortened depth bound.
            direct_start = time.perf_counter()
            native_direct = workload.runtime.graph._walk_at_depth(changed_ids, 2, False)
            base_rankings["graph_direct"] = sorted(raw_to_alias[key] for key in native_direct if raw_to_alias.get(key) in by_id)
            ranking_ms["graph_direct"] = (time.perf_counter() - direct_start) * 1000
            bundles: dict[tuple[str, int | None], PackedContext] = {}
            for budget in [*config["budgets"], None]:
                for arm, ranking in base_rankings.items():
                    bundles[(arm, budget)] = pack_records([by_id[key] for key in ranking], budget, counter)
                start = time.perf_counter()
                bundles[("iterative_hybrid", budget)] = iterative_hybrid(
                    records, query, bm25, dense, budget, counter,
                    rounds=None if config["iterative_rounds"] == "corpus_size" else config["iterative_rounds"],
                    round_width=config["iterative_round_width"], constant=config["rrf_constant"])
                ranking_ms[f"iterative_hybrid:{budget}"] = (time.perf_counter() - start) * 1000
            bundles[("full_context", None)] = pack_records(records, None, counter)
            # All contexts and predictions are frozen before any refresh.
            predictions = {}
            for (arm, budget), packed in bundles.items():
                prediction = read_affected(packed.records, query.changed_ids)
                predictions[(arm, budget)] = list(prediction)
                row = {"scenario": scenario.id, "split": scenario.split, "category": scenario.category,
                       "arm": arm, "budget": "all" if budget is None else budget,
                       "context_tokens": packed.tokens, "corpus_tokens": corpus_tokens,
                       "retrieved_ids": [record.id for record in packed.records], "predicted_ids": sorted(prediction),
                       "impact": score_sets(expected, prediction),
                       "retrieval_ms": ranking_ms.get(f"{arm}:{budget}", ranking_ms.get(arm, 0.0)),
                       "retrieval_calls": graph_calls if arm == "graph" else packed.retrieval_calls,
                       "corpus_sha256": corpus_digest(records), "fixture_manifest_sha256": manifest_sha,
                       "context_sha256": hashlib.sha256(render_context(packed.records).encode()).hexdigest()}
                results.append(row)
                _append(output / "retrieval.jsonl", row)
                context_name = f"{arm}-{budget if budget is not None else 'all'}"
                (directory / f"context-{context_name}.jsonl").write_text(render_context(packed.records) + "\n")
            if not args.retrieval_only:
                from .execution import run_refresh_check
                for arm in config["execution_arms"]:
                    budget = None if arm == "full_context" else config["main_budget"]
                    print(f"[{scenario.id}] execute {arm} ({budget or 'all'} tokens)", flush=True)
                    execution = run_refresh_check(workload, scenario, predictions[(arm, budget)], alias_to_raw,
                                                  expected_values, expected_errors, directory / f"execute-{arm}")
                    execution.update(scenario=scenario.id, split=scenario.split, category=scenario.category,
                                     arm=arm, budget="all" if budget is None else budget,
                                     fixture_manifest_sha256=manifest_sha)
                    executions.append(execution)
                    _append(output / "execution.jsonl", execution)
            write_json(output / "summary.json", {**summarize(results), "execution": executions})
            print(f"[{scenario.id}] complete: {len(records)} records, {corpus_tokens} evidence tokens", flush=True)
        finally:
            workload.close()
    run_metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
    run_metadata["scenarios"] = [scenario.id for scenario in scenarios]
    run_metadata["partial_run"] = bool(args.case)
    write_json(output / "run_manifest.json", run_metadata)
    print(json.dumps(summarize(results), indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/BENCHMARK_MANIFEST.json")
    parser.add_argument("--model-cache", type=Path, default=ROOT / ".cache/fastembed")
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--case", action="append", help="Run an explicitly partial development/debug subset; preserve this disclosure")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
