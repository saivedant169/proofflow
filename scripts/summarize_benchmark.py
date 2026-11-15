#!/usr/bin/env python3
"""Publish a complete pilot run without importing its retrieval/scoring code.

This reader checks raw row completeness and recalculates aggregate execution
counts from the per-report observations. It refuses unfinished or partial runs.
It does not run tools, query HydraDB, alter outcomes, or select favorable cases.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORDER = ["bm25", "dense", "hybrid", "iterative_hybrid", "graph", "exact_flat",
         "direct_id", "graph_direct", "full_context"]
LABELS = {"bm25": "BM25", "dense": "Dense BGE", "hybrid": "Hybrid RRF",
          "iterative_hybrid": "Iterative hybrid", "graph": "ProofFlow / HydraDB",
          "exact_flat": "Exact flat traversal", "direct_id": "Direct ID",
          "graph_direct": "Hydra direct only", "full_context": "All-record context"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def retrieval_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scenarios": len(rows),
        "exact_affected_sets": sum(bool(row["impact"]["exact_match"]) for row in rows),
        "mean_precision": mean(row["impact"]["precision"] for row in rows),
        "mean_recall": mean(row["impact"]["recall"] for row in rows),
        "mean_f1": mean(row["impact"]["f1"] for row in rows),
        "true_positives": sum(row["impact"]["tp"] for row in rows),
        "false_positives": sum(row["impact"]["fp"] for row in rows),
        "false_negatives": sum(row["impact"]["fn"] for row in rows),
        "mean_context_tokens": mean(row["context_tokens"] for row in rows),
        "mean_retrieval_ms": mean(row["retrieval_ms"] for row in rows),
        "total_retrieval_calls": sum(row["retrieval_calls"] for row in rows),
    }


def execution_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = defaultdict(int)
    for row in rows:
        reports = row["reports"]
        eligible = [report for report in reports if report["oracle_available"]]
        affected = [report for report in eligible if report["expected_revalidation"]]
        unavailable = [report for report in reports if not report["oracle_available"]]
        unaffected = [report for report in reports if not report["expected_revalidation"]]
        recomputed = {
            "report_count": len(reports),
            "eligible_reports": len(eligible),
            "complete_fresh_reports": sum(report["fresh_complete"] for report in eligible),
            "eligible_affected_reports": len(affected),
            "fresh_affected_reports": sum(report["fresh_complete"] for report in affected),
            "oracle_unavailable_reports": len(unavailable),
            "correctly_blocked_reports": sum(report["correctly_blocked"] for report in unavailable),
            "incorrect_current_reports": sum(report["state"] == "current"
                and (not report["oracle_available"] or report["value_matches_oracle"] is False)
                for report in reports),
            "unaffected_reports": len(unaffected),
            "unaffected_report_artifacts_preserved": sum(report["preserved_original_artifact"]
                                                        for report in unaffected),
            "tool_calls": len(row["calls"]),
        }
        for key, value in recomputed.items():
            require(row[key] == value, f"Execution count mismatch: {row['scenario']} {row['arm']} {key}")
            counts[key] += value
        all_eligible = bool(eligible) and all(report["fresh_complete"] for report in eligible)
        require(row["all_eligible_reports_fresh"] == all_eligible,
                f"All-fresh mismatch: {row['scenario']} {row['arm']}")
        counts["scenarios_all_eligible_reports_fresh"] += all_eligible
        counts["scenarios_refresh_completed"] += row["refresh_completed"]
        counts["scenarios_with_refresh_error"] += row["refresh_error"] is not None
        counts["inspection_errors"] += len(row["inspection_errors"])
        counts["refresh_graph_queries"] += row["refresh_graph_queries"]
        counts["inspection_graph_queries"] += row["inspection_graph_queries"]
    return {"scenarios": len(rows), **dict(counts),
            "mean_refresh_ms": mean(row["refresh_elapsed_ms"] for row in rows)}


def build_report(directory: Path) -> dict[str, Any]:
    manifest_path = directory / "run_manifest.json"
    manifest = read_json(manifest_path)
    require(bool(manifest.get("finished_at")), "Benchmark is unfinished; no final report can be published")
    require(not manifest.get("partial_run", True), "Refusing a partial run as a complete benchmark")
    require(manifest["split"] == "test", "This report is reserved for the held-out test split")
    scenarios = manifest["scenarios"]
    require(len(scenarios) == len(set(scenarios)), "Duplicate manifest scenarios")
    require(set(scenarios) == {f"T{i:02d}" for i in range(1, 13)}, "The complete pilot requires all twelve frozen test scenarios")
    config = manifest["configuration"]
    retrieval_rows = read_rows(directory / "retrieval.jsonl")
    execution_rows = read_rows(directory / "execution.jsonl")
    retrieval_groups = defaultdict(list)
    execution_groups = defaultdict(list)
    for row in retrieval_rows:
        require(row["split"] == "test", "Unexpected retrieval split")
        require(row["fixture_manifest_sha256"] == manifest["fixture_manifest_sha256"], "Retrieval manifest mismatch")
        retrieval_groups[(row["arm"], str(row["budget"]))].append(row)
    for row in execution_rows:
        require(row["split"] == "test", "Unexpected execution split")
        require(row["fixture_manifest_sha256"] == manifest["fixture_manifest_sha256"], "Execution manifest mismatch")
        expected_budget = "all" if row["arm"] == "full_context" else config["main_budget"]
        require(row["budget"] == expected_budget, "Execution budget differs from the main comparison")
        execution_groups[row["arm"]].append(row)
    expected_groups = {(arm, str(budget)) for arm in ORDER if arm != "full_context"
                       for budget in [*config["budgets"], "all"]} | {("full_context", "all")}
    require(set(retrieval_groups) == expected_groups, "Missing or unexpected retrieval arm/budget group")
    require(set(execution_groups) == set(config["execution_arms"]), "Missing or unexpected execution arm")
    for key, rows in [*retrieval_groups.items(), *execution_groups.items()]:
        require(len(rows) == len(scenarios) and {row["scenario"] for row in rows} == set(scenarios),
                f"Missing or duplicate scenario in {key}")
    retrieval = {arm: {str(budget): retrieval_summary(retrieval_groups[(arm, str(budget))])
                       for budget in [*config["budgets"], "all"]
                       if (arm, str(budget)) in retrieval_groups} for arm in ORDER}
    execution = {arm: execution_summary(execution_groups[arm]) for arm in ORDER if arm in execution_groups}
    by_case = {}
    for scenario in scenarios:
        case = read_json(directory / scenario / "case.json")
        by_case[scenario] = {
            "description": case["scenario"]["description"],
            "category": case["scenario"]["category"],
            "corpus_tokens": case["corpus_tokens"],
            "corpus_records": case["corpus_records"],
            "retrieval": {row["arm"]: {"impact": row["impact"], "context_tokens": row["context_tokens"]}
                          for row in retrieval_rows if row["scenario"] == scenario and row["budget"] == config["main_budget"]},
            "execution": {row["arm"]: {key: row[key] for key in [
                "fresh_affected_reports", "eligible_affected_reports", "complete_fresh_reports",
                "eligible_reports", "correctly_blocked_reports", "oracle_unavailable_reports",
                "tool_calls", "refresh_error", "incorrect_current_reports"]}
                for row in execution_rows if row["scenario"] == scenario},
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_directory": str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory),
        "source_sha256": {name: digest(directory / name) for name in ["run_manifest.json", "retrieval.jsonl", "execution.jsonl"]},
        "run_manifest": manifest,
        "scenarios": scenarios,
        "retrieval": retrieval,
        "execution": execution,
        "by_case": by_case,
        "scope": "Twelve authored scenarios; deterministic evidence reader plus actual tool refresh, not an LLM-agent evaluation.",
        "shared_executor": "All arms use the same Hydra-assisted currentness and recursive refresh executor. Standalone baseline safety is not evaluated.",
    }


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def markdown(report: dict[str, Any]) -> str:
    manifest = report["run_manifest"]
    budget = str(manifest["configuration"]["main_budget"])
    n = len(report["scenarios"])
    lines = ["# ProofFlow held-out pilot results", "",
        f"Complete `{manifest['configuration']['benchmark_version']}` run: **{n} authored held-out scenarios**, "
        f"finished {manifest['finished_at']}. This measures a deterministic evidence reader followed by actual analytics-tool refresh. "
        "No LLM participates in these results.", "",
        "All methods receive the same evidence records, direct dependency IDs, scope filtering, exact-ID seeding facility, "
        "and token budgets. Every refresh arm uses the same **Hydra-assisted currentness and recursive refresh executor**. "
        "This compares retrieval selectors within that executor; it does not compare standalone vector-versus-graph safety.", "",
        f"## Main comparison: {int(budget):,} evidence tokens", "",
        "Fresh affected reports count only reports that require revalidation and have an available independent numeric oracle. "
        "The all-fresh scenario column covers all oracle-available reports, including unaffected reports. A blocked report "
        "with a missing source is excluded from both fresh-report denominators and reported separately below.", "",
        "| Method | Exact affected sets | Mean precision | Mean recall | Fresh affected reports | Scenarios with all eligible reports fresh | Mean context tokens | Actual tool calls |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ORDER:
        if arm not in report["execution"] or arm == "full_context":
            continue
        r, e = report["retrieval"][arm][budget], report["execution"][arm]
        lines.append(f"| {LABELS[arm]} | {r['exact_affected_sets']}/{n} | {pct(r['mean_precision'])} | "
                     f"{pct(r['mean_recall'])} | {e['fresh_affected_reports']}/{e['eligible_affected_reports']} | "
                     f"{e['scenarios_all_eligible_reports_fresh']}/{n} | {r['mean_context_tokens']:.0f} | {e['tool_calls']} |")
    graph, flat = report["retrieval"]["graph"][budget], report["retrieval"]["exact_flat"][budget]
    same_selection_metrics = all(graph[key] == flat[key] for key in ["exact_affected_sets", "true_positives", "false_positives", "false_negatives"])
    same_execution = all(report["execution"]["graph"][key] == report["execution"]["exact_flat"][key]
                         for key in ["fresh_affected_reports", "tool_calls", "incorrect_current_reports"])
    lines += ["", "Precision and recall score the affected-artifact set identified by the common deterministic reader from the selected records; "
              "they are not raw top-k document-relevance scores. The reader follows only explicit paths present in its context.", "",
              "The exact flat dependency-traversal control " +
              ("ties ProofFlow on these selection and execution metrics." if same_selection_metrics and same_execution
               else "does not match ProofFlow on every selection/execution metric; inspect the complete raw rows.") +
              " Explicit dependency structure is the intervention; this pilot does not establish an exclusive advantage of the HydraDB storage engine.", "",
              "Tool-call totals include recursively refreshed prerequisites. Fewer calls are not better when required reports remain unresolved. "
              "Unselected stale/unknown reports are withheld by the common executor, not counted as incorrect answers served.", "",
              "## Full evidence-budget ladder", "",
              "Each cell is **exact affected sets / scenarios; mean recall; mean context tokens**. “All” removes the evidence-token limit. "
              "Direct-ID and Hydra-direct conditions are ablations and do not have separate refresh experiments.", "",
              "| Method | 512 tokens | 1,024 tokens | 2,048 tokens | Unlimited evidence budget |", "|---|---:|---:|---:|---:|"]
    for arm in ORDER:
        cells = []
        for key in ["512", "1024", "2048", "all"]:
            r = report["retrieval"][arm].get(key)
            cells.append(f"{r['exact_affected_sets']}/{n}; {pct(r['mean_recall'])}; {r['mean_context_tokens']:.0f}" if r else "—")
        lines.append(f"| {LABELS[arm]} | " + " | ".join(cells) + " |")
    full_r = report["retrieval"]["full_context"]["all"]
    full_e = report["execution"]["full_context"]
    lines += ["", f"The all-record control uses {full_r['mean_context_tokens']:.0f} mean evidence tokens, "
              f"refreshes {full_e['fresh_affected_reports']}/{full_e['eligible_affected_reports']} eligible affected reports "
              f"in {full_e['tool_calls']} tool calls, and reaches all eligible reports fresh in "
              f"{full_e['scenarios_all_eligible_reports_fresh']}/{n} scenarios.", "",
              "## Failures, blocking, and preserved work", "",
              "| Method | Correctly blocked / unavailable reports | Incorrect current reports | Unaffected report artifacts preserved | Refresh errors |", "|---|---:|---:|---:|---:|"]
    for arm, e in report["execution"].items():
        lines.append(f"| {LABELS[arm]} | {e['correctly_blocked_reports']}/{e['oracle_unavailable_reports']} | "
                     f"{e['incorrect_current_reports']} | {e['unaffected_report_artifacts_preserved']}/{e['unaffected_reports']} | "
                     f"{e['scenarios_with_refresh_error']} |")
    lines += ["", "Missing-source errors are preserved in the raw execution rows. Correct blocking is a safety outcome, "
              "not a successfully completed report. Inspection failures, if any, are separately recorded in the JSON summary.", "",
              "## Every held-out case", "",
              "Cells show **selected true affected / expected affected artifacts; fresh affected / eligible affected reports** "
              "at 2,048 tokens. A 0/0 fresh-report entry means no affected report has an available oracle; consult the blocking table.", "",
              "| Case | BM25 | Dense BGE | Iterative hybrid | ProofFlow |", "|---|---:|---:|---:|---:|"]
    for scenario, case in report["by_case"].items():
        cells = []
        for arm in ["bm25", "dense", "iterative_hybrid", "graph"]:
            r, e = case["retrieval"][arm]["impact"], case["execution"][arm]
            cells.append(f"{r['tp']}/{r['tp'] + r['fn']}; {e['fresh_affected_reports']}/{e['eligible_affected_reports']}")
        lines.append(f"| {scenario} | " + " | ".join(cells) + " |")
    lines += ["", "## Reproduce and inspect", "",
              f"- Frozen code: [`{manifest['code']['revision'][:7]}`](https://github.com/saivedant169/proofflow/tree/{manifest['code']['revision']}).",
              f"- Case/configuration manifest SHA-256: `{manifest['fixture_manifest_sha256']}`.",
              "- Dense model: `BAAI/bge-small-en-v1.5`, real FastEmbed ONNX embeddings, overlapping tokenizer-aware chunks; hashes are in the run manifest.",
              "- [Raw run manifest](../results/test-v1/run_manifest.json), [retrieval rows](../results/test-v1/retrieval.jsonl), [execution rows](../results/test-v1/execution.jsonl).",
              "- [Machine-readable summary](../evidence/benchmark_summary.json) and [methodology](BENCHMARK_SPEC.md).", "",
              "```sh", "uv run python -m proofflow.eval.runner --split test --allow-test --output results/test-reproduction",
              "uv run python scripts/summarize_benchmark.py --input results/test-reproduction", "```", "",
              "A reproduction needs the local HydraDB service and benchmark dependencies. The runner refuses to overwrite an existing run "
              "and refuses held-out execution with tracked/staged changes. The report generator refuses unfinished or partial runs.", "",
              "These twelve scenarios reuse an authored commerce workload and staged mutations. They do not establish statistical or universal "
              "superiority across domains. Results separate potential revalidation from actual numeric value changes. T12 uses a declared new "
              "composition and is not evidence that an agent independently discovered that composition. Application-reopen and database-container "
              "restart evidence are reported separately. Latencies are descriptive measurements on a shared development machine with concurrent work and include different index/query work; "
              "they are not a production throughput benchmark.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/test-v1")
    parser.add_argument("--markdown", type=Path, default=ROOT / "docs/BENCHMARK_RESULTS.md")
    parser.add_argument("--json", type=Path, default=ROOT / "evidence/benchmark_summary.json")
    args = parser.parse_args()
    report = build_report(args.input.resolve())
    for path in [args.markdown, args.json]:
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    args.markdown.write_text(markdown(report))
    print(json.dumps({"scenarios": len(report["scenarios"]), "markdown": str(args.markdown),
                      "json": str(args.json), "source": report["source_directory"]}))


if __name__ == "__main__":
    main()
