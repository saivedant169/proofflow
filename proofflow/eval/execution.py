"""Measure actual selective refresh against an independent numeric oracle.

Every retrieval policy uses the same safe executor. Unselected stale reports are
therefore *unresolved*, not falsely counted as answers served to a user. The
executor may recursively refresh prerequisites; every resulting tool call is
counted here rather than charging only the policy's selected roots.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import time
from typing import Any, Iterable

from .cases import Scenario, expected_affected_names
from .workload import Workload, clone_runtime, evidence_alias, in_scope


def _failure(exc: Exception) -> dict[str, str]:
    """Keep the failure class and message without converting it into success."""
    return {"type": type(exc).__name__, "message": str(exc)}


def run_refresh_check(
    workload: Workload,
    scenario: Scenario,
    selected_aliases: Iterable[str],
    alias_to_raw: dict[str, str],
    expected_values: dict[str, Any],
    expected_errors: dict[str, str],
    output_directory: str | Path,
) -> dict[str, Any]:
    """Refresh a policy's chosen roots in a clone and score all scoped reports.

    Preconditions: all retrieval policies have already made their selections;
    the workload contains the scenario's source/tool mutations; oracle values
    were independently computed from that changed source data. The clone has
    private heads and blobs but shares immutable graph history. No retrieval or
    impact-discovery query is performed here after arm execution begins.

    The returned numeric values are evaluation evidence, not a serving API.
    ``complete_fresh_reports`` excludes oracle-unavailable reports, which can
    instead earn ``correctly_blocked_reports``. A matching cached numeric value
    alone is never success when its currentness is stale or unknown.
    """
    selected = list(dict.fromkeys(selected_aliases))
    invalid = [alias for alias in selected if alias not in alias_to_raw]
    if invalid:
        raise ValueError(f"Refresh selection contains unknown evidence aliases: {invalid}")
    selected_raw = [alias_to_raw[alias] for alias in selected]

    originals = sorted(
        ((name, record) for name, record in workload.refs.items()
         if record.kind == "artifact"
         and record.metadata.get("tool") == "compose_report"
         and in_scope(record.logical_id, scenario)),
        key=lambda item: item[0],
    )
    missing_oracle = [name for name, _ in originals
                      if name not in expected_values and name not in expected_errors]
    if missing_oracle:
        raise ValueError(f"Independent oracle has no result for report(s): {missing_oracle}")
    overlap = set(expected_values) & set(expected_errors)
    if overlap:
        raise ValueError(f"Independent oracle simultaneously supplies values and errors: {sorted(overlap)}")

    # Ground truth affects scoring only. It is never supplied to refresh().
    affected_names = expected_affected_names(scenario, workload.recipes)
    runtime = clone_runtime(workload, Path(output_directory))
    started = time.perf_counter()
    refresh_result = None
    refresh_error = None
    reports: list[dict[str, Any]] = []
    inspection_errors: list[dict[str, Any]] = []
    try:
        refresh_queries_before = runtime.graph.queries
        # One production call, with the selected order preserved. If a tool
        # fails, do not silently retry or complete omitted reports for an arm.
        try:
            refresh_result = runtime.refresh(selected_raw).to_dict()
        except Exception as exc:
            refresh_error = _failure(exc)

        refresh_elapsed_ms = (time.perf_counter() - started) * 1000
        refresh_graph_queries = runtime.graph.queries - refresh_queries_before
        inspection_queries_before = runtime.graph.queries
        for name, original in originals:
            oracle_available = name in expected_values
            result: dict[str, Any] = {
                "name": name,
                "logical_id": original.logical_id,
                "original_id": original.id,
                "original_alias": evidence_alias(original, runtime.store),
                "original_content_hash": original.content_hash,
                "expected_revalidation": name in affected_names,
                "oracle_available": oracle_available,
                "expected_value": expected_values.get(name),
                "expected_error": expected_errors.get(name),
                "head_id": None,
                "head_content_hash": None,
                "state": "error",
                "currentness_reasons": [],
                "actual_stored_value": None,
                "value_matches_oracle": None,
                "fresh_complete": False,
                "correctly_blocked": False,
                "preserved_original_artifact": False,
                "preserved_original_content": False,
                "original_value_matches_oracle": None,
                "inspection_error": None,
            }
            try:
                head = runtime.store.get_head(original.logical_id)
                if head is None:
                    raise ValueError(f"Report head disappeared: {original.logical_id}")
                status = runtime.currentness(head.id)
                # Forensic inspection is deliberately separate from context(),
                # which does not serve this stored value if it is not current.
                actual = runtime.store.read(head.id)
                original_value = runtime.store.read(original.id)
                equality = actual == expected_values[name] if oracle_available else None
                result.update(
                    head_id=head.id,
                    head_content_hash=head.content_hash,
                    state=status.state,
                    currentness_reasons=list(status.reasons),
                    actual_stored_value=actual,
                    value_matches_oracle=equality,
                    fresh_complete=bool(oracle_available and status.is_current and equality),
                    correctly_blocked=bool(not oracle_available and status.state in {"stale", "unknown"}),
                    preserved_original_artifact=head.id == original.id,
                    preserved_original_content=head.content_hash == original.content_hash,
                    original_value_matches_oracle=(original_value == expected_values[name]
                                                   if oracle_available else None),
                )
            except Exception as exc:
                result["inspection_error"] = _failure(exc)
                inspection_errors.append({"report": name, **_failure(exc)})
            reports.append(result)

        calls = deepcopy(runtime.calls)
        eligible = [report for report in reports if report["oracle_available"]]
        unavailable = [report for report in reports if not report["oracle_available"]]
        unaffected = [report for report in reports if not report["expected_revalidation"]]
        affected_eligible = [report for report in eligible if report["expected_revalidation"]]
        complete_count = sum(report["fresh_complete"] for report in eligible)
        correct_blocks = sum(report["correctly_blocked"] for report in unavailable)
        return {
            "scenario_id": scenario.id,
            "selected_aliases": selected,
            "selected_raw_ids": selected_raw,
            "refresh_completed": refresh_error is None,
            "refresh_result": refresh_result,
            "refresh_error": refresh_error,
            "refresh_elapsed_ms": refresh_elapsed_ms,
            "refresh_graph_queries": refresh_graph_queries,
            "inspection_graph_queries": runtime.graph.queries - inspection_queries_before,
            "evaluation_elapsed_ms": (time.perf_counter() - started) * 1000,
            "inspection_errors": inspection_errors,
            "reports": reports,
            "report_count": len(reports),
            "eligible_reports": len(eligible),
            "complete_fresh_reports": complete_count,
            "fresh_report_rate": complete_count / len(eligible) if eligible else None,
            "eligible_affected_reports": len(affected_eligible),
            "fresh_affected_reports": sum(report["fresh_complete"] for report in affected_eligible),
            "affected_report_rate": (sum(report["fresh_complete"] for report in affected_eligible) / len(affected_eligible)
                                     if affected_eligible else None),
            "all_eligible_reports_fresh": bool(eligible) and complete_count == len(eligible),
            "oracle_unavailable_reports": len(unavailable),
            "correctly_blocked_reports": correct_blocks,
            "all_oracle_unavailable_reports_blocked": correct_blocks == len(unavailable),
            "stale_reports_remaining": sum(report["state"] == "stale" for report in reports),
            "unknown_reports_remaining": sum(report["state"] == "unknown" for report in reports),
            "blocked_reports": sum(report["state"] in {"stale", "unknown"} for report in reports),
            "unresolved_eligible_reports": len(eligible) - complete_count,
            "incorrect_current_reports": sum(report["state"] == "current"
                                             and (not report["oracle_available"]
                                                  or report["value_matches_oracle"] is False)
                                             for report in reports),
            "unaffected_reports": len(unaffected),
            "unaffected_report_artifacts_preserved": sum(report["preserved_original_artifact"]
                                                         for report in unaffected),
            "unaffected_report_content_preserved": sum(report["preserved_original_content"]
                                                       for report in unaffected),
            "tool_calls": len(calls),
            "successful_tool_calls": sum(call.get("status") == "success" for call in calls),
            "failed_tool_calls": sum(call.get("status") == "failed" for call in calls),
            "unpublished_tool_calls": sum(call.get("status") == "unpublished" for call in calls),
            "calls": calls,
            "serving_policy": "All arms use the same Hydra-assisted currentness and recursive refresh executor; standalone baseline safety is not evaluated. Stale or unknown reports are blocked, not served.",
            "clone_protocol": "Private manifest heads and blobs; shared immutable graph; selections frozen before execution.",
        }
    finally:
        try:
            runtime.store.close()
        finally:
            runtime.graph.close()
