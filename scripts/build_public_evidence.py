#!/usr/bin/env python3
"""Build the static, results-only ProofFlow model evidence download."""

from argparse import ArgumentParser
from collections import defaultdict
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
import json
import os
import re

import audit_model_comparison_v4 as audit
import verify_public_evidence as bundle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "frontend/public/evidence"
ARCHIVE = "proofflow-model-evidence.zip"
CHECKSUM = f"{ARCHIVE}.sha256"
DELIVERY_ARCHIVE = "proofflow-delivery-evidence.zip"
DELIVERY_CHECKSUM = f"{DELIVERY_ARCHIVE}.sha256"
FIXED_ARCHIVE = "proofflow-fixed-budget-evidence.zip"
FIXED_CHECKSUM = f"{FIXED_ARCHIVE}.sha256"
PORTAL_FILES = ("index.html", "evidence.css")
SUMMARY = audit.RUN / "summary.json"
STARTED = audit.RUN / "started.json"
AUDIT_JSON = bundle.PUBLICATION / "audit.json"
PROVIDER_JSON = bundle.PUBLICATION / "provider_metrics.json"
RAW_INDEX = bundle.PUBLICATION / "raw_sha256.json"
POSTSTATE_INDEX = bundle.PUBLICATION / "poststate_manifest.json"
ORIGINAL_PUBLICATION_SHA256 = "0c2a1bb52541579e9e73108e519ce0158eab494708037dba09b973f58cc04908"
WITHHELD = "[withheld]"
SECRET_NAMES = ("PROOFFLOW_HYDRA_TOKEN", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY")
SENSITIVE_PATTERNS = {
    "host-local path": rb"/(?:Users|home|root|private|Volumes|tmp|var/(?:tmp|folders)|opt/homebrew)/|[A-Z]:\\+Users\\+",
    "credential prefix": rb"\b(?:sk-(?:ant-|proj-|live-)?[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{12,})\b",
    "authorization credential": rb"(?i)\b(?:bearer|basic) [A-Za-z0-9_+/.=\-]{12,}",
    "private key": rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    "credential or session field": rb'(?i)"(?:session_id|sessionId|cookie|set-cookie|authorization|api_key|access_token|refresh_token|proofflow_hydra_token)"\s*:\s*"[^"]+"',
}


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def fingerprint(data):
    return {"bytes": len(data), "sha256": sha256(data).hexdigest()}


def repo_file(path):
    candidate = ROOT / path
    audit.check(candidate.resolve() == candidate and candidate.is_file(), path, "regular allowlisted source file")
    return candidate.read_bytes()


def redact_path(document, key, suffix, replacement, changes, label=""):
    value = PurePosixPath(document[key])
    expected = PurePosixPath(suffix).parts
    audit.check(value.is_absolute() and value.parts[-len(expected):] == expected, f"{label}/{key}",
                "unexpected path in saved study")
    document[key] = replacement
    changes.append(f"{label}/{key}")


def redact_protocol(record, changes):
    redact_path(record["protocol"], "study_state_directory", "study_state", WITHHELD, changes, "/protocol")


def redact_job(record, changes, label=""):
    case, arm = record["case_id"], record["arm"]
    case_path = audit.PREPARED / case / "case.json"
    request = audit.PREPARED / case / "requests" / arm / "request.json"
    redact_path(record, "case_path", case_path, case_path.as_posix(), changes, label)
    redact_path(record, "request_path", request, request.as_posix(), changes, label)


def redact_case(record, changes, label=""):
    case = audit.PREPARED / record["case_id"]
    for key, name in (("case_path", "case.json"), ("corpus_path", "corpus.jsonl"),
                      ("initial_records_path", "initial_records.json"), ("source_values_path", "current_sources.json")):
        redact_path(record, key, case / name, (case / name).as_posix(), changes, label)
    redact_path(record, "initial_store_path", case / "initial", WITHHELD, changes, label)
    for arm, request in record["requests_by_arm"].items():
        directory = case / "requests" / arm
        for key, name in (("context_path", "context.jsonl"), ("prompt_path", "prompt.txt"), ("request_path", "request.json")):
            redact_path(request, key, directory / name, (directory / name).as_posix(),
                        changes, f"{label}/requests_by_arm/{arm}")


def redact_cell(record, changes, label=""):
    redact_job(record, changes, label)
    process = record["process"]
    cli = audit.RUN / record["case_id"] / record["arm"] / "cli"
    redact_path(process, "cwd", cli / "cwd", WITHHELD, changes, f"{label}/process")
    argv = process["argv"]
    audit.check(argv.count("--settings") == 1, record["job_id"], "settings path flag")
    index = argv.index("--settings") + 1
    redact_path(argv, index, cli / "settings.json", WITHHELD, changes, f"{label}/process/argv")


def historical_rows():
    sources = {
        "pilot": Path("results/test-v1/execution.jsonl"),
        "retail": Path("results/retail-test-v1/execution.jsonl"),
        "development": Path("results/retail-dev-v1/retrieval.jsonl"),
    }
    original = {label: repo_file(path) for label, path in sources.items()}
    pilot, retail, dev = ([json.loads(line) for line in raw.splitlines()] for raw in original.values())
    pilot_counts = [
        {"case": row["scenario"], "arm": row["arm"],
         "fresh": row["fresh_affected_reports"], "eligible": row["eligible_affected_reports"]}
        for row in pilot if row["budget"] == 2048 and row["arm"] in bundle.HISTORICAL_ARMS
    ]
    retail_counts = [
        {"case": row["scenario"], "arm": row["arm"],
         "fresh": row["reports_counts"]["fresh_affected"], "eligible": row["reports_counts"]["eligible_affected"]}
        for row in retail if row["condition"] == "fixed_2048"
    ]
    dev_tokens = defaultdict(dict)
    for row in dev:
        if row["condition"] == "unlimited" and row["arm"] in {"graph", "full_context"}:
            case, key = row["scenario"], f"{row['arm']}_tokens"
            audit.check(key not in dev_tokens[case], case, "duplicate development arm")
            dev_tokens[case][key] = row["context_tokens"]
    return {
        "source_sha256": {label: sha256(raw).hexdigest() for label, raw in original.items()},
        "pilot_fixed_2048": sorted(pilot_counts, key=lambda row: (row["case"], row["arm"])),
        "retail_fixed_2048": sorted(retail_counts, key=lambda row: (row["case"], row["arm"])),
        "retail_development": [{"case": case, **counts} for case, counts in sorted(dev_tokens.items())],
        "retail_development_maximum_ratio": 0.4,
    }


def observed_private_values():
    values = {os.environ.get(name, "") for name in SECRET_NAMES}
    dotenv = ROOT / ".env"
    if dotenv.is_file():
        for line in dotenv.read_text().splitlines():
            key, _, value = line.removeprefix("export ").partition("=")
            if key.strip() in SECRET_NAMES:
                values.add(value.strip().strip("\"'"))
    for case in audit.CASES:
        for arm in audit.ARMS:
            log = ROOT / audit.RUN / case / arm / "cli/stdout.log"
            if log.is_file():
                for raw in re.findall(rb'"(?:session_id|request_id|uuid)"\s*:\s*"([^"]+)"', log.read_bytes()):
                    values.add(raw.decode())
    return [value.encode() for value in values if len(value) >= 8]


def scan_public_bytes(payloads):
    observed = observed_private_values()
    patterns = {label: re.compile(pattern) for label, pattern in SENSITIVE_PATTERNS.items()}
    for path, data in payloads.items():
        audit.check(not any(value in data for value in observed), path, "configured secret or observed provider ID in public data")
        for label, pattern in patterns.items():
            audit.check(pattern.search(data) is None, path, f"{label} in public data")


def redact_originals(original):
    public = original.copy()
    edits = {}

    def update(path, record, changes):
        public[path] = json_bytes(record)
        edits[path] = changes

    def read(path):
        return json.loads(public[path])

    # Keep historical source rows, prompts, values and receipts byte-identical.
    freeze = read(bundle.FREEZE)
    changes = []
    redact_protocol(freeze, changes)
    del freeze["code_sha256"]
    update(bundle.FREEZE, freeze, [*changes, "/code_sha256"])
    freeze_hash = fingerprint(public[bundle.FREEZE])["sha256"]

    for case in audit.CASES:
        path = audit.PREPARED / case / "case.json"
        row, changes = read(path), []
        redact_case(row, changes)
        update(path, row, changes)

    prepared = read(bundle.FROZEN_PREPARATION)
    changes = []
    redact_protocol(prepared, changes)
    redact_path(prepared, "freeze_path", bundle.FREEZE, bundle.FREEZE.as_posix(), changes)
    prepared["freeze_sha256"] = freeze_hash
    del prepared["code_sha256"]
    prepared["artifact_sha256"] = {
        path.as_posix(): fingerprint(public[audit.PREPARED / path])["sha256"] for path in bundle.prepared_payloads()
    }
    for index, case in enumerate(prepared["cases"]):
        redact_case(case, changes, f"/cases/{index}")
    for index, job in enumerate(prepared["jobs"]):
        redact_job(job, changes, f"/jobs/{index}")
    update(bundle.FROZEN_PREPARATION, prepared, [*changes, "/freeze_sha256", "/code_sha256", "/artifact_sha256"])
    prepared_hash = fingerprint(public[bundle.FROZEN_PREPARATION])["sha256"]

    for case in audit.CASES:
        for arm in audit.ARMS:
            path = audit.RUN / case / arm / "result.json"
            row, changes = read(path), []
            redact_cell(row, changes)
            update(path, row, changes)

    summary = read(SUMMARY)
    changes = []
    redact_protocol(summary, changes)
    for index, row in enumerate(summary["cells"]):
        redact_cell(row, changes, f"/cells/{index}")
    for index, row in enumerate(summary["ledger"]["attempts"]):
        audit.check(row["run_identity"] == audit.PREPARED_SHA256, row["job_id"], "original reservation binding")
        row["run_identity"] = prepared_hash
        changes.append(f"/ledger/attempts/{index}/run_identity")
    for index, row in enumerate(summary["ledger"]["dry_runs"]):
        redact_path(row, "output", "model-v4-dev-dryrun-1", WITHHELD, changes, f"/ledger/dry_runs/{index}")
    update(SUMMARY, summary, changes)

    for path in (STARTED, AUDIT_JSON, PROVIDER_JSON, RAW_INDEX, POSTSTATE_INDEX):
        row = read(path)
        audit.check(row["prepared_sha256"] == audit.PREPARED_SHA256, path, "original preparation binding")
        row["prepared_sha256"] = prepared_hash
        update(path, row, ["/prepared_sha256"])

    raw_index = read(RAW_INDEX)
    changes = edits[RAW_INDEX].copy()
    for filename in ("summary.json", "started.json"):
        raw_index["run_files"][filename] = fingerprint(public[audit.RUN / filename])["sha256"]
        changes.append(f"/run_files/{filename}")
    for case in audit.CASES:
        for arm in audit.ARMS:
            path = Path(case) / arm / "result.json"
            raw_index["cells"][f"{case}:{arm}"][path.as_posix()] = fingerprint(public[audit.RUN / path])["sha256"]
            changes.append(f"/cells/{case}:{arm}/{path.as_posix().replace('/', '~1')}")
    update(RAW_INDEX, raw_index, changes)

    audit_doc = read(AUDIT_JSON)
    audit_doc["actual_run_summary_sha256"] = fingerprint(public[SUMMARY])["sha256"]
    audit_doc["freeze_sha256"] = freeze_hash
    for key in ("ci_run", "publication"):
        del audit_doc[key]
    update(AUDIT_JSON, audit_doc, [*edits[AUDIT_JSON], "/actual_run_summary_sha256", "/freeze_sha256", "/ci_run", "/publication"])

    poststate = read(POSTSTATE_INDEX)
    files = {}
    for path in bundle.cell_payloads():
        binding = fingerprint(public[path])
        files[path.as_posix()] = {"sha256": binding["sha256"], "size_bytes": binding["bytes"]}
    poststate["files"] = files
    poststate["counts"]["bytes"] = sum(info["size_bytes"] for info in files.values())
    for tail, row in poststate["by_kind"].items():
        matches = {path: info["size_bytes"] for path, info in files.items() if path.endswith(f"/{tail}")}
        largest = max(sorted(matches), key=matches.__getitem__)
        row.update(bytes=sum(matches.values()), largest={"path": largest, "size_bytes": matches[largest]})
    poststate["already_tracked_reconstruction_inputs"] = sorted(path.as_posix() for path in bundle.reconstruction_inputs())
    poststate["publication_conditions"] = [
        "Archived results preserve the saved scientific observations. The bundle manifest records public-copy changes."
    ]
    update(POSTSTATE_INDEX, poststate, [*edits[POSTSTATE_INDEX], "/files", "/counts/bytes", "/by_kind",
                                        "/already_tracked_reconstruction_inputs", "/publication_conditions"])

    update(bundle.PUBLICATION_MANIFEST, {
        "source_revision": audit.REVISION,
        "scope": "Public results package with host-local paths removed",
        "files": {path.as_posix(): fingerprint(public[path]) for path in bundle.run_payloads()},
    }, ["/files", "/scope", "/original_per_cell_and_poststate_bytes", "/raw_provider_and_store_archive",
        "/actual_hydra_credential_value_scan", "/observed_provider_session_ids_scan"])

    needle = f'PREPARED_SHA256 = "{audit.PREPARED_SHA256}"'.encode()
    audit.check(public[bundle.AUDITOR].count(needle) == 1, "verifier preparation binding")
    public[bundle.AUDITOR] = public[bundle.AUDITOR].replace(needle, f'PREPARED_SHA256 = "{prepared_hash}"'.encode())
    edits[bundle.AUDITOR] = ["PREPARED_SHA256"]
    return public, edits


def release_payloads():
    audit.require_hash(ROOT / bundle.PUBLICATION_MANIFEST, ORIGINAL_PUBLICATION_SHA256)
    audit.verify(ROOT)
    original = {path: repo_file(path) for path in bundle.package_payloads() - {bundle.HISTORICAL, Path("README.md")}}
    public, edits = redact_originals(original)
    public[bundle.HISTORICAL] = json_bytes(historical_rows())
    public[Path("README.md")] = repo_file(Path("docs/PUBLIC_EVIDENCE.md"))
    inventory = {}
    for path, data in public.items():
        item = fingerprint(data)
        if path in edits:
            item.update(original=fingerprint(original[path]), changed_fields=edits[path])
        else:
            audit.check(path not in original or original[path] == data, path, "unlogged byte change")
        inventory[path.as_posix()] = item
    public[bundle.MANIFEST] = json_bytes({
        "schema_version": 1,
        "frozen_study_revision": audit.REVISION,
        "historical_preparation_sha256": audit.PREPARED_SHA256,
        "public_preparation_sha256": fingerprint(public[bundle.FROZEN_PREPARATION])["sha256"],
        "files": inventory,
    })
    portal = {Path(name): repo_file(Path("frontend/public/evidence") / name) for name in PORTAL_FILES}
    audit.check(set(public) == bundle.package_payloads() | {bundle.MANIFEST}, "exact archive allowlist")
    scan_public_bytes({**public, **portal})
    return public


def build_archive(destination, payloads):
    with ZipFile(destination, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(payloads.items()):
            member = ZipInfo(path.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            archive.writestr(member, data, compress_type=ZIP_DEFLATED, compresslevel=9)


def verify_build(payloads):
    archive_path = OUTPUT_DIR / ARCHIVE
    with ZipFile(archive_path) as archive:
        audit.check(archive.namelist() == [path.as_posix() for path in sorted(payloads)], "exact ordered archive inventory")
        for path, data in payloads.items():
            member = archive.getinfo(path.as_posix())
            audit.check(member.date_time == (1980, 1, 1, 0, 0, 0) and member.create_system == 3
                        and member.external_attr == 0o100644 << 16 and member.compress_type == ZIP_DEFLATED,
                        path, "stable archive metadata")
            audit.check(archive.read(member) == data, path, "archive payload differs from the rebuilt copy")
    return archive_path.read_bytes()


def check_public_directory(require_archive):
    audit.check(OUTPUT_DIR.resolve() == OUTPUT_DIR and OUTPUT_DIR.is_dir(), "regular public evidence directory")
    present = set()
    model = {*PORTAL_FILES, ARCHIVE, CHECKSUM}
    allowed = model | {DELIVERY_ARCHIVE, DELIVERY_CHECKSUM, FIXED_ARCHIVE, FIXED_CHECKSUM}
    for path in OUTPUT_DIR.iterdir():
        audit.check(path.name in allowed and path.is_file() and not path.is_symlink(),
                    path.name, "unexpected file in the public evidence directory")
        present.add(path.name)
    required = model if require_archive else set(PORTAL_FILES)
    audit.check(required <= present, "complete public evidence directory")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check the payloads and checksum of the checked-in download")
    args = parser.parse_args()
    check_public_directory(require_archive=args.check)
    payloads = release_payloads()
    if args.check:
        data = verify_build(payloads)
    else:
        with TemporaryDirectory(prefix="proofflow-evidence-") as temporary:
            archive = Path(temporary) / ARCHIVE
            build_archive(archive, payloads)
            data = archive.read_bytes()
        (OUTPUT_DIR / ARCHIVE).write_bytes(data)
    checksum = f"{sha256(data).hexdigest()}  {ARCHIVE}\n".encode()
    target = OUTPUT_DIR / CHECKSUM
    if args.check:
        audit.check(target.read_bytes() == checksum, CHECKSUM, "download checksum differs")
    else:
        target.write_bytes(checksum)
    check_public_directory(require_archive=True)
    print(f"{len(data):,} bytes • {checksum.decode().strip()}")


if __name__ == "__main__":
    main()
