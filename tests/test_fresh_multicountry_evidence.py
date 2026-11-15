"""Offline evidence checks and resealed negative controls; no app/service calls."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import verify_fresh_multicountry as verifier


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = f"{verifier.RESULTS}/receipt.json"


def reseal(root, label):
    path = root / label
    manifest_path = root / verifier.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    payload = path.read_bytes()
    manifest["files"][label] = {"bytes": len(payload), "sha256": verifier.sha256(payload)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


@pytest.fixture
def package(tmp_path):
    for label in verifier.REQUIRED_FILES:
        destination = tmp_path / label
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / label, destination)
    manifest = {"files": {label: {"bytes": (tmp_path / label).stat().st_size,
                  "sha256": verifier.sha256((tmp_path / label).read_bytes())}
                          for label in sorted(verifier.REQUIRED_FILES)}}
    (tmp_path / verifier.MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return tmp_path


def mutate_receipt(root, mutate):
    path = root / RECEIPT
    receipt = json.loads(path.read_text())
    mutate(receipt)
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    reseal(root, RECEIPT)


def test_complete_projection_and_arithmetic_verify_without_site_packages(package):
    result = subprocess.run([sys.executable, "-S", str(ROOT / "scripts/verify_fresh_multicountry.py"),
                             "--root", str(package)], cwd=package.parent, env={"PATH": os.defpath},
                            text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["rows"] == 933
    assert observed["rows_by_region"] == {"Belgium": 26, "United Kingdom": 907}
    assert observed["receipt"]["semantic_output_checks_per_arm"] == 16
    assert observed["receipt"]["stale_refusals_per_arm"] == observed["receipt"]["current_handoffs_per_arm"] == 2
    assert observed["receipt"]["proofflow_total_invocations"] == 74
    assert observed["receipt"]["proofflow_fx_correction_invocations"] == 31
    assert observed["receipt"]["ordinary_full_csv_scans"] == 2
    assert "not independent attestation" in observed["scope"]


def test_resealed_one_cent_upload_mutation_fails_raw_cell_arithmetic(package):
    label = f"{verifier.FIXTURE}/orders.csv"
    path = package / label
    rows = list(csv.DictReader(io.StringIO(path.read_text())))
    rows[0]["gross_cents"] = str(int(rows[0]["gross_cents"]) + 1)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    reseal(package, label)
    # Prove the cryptographic file check passes; independent arithmetic must fail.
    verifier.verify_manifest(package)
    with pytest.raises(ValueError, match="upload line differs from original worksheet cells"):
        verifier.verify(package)


@pytest.mark.parametrize("arm", ["ordinary", "proofflow"])
def test_resealed_one_cent_receipt_mutation_fails_independent_oracle(package, arm):
    def mutate(receipt):
        receipt[arm]["initial"]["outputs"]["company_report"] += 1
    mutate_receipt(package, mutate)
    verifier.verify_manifest(package)
    with pytest.raises(ValueError, match="Independent raw-cell arithmetic differs"):
        verifier.verify(package)


def test_resealed_counter_mutation_is_not_accepted_as_fewer_calculations(package):
    def mutate(receipt):
        event = next(item for item in receipt["operations"] if item["step"] == "fx-correction.refresh")
        event["actual_calculation_counts"]["verification"] -= 1
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="calculation invocation accounting differs"):
        verifier.verify(package)


def test_resealed_stale_handoff_acceptance_is_rejected(package):
    def mutate(receipt):
        event = next(item for item in receipt["operations"]
                     if item["arm"] == "ordinary" and item["step"] == "fx-correction.old-during")
        event["accepted"] = event["report_content_returned"] = True
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="guarded handoff differs"):
        verifier.verify(package)


def test_resealed_non_export_route_cannot_count_as_current_handoff(package):
    def mutate(receipt):
        event = next(item for item in receipt["operations"]
                     if item["arm"] == "proofflow" and item["step"] == "initial.current")
        event["route"], event["cache_control"] = "/api/import/not-an-export", "public"
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="HTTP method/route differs"):
        verifier.verify(package)


def test_resealed_unrelated_read_cannot_replace_current_state_reload(package):
    def mutate(receipt):
        event = next(item for item in receipt["operations"] if item["step"] == "initial.reload-current")
        event["step"], event["route"] = "unrelated.read", "/health"
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="Complete operation step inventory differs"):
        verifier.verify(package)


def test_resealed_retained_artifact_alias_change_is_rejected(package):
    def mutate(receipt):
        receipt["proofflow"]["fx-correction"]["artifact_ids"]["support"] = "artifact.support.v2"
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="Retained artifact/receipt aliases differ"):
        verifier.verify(package)


def test_resealed_snapshot_preservation_mismatch_is_rejected(package):
    def mutate(receipt):
        event = next(item for item in receipt["operations"]
                     if item["arm"] == "ordinary" and item["step"] == "fx-correction.retained-file")
        event["actual_sha256"] = "0" * 64
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="retained snapshot commitment differs"):
        verifier.verify(package)


def test_resealed_projection_cannot_claim_native_execution_attestation(package):
    mutate_receipt(package, lambda receipt: receipt["projection"].update(native_execution_independently_attested=True))
    with pytest.raises(ValueError, match="attestation limits"):
        verifier.verify(package)


def test_resealed_stale_claim_cannot_be_presented_as_current(package):
    def mutate(receipt):
        claim = receipt["proofflow"]["fx-correction"]["stale_boundary"]["state"][0]["claims"][0]
        claim["value"] = claim["saved_value"]
    mutate_receipt(package, mutate)
    with pytest.raises(ValueError, match="Stale claim leaked current content"):
        verifier.verify(package)


def test_workbook_audit_rejects_wrong_original_before_parsing(package):
    workbook = package / "not-the-original.xlsx"
    workbook.write_bytes(b"This is not the pinned workbook.")
    selection = json.loads((package / verifier.FIXTURE / "selection.json").read_text())
    with pytest.raises(ValueError, match="Original workbook SHA-256 differs"):
        verifier.audit_workbook(workbook, package / verifier.FIXTURE, selection)
