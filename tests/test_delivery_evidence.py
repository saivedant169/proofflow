"""Verify the public delivery package without starting any services."""

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend/public/evidence"
DELIVERY = PUBLIC / "proofflow-delivery-evidence.zip"
RECEIPT = "results/real-partition-v1/receipt.json"


def digest(data):
    return sha256(data).hexdigest()


@pytest.fixture
def extracted(tmp_path):
    with ZipFile(DELIVERY) as archive:
        names = archive.namelist()
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
        assert len(set(names)) == len(names)
        archive.extractall(tmp_path)
    return tmp_path


def verify(path):
    return subprocess.run([sys.executable, "-B", str(path / "verify_delivery_evidence.py")], cwd=path,
                          capture_output=True, text=True, env={"PATH": os.defpath}, timeout=30, check=False)


def test_offline_delivery_archive_checks_receipts_and_original_model_zip(extracted):
    assert digest(DELIVERY.read_bytes()) == DELIVERY.with_suffix(".zip.sha256").read_text().split()[0]
    model = PUBLIC / "proofflow-model-evidence.zip"
    assert digest(model.read_bytes()) == "996d670a4d49929ff4eefc01441e8fa05d29099a45e109f4e73b3dbbf9c40be7"
    completed = verify(extracted)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["real_partition"] == dict(rows=642, invoices=25, initial_usd_cents=905258,
                                            corrected_usd_cents=941468, verified_phases=6)
    paired = result["paired_workflow"]
    assert paired["stale_refusals_per_method"] == 4 and paired["proofflow_retained_heads_and_receipts"] == [0, 4, 2]
    assert result["hosted"]["restart_transient_502s"] == 2
    assert result["interrupted_update"]["checks_passed"] == result["interrupted_update"]["linux_replication_checks_passed"] == 15
    diagnostic = result["fixed_budget_diagnostic"]
    assert diagnostic["original_completed"] is False
    assert diagnostic["original_wrapper_execution_errors"] == diagnostic["recovered_scored_cells"] == 88
    assert diagnostic["fresh_affected"]["fixed_8192"]["iterative_hybrid"] == 28


def test_resealed_one_cent_mutation_is_rejected_by_independent_arithmetic(extracted):
    receipt_path = extracted / RECEIPT
    receipt = json.loads(receipt_path.read_bytes())
    receipt["initial"]["revenue_usd_cents"]["company"] += 1
    changed = json.dumps(receipt, indent=2).encode()
    receipt_path.write_bytes(changed)
    manifest_path = extracted / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"][RECEIPT].update(bytes=len(changed), sha256=digest(changed))
    manifest_path.write_text(json.dumps(manifest))
    completed = verify(extracted)
    assert completed.returncode == 1
    assert "Independent real arithmetic differs from saved report revenue" in completed.stderr


def test_delivery_verifier_rejects_unlisted_files(extracted):
    (extracted / "extra.txt").touch()
    completed = verify(extracted)
    assert completed.returncode == 1
    assert "Exact extracted delivery bundle files" in completed.stderr


def test_delivery_verifier_rejects_manifest_symlink_and_extra_directory(extracted, tmp_path_factory):
    spurious = extracted / "unexpected"
    spurious.mkdir()
    completed = verify(extracted)
    assert completed.returncode == 1
    assert "Exact extracted delivery bundle files" in completed.stderr
    spurious.rmdir()

    outside = tmp_path_factory.mktemp("private") / "manifest.json"
    manifest = extracted / "manifest.json"
    manifest.replace(outside)
    manifest.symlink_to(outside)
    completed = verify(extracted)
    assert completed.returncode == 1
    assert "Regular delivery evidence file: manifest.json" in completed.stderr
