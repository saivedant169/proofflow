"""Check the public navigation receipt and its retained historical bindings."""

import json
from pathlib import Path

import pytest

from scripts import public_download_acceptance as acceptance


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "frontend/public/agent"
RECEIPT = AGENT / acceptance.NAVIGATION_RECEIPT


def test_receipt_is_bound_to_the_audited_bytes_and_public_routes():
    data = RECEIPT.read_bytes()
    acceptance.verify_sidecar(data, RECEIPT.with_suffix(".json.sha256").read_bytes(), RECEIPT.name)
    summary = acceptance.verify_navigation_receipt(data)
    assert summary["obligations_passed"] == 8 and summary["matched_results"] == 13
    assert summary["stale_export_attempted"] is False

    paths = acceptance.EVIDENCE_FILES | acceptance.DELIVERY_FILES | acceptance.FIXED_FILES | acceptance.AGENT_FILES
    assert len(paths) == 14
    assert paths[f"/agent/{RECEIPT.name}"] == (f"agent/{RECEIPT.name}", "application/json")
    assert paths[f"/agent/{RECEIPT.name}.sha256"] == (f"agent/{RECEIPT.name}.sha256", None)
    page = (AGENT / "index.html").read_text()
    assert f'href="{RECEIPT.name}"' in page and f'href="{RECEIPT.name}.sha256"' in page


def test_rehashed_receipt_mutation_fails_the_independent_audit_binding():
    report = json.loads(RECEIPT.read_bytes())
    report["export"]["stale_export_attempted"] = True
    data = json.dumps(report).encode()
    sidecar = f"{acceptance.digest(data)}  {RECEIPT.name}\n".encode()
    acceptance.verify_sidecar(data, sidecar, RECEIPT.name)
    with pytest.raises(acceptance.CheckFailure, match="independently audited bytes"):
        acceptance.verify_navigation_receipt(data)
