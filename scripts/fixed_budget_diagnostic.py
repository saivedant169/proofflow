"""Freeze and run the local deterministic March fixed-budget diagnostic."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time
from types import SimpleNamespace
import uuid

from proofflow.artifacts import ArtifactStore
from proofflow.eval.model_contexts_v4 import ARMS, RETRIEVAL_CONFIG
from proofflow.eval.model_scoring_v4 import planned_report_counts, score_selection
from proofflow.eval.retrieval import (
    BM25Index, DenseEncoder, DenseIndex, EvidenceRecord, RetrievalQuery, TokenCounter,
    canonical, exact_seed, iterative_hybrid, pack_records, rank_exact_closure,
    read_affected, render_context, score_sets,
)
from proofflow.eval.workload import Workload, export_evidence
from proofflow.graph import HydraGraph
from proofflow.models import ArtifactRecord
from proofflow.runtime import ProofFlowRuntime
from scripts.audit_model_comparison_v4 import (
    CASES, FIXTURE, PREPARED, PREPARED_SHA256, REVISION, baseline_sources, case_truth, load,
)

ROOT = Path(__file__).resolve().parents[1]
STUDY = "fixed-budget-diagnostic-v1"
FREEZE = Path("fixtures/fixed_budget_diagnostic/freeze.json")
MARCH_FREEZE = Path("fixtures/model_comparison_v4/study_freeze.json")
PROTOCOL = Path("docs/FIXED_BUDGET_DIAGNOSTIC_PROTOCOL.md")
BUDGETS = (4096, 8192)
FULL_CONTEXT = "full_context"
ENCODING = "cl100k_base"
TOKENIZER_CACHE_KEY = "9b5ad71b2ce5302211f9c61530b329a4922fc6a4"
TOKENIZER_SHA256 = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
BGE_CACHE_REPOSITORY = "models--Qdrant--bge-small-en-v1.5-onnx-Q"
BGE_REVISION = "aa8f8b060edb00e03bfdd08813a2949946c8ba55"
BGE_SPECIAL_TOKENS_SHA256 = "5d5b662e421ea9fac075174bb0688ee0d9431699900b90662acd44b2a350503a"
HYDRA_URL = "http://127.0.0.1:18443"
HYDRA_IMAGE = (
    "ghcr.io/hydra-db/hydradb:0.4.0@"
    "sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880"
)
EVAL_MODULES = (
    "cases", "config", "model_comparison_data", "model_comparison_oracle",
    "model_contexts_v4", "model_scoring_v4", "retail_data", "retail_oracle",
    "retail_runner", "retrieval", "workload",
)
CODE_PATHS = (
    PROTOCOL, Path("scripts/fixed_budget_diagnostic.py"),
    Path("scripts/audit_model_comparison_v4.py"),
    Path("tests/test_fixed_budget_diagnostic.py"),
    Path("docs/MODEL_COMPARISON_DATA_SPEC.md"), Path("docker-compose.yml"), Path("pyproject.toml"), Path("uv.lock"),
    *(Path("proofflow") / f"{name}.py" for name in
      ("__init__", "agent", "analytics", "artifacts", "graph", "models", "runtime")),
    *(Path("proofflow/eval") / f"{name}.py" for name in ("__init__", *EVAL_MODULES)),
)


@dataclass(frozen=True)
class Cell:
    case_id: str
    arm: str
    cap: int | None

    @property
    def condition(self) -> str:
        return "uncapped_reference" if self.cap is None else f"fixed_{self.cap}"

    @property
    def path(self) -> Path:
        return Path(self.case_id) / self.condition / self.arm

    def identity(self) -> dict:
        return {
            "cell_id": self.path.as_posix(), "case_id": self.case_id, "arm": self.arm,
            "condition": self.condition, "cap": self.cap,
        }


def schedule() -> list[Cell]:
    cells = []
    for index, case_id in enumerate(CASES):
        offset = index % len(ARMS)
        for arm in ARMS[offset:] + ARMS[:offset]:
            caps = (None,) if arm == FULL_CONTEXT else BUDGETS
            cells.extend(Cell(case_id, arm, cap) for cap in caps)
    return cells


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def failure(exc: Exception) -> dict:
    return {"type": type(exc).__name__, "message": str(exc)}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def store_json(path: Path, value: object, *, new: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if new:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def march_paths(prepared: dict) -> list[Path]:
    paths = [PREPARED / "prepared.json", MARCH_FREEZE]
    for case_id in CASES:
        relative_files = ["case.json", "corpus.jsonl", "current_sources.json", "initial_records.json"]
        relative_files += [f"requests/{arm}/{name}" for arm in ARMS
                           for name in ("context.jsonl", "request.json", "prompt.txt")]
        for name in relative_files:
            relative = f"{case_id}/{name}"
            path = PREPARED / relative
            require(sha((ROOT / path).read_bytes()) == prepared["artifact_sha256"][relative],
                    f"Historical prepared input changed: {relative}")
            paths.append(path)
    paths.extend(path.relative_to(ROOT) for path in sorted((ROOT / FIXTURE).iterdir()) if path.is_file())
    return paths


def frozen_oracles() -> dict:
    """Cross-check saved arithmetic and source patches without ranking the corpus."""
    fixture = load(ROOT / FIXTURE / "fixture.json")
    baseline, raw = baseline_sources(ROOT, fixture)
    oracles = {}
    for case_id in CASES:
        directory = ROOT / PREPARED / case_id
        metadata = load(directory / "case.json")
        truth = case_truth(directory, metadata, fixture, baseline, raw)
        anchor = truth["anchor"]
        aliases = {key: alias for alias, key in metadata["alias_to_raw"].items()}
        affected = truth["affected"]
        unaffected = truth["reports"] - affected
        counts = planned_report_counts(metadata)
        require((counts["eligible_affected_reports"], counts["unavailable_reports"], counts["unaffected_reports"]) ==
                (len(truth["eligible_affected"]), len(truth["unavailable"]), len(unaffected)),
                f"{case_id}: two independent denominator calculations disagree")
        oracles[case_id] = {
            "counts": counts,
            "affected_names": sorted(affected),
            "affected_aliases": sorted(aliases[anchor["artifact_heads"][f"artifact:{name}"]] for name in affected),
            "eligible_affected_reports": sorted(truth["eligible_affected"]),
            "unavailable_reports": sorted(truth["unavailable"]),
            "numerically_changed_reports": sorted(truth["numeric_change"]),
            "unaffected_report_heads": {name: anchor["artifact_heads"][f"artifact:{name}"] for name in sorted(unaffected)},
            "expected_values_sha256": sha(canonical(truth["values"])),
        }
    return oracles


def freeze_payload() -> dict:
    prepared_path = ROOT / PREPARED / "prepared.json"
    require(sha(prepared_path.read_bytes()) == PREPARED_SHA256, "Historical prepared manifest changed")
    prepared = load(prepared_path)
    require(len(prepared["jobs"]) == 48 and tuple(case["case_id"] for case in prepared["cases"]) == CASES,
            "Historical request schedule differs from the March study")
    march_freeze = load(ROOT / MARCH_FREEZE)
    require(sha((ROOT / MARCH_FREEZE).read_bytes()) == prepared["freeze_sha256"], "Historical settings changed")
    paths = march_paths(prepared)
    oracles = frozen_oracles()
    expected_denominators = {"eligible_affected_reports": 32, "unavailable_reports": 4, "unaffected_reports": 52}
    for key, count in expected_denominators.items():
        require(sum(value["counts"][key] for value in oracles.values()) == count,
                f"Unexpected frozen denominator for {key}")
    return {
        "study": STUDY, "historical_revision": REVISION, "historical_prepared_sha256": PREPARED_SHA256,
        "budgets": list(BUDGETS), "planned_cells": [cell.identity() for cell in schedule()],
        "retrieval": {key: value for key, value in RETRIEVAL_CONFIG.items() if key != "evidence_budget"},
        "tokenizer": {"encoding": ENCODING, "vocabulary_sha256": TOKENIZER_SHA256},
        "embedding": march_freeze["embedding"], "package_versions": march_freeze["environment"]["packages"],
        "embedding_snapshot": {"revision": BGE_REVISION, "repository": BGE_CACHE_REPOSITORY,
                               "special_tokens_sha256": BGE_SPECIAL_TOKENS_SHA256},
        "hydra": {"image": HYDRA_IMAGE, "url": HYDRA_URL},
        "oracle": oracles,
        "historical_input_sha256": {path.as_posix(): sha((ROOT / path).read_bytes()) for path in paths},
        "code_sha256": {path.as_posix(): sha((ROOT / path).read_bytes()) for path in CODE_PATHS},
    }


def verify_frozen_inputs(revision: str, manifest: dict, freeze_sha: str) -> None:
    resolved = git("rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    require(revision == resolved, "Supply the full approved Git commit SHA")
    expected_files = manifest["historical_input_sha256"] | manifest["code_sha256"] | {FREEZE.as_posix(): freeze_sha}
    for name, expected in expected_files.items():
        require(sha((ROOT / name).read_bytes()) == expected and sha(git("show", f"{revision}:{name}")) == expected,
                f"Working or committed frozen file changed: {name}")
    require(set(manifest["code_sha256"]) == {path.as_posix() for path in CODE_PATHS},
            "Frozen source inventory differs from the implementation")
    require(manifest["study"] == STUDY and manifest["planned_cells"] == [cell.identity() for cell in schedule()]
            and manifest["budgets"] == list(BUDGETS), "Frozen schedule or caps changed")


def verify_local_hydra() -> None:
    container = subprocess.check_output(
        ["docker", "compose", "ps", "--quiet", "hydradb"], cwd=ROOT, text=True,
    ).strip()
    require(bool(container) and "\n" not in container, "The pinned local HydraDB service must be running")
    info, = json.loads(subprocess.check_output(["docker", "inspect", container], cwd=ROOT))
    require(info["Config"]["Image"] == HYDRA_IMAGE, "The local HydraDB image differs from the frozen image")
    require(info["NetworkSettings"]["Ports"]["8443/tcp"] == [{"HostIp": "127.0.0.1", "HostPort": "18443"}],
            "The pinned HydraDB service is not published on the expected loopback port")
    os.environ.update(PROOFFLOW_HYDRA_URL=HYDRA_URL, NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")


def verify_cached_inputs(cache: Path, manifest: dict) -> tuple[Path, str]:
    token_cache = (os.environ.get("TIKTOKEN_CACHE_DIR") or os.environ.get("DATA_GYM_CACHE_DIR")
                   or str(Path(tempfile.gettempdir()) / "data-gym-cache"))
    require(sha((Path(token_cache) / TOKENIZER_CACHE_KEY).read_bytes()) == TOKENIZER_SHA256,
            "A cached original cl100k_base vocabulary is required")
    repository = cache / BGE_CACHE_REPOSITORY
    snapshot = repository / "snapshots" / BGE_REVISION
    require((repository / "refs/main").read_text().strip() == BGE_REVISION, "Cached BGE revision differs from the freeze")
    hashes = manifest["embedding"]["model_file_sha256"] | {"special_tokens_map.json": BGE_SPECIAL_TOKENS_SHA256}
    for name, digest in hashes.items():
        require(sha((snapshot / name).read_bytes()) == digest, f"Cached BGE asset differs from the freeze: {name}")
    return snapshot, token_cache


def local_resources(cache: Path, manifest: dict) -> tuple[DenseEncoder, TokenCounter]:
    versions = {name: importlib.metadata.version(name) for name in manifest["package_versions"]}
    require(versions == manifest["package_versions"], "Installed benchmark dependencies differ from the March study")
    os.environ["HF_HUB_OFFLINE"] = "1"
    snapshot, token_cache = verify_cached_inputs(cache, manifest)
    os.environ["TIKTOKEN_CACHE_DIR"] = token_cache
    counter = TokenCounter(ENCODING)
    encoder = DenseEncoder(RETRIEVAL_CONFIG["dense_model"], cache)
    embedding = {key: value for key, value in encoder.metadata().items() if key not in {"cache_dir", "model_directory"}}
    require(encoder.model_dir.resolve() == snapshot.resolve() and embedding == manifest["embedding"],
            "Loaded BGE model, tokenizer, or chunk configuration differs from the frozen cache")
    return encoder, counter


def restore_store(store: ArtifactStore, anchor: dict) -> None:
    """Rehydrate exact immutable IDs and heads from the tracked March export."""
    records = anchor["records"]
    heads = {identifier: (kind, logical) for kind in ("artifact", "source", "tool")
             for logical, identifier in anchor[f"{kind}_heads"].items()}
    workspace, = {identifier.split(":", 1)[0] for identifier in records}
    with store.db:
        store.db.execute("UPDATE settings SET value=? WHERE key='workspace'", (workspace,))
    store.workspace = workspace
    for identifier, exported in records.items():
        record = ArtifactRecord(**{key: value for key, value in exported.items() if key != "value"})
        require(record.id == identifier and heads.get(identifier, (record.kind, record.logical_id)) ==
                (record.kind, record.logical_id), f"Invalid immutable identity: {identifier}")
        store.commit(record, exported["value"], head=identifier in heads)
    require({record.id for record in store.heads()} == heads.keys(), "Restored store is missing anchored heads")


def publish_receipt_graph(runtime: ProofFlowRuntime) -> None:
    """Publish frozen runtime lineage with the same edge semantics as execute()."""
    records = runtime.store.list_records()
    for record in records:
        runtime._write_node(record)
    for record in records:
        if record.kind != "artifact":
            continue
        metadata = record.metadata
        receipt_id = metadata["receipt_id"]
        receipt = runtime.store.read(receipt_id)
        require(receipt["output_id"] == record.id and receipt["inputs"] == metadata["inputs"] and
                receipt["tool_version_id"] == metadata["tool_version_id"], f"Malformed anchored receipt: {receipt_id}")
        for identifier in sorted(set(receipt["inputs"].values())):
            runtime.graph.put_edge(identifier, receipt_id, "CONSUMED")
        runtime.graph.put_edge(receipt["tool_version_id"], receipt_id, "USED_TOOL")
        runtime.graph.put_edge(receipt_id, record.id, "PRODUCED")


def load_case(case_id: str, directory: Path, namespace: str) -> tuple[dict, list[EvidenceRecord], RetrievalQuery]:
    historical = ROOT / PREPARED / case_id
    metadata = load(historical / "case.json")
    anchor_path = historical / "initial_records.json"
    require(sha(anchor_path.read_bytes()) == metadata["initial_records_sha256"], f"{case_id}: initial anchor changed")
    initial = directory / "initial"
    with closing(ArtifactStore(initial)) as store:
        restore_store(store, load(anchor_path))
        refs = {record.logical_id.removeprefix("artifact:"): record for record in store.heads("artifact")}
        declarations = [SimpleNamespace(**recipe) for recipe in metadata["recipes"]]
        workload = Workload(ProofFlowRuntime(store, None), {}, declarations, refs, namespace)
        exported, aliases = export_evidence(workload)
    corpus = (historical / "corpus.jsonl").read_bytes()
    require(corpus == (render_context(exported) + "\n").encode() and aliases == metadata["alias_to_raw"],
            f"{case_id}: reconstructed store exported different evidence or aliases")
    require(len(exported) == 39 and len({record.id for record in exported}) == 39,
            f"{case_id}: incomplete or duplicate candidate scope")
    metadata.update(initial_store_path=str(initial), initial_records_path=str(anchor_path))
    return metadata, exported, RetrievalQuery(metadata["query"]["text"], tuple(metadata["query"]["changed_ids"]))


def native_membership(metadata: dict, records: list[EvidenceRecord], namespace: str) -> tuple[set[str], dict]:
    with closing(ArtifactStore(metadata["initial_store_path"])) as store, HydraGraph(namespace=namespace) as graph:
        runtime = ProofFlowRuntime(store, graph)
        publish_receipt_graph(runtime)
        started, before_queries = time.perf_counter(), graph.queries
        native = {record.id for record in runtime.affected(metadata["changed_raw_ids"])}
        discovery_ms = (time.perf_counter() - started) * 1000
        candidates = {record.id for record in records}
        raw_to_alias = {raw: alias for alias, raw in metadata["alias_to_raw"].items() if alias in candidates}
        members = {raw_to_alias[key] for key in native}
        require(members == set(metadata["native_graph_ids"]), "Fresh native membership differs from frozen native membership")
        return members, {
            "native_discovery_queries": graph.queries - before_queries, "native_discovery_ms": discovery_ms,
            "namespace": namespace, "reconstructed_graph_mutations": graph.mutations,
            "native_membership_aliases": sorted(members),
        }


def plan_cell(
    cell: Cell, records: list[EvidenceRecord], query: RetrievalQuery, native: set[str],
    bm25: BM25Index | None, dense: DenseIndex | None, counter: TokenCounter,
) -> tuple[str, dict]:
    started = time.perf_counter()
    by_id = {record.id: record for record in records}
    if cell.arm == "graph":
        graph_rank = rank_exact_closure([by_id[key] for key in sorted(native)], query.changed_ids)
        ranking = list(dict.fromkeys([*graph_rank, *sorted(native)]))
    elif cell.arm == "exact_flat":
        ranking = rank_exact_closure(records, query.changed_ids)
    elif cell.arm in {"bm25", "dense"}:
        index = bm25 if cell.arm == "bm25" else dense
        ranking = exact_seed(index.rank(query.render()), records, query.changed_ids)
    elif cell.arm == FULL_CONTEXT:
        ranking = [record.id for record in records]
    elif cell.arm != "iterative_hybrid":
        raise ValueError(f"Unknown arm: {cell.arm}")
    if cell.arm == "iterative_hybrid":
        packed = iterative_hybrid(
            records, query, bm25, dense, cell.cap, counter,
            round_width=RETRIEVAL_CONFIG["iterative_round_width"], constant=RETRIEVAL_CONFIG["rrf_constant"],
        )
    else:
        packed = pack_records([by_id[identifier] for identifier in ranking], cell.cap, counter)
    planning_ms = (time.perf_counter() - started) * 1000
    context = render_context(packed.records)
    require(packed.tokens == counter(context) and (cell.cap is None or packed.tokens <= cell.cap),
            f"Exact evidence count violates cap for {cell.path}")
    selected = read_affected(packed.records, query.changed_ids)
    retrieved = [record.id for record in packed.records]
    require(selected.keys() <= set(retrieved), "Reader selected an alias outside the evidence")
    return context, {
        "evidence_tokens": packed.tokens, "retrieved_aliases": retrieved, "skipped_aliases": packed.skipped_ids,
        "selected_aliases": list(selected), "selected_depths": selected, "context_sha256": sha(context),
        "index_calls": packed.retrieval_calls if cell.arm in {"bm25", "dense", "iterative_hybrid"} else 0,
        "ranking_and_packing_ms": planning_ms,
    }


def case_indexes(records: list[EvidenceRecord], encoder: DenseEncoder) -> tuple[dict, dict]:
    """Independent index preparation preserves failures for affected arms."""
    encoder.memo.clear()
    indexes, errors = {}, {}
    builders = (("bm25", lambda: BM25Index(records, **RETRIEVAL_CONFIG["bm25"])),
                ("dense", lambda: DenseIndex(records, encoder)))
    for name, build in builders:
        try:
            indexes[name] = build()
        except Exception as exc:
            errors[name] = failure(exc)
    return indexes, errors


def execute_cell(metadata: dict, selected: list[str], private: Path, namespace: str, oracle: dict) -> dict:
    with closing(ArtifactStore(metadata["initial_store_path"])) as store, HydraGraph(namespace=namespace) as graph:
        publish_receipt_graph(ProofFlowRuntime(store, graph))
        graph_mutations = graph.mutations
    result = score_selection({**metadata, "graph_namespace": namespace}, selected, private)
    store_json(private / "scoring_result.json", result, new=True)
    raw = result["raw_execution"]
    require(raw["selected_aliases"] == selected, "The executor's selected IDs differ from the reader's exact plan")
    require(result["expected_affected_names"] == oracle["affected_names"] and
            sha(canonical({item["name"]: item["expected_value"] for item in raw["artifacts"]})) ==
            oracle["expected_values_sha256"], "Scorer expectations differ from the prospectively frozen oracle")
    by_name = {item["name"]: item for item in result["verified_artifacts"]}
    report_counts = result["verified_report_counts"]
    require(sorted(name for name, item in by_name.items() if item["is_report"] and item["expected_revalidation"]
                   and item["oracle_available"]) == oracle["eligible_affected_reports"] and
            sorted(name for name, item in by_name.items() if item["is_report"] and not item["oracle_available"]) ==
            oracle["unavailable_reports"] and
            {name: item["original_id"] for name, item in by_name.items()
             if item["is_report"] and not item["expected_revalidation"]} == oracle["unaffected_report_heads"],
            "Scored report identities differ from the prospectively frozen oracle")
    return {
        "whole_case_correct": result["absolute_correct"] and (metadata["case_id"] != "M08" or not selected),
        "verified_report_counts": report_counts, "verified_artifact_counts": result["verified_artifact_counts"],
        "verified_artifacts": result["verified_artifacts"], "scoring_errors": result["scoring_errors"],
        "independent_global_validation": result["independent_global_validation"],
        "expected_missing_source_refusal": raw["expected_source_unavailable_refusal"],
        "safe_empty_missing_selection": metadata["case_id"] == "M07" and not selected and result["absolute_correct"],
        "refresh_error": raw["refresh_error"], "inspection_errors": raw["inspection_errors"],
        "refresh_tool_calls": raw["tool_calls"], "refresh_graph_queries": raw["refresh_graph_queries"],
        "scoring_total_ms": result["scoring_total_ms"], "refresh_ms": raw["refresh_ms"],
        "namespace": namespace, "reconstructed_graph_mutations": graph_mutations,
        "post_snapshot_sha256": result["post_snapshot_sha256"], "independent_audit_sha256": result["independent_audit_sha256"],
    }


def plan_case(case_id: str, output: Path, private: Path, cells: list[Cell], rows: dict, run_id: str,
              encoder: DenseEncoder, counter: TokenCounter, oracle: dict) -> dict | None:
    case_output = output / case_id
    discovery_namespace = f"{STUDY}-{run_id}-{case_id}-discovery"
    setup = {"status": "running", "started_at": timestamp()}
    store_json(case_output / "setup.json", setup)
    try:
        metadata, records, query = load_case(case_id, private / case_id, discovery_namespace)
    except Exception as exc:
        error = failure(exc)
        setup.update(status="failed", finished_at=timestamp(), error=error)
        store_json(case_output / "setup.json", setup)
        for cell in cells:
            rows[cell]["dependency_error"] = {"component": "case_setup", **error}
        return None
    facts = {
        "query": query.text, "changed_aliases": list(query.changed_ids), "query_tokens": counter(query.render()),
        "corpus_sha256": sha(render_context(records)), "corpus_records": len(records),
        "corpus_tokens": counter(render_context(records)),
    }
    native, native_error = set(), None
    try:
        native, facts["native"] = native_membership(metadata, records, discovery_namespace)
    except Exception as exc:
        native_error = failure(exc)
        facts["native_error"] = native_error
    indexes, errors = case_indexes(records, encoder)
    facts["index_build_errors"] = errors
    store_json(case_output / "case.json", facts)
    setup.update(status="partial" if native_error or errors else "ready",
                 finished_at=timestamp(), native_error=native_error, index_build_errors=errors)
    store_json(case_output / "setup.json", setup)
    dependency_errors = {
        "graph": ("native_discovery", native_error),
        "bm25": ("bm25_index", errors.get("bm25")),
        "dense": ("dense_index", errors.get("dense")),
        "iterative_hybrid": ("hybrid_index", errors.get("bm25") or errors.get("dense")),
    }
    for cell in cells:
        row = rows[cell]
        attempt = output / cell.path / "attempt.json"
        component, error = dependency_errors.get(cell.arm, (None, None))
        if error is not None:
            row["dependency_error"] = {"component": component, **error}
            store_json(attempt, row)
            continue
        row.update(status="planning", planning_started_at=timestamp())
        store_json(attempt, row)
        try:
            context, plan = plan_cell(cell, records, query, native, indexes.get("bm25"), indexes.get("dense"), counter)
            (output / cell.path / "context.jsonl").write_bytes(context.encode())
            expected = oracle["affected_aliases"]
            plan.update(retrieved_affected=score_sets(expected, plan["retrieved_aliases"]),
                        reader_affected=score_sets(expected, plan["selected_aliases"]))
            row.update(status="planned", plan=plan)
        except Exception as exc:
            row.update(status="plan_failed", planning_error=failure(exc))
        row["planning_finished_at"] = timestamp()
        store_json(attempt, row)
    return metadata


def summarize(rows: dict[Cell, dict], oracles: dict, integrity: bool) -> dict:
    groups = [(arm, cap) for cap in BUDGETS for arm in ARMS if arm != FULL_CONTEXT] + [(FULL_CONTEXT, None)]
    aggregates = []
    safety_counts = {
        "fresh_affected": "fresh_affected", "unavailable_blocked": "correctly_blocked",
        "unaffected_preserved": "unaffected_artifacts_preserved", "incorrect_current": "incorrect_current",
    }
    for arm, cap in groups:
        group = [row for cell, row in rows.items() if (cell.arm, cell.cap) == (arm, cap)]
        planned = [row["planned_report_counts"] for row in group]
        scored = [row["score"] for row in group if row["status"] == "scored"]
        plans = [row["plan"] for row in group if "plan" in row]
        denominators = {
            "eligible_affected": sum(row["eligible_affected_reports"] for row in planned),
            "unavailable": sum(row["unavailable_reports"] for row in planned),
            "unaffected": sum(row["unaffected_reports"] for row in planned),
            "affected_artifacts": sum(len(oracles[row["case_id"]]["affected_names"]) for row in group),
        }
        observed_counts = {label: (sum(score["verified_report_counts"][key] for score in scored) if scored else None)
                           for label, key in safety_counts.items()}
        whole = sum(score["whole_case_correct"] for score in scored)
        complete = len(scored) == len(group) == len(CASES)
        retrieval = {field: ({metric: sum(plan[field][metric] for plan in plans) for metric in ("tp", "fp", "fn")}
                             if plans else None) for field in ("retrieved_affected", "reader_affected")}
        aggregates.append({
            "arm": arm, "cap": cap, "condition": group[0]["condition"], "planned_cells": len(group),
            "status_counts": dict(Counter(row["status"] for row in group)), "scored_cells": len(scored),
            "planned_denominators": denominators, "reports_observed": observed_counts, "whole_cases_correct": whole,
            "expected_missing_source_refusals": sum(score["expected_missing_source_refusal"] for score in scored),
            "safe_empty_missing_selections": sum(score["safe_empty_missing_selection"] for score in scored),
            "evidence_tokens_observed": sum(plan["evidence_tokens"] for plan in plans) if plans else None,
            "planned_contexts_observed": len(plans), **retrieval,
            "absolute_report_gate": bool(integrity and complete and whole == len(CASES)
                                        and observed_counts["fresh_affected"] == denominators["eligible_affected"]
                                        and observed_counts["unavailable_blocked"] == denominators["unavailable"]
                                        and observed_counts["unaffected_preserved"] == denominators["unaffected"]
                                        and observed_counts["incorrect_current"] == 0),
        })
    parity = {}
    for cap in BUDGETS:
        pairs = [(rows[Cell(case_id, "graph", cap)].get("plan"), rows[Cell(case_id, "exact_flat", cap)].get("plan"))
                 for case_id in CASES]
        observed = [(graph, flat) for graph, flat in pairs if graph is not None and flat is not None]
        parity[str(cap)] = {"planned": len(CASES), "observed": len(observed),
                            "matching_contexts": sum(graph["context_sha256"] == flat["context_sha256"]
                                                     for graph, flat in observed)}
    return {
        "study": STUDY, "planned_cells": len(rows), "status_counts": dict(Counter(row["status"] for row in rows.values())),
        "complete": len(rows) == 88 and all(row["status"] == "scored" for row in rows.values()) and integrity,
        "freeze_integrity_verified": integrity, "graph_exact_flat_context_parity": parity, "groups": aggregates,
    }


def run(revision: str, output: Path, private: Path, cache: Path) -> bool:
    freeze_path = ROOT / FREEZE
    freeze_sha = sha(freeze_path.read_bytes())
    frozen = load(freeze_path)
    verify_frozen_inputs(revision, frozen, freeze_sha)
    output, private = output.resolve(), private.resolve()
    require(not (output.exists() or private.exists() or output.is_relative_to(private) or private.is_relative_to(output)),
            "Public and private run directories must be new and distinct")
    require(not private.is_relative_to(ROOT), "Private scoring artifacts must stay outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    run_id = uuid.uuid4().hex
    cells = schedule()
    oracles = frozen["oracle"]
    rows = {cell: {**cell.identity(), "status": "unattempted",
                   "planned_report_counts": oracles[cell.case_id]["counts"]} for cell in cells}
    run_manifest = {
        "study": STUDY, "run_id": run_id, "started_at": timestamp(), "finished": False,
        "approved_frozen_revision": revision, "working_revision_at_start": git("rev-parse", "HEAD").decode().strip(),
        "freeze_sha256": freeze_sha, "planned_cells": list(rows.values()), "hydra": frozen["hydra"],
        "python": platform.python_version(), "platform": platform.platform(),
        "package_versions": frozen["package_versions"], "embedding": frozen["embedding"],
        "embedding_snapshot": frozen["embedding_snapshot"],
        "generative_provider_invocations": 0,
    }
    store_json(output / "run_manifest.json", run_manifest, new=True)
    stop_error, integrity_error, resource_integrity_error = None, None, None
    resources_ready, resource_integrity_verified = False, False
    try:
        verify_local_hydra()
        encoder, counter = local_resources(cache, frozen)
        resources_ready = True
        metadata = {}
        for case_id in CASES:
            print(f"[{case_id}] Preparing fixed-budget reader selections", flush=True)
            metadata[case_id] = plan_case(case_id, output, private, [cell for cell in cells if cell.case_id == case_id],
                                          rows, run_id, encoder, counter, oracles[case_id])
        for cell in cells:
            row = rows[cell]
            if row["status"] != "planned":
                continue
            attempt = output / cell.path / "attempt.json"
            print(f"[{cell.path}] Running shared refresh and audit", flush=True)
            row.update(status="executing", execution_started_at=timestamp())
            store_json(attempt, row)
            try:
                context = (output / cell.path / "context.jsonl").read_bytes()
                require(sha(context) == row["plan"]["context_sha256"], f"Context changed after planning: {cell.path}")
                namespace = f"{STUDY}-{run_id}-{cell.path.as_posix().replace('/', '-')}"
                row["score"] = execute_cell(metadata[cell.case_id], row["plan"]["selected_aliases"],
                                            private / cell.path / "execution", namespace, oracles[cell.case_id])
                row["status"] = "scored"
            except Exception as exc:
                row.update(status="execution_failed", execution_error=failure(exc))
            row["execution_finished_at"] = timestamp()
            store_json(attempt, row)
    except (Exception, KeyboardInterrupt) as exc:
        stop_error = failure(exc)
    finally:
        try:
            verify_frozen_inputs(revision, frozen, freeze_sha)
        except Exception as exc:
            integrity_error = failure(exc)
        if resources_ready:
            try:
                verify_local_hydra()
                verify_cached_inputs(cache, frozen)
                resource_integrity_verified = True
            except Exception as exc:
                resource_integrity_error = failure(exc)
        else:
            resource_integrity_error = stop_error or {"type": "Unverified", "message": "Runtime setup did not complete"}
        for cell, row in rows.items():
            if row["status"] == "unattempted":
                if not resources_ready:
                    row["dependency_error"] = {"component": "shared_environment", **resource_integrity_error}
                store_json(output / cell.path / "attempt.json", row)
        summary = summarize(rows, oracles, integrity_error is None and resource_integrity_verified)
        integrity = {
            "source_integrity_verified": integrity_error is None, "integrity_error": integrity_error,
            "resource_integrity_verified": resource_integrity_verified, "resource_integrity_error": resource_integrity_error,
        }
        summary.update(stop_error=stop_error, **integrity)
        store_json(output / "summary.json", summary)
        run_manifest.update(finished=True, finished_at=timestamp(), stop_error=stop_error, **integrity,
                            working_revision_at_finish=git("rev-parse", "HEAD").decode().strip())
        # The planned rows in this file must remain the original unobserved plan.
        run_manifest["planned_cells"] = [{**cell.identity(), "status": "unattempted",
                                          "planned_report_counts": oracles[cell.case_id]["counts"]} for cell in cells]
        store_json(output / "run_manifest.json", run_manifest)
    print(json.dumps({"complete": summary["complete"], "status_counts": summary["status_counts"],
                      "stop_error": stop_error, "integrity_error": integrity_error}, sort_keys=True), flush=True)
    return summary["complete"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze", help="Create the prospective input/oracle manifest without running retrieval or refresh")
    measure = commands.add_parser("run", help="Execute all 88 cells from the owner-approved locked revision")
    measure.add_argument("--expected-revision", required=True)
    measure.add_argument("--output", type=Path, default=ROOT / "results" / STUDY)
    measure.add_argument("--private-output", type=Path, required=True)
    measure.add_argument("--model-cache", type=Path, default=ROOT / ".cache/fastembed")
    args = parser.parse_args()
    if args.command == "freeze":
        destination = ROOT / FREEZE
        require(not destination.exists(), "The prospective freeze already exists")
        store_json(destination, freeze_payload(), new=True)
        print(f"Wrote {FREEZE} with SHA-256 {sha(destination.read_bytes())}")
    elif not run(args.expected_revision, args.output, args.private_output, args.model_cache):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
