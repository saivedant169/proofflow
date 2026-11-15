#!/usr/bin/env python3
"""Prepare an immutable source split without retrieval/runtime/model calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofflow.eval.model_comparison_data import prepare_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    args = parser.parse_args()
    result = prepare_fixture(args.workbook, args.split)
    print(json.dumps({"split": result["split"], "dates": result["dates"],
        "rows": result["profile"]["selected_rows"], "invoices": result["profile"]["selected_invoices"],
        "artifacts": len(result["recipes"]), "reports": sum(r["tool"] == "compose_report" for r in result["recipes"]),
        "cases": len(result["cases"])}, indent=2))


if __name__ == "__main__":
    main()
