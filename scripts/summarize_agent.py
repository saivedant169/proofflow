"""Render a conservative report from a completed frozen agent comparison.

This reads saved observations only. It does not call a model, retrieve evidence,
query HydraDB, modify the benchmark, or publish anything.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def fraction(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({100 * numerator / denominator:.1f}%)" if denominator else "0/0 (not applicable)"


def provider_evidence(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("plan", {}).get("provider_result") or row.get("provider_result")
    if result:
        return result
    raw = row.get("provider_evidence", {})
    return {"model_usage": raw.get("modelUsage") or {}, "usage": raw.get("usage") or {},
            "reported_cost_usd": raw.get("total_cost_usd"), "elapsed_seconds": raw.get("elapsed_seconds")}


def render(directory: Path) -> str:
    manifest = read_json(directory / "prepared.json")
    summary = read_json(directory / "summary.json")
    if not summary.get("finished_at"):
        raise ValueError("Refusing to report an unfinished comparison")
    rows = summary["results"]
    jobs = manifest["jobs"]
    expected = {(job["scenario"], job["arm"]) for job in jobs}
    observed = [(row["scenario"], row["arm"]) for row in rows]
    if len(observed) != len(jobs) or len(set(observed)) != len(observed) or set(observed) != expected:
        raise ValueError("Missing, repeated, or unexpected comparison observations")
    protocol = manifest["protocol"]
    if summary["protocol"] != protocol:
        raise ValueError("Protocol differs between prepared and finished comparison")
    arms = protocol["arms"]
    cases = protocol["cases"][manifest["split"]]
    labels = {"bm25": "BM25", "dense": "Dense", "iterative_hybrid": "Iterative hybrid", "graph": "Graph"}
    by_arm = {arm: [row for row in rows if row["arm"] == arm] for arm in arms}
    traces = [provider_evidence(row) for row in rows]
    actual_models = sorted({data.get("canonicalModel", key) for trace in traces
                            for key, data in trace.get("model_usage", {}).items() if isinstance(data, dict)})
    model_traces = sum(bool(trace.get("model_usage")) for trace in traces)
    known_costs = [trace["reported_cost_usd"] for trace in traces
                   if isinstance(trace.get("reported_cost_usd"), (int, float))]
    token_totals = {name: sum(data.get(name, 0) for trace in traces
                              for data in trace.get("model_usage", {}).values() if isinstance(data, dict))
                    for name in ("inputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "outputTokens", "thinkingTokens")}
    code_revision = manifest["code"]["revision"]
    failures = sum(row["status"] == "failed" for row in rows)
    abstentions = sum(row["status"] == "abstained" for row in rows)
    executions = [row["execution"] for row in rows if row.get("execution") is not None]
    score_failures = sum("execution_error" in row for row in rows)
    incorrect = sum(item["incorrect_current_reports"] for item in executions)
    affected_totals = {arm: (
        sum(row["execution"]["fresh_affected_reports"] for row in by_arm[arm] if row.get("execution")),
        sum(row["execution"]["eligible_affected_reports"] for row in by_arm[arm] if row.get("execution")),
    ) for arm in arms}
    path_label = directory.as_posix()
    lines = [
        "# Actual model comparison",
        "",
        "This is a small authored retrieval-and-refresh pilot: one frozen model planning step chooses among presented artifact receipts, then a shared safe executor runs the selected calculations. It does not evaluate an autonomous agent inventing workflows or establish universal graph-database superiority.",
        "",
        f"Completed **{len(rows)}/{len(jobs)} prespecified attempts** on {', '.join(cases)}. Model/planning failures: **{failures}**; abstentions: **{abstentions}**; scoring infrastructure failures: **{score_failures}**. These counts remain visible even when a conditional report-rate denominator excludes failed executions.",
        "",
        "Fresh affected reports after actual refresh: " + "; ".join(
            f"**{labels.get(arm, arm)} {fraction(*affected_totals[arm])}**" for arm in arms) + ". "
        + (f"Graph still left **{affected_totals['graph'][1] - affected_totals['graph'][0]}/{affected_totals['graph'][1]} recoverable affected reports unresolved**. " if "graph" in affected_totals else "")
        + "The full per-case results below retain ties, omissions, and missing-source blocking.",
        "",
        "## Frozen conditions",
        "",
        f"- Harness revision: `{code_revision}`; tracked changes at preparation: `{str(manifest['code']['tracked_changes']).lower()}`.",
        f"- Requested model: `{protocol['model']}`; reasoning effort: `{protocol['effort']}`. Provider-observed canonical model(s): {', '.join(f'`{model}`' for model in actual_models) or 'unavailable'}; usage trace available for {model_traces}/{len(rows)} attempts.",
        f"- Evidence budget: **{protocol['context_budget']} {protocol['tokenizer']} tokens** per arm. Exact frozen JSONL records, schema, and system prompt are shared; only retrieved records differ. The allowed selection IDs are exactly those presented.",
        "- BM25 and dense use the benchmark's exact-ID seeding; iterative hybrid is the stronger retrieval control. All arms see identical underlying receipts and source-change IDs. No gold labels or hidden candidate list enter the model prompt.",
        "- All model plans finish before any refresh. Each execution has private manifest heads/blob storage and shares immutable Hydra graph history. Every arm uses the same Hydra-assisted currentness checks and recursive refresh executor.",
        f"- One sample per case/arm, no retry or model fallback. Fixed rotation determines arm order. Per-call timeout: {protocol['timeout_seconds']} seconds; configured per-call budget: ${protocol['max_budget_usd_per_call']:.2f}.",
        "- Report recipes and arithmetic tools already exist. This tests context-driven selection and actual refresh, not model-created report composition.",
        "",
        "## Affected report completion",
        "",
        "The numerator counts affected reports that are both current and equal to an independent numeric oracle after refresh. The denominator counts affected reports with an available oracle in successfully scored executions. Missing-source cases have no recoverable oracle for the affected reports and appear separately below. Unaffected already-current reports do not inflate this primary rate.",
        "",
        "| Arm | Attempts | Model failures / abstentions | Scored executions | Fresh affected reports | Exact artifact selections | Actual tool calls |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        selected = by_arm[arm]
        scored = [row["execution"] for row in selected if row.get("execution") is not None]
        eligible = sum(item["eligible_affected_reports"] for item in scored)
        fresh = sum(item["fresh_affected_reports"] for item in scored)
        exact = sum(bool(row.get("impact", {}).get("exact_match")) for row in selected if row.get("impact"))
        lines.append(f"| {labels.get(arm, arm)} | {len(selected)} | {sum(row['status'] == 'failed' for row in selected)} / {sum(row['status'] == 'abstained' for row in selected)} | {len(scored)} | {fraction(fresh, eligible)} | {exact}/{len(selected)} | {sum(item['tool_calls'] for item in scored)} |")
    lines += [
        "",
        "Exact artifact selection is a secondary metric: the chosen IDs must equal the complete expected revalidation set. Selecting a terminal report can recursively refresh its prerequisites through the common executor; artifact selection and report completion therefore measure different behavior.",
        "",
        "## Every prespecified case and arm",
        "",
        "| Case | Arm | Plan status | Evidence tokens | Artifact precision / recall | Fresh affected reports | All eligible reports fresh | Correctly blocked unavailable reports | Tool calls |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case in cases:
        for arm in arms:
            row = next(row for row in rows if row["scenario"] == case and row["arm"] == arm)
            execution, impact = row.get("execution"), row.get("impact")
            if execution:
                affected = fraction(execution["fresh_affected_reports"], execution["eligible_affected_reports"])
                all_reports = fraction(execution["complete_fresh_reports"], execution["eligible_reports"])
                blocked = fraction(execution["correctly_blocked_reports"], execution["oracle_unavailable_reports"])
                calls = str(execution["tool_calls"])
            else:
                affected = all_reports = blocked = calls = "not scored"
            precision = f"{impact['precision']:.3f} / {impact['recall']:.3f}" if impact else "not scored"
            status = row["status"] + ("; scoring failed" if "execution_error" in row else "")
            lines.append(f"| {case} | {labels.get(arm, arm)} | {status} | {row['context_tokens_budgeted']} | {precision} | {affected} | {all_reports} | {blocked} | {calls} |")
    lines += [
        "",
        f"Across successfully scored executions, **{incorrect} incorrect-current reports** were observed. This safety result belongs to the shared Hydra-assisted executor. It is not evidence that standalone BM25 or vector systems are unsafe, nor that the graph planner uniquely handles missing sources.",
        "",
        "## Provider usage and failures",
        "",
        f"Known provider-reported list cost: **${sum(known_costs):.6f}** across {len(known_costs)}/{len(rows)} attempts. {len(rows) - len(known_costs)} attempts have unknown cost; unknown usage is never treated as zero spend. These are provider list estimates, not a subscription billing statement.",
        "",
        "| Arm | Known reported cost | Calls with unknown cost | Uncached input tokens | Cache-created input tokens | Cache-read input tokens | Output tokens | Thinking tokens (subset) | Model elapsed seconds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        evidence = [provider_evidence(row) for row in by_arm[arm]]
        known = [trace["reported_cost_usd"] for trace in evidence if isinstance(trace.get("reported_cost_usd"), (int, float))]
        tokens = {name: sum(data.get(name, 0) for trace in evidence for data in trace.get("model_usage", {}).values()
                           if isinstance(data, dict)) for name in token_totals}
        seconds = sum(trace.get("elapsed_seconds") or 0 for trace in evidence)
        lines.append(f"| {labels.get(arm, arm)} | ${sum(known):.6f} | {len(evidence) - len(known)} | {tokens['inputTokens']:,} | {tokens['cacheCreationInputTokens']:,} | {tokens['cacheReadInputTokens']:,} | {tokens['outputTokens']:,} | {tokens['thinkingTokens']:,} | {seconds:.2f} |")
    lines += [
        "",
        f"Provider-accounted input totals: {token_totals['inputTokens']:,} uncached + {token_totals['cacheCreationInputTokens']:,} cache-created + {token_totals['cacheReadInputTokens']:,} cache-read. Output totals: {token_totals['outputTokens']:,}, including {token_totals['thinkingTokens']:,} reported thinking tokens. Thinking tokens are not added a second time.",
        "",
        "The 2,048-token limit applies to retrieved evidence, not the entire Claude request. Provider counts include the system prompt, schema, CLI overhead, and caching; the saved cl100k prompt estimate is a separate tokenizer measurement. CLI-reported `num_turns` and full model/iteration usage remain in each observation; a single requested planning step need not equal the CLI's internal turn counter.",
        "",
        "Cache warmth was not experimentally controlled, and only one fixed rotation was run. The development graph smoke also warmed its later development prompt. No cost or latency superiority claim should be made from these measurements. The heldout source remains the prespecified four-case subset; development observations are not pooled into it.",
        "",
    ]
    errors = [row for row in rows if row["status"] == "failed" or "execution_error" in row
              or (row.get("execution") or {}).get("refresh_error")]
    if errors:
        lines += ["| Case | Arm | Failure location | Saved error |", "|---|---|---|---|"]
        for row in errors:
            if row["status"] == "failed":
                location, detail = "model / protocol", f"{row.get('error_type')}: {row.get('error')}"
            elif "execution_error" in row:
                location, detail = "scoring infrastructure", str(row["execution_error"])
            else:
                location, detail = "runtime refresh", str(row["execution"]["refresh_error"])
            detail = detail.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {row['scenario']} | {labels.get(row['arm'], row['arm'])} | {location} | {detail} |")
        lines += ["", "A missing-source runtime refresh failure can be the correct fail-closed behavior; it remains recorded instead of being converted into a successful calculation.", ""]
    else:
        lines += ["No model, schema, scoring-infrastructure, or runtime refresh errors were recorded.", ""]
    lines += [
        "## Interpretation and reproducibility",
        "",
        "- These are authored workloads with known direct dependencies, a single model sample per condition, and a small prespecified subset. There is no statistical or universal agent-performance claim.",
        "- Exact adjacency traversal over the same receipts can match native graph retrieval. This comparison tests retrieval against BM25/dense/iterative hybrid, not a unique correctness advantage of Hydra over every other dependency representation.",
        "- Shared currentness checks, recursive execution, and refusal to serve stale/unknown values benefit every arm. Missing-source blocking is reported as a shared safety property.",
        "- Failures and abstentions remain in the attempt counts. Conditional rates should always be displayed with those counts and explicit numerators/denominators.",
        "- The local Claude Code bridge uses the existing authenticated CLI with external tools disabled. It is not a credential-distribution or public-service authentication design.",
        "",
        f"Source artifacts: `{path_label}/prepared.json`, `{path_label}/summary.json`, and each `<case>/<arm>/request.json`, `observation.json`, and `result.json`. Frozen request hashes, source-case hashes, code hashes, raw model usage, rationale, selected aliases, numeric-oracle comparisons, and actual tool receipts are retained there.",
        "",
        "Regenerate this report without any model calls:",
        "",
        "```bash",
        f".venv/bin/python scripts/summarize_agent.py --input {path_label} --output docs/AGENT_RESULTS.md",
        "```",
        "",
        f"Comparison finished at `{summary['finished_at']}`. This report describes the saved run; it does not rerun or alter the benchmark.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = render(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(json.dumps({"report": str(args.output), "completed_source": str(args.input)}))


if __name__ == "__main__":
    main()
