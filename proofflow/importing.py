"""Bounded CSV ingestion for actual local analytics, without a model or SQL input.

Input ticket counts are expanded into synthetic counting rows. Their generated
IDs are provenance for that expansion, not identifiers of original tickets.
The import is preflighted before writes, but publishing multiple source heads
is not a distributed transaction. Any runtime/database failure remains a failure.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import io
import re
from typing import Any, Mapping

from .analytics import execute_tool
from .runtime import ProofFlowRuntime


MAX_BYTES = 1024 * 1024
MAX_ROWS = 1000
MAX_TICKETS = 10000
MAX_CENTS_PER_ROW = 10**12
CURRENCIES = frozenset({"USD", "EUR", "GBP"})
REQUIRED_FIELDS = ("order_id", "region", "currency", "gross_cents")
OPTIONAL_FIELDS = ("refund_cents", "ticket_count")
COMPANY_REPORT = "import:report:company"
REGION_REPORT = "import:report:region"
SUPPORT_ARTIFACT = "import:metric:support"


class CSVImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportedDataset:
    sources: dict[str, Any]
    region: str
    row_count: int
    content_sha256: str


def _text(value: str, label: str, limit: int) -> str:
    if (not value or value != value.strip() or len(value) > limit
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise CSVImportError(f"{label} must be nonempty, trimmed text of at most {limit} characters")
    return value


def _count(value: str, label: str, maximum: int) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise CSVImportError(f"{label} must be a nonnegative integer, without currency symbols or decimals")
    if len(value) > 16 or int(value) > maximum:
        raise CSVImportError(f"{label} exceeds its supported limit of {maximum}")
    return int(value)


def _rates(values: Mapping[str, str] | None, used: set[str]) -> dict[str, str]:
    if values is not None and (not isinstance(values, Mapping)
                               or any(key not in CURRENCIES for key in values)):
        raise CSVImportError("FX accepts USD, EUR and GBP only")
    supplied = {"USD": "1", **(dict(values) if values is not None else {})}
    output = {}
    for currency, text in sorted(supplied.items()):
        if not isinstance(text, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?", text):
            raise CSVImportError(f"FX for {currency} must be a positive decimal string")
        try:
            value = Decimal(text)
        except InvalidOperation as exc:
            raise CSVImportError(f"FX for {currency} is invalid") from exc
        if not value.is_finite() or not Decimal("0") < value <= Decimal("1000"):
            raise CSVImportError(f"FX for {currency} must be greater than zero and at most 1000")
        if currency == "USD" and value != 1:
            raise CSVImportError("USD is the output currency, so its USD rate must equal 1")
        output[currency] = format(value.normalize(), "f")
    missing = used - set(output)
    if missing:
        raise CSVImportError(f"Explicit USD exchange rates are required for: {', '.join(sorted(missing))}")
    return output


def parse_csv(payload: bytes, *, rates: Mapping[str, str] | None = None,
              region: str | None = None) -> ImportedDataset:
    """Validate UTF-8 bytes and derive four typed sources without any writes."""
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_BYTES:
        raise CSVImportError("CSV must contain 1 byte to 1 MiB")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError("CSV must be UTF-8 encoded") from exc
    orders, refunds, tickets = [], [], []
    seen: set[str] = set()
    region_currencies: dict[str, str] = {}
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        fields = next(reader, [])
        if len(fields) != len(set(fields)) or set(fields) - set(REQUIRED_FIELDS + OPTIONAL_FIELDS):
            raise CSVImportError("CSV has duplicate or unsupported headers")
        if not set(REQUIRED_FIELDS) <= set(fields):
            raise CSVImportError(f"Required CSV headers: {', '.join(REQUIRED_FIELDS)}")
        for row_number, cells in enumerate(reader, 2):
            if not cells:
                continue
            if len(cells) != len(fields):
                raise CSVImportError(f"Row {row_number} has the wrong number of columns")
            if len(orders) >= MAX_ROWS:
                raise CSVImportError(f"CSV exceeds {MAX_ROWS} order rows")
            row = dict(zip(fields, cells))
            order_id = _text(row["order_id"], f"Row {row_number} order_id", 200)
            area = _text(row["region"], f"Row {row_number} region", 64)
            if area.startswith("__"):
                raise CSVImportError("Region names starting with '__' are unsupported report paths")
            currency = row["currency"]
            if currency not in CURRENCIES:
                raise CSVImportError(f"Row {row_number} currency must be USD, EUR or GBP")
            if order_id in seen:
                raise CSVImportError(f"Duplicate order_id at row {row_number}")
            seen.add(order_id)
            if area in region_currencies and region_currencies[area] != currency:
                raise CSVImportError(f"Region {area!r} contains mixed currencies")
            region_currencies[area] = currency
            gross = _count(row["gross_cents"], f"Row {row_number} gross_cents", MAX_CENTS_PER_ROW)
            refund = _count(row.get("refund_cents") or "0", f"Row {row_number} refund_cents", MAX_CENTS_PER_ROW)
            count = _count(row.get("ticket_count") or "0", f"Row {row_number} ticket_count", MAX_TICKETS)
            if refund > gross:
                raise CSVImportError(f"Row {row_number} refunds exceed that order's gross amount")
            if len(tickets) + count > MAX_TICKETS:
                raise CSVImportError(f"CSV ticket counts exceed {MAX_TICKETS} expanded counting rows")
            orders.append({"order_id": order_id, "region": area, "currency": currency, "gross_cents": gross})
            if refund:
                refunds.append({"order_id": order_id, "refund_cents": refund})
            prefix = hashlib.sha256(order_id.encode()).hexdigest()
            tickets.extend({"ticket_id": f"csv-count:{prefix}:{index}", "region": area,
                            "status": "reported_count"} for index in range(count))
    except csv.Error as exc:
        raise CSVImportError("CSV quoting or field size is invalid") from exc
    if not orders:
        raise CSVImportError("CSV must contain at least one order")
    selected = region if region is not None else sorted(region_currencies)[0]
    if selected not in region_currencies:
        raise CSVImportError("Selected region must exist in the imported orders")
    sources = {
        "orders": sorted(orders, key=lambda row: row["order_id"]),
        "refunds": sorted(refunds, key=lambda row: row["order_id"]),
        "tickets": sorted(tickets, key=lambda row: row["ticket_id"]),
        "fx": _rates(rates, set(region_currencies.values())),
    }
    dataset = ImportedDataset(sources, selected, len(orders), hashlib.sha256(payload).hexdigest())
    _preflight(dataset)
    return dataset


def _report_params(region: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {"title": "Imported company revenue", "sections": [{
            "key": "company_revenue", "label": "Company net revenue", "input": "revenue",
            "path": ["usd_cents"], "unit": "USD cents"}]},
        {"title": f"{region} revenue brief", "sections": [{
            "key": "regional_revenue", "label": f"{region} net revenue", "input": "revenue",
            "path": ["regions", region, "usd_cents"], "unit": "USD cents"}]},
    )


def _preflight(dataset: ImportedDataset) -> None:
    """Exercise every supported calculation/path before publishing source heads."""
    values = dataset.sources
    gross = execute_tool("gross_by_region", {"orders": values["orders"]})
    refunds = execute_tool("refunds_by_region", {"orders": values["orders"], "refunds": values["refunds"]})
    net = execute_tool("net_by_region", {"gross": gross, "refunds": refunds})
    regional = execute_tool("convert_to_usd", {"net": net, "fx": values["fx"]})
    company = execute_tool("company_total", {"regional": regional})
    execute_tool("support_by_region", {"tickets": values["tickets"]})
    company_params, region_params = _report_params(dataset.region)
    execute_tool("compose_report", {"revenue": company}, company_params)
    execute_tool("compose_report", {"revenue": regional}, region_params)


def apply_import(runtime: ProofFlowRuntime, dataset: ImportedDataset) -> dict[str, Any]:
    """Create or refresh an isolated CSV workspace using real runtime operations.

    Callers must serialize access to a workspace across processes. The supplied
    CLI does this with a file lock; the runtime lock protects this entire local
    sequence within one process. No API accepts filesystem paths through here.
    """
    _preflight(dataset)
    with runtime._lock:
        if any(not head.logical_id.startswith(("source:csv:", "tool:", "import:"))
               for head in runtime.store.heads()):
            raise CSVImportError("CSV imports require an isolated import workspace")
        old_company = runtime.store.get_head(COMPANY_REPORT)
        old_region = runtime.store.get_head(REGION_REPORT)
        company_params, region_params = _report_params(dataset.region)
        if old_region and old_region.metadata["params"] != region_params:
            raise CSVImportError("Keep the existing selected region, or choose a new import workspace")
        changes, sources = [], {}
        before = len(runtime.calls)
        for name, value in dataset.sources.items():
            change = runtime.set_source(f"csv:{name}", value,
                "Imported CSV count expansion; generated IDs are not original ticket IDs"
                if name == "tickets" else f"User-supplied CSV {name}; FX supplied explicitly")
            sources[name] = change.current_id
            if change.changed and change.previous_id:
                changes.append(change.previous_id)
        affected = runtime.affected(changes) if changes else []
        refresh = None
        support = runtime.store.get_head(SUPPORT_ARTIFACT)
        if old_company and old_region and support:
            refresh = runtime.refresh([old_company.id, old_region.id, support.id]).to_dict()
        else:
            def run(tool: str, inputs: dict[str, str], name: str):
                return runtime.execute(tool, inputs, logical_id=f"import:metric:{name}", run_id="csv-company-run")
            gross = run("gross_by_region", {"orders": sources["orders"]}, "gross")
            refunds = run("refunds_by_region", {"orders": sources["orders"], "refunds": sources["refunds"]}, "refunds")
            net = run("net_by_region", {"gross": gross.id, "refunds": refunds.id}, "net")
            regional = run("convert_to_usd", {"net": net.id, "fx": sources["fx"]}, "regional")
            company = run("company_total", {"regional": regional.id}, "company")
            run("support_by_region", {"tickets": sources["tickets"]}, "support")
            runtime.execute("compose_report", {"revenue": company.id}, company_params,
                            logical_id=COMPANY_REPORT, run_id="csv-company-run")
            runtime.execute("compose_report", {"revenue": regional.id}, region_params,
                            logical_id=REGION_REPORT, run_id="csv-region-run")
        reports = []
        for logical_id in [COMPANY_REPORT, REGION_REPORT]:
            record = runtime.store.get_head(logical_id)
            state = runtime.currentness(record.id)
            saved = runtime.store.read(record.id)
            parity = saved == runtime.full_recompute(record.id)
            if not state.is_current or not parity:
                raise CSVImportError("Import did not produce current reports with recomputation parity")
            reports.append({"id": record.id, "logical_id": logical_id, "state": state.state,
                            "claims": runtime.report_claims(record.id), "recomputation_parity": parity})
        support = runtime.store.get_head(SUPPORT_ARTIFACT)
        support_state = runtime.currentness(support.id)
        if not support_state.is_current:
            raise CSVImportError("Imported support-count artifact is not current")
        return {"status": "complete", "workspace": runtime.store.workspace,
                "source_csv_sha256": dataset.content_sha256, "row_count": dataset.row_count,
                "selected_region": dataset.region, "changed_source_version_ids": changes,
                "affected_artifacts": [record.to_dict() for record in affected],
                "reports": reports, "refresh": refresh,
                "tool_calls": runtime.calls[before:], "tool_call_count": len(runtime.calls) - before,
                "support": {"id": support.id, "state": support_state.state,
                            "value": runtime.store.read(support.id)},
                "scope": "User-supplied CSV; guided recipes and real analytics. No model or generic SQL execution.",
                "verification": "Currentness plus clean recipe recomputation; shared arithmetic, not an independent benchmark oracle.",
                "ticket_semantics": "Per-order counts expanded into synthetic counting rows, not original ticket identifiers.",
                "atomicity": "Source heads are individually durable; multi-source publication is not transactional."}
