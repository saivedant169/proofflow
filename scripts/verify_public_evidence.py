#!/usr/bin/env python3
"""Check the integrity and arithmetic of an extracted ProofFlow evidence bundle."""

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

import audit_model_comparison_v4 as audit


MANIFEST = Path("manifest.json")
HISTORICAL = Path("historical-results.json")
PUBLICATION = audit.RUN / "publication"
PUBLICATION_MANIFEST = PUBLICATION / "publication_manifest.json"
FROZEN_PREPARATION = audit.PREPARED / "prepared.json"
FREEZE = audit.FIXTURE.parent / "study_freeze.json"
DATASET_NOTICE = audit.FIXTURE / "DATASET_NOTICE.md"
AUDITOR = Path("scripts/audit_model_comparison_v4.py")
VERIFIER = Path("scripts/verify_public_evidence.py")
CELL_FILES = ("result.json", "execution/independent_audit.json", "execution/post_snapshot.json")
PUBLICATION_FILES = (
    "audit.json",
    "poststate_manifest.json",
    "prelaunch_resolution.json",
    "prelaunch_stop.json",
    "provider_metrics.json",
    "raw_sha256.json",
)
CASE_FILES = ("case.json", "initial_records.json", "current_sources.json", "corpus.jsonl")
REQUEST_FILES = ("request.json", "context.jsonl", "prompt.txt")
HISTORICAL_ARMS = ("graph", "exact_flat", "bm25", "dense", "iterative_hybrid")


def cell_payloads():
    return {audit.RUN / case / arm / name for case in audit.CASES for arm in audit.ARMS for name in CELL_FILES}


def run_payloads():
    return (
        cell_payloads()
        | {PUBLICATION / name for name in PUBLICATION_FILES}
        | {audit.RUN / "summary.json", audit.RUN / "started.json"}
    )


def prepared_payloads():
    cases = {Path(case) / name for case in audit.CASES for name in CASE_FILES}
    requests = {
        Path(case) / "requests" / arm / name
        for case in audit.CASES
        for arm in audit.ARMS
        for name in REQUEST_FILES
    }
    return cases | requests


def reconstruction_inputs():
    dates = (f"2011-03-{day:02}" for day in range(1, 5))
    return (
        {audit.FIXTURE / f"{day}.{extension}" for day in dates for extension in ("csv", "provenance.json")}
        | {audit.FIXTURE / "fixture.json", DATASET_NOTICE, FREEZE, FROZEN_PREPARATION}
        | {audit.PREPARED / path for path in prepared_payloads()}
    )


def package_payloads():
    return (
        run_payloads()
        | reconstruction_inputs()
        | {PUBLICATION_MANIFEST, HISTORICAL, AUDITOR, VERIFIER, Path("README.md"), Path("LICENSE")}
    )


def verify_historical(path):
    saved = audit.load(path)
    fixed = {}
    for key, count, prefix in (("pilot_fixed_2048", 12, "T"), ("retail_fixed_2048", 10, "R")):
        rows = saved[key]
        keys = {(row["case"], row["arm"]) for row in rows}
        expected = {(f"{prefix}{i:02}", arm) for i in range(1, count + 1) for arm in HISTORICAL_ARMS}
        audit.check(len(rows) == len(keys) and keys == expected, key, "complete fixed-budget rows")
        fresh, eligible = Counter(), Counter()
        for row in rows:
            numerator, denominator, arm = row["fresh"], row["eligible"], row["arm"]
            audit.check(type(numerator) is type(denominator) is int and 0 <= numerator <= denominator, key, "report counts")
            fresh[arm] += numerator
            eligible[arm] += denominator
        fixed[key] = {arm: {"fresh": fresh[arm], "eligible": eligible[arm]} for arm in HISTORICAL_ARMS}

    rows = saved["retail_development"]
    audit.check(len(rows) == 4 and {row["case"] for row in rows} == {f"RD{i:02}" for i in range(1, 5)},
                "complete development rows")
    for row in rows:
        audit.check(type(row["graph_tokens"]) is type(row["full_context_tokens"]) is int
                    and 0 <= row["graph_tokens"] <= row["full_context_tokens"], "development tokens")
    graph = sum(row["graph_tokens"] for row in rows)
    full = sum(row["full_context_tokens"] for row in rows)
    audit.check(full > 0 and saved["retail_development_maximum_ratio"] == 0.4, "development gate")
    ratio = graph / full
    return {
        **fixed,
        "retail_development": {
            "graph_tokens": graph,
            "full_context_tokens": full,
            "ratio": ratio,
            "maximum_ratio": 0.4,
            "passed": ratio <= 0.4,
        },
    }


def verify_bundle(root):
    manifest = audit.load(root / MANIFEST)
    audit.check(manifest["schema_version"] == 1 and manifest["frozen_study_revision"] == audit.REVISION,
                "bundle schema and study revision")
    files = manifest["files"]
    audit.check(set(files) == {path.as_posix() for path in package_payloads()}, "exact bundle inventory")
    preparation = files[FROZEN_PREPARATION.as_posix()]
    audit.check(preparation["sha256"] == manifest["public_preparation_sha256"] == audit.PREPARED_SHA256
                and preparation["original"]["sha256"] == manifest["historical_preparation_sha256"],
                "public and historical preparation bindings")
    for name, info in files.items():
        path = root / name
        audit.check(path.resolve() == path and path.is_file(), name, "regular bundle file")
        audit.check(path.stat().st_size == info["bytes"], name, "bundle bytes")
        audit.require_hash(path, info["sha256"])
    return {
        "bundle_files_verified": len(files),
        "model_study": audit.verify(root),
        "earlier_studies": verify_historical(root / HISTORICAL),
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path, default=Path(__file__).resolve().parents[1],
                        help="extracted bundle root (defaults to the directory above this script)")
    try:
        result = verify_bundle(parser.parse_args().bundle.resolve())
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration, ArithmeticError) as error:
        parser.exit(1, f"Evidence verification failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["model_study"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
