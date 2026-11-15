#!/usr/bin/env python3
"""Export reviewed study witnesses and build the standalone fixed-budget ZIP."""

from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import re

import audit_model_comparison_v4 as audit
from build_public_evidence import (
    FIXED_ARCHIVE, FIXED_CHECKSUM, OUTPUT_DIR, ROOT, build_archive, check_public_directory,
    redact_case, repo_file, scan_public_bytes,
)
import verify_fixed_budget_evidence as fixed


DOCUMENTATION = Path("docs/PUBLIC_FIXED_BUDGET_EVIDENCE.md")
LOOPBACK = re.compile(r"http://127\.0\.0\.1:\d+/?")
ARCHIVE_FILES = ("post_snapshot", "scoring_result", "independent_audit")


def regular_file(path):
    audit.check(path.is_file() and path.resolve() == path, path.name, "regular retained study artifact")
    return path.read_bytes()


def export_witnesses(private):
    recovered = fixed.read_jsonl(ROOT / fixed.RECOVERED)
    audit.require_hash(ROOT / fixed.RECOVERED, fixed.RECOVERED_CELLS_SHA256)
    anchors = {case: audit.load(ROOT / audit.PREPARED / case / "initial_records.json") for case in fixed.CASES}
    output = []
    archived_scores = set()
    for case, recovered_row in zip(fixed.cells(), recovered, strict=True):
        job = case["cell_id"]
        truth = recovered_row["score"]
        audit.check(recovered_row["cell_id"] == job, job, "retained observation order")
        root = private / job / "execution"
        raw = {kind: regular_file(root / f"{kind}.json") for kind in ARCHIVE_FILES}
        original = {kind: fixed.binding(data) for kind, data in raw.items()}
        archive_keys = {"post_snapshot": "post_snapshot_sha256", "scoring_result": "retained_scoring_result_sha256",
                        "independent_audit": "independent_audit_sha256"}
        audit.check(all(original[kind]["sha256"] == truth[key] for kind, key in archive_keys.items()),
                    job, "retained archive matches independently reviewed outcome hashes")
        document = {kind: audit.load(root / f"{kind}.json") for kind in raw}
        audit.check(all(fixed.json_bytes(document[kind]) == blob for kind, blob in raw.items()),
                    job, "round-trip exact retained snapshot and scorer serialization")
        archived_scores.add(root / "scoring_result.json")
        score = document["scoring_result"]
        for kind in ("post_snapshot", "independent_audit"):
            path = score.pop(f"{kind}_path")
            audit.check(Path(path).is_absolute() and Path(path).parts[-len((Path(job) / "execution" / f"{kind}.json").parts):]
                        == (Path(job) / "execution" / f"{kind}.json").parts,
                        job, kind, "only the known private scorer path is withheld")
        anchor, post = anchors[case["case_id"]], document["post_snapshot"]
        audit.check(all(post["records"].get(key) == value for key, value in anchor["records"].items())
                    and post["source_heads"] == anchor["source_heads"] and post["tool_heads"] == anchor["tool_heads"],
                    job, "complete matching anchor before compacting")
        witness = {
            "cell_id": job, "artifact_heads": post["artifact_heads"],
            "new_records": {key: value for key, value in post["records"].items() if key not in anchor["records"]},
            "audit": document["independent_audit"], "score": score, "original": original,
            "public_score": fixed.binding(fixed.json_bytes(score)), "score_redactions": list(fixed.KNOWN_SCORE_REDACTIONS),
        }
        audit.check(fixed.reconstruct_snapshot(witness, anchor) == post, job, "lossless poststate delta")
        output.append(audit.canon(witness).encode() + b"\n")
    audit.check(archived_scores == set(private.glob("M*/**/execution/scoring_result.json")),
                "exact retained scorer inventory")
    data = b"".join(output)
    scan_public_bytes({fixed.EVIDENCE: data})
    (ROOT / fixed.EVIDENCE).write_bytes(data)


def public_copy(path, original):
    if path not in fixed.redacted_paths():
        return original, []
    record = audit.load(ROOT / path)
    if path in {fixed.FREEZE, fixed.RUN_MANIFEST}:
        audit.check(LOOPBACK.fullmatch(record["hydra"].pop("url")), path, "known loopback study endpoint")
        changes = ["/hydra/url"]
    else:
        changes = []
        redact_case(record, changes)
    audit.check(changes == fixed.redaction_fields(path), path, "exact redactions")
    return fixed.json_bytes(record), changes


def payloads():
    data, entries = {}, {}
    sources = {**{path: path for path in fixed.source_paths()}, Path("README.md"): DOCUMENTATION}
    for path, source in sources.items():
        original = repo_file(source)
        public, changes = public_copy(path, original)
        info = fixed.binding(public)
        if changes:
            info.update(original=fixed.binding(original), changed_fields=changes)
        data[path] = public
        entries[path.as_posix()] = info
    data[fixed.MANIFEST] = fixed.json_bytes({"schema_version": 1, "frozen_study_revision": fixed.REVISION, "files": entries})
    scan_public_bytes(data)
    for path, body in data.items():
        audit.check(not re.search(rb'https?://(?:localhost|127\.0\.0\.1)', body), path, "no local endpoint")
    return data


def check_zip(path, data):
    with ZipFile(path) as archive:
        audit.check(archive.namelist() == [path.as_posix() for path in sorted(data)], "exact fixed-budget ZIP inventory")
        for name, expected in data.items():
            member = archive.getinfo(name.as_posix())
            audit.check(member.date_time == (1980, 1, 1, 0, 0, 0) and member.create_system == 3
                        and member.external_attr == 0o100644 << 16 and member.compress_type == ZIP_DEFLATED
                        and archive.read(member) == expected, name, "stable ZIP metadata and exact public bytes")


def main():
    parser = ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="verify the checked-in package against the frozen inputs")
    operation.add_argument("--export-witnesses", type=Path, metavar="RETAINED_RUN",
                           help="one-time read-only projection of the original private execution JSON")
    args = parser.parse_args()
    if args.export_witnesses:
        export_witnesses(args.export_witnesses.resolve())
        return
    check_public_directory(require_archive=True)
    data = payloads()
    destination, checksum = OUTPUT_DIR / FIXED_ARCHIVE, OUTPUT_DIR / FIXED_CHECKSUM
    with TemporaryDirectory(prefix="proofflow-fixed-budget-evidence-") as temporary:
        stage = Path(temporary).resolve() / "evidence"
        for name, body in data.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        result = fixed.verify(stage)
        if args.check:
            check_zip(destination, data)
        else:
            archive = stage.parent / FIXED_ARCHIVE
            build_archive(archive, data)
            destination.write_bytes(archive.read_bytes())
    blob = destination.read_bytes()
    sidecar = f"{audit.sha(blob)}  {FIXED_ARCHIVE}\n".encode()
    if args.check:
        audit.check(checksum.read_bytes() == sidecar, "fixed-budget SHA-256 sidecar matches")
    else:
        checksum.write_bytes(sidecar)
    print(f"{len(blob):,} bytes, {result['verified_cells']} verified cells, SHA-256 {audit.sha(blob)}")


if __name__ == "__main__":
    main()
