"""Check the downloaded fixed-budget witness without the app or tokenizer package."""

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
ARCHIVE = PUBLIC / "proofflow-fixed-budget-evidence.zip"
WITNESS = "evidence/fixed_budget_witnesses_v1.jsonl"


def digest(blob):
    return sha256(blob).hexdigest()


@pytest.fixture
def extracted(tmp_path):
    with ZipFile(ARCHIVE) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
        archive.extractall(tmp_path)
    return tmp_path


def verify(directory):
    return subprocess.run(
        [sys.executable, "-E", "-s", "-S", str(directory / "scripts/verify_fixed_budget_evidence.py")],
        cwd=directory, env={"PATH": os.defpath}, capture_output=True, text=True, timeout=60, check=False,
    )


def test_portable_fixed_budget_verifier_and_unchanged_prior_archives(extracted):
    assert ARCHIVE.with_suffix(".zip.sha256").read_text() == f"{digest(ARCHIVE.read_bytes())}  {ARCHIVE.name}\n"
    assert digest((PUBLIC / "proofflow-model-evidence.zip").read_bytes()) == (
        "996d670a4d49929ff4eefc01441e8fa05d29099a45e109f4e73b3dbbf9c40be7"
    )
    assert digest((PUBLIC / "proofflow-delivery-evidence.zip").read_bytes()) == (
        "a04416f1232112b253c9953e974f606b66882a895b55b8d7f1cfdaf87e293791"
    )
    result = verify(extracted)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["verified_cells"] == len(report["cells"]) == report["original_wrapper_execution_errors"] == 88
    assert report["bundle_files_verified"] == 249 and report["reconstructed_source_rows"] == 4681
    assert report["original_completed"] is False
    assert all(group["reports_observed"]["unavailable_blocked"] == 4
               and group["reports_observed"]["unaffected_preserved"] == 52
               and group["reports_observed"]["incorrect_current"] == 0 for group in report["groups"])
    rows = {item["id"]: item for item in report["cells"]}
    assert rows["M05/fixed_8192/graph"]["fresh_affected"] == 6
    assert rows["M05/fixed_8192/iterative_hybrid"]["fresh_affected"] == 7
    assert rows["M07/uncapped_reference/full_context"]["correctly_blocked"] == 4
    assert all(group["matching_contexts"] == 8 for group in report["graph_exact_flat_context_parity"].values())


def test_resealed_one_cent_edit_reaches_independent_arithmetic(extracted):
    path = extracted / WITNESS
    first, tail = path.read_bytes().split(b"\n", 1)
    row = json.loads(first)
    assert row["cell_id"] == "M01/fixed_4096/graph"
    report_id = row["artifact_heads"]["artifact:2011-03-02:daily_close"]
    row["new_records"][report_id]["value"]["sections"][0]["value"] += 1
    changed = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\n" + tail
    path.write_bytes(changed)
    manifest_path = extracted / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"][WITNESS].update(bytes=len(changed), sha256=digest(changed))
    manifest_path.write_text(json.dumps(manifest))
    result = verify(extracted)
    assert result.returncode == 1
    assert "independent Decimal output mismatch" in result.stderr
    assert "M01/fixed_4096/graph" in result.stderr


def test_verifier_rejects_unlisted_entry_and_symbolic_link_before_read(extracted, tmp_path_factory):
    extra = extracted / "empty-unlisted-dir"
    extra.mkdir()
    result = verify(extracted)
    assert result.returncode == 1 and "exact extracted fixed-budget inventory" in result.stderr
    extra.rmdir()

    helper = extracted / "scripts/fixed_budget_tokenizer.py"
    outside = tmp_path_factory.mktemp("linked-helper") / helper.name
    helper.replace(outside)
    helper.symlink_to(outside)
    result = verify(extracted)
    assert result.returncode == 1 and "helper verification failed" in result.stderr
