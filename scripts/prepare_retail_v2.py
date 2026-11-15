"""Prepare the frozen external retail fixtures, without any scored execution."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proofflow.eval.retail_data import FIXTURE_DIR, prepare_fixture, sha_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=ROOT / ".cache/retail_v2/Online Retail.xlsx")
    parser.add_argument("--output", type=Path, default=FIXTURE_DIR)
    args = parser.parse_args()
    fixture = prepare_fixture(args.workbook, args.output)
    print(f"Prepared {sum(item['rows'] for item in fixture['partition_files'].values())} positive transaction lines")
    print(f"Cases: {len(fixture['cases'])}; fixture SHA256: {sha_file(args.output / 'fixture.json')}")
    print("No runtime, retrieval, model, or scored evaluation was executed. Commit the reviewed freeze before scoring.")


if __name__ == "__main__":
    main()
