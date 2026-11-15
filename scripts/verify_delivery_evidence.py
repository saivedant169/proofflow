#!/usr/bin/env python3
"""Verify saved delivery, workflow and recovery evidence with the standard library."""

from argparse import ArgumentParser
from collections import Counter
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
import json
from pathlib import Path
import re


HOSTED = tuple(Path(f"evidence/hosted_delivery_v{version}.json") for version in (1, 2, 3))
RETAIL = Path("fixtures/real_partition_v1")
RETAIL_RUN = Path("results/real-partition-v1")
PAIRED = Path("fixtures/workflow_comparison")
PAIRED_RUN = Path("results/workflow-comparison-v1")
ATTEMPT = PAIRED_RUN / "attempt-001"
RECOVERY = Path("fixtures/recovery_v1")
RECOVERY_RUN = Path("results/recovery-v1")
RECOVERY_CI = Path("evidence/recovery_ci_replication.json")
DIAGNOSTIC = Path("results/fixed-budget-diagnostic-v1")
DIAGNOSTIC_SHA256 = {
    DIAGNOSTIC / "summary.json": "19b100a8bb4892408b4620c3582ac97cf4327c5dd27940707b722cbfcf67cc8b",
    DIAGNOSTIC / "publication/recovered_summary.json": "01b843c0c0f851b8a71293a10cdd8f9a4ae8d95b14c6008a51ce326022fdf027",
    DIAGNOSTIC / "publication/original_evidence_sha256.json": "0756e6f1cb859fb0979c42557490f656b7c3b976521e533d2b06fa3f8cb1bb51",
}
PHASES = ("initial", "fx-correction", "refund-correction")
ARMS = ("ordinary", "proofflow")
RELEASES = ("0535ba672b4b31c563c13d95df03285a73a4d736", "fdee9c999a1a5c62de4cf624f9bcc42ba6c124a6",
            "92da58c806a07d2577aef27bf5c967e7751325a0")
MANIFEST = Path("manifest.json")
VERIFIER = Path("verify_delivery_evidence.py")
PRIVATE_RECEIPT_FIELDS = {
    HOSTED[0]: (("ip_tested_origin",), ("domain_verification", "dns", "ipv4_address")),
    RECOVERY_RUN / "negative-control.json": (("mutated_response", "session_id"), ("mutated_response", "generation")),
    RECOVERY_RUN / "parent-observed-boundary.json": (
        ("manifest", "workspace_directory"), ("manifest", "namespace"), ("manifest", "metadata", "workspace_id")),
    RECOVERY_RUN / "interrupted-final-manifest.json": (
        ("workspace_directory",), ("namespace",), ("metadata", "workspace_id")),
    **{RECOVERY_RUN / f"{stem}.json": (("session_id",), ("generation",)) for stem in (
        "interrupted-initial", "reopened-state", "interrupted-updated", "interrupted-final")},
}
PRIVATE_RUN_FIELDS = {
    HOSTED[1]: (("release_ci", "run_url"), ("hosted_acceptance", "run_url"),
                         *(("hosted_acceptance", "archived_github_artifacts", index, "url") for index in range(2))),
    HOSTED[2]: (("release_ci", "run_url"), ("external_acceptance", "run_url"),
                         *(("external_acceptance", "archived_github_artifacts", index, "url") for index in range(3))),
    RECOVERY_CI: (("artifact", "source"),),
    RETAIL_RUN / "receipt.json": (("runner", "run_url"),),
    RETAIL_RUN / "verified-provenance.json": (("run", "url"),),
}


def pointer(path):
    return "/" + "/".join(str(key).replace("~", "~0").replace("/", "~1") for key in path)


def redacted_fields(path):
    return [pointer(field) for fields in (PRIVATE_RECEIPT_FIELDS, PRIVATE_RUN_FIELDS)
            for field in fields.get(path, ())]


def source_files():
    return (
        set(HOSTED) | set(DIAGNOSTIC_SHA256) | {RECOVERY_CI, Path("LICENSE")}
        | {Path(f"docs/{name}.md") for name in (
            "REAL_PARTITION_PROTOCOL", "WORKFLOW_COMPARISON_PROTOCOL", "RECOVERY_V1_PROTOCOL")}
        | {RETAIL / name for name in ("DATASET_NOTICE.md", "fixture.json", "orders.csv", "source_cells.csv")}
        | {RETAIL_RUN / name for name in ("receipt.json", "verified-provenance.json")}
        | {PAIRED / name for name in ("base.csv", "refund-corrected.csv", "cases.json")}
        | {PAIRED_RUN / "summary.json"}
        | {ATTEMPT / name for name in ("run.json", "operations.jsonl", "ordinary-progress.json",
                                       "proofflow-progress.json", "proofflow-fx-correction-stale-paths.json",
                                       "proofflow-refund-correction-stale-paths.json")}
        | {ATTEMPT / f"{arm}-{phase}.txt" for arm in ARMS for phase in PHASES}
        | {RECOVERY / name for name in ("base.csv", "corrected.csv", "manifest.json")}
        | {RECOVERY_RUN / name for name in (
            "summary.json", "run-manifest.json", "parent-observed-boundary.json", "kill-result.json",
            "interrupted-initial.json", "reopened-state.json", "interrupted-updated.json", "interrupted-final.json",
            "interrupted-final-manifest.json", "blocked-recovery-actions.json", "negative-control.json",
            "control-semantic-lineage.json", "interrupted-semantic-lineage.json", "lifecycle-accounting.json")}
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_keys(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "Duplicate JSON key")
    return result


def load(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_keys)


def digest(data):
    return sha256(data).hexdigest()


def binding(data):
    return {"bytes": len(data), "sha256": digest(data)}


def file_matches(data, declared):
    return binding(data) == {key: declared[key] for key in ("bytes", "sha256")}


def json_hash(value):
    return digest(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode())


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def cents_in_usd(native_cents, rate):
    return int((native_cents * Decimal(rate)).to_integral_value(rounding=ROUND_HALF_EVEN))


def usd_text(cents):
    return f"${Decimal(cents) / 100:,.2f}"


def commerce_totals(rows, rates, selected, refund_rows=None):
    gross, refunds, support = Counter(), Counter(), Counter()
    region_currency = {}
    refund_amounts = {row["order_id"]: int(row["refund_cents"]) for row in (
        rows if refund_rows is None else refund_rows
    )}
    require(len(refund_amounts) == len(rows) and set(refund_amounts) == {row["order_id"] for row in rows},
            "Commerce fixture order identities")
    for row in rows:
        region, currency = row["region"], row["currency"]
        gross[region] += int(row["gross_cents"])
        refunds[region] += refund_amounts[row["order_id"]]
        support[region] += int(row["ticket_count"])
        require(region_currency.setdefault(region, currency) == currency, "Mixed currencies within one region")
    net = {region: total - refunds[region] for region, total in gross.items()}
    converted = {region: cents_in_usd(total, {"USD": "1", **rates}[region_currency[region]])
                 for region, total in net.items()}
    company = sum(converted.values())
    return dict(gross=dict(gross), refunds=dict(refunds), net=net, regional=converted, support=dict(support),
                company=company, company_report=company, region_report=converted[selected])


def verify_retail(root, manifest):
    fixture = load(root / RETAIL / "fixture.json")
    receipt = load(root / RETAIL_RUN / "receipt.json")
    artifact = load(root / RETAIL_RUN / "verified-provenance.json")
    source_rows = csv_rows(root / RETAIL / "source_cells.csv")
    uploaded = csv_rows(root / RETAIL / "orders.csv")
    invoices, source_ids = set(), set()
    gross = Counter()
    for source, upload in zip(source_rows, uploaded, strict=True):
        day = date(1899, 12, 30) + timedelta(days=int(Decimal(source["invoice_date_raw_xml"])))
        invoice, country = source["invoice_no"], source["country"]
        key = f"uci:{invoice}:row:{source['source_row']}"
        quantity = Decimal(str(float(source["quantity_raw_xml"])))
        price = Decimal(str(float(source["unit_price_raw_xml"])))
        pence = quantity * price * 100
        require(day.isoformat() == fixture["selected_date"] and key not in source_ids
                and not invoice.upper().startswith("C") and 0 < quantity <= 10**9
                and quantity == quantity.to_integral_value() and price > 0
                and 0 < pence <= 10**12 and pence == pence.to_integral_value(), "Real source-cell eligibility")
        require(upload == dict(order_id=key, region=country, currency="GBP", gross_cents=str(int(pence))),
                "Real upload row differs from its original cells")
        source_ids.add(key)
        invoices.add(invoice)
        gross[country] += int(pence)
    require(len(source_ids) == fixture["rows"] == receipt["fixture"]["rows"] == 642
            and len(invoices) == fixture["invoices"] == receipt["fixture"]["invoices"] == 25
            and fixture["selected_region"] == receipt["fixture"]["report_region"] == "United Kingdom",
            "Real partition row, invoice and country bindings")
    require({country: f"{Decimal(value) / 100:.2f}" for country, value in gross.items()} ==
            fixture["oracle"]["gross_gbp_by_region"] == {"United Kingdom": "7242.06"}, "Real GBP subtotal")
    expected = {}
    for phase, rate in fixture["authored_gbp_to_usd"].items():
        by_country = {country: cents_in_usd(value, rate) for country, value in gross.items()}
        expected[phase] = {"company": sum(by_country.values()), "region": by_country[fixture["selected_region"]]}
        recorded = fixture["oracle"][phase]
        require(recorded == dict(by_region_usd_cents=by_country, company_usd_cents=expected[phase]["company"],
                                 region_usd_cents=expected[phase]["region"]), "Independent real output differs from frozen arithmetic")
    require(receipt["initial"]["revenue_usd_cents"] == expected["initial"]
            and receipt["refresh"]["revenue_usd_cents"] == receipt["reload"]["revenue_usd_cents"] == expected["corrected"],
            "Independent real arithmetic differs from saved report revenue")
    for name in ("orders.csv", "source_cells.csv"):
        require(file_matches((root / RETAIL / name).read_bytes(), fixture["files"][name]), f"Real fixture digest {name}")
    observed_fixture = receipt["fixture"]
    require(observed_fixture["files"] == fixture["files"] and observed_fixture["oracle"] == fixture["oracle"]
            and observed_fixture["date"] == fixture["selected_date"] and observed_fixture["authored_gbp_to_usd"] ==
            fixture["authored_gbp_to_usd"], "Real receipt binds frozen fixture contents")
    require(observed_fixture["manifest_sha256"] == digest((root / RETAIL / "fixture.json").read_bytes())
            and observed_fixture["protocol_sha256"] == digest((root / "docs/REAL_PARTITION_PROTOCOL.md").read_bytes()),
            "Real receipt binds fixture manifest and protocol")
    receipt_name = (RETAIL_RUN / "receipt.json").as_posix()
    require(artifact["artifact"]["receipt_sha256"] == manifest[receipt_name].get("original", manifest[receipt_name])["sha256"]
            and artifact["run"]["headSha"] == receipt["checkout_revision"], "Archived real receipt identity")

    correction = receipt["correction"]
    require(correction["changed_sources"] == ["fx"] and correction["old_head_export_http_status"] == 409
            and correction["old_head_export_error"] == "evidence_unavailable" and correction["old_head_export_downloads"] == 0
            and correction["current_revenue_usd_cents"] == {"company": None, "region": None},
            "Saved real stale-export refusal")
    for result in (receipt["initial"], receipt["refresh"]):
        export = result["export"]
        require(export["http_status"] == 200 and all(export[key] is True for key in (
            "no_store", "matches_server_bytes", "both_amounts_and_report_claim_ids_match")), "Saved real checked export")
    refresh = receipt["refresh"]
    require(refresh["recorded_tools"] == {"company_total": 1, "compose_report": 2, "convert_to_usd": 1}
            and refresh["accounting"]["recorded_tool_call_count"] == 4
            and refresh["accounting"]["verification_calculation_count"] == 11
            and refresh["initial_file_remained_unchanged"] is True and receipt["reload"]["same_session_source_and_artifact_heads"] is True,
            "Saved real refresh and reload accounting")
    steps = receipt["steps"]
    require(receipt["passed"] is True and len(steps) == 6 and all(row["status"] == "pass" for row in steps.values())
            and len(receipt["write_request_attempts"]) == 9
            and all(row["allowed"] is True for row in receipt["write_request_attempts"]), "Six real phases and nine planned writes")
    return {"rows": len(source_ids), "invoices": len(invoices), "initial_usd_cents": expected["initial"]["company"],
            "corrected_usd_cents": expected["corrected"]["company"], "verified_phases": len(steps)}


def verify_pair(root):
    specification = load(root / PAIRED / "cases.json")
    summary = load(root / PAIRED_RUN / "summary.json")
    run = load(root / ATTEMPT / "run.json")
    ordinary, proof = (load(root / ATTEMPT / f"{arm}-progress.json") for arm in ARMS)
    operations = [json.loads(line, object_pairs_hook=unique_keys)
                  for line in (root / ATTEMPT / "operations.jsonl").read_text(encoding="utf-8").splitlines()]
    require(run["freeze_sha256"] == summary["freeze_sha256"] and run["model_calls"] == 0
            and run["status"] == summary["status"] == "passed", "Paired attempt identity")
    require(tuple(case["id"] for case in specification["cases"]) == tuple(phase["id"] for phase in summary["phases"]) == PHASES,
            "Three frozen paired phases")

    prior = None
    retained_counts, new_counts = [], []
    for case, stage in zip(specification["cases"], summary["phases"], strict=True):
        phase = case["id"]
        require(case["csv"] in {"base.csv", "refund-corrected.csv"}, "Paired fixture filename")
        data = root / PAIRED / case["csv"]
        rows = csv_rows(data)
        known = commerce_totals(rows, case["rates"], specification["selected_region"])
        require(known == ordinary[phase]["outputs"] == proof[phase]["outputs"] == case["expected"],
                f"Paired independent arithmetic: {phase}")
        require(len(rows) == 9 and stage["csv_sha256"] == digest(data.read_bytes()) and stage["oracle_outputs_matched_per_arm"] == 8
                and stage["company_usd_cents"] == known["company"] and stage["selected_region_usd_cents"] == known["region_report"],
                f"Paired per-phase observations: {phase}")
        current = proof[phase]
        evidence = stage["proofflow"]
        retained = {key for key in known if prior and all(current[name][key] == prior[name][key]
                    for name in ("artifact_ids", "receipt_ids"))}
        new = set(known) - retained
        require(retained == set(evidence["retained_heads_and_receipts"]) and new == set(evidence["new_recorded_outputs"])
                and current["retained_work"]["recorded_outputs"] == evidence["new_recorded_outputs"],
                f"Paired retained and replaced published records: {phase}")
        counts = evidence["arithmetic"]
        require(counts["recorded"] == len(new) and counts["total"] == sum(counts[key] for key in
                ("preflight", "recorded", "verification")), f"Paired arithmetic accounting: {phase}")
        if prior:
            require(new == set(case["affected_outputs"]) and all(current[name][key] != prior[name][key]
                    for key in new for name in ("artifact_ids", "receipt_ids")), f"Paired changed heads: {phase}")
            paths = load(root / ATTEMPT / f"proofflow-{phase}-stale-paths.json")
            require(set(paths) == {"company", "region"} and evidence["current_claims_withheld_after_update"] == 2,
                    f"Paired stale reports: {phase}")
            for report, observations in paths.items():
                require(len(observations) == 1, f"Paired one saved path: {phase}")
                path = observations[0]
                nodes = [node["id"] for node in path["nodes"]]
                require(nodes[0] == path["source_id"] == current["stale_boundary"]["superseded_source_id"]
                        and nodes[-1] == path["target_id"] == prior["report_ids"][report]
                        and [(edge["source"], edge["target"]) for edge in path["edges"]] == list(zip(nodes, nodes[1:])),
                        f"Paired path edges and endpoints: {phase} {report}")
        for arm, observations in zip(ARMS, (ordinary, proof), strict=True):
            snapshot = stage["snapshots"][arm]
            data = (root / ATTEMPT / f"{arm}-{phase}.txt").read_bytes()
            require(digest(data) == snapshot["sha256"] == observations[phase]["snapshot_sha256"]
                    and all(usd_text(known[key]).encode() in data for key in ("company_report", "region_report")),
                    f"Paired checked snapshot: {arm} {phase}")
        retained_counts.append(len(retained))
        new_counts.append(len(new))
        prior = current

    for arm in ARMS:
        verdicts = [row for row in operations if row["arm"] == arm and "accepted" in row]
        accepted = sum(row["accepted"] is True and row["report_content_returned"] is True for row in verdicts)
        refused = sum(row["accepted"] is False and row["report_content_returned"] is False for row in verdicts)
        old_files = [row for row in operations if row["arm"] == arm and row["step"].endswith(".retained-file")]
        require(len(verdicts) == 7 and accepted == summary["handoffs"][arm]["current_accepted"] == 3
                and refused == summary["handoffs"][arm]["stale_rejected_without_content"] == 4
                and len(old_files) == summary["handoffs"][arm]["old_file_integrity_checks_passed"] == 3
                and all(row["actual_sha256"] == row["expected_sha256"] for row in old_files),
                f"Paired ordered handoff and old-file checks: {arm}")
    exports = [row for row in operations if row.get("route") == "/api/import/export"]
    require(Counter(row["http_status"] for row in exports) == {200: 3, 409: 4}
            and all(row["cache_control"] == "no-store" and not row["analytics_calls"] for row in exports),
            "Paired ProofFlow export responses")
    work = {row["step"]: row["actual_calculation_counts"] for row in operations
            if row["arm"] == "proofflow" and "actual_calculation_counts" in row}
    warm_total = 0
    for phase in PHASES[1:]:
        per_step = [work[f"{phase}.{action}"] for action in ("preview", "update", "refresh")]
        breakdown = {key: sum(row[key] for row in per_step) for key in ("preflight", "recorded", "verification")}
        warm_calls = sum(breakdown.values())
        stage = next(stage for stage in summary["phases"] if stage["id"] == phase)
        require(stage["proofflow"]["arithmetic"] == {**breakdown, "total": warm_calls},
                f"Paired warm phase binds observed analytics calls: {phase}")
        warm_total += warm_calls
    require(warm_total == summary["two_warm_corrections"]["proofflow_registered_arithmetic_invocations"] == 64,
            "Paired warm corrections retained complete analytics accounting")
    return {"phases": 3, "stale_refusals_per_method": 4, "current_handoffs_per_method": 3,
            "proofflow_new_outputs": new_counts, "proofflow_retained_heads_and_receipts": retained_counts,
            "proofflow_warm_analytics_calls": warm_total}


def report_claims(state, expected, claim_state, current):
    reports = {report["key"]: report for report in state["reports"]}
    if set(reports) != {"company", "region"} or len(state["reports"]) != 2:
        return False
    for identity, saved in zip(("company", "region"), expected, strict=True):
        report = reports[identity]
        if len(report["claims"]) != 1:
            return False
        claim = report["claims"][0]
        if (report["state"], claim["state"], claim["value"], claim["saved_value"]) != (
            claim_state, claim_state, saved if current else None, saved
        ):
            return False
    return True


def verify_recovery(root):
    frozen = load(root / RECOVERY / "manifest.json")
    run = load(root / RECOVERY_RUN / "run-manifest.json")
    summary = load(root / RECOVERY_RUN / "summary.json")
    replicate = load(root / RECOVERY_CI)
    require(summary["revision"] == run["revision"] and frozen["production_commit"].startswith(run["production_base"]),
            "Recovery protocol and runtime identities")
    require(summary["passed"] is True and summary["model_calls"] == 0 and len(summary["checks"]) == 15
            and all(passed is True for passed in summary["checks"].values()), "15 saved local recovery checks")
    ci = replicate["recovery_summary"]
    require(replicate["artifact"]["revision"] == ci["revision"] and ci["passed"] is True
            and ci["checks"] == summary["checks"] and ci["model_calls"] == 0, "Linux recovery check replication")
    verify_files = ("docs/RECOVERY_V1_PROTOCOL.md", (RECOVERY / "manifest.json").as_posix(),
                    (RECOVERY / "base.csv").as_posix(), (RECOVERY / "corrected.csv").as_posix())
    for filename in verify_files:
        require(digest((root / filename).read_bytes()) == run["sha256"][filename], f"Recovery freeze digest: {filename}")

    base, corrected = (csv_rows(root / RECOVERY / f"{name}.csv") for name in ("base", "corrected"))
    rates, region = (frozen["request_parameters"][key] for key in ("rates", "region"))
    initial = commerce_totals(base, rates, region)
    final = commerce_totals(corrected, rates, region)
    mixed = commerce_totals(corrected, rates, region, refund_rows=base)
    for key, values in (("baseline", initial), ("corrected", final), ("mixed_new_orders_old_refunds_diagnostic_only", mixed)):
        recorded = frozen["independent_expected_values"][key]
        require((recorded["company_usd_cents"], recorded["river_usd_cents"]) == (values["company"], values["region_report"]),
                f"Recovery independent arithmetic: {key}")

    boundary = load(root / RECOVERY_RUN / "parent-observed-boundary.json")
    kill = load(root / RECOVERY_RUN / "kill-result.json")
    require(kill["parent_verified_storage_before_kill"] is True and kill["returncode"] == -9
            and kill["signal"] == "SIGKILL" and kill["child_pid"] == boundary["child_pid"],
            "Saved API child termination and durable boundary")
    store = boundary["manifest"]
    require(store["metadata"]["incomplete_update"] is True, "Incomplete-update marker persisted before kill")
    orders = [{**{key: row[key] for key in ("order_id", "region", "currency")},
               "gross_cents": int(row["gross_cents"])} for row in sorted(corrected, key=lambda row: row["order_id"])]
    refunds = [{"order_id": row["order_id"], "refund_cents": int(row["refund_cents"])}
               for row in sorted(base, key=lambda row: row["order_id"])]
    for name, value, native in (("orders", orders, boundary["native_order_node"]),
                                ("refunds", refunds, boundary["native_refund_node"])):
        logical_id = f"source:csv:{name}"
        head = store["heads"][logical_id]
        require(head["value"] == value and head["id"] == native["id"]
                and native["properties"]["logical_id"] == logical_id
                and native["properties"]["content_hash"] == head["content_hash"] == json_hash(value),
                f"Saved mixed source boundary: {name}")

    before, reopened, resubmitted, after = (load(root / RECOVERY_RUN / f"{stage}.json") for stage in (
        "interrupted-initial", "reopened-state", "interrupted-updated", "interrupted-final"))
    initial_pair = (initial["company"], initial["region_report"])
    final_pair = (final["company"], final["region_report"])
    require(report_claims(before, initial_pair, "current", True)
            and report_claims(reopened, initial_pair, "stale", False) and reopened["incomplete_update"] is True
            and report_claims(resubmitted, initial_pair, "stale", False)
            and report_claims(after, final_pair, "current", True) and after["incomplete_update"] is False,
            "Saved recovery withholding and current reports")
    require(set(store["metadata"]["pending_roots"]) == set(resubmitted["impact"]["changed_source_ids"])
            and len(store["metadata"]["pending_roots"]) == 2, "Original affected roots retained on resubmission")
    support = [next(node for node in state["graph"]["nodes"] if node["logical_id"] == "import:metric:support"
                    and node["current_head"]) for state in (before, reopened, after)]
    require(all(node["state"] == "current" and node["id"] == support[0]["id"] for node in support),
            "Support head remained current through the interruption")
    blocked = load(root / RECOVERY_RUN / "blocked-recovery-actions.json")
    require(set(blocked) == {"refresh", "verify"} and all(row["http_status"] == 409
            and row["body"]["error"]["code"] == "evidence_unavailable" for row in blocked.values()),
            "Saved refresh and verification refusal")
    negative = load(root / RECOVERY_RUN / "negative-control.json")
    exposed = [claim for report in negative["mutated_response"]["reports"] for claim in report["claims"]
               if claim["state"] == "current" and claim["value"] is not None]
    require(negative["detected"] is True and negative["reason"] == "stale monetary value was served"
            and len(exposed) == 1 and exposed[0]["saved_value"] == exposed[0]["value"] == initial["company"],
            "Saved stale-response negative control")
    refresh = after["last_refresh"]
    require(refresh["executed_count"] == 7 and refresh["numeric_parity"] is True
            and Counter(call["tool"] for call in refresh["tool_calls"]) ==
            +Counter(frozen["refresh_recorded_tool_counts"]), "Seven successful saved recovery refresh executions")

    control = load(root / RECOVERY_RUN / "control-semantic-lineage.json")
    recovered = load(root / RECOVERY_RUN / "interrupted-semantic-lineage.json")
    final_store = load(root / RECOVERY_RUN / "interrupted-final-manifest.json")
    heads = final_store["heads"]
    require(control == recovered and len(recovered) == frozen["final_current_artifact_heads"] == 8
            and len(heads) == len({head["id"] for head in heads.values()}) == final_store["distinct_logical_head_count"] == 19,
            "Recovered state matches uninterrupted control with distinct heads")
    for logical_id, artifact in recovered.items():
        require(heads[logical_id]["value"] == artifact["value"]
                and heads[logical_id]["content_hash"] == artifact["content_hash"] == json_hash(artifact["value"]),
                f"Recovery value and content hash: {logical_id}")
        require(all(ref["content_hash"] == heads[ref["logical_id"]]["content_hash"] for ref in artifact["inputs"].values()),
                f"Recovery lineage binds current inputs: {logical_id}")
    require(recovered["import:metric:company"]["value"]["usd_cents"] == final["company"]
            and {region: value["tickets"] for region, value in recovered["import:metric:support"]["value"]["regions"].items()}
            == final["support"], "Recovery arithmetic matches stored heads")
    accounting = load(root / RECOVERY_RUN / "lifecycle-accounting.json")
    require(all(row["observed"] == row["expected"] and sum(row["observed"].values()) == row["total"]
                for row in accounting.values()), "Recovery lifecycle accounting")
    control_total = accounting["control"]["total"]
    recovered_total = sum(row["total"] for step, row in accounting.items() if step != "control")
    require((control_total, recovered_total, accounting["fault"]["total"]) == (61, 69, 8),
            "Recovery accounting preserves interruption work")
    return {"checks_passed": len(summary["checks"]), "linux_replication_checks_passed": len(ci["checks"]),
            "corrected_company_usd_cents": final["company"], "corrected_river_usd_cents": final["region_report"],
            "recorded_refresh_calls": refresh["executed_count"], "control_arithmetic_calls": control_total,
            "interrupted_arithmetic_calls": recovered_total}


def verify_hosted(root):
    v1, v2, v3 = (load(root / path) for path in HOSTED)
    origins = {row["canonical_origin"] for row in (v1, v2, v3)}
    require(tuple(row["release"]["source_revision"] for row in (v1, v2, v3)) == RELEASES
            and origins == {"https://proofflow.arnavbule.in"}, "Three distinct historical hosted release identities")
    restart = v1["application_restart"]
    statuses = restart["http_response_statuses"]
    require(restart["status"] == "pass" and restart["component_tested"] == "app"
            and restart["check_count"] == 87 and len(statuses) == restart["request_count"] == 12
            and statuses == [200, 200, 404, 200, 502, 502, 200, 200, 200, 200, 200, 200]
            and datetime.fromisoformat(restart["app_started_at_before_utc"]) <
            datetime.fromisoformat(restart["began_at_utc"]) <= datetime.fromisoformat(restart["app_started_at_after_utc"]),
            "Historical application restart and transient HTTP failures")
    stages = restart["stages"]
    require(stages["initial"] == stages["restored"] ==
            {"company_usd_cents": 30800, "north_usd_cents": 10800, "report_state": "current"}
            and stages["refreshed"] == stages["final_reload"] ==
            {"company_usd_cents": 31700, "north_usd_cents": 11700, "report_state": "current"}
            and stages["corrected"] == stages["withheld_reload"] ==
            {"company_usd_cents": None, "north_usd_cents": None, "report_state": "stale"}
            and all(restart["check_observations"].values()), "Historical restoration, withholding and refresh")
    earlier = v2["historical_hosted_app_restart"]
    require(earlier["source_revision"] == RELEASES[0] and earlier["checks_passed"] == restart["check_count"]
            and earlier["http_responses"] == restart["request_count"], "Earlier restart receipt relationship")
    latest = v3["external_acceptance"]
    for row in (v2["hosted_acceptance"], latest):
        require(row["chrome_steps_passed"] == 11 and row["guided_http_checks_passed"] == 13
                and row["run_attempt"] == 1 and row["conclusion"] == "success",
                "Saved cold hosted Chrome and guided checks")
    require(latest["deployed_runtime_revision"] == RELEASES[2] and latest["run_attempt"] == 1
            and latest["checkout_source_revision"] == "f0173e70337fc87972a7eda77ae55475be43649c"
            and latest["runtime_and_frontend_path_bytes_match_across_revisions"] is True,
            "External runner binds historical release")
    downloads = v3["public_downloads"]
    files = downloads["files"]
    require(len(files) == downloads["matching_responses"] == 8 and all(value["status"] == 200
            and value["byte_match"] is True and value["set_cookie_present"] is False for value in files.values()),
            "Eight saved anonymous download responses")
    require(files["/evidence/proofflow-model-evidence.zip"]["sha256"] ==
            "996d670a4d49929ff4eefc01441e8fa05d29099a45e109f4e73b3dbbf9c40be7",
            "Historical model archive identity")
    connector = downloads["cold_connector_handshake"]
    require(connector["tool_calls"] == 0 and connector["fresh_uv_cache"] is True and set(connector["tools"]) == {
        "create_csv_reports", "export_current_reports", "inspect_reports", "refresh_reports", "update_csv"},
            "Saved discovery-only cold connector handshake")
    partition = load(root / RETAIL_RUN / "receipt.json")
    require(partition["operator_verified_release"] ==
            {"source_revision": RELEASES[2], "image_id": v3["release"]["app_image_id"]}
            and partition["preflight"]["frontend_byte_match"] is True, "Real workflow binds tested image and frontend observation")
    return {"releases": list(RELEASES), "latest_observation_revision": RELEASES[2],
            "v3_matching_downloads": len(files), "restart_checks": restart["check_count"],
            "restart_http_responses": restart["request_count"], "restart_transient_502s": statuses.count(502),
            "cold_connector_tools_discovered": len(connector["tools"]), "cold_connector_tool_calls": connector["tool_calls"]}


def verify_diagnostic(root):
    for name, expected in DIAGNOSTIC_SHA256.items():
        require(digest((root / name).read_bytes()) == expected, f"Reviewed fixed-budget artifact digest: {name}")
    original = load(root / DIAGNOSTIC / "summary.json")
    recovered = load(root / DIAGNOSTIC / "publication/recovered_summary.json")
    inventory = load(root / DIAGNOSTIC / "publication/original_evidence_sha256.json")
    require(recovered["original_run_summary_sha256"] == inventory["summary.json"] ==
            DIAGNOSTIC_SHA256[DIAGNOSTIC / "summary.json"]
            and recovered["original_run_manifest_sha256"] == inventory["run_manifest.json"],
            "Fixed-budget recovery binds original run records")
    require(original["complete"] is recovered["original_frozen_run_complete"] is False
            and original["status_counts"] == recovered["original_status_counts"] == {"execution_failed": 88}
            and recovered["status_counts"] == {"recovered_observation": 88}
            and recovered["original_wrapper_error"] == {"type": "KeyError", "message": "'verified_report_counts'"}
            and recovered["all_retained_scores_verified"] is True,
            "Fixed-budget original wrapper failure and separately recovered scores")

    fresh = {}
    original_groups = {(group["condition"], group["arm"]): group for group in original["groups"]}
    recovered_groups = {(group["condition"], group["arm"]): group for group in recovered["groups"]}
    require(len(original_groups) == len(recovered_groups) == 11 and original_groups.keys() == recovered_groups.keys(),
            "Fixed-budget original and recovered conditions")
    scored = 0
    for (condition, arm), group in recovered_groups.items():
        recorded = original_groups[condition, arm]
        require(group["planned_cells"] == recorded["planned_cells"] == group["scored_cells"] == 8
                and recorded["scored_cells"] == 0 and recorded["reports_observed"]["fresh_affected"] is None
                and group["planned_denominators"] == recorded["planned_denominators"]
                and group["planned_denominators"]["eligible_affected"] == 32,
                f"Fixed-budget recovered denominators and original failure: {condition} {arm}")
        scored += group["scored_cells"]
        fresh.setdefault(condition, {})[arm] = group["reports_observed"]["fresh_affected"]
    require(scored == original["planned_cells"] == recovered["planned_cells"] == 88
            and fresh == {
                "fixed_4096": {"graph": 15, "exact_flat": 15, "bm25": 5, "dense": 2, "iterative_hybrid": 15},
                "fixed_8192": {"graph": 27, "exact_flat": 27, "bm25": 25, "dense": 10, "iterative_hybrid": 28},
                "uncapped_reference": {"full_context": 32},
            }, "Fixed-budget saved scores and losses")
    parity = {str(cap): {"matching_contexts": 8, "observed": 8, "planned": 8} for cap in (4096, 8192)}
    require(recovered["graph_exact_flat_context_parity"] == original["graph_exact_flat_context_parity"] == parity,
            "Fixed-budget graph/exact-flat context parity")
    return {"planned_cells": scored, "original_completed": original["complete"],
            "original_wrapper_execution_errors": original["status_counts"]["execution_failed"],
            "recovered_scored_cells": scored, "fresh_affected": fresh}


def verify(root):
    expected = source_files() | {Path("README.md"), VERIFIER}
    directories = {parent for path in expected for parent in path.parents if parent != Path(".")}
    entries = {path.relative_to(root) for path in root.rglob("*")}
    require(entries == expected | directories | {MANIFEST}, "Exact extracted delivery bundle files")
    for relative in expected | {MANIFEST}:
        path = root / relative
        require(path.resolve() == path and path.is_file(), f"Regular delivery evidence file: {relative}")
    for relative in directories:
        require((root / relative).is_dir() and not (root / relative).is_symlink(),
                f"Regular delivery evidence directory: {relative}")
    metadata = load(root / MANIFEST)
    files = metadata["files"]
    require(metadata["schema_version"] == 1 and set(files) == {path.as_posix() for path in expected},
            "Exact delivery bundle manifest inventory")
    for name, info in files.items():
        path = root / name
        require(file_matches(path.read_bytes(), info), f"Delivery evidence digest: {name}")
        changed = redacted_fields(Path(name))
        expected_fields = {"bytes", "sha256", "original", "changed_fields"} if changed else {"bytes", "sha256"}
        require(set(info) == expected_fields, f"Delivery manifest record fields: {name}")
        if changed:
            original = info["original"]
            require(info["changed_fields"] == changed and set(original) == {"bytes", "sha256"}
                    and type(original["bytes"]) is int and original["bytes"] > 0
                    and re.fullmatch(r"[0-9a-f]{64}", original["sha256"]) and original["sha256"] != info["sha256"],
                    f"Delivery redaction provenance: {name}")
    return {"bundle_files_verified": len(files), "hosted": verify_hosted(root),
            "real_partition": verify_retail(root, files), "paired_workflow": verify_pair(root),
            "interrupted_update": verify_recovery(root),
            "fixed_budget_diagnostic": verify_diagnostic(root)}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, default=Path(__file__).resolve().parent, nargs="?")
    try:
        result = verify(parser.parse_args().bundle.resolve())
    except (OSError, ValueError, TypeError, KeyError, ArithmeticError, IndexError, StopIteration) as error:
        parser.exit(1, f"Delivery evidence verification failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
