#!/usr/bin/env python3
"""Package the explicitly allowed saved delivery and recovery observations."""

from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import json
import re

from build_public_evidence import DELIVERY_ARCHIVE, DELIVERY_CHECKSUM, OUTPUT_DIR, build_archive
from build_public_evidence import check_public_directory, json_bytes, repo_file, scan_public_bytes
import verify_delivery_evidence as delivery


README = Path("docs/PUBLIC_DELIVERY_EVIDENCE.md")
PRIVATE_RUN_URL = re.compile(r"https://github\.com/[^/]+/[^/]+/actions/runs/(\d+)(?:/artifacts/(\d+))?")

def parent_key(document, path):
    for key in path[:-1]:
        document = document[key]
    return document, path[-1]


def redact(path, original):
    fields = delivery.PRIVATE_RECEIPT_FIELDS.get(path, ())
    urls = delivery.PRIVATE_RUN_FIELDS.get(path, ())
    if not fields and not urls:
        return original, []
    document = json.loads(original)
    for field in fields:
        parent, key = parent_key(document, field)
        del parent[key]
    for field in urls:
        parent, key = parent_key(document, field)
        match = PRIVATE_RUN_URL.fullmatch(parent[key])
        delivery.require(match is not None, f"Unexpected private-run URL field: {path} {delivery.pointer(field)}")
        run, artifact = match.groups()
        parent[key] = f"GitHub Actions run {run}" + (f", artifact {artifact}" if artifact else "")
    return json_bytes(document), delivery.redacted_fields(path)


def payloads():
    data, inventory = {}, {}
    for name, source in {**{path: path for path in delivery.source_files()}, Path("README.md"): README,
                         delivery.VERIFIER: Path("scripts") / delivery.VERIFIER}.items():
        original = repo_file(source)
        public, changes = redact(name, original)
        info = delivery.binding(public)
        if changes:
            info.update(original=delivery.binding(original), changed_fields=changes)
        data[name] = public
        inventory[name.as_posix()] = info
    data[delivery.MANIFEST] = json_bytes({"schema_version": 1, "files": inventory})
    scan_public_bytes(data)
    historical = json.loads(repo_file(delivery.HOSTED[0]))
    direct_ip = historical["domain_verification"]["dns"]["ipv4_address"].encode()
    withheld_values = {direct_ip}
    for name, fields in delivery.PRIVATE_RECEIPT_FIELDS.items():
        record = json.loads(repo_file(name))
        for field in fields:
            if field[-1] in {"session_id", "generation", "workspace_id", "workspace_directory", "namespace"}:
                parent, key = parent_key(record, field)
                withheld_values.add(parent[key].encode())
    for name, blob in data.items():
        delivery.require(not any(value in blob for value in withheld_values), f"Withheld receipt identifier in public evidence: {name}")
    for name, blob in data.items():
        delivery.require(not PRIVATE_RUN_URL.search(blob.decode("utf-8")), f"Private run URL in public evidence: {name}")
    return data


def check_archive(path, expected):
    with ZipFile(path) as archive:
        names = sorted(expected)
        delivery.require(archive.namelist() == [path.as_posix() for path in names], "Exact delivery ZIP inventory")
        for name in names:
            member = archive.getinfo(name.as_posix())
            delivery.require(member.date_time == (1980, 1, 1, 0, 0, 0) and member.create_system == 3
                             and member.external_attr == 0o100644 << 16 and member.compress_type == ZIP_DEFLATED,
                             f"Stable delivery archive metadata: {name}")
            delivery.require(archive.read(member) == expected[name], f"Delivery archive payload drift: {name}")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify checked-in ZIP and checksum against the allowlist")
    args = parser.parse_args()
    check_public_directory(require_archive=True)
    expected = payloads()
    archive_path = OUTPUT_DIR / DELIVERY_ARCHIVE
    checksum_path = OUTPUT_DIR / DELIVERY_CHECKSUM
    with TemporaryDirectory(prefix="proofflow-delivery-evidence-") as temp:
        temp = Path(temp).resolve()
        extracted = temp / "bundle"
        for name, blob in expected.items():
            dest = extracted / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
        result = delivery.verify(extracted)
        if args.check:
            check_archive(archive_path, expected)
        else:
            draft = temp / DELIVERY_ARCHIVE
            build_archive(draft, expected)
            archive_path.write_bytes(draft.read_bytes())
    data = archive_path.read_bytes()
    checksum = f"{delivery.digest(data)}  {DELIVERY_ARCHIVE}\n".encode()
    if args.check:
        delivery.require(checksum_path.read_bytes() == checksum, "Delivery ZIP checksum mismatch")
    else:
        checksum_path.write_bytes(checksum)
    print(f"{len(data):,} bytes, {result['bundle_files_verified']} verified payloads, SHA-256 {delivery.digest(data)}")


if __name__ == "__main__":
    main()
