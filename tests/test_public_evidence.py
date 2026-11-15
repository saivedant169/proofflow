"""Check the distributed evidence in an isolated directory, without the app."""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
import os
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "frontend/public/evidence/proofflow-model-evidence.zip"
RUN = Path("results/model-v4-test-run-1")
PUBLICATION = RUN / "publication/publication_manifest.json"
SNAPSHOT = RUN / "M01/graph/execution/post_snapshot.json"


def binding(data):
    return {"bytes": len(data), "sha256": sha256(data).hexdigest()}


def load(path):
    return json.loads(path.read_bytes())


def write(path, record):
    data = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(data)
    return binding(data)


@pytest.fixture
def portable_copy(tmp_path):
    with ZipFile(ARCHIVE) as bundle:
        names = bundle.namelist()
        manifest = json.loads(bundle.read("manifest.json"))
        assert sorted(names) == sorted([*manifest["files"], "manifest.json"])
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
        bundle.extractall(tmp_path)
    return tmp_path


def verify(portable_copy):
    return subprocess.run(
        [sys.executable, "-B", str(portable_copy / "scripts/verify_public_evidence.py")],
        cwd=portable_copy,
        env={"PATH": os.defpath},
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_portable_copy_checks_48_saved_model_cells_and_earlier_failures(portable_copy):
    checksum = ARCHIVE.with_suffix(".zip.sha256").read_text().split()[0]
    assert checksum == sha256(ARCHIVE.read_bytes()).hexdigest()
    completed = verify(portable_copy)
    assert completed.returncode == 0, completed.stderr
    verified = json.loads(completed.stdout)
    model = verified["model_study"]
    assert model["passed"] and model["scored_cells"] == 48 and model["published_files_verified"] == 152
    assert model["reconstructed_source_rows"] == 4681
    assert model["fresh_affected"] == {
        "graph": 32, "exact_flat": 32, "full_context": 32, "bm25": 25, "dense": 5, "iterative_hybrid": 28,
    }
    provider = model["provider_input_non_noop"]
    assert (provider["graph"], provider["full_context"]) == (75422, 191774)
    earlier = verified["earlier_studies"]
    assert earlier["pilot_fixed_2048"]["graph"] == {"fresh": 16, "eligible": 29}
    assert earlier["retail_fixed_2048"]["graph"] == {"fresh": 8, "eligible": 38}
    dev = earlier["retail_development"]
    assert (dev["graph_tokens"], dev["full_context_tokens"], dev["passed"]) == (6752, 11107, False)


def test_one_cent_edit_fails_even_when_outer_and_publication_hashes_are_updated(portable_copy):
    snapshot = load(portable_copy / SNAPSHOT)
    head = snapshot["artifact_heads"]["artifact:2011-03-02:daily_close"]
    snapshot["records"][head]["value"]["sections"][0]["value"] += 1
    changed = write(portable_copy / SNAPSHOT, snapshot)

    publication = load(portable_copy / PUBLICATION)
    publication["files"][SNAPSHOT.as_posix()] = changed
    publication_binding = write(portable_copy / PUBLICATION, publication)

    inventory = load(portable_copy / "manifest.json")
    inventory["files"][SNAPSHOT.as_posix()] = changed
    inventory["files"][PUBLICATION.as_posix()].update(publication_binding)
    write(portable_copy / "manifest.json", inventory)

    completed = verify(portable_copy)
    assert completed.returncode == 1
    assert "independent Decimal output mismatch" in completed.stderr


def test_public_directory_rejects_unlisted_files_and_symlinks(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_public_evidence as builder

    monkeypatch.setattr(builder, "OUTPUT_DIR", tmp_path)
    for filename in (*builder.PORTAL_FILES, builder.ARCHIVE, builder.CHECKSUM):
        (tmp_path / filename).touch()
    builder.check_public_directory(require_archive=True)

    extra = tmp_path / "scratch.txt"
    extra.touch()
    with pytest.raises(builder.audit.AuditError, match="unexpected file in the public evidence directory"):
        builder.check_public_directory(require_archive=True)
    extra.unlink()

    name = tmp_path / builder.CHECKSUM
    name.unlink()
    name.symlink_to(tmp_path / builder.ARCHIVE)
    with pytest.raises(builder.audit.AuditError, match="unexpected file in the public evidence directory"):
        builder.check_public_directory(require_archive=True)
