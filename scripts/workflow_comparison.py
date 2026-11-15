"""Compare small-file recalculation with the real ProofFlow CSV handoff flow."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack, contextmanager
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from functools import wraps
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "workflow_comparison"
FREEZE = FIXTURES / "freeze.json"
EXPORT_ROUTE = "/api/import/export"
PROTOCOL = "docs/WORKFLOW_COMPARISON_PROTOCOL.md"
OUTPUT_IDS = {
    "gross": "import:metric:gross", "refunds": "import:metric:refunds",
    "net": "import:metric:net", "regional": "import:metric:regional",
    "company": "import:metric:company", "support": "import:metric:support",
    "company_report": "import:report:company", "region_report": "import:report:region",
}
LOGICAL_NAMES = {logical_id: name for name, logical_id in OUTPUT_IDS.items()}
ACCOUNTING = {
    "preflight": "preflight_calculation_count",
    "recorded": "recorded_tool_call_count",
    "verification": "verification_calculation_count",
}
CURRENCIES = {"USD", "EUR", "GBP"}
REQUIRED_FIELDS = {"order_id", "region", "currency", "gross_cents"}
OPTIONAL_FIELDS = {"refund_cents", "ticket_count"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_text(data: object, *, pretty: bool = False) -> str:
    return json.dumps(data, sort_keys=True, indent=2 if pretty else None,
                      ensure_ascii=False, allow_nan=False)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_json(path: Path, data: object) -> None:
    path.write_text(json_text(data, pretty=True) + "\n", encoding="utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def money(cents: int) -> str:
    dollars, remainder = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}${dollars:,}.{remainder:02d} USD"


@dataclass(frozen=True)
class InputRevision:
    csv_bytes: bytes
    rates: dict[str, str]
    region: str

    @property
    def metadata(self) -> dict:
        return {"csv_sha256": sha256(self.csv_bytes), "rates": self.rates, "region": self.region}

    @property
    def digest(self) -> str:
        return sha256(json_text(self.metadata).encode("utf-8"))

    def request(self) -> dict:
        return {"csv_text": self.csv_bytes.decode("utf-8"), "rates": self.rates, "region": self.region}


def input_count(value: str, name: str, maximum: int) -> int:
    valid = re.fullmatch(r"0|[1-9][0-9]{0,15}", value)
    require(bool(valid) and int(value) <= maximum, f"Invalid {name}")
    return int(value)


def valid_text(value: str, limit: int) -> bool:
    return bool(value) and value == value.strip() and len(value) <= limit and value.isprintable()


def ordinary_full_recalculate(revision: InputRevision) -> tuple[dict, dict]:
    """Read rows once, calculate every output, and reconcile control totals."""
    require(0 < len(revision.csv_bytes) <= 1024 * 1024, "CSV byte limit")
    require(set(revision.rates) <= CURRENCIES, "Unsupported rate currency")
    rates = {"USD": Decimal(1)}
    for currency, text in revision.rates.items():
        require(bool(re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]{1,12})?", text)), "Invalid rate format")
        rate = Decimal(text)
        require(0 < rate <= 1000 and (currency != "USD" or rate == 1), "Invalid rate value")
        rates[currency] = rate

    reader = csv.reader(io.StringIO(revision.csv_bytes.decode("utf-8-sig"), newline=""), strict=True)
    fields = next(reader, [])
    require(len(fields) == len(set(fields)) and REQUIRED_FIELDS <= set(fields) <= (
        REQUIRED_FIELDS | OPTIONAL_FIELDS), "Incorrect CSV fields")
    region_currencies, seen = {}, set()
    gross, refunds, row_net, support = (defaultdict(int) for _ in range(4))
    ticket_total = 0
    for cells in reader:
        if not cells:
            continue
        require(len(cells) == len(fields) and len(seen) < 1000, "Incorrect row shape or row limit")
        row = dict(zip(fields, cells))
        order, region, currency = row["order_id"], row["region"], row["currency"]
        require(valid_text(order, 200) and order not in seen, "Invalid or duplicate order ID")
        require(valid_text(region, 64) and not region.startswith("__"), "Invalid region")
        require(currency in rates, "Missing or unsupported currency rate")
        require(region_currencies.setdefault(region, currency) == currency, "Mixed region currency")
        seen.add(order)
        gross_cents = input_count(row["gross_cents"], "gross", 10**12)
        refund_cents = input_count(row.get("refund_cents") or "0", "refund", 10**12)
        tickets = input_count(row.get("ticket_count") or "0", "support count", 10_000)
        ticket_total += tickets
        require(refund_cents <= gross_cents and ticket_total <= 10_000, "Refund or ticket limit")
        gross[region] += gross_cents
        row_net[region] += gross_cents - refund_cents
        if refund_cents:
            refunds[region] += refund_cents
        if tickets:
            support[region] += tickets
    require(revision.region in region_currencies, "Selected region missing")

    net = {region: amount - refunds.get(region, 0) for region, amount in gross.items()}
    with localcontext() as context:
        context.prec = 50
        regional = {region: int((amount * rates[region_currencies[region]]).quantize(
            Decimal(1), rounding=ROUND_HALF_EVEN)) for region, amount in net.items()}
    company = sum(regional.values())
    remaining = sum(cents for region, cents in regional.items() if region != revision.region)
    output = {
        "gross": dict(gross), "refunds": dict(refunds), "net": net, "regional": regional,
        "company": company, "support": dict(support), "company_report": company,
        "region_report": regional[revision.region],
    }
    checks = {
        "grouped_net_matches_row_net_for_each_region": net == row_net,
        "support_matches_input_control_total": sum(support.values()) == ticket_total,
        "company_report_reconciles_to_region_plus_remaining_regions":
            output["company_report"] == output["region_report"] + remaining,
        "selected_report_matches_converted_region": output["region_report"] == regional[revision.region],
    }
    require(all(checks.values()), "Ordinary recalculation control failed")
    accounting = {
        "full_csv_scans": 1, "validated_rows": len(seen), "fresh_logical_outputs": sorted(output),
        "input_validation_passed": True, "region_currencies": region_currencies,
        "reconciliation_controls": checks,
    }
    return output, accounting


class SharedReports:
    """Single-writer shared version pointer and immutable versioned files."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.sources = directory / "sources"
        self.reports = directory / "reports"
        self.sources.mkdir(parents=True)
        self.reports.mkdir()

    def set_source(self, revision: InputRevision) -> None:
        version = self.sources / revision.digest
        version.mkdir()
        (version / "orders.csv").write_bytes(revision.csv_bytes)
        write_json(version / "input.json", revision.metadata)
        atomic_write(self.directory / "latest-input", revision.digest.encode("ascii"))

    def latest_input(self) -> str:
        return (self.directory / "latest-input").read_text(encoding="ascii")

    def full_recalculate_and_publish(self) -> tuple[str, dict, dict]:
        version = self.latest_input()
        source = self.sources / version
        metadata = json.loads((source / "input.json").read_text(encoding="utf-8"))
        revision = InputRevision((source / "orders.csv").read_bytes(), metadata["rates"], metadata["region"])
        require(revision.digest == version and revision.metadata == metadata, "Shared input versions disagree")
        output, accounting = ordinary_full_recalculate(revision)
        require(self.latest_input() == version, "Shared input changed during calculation")
        report = "\n".join((
            "Current revenue report snapshot",
            f"Input revision SHA-256: {version}",
            f"Calculated at (UTC): {now()}",
            "Static snapshot. Compare the input revision with the latest shared version before handing off as current.",
            f"Company net revenue: {money(output['company_report'])}",
            f"Regional net revenue ({revision.region!r}): {money(output['region_report'])}",
            "",
        ))
        destination = self.reports / f"{version}.txt"
        require(not destination.exists(), "Ordinary report revision was already published")
        atomic_write(destination, report.encode("utf-8"))
        return report, output, accounting

    def check_handoff(self, working_copy: str) -> dict:
        latest = self.latest_input()
        version_label = f"Input revision SHA-256: {latest}"
        if version_label not in working_copy.splitlines():
            return {"accepted": False, "reason": "working_copy_input_revision_mismatch",
                    "latest_input_revision_sha256": latest}
        report = self.reports / f"{latest}.txt"
        if not report.is_file() or working_copy.encode("utf-8") != report.read_bytes():
            return {"accepted": False, "reason": "current_published_snapshot_not_matched",
                    "latest_input_revision_sha256": latest}
        return {"accepted": True, "latest_input_revision_sha256": latest, "content": working_copy}


class Ledger:
    def __init__(self, directory: Path):
        self.directory = directory

    def append(self, **event) -> None:
        with (self.directory / "operations.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json_text({"at": now(), **event}) + "\n")

    def save(self, name: str, data: object) -> None:
        write_json(self.directory / f"{name}.json", data)

    def snapshot(self, name: str, content: str) -> str:
        encoded = content.encode("utf-8")
        with (self.directory / f"{name}.txt").open("xb") as handle:
            handle.write(encoded)
        return sha256(encoded)


class ArithmeticTrace:
    """Observe original tool calls inside the API process without modifying their results."""

    def __init__(self):
        self.calls = []
        self.execution = threading.local()

    @contextmanager
    def install(self):
        from proofflow import importing, runtime

        def observed(original, category):
            @wraps(original)
            def wrapped(tool, *args, **kwargs):
                kind = category()
                call = {"tool": tool, "category": kind, "status": "started"}
                self.calls.append(call)
                try:
                    result = original(tool, *args, **kwargs)
                except Exception:
                    call["status"] = "failed"
                    raise
                call["status"] = "success"
                return result
            return wrapped

        original_execute = runtime.ProofFlowRuntime.execute

        @wraps(original_execute)
        def execute(instance, *args, **kwargs):
            previous = getattr(self.execution, "recorded", False)
            self.execution.recorded = True
            try:
                return original_execute(instance, *args, **kwargs)
            finally:
                self.execution.recorded = previous

        def runtime_category():
            return "recorded" if getattr(self.execution, "recorded", False) else "verification"

        with ExitStack() as stack:
            stack.enter_context(patch.object(importing, "execute_tool",
                observed(importing.execute_tool, lambda: "preflight")))
            stack.enter_context(patch.object(runtime, "execute_tool",
                observed(runtime.execute_tool, runtime_category)))
            stack.enter_context(patch.object(runtime.ProofFlowRuntime, "execute", execute))
            yield


def pf_request(ledger, trace, client, step, method, route, *, payload=None, expected_status=200):
    start = len(trace.calls)
    event = {"arm": "proofflow", "step": step, "method": method, "route": route}
    try:
        response = client.request(method, route, **({"json": payload} if payload is not None else {}))
    except Exception as exc:
        ledger.append(**event, http_status=None, analytics_calls=trace.calls[start:],
                      request_error=type(exc).__name__)
        raise
    calls = trace.calls[start:]
    actual = Counter(call["category"] for call in calls)
    counts = {category: actual[category] for category in ACCOUNTING}
    event.update(http_status=response.status_code, cache_control=response.headers.get("Cache-Control"),
                 actual_calculation_counts=counts, analytics_calls=calls)
    try:
        body = response.json()
    except ValueError:
        ledger.append(**event, request_error="invalid_json")
        raise
    ledger.append(**event, error=body.get("error"))
    require(response.status_code == expected_status, f"{step} returned HTTP {response.status_code}")
    operation = None
    if route.endswith("/preview"):
        operation = body["accounting"]
    if route.endswith(("/create", "/update", "/refresh")):
        operation = body["last_operation"]
    if operation is not None:
        require(all(operation[field] == counts[name] for name, field in ACCOUNTING.items())
                and operation["total_calculation_count"] == sum(counts.values())
                and all(call["status"] == "success" for call in calls),
                f"{step} has unmatched arithmetic accounting")
    if route == EXPORT_ROUTE:
        require(response.headers.get("Cache-Control") == "no-store" and not calls,
                f"{step} was cacheable or calculated values")
        if expected_status == 409:
            require(set(body) == {"error"} and "$" not in response.text, f"{step} leaked report content")
            return {"accepted": False, "http_status": 409, "error": body["error"]}
    return body


def head_artifacts(state: dict) -> dict:
    heads = {LOGICAL_NAMES[node["logical_id"]]: node for node in state["graph"]["nodes"]
             if node["kind"] == "artifact" and node["current_head"] and node["logical_id"] in LOGICAL_NAMES}
    require(set(heads) == set(OUTPUT_IDS), "ProofFlow did not expose the eight artifact heads")
    return heads


def source_heads(state: dict) -> dict:
    return {source["name"]: source for source in state["dataset"]["sources"]}


def export_request(state: dict) -> dict:
    return {"generation": state["generation"],
            "report_ids": {report["key"]: report["id"] for report in state["reports"]}}


def cents(value: int | str) -> int:
    require(type(value) is int or (isinstance(value, str) and bool(re.fullmatch(r"-?[0-9]+", value))),
            "Report claim is not encoded in integer cents")
    return int(value)


def assert_snapshot(content: str, expected: dict, region: str) -> None:
    labels = {
        f"Company net revenue: {money(expected['company_report'])}",
        f"Regional net revenue ({region!r}): {money(expected['region_report'])}",
    }
    require(labels <= set(content.splitlines()), "Handoff claims differ from the frozen oracle")


def artifact_value(name: str, artifact: dict, currencies: dict) -> object:
    value = artifact["saved_value"]
    if name in ("gross", "refunds", "net"):
        require(all(row["currency"] == currencies[region] for region, row in value["regions"].items()),
                f"{name} currency mismatch")
        return {region: cents(row["amount_cents"]) for region, row in value["regions"].items()}
    if name in ("regional", "support"):
        field = "usd_cents" if name == "regional" else "tickets"
        return {region: cents(row[field]) for region, row in value["regions"].items()}
    if name == "company":
        return cents(value["usd_cents"])
    sections = value["sections"]
    require(len(sections) == 1 and sections[0]["unit"] == "USD cents", "Incorrect report claim unit")
    return cents(sections[0]["value"])


def check_outputs(observed: dict, expected: dict, arm: str) -> None:
    require(observed == expected, f"{arm} disagreed with the frozen semantic oracle: "
            f"{sorted(name for name in observed.keys() | expected.keys() if observed.get(name) != expected.get(name))}")


def observe_current(ledger, trace, client, state, case, currencies) -> dict:
    phase = case["id"]
    require(state["backend"]["engine"] == "HydraDB OSS" and state["backend"]["native_queries"] > 0
            and state["backend"]["fallback"] is False, f"{phase} was not a native HydraDB run")
    evidence, outputs = {}, {}
    for name, node in head_artifacts(state).items():
        route = f"/api/import/evidence/{quote(node['id'], safe='')}"
        entry = pf_request(ledger, trace, client, f"{phase}.evidence.{name}", "GET", route)
        evidence[name] = entry
        ledger.save(f"proofflow-{phase}-current-evidence", evidence)
        artifact, receipt = entry["artifact"], entry["receipt"]
        require(artifact["id"] == node["id"] and artifact["state"] == node["state"] == "current"
                and receipt["id"] == artifact["metadata"]["receipt_id"]
                and receipt["output_id"] == node["id"]
                and receipt["output_hash"] == artifact["content_hash"]
                and receipt["status"] == "success", f"{phase}/{name} lacks matching current receipt evidence")
        outputs[name] = artifact_value(name, artifact, currencies)
    for report in state["reports"]:
        claim, = report["claims"]
        require(report["state"] == claim["state"] == "current" and claim["unit"] == "USD cents"
                and cents(claim["value"]) == outputs[f"{report['key']}_report"],
                f"{phase} visible report differs from its evidence")
    check_outputs(outputs, case["expected"], "ProofFlow")
    return {"outputs": outputs, "sources": source_heads(state), "reports": state["reports"],
            "heads": head_artifacts(state), "receipt_ids": {name: entry["receipt"]["id"] for name, entry in evidence.items()},
            "backend": state["backend"], "executions": state["executions"]}


def observe_stale(ledger, trace, client, phase, updated, previous, case) -> dict:
    old_sources, new_sources = source_heads(previous), source_heads(updated)
    changed = case["changed_source"]
    changed_names = {name for name in old_sources if old_sources[name]["id"] != new_sources[name]["id"]}
    require(changed_names == {changed}, f"{phase} changed unexpected source heads")
    ancestor = old_sources[changed]["id"]
    affected = {LOGICAL_NAMES[item["logical_id"]] for item in updated["impact"]["affected_artifacts"]}
    require(affected == set(case["affected_outputs"]), f"{phase} affected scope mismatch")
    require([report["id"] for report in updated["reports"]] == [report["id"] for report in previous["reports"]]
            and updated["executions"] == previous["executions"], f"{phase} update wrote report work before refresh")
    require(not updated["incomplete_update"], f"{phase} had incomplete source publication")
    prior_heads = head_artifacts(previous)
    for name, node in head_artifacts(updated).items():
        expect = "stale" if name in affected else "current"
        require(node["id"] == prior_heads[name]["id"] and node["state"] == expect,
                f"{phase}/{name} has wrong freshness at the update boundary")
    graph_edges = {(edge["source"], edge["target"], edge["kind"]) for edge in updated["graph"]["edges"]}
    paths = {}
    for report in updated["reports"]:
        require(report["state"] == "stale" and all(claim["state"] == "stale" and claim["value"] is None
                for claim in report["claims"]), f"{phase} served a stale claim as current")
        evidence = pf_request(ledger, trace, client, f"{phase}.stale-evidence.{report['key']}", "GET",
                              f"/api/import/evidence/{quote(report['id'], safe='')}")
        candidates = [path for path in evidence["paths"] if path["source_id"] == ancestor
                      and path["target_id"] == report["id"]]
        paths[report["key"]] = candidates
        ledger.save(f"proofflow-{phase}-stale-paths", paths)
        require(bool(candidates), f"{phase} source path to {report['key']} is missing")
        for path in candidates:
            nodes = path["nodes"]
            require(nodes[0]["id"] == ancestor and nodes[0]["kind"] == "source"
                    and nodes[-1]["id"] == report["id"] and len(nodes) >= 3
                    and [node["kind"] for node in nodes[1:]] == ["execution", "artifact"] * ((len(nodes) - 1) // 2),
                    f"{phase} source path has incorrect endpoints or node kinds")
            observed = {(edge["source"], edge["target"], edge["kind"]) for edge in path["edges"]}
            expected = {(a["id"], b["id"], "PRODUCED" if a["kind"] == "execution" else "CONSUMED")
                        for a, b in zip(nodes, nodes[1:])}
            require(expected == observed and observed <= graph_edges,
                    f"{phase} source path does not match the native graph edges")
    return {"affected": sorted(affected), "superseded_source_id": ancestor,
            "updated_sources": new_sources, "state": updated["reports"], "heads": head_artifacts(updated),
            "native_path_counts": {name: len(items) for name, items in paths.items()}}


def guard_event(ledger, arm, step, outcome, expected_accept, **extra) -> None:
    accepted = outcome["accepted"]
    has_content = "content" in outcome
    ledger.append(arm=arm, step=step, accepted=accepted, report_content_returned=has_content,
                  **{key: value for key, value in outcome.items() if key not in {"accepted", "content"}}, **extra)
    require(accepted == has_content == expected_accept, f"{arm}/{step} handoff failed its expected policy")


def run_ordinary(ledger, directory, cases, region, currencies) -> dict:
    shared = SharedReports(directory)
    old_copy = None
    previous_outputs = {}
    results = {}
    for case in cases:
        phase = case["id"]
        ledger.append(arm="ordinary", step=f"{phase}.start")
        revision = InputRevision((FIXTURES / case["csv"]).read_bytes(), case["rates"], region)
        shared.set_source(revision)
        ledger.append(arm="ordinary", step=f"{phase}.publish-source", input=revision.metadata,
                      input_revision_sha256=revision.digest)
        if old_copy is not None:
            guard_event(ledger, "ordinary", f"{phase}.old-during",
                        shared.check_handoff(old_copy), False)
        report, outputs, accounting = shared.full_recalculate_and_publish()
        ledger.save(f"ordinary-{phase}-calculation", {"outputs": outputs, "accounting": accounting})
        check_outputs(outputs, case["expected"], "Ordinary")
        require(accounting["region_currencies"] == currencies, "Ordinary region currency does not match oracle")
        if old_copy is not None:
            guard_event(ledger, "ordinary", f"{phase}.old-after",
                        shared.check_handoff(old_copy), False)
        outcome = shared.check_handoff(report)
        guard_event(ledger, "ordinary", f"{phase}.current", outcome, True)
        assert_snapshot(outcome["content"], case["expected"], region)
        digest = ledger.snapshot(f"ordinary-{phase}", outcome["content"])
        unchanged = sorted(name for name in outputs if outputs[name] == previous_outputs.get(name))
        retained_file_check(ledger, "ordinary", results, phase)
        results[phase] = {
            "outputs": outputs, "recalculation": accounting, "old_values_equal": unchanged,
            "source": revision.metadata, "input_revision_sha256": revision.digest,
            "snapshot_sha256": digest,
        }
        ledger.save("ordinary-progress", results)
        previous_outputs, old_copy = outputs, report
    return results


def assert_current_handoff(snapshot: dict, state: dict, expected: dict, region: str) -> None:
    content = snapshot["content"]
    lines = content.splitlines()
    checked_at = datetime.fromisoformat(snapshot["checked_at"])
    require(checked_at.utcoffset() == timezone.utc.utcoffset(checked_at), "Snapshot check time is not UTC")
    require(f"Checked at (UTC): {snapshot['checked_at']}" in lines
            and "This file will not update after subsequent changes." in lines,
            "ProofFlow snapshot is missing its check-time or static label")
    for report in state["reports"]:
        claim, = report["claims"]
        require(f"Report artifact ID: {report['id']}" in lines
                and f"Claim artifact ID: {claim['artifact_id']}" in lines,
                "ProofFlow snapshot is missing its report or claim identity")
    assert_snapshot(content, expected, region)


def compare_refresh(current: dict, previous: dict, state: dict, case: dict) -> dict:
    retained = {name for name, node in current["heads"].items() if previous["heads"][name]["id"] == node["id"]}
    same_receipts = {name for name, receipt in current["receipt_ids"].items()
                     if previous["receipt_ids"][name] == receipt}
    changed = set(OUTPUT_IDS) - retained
    require(retained == same_receipts and changed == set(case["affected_outputs"]),
            "Refresh did not retain the expected heads and receipts")
    old_executions = {receipt["id"] for receipt in previous["executions"]}
    new_executions = [receipt for receipt in current["executions"] if receipt["id"] not in old_executions]
    summary = state["last_refresh"]
    expected_output_ids = {current["heads"][name]["id"] for name in changed}
    require(old_executions <= {receipt["id"] for receipt in current["executions"]}
            and len(new_executions) == summary["executed_count"] == len(changed)
            and {receipt["output_id"] for receipt in new_executions} == expected_output_ids
            and {call["output_id"] for call in summary["tool_calls"]} == expected_output_ids
            and summary["numeric_parity"] is True and summary["unchanged_support"] is True,
            "Recorded refresh calls, receipt deltas or fresh-recipe verification disagree")
    return {"retained_heads_and_receipts": sorted(retained), "recorded_outputs": sorted(changed),
            "new_receipt_ids": sorted(receipt["id"] for receipt in new_executions),
            "tool_calls": [{key: call[key] for key in ("tool", "status", "output_id")}
                           for call in summary["tool_calls"]]}


def run_proofflow(ledger, directory, cases, region, currencies) -> dict:
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from proofflow.api import COOKIE, create_app

    trace = ArithmeticTrace()
    app = create_app(state_dir=directory, static_dir=directory / "no-frontend")
    results = {}
    previous_state = previous_current = cached_export = None
    with trace.install(), TestClient(app, base_url="https://testserver") as first:
        second = TestClient(app, base_url="https://testserver")
        try:
            pf_request(ledger, trace, first, "health", "GET", "/health")
            bootstrapped = pf_request(ledger, trace, first, "session.bootstrap", "POST", "/api/session")
            ledger.save("proofflow-demo-bootstrap", {"backend": bootstrapped["backend"],
                        "executions": bootstrapped["executions"]})
            second.cookies.set(COOKIE, first.cookies[COOKIE])
            for case in cases:
                phase = case["id"]
                revision = InputRevision((FIXTURES / case["csv"]).read_bytes(), case["rates"], region)
                ledger.append(arm="proofflow", step=f"{phase}.start", input=revision.metadata,
                              input_revision_sha256=revision.digest)
                preview = pf_request(ledger, trace, second, f"{phase}.preview", "POST", "/api/import/preview",
                                     payload=revision.request())
                require(preview["valid"] is True and preview["persisted"] is False
                        and preview["content_sha256"] == revision.metadata["csv_sha256"]
                        and preview["selected_region"] == region, f"{phase} preview selected the wrong inputs")
                ledger.save(f"proofflow-{phase}-preview", preview)
                boundary = None
                if cached_export is None:
                    state = pf_request(ledger, trace, second, f"{phase}.create", "POST", "/api/import/create",
                                       payload=revision.request())
                else:
                    updated = pf_request(ledger, trace, second, f"{phase}.update", "POST", "/api/import/update",
                                         payload=revision.request())
                    ledger.save(f"proofflow-{phase}-update", {
                        "reports": updated["reports"], "sources": source_heads(updated),
                        "operation": updated["last_operation"], "impact": updated["impact"],
                        "graph": updated["graph"], "incomplete_update": updated["incomplete_update"],
                    })
                    during = pf_request(ledger, trace, first, f"{phase}.old-during", "POST", EXPORT_ROUTE,
                                        payload=cached_export, expected_status=409)
                    guard_event(ledger, "proofflow", f"{phase}.old-during-verdict", during, False, client="A")
                    fresh_stale = pf_request(ledger, trace, second, f"{phase}.fresh-stale-state", "GET",
                                             "/api/import/state")
                    require(fresh_stale["reports"] == updated["reports"] and source_heads(fresh_stale)
                            == source_heads(updated), f"{phase} fresh state differed at the update boundary")
                    boundary = observe_stale(ledger, trace, second, phase, fresh_stale, previous_state, case)
                    state = pf_request(ledger, trace, second, f"{phase}.refresh", "POST", "/api/import/refresh",
                                       payload={})
                    after = pf_request(ledger, trace, first, f"{phase}.old-after", "POST", EXPORT_ROUTE,
                                       payload=cached_export, expected_status=409)
                    guard_event(ledger, "proofflow", f"{phase}.old-after-verdict", after, False, client="A")
                require(state["dataset"]["source_csv_sha256"] == revision.metadata["csv_sha256"]
                        and state["dataset"]["selected_region"] == region
                        and all(Decimal(source_heads(state)["fx"]["summary"][code]) == Decimal(rate)
                                for code, rate in revision.rates.items()), f"{phase} used the wrong published inputs")
                current = observe_current(ledger, trace, second, state, case, currencies)
                if previous_current is None:
                    require(len(current["executions"]) == len(OUTPUT_IDS)
                            and {item["output_id"] for item in current["executions"]}
                            == {item["id"] for item in current["heads"].values()}, "Cold receipt scope mismatch")
                    work = {"recorded_outputs": sorted(OUTPUT_IDS), "retained_heads_and_receipts": []}
                else:
                    work = compare_refresh(current, previous_current, state, case)
                fresh = pf_request(ledger, trace, first, f"{phase}.reload-current", "GET", "/api/import/state")
                cached_export = export_request(fresh)
                require(cached_export == export_request(state), f"{phase} fresh view does not match published heads")
                snapshot = pf_request(ledger, trace, first, f"{phase}.current", "POST", EXPORT_ROUTE,
                                      payload=cached_export)
                guard_event(ledger, "proofflow", f"{phase}.current-verdict",
                            {"accepted": True, "content": snapshot["content"]}, True, client="A")
                assert_current_handoff(snapshot, fresh, case["expected"], region)
                digest = ledger.snapshot(f"proofflow-{phase}", snapshot["content"])
                retained_file_check(ledger, "proofflow", results, phase)
                results[phase] = {
                    "outputs": current["outputs"], "backend": current["backend"],
                    "sources": current["sources"], "report_ids": cached_export["report_ids"],
                    "artifact_ids": {name: node["id"] for name, node in current["heads"].items()},
                    "receipt_ids": current["receipt_ids"], "retained_work": work,
                    "stale_boundary": boundary, "source": revision.metadata,
                    "input_revision_sha256": revision.digest, "snapshot_sha256": digest,
                }
                ledger.save("proofflow-progress", results)
                previous_state, previous_current = state, current
        finally:
            second.close()
    return results


def retained_file_check(ledger: Ledger, arm: str, previous: dict, phase: str) -> None:
    for old_phase, item in previous.items():
        old_file = ledger.directory / f"{arm}-{old_phase}.txt"
        actual = sha256(old_file.read_bytes())
        ledger.append(arm=arm, step=f"{phase}.retained-file", file=old_file.name,
                      expected_sha256=item["snapshot_sha256"], actual_sha256=actual)
        require(item["snapshot_sha256"] == actual, f"{arm}/{old_phase} historical snapshot changed")


def source_hashes() -> dict:
    files = [
        PROTOCOL, "scripts/workflow_comparison.py", "docker-compose.yml", "pyproject.toml", "uv.lock",
        "fixtures/workflow_comparison/cases.json", "fixtures/workflow_comparison/base.csv",
        "fixtures/workflow_comparison/refund-corrected.csv",
        *[f"proofflow/{name}.py" for name in (
            "__init__", "analytics", "api", "artifacts", "browser_import", "demo", "graph",
            "importing", "models", "runtime",
        )],
    ]
    return {name: {"bytes": (ROOT / name).stat().st_size, "sha256": sha256((ROOT / name).read_bytes())}
            for name in files}


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def freeze_inputs() -> None:
    require(not FREEZE.exists(), f"{FREEZE.name} already exists")
    frozen = {
        "protocol": "workflow-comparison-v1", "frozen_at_utc": now(), "source_commit": git(["rev-parse", "HEAD"]),
        "runtime_paths_diff": git(["diff", "HEAD", "--name-only", "--", "proofflow", "pyproject.toml", "uv.lock"]),
        "files": source_hashes(),
    }
    write_json(FREEZE, frozen)
    print(sha256(FREEZE.read_bytes()))


def named_hydra_service() -> dict:
    args = ["docker", "inspect", "--format", "{{.State.Status}} {{.Image}}", "proofflow-hydradb-1"]
    status, digest = subprocess.check_output(args, text=True).split()
    require(status == "running" and digest ==
            "sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880",
            "Pinned loopback HydraDB OSS container is not available")
    return {"engine": "HydraDB OSS 0.4.0", "container_status": status, "image_digest": digest,
            "connection": "local Docker loopback TCP 18443"}


def module_versions() -> dict:
    from importlib.metadata import version

    return {"python": platform.python_version(), "system": platform.system(),
            "machine": platform.machine(), **{name: version(name) for name in ("fastapi", "httpx", "starlette")}}


def record_run(output: Path, reason: str) -> bool:
    require(FREEZE.exists(), "Freeze the comparison inputs before running")
    output.mkdir(parents=True, exist_ok=True)
    attempt_no = 1
    while True:
        attempt = output / f"attempt-{attempt_no:03d}"
        try:
            attempt.mkdir()
            break
        except FileExistsError:
            attempt_no += 1
    ledger = Ledger(attempt)
    run = {"started_at_utc": now(), "attempt": attempt_no, "reason": reason,
           "freeze_sha256": sha256(FREEZE.read_bytes()), "status": "running",
           "model_calls": 0, "arm_status": {"ordinary": "unobserved", "proofflow": "unobserved"}, "errors": {}}
    ledger.save("run", run)
    results = {}
    try:
        frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
        require(frozen["files"] == source_hashes(), "Finite comparison inputs differ from the prospective freeze")
        manifest = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
        cases, region, currencies = manifest["cases"], manifest["selected_region"], manifest["region_currencies"]
        run.update(source_commit=frozen["source_commit"], versions=module_versions())
        with tempfile.TemporaryDirectory(prefix="proofflow-workflow-comparison-") as directory:
            state = Path(directory)
            for arm, execute in (("ordinary", run_ordinary), ("proofflow", run_proofflow)):
                run["arm_status"][arm] = "running"
                ledger.save("run", run)
                try:
                    if arm == "proofflow":
                        run["backend"] = named_hydra_service()
                        ledger.save("run", run)
                    with patch.dict(os.environ, {
                        "PROOFFLOW_HYDRA_URL": "http://127.0.0.1:18443",
                        "PROOFFLOW_HYDRA_TOKEN_FILE": str(ROOT / ".state" / "hydra-token"),
                    }):
                        os.environ.pop("PROOFFLOW_HYDRA_TOKEN", None)
                        results[arm] = execute(ledger, state / arm, cases, region, currencies)
                except Exception as exc:
                    run["arm_status"][arm] = "failed"
                    run["errors"][arm] = {"type": type(exc).__name__, "message": str(exc)}
                    ledger.append(arm=arm, step="failed", **run["errors"][arm])
                else:
                    run["arm_status"][arm] = "passed"
                    ledger.append(arm=arm, step="passed")
                ledger.save("run", run)
        if not run["errors"]:
            require(all(results["ordinary"][case["id"]]["outputs"] == results["proofflow"][case["id"]]["outputs"]
                        for case in cases), "Cross-arm output mismatch")
    except Exception as exc:
        run["errors"]["runner"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        run["finished_at_utc"] = now()
        run["status"] = "passed" if set(run["arm_status"].values()) == {"passed"} and not run["errors"] else "failed"
        ledger.save("run", run)
    print(json_text({"attempt": attempt.name, "status": run["status"], "errors": run["errors"]}, pretty=True))
    return run["status"] == "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommand = parser.add_subparsers(dest="command", required=True)
    subcommand.add_parser("freeze", help="Record prospective inputs without running either workflow")
    run = subcommand.add_parser("run", help="Run a new paired attempt without overwriting earlier evidence")
    run.add_argument("--output", type=Path, default=ROOT / "results" / "workflow-comparison-v1")
    run.add_argument("--reason", required=True, help="Give the initial run or rerun reason for the attempt ledger")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze_inputs()
        return 0
    return 0 if record_run(args.output.resolve(), args.reason) else 1


if __name__ == "__main__":
    raise SystemExit(main())
