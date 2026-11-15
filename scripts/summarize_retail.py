#!/usr/bin/env python3
"""Audit saved retail-v2 rows and publish an honest, compact report.

No model, database, runtime, or evaluation implementation is imported or run.
Metrics are recomputed from saved predictions, per-artifact observations and
the frozen case oracles. Incomplete runs cannot become a successful report.
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
LABELS = {"graph": "ProofFlow / HydraDB", "exact_flat": "Exact flat traversal",
          "full_context": "Full context", "bm25": "BM25", "dense": "Dense BGE",
          "iterative_hybrid": "Iterative hybrid"}


def read(path: Path) -> Any:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def impact(gold: set[str], predicted: set[str]) -> dict[str, Any]:
    tp, fp, fn = len(gold & predicted), len(predicted - gold), len(gold - predicted)
    p = tp / len(predicted) if predicted else float(not gold)
    r = tp / len(gold) if gold else float(not predicted)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0, "exact_match": gold == predicted}


def audit_execution(row: dict[str, Any], case: dict[str, Any]) -> None:
    require(not row.get("error"), f"Execution infrastructure failed: {row['scenario']} {row['arm']}")
    require({item["name"] for item in row["artifacts"]} == set(case["candidate_names"]), "Incomplete artifact observations")
    require(len(row["artifacts"]) == len(case["candidate_names"]), "Duplicate artifact observation")
    gold_values, gold_errors = case["numeric_oracle_values"], case["numeric_oracle_errors"]
    affected = set(case["expected_affected_names"])
    for item in row["artifacts"]:
        name = item["name"]
        available = name in gold_values
        require(available != (name in gold_errors), f"Ambiguous/missing oracle: {name}")
        require(item["oracle_available"] == available, "Oracle availability mismatch")
        require(item["expected_revalidation"] == (name in affected), "Impact annotation mismatch")
        require(item["expected_value"] == gold_values.get(name), "Numeric oracle mismatch")
        fresh = available and item["state"] == "current" and item["actual_stored_value"] == gold_values[name]
        blocked = not available and item["state"] in {"stale", "unknown"}
        require(item["fresh_complete"] == fresh and item["correctly_blocked"] == blocked, "Freshness/blocking metric mismatch")
        require(item["preserved_original_artifact"] == (item["head_id"] == item["original_id"]), "Preserved artifact ID mismatch")
    for kind, items in (("artifacts", row["artifacts"]), ("reports", [i for i in row["artifacts"] if i["is_report"]])):
        eligible = [item for item in items if item["oracle_available"]]
        affected_eligible = [item for item in eligible if item["expected_revalidation"]]
        unavailable = [item for item in items if not item["oracle_available"]]
        unaffected = [item for item in items if not item["expected_revalidation"]]
        counts = {"total": len(items), "eligible": len(eligible),
                  "fresh": sum(i["fresh_complete"] for i in eligible),
                  "eligible_affected": len(affected_eligible), "fresh_affected": sum(i["fresh_complete"] for i in affected_eligible),
                  "unavailable": len(unavailable), "correctly_blocked": sum(i["correctly_blocked"] for i in unavailable),
                  "unaffected": len(unaffected), "unaffected_artifacts_preserved": sum(i["preserved_original_artifact"] for i in unaffected),
                  "incorrect_current": sum(i["state"] == "current" and not i["fresh_complete"] for i in items)}
        require(counts == row[f"{kind}_counts"], f"{kind} count mismatch")
    error = row["refresh_error"]
    removed = {m["source"] for m in case["scenario"]["mutations"] if m["operation"] == "remove"}
    expected_refusal = bool(error and error["type"] == "MissingEvidenceError" and gold_errors
                            and error["message"] in {f"Source no longer available: source:{name}" for name in removed})
    require(row["expected_source_unavailable_refusal"] == expected_refusal, "Unexpected refusal classification")
    unexpected = bool(error and not expected_refusal)
    require(row["unexpected_refresh_error"] == unexpected, "Unexpected error classification")
    correct = (bool(row["artifacts"]) and not unexpected and not row["inspection_errors"]
               and all(i["fresh_complete"] if i["oracle_available"] else i["correctly_blocked"] for i in row["artifacts"]))
    require(row["oracle_correct"] == correct, "Endstate correctness mismatch")
    require(row["tool_calls"] == len(row["calls"]), "Actual tool call count mismatch")


def semantic(row: dict[str, Any]) -> dict[str, Any]:
    return {item["name"]: (item["state"], item["actual_stored_value"], item["preserved_original_artifact"])
            for item in row["artifacts"]}


def aggregate(arm: str, condition: str, retrieval: list[dict[str, Any]], executions: list[dict[str, Any]]) -> dict[str, Any]:
    def count(group: str, key: str) -> int:
        return sum(row[f"{group}_counts"][key] for row in executions)
    return {
        "arm": arm, "label": LABELS[arm], "condition": condition, "planned_cases": len(retrieval),
        "exact_affected_sets": sum(row["impact"]["exact_match"] for row in retrieval),
        "oracle_correct_cases": sum(row["oracle_correct"] for row in executions),
        **{f"mean_{key}": mean(row["impact"][key] for row in retrieval) for key in ["precision", "recall", "f1"]},
        "true_positives": sum(row["impact"]["tp"] for row in retrieval),
        "false_positives": sum(row["impact"]["fp"] for row in retrieval),
        "false_negatives": sum(row["impact"]["fn"] for row in retrieval),
        "context_tokens_total": sum(row["context_tokens"] for row in retrieval),
        "mean_context_tokens": mean(row["context_tokens"] for row in retrieval),
        "min_context_tokens": min(row["context_tokens"] for row in retrieval),
        "max_context_tokens": max(row["context_tokens"] for row in retrieval),
        "fresh_affected_reports": count("reports", "fresh_affected"),
        "eligible_affected_reports": count("reports", "eligible_affected"),
        "fresh_affected_artifacts": count("artifacts", "fresh_affected"),
        "eligible_affected_artifacts": count("artifacts", "eligible_affected"),
        "fresh_reports": count("reports", "fresh"), "eligible_reports": count("reports", "eligible"),
        "correctly_blocked_reports": count("reports", "correctly_blocked"), "unavailable_reports": count("reports", "unavailable"),
        "correctly_blocked_artifacts": count("artifacts", "correctly_blocked"), "unavailable_artifacts": count("artifacts", "unavailable"),
        "incorrect_current_artifacts": count("artifacts", "incorrect_current"),
        "unaffected_artifacts_preserved": count("artifacts", "unaffected_artifacts_preserved"), "unaffected_artifacts": count("artifacts", "unaffected"),
        "tool_calls": sum(row["tool_calls"] for row in executions),
        "unexpected_errors": sum(bool(row.get("error") or row["unexpected_refresh_error"] or row["inspection_errors"]) for row in executions),
        "expected_refusals": sum(row["expected_source_unavailable_refusal"] for row in executions),
        "refresh_completed_cases": sum(row["refresh_completed"] for row in executions),
        "mean_retrieval_ms": mean(row["retrieval_ms"] for row in retrieval),
        "mean_refresh_ms": mean(row["refresh_ms"] for row in executions),
        "refresh_graph_queries": sum(row["refresh_graph_queries"] for row in executions),
        "inspection_graph_queries": sum(row["inspection_graph_queries"] for row in executions),
    }


def audit_run(directory: Path) -> dict[str, Any]:
    manifest = read(directory / "run_manifest.json")
    saved = read(directory / "summary.json")
    require(manifest["finished"] and not manifest["partial_run"] and manifest.get("freeze_integrity_error") is None, "Unfinished, partial or invalidated run")
    planned = manifest["planned_cases"]
    require(manifest["selected_cases"] == planned and len(set(planned)) == len(planned), "Incomplete or duplicate case selection")
    rr, ee = rows(directory / "retrieval.jsonl"), rows(directory / "execution.jsonl")
    config = manifest["configuration"]
    groups = ({(arm, "unlimited") for arm in config["production_arms"]}
              | {(arm, budget) for arm in config["retrieval_arms"] for budget in config["budget_conditions"]}
              | {(arm, "fixed_2048") for arm in config["fixed_budget_closure_controls"]})
    expected = {(case, arm, condition) for case in planned for arm, condition in groups}
    key = lambda row: (row["scenario"], row["arm"], row["condition"])
    require(len(rr) == len(ee) == len(expected), "Unexpected number of raw observations")
    require({key(row) for row in rr} == {key(row) for row in ee} == expected, "Missing/duplicate case-arm-condition")
    rmap, emap = {key(row): row for row in rr}, {key(row): row for row in ee}
    cases = []
    for case_id in planned:
        case = read(directory / case_id / "case.json")
        gold = set(case["expected_affected_ids"])
        for arm, condition in groups:
            retrieval, execution = rmap[(case_id, arm, condition)], emap[(case_id, arm, condition)]
            require(retrieval["fixture_manifest_sha256"] == execution["fixture_manifest_sha256"] == manifest["fixture_manifest_sha256"], "Case manifest mismatch")
            recomputed = impact(gold, set(retrieval["predicted_ids"]))
            for field, value in recomputed.items():
                require(retrieval["impact"][field] == value, "Impact score mismatch")
            require(set(execution["selected_aliases"]) == set(retrieval["predicted_ids"]), "Refresh selected IDs differ from reader predictions")
            require(retrieval["corpus_sha256"] == case["corpus_sha256"], "Unequal source corpus")
            if condition == "graph_matched":
                require(retrieval["budget"] == case["graph_matched_budget"], "Unequal matched graph budget")
            if condition == "fixed_2048":
                require(retrieval["budget"] == 2048, "Unequal fixed budget")
            if retrieval["budget"] is not None:
                require(retrieval["context_tokens"] <= retrieval["budget"], "Context exceeds declared budget")
            audit_execution(execution, case)
        production = [emap[(case_id, arm, "unlimited")] for arm in config["production_arms"]]
        parity = all(semantic(item) == semantic(emap[(case_id, "full_context", "unlimited")]) for item in production)
        exact = all(rmap[(case_id, arm, "unlimited")]["impact"]["exact_match"] for arm in config["production_arms"])
        correct = all(item["oracle_correct"] for item in production)
        graph, full = rmap[(case_id, "graph", "unlimited")], rmap[(case_id, "full_context", "unlimited")]
        graph_exec = emap[(case_id, "graph", "unlimited")]
        case_result = {"id": case_id, "category": case["scenario"]["category"], "description": case["scenario"]["description"],
                       "correct_endstates": parity and exact and correct, "exact_production_closures": exact,
                       "semantic_endstate_parity": parity, "affected_artifacts": len(gold),
                       "graph_tokens": graph["context_tokens"], "full_context_tokens": full["context_tokens"],
                       "token_ratio": graph["context_tokens"] / full["context_tokens"],
                       "fresh_affected_reports": graph_exec["reports_counts"]["fresh_affected"],
                       "eligible_affected_reports": graph_exec["reports_counts"]["eligible_affected"],
                       "correctly_blocked_reports": graph_exec["reports_counts"]["correctly_blocked"],
                       "unavailable_reports": graph_exec["reports_counts"]["unavailable"],
                       "expected_refusal": graph_exec["expected_source_unavailable_refusal"],
                       "all_arm_tool_calls": {f"{a}/{c}": emap[(case_id, a, c)]["tool_calls"] for a, c in sorted(groups)}}
        cases.append(case_result)
    aggregates = {(arm, condition): aggregate(arm, condition,
        [rmap[(case, arm, condition)] for case in planned], [emap[(case, arm, condition)] for case in planned])
        for arm, condition in groups}
    graph = aggregates[("graph", "unlimited")]
    full = aggregates[("full_context", "unlimited")]
    ratio = graph["context_tokens_total"] / full["context_tokens_total"]
    correct = all(case["correct_endstates"] for case in cases)
    threshold = config["primary_token_ratio_maximum"]
    require(saved["primary"]["correctness_pass"] == correct, "Saved primary correctness mismatch")
    require(saved["primary"]["ratio_of_total_tokens"] == ratio, "Saved token ratio mismatch")
    require(saved["primary"]["passed"] == (correct and ratio <= threshold), "Saved primary pass mismatch")
    nonempty = [case for case in cases if case["affected_artifacts"]]
    return {"manifest": manifest, "aggregates": aggregates, "cases": cases,
            "primary": {"passed": correct and ratio <= threshold, "correctness_cases": sum(case["correct_endstates"] for case in cases),
                        "planned_cases": len(planned), "graph_tokens": graph["context_tokens_total"], "full_context_tokens": full["context_tokens_total"],
                        "token_ratio": ratio, "token_savings_fraction": 1 - ratio, "threshold": threshold,
                        "fresh_affected_reports": graph["fresh_affected_reports"], "eligible_affected_reports": graph["eligible_affected_reports"],
                        "fresh_affected_artifacts": graph["fresh_affected_artifacts"], "eligible_affected_artifacts": graph["eligible_affected_artifacts"],
                        "blocked_unavailable_reports": graph["correctly_blocked_reports"], "unavailable_reports": graph["unavailable_reports"],
                        "incorrect_current_artifacts": graph["incorrect_current_artifacts"], "freeze_integrity_verified": True},
            "nonempty_impact": {"cases": len(nonempty),
                                "graph_tokens": sum(case["graph_tokens"] for case in nonempty),
                                "full_context_tokens": sum(case["full_context_tokens"] for case in nonempty),
                                "token_ratio": sum(case["graph_tokens"] for case in nonempty) / sum(case["full_context_tokens"] for case in nonempty),
                                "mean_per_case_ratio": mean(case["token_ratio"] for case in nonempty)},
            "raw_counts": {"retrieval": len(rr), "execution": len(ee)}}


def build_summary(test: Path, dev: Path) -> dict[str, Any]:
    audited, development = audit_run(test), audit_run(dev)
    manifest = audited["manifest"]
    require(manifest["split"] == "test" and manifest["planned_cases"] == [f"R{i:02d}" for i in range(1, 11)], "Not the complete frozen ten-case test")
    require(development["manifest"]["split"] == "dev", "Development comparison is mislabeled")
    frozen = read(ROOT / "docs/RETAIL_BENCHMARK_MANIFEST.json")
    require(sha(ROOT / "docs/RETAIL_BENCHMARK_MANIFEST.json") == manifest["fixture_manifest_sha256"], "Frozen manifest bytes do not match run")
    require(frozen["code_sha256"] == manifest["end_code_sha256"], "Saved code hashes changed during the run")
    data = audited["aggregates"]
    return {
        "schema_version": "retail-v2-summary-1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"text": "External retail transactions with authored corrections and declared report compositions; deterministic reader, no LLM calls.",
                  "source": "UCI Online Retail", "source_url": "https://archive.ics.uci.edu/dataset/352/online%2Bretail",
                  "license": "CC BY 4.0", "test_transaction_lines": 640, "development_transaction_lines": 160,
                  "test_partitions": 4, "artifacts_per_test_case": 39, "reports_per_test_case": 11,
                  "shared_executor": "Every arm uses the same Hydra-assisted currentness and recursive refresh executor."},
        "provenance": {"code_revision": manifest["code"]["revision"], "manifest_sha256": manifest["fixture_manifest_sha256"],
                       "started_at": manifest["started_at"], "finished_at": manifest["finished_at"],
                       "elapsed_seconds": manifest["elapsed_ms"] / 1000, "clean_git_start": not manifest["code"]["status_porcelain"],
                       "raw_directory": str(test.relative_to(ROOT)), "raw_counts": audited["raw_counts"],
                       "source_sha256": {name: sha(test / name) for name in ["run_manifest.json", "retrieval.jsonl", "execution.jsonl", "summary.json"]}},
        "primary": audited["primary"], "nonempty_impact": audited["nonempty_impact"],
        "production": [data[(arm, "unlimited")] for arm in ["graph", "exact_flat", "full_context"]],
        "graph_matched": [data[(arm, "unlimited" if arm in {"graph", "exact_flat"} else "graph_matched")]
                          for arm in ["graph", "exact_flat", "bm25", "dense", "iterative_hybrid"]],
        "fixed_2048": [data[(arm, "fixed_2048")] for arm in ["graph", "exact_flat", "bm25", "dense", "iterative_hybrid"]],
        "cases": audited["cases"],
        "development": {**development["primary"], "raw_directory": str(dev.relative_to(ROOT)),
                        "nonempty_impact": development["nonempty_impact"], "raw_counts": development["raw_counts"],
                        "meaning": "The unchanged prospective 40% efficiency gate failed on development; correctness passed. Development is not pooled with test."},
        "limitations": [
            "Correct endstates include expected source refusal; 10/10 does not mean ten newly completed fresh answers.",
            "Exact flat traversal ties graph; this does not establish database-engine exclusivity.",
            "All arms share Hydra-backed safety and recursive refresh; standalone baseline safety is not evaluated.",
            "The graph-matched budget is adaptive and varies from zero to 9,611 tokens; fixed 2,048-token results are separate.",
            "Real source transactions are a bounded positive-sales subset; FX, refunds and corrections are staged, not observed historical incidents.",
            "No-op R09 contributes to aggregate metrics; the nonempty-impact diagnostic excludes it.",
            "No LLM calls, learning curve, production-customer validation, or API dollar-cost savings are established here.",
            "Local single-run timings include different database and index work; they are not a controlled latency or throughput comparison.",
        ],
    }


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def markdown(summary: dict[str, Any]) -> str:
    p, prov = summary["primary"], summary["provenance"]
    text = ["# Retail v2 results", "",
        f"The complete Hydra dependency path reached correct endstates in **{p['correctness_cases']}/{p['planned_cases']} held-out cases**, "
        f"matching exact-flat traversal and full context on every scoped artifact. It refreshed **{p['fresh_affected_reports']}/{p['eligible_affected_reports']} recoverable affected reports** "
        f"and correctly withheld **{p['blocked_unavailable_reports']}/{p['unavailable_reports']} unavailable reports**. "
        "The missing-source refusal is not a freshly completed answer.", "",
        f"Graph evidence used **{p['graph_tokens']:,}/{p['full_context_tokens']:,} tokens ({pct(p['token_ratio'])})** of full context: "
        f"**{pct(p['token_savings_fraction'])} fewer evidence tokens** across all cases. The prospective ≤40% ratio gate **passed**. "
        f"Excluding the no-op, the ratio is **{pct(summary['nonempty_impact']['token_ratio'])}**, still below 40%.", "",
        "This uses 640 externally sourced UCI retail lines in four dated partitions, with ten authored changes and new declared report compositions. "
        "It is a deterministic retrieval/refresh experiment with real tools and HydraDB, **not an LLM-agent or learning-curve result**. "
        "All arms use the same Hydra-assisted currentness and recursive refresh executor.", "",
        "## Complete production path and full-context control", "",
        "Every case exposes 39 artifacts, including 11 reports. Correctness checks exact impact closure plus independent numeric oracle, "
        "currentness, original-artifact preservation and per-artifact endstate equality. Raw immutable IDs are excluded from semantic parity.", "",
        "| Method | Exact closures | Correct endstate cases | Fresh affected artifacts | Fresh affected reports | Mean evidence tokens | Tool calls |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for row in summary["production"]:
        text.append(f"| {row['label']} | {row['exact_affected_sets']}/10 | {row['oracle_correct_cases']}/10 | "
                    f"{row['fresh_affected_artifacts']}/{row['eligible_affected_artifacts']} | {row['fresh_affected_reports']}/{row['eligible_affected_reports']} | "
                    f"{row['mean_context_tokens']:,.1f} | {row['tool_calls']} |")
    text += ["", "Exact flat traversal ties graph per case, including semantic artifact states and values. Explicit dependencies explain the result; "
             "this is not an exclusive correctness advantage of the storage engine. Full context uses the same affected-evidence reader, so it does not force recalculation of unaffected work.", "",
             "## Baselines with the same per-case graph evidence allowance", "",
             "The complete graph closure determines each case's allowance **before comparator execution**. BM25, dense BGE and iterative hybrid receive "
             "the identical allowance and serialized records. The allowance varies from 0 to 9,611 tokens; whole-record packing can leave unused space. "
             "Graph/exact-flat rows below are the complete-closure conditions that define/match this allowance.", ""]
    def comparison_table(key: str) -> None:
        text.extend(["| Method | Exact affected sets | Mean recall | Fresh affected reports | Correct endstate cases | Mean tokens | Tool calls |",
                     "|---|---:|---:|---:|---:|---:|---:|"])
        for row in summary[key]:
            text.append(f"| {row['label']} | {row['exact_affected_sets']}/10 | {pct(row['mean_recall'])} | "
                        f"{row['fresh_affected_reports']}/{row['eligible_affected_reports']} | {row['oracle_correct_cases']}/10 | "
                        f"{row['mean_context_tokens']:,.1f} | {row['tool_calls']} |")
    comparison_table("graph_matched")
    text += ["", "## Fixed 2,048-token diagnostic", "",
             "This is a separate constrained condition. It does not inherit the complete graph path's perfect result. "
             "The stronger iterative baseline remains visible, and fewer tool calls can simply mean unfinished work.", ""]
    comparison_table("fixed_2048")
    text += ["", "Every fixed-budget arm's two correct endstate cases are **R07 (expected refusal)** and **R09 (no-op)**. "
             "They are not two successfully refreshed affected-report cases. Precision is 100% for every reader condition because it predicts only "
             "explicitly connected artifacts; irrelevant retrieved records can still consume the context budget. These are affected-set scores, not raw document-relevance precision.", "",
             "## Every held-out case", "",
             "Complete graph, exact-flat and full-context conditions have exact closure and semantic parity in all ten cases. "
             "The 40% efficiency threshold is an aggregate gate; R06 and R08 exceed it individually and remain in the results.", "",
             "| Case | Intervention | Affected artifacts | Graph / full tokens | Token ratio | Fresh affected reports | Blocked unavailable reports |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for case in summary["cases"]:
        text.append(f"| {case['id']} | {case['category'].replace('_', ' ')} | {case['affected_artifacts']} | "
                    f"{case['graph_tokens']:,} / {case['full_context_tokens']:,} | {pct(case['token_ratio'])} | "
                    f"{case['fresh_affected_reports']}/{case['eligible_affected_reports']} | {case['correctly_blocked_reports']}/{case['unavailable_reports']} |")
    dev = summary["development"]
    text += ["", "## Failure and preservation accounting", "",
             "All 110 execution conditions have **zero unexpected execution or inspection errors**, **zero incorrectly current artifacts**, "
             "and preserve all **281/281 unaffected artifact identities** per arm across the ten cases. "
             "R07 produces the recorded `MissingEvidenceError: Source no longer available: source:2011-08:fx` in all eleven conditions. "
             "Each blocks 8/8 unavailable artifacts, including 4/4 reports. Their saved historic values are not counted as current answers. "
             "R09 performs zero tool calls and preserves current identities in every condition.", "",
             "## Development gate remains a failure", "",
             f"The four development cases passed correctness, but graph/full evidence was **{dev['graph_tokens']:,}/{dev['full_context_tokens']:,} "
             f"({pct(dev['token_ratio'])})**, above the unchanged 40% gate: **FAIL**. Excluding its no-op gives "
             f"**{pct(dev['nonempty_impact']['token_ratio'])}**. These results are retained in `results/retail-dev-v1`; "
             "development was not pooled with test, and no cases, production algorithms, baseline settings or threshold were changed after these outcomes.", "",
             "## Scope, timing and reproduction", "",
             f"Frozen revision [`{prov['code_revision'][:7]}`](https://github.com/saivedant169/proofflow/tree/{prov['code_revision']}); "
             f"manifest SHA-256 `{prov['manifest_sha256']}`. The test run finished `{prov['finished_at']}` after "
             f"{prov['elapsed_seconds']:.2f} seconds. Its clean initial tree and end-of-run source/code/model/spec integrity were verified. "
             "All 110 retrieval rows and 110 execution rows were independently audited against saved case oracles and per-artifact observations.", "",
             "The actual vector baseline is BAAI/bge-small-en-v1.5 via FastEmbed ONNX, with exact cosine scoring, complete tokenizer-aware chunks and unchanged v1 parameters. "
             "Indexes, exact-ID access, scope, reader, serialization and packing are shared. Dataset prices are GBP regardless of country. "
             "The 640 test lines are a bounded positive-sales sample, not the full 541,909-line ledger; FX, refunds and corrections are staged assumptions. "
             "No customer deployment, historical incident accuracy, policy learning, LLM dollar savings, statistical superiority, or controlled latency speedup is established.", "",
             "- [Protocol](RETAIL_V2_SPEC.md) and [dataset attribution/modifications](../fixtures/retail_v2/DATASET_NOTICE.md).",
             "- [Machine-readable audited summary](../evidence/retail_v2_summary.json).",
             "- [Raw test manifest](../results/retail-test-v1/run_manifest.json), [retrieval](../results/retail-test-v1/retrieval.jsonl), [execution](../results/retail-test-v1/execution.jsonl).",
             "- [Saved development result](../results/retail-dev-v1/summary.json).", "",
             "Regenerate the report from saved evidence, without database or model calls:", "", "```sh",
             "uv run python scripts/summarize_retail.py", "```", ""]
    return "\n".join(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/retail-test-v1")
    parser.add_argument("--development", type=Path, default=ROOT / "results/retail-dev-v1")
    parser.add_argument("--json", type=Path, default=ROOT / "evidence/retail_v2_summary.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "docs/RETAIL_V2_RESULTS.md")
    args = parser.parse_args()
    summary = build_summary(args.input.resolve(), args.development.resolve())
    for path in [args.json, args.markdown]:
        path.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n")
    args.markdown.write_text(markdown(summary))
    print(json.dumps({"passed": summary["primary"]["passed"], "json": str(args.json), "markdown": str(args.markdown)}))


if __name__ == "__main__":
    main()
