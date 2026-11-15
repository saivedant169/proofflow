"""Freeze the displayed values from audited results; no model or browser calls."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = (HERE / json.loads((HERE / "manifest.json").read_text())["source_root"]).resolve()


def read(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def extract() -> dict:
    run = "results/model-v4-test-run-1"
    audit = read(f"{run}/publication/audit.json")
    summary = read(f"{run}/summary.json")
    cells = audit["cells"]
    arms = audit["arms"]
    case_count = len({c["case"] for c in cells})
    assert audit["audit_passed"] and audit["gates"]["passed"] and not audit["mismatches"]
    assert audit["settled_attempts"] == audit["scorable_cells"] == len(cells) == case_count * len(arms)
    assert audit["provider_model"] == "claude-fable-5-2" and audit["effort"] == "high"
    assert len(audit["graph_exact_flat_matching_prompts"]) == case_count
    capped = [c["evidence_budget"] for c in cells if c["arm"] != "full_context"]
    assert summary["protocol"]["retrieval"]["evidence_budget"].endswith("full context uncapped")
    provider = audit["gates"]["provider_non_noop"]
    assert provider["ratio"] == provider["graph"] / provider["full_context"]

    all_arm_totals = {
        "eligible_affected": {a["eligible_affected"] for a in arms.values()},
        "correct_unavailable_blocks": {a["correct_unavailable_blocks"] for a in arms.values()},
        "unaffected_reports_preserved": {a["unaffected_reports_preserved"] for a in arms.values()},
        "incorrect_current_reports": {a["incorrect_current_reports"] for a in arms.values()},
    }
    assert all(len(value) == 1 for value in all_arm_totals.values())

    retail = read("evidence/retail_v2_summary.json")
    previous_fixed = next(a for a in retail["fixed_2048"] if a["arm"] == "graph")
    previous_dev = retail["development"]
    assert not previous_dev["passed"]
    mcp = read("results/mcp-agent-v2/summary.json")
    mcp_audit = read("results/mcp-agent-v2/independent-audit.json")
    assert mcp["audit_checks"] == mcp_audit["checks"]
    checks = list(mcp["checks"].values()) + list(mcp_audit["checks"].values())
    return {
        "model": {
            "name": audit["provider_model"],
            "effort": audit["effort"],
            "cases": case_count,
            "methods": len(arms),
            "cli_invocations": audit["scorable_cells"],
            "cli_turns": sum(c["num_turns"] for c in cells),
            "test_dates": audit["test_dates"],
            "test_rows": audit["test_rows"],
            "fresh_affected": {key: a["fresh_affected"] for key, a in arms.items()},
            **{key: next(iter(value)) for key, value in all_arm_totals.items()},
            "provider_input_excluding_noop": provider,
            "receipt_input_excluding_noop": audit["gates"]["receipts_non_noop"],
            "capped_evidence_token_range": [min(capped), max(capped)],
            "same_prompt_cases": len(audit["graph_exact_flat_matching_prompts"]),
        },
        "previous_deterministic": {
            "fixed_token_cap": 2048,
            "fixed_fresh_affected_reports": previous_fixed["fresh_affected_reports"],
            "fixed_eligible_affected_reports": previous_fixed["eligible_affected_reports"],
            "development_ratio": previous_dev["token_ratio"],
            "development_cutoff": previous_dev["threshold"],
        },
        "mcp": {
            "model": mcp["client_model"],
            "effort": mcp["effort"],
            "passed_checks": sum(checks),
            "total_checks": len(checks),
            "requests": mcp["client_tool_requests"],
            "runtime_calls": mcp["recorded_runtime_calls"],
            "preflight_calculations": mcp["csv_preflight_calculations"],
            "previous_passed": mcp["infrastructure_correction"]["previous_passed"],
            "server_model_calls": mcp["server_model_calls"],
        },
    }


if __name__ == "__main__":
    (HERE / "evidence_extract.json").write_text(json.dumps(extract(), indent=2) + "\n")
