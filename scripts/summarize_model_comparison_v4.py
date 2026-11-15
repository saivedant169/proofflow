"""Project committed March v4 evidence into a small, data-only benchmark UI summary.

Run from the repository root with Python 3.10+: python3 scripts/summarize_model_comparison_v4.py
Use --check to verify the tracked summary without writing it. This reads saved
publication files only; it does not call a model or the application runtime.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = Path("results/model-v4-test-run-1")
OUTPUT = ROOT / "evidence/model_comparison_v4_summary.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def summarize():
    manifest = json.loads((ROOT / RUN / "publication/publication_manifest.json").read_bytes())
    sources = {}

    def read(relative):
        path = (RUN / relative).as_posix()
        payload = (ROOT / path).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        require(manifest["files"][path]["sha256"] == digest, f"Publication hash mismatch: {path}")
        sources[path] = digest
        return json.loads(payload)

    summary = read("summary.json")
    provider = read("publication/provider_metrics.json")
    audit = read("publication/audit.json")
    require(summary["complete_study"] and summary["integrity_verified"] and audit["audit_passed"],
            "Expected a complete, audited study")

    protocol = summary["protocol"]
    model = protocol["model"]
    cases = protocol["test_cases"]
    arms = protocol["arms"]
    no_op = protocol["no_op_case"]
    jobs = {f"{case}:{arm}" for case in cases for arm in arms}
    cells = {cell["job_id"]: cell for cell in summary["cells"]}
    metrics = {cell["job_id"]: cell for cell in provider["cells"]}
    require(cells.keys() == metrics.keys() == jobs
            and len(jobs) == len(summary["cells"]) == len(provider["cells"])
            == protocol["planned_invocations"] == audit["scorable_cells"], "Incomplete cell grid")

    primary_tokens = {"graph": 0, "full_context": 0}
    caps, turns, matching_prompts = [], 0, 0
    case_rows = []
    for case in cases:
        graph, flat = (metrics[f"{case}:{arm}"] for arm in ("graph", "exact_flat"))
        matching_prompts += int(graph["request_sha256"] == flat["request_sha256"]
                                and graph["context_sha256"] == flat["context_sha256"])
        cap = cells[f"{case}:graph"]["evidence_budget"]
        caps.append(cap)
        available, unavailable, fresh = set(), set(), []
        for arm in arms:
            cell = cells[f"{case}:{arm}"]
            usage = metrics[cell["job_id"]]
            counters = usage["modelUsage"][model]
            input_tokens = sum(counters[field] for field in
                               ("inputTokens", "cacheCreationInputTokens", "cacheReadInputTokens"))
            require(input_tokens == cell["usage"]["provider_input_exposure"]
                    and usage["num_turns"] == cell["usage"]["num_turns"], f"Usage mismatch: {cell['job_id']}")
            require(cell["evidence_budget"] == (None if arm == "full_context" else cap),
                    f"Evidence cap mismatch: {cell['job_id']}")
            if case != no_op and arm in primary_tokens:
                primary_tokens[arm] += input_tokens
            turns += usage["num_turns"]
            counts = cell["score"]["verified_reports_counts"]
            available.add(counts["eligible_affected"])
            unavailable.add(counts["unavailable"])
            fresh.append(counts["fresh_affected"])
        require(len(available) == len(unavailable) == 1, f"Denominator mismatch: {case}")
        case_rows.append({"id": case, "eligible": available.pop(), "unavailable": unavailable.pop(),
                          "fresh_by_arm": fresh})

    recoverable_cases = [case["id"] for case in case_rows if case["eligible"]]
    eligible = sum(case["eligible"] for case in case_rows)
    unavailable = sum(case["unavailable"] for case in case_rows)
    arm_rows = []
    for index, arm in enumerate(arms):
        reports = [cells[f"{case}:{arm}"]["score"]["verified_reports_counts"] for case in cases]
        corrected = sum(cells[f"{case}:{arm}"]["model_task"]["model_task_success"] for case in recoverable_cases)
        fresh = sum(case["fresh_by_arm"][index] for case in case_rows)
        blocked = sum(report["correctly_blocked"] for report in reports)
        audited = audit["arms"][arm]
        require((eligible, fresh, len(recoverable_cases), corrected, unavailable, blocked) ==
                tuple(audited[key] for key in ("eligible_affected", "fresh_affected", "correction_case_denominator",
                                               "correction_case_success", "unavailable_reports",
                                               "correct_unavailable_blocks")), f"Outcome mismatch: {arm}")
        require(blocked == unavailable, f"Unavailable reports were not all blocked: {arm}")
        arm_rows.append({"id": arm, "fresh_affected": fresh, "correction_cases_completed": corrected})

    require(matching_prompts == len(audit["graph_exact_flat_matching_prompts"])
            and math.isclose(primary_tokens["graph"] / primary_tokens["full_context"],
                             summary["primary"]["non_noop_provider_input_ratio"]), "Primary evidence mismatch")
    require(model == audit["provider_model"] == "claude-fable-5-2" and protocol["effort"] == audit["effort"],
            "Model identity mismatch")
    require(audit["frozen_revision"] == provider["frozen_revision"]
            and audit["prepared_sha256"] == provider["prepared_sha256"], "Provenance mismatch")

    return {
        "model": "Fable 5.2",
        "effort": protocol["effort"],
        "test_rows": audit["test_rows"],
        "cli_calls": len(jobs),
        "cli_turns": turns,
        "eligible_affected_reports": eligible,
        "recoverable_cases": len(recoverable_cases),
        "unavailable_reports": unavailable,
        "arms": arm_rows,
        "cases": case_rows,
        "matching_graph_exact_flat_prompts": matching_prompts,
        "evidence_caps": {"min": min(caps), "max": max(caps)},
        "provider_input_excluding_no_op": primary_tokens,
        "provenance": {"frozen_revision": provider["frozen_revision"], "source_sha256": sources},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(summarize(), indent=2) + "\n"
    if args.check:
        require(OUTPUT.read_text(encoding="utf-8") == rendered, f"Regenerate {OUTPUT.relative_to(ROOT)}")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
