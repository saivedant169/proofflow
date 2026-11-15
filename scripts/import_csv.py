"""Run ProofFlow on a local CSV; rerun the same workspace to refresh its reports.

Example:
  uv run python scripts/import_csv.py orders.csv --workspace my-orders --region APAC --fx EUR=1.10

Required columns: order_id,region,currency,gross_cents
Optional columns: refund_cents,ticket_count (blank means zero)
Money is integer cents. EUR/GBP require explicit USD rates; USD is always 1.
Input stays local; the CLI never calls a model or uploads CSV data to a provider.
"""
from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from proofflow.artifacts import ArtifactStore
from proofflow.graph import HydraGraph
from proofflow.importing import CSVImportError, MAX_BYTES, apply_import, parse_csv
from proofflow.runtime import ProofFlowRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_file", type=Path, help="Explicit local UTF-8 CSV file")
    parser.add_argument("--workspace", required=True, help="1–48 lowercase letters, digits or hyphens; stored under .state/imports")
    parser.add_argument("--region", help="Region to show in the second report; defaults to first sorted region")
    parser.add_argument("--fx", action="append", default=[], metavar="CURRENCY=RATE", help="Explicit USD conversion rate; repeat for EUR/GBP")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", args.workspace):
            raise CSVImportError("Workspace must contain 1–48 lowercase letters, digits or hyphens")
        rates = {}
        for item in args.fx:
            if item.count("=") != 1:
                raise CSVImportError("FX arguments must be CURRENCY=RATE")
            currency, value = item.split("=", 1)
            if currency in rates:
                raise CSVImportError("Each FX currency may be supplied only once")
            rates[currency] = value
        with args.csv_file.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        dataset = parse_csv(payload, rates=rates, region=args.region)
        directory = ROOT / ".state" / "imports" / args.workspace
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".import.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CSVImportError("This workspace is already being imported by another process") from exc
            store = ArtifactStore(directory)
            try:
                with HydraGraph(namespace=f"csv-import-{store.workspace}") as graph:
                    result = apply_import(ProofFlowRuntime(store, graph), dataset)
                    result["hydra_queries"] = graph.queries
                    result["backend"] = "HydraDB OSS, native traversal; no fallback"
            finally:
                store.close()
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc),
                          "note": "No successful import is claimed. A database failure may leave individually published source versions; retry the same input after recovery."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
