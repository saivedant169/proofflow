"""Check the normalized multi-country evidence and raw-cell arithmetic offline.

This verifies file integrity, arithmetic, and consistency of a normalized public
projection. It does not independently attest the private native-service run.
The optional original-workbook audit independently parses the pinned XLSX using
only Python's standard library. No application, service, or network is called.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

try:
    from scripts.fresh_multicountry_oracle import audit_fixture, build_cases
except ModuleNotFoundError:
    from fresh_multicountry_oracle import audit_fixture, build_cases


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "fixtures/fresh_multicountry_v1"
RESULTS = "results/fresh-multicountry-v1"
MANIFEST = f"{RESULTS}/manifest.json"
WORKBOOK_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
FROZEN_ORACLE_SHA256 = "6312e034b4dae557f55ef182441805823e8f416b05ccb3bc73eec0cbd9b07d53"
EXCLUDED_MONTHS = ["2010-12", "2011-01", "2011-02", "2011-03", "2011-05",
                   "2011-06", "2011-08", "2011-09", "2011-11"]
REQUIRED_FILES = {
    *(f"{FIXTURE}/{name}" for name in ("orders.csv", "source_cells.csv", "selection.json",
                                      "cases.json", "oracle-audit.json", "fixture.json", "DATASET_NOTICE.md")),
    "docs/FRESH_MULTICOUNTRY_RESULTS.md", "docs/FRESH_MULTICOUNTRY_PROTOCOL.md",
    "scripts/fresh_multicountry_oracle.py", "scripts/verify_fresh_multicountry.py",
    "tests/test_fresh_multicountry_evidence.py", f"{RESULTS}/receipt.json",
}
OUTPUTS = {"gross", "refunds", "net", "regional", "company", "support", "company_report", "region_report"}
FX_OUTPUTS = {"regional", "company", "company_report", "region_report"}
RETAINED_OUTPUTS = OUTPUTS - FX_OUTPUTS
SOURCE_COMMIT = "c2c19c1397026e136bf7648ddb0604a4d2ea6d7f"
PREREGISTRATION = {
    "freeze_sha256": "855e22cec6cc68afd80cb0b2f4c98749e06cdaaf76b1551cb50c6241204d2cdd",
    "protocol_sha256": "a3d1ac8b8820e632e341373efaa983717275d34a324c63dbe0f50b3204987c84",
    "selection_freeze_sha256": "e48684119133192701991364c661b9d757386c57169ef49925a971210d3a2894",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: object, *, pretty: bool = False) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      indent=2 if pretty else None).encode("utf-8") + (b"\n" if pretty else b"")


def same(first: object, second: object) -> bool:
    """JSON equality also distinguishes true/false from integer one/zero."""
    return canonical(first) == canonical(second)


def digest_string(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def checked_path(root: Path, label: str) -> Path:
    relative = PurePosixPath(label)
    require(not relative.is_absolute() and ".." not in relative.parts
            and relative.as_posix() == label and bool(relative.parts), "Manifest path must be relative")
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink(), f"Evidence path must not be a symlink: {label}")
    require(current.is_file(), f"Evidence file is absent: {label}")
    return current


def verify_manifest(root: Path) -> dict:
    manifest = read_json(checked_path(root, MANIFEST))
    require(set(manifest["files"]) == REQUIRED_FILES, "Manifest must enumerate exactly the declared evidence files")
    for label, record in manifest["files"].items():
        payload = checked_path(root, label).read_bytes()
        require(record == {"bytes": len(payload), "sha256": sha256(payload)}, f"Evidence hash/size mismatch: {label}")
    require(manifest["files"]["scripts/fresh_multicountry_oracle.py"]["sha256"] == FROZEN_ORACLE_SHA256,
            "Independent oracle is not the exact frozen source")
    return manifest


def verify_fixture(root: Path) -> tuple[dict, dict, dict]:
    directory = root / FIXTURE
    fixture = read_json(directory / "fixture.json")
    require(fixture["schema_version"] == 1 and fixture["study"] == "fresh-multicountry-v1"
            and fixture["source_commit"] == SOURCE_COMMIT and fixture["selection_file"] == "selection.json"
            and fixture["oracle_file"] == "cases.json" and fixture["preregistration"] == PREREGISTRATION,
            "Fixture provenance differs from the declared study")
    require(fixture["source"]["workbook_sha256"] == WORKBOOK_SHA256
            and fixture["source"]["doi"] == "10.24432/C5BW33" and fixture["source"]["license"] == "CC BY 4.0"
            and fixture["missing_observations"] == ["refund_cents", "ticket_count"]
            and "not an unseen or sealed holdout" in fixture["claim_scope"], "Fixture attribution or scope differs")
    selection = read_json(directory / "selection.json")
    require(selection["excluded_months"] == EXCLUDED_MONTHS, "Frozen excluded months differ")
    require(selection["workbook_sha256"] == WORKBOOK_SHA256 and selection["workbook_rows"] == 541_909,
            "Original workbook identity differs")
    require(selection["selected_date"] == "2011-04-10" and selection["rows"] == 933
            and selection["invoices"] == 32 and selection["rows_by_region"] == {"Belgium": 26, "United Kingdom": 907}
            and selection["selected_region"] == "United Kingdom", "Frozen selected population differs")
    require(selection["invoice_overlap_with_excluded_months"] == 0,
            "Selected invoices overlap excluded months")
    audit = audit_fixture(directory, selection["selected_region"])
    for key in ("selected_date", "rows", "invoices", "rows_by_region", "selected_region", "files"):
        require(audit[key] == selection[key], f"Independent source audit differs: {key}")
    require(audit == read_json(directory / "oracle-audit.json"), "Independent source audit differs from saved audit")
    candidates = selection["candidate_profiles_through_selected_date"]
    require([item["date"] for item in candidates] == sorted({item["date"] for item in candidates}),
            "Candidate dates are not unique chronological days")
    for item in candidates:
        require(item["date"][:7] not in EXCLUDED_MONTHS and sum(item["counts"].values()) == item["rows"]
                and sum(item["countries"].values()) == item["counts"].get("eligible", 0),
                "Candidate profile counts are inconsistent")
    qualifying = [item for item in candidates if 1 <= item["counts"].get("eligible", 0) <= 1000
                  and len(item["countries"]) >= 2]
    require(len(qualifying) == 1 and qualifying[0] == candidates[-1]
            and qualifying[0]["date"] == selection["selected_date"], "Candidate profiles do not establish first qualifying day")
    cases = read_json(directory / "cases.json")
    require(cases["cases"] == build_cases(directory, selection["selected_region"]),
            "Independent raw-cell arithmetic differs from frozen case values")
    require(cases["selected_region"] == selection["selected_region"]
            and cases["region_currencies"] == audit["region_currencies"], "Frozen case country/currency scope differs")
    return selection, audit, cases


def _eligible_original(index: int, cells: dict[str, str]) -> tuple[dict | None, str]:
    """Independent implementation of the frozen raw-cell eligibility policy."""
    invoice, country = cells.get("A", "").strip(), cells.get("H", "").strip()
    identifier = f"uci:{invoice}:row:{index}"
    if invoice.upper().startswith("C"):
        return None, "cancellation_invoice"
    if (not invoice or not country or len(country) > 64 or country.startswith("__")
            or len(identifier) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in country + identifier)):
        return None, "invalid_invoice_or_country"
    try:
        quantity, price = Decimal(str(float(cells["D"]))), Decimal(str(float(cells["F"])))
        if not quantity.is_finite() or not 0 < quantity <= 10**9 or quantity != quantity.to_integral_value():
            return None, "invalid_quantity"
        if not price.is_finite() or price <= 0:
            return None, "invalid_price"
        pence = quantity * price * 100
        if pence != pence.to_integral_value():
            return None, "fractional_line_pence"
        if not 0 < pence <= 10**12:
            return None, "line_amount_outside_bounds"
    except (KeyError, ValueError, InvalidOperation, OverflowError):
        return None, "invalid_numeric_cells"
    return {
        "source_row": str(index), "invoice_no": invoice, "invoice_date_raw_xml": cells["E"],
        "quantity_raw_xml": cells["D"], "unit_price_raw_xml": cells["F"], "country": country,
    }, "eligible"


def audit_workbook(workbook: Path, fixture_dir: Path, selection: dict) -> dict:
    """Verify original cells, whole-day completeness and prospective selection.

    Source inspection includes all invoice IDs in excluded months to recheck the
    overlap boundary. Only candidate dates through the selected date are profiled.
    Customer and product fields are never returned or written.
    """
    require(sha256(workbook.read_bytes()) == WORKBOOK_SHA256, "Original workbook SHA-256 differs")
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    counts, countries = defaultdict(Counter), defaultdict(Counter)
    originals, excluded_invoices = [], set()
    total, previous_index, previous_day = 0, 0, ""
    with ZipFile(workbook) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.text or "" for node in entry.iter(namespace + "t")) for entry in shared]
        with archive.open("xl/worksheets/sheet1.xml") as source:
            for _, row in ET.iterparse(source, events=("end",)):
                if row.tag != namespace + "row":
                    continue
                index = int(row.attrib["r"])
                require(index > previous_index, "Workbook row order is not strictly increasing")
                previous_index = index
                cells = {}
                for cell in row:
                    label = "".join(char for char in cell.attrib.get("r", "") if char.isalpha())
                    value = cell.find(namespace + "v")
                    text = "" if value is None else value.text or ""
                    if cell.attrib.get("t") == "s":
                        text = strings[int(text)]
                    elif cell.attrib.get("t") == "inlineStr":
                        text = "".join(node.text or "" for node in cell.iter(namespace + "t"))
                    cells[label] = text
                row.clear()
                if index == 1:
                    require([cells.get(key) for key in "ABCDEFGH"] == ["InvoiceNo", "StockCode", "Description",
                            "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"], "Workbook header differs")
                    continue
                total += 1
                day = (date(1899, 12, 30) + timedelta(days=int(Decimal(cells["E"])))).isoformat()
                require(day >= previous_day, "Workbook dates are not chronological")
                previous_day = day
                if day[:7] in EXCLUDED_MONTHS:
                    excluded_invoices.add(cells.get("A", "").strip())
                    continue
                if day > selection["selected_date"]:
                    continue
                original, reason = _eligible_original(index, cells)
                counts[day][reason] += 1
                if original is not None:
                    countries[day][original["country"]] += 1
                    if day == selection["selected_date"]:
                        originals.append(original)
    require(total == 541_909, "Original workbook row count differs")
    profiles = [{"date": day, "counts": dict(values), "countries": dict(countries[day]), "rows": sum(values.values())}
                for day, values in sorted(counts.items())]
    require(profiles == selection["candidate_profiles_through_selected_date"], "Original candidate profiles differ")
    qualifying = [item["date"] for item in profiles if 1 <= item["counts"].get("eligible", 0) <= 1000
                  and len(item["countries"]) >= 2]
    require(qualifying == [selection["selected_date"]], "Original workbook does not establish first qualifying date")
    with (fixture_dir / "source_cells.csv").open(encoding="utf-8", newline="") as source:
        require(originals == list(csv.DictReader(source)), "Original workbook differs from complete selected provenance")
    require(not {row["invoice_no"] for row in originals} & excluded_invoices, "Original invoices overlap excluded months")
    return {"workbook_sha256": WORKBOOK_SHA256, "workbook_rows": total, "selected_rows": len(originals),
            "first_qualifying_date": selection["selected_date"], "exact_original_cells": True,
            "complete_selected_day": True, "excluded_invoice_overlap": 0}


def verify_receipt(receipt: dict, cases: dict, selection: dict) -> dict:
    require(receipt["schema_version"] == 1 and receipt["study"] == "fresh-multicountry-v1"
            and receipt["source_commit"] == SOURCE_COMMIT, "Receipt study identity differs")
    projection = receipt["projection"]
    require(projection["kind"] == "sanitized_observation_projection"
            and projection["native_execution_independently_attested"] is False
            and projection["raw_attempt_retained_privately"] is True
            and "aliases" in projection["identifiers"] and "private raw attempt" in projection["scope"],
            "Receipt must disclose its normalized projection and attestation limits")
    require(all(receipt["preregistration"].get(key) == value for key, value in PREREGISTRATION.items())
            and receipt["preregistration"]["independent_pre_execution_review_sha256"]
                == "3149cf93de13fc4ed6817b2ee9468820b8016e44c081545722947a02f42576a4",
            "Receipt preregistration commitments differ")
    require(receipt["independent_postrun_audit_sha256"]
            == "96615fa0204248d030f6e15b4c6ee77970dd5a4ceedcf7050c3147e74ec79bdc", "Post-run audit commitment differs")
    audit = receipt["independent_postrun_audit"]
    require(audit["status"] == "passed" and audit["checks_passed"] == len(audit["checks"]) == 44
            and all(value is True for value in audit["checks"].values()) and len(audit["audit_corrections"]) == 2,
            "Projected private audit record is inconsistent")
    run = receipt["run"]
    require(run["attempt"] == 1 and run["status"] == "passed"
            and run["arm_status"] == {"ordinary": "passed", "proofflow": "passed"}
            and type(run["model_calls"]) is int and run["model_calls"] == 0
            and type(run["hosted_app_writes"]) is int and run["hosted_app_writes"] == 0
            and run["timing_comparison"] is False, "Projected run scope or outcome differs")
    started, finished = (datetime.fromisoformat(run[key]) for key in ("started_at_utc", "finished_at_utc"))
    require(started.utcoffset() == finished.utcoffset() == timedelta(0) and started < finished,
            "Projected run chronology is invalid")
    limitations = " ".join(receipt["limitations"])
    require(all(text in limitations for text in ("not an unseen or sealed holdout", "not observed zero activity",
            "no timing", "not concurrency", "Snapshot bytes remain private", "not independently attested",
            "saved visualization displays seven initial executions")), "Receipt limitations are incomplete")
    raw_hashes = receipt["raw_file_hashes"]
    require(len(raw_hashes) == 17 and sha256(canonical(raw_hashes, pretty=True)) == receipt["raw_hash_manifest_sha256"],
            "Private raw-file hash inventory commitment differs")
    for name, record in raw_hashes.items():
        require(Path(name).name == name and type(record["bytes"]) is int and record["bytes"] > 0
                and digest_string(record["sha256"]), "Invalid private raw-file hash commitment")

    phases = {case["id"]: case for case in cases["cases"]}
    require(set(receipt["ordinary"]) == set(receipt["proofflow"]) == set(phases), "Receipt phase scope differs")
    for phase, case in phases.items():
        source = {"csv_sha256": selection["files"]["orders.csv"]["sha256"], "rates": case["rates"],
                  "region": selection["selected_region"]}
        for arm in ("ordinary", "proofflow"):
            observed = receipt[arm][phase]
            require(same(observed["outputs"], case["expected"]), f"Independent raw-cell arithmetic differs from {arm}/{phase} outputs")
            require(observed["source"] == source and observed["input_revision_sha256"] == sha256(canonical(source)),
                    f"{arm}/{phase} input information differs")
            require(observed["snapshot_sha256"] == raw_hashes[f"{arm}-{phase}.txt"]["sha256"],
                    f"{arm}/{phase} snapshot commitment differs")
        ordinary = receipt["ordinary"][phase]
        accounting = ordinary["recalculation"]
        require(accounting["full_csv_scans"] == 1 and accounting["validated_rows"] == selection["rows"]
                and accounting["input_validation_passed"] is True
                and accounting["fresh_logical_outputs"] == sorted(OUTPUTS)
                and accounting["region_currencies"] == cases["region_currencies"]
                and set(accounting["reconciliation_controls"]) == {
                    "grouped_net_matches_row_net_for_each_region", "support_matches_input_control_total",
                    "company_report_reconciles_to_region_plus_remaining_regions", "selected_report_matches_converted_region"}
                and all(value is True for value in accounting["reconciliation_controls"].values()),
                f"Ordinary {phase} calculation accounting differs")
        require(ordinary["old_values_equal"] == ([] if phase == "initial" else sorted(RETAINED_OUTPUTS)),
                "Ordinary unchanged-value inventory differs")
        calculation = canonical({"outputs": ordinary["outputs"], "accounting": accounting}, pretty=True)
        require(raw_hashes[f"ordinary-{phase}-calculation.json"] == {"bytes": len(calculation), "sha256": sha256(calculation)},
                "Ordinary projected calculation does not match raw-file commitment")
        pf = receipt["proofflow"][phase]
        require(pf["backend"]["engine"] == "HydraDB OSS" and pf["backend"]["fallback"] is False
                and type(pf["backend"]["native_queries"]) is int and pf["backend"]["native_queries"] > 0,
                "Projected native backend fields differ")
        require(set(pf["artifact_ids"]) == set(pf["receipt_ids"]) == OUTPUTS, "Artifact/receipt alias scope differs")
        for name in OUTPUTS:
            version = 2 if phase == "fx-correction" and name in FX_OUTPUTS else 1
            require(pf["artifact_ids"][name] == f"artifact.{name}.v{version}"
                    and pf["receipt_ids"][name] == f"execution.{name}.v{version}", "Retained artifact/receipt aliases differ")
        require(pf["report_ids"] == {key: pf["artifact_ids"][f"{key}_report"] for key in ("company", "region")},
                "Report aliases do not match artifact aliases")
        require(set(pf["sources"]) == {"orders", "refunds", "tickets", "fx"}, "Source alias scope differs")
        for name, item in pf["sources"].items():
            version = 2 if phase == "fx-correction" and name == "fx" else 1
            require(item["id"] == f"source.{name}.v{version}" and item["name"] == name
                    and item["removed"] is False and digest_string(item["content_hash"]), "Source alias/provenance differs")
        require(pf["sources"]["orders"]["summary"] == {"rows": selection["rows"]}
                and pf["sources"]["refunds"]["summary"] == pf["sources"]["tickets"]["summary"] == {"rows": 0}
                and {key: Decimal(value) for key, value in pf["sources"]["fx"]["summary"].items()}
                    == {"GBP": Decimal(case["rates"]["GBP"]), "USD": Decimal(1)}, "Source summaries differ")

    initial, corrected = receipt["proofflow"]["initial"], receipt["proofflow"]["fx-correction"]
    require(initial["stale_boundary"] is None and initial["retained_work"] == {
        "recorded_outputs": sorted(OUTPUTS), "retained_heads_and_receipts": []}, "Initial work inventory differs")
    for name in ("orders", "refunds", "tickets"):
        require(initial["sources"][name] == corrected["sources"][name], "Unaffected source changed")
    work = corrected["retained_work"]
    require(work["recorded_outputs"] == sorted(FX_OUTPUTS) and work["retained_heads_and_receipts"] == sorted(RETAINED_OUTPUTS)
            and set(work["new_receipt_ids"]) == {corrected["receipt_ids"][name] for name in FX_OUTPUTS}
            and len(work["new_receipt_ids"]) == 4, "Corrected work/receipt inventory differs")
    expected_tools = {"regional": "convert_to_usd", "company": "company_total",
                      "company_report": "compose_report", "region_report": "compose_report"}
    require(len(work["tool_calls"]) == 4 and {call["output_id"] for call in work["tool_calls"]}
            == {corrected["artifact_ids"][name] for name in FX_OUTPUTS}, "Corrected recorded outputs differ")
    for call in work["tool_calls"]:
        name = next(name for name in FX_OUTPUTS if corrected["artifact_ids"][name] == call["output_id"])
        require(call["status"] == "success" and call["tool"] == expected_tools[name], "Corrected recorded tool differs")
    boundary = corrected["stale_boundary"]
    require(boundary["affected"] == sorted(FX_OUTPUTS) and boundary["superseded_source_id"] == "source.fx.v1"
            and boundary["updated_sources"] == corrected["sources"] and set(boundary["heads"]) == OUTPUTS,
            "Stale boundary scope or source aliases differ")
    for name, head in boundary["heads"].items():
        require(head["id"] == initial["artifact_ids"][name] and head["kind"] == "artifact"
                and head["current_head"] is True and head["state"] == ("stale" if name in FX_OUTPUTS else "current"),
                "Stale boundary head identity/state differs")
    require(len(boundary["state"]) == 2 and {report["key"] for report in boundary["state"]} == {"company", "region"},
            "Stale report scope differs")
    for report in boundary["state"]:
        name = report["key"]
        require(report["id"] == initial["report_ids"][name] and report["state"] == "stale" and len(report["claims"]) == 1,
                "Stale report identity/state differs")
        claim = report["claims"][0]
        require(claim["value"] is None and claim["state"] == "stale" and claim["unit"] == "USD cents"
                and claim["saved_value"] == phases["initial"]["expected"][f"{name}_report"]
                and claim["artifact_id"] == initial["artifact_ids"]["company" if name == "company" else "regional"],
                "Stale claim leaked current content or lost its historical value")
        require(claim["reasons"] == [{"current_id": "source.fx.v2", "id": "source.fx.v1",
                    "logical_id": "source:csv:fx", "reason": "version_changed"}], "Stale claim version reason differs")
    require(set(receipt["native_stale_paths"]) == {"company", "region"}, "Projected native path scope differs")
    for report, paths in receipt["native_stale_paths"].items():
        require(len(paths) == boundary["native_path_counts"][report] == 1, "Projected native path count differs")
        expected_ids = ["source.fx.v1", "execution.regional.v1", "artifact.regional.v1"]
        if report == "company":
            expected_ids += ["execution.company.v1", "artifact.company.v1"]
        expected_ids += [f"execution.{report}_report.v1", f"artifact.{report}_report.v1"]
        path = paths[0]
        require([node["id"] for node in path["nodes"]] == expected_ids
                and [node["kind"] for node in path["nodes"]] == [label.split(".")[0] for label in expected_ids]
                and path["source_id"] == expected_ids[0] and path["target_id"] == expected_ids[-1],
                "Projected native path aliases are inconsistent")
        edges = [{"source": source, "target": target, "kind": "PRODUCED" if source.startswith("execution.") else "CONSUMED"}
                 for source, target in zip(expected_ids, expected_ids[1:])]
        require(path["edges"] == edges, "Projected native path edge consistency failed")
    accounting = verify_operations(receipt)
    ordinary_payload = canonical(receipt["ordinary"], pretty=True)
    require(raw_hashes["ordinary-progress.json"] == {"bytes": len(ordinary_payload), "sha256": sha256(ordinary_payload)},
            "Ordinary projection differs from its raw-file commitment")
    return {"semantic_output_checks_per_arm": 16, "stale_refusals_per_arm": 2, "current_handoffs_per_arm": 2,
            "retained_head_and_receipt_aliases": sorted(RETAINED_OUTPUTS), "changed_output_aliases": sorted(FX_OUTPUTS),
            "projected_private_postrun_audit_checks": len(audit["checks"]), **accounting}


def verify_operations(receipt: dict) -> dict:
    operations = receipt["operations"]
    keys = [(item["arm"], item["step"]) for item in operations]
    require(len(keys) == len(set(keys)) == 50, "Operation keys are duplicated or scope differs")
    ordinary_steps = ["initial.start", "initial.publish-source", "initial.current", "fx-correction.start",
                      "fx-correction.publish-source", "fx-correction.old-during", "fx-correction.old-after",
                      "fx-correction.current", "fx-correction.retained-file", "passed"]
    http = {
        "health": ("GET", "/health"), "session.bootstrap": ("POST", "/api/session"),
        "initial.preview": ("POST", "/api/import/preview"),
        "initial.create": ("POST", "/api/import/create"),
        "initial.reload-current": ("GET", "/api/import/state"),
        "initial.current": ("POST", "/api/import/export"),
        "fx-correction.preview": ("POST", "/api/import/preview"),
        "fx-correction.update": ("POST", "/api/import/update"),
        "fx-correction.old-during": ("POST", "/api/import/export"),
        "fx-correction.fresh-stale-state": ("GET", "/api/import/state"),
        "fx-correction.stale-evidence.company": ("GET", "/api/import/evidence/<artifact>"),
        "fx-correction.stale-evidence.region": ("GET", "/api/import/evidence/<artifact>"),
        "fx-correction.refresh": ("POST", "/api/import/refresh"),
        "fx-correction.old-after": ("POST", "/api/import/export"),
        "fx-correction.reload-current": ("GET", "/api/import/state"),
        "fx-correction.current": ("POST", "/api/import/export"),
        **{f"{phase}.evidence.{name}": ("GET", "/api/import/evidence/<artifact>")
           for phase in ("initial", "fx-correction") for name in OUTPUTS},
    }
    pf_non_http = {"initial.start", "initial.current-verdict", "fx-correction.start",
                   "fx-correction.old-during-verdict", "fx-correction.old-after-verdict",
                   "fx-correction.current-verdict", "fx-correction.retained-file", "passed"}
    expected_keys = {("ordinary", step) for step in ordinary_steps} | {
        ("proofflow", step) for step in set(http) | pf_non_http}
    require(set(keys) == expected_keys and [step for arm, step in keys if arm == "ordinary"] == ordinary_steps,
            "Complete operation step inventory differs")
    for event in operations:
        expected_http = http.get(event["step"]) if event["arm"] == "proofflow" else None
        if expected_http is None:
            require("method" not in event and "route" not in event, "Unexpected HTTP fields on a non-HTTP event")
        else:
            require((event.get("method"), event.get("route")) == expected_http,
                    f"{event['step']} HTTP method/route differs")
    moments = [datetime.fromisoformat(item["at"]) for item in operations]
    require(moments == sorted(moments)
            and datetime.fromisoformat(receipt["run"]["started_at_utc"]) <= moments[0]
            and moments[-1] <= datetime.fromisoformat(receipt["run"]["finished_at_utc"]), "Operation chronology differs")
    by_key = dict(zip(keys, operations))
    positions = {key: position for position, key in enumerate(keys)}
    require(max(positions["ordinary", step] for step in ordinary_steps)
            < positions["proofflow", "health"], "Arm execution order differs")
    for phase, lower in (("initial", "initial.create"), ("fx-correction", "fx-correction.old-after-verdict")):
        for name in OUTPUTS:
            require(positions["proofflow", lower] < positions["proofflow", f"{phase}.evidence.{name}"]
                    < positions["proofflow", f"{phase}.reload-current"], "Current evidence/read chronology differs")
        require(positions["proofflow", f"{phase}.reload-current"] < positions["proofflow", f"{phase}.current"],
                "Current handoff preceded its fresh-state read")
    require(positions["proofflow", "fx-correction.old-during-verdict"]
            < positions["proofflow", "fx-correction.fresh-stale-state"]
            < min(positions["proofflow", f"fx-correction.stale-evidence.{name}"] for name in ("company", "region"))
            and max(positions["proofflow", f"fx-correction.stale-evidence.{name}"] for name in ("company", "region"))
            < positions["proofflow", "fx-correction.refresh"], "Stale evidence/read chronology differs")
    for arm in ("ordinary", "proofflow"):
        suffix = "-verdict" if arm == "proofflow" else ""
        for step, expected in (("initial.current", True), ("fx-correction.old-during", False),
                               ("fx-correction.old-after", False), ("fx-correction.current", True)):
            event = by_key[arm, step + suffix]
            require(event["accepted"] is expected and event["report_content_returned"] is expected,
                    f"{arm}/{step} guarded handoff differs")
            if arm == "proofflow":
                require(positions[arm, step + suffix] == positions[arm, step] + 1,
                        "Guard verdict is not paired with its export request")
        retained = by_key[arm, "fx-correction.retained-file"]
        require(retained["file"] == f"{arm}-initial.txt"
                and retained["actual_sha256"] == retained["expected_sha256"] == receipt[arm]["initial"]["snapshot_sha256"],
                f"{arm} retained snapshot commitment differs")
    post_steps = [item["step"] for item in operations if item.get("method") == "POST"]
    require(post_steps == ["session.bootstrap", "initial.preview", "initial.create", "initial.current",
                          "fx-correction.preview", "fx-correction.update", "fx-correction.old-during",
                          "fx-correction.refresh", "fx-correction.old-after", "fx-correction.current"],
            "POST operation schedule differs")
    expected_counts = {
        "session.bootstrap": (0, 8, 0), "initial.preview": (8, 0, 0), "initial.create": (8, 8, 11),
        "fx-correction.preview": (8, 0, 0), "fx-correction.update": (8, 0, 0), "fx-correction.refresh": (0, 4, 11),
    }
    categories = ("preflight", "recorded", "verification")
    totals = Counter()
    for event in operations:
        if "method" not in event:
            continue
        require(event["arm"] == "proofflow", "Unexpected HTTP arm")
        step = event["step"]
        expected = dict(zip(categories, expected_counts.get(step, (0, 0, 0))))
        calls = event["analytics_calls"]
        actual = Counter(call["category"] for call in calls)
        require(all(call["status"] == "success" and call["category"] in categories for call in calls)
                and same(event["actual_calculation_counts"], expected)
                and {key: actual[key] for key in categories} == expected,
                f"{step} calculation invocation accounting differs")
        totals.update(actual)
        stale = step in {"fx-correction.old-during", "fx-correction.old-after"}
        require(event["http_status"] == (409 if stale else 200), f"{step} HTTP outcome differs")
        if event["route"] == "/api/import/export":
            require(event["cache_control"] == "no-store" and not calls, "Export caching/calculation behavior differs")
        if stale:
            require(event["error"]["code"] == "evidence_unavailable", "Stale export refusal code differs")
        else:
            require(event["error"] is None, f"Unexpected error on {step}")
    require(dict(totals) == {"recorded": 20, "preflight": 32, "verification": 22}, "Total invocation accounting differs")
    return {"proofflow_invocations_including_bootstrap": dict(totals), "proofflow_total_invocations": sum(totals.values()),
            "ordinary_full_csv_scans": 2, "ordinary_fresh_logical_outputs_per_revision": 8,
            "proofflow_bootstrap_invocations": 8, "proofflow_initial_import_invocations": 35,
            "proofflow_fx_correction_invocations": 31, "ordered_post_requests": len(post_steps)}


def verify(root: Path = ROOT, workbook: Path | None = None) -> dict:
    root = Path(root).resolve()
    manifest = verify_manifest(root)
    selection, audit, cases = verify_fixture(root)
    receipt = verify_receipt(read_json(root / RESULTS / "receipt.json"), cases, selection)
    result = {
        "verified": True, "files_checked": len(manifest["files"]),
        "selected_date": selection["selected_date"], "rows": audit["rows"],
        "rows_by_region": audit["rows_by_region"], "receipt": receipt,
        "scope": "Normalized projection consistency and independent raw-cell arithmetic; not independent attestation of native service execution.",
    }
    if workbook is not None:
        result["original_workbook"] = audit_workbook(Path(workbook), root / FIXTURE, selection)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Checkout or extracted evidence root")
    parser.add_argument("--workbook", type=Path, help="Optional original UCI Online Retail.xlsx")
    args = parser.parse_args()
    try:
        result = verify(args.root, args.workbook)
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as exc:
        print(f"Fresh multi-country verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
