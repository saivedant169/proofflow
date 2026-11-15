#!/usr/bin/env python3
"""Verify and publish the completed scorer outputs from the single frozen run.

The original wrapper summary and all original attempts remain the run record.
This publisher opens retained JSON and JSONL, and has no retrieval or runtime
invocation. It relates the saved scorer output to independently verified truth
and exact evidence bytes.
"""
from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from proofflow.eval.model_comparison_oracle import audit_provenance, compute_values, expected_affected_names
from proofflow.eval.model_scoring_v4 import _expected_inputs, aggregate_verified_outcome
from proofflow.eval.retrieval import EvidenceRecord, TokenCounter, canonical, read_affected, render_context, score_sets
from scripts.audit_model_comparison_v4 import CASES, FIXTURE, PREPARED, baseline_sources, case_truth, independent_provenance
from scripts.fixed_budget_diagnostic import (
    ENCODING, FREEZE, load, require, schedule, sha, store_json, summarize, verify_cached_inputs, verify_frozen_inputs,
)

FROZEN_REVISION = "4f43dd497a05078edf226de62070778b17d91498"
FROZEN_MANIFEST_SHA256 = "cd609ff71f8f74162fb2ae911e8f7cae6d1429db347debff79a1e69fd857f92f"
ORIGINAL_MANIFEST_SHA256 = "d3579815f2f2c6d8c7f1948c86badd2e7104288ced930447703b3aee20a3cbb7"
ORIGINAL_SUMMARY_SHA256 = "19b100a8bb4892408b4620c3582ac97cf4327c5dd27940707b722cbfcf67cc8b"
WRAPPER_ERROR = {"type": "KeyError", "message": "'verified_report_counts'"}


def original_inventory(public: Path) -> dict:
    names = [Path("run_manifest.json"), Path("summary.json")]
    for case_id in CASES:
        names.extend(Path(case_id) / filename for filename in ("case.json", "setup.json"))
    for cell in schedule():
        names.extend(cell.path / filename for filename in ("attempt.json", "context.jsonl"))
    expected_attempts = {public / name for name in names if name.name == "attempt.json"}
    require(set(public.rglob("attempt.json")) == expected_attempts, "Original attempt inventory differs from the schedule")
    return {name.as_posix(): sha((public / name).read_bytes()) for name in names}


def verified_cases(public: Path, frozen: dict, counter: TokenCounter) -> dict:
    fixture = load(REPO / FIXTURE / "fixture.json")
    base, raw_rows = baseline_sources(REPO, fixture)
    cases = {}
    for case_id in CASES:
        directory = REPO / PREPARED / case_id
        metadata = load(directory / "case.json")
        truth = case_truth(directory, metadata, fixture, base, raw_rows)
        oracle = frozen["oracle"][case_id]
        anchor = truth["anchor"]
        declarations = [SimpleNamespace(**recipe) for recipe in metadata["recipes"]]
        sources, tools, changed_sources, changed_tools = _expected_inputs(
            metadata, declarations, anchor, metadata["analytics_sha256"],
        )
        values, errors = compute_values(declarations, sources)
        candidates = set(metadata["candidate_names"])
        affected = expected_affected_names(declarations, changed_sources, changed_tools, candidates)
        expected_values = {name: values.get(name) for name in candidates}
        require(expected_values == truth["values"] and sha(canonical(expected_values)) == oracle["expected_values_sha256"]
                and affected == truth["affected"] == set(oracle["affected_names"]),
                f"{case_id}: independent source staging or values disagree with frozen oracle")
        require(set(oracle["eligible_affected_reports"]) == truth["eligible_affected"]
                and set(oracle["unavailable_reports"]) == truth["unavailable"]
                and oracle["unaffected_report_heads"] == {
                    name: anchor["artifact_heads"][f"artifact:{name}"] for name in truth["reports"] - affected
                }, f"{case_id}: frozen report labels differ from independent truth")
        text = (directory / "corpus.jsonl").read_text(encoding="utf-8").removesuffix("\n")
        corpus = {record.id: record for record in (EvidenceRecord(**json.loads(line)) for line in text.split("\n"))}
        facts = load(public / case_id / "case.json")
        require(load(public / case_id / "setup.json")["status"] == "ready" and len(corpus) == 39
                and facts["changed_aliases"] == metadata["query"]["changed_ids"]
                and facts["query"] == metadata["query"]["text"]
                and facts["corpus_tokens"] == counter(text) and facts["corpus_sha256"] == sha(text)
                and facts["native"]["native_membership_aliases"] == metadata["native_graph_ids"],
                f"{case_id}: original case outcome differs from frozen inputs")
        cases[case_id] = {
            "corpus": corpus, "metadata": metadata, "truth": truth, "anchor": anchor, "oracle": oracle,
            "declarations": declarations, "sources": sources, "tools": tools, "values": values, "errors": errors,
            "candidates": candidates, "affected": affected,
        }
    return cases


def verify_context(cell, row: dict, directory: Path, case: dict, counter: TokenCounter) -> None:
    plan = row["plan"]
    corpus = case["corpus"]
    retrieved = plan["retrieved_aliases"]
    records = [corpus[identifier] for identifier in retrieved]
    context = (directory / "context.jsonl").read_bytes()
    require(len(set(retrieved)) == len(retrieved) and render_context(records).encode() == context
            and sha(context) == plan["context_sha256"] and counter(context.decode()) == plan["evidence_tokens"],
            f"{cell.path}: context differs from the canonical ordered receipts")
    if cell.cap is None:
        require(retrieved == list(corpus), f"{cell.path}: incomplete uncapped reference")
    else:
        require(plan["evidence_tokens"] <= cell.cap, f"{cell.path}: original evidence cap exceeded")
    selected = read_affected(records, case["metadata"]["query"]["changed_ids"])
    expected = case["oracle"]["affected_aliases"]
    require(list(selected) == plan["selected_aliases"] and selected == plan["selected_depths"]
            and plan["reader_affected"] == score_sets(expected, selected)
            and plan["retrieved_affected"] == score_sets(expected, retrieved),
            f"{cell.path}: retained selection or impact summary differs from the exact context")


def verify_score(cell, row: dict, private: Path, case: dict) -> dict:
    raw_path = private / "scoring_result.json"
    result = load(raw_path)
    require("verified_report_counts" not in result and "verified_artifact_counts" not in result
            and "verified_reports_counts" in result and "verified_artifacts_counts" in result,
            f"{cell.path}: retained scorer fields do not explain the wrapper error")
    snapshot = private / "post_snapshot.json"
    audit_path = private / "independent_audit.json"
    require(Path(result["post_snapshot_path"]).resolve() == snapshot
            and Path(result["independent_audit_path"]).resolve() == audit_path
            and sha(snapshot.read_bytes()) == result["post_snapshot_sha256"]
            and sha(audit_path.read_bytes()) == result["independent_audit_sha256"],
            f"{cell.path}: snapshot/audit file locations or digests differ from the recorded scorer")
    post, raw = load(snapshot), result["raw_execution"]
    selected = row["plan"]["selected_aliases"]
    require(raw["selected_aliases"] == selected and result["expected_affected_names"] == sorted(case["affected"]),
            f"{cell.path}: refresh selection or scoring scope differs from the frozen cell")
    raw_expected = {item["name"]: item["expected_value"] for item in raw["artifacts"]}
    require(len(raw_expected) == len(raw["artifacts"]) and raw_expected.keys() == case["candidates"]
            and sha(canonical(raw_expected)) == case["oracle"]["expected_values_sha256"],
            f"{cell.path}: retained raw expected values differ from the frozen oracle")
    anchor = case["anchor"]
    require(post["source_heads"] == anchor["source_heads"] and post["tool_heads"] == anchor["tool_heads"],
            f"{cell.path}: refresh changed an initial source/tool head")
    unavailable_sources = {name for name, value in case["sources"].items() if value is None}
    expected_missing_messages = {f"Source no longer available: source:{name}" for name in unavailable_sources}
    error = raw["refresh_error"]
    expected_refusal = bool(error and error["type"] == "MissingEvidenceError" and
                            error["message"] in expected_missing_messages and case["errors"])
    require(raw["expected_source_unavailable_refusal"] == expected_refusal
            and raw["unexpected_refresh_error"] == bool(error and not expected_refusal),
            f"{cell.path}: runtime refusal/error classification differs")
    audit = audit_provenance(
        case["declarations"], post["records"], post["artifact_heads"], post["source_heads"], post["tool_heads"],
        case["sources"], case["tools"], prior_records=anchor["records"],
    )
    require(load(audit_path) == audit and audit["immutable_anchor_pass"] is True,
            f"{cell.path}: regenerated audit differs or an original record changed")
    verified = aggregate_verified_outcome(
        raw, audit, post, anchor, case["candidates"], case["affected"], case["values"], case["errors"],
        case["truth"]["reports"], unavailable_sources,
    )
    require(all(result[key] == value for key, value in verified.items()),
            f"{cell.path}: saved scorer differs from the pure verified aggregation")
    stale = independent_provenance(post, case["truth"], cell.path.as_posix())
    for item in verified["verified_artifacts"]:
        name = item["name"]
        logical = f"artifact:{name}"
        head = post["records"][post["artifact_heads"][logical]]
        expected_value = case["truth"]["values"][name]
        require(item["provenance_current"] == (not stale[name]) and item["head_id"] == head["id"]
                and item["numeric_match"] == (expected_value is not None and head["value"] == expected_value)
                and item["expected_revalidation"] == (name in case["truth"]["affected"]),
                f"{cell.path}: independent receipt-chain or value disagreement for {name}")
    counts = verified["verified_reports_counts"]
    oracle = case["oracle"]["counts"]
    require((counts["eligible_affected"], counts["unavailable"], counts["unaffected"]) ==
            (oracle["eligible_affected_reports"], oracle["unavailable_reports"], oracle["unaffected_reports"]),
            f"{cell.path}: retained score differs from the frozen denominators")
    return {
        "whole_case_correct": verified["absolute_correct"] and (cell.case_id != "M08" or not selected),
        "verified_report_counts": counts, "verified_artifact_counts": verified["verified_artifacts_counts"],
        "verified_artifacts": verified["verified_artifacts"],
        "independent_global_validation": verified["independent_global_validation"],
        "scoring_errors": verified["scoring_errors"], "refresh_error": error,
        "inspection_errors": raw["inspection_errors"], "refresh_tool_calls": raw["tool_calls"],
        "refresh_graph_queries": raw["refresh_graph_queries"], "expected_missing_source_refusal": expected_refusal,
        "safe_empty_missing_selection": cell.case_id == "M07" and not selected and verified["absolute_correct"],
        "retained_scoring_result_sha256": sha(raw_path.read_bytes()),
        "post_snapshot_sha256": result["post_snapshot_sha256"],
        "independent_audit_sha256": result["independent_audit_sha256"],
    }


def recover(public: Path, private: Path, publication: Path, model_cache: Path,
            manifest_sha256: str, summary_sha256: str) -> None:
    require(not publication.exists(), "Use a new recovery publication directory")
    frozen_path = REPO / FREEZE
    frozen = load(frozen_path)
    verify_frozen_inputs(FROZEN_REVISION, frozen, FROZEN_MANIFEST_SHA256)
    inventory = original_inventory(public)
    require(inventory["run_manifest.json"] == manifest_sha256 and inventory["summary.json"] == summary_sha256,
            "Original manifest or summary does not match its previously recorded digest")
    manifest, original = load(public / "run_manifest.json"), load(public / "summary.json")
    require(manifest["finished"] and manifest["freeze_sha256"] == FROZEN_MANIFEST_SHA256
            and manifest["approved_frozen_revision"] == FROZEN_REVISION and manifest["generative_provider_invocations"] == 0
            and len(manifest["planned_cells"]) == 88 and not original["complete"]
            and original["status_counts"] == {"execution_failed": 88} and original["freeze_integrity_verified"]
            and all(item["source_integrity_verified"] and item["resource_integrity_verified"] and item["stop_error"] is None
                    for item in (manifest, original)), "Run manifest and original outcome do not match the retained case")
    require(version("tiktoken") == frozen["package_versions"]["tiktoken"], "Installed tokenizer differs from the freeze")
    _, token_cache = verify_cached_inputs(model_cache, frozen)
    os.environ["TIKTOKEN_CACHE_DIR"] = token_cache
    counter = TokenCounter(ENCODING)
    cases = verified_cases(public, frozen, counter)
    expected_scores = {private / cell.path / "execution/scoring_result.json" for cell in schedule()}
    require(set(private.rglob("scoring_result.json")) == expected_scores, "Retained raw scorer file inventory differs")

    rows, planning_ends, execution_starts = {}, [], []
    previous_execution_end = None
    for cell, planned in zip(schedule(), manifest["planned_cells"], strict=True):
        directory = public / cell.path
        row = load(directory / "attempt.json")
        case = cases[cell.case_id]
        require(all(row[key] == value == planned[key] for key, value in cell.identity().items())
                and row["status"] == "execution_failed" and row["execution_error"] == WRAPPER_ERROR
                and row["planned_report_counts"] == planned["planned_report_counts"] == case["oracle"]["counts"],
                f"{cell.path}: original row differs from its registered attempt")
        started, planned_at, execution_at, finished = (
            datetime.fromisoformat(row[key]) for key in
            ("planning_started_at", "planning_finished_at", "execution_started_at", "execution_finished_at")
        )
        require(started <= planned_at <= execution_at <= finished
                and (previous_execution_end is None or previous_execution_end <= execution_at),
                f"{cell.path}: original attempt order differs from the schedule")
        planning_ends.append(planned_at)
        execution_starts.append(execution_at)
        previous_execution_end = finished
        verify_context(cell, row, directory, case, counter)
        score = verify_score(cell, row, private / cell.path / "execution", case)
        rows[cell] = {
            **row, "status": "scored", "score": score, "frozen_wrapper_status": row["status"],
            "original_attempt_sha256": inventory[(cell.path / "attempt.json").as_posix()],
        }
    require(max(planning_ends) <= min(execution_starts), "An execution started before all contexts were fixed")
    verify_frozen_inputs(FROZEN_REVISION, frozen, FROZEN_MANIFEST_SHA256)
    require(original_inventory(public) == inventory, "Original run evidence changed during recovery")
    summary = summarize(rows, frozen["oracle"], True)
    require(summary["complete"] and summary["graph_exact_flat_context_parity"] ==
            original["graph_exact_flat_context_parity"], "Recovered row inventory or Graph/flat context parity differs")
    summary["all_retained_scores_verified"] = summary.pop("complete")
    summary["status_counts"] = {"recovered_observation": len(rows)}
    summary.update(original_frozen_run_complete=original["complete"], original_status_counts=original["status_counts"],
                   original_wrapper_error=WRAPPER_ERROR, approved_frozen_revision=FROZEN_REVISION,
                   frozen_manifest_sha256=FROZEN_MANIFEST_SHA256, recovery_parser_sha256=sha(Path(__file__).read_bytes()),
                   original_run_manifest_sha256=manifest_sha256, original_run_summary_sha256=summary_sha256)
    for group in summary["groups"]:
        group["absolute_report_conditions_met_in_retained_scores"] = group.pop("absolute_report_gate")
        group["status_counts"] = {"recovered_observation": group["scored_cells"]}
    publication.mkdir(parents=True, exist_ok=False)
    store_json(publication / "recovered_summary.json", summary, new=True)
    store_json(publication / "original_evidence_sha256.json", inventory, new=True)
    with (publication / "recovered_cells.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows.values():
            stream.write(canonical({**row, "status": "recovered_observation"}) + "\n")
    print(json.dumps({"recovered_observations": len(rows), "original_frozen_run_complete": original["complete"],
                      "original_status_counts": original["status_counts"]}, sort_keys=True))


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--private-execution", type=Path, required=True)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--model-cache", type=Path, default=REPO / ".cache/fastembed")
    parser.add_argument("--original-manifest-sha256", default=ORIGINAL_MANIFEST_SHA256,
                        help="Archived manifest digest, or the recorded digest of a distinct reproduction")
    parser.add_argument("--original-summary-sha256", default=ORIGINAL_SUMMARY_SHA256,
                        help="Archived summary digest, or the recorded digest of a distinct reproduction")
    args = parser.parse_args()
    recover(args.original.resolve(), args.private_execution.resolve(), args.publication.resolve(), args.model_cache.resolve(),
            args.original_manifest_sha256, args.original_summary_sha256)


if __name__ == "__main__":
    main()
