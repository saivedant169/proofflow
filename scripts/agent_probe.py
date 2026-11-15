"""Run one real local model planning step over a prepared evidence request.

Input is an AgentRequest JSON object, never an evaluation-results file.
This script performs no runtime actions; use the validated execute_plan API
when integrating with a resettable benchmark scenario.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from proofflow.agent import AgentRequest, ClaudeCLIProvider, plan_refresh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="claude-fable-5-2")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-budget-usd", type=float, default=1.0)
    args = parser.parse_args()
    data = json.loads(args.request.read_text())
    if set(data) != {"task", "changed_ids", "context_text", "allowed_artifact_ids"}:
        raise ValueError("Request must contain only task, changed_ids, context_text, allowed_artifact_ids")
    request = AgentRequest(task=data["task"], changed_ids=tuple(data["changed_ids"]),
                           context_text=data["context_text"], allowed_artifact_ids=tuple(data["allowed_artifact_ids"]))
    provider = ClaudeCLIProvider(model=args.model, effort=args.effort, timeout_seconds=args.timeout,
                                  max_budget_usd=args.max_budget_usd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("Refusing to overwrite a prior model observation")
    try:
        result = plan_refresh(provider, request)
    except Exception as exc:
        provider_result = getattr(exc, "provider_result", None)
        failure = {"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                   "provider_result": asdict(provider_result) if provider_result else None,
                   "provider_evidence": getattr(exc, "evidence", {}),
                   "no_retry": True, "request": str(args.request)}
        args.output.write_text(json.dumps(failure, indent=2) + "\n")
        raise
    args.output.write_text(json.dumps(result.to_dict(), indent=2) + "\n")
    print(json.dumps({"model": result.provider_result.model, "selected_ids": result.selected_ids,
                      "abstain": result.abstain, "output": str(args.output),
                      "elapsed_seconds": result.provider_result.elapsed_seconds}))


if __name__ == "__main__":
    main()
