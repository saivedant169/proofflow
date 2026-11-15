"""Frozen external-data fixtures for retail-v2; no runtime or retrieval imports.

This module prepares public transaction data and declares requests. It never
queries HydraDB, computes a retrieval score, or reads prior benchmark results.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "retail_v2"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/352/online%2Bretail.zip"
SOURCE_PAGE = "https://archive.ics.uci.edu/dataset/352/online%2Bretail"
ZIP_SHA256 = "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b"
XLSX_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
DEV_PARTITIONS = ("2010-12",)
TEST_PARTITIONS = ("2011-02", "2011-05", "2011-08", "2011-11")
PARTITIONS = DEV_PARTITIONS + TEST_PARTITIONS
MAX_PARTITION_ROWS = 160
SELECTION_SALT = "proofflow-retail-v2-invoices-1"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = ("InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class RetailRecipe:
    name: str
    tool: str
    inputs: dict[str, str]
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    run: str = "retail-run"


@dataclass(frozen=True)
class RetailMutation:
    source: str = ""
    operation: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    tool: str = ""


@dataclass(frozen=True)
class RetailCase:
    id: str
    split: str
    description: str
    mutations: tuple[RetailMutation, ...]
    category: str
    scope_partitions: tuple[str, ...]
    restart: bool = False


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(item.text or "" for item in cell.iter(NS + "t"))
    value = cell.findtext(NS + "v", "")
    return shared[int(value)] if kind == "s" and value else value


def iter_source_rows(workbook: Path) -> Iterable[tuple[int, dict[str, str]]]:
    """Stream the pinned worksheet; never export CustomerID/Description."""
    if sha_file(workbook) != XLSX_SHA256:
        raise ValueError("Unexpected source workbook hash; do not silently replace the frozen source")
    with zipfile.ZipFile(workbook) as archive:
        wb = ET.fromstring(archive.read("xl/workbook.xml"))
        properties = wb.find(NS + "workbookPr")
        if properties is not None and properties.attrib.get("date1904") in {"1", "true"}:
            raise ValueError("The frozen parser expects the workbook's 1900 date system")
        shared = []
        with archive.open("xl/sharedStrings.xml") as stream:
            for _, item in ET.iterparse(stream, events=("end",)):
                if item.tag == NS + "si":
                    shared.append("".join(node.text or "" for node in item.iter(NS + "t")))
                    item.clear()
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            for _, row in ET.iterparse(stream, events=("end",)):
                if row.tag != NS + "row":
                    continue
                row_number = int(row.attrib["r"])
                cells = {"".join(c for c in cell.attrib["r"] if c.isalpha()): _cell_text(cell, shared)
                         for cell in row.findall(NS + "c")}
                values = {header: cells.get(chr(65 + i), "") for i, header in enumerate(HEADERS)}
                if row_number == 1:
                    if tuple(values.values()) != HEADERS:
                        raise ValueError("Unexpected workbook header")
                else:
                    yield row_number, values
                row.clear()


def normalize_row(source_row: int, raw: dict[str, str]) -> tuple[str | None, dict[str, Any] | None, str]:
    """Interpret XLSX numeric cells as binary64, then use exact Decimal pence."""
    try:
        serial = float(raw["InvoiceDate"])
        if not math.isfinite(serial):
            return None, None, "invalid_date"
        stamp = datetime(1899, 12, 30) + timedelta(days=serial)
        partition = stamp.strftime("%Y-%m")
    except (ValueError, OverflowError):
        return None, None, "invalid_date"
    if partition not in PARTITIONS:
        return partition, None, "outside_declared_partitions"
    invoice = raw["InvoiceNo"].strip()
    country = raw["Country"].strip()
    if invoice.upper().startswith("C"):
        return partition, None, "cancellation_invoice"
    if not invoice or not country or len(country) > 64 or country.startswith("__") or any(ord(c) < 32 for c in country):
        return partition, None, "invalid_identifier_or_country"
    try:
        quantity_number = float(raw["Quantity"])
        price_number = float(raw["UnitPrice"])
        if not math.isfinite(quantity_number) or not quantity_number.is_integer() or quantity_number <= 0:
            return partition, None, "nonpositive_or_noninteger_quantity"
        if not math.isfinite(price_number) or price_number <= 0:
            return partition, None, "nonpositive_or_invalid_price"
        quantity = int(quantity_number)
        if quantity > 10**9:
            return partition, None, "quantity_bound"
        price = str(price_number)
        amount = Decimal(price) * quantity * 100
        if amount != amount.to_integral_value():
            return partition, None, "fractional_line_pence"
        gross = int(amount)
        if not 0 < gross <= 10**12:
            return partition, None, "amount_bound"
    except (ValueError, OverflowError):
        return partition, None, "invalid_numeric_cell"
    return partition, {
        "order_id": f"uci:{invoice}:row:{source_row}", "region": country, "currency": "GBP",
        "gross_cents": gross, "quantity": quantity, "unit_price_gbp": price,
        "unit_price_raw_xml": raw["UnitPrice"], "quantity_raw_xml": raw["Quantity"],
        "source_row": source_row, "invoice_no": invoice, "stock_code": raw["StockCode"],
        "invoice_date": stamp.replace(microsecond=0).isoformat(),
    }, "eligible"


def select_partitions(workbook: Path) -> tuple[dict[str, list[dict]], dict[str, Any]]:
    groups: dict[str, dict[str, list[dict]]] = {p: defaultdict(list) for p in PARTITIONS}
    counts: dict[str, Counter] = {p: Counter() for p in PARTITIONS}
    total = 0
    for source_row, raw in iter_source_rows(workbook):
        total += 1
        partition, row, reason = normalize_row(source_row, raw)
        if partition in counts:
            counts[partition][reason] += 1
        if row is not None:
            groups[partition][row["invoice_no"]].append(row)
    selected = {}
    metadata = {"worksheet_data_rows": total, "partition_profiles": {}}
    seen_invoices: set[str] = set()
    for partition in PARTITIONS:
        invoices = groups[partition]
        order = sorted(invoices, key=lambda invoice: (hashlib.sha256(f"{SELECTION_SALT}:{invoice}".encode()).hexdigest(), invoice))
        rows: list[dict] = []
        chosen, skipped_size = [], []
        for invoice in order:
            eligible_rows = invoices[invoice]
            if len(rows) + len(eligible_rows) > MAX_PARTITION_ROWS:
                skipped_size.append(invoice)
                continue
            chosen.append(invoice)
            rows.extend(eligible_rows)
        if len(rows) < 40:
            raise ValueError(f"Insufficient eligible sample for {partition}")
        overlap = seen_invoices.intersection(chosen)
        if overlap:
            raise ValueError("Invoice identities overlap partitions; refuse split contamination")
        seen_invoices.update(chosen)
        selected[partition] = sorted(rows, key=lambda row: row["order_id"])
        metadata["partition_profiles"][partition] = {
            "eligibility_counts": dict(sorted(counts[partition].items())),
            "eligible_invoices": len(invoices), "selected_invoices": chosen,
            "selected_rows": len(rows), "selected_countries": sorted({row["region"] for row in rows}),
            "skipped_invoice_groups_for_size": len(skipped_size),
            "selected_original_row_numbers": sorted(row["source_row"] for row in rows),
        }
    return selected, metadata


def _section(key: str, label: str, port: str, path: list[str]) -> dict:
    return {"key": key, "label": label, "input": port, "path": path, "unit": "USD cents"}


def recipe_definitions(partitions: tuple[str, ...], rows: dict[str, list[dict]]) -> list[RetailRecipe]:
    declared = []
    for p in partitions:
        region = sorted({row["region"] for row in rows[p]})[0]
        for name, tool, inputs, label in [
            ("gross", "gross_by_region", {"orders": f"source:{p}:orders"}, "Positive sampled gross sales by country in GBP"),
            ("refunds", "refunds_by_region", {"orders": f"source:{p}:orders", "refunds": f"source:{p}:refunds"}, "Staged refunds, initially empty, by country in GBP"),
            ("net", "net_by_region", {"gross": f"{p}:gross", "refunds": f"{p}:refunds"}, "Sampled gross sales less staged refunds in GBP"),
            ("gross_usd", "convert_to_usd", {"net": f"{p}:gross", "fx": f"source:{p}:fx"}, "Gross sales converted directly to USD, without the net-sales branch"),
            ("net_usd", "convert_to_usd", {"net": f"{p}:net", "fx": f"source:{p}:fx"}, "Net sales converted to USD after staged refunds"),
            ("gross_total", "company_total", {"regional": f"{p}:gross_usd"}, "Whole selected sample gross sales in USD"),
            ("net_total", "company_total", {"regional": f"{p}:net_usd"}, "Whole selected sample net sales in USD"),
        ]:
            declared.append(RetailRecipe(f"{p}:{name}", tool, inputs, description=f"{label}; {p}.", run=f"snapshot-{p}"))
        declared.append(RetailRecipe(f"{p}:gross_net_brief", "compose_report",
            {"gross": f"{p}:gross_total", "net": f"{p}:net_total"},
            {"title": f"{p} positive-sales sample gross and net brief", "sections": [
                _section("gross", "Sample gross sales", "gross", ["usd_cents"]),
                _section("net", "Sample sales less staged refunds", "net", ["usd_cents"])]},
            f"Two parallel monetary branches for the actual sampled invoices from {p}.", f"brief-{p}"))
        declared.append(RetailRecipe(f"{p}:country_brief", "compose_report",
            {"gross": f"{p}:gross_usd", "net": f"{p}:net_usd"},
            {"title": f"{region} positive-sales sample for {p}", "sections": [
                _section("gross", f"{region} sampled gross sales", "gross", ["regions", region, "usd_cents"]),
                _section("net", f"{region} sales less staged refunds", "net", ["regions", region, "usd_cents"])]},
            f"Country-specific brief for {region}, {p}; both monetary artifacts reused from the earlier snapshot run.", f"country-{p}"))
    for prior, current in zip(partitions, partitions[1:]):
        region = sorted({row["region"] for row in rows[current]})[0]
        declared.append(RetailRecipe(f"cross:{prior}:{current}:three_input", "compose_report",
            {"previous_net": f"{prior}:net_total", "current_gross": f"{current}:gross_total", "current_country_net": f"{current}:net_usd"},
            {"title": f"Sample comparison {prior} and {current}", "sections": [
                _section("previous_net", f"{prior} sample net sales", "previous_net", ["usd_cents"]),
                _section("current_gross", f"{current} sample gross sales", "current_gross", ["usd_cents"]),
                _section("current_country_net", f"{current} {region} sample net sales", "current_country_net", ["regions", region, "usd_cents"])]},
            "Three-input composition reuses gross and net artifacts from two independent dated snapshot runs.", f"comparison-{prior}-{current}"))
    return declared


def _target(rows: list[dict]) -> dict:
    return next(row for row in rows if Decimal(row["unit_price_gbp"]) * 100 == (Decimal(row["unit_price_gbp"]) * 100).to_integral_value())


def case_definitions(rows: dict[str, list[dict]]) -> list[RetailCase]:
    def mutation(p, operation, **parameters):
        return RetailMutation(f"{p}:orders", operation, parameters)
    def quantity(p):
        row = _target(rows[p])
        return mutation(p, "quantity_delta", order_id=row["order_id"], delta_quantity=1,
                        unit_price_gbp=row["unit_price_gbp"])
    def price(p):
        row = _target(rows[p])
        return mutation(p, "unit_price_delta_pence", order_id=row["order_id"], delta_pence=1,
                        quantity=row["quantity"])
    def refund(p):
        row = rows[p][0]
        return RetailMutation(f"{p}:refunds", "refund_add", {"order_id": row["order_id"], "refund_cents": max(1, row["gross_cents"] // 10)})
    d = DEV_PARTITIONS[0]
    a, b, c, e = TEST_PARTITIONS
    cases = [
        RetailCase("RD01", "dev", f"Correct the quantity on one sampled invoice line in {d}.", (quantity(d),), "quantity", DEV_PARTITIONS),
        RetailCase("RD02", "dev", f"Add a staged refund in {d}; gross sales remain reusable.", (refund(d),), "gross_net_divergence", DEV_PARTITIONS),
        RetailCase("RD03", "dev", f"Correct the illustrative GBP conversion for {d} to 1.27 USD.", (RetailMutation(f"{d}:fx", "fx_set", {"GBP": "1.27"}),), "fx", DEV_PARTITIONS),
        RetailCase("RD04", "dev", f"Reorder identical selected invoice lines from {d}; canonical source input remains equal.", (mutation(d, "reorder"),), "canonical_noop", DEV_PARTITIONS),
        RetailCase("R01", "test", f"A quantity correction in {a} must reach both gross and net branches and later reused briefs.", (quantity(a),), "parallel_quantity", TEST_PARTITIONS),
        RetailCase("R02", "test", f"A one-penny unit-price correction in {b} changes a sampled invoice subtotal.", (price(b),), "price", TEST_PARTITIONS),
        RetailCase("R03", "test", f"Add a clearly staged refund in {c}; only the net branch and its consumers need revalidation.", (refund(c),), "gross_net_divergence", TEST_PARTITIONS),
        RetailCase("R04", "test", f"Correct the illustrative GBP-to-USD rate in {e} to 1.31; earlier partition evidence stays usable.", (RetailMutation(f"{e}:fx", "fx_set", {"GBP": "1.31"}),), "fx_partition", TEST_PARTITIONS),
    ]
    by_country: dict[str, list[dict]] = defaultdict(list)
    for row in rows[a]:
        by_country[row["region"]].append(row)
    country = next(key for key in sorted(by_country) if len(by_country[key]) >= 2)
    pair = by_country[country][:2]
    cases.extend([
        RetailCase("R05", "test", f"Offset two {country} invoice-line subtotals in {a} by one penny; all country aggregates remain equal but source contents change.",
                   (mutation(a, "offset_gross", first=pair[0]["order_id"], second=pair[1]["order_id"], delta_cents=1),), "same_value_revalidation", TEST_PARTITIONS),
        RetailCase("R06", "test", f"Apply a staged refund in {b} and a quantity correction in {e}; find their combined cross-run impact.",
                   (refund(b), quantity(e)), "multiple_partitions", TEST_PARTITIONS),
        RetailCase("R07", "test", f"The illustrative FX source for {c} is unavailable; block dependent claims while preserving other dated reports.",
                   (RetailMutation(f"{c}:fx", "remove"),), "missing_source", TEST_PARTITIONS),
        RetailCase("R08", "test", "The conversion implementation version is replaced for every saved snapshot; arithmetic is unchanged but old receipts require revalidation.",
                   (RetailMutation(operation="tool_version", tool="convert_to_usd", parameters={"version": "retail-v2-2"}),), "global_tool_version", TEST_PARTITIONS),
        RetailCase("R09", "test", f"Reorder the identical selected invoice lines in {b}; normalization must preserve source identities and do no new calculations.",
                   (mutation(b, "reorder"),), "canonical_noop", TEST_PARTITIONS),
        RetailCase("R10", "test", f"Correct one quantity in {e}, then reopen the application before selecting evidence and refreshing cross-partition briefs.",
                   (quantity(e),), "restart_after_change", TEST_PARTITIONS, restart=True),
    ])
    return cases


def mutate_value(value: Any, mutation: RetailMutation) -> Any:
    """Apply a frozen staged change; no labels or retrieval decisions enter here."""
    if mutation.operation == "remove":
        return None
    result = deepcopy(value)
    p = mutation.parameters
    if mutation.operation == "quantity_delta":
        row = next(row for row in result if row["order_id"] == p["order_id"])
        change = Decimal(p["unit_price_gbp"]) * p["delta_quantity"] * 100
        if change != change.to_integral_value():
            raise ValueError("Quantity correction has fractional line pence")
        row["gross_cents"] += int(change)
    elif mutation.operation == "unit_price_delta_pence":
        row = next(row for row in result if row["order_id"] == p["order_id"])
        row["gross_cents"] += p["delta_pence"] * p["quantity"]
    elif mutation.operation == "refund_add":
        result.append(dict(p))
    elif mutation.operation == "fx_set":
        result.update(p)
    elif mutation.operation == "offset_gross":
        next(row for row in result if row["order_id"] == p["first"])["gross_cents"] += p["delta_cents"]
        next(row for row in result if row["order_id"] == p["second"])["gross_cents"] -= p["delta_cents"]
    elif mutation.operation == "reorder":
        result = list(reversed(result))
    else:
        raise ValueError(f"Unsupported retail data mutation: {mutation.operation}")
    if isinstance(result, list):
        result.sort(key=lambda row: row["order_id"])
    return result


def manifest_data() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "fixture.json").read_text())


def fixture_sources(split: str = "test") -> dict[str, Any]:
    fixture = manifest_data()
    parts = set(fixture["partitions_by_split"][split])
    return deepcopy({key: value for key, value in fixture["sources"].items() if key.split(":", 1)[0] in parts})


def recipes(split: str = "test") -> list[RetailRecipe]:
    return [RetailRecipe(**entry) for entry in manifest_data()["recipes_by_split"][split]]


def scenarios(split: str = "test") -> list[RetailCase]:
    result = []
    for entry in manifest_data()["cases"]:
        if entry["split"] == split:
            result.append(RetailCase(**{**entry, "mutations": tuple(RetailMutation(**m) for m in entry["mutations"]),
                                      "scope_partitions": tuple(entry["scope_partitions"])}))
    return result


def candidate_names(case: RetailCase, declarations: list[RetailRecipe]) -> set[str]:
    scope = set(case.scope_partitions)
    selected = set()
    for recipe in declarations:
        parts = recipe.name.split(":")
        if (parts[0] in scope) or (parts[0] == "cross" and set(parts[1:3]) <= scope):
            selected.add(recipe.name)
    return selected


def fixture_file_hashes() -> list[dict[str, str]]:
    return [{"path": str(path.relative_to(ROOT)), "sha256": sha_file(path)}
            for path in sorted(FIXTURE_DIR.rglob("*")) if path.is_file()]


def prepare_fixture(workbook: Path, destination: Path = FIXTURE_DIR) -> dict[str, Any]:
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Refusing to overwrite retail-v2 fixtures; preserve the original freeze")
    rows, profile = select_partitions(workbook)
    destination.mkdir(parents=True, exist_ok=True)
    sources = {}
    files = {}
    for p in PARTITIONS:
        orders = [{k: row[k] for k in ("order_id", "region", "currency", "gross_cents")} for row in rows[p]]
        sources.update({f"{p}:orders": orders, f"{p}:refunds": [], f"{p}:tickets": [],
                        f"{p}:fx": {"GBP": "1.25", "USD": "1"}})
        csv_path = destination / f"{p}.csv"
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["order_id", "region", "currency", "gross_cents"])
            writer.writeheader()
            writer.writerows(orders)
        provenance = destination / f"{p}.provenance.json"
        provenance.write_text(json.dumps(rows[p], indent=2, ensure_ascii=False) + "\n")
        files[p] = {"csv": csv_path.name, "csv_sha256": sha_file(csv_path),
                    "provenance": provenance.name, "provenance_sha256": sha_file(provenance),
                    "rows": len(orders), "selected_region": sorted({row["region"] for row in rows[p]})[0]}
    fixture = {
        "version": "retail-v2-1", "source": {"page": SOURCE_PAGE, "download": SOURCE_URL,
            "zip_sha256": ZIP_SHA256, "xlsx_sha256": XLSX_SHA256, "worksheet": "Online Retail",
            "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33",
            "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"},
        "numeric_policy": "XLSX numeric XML decoded as finite binary64, shortest round-trip decimal string; exact Decimal quantity*GBP_price*100 integer pence; no monetary rounding",
        "selection": {"salt": SELECTION_SALT, "max_rows_per_partition": MAX_PARTITION_ROWS,
            "policy": "SHA256-order complete eligible invoice groups; skip a group if it exceeds remaining row capacity; all selected eligible lines retained; positive sales only"},
        "partitions_by_split": {"dev": list(DEV_PARTITIONS), "test": list(TEST_PARTITIONS)},
        "partition_files": files, "profile": profile, "sources": sources,
        "recipes_by_split": {"dev": [asdict(r) for r in recipe_definitions(DEV_PARTITIONS, rows)],
                             "test": [asdict(r) for r in recipe_definitions(TEST_PARTITIONS, rows)]},
        "cases": [asdict(case) for case in case_definitions(rows)],
        "limitations": ["Positive sampled sales, not complete merchant revenue", "FX and corrections are staged interventions, not historical incidents",
                        "No CustomerID or product descriptions exported", "No ticket or refund observations invented; initial refund/ticket sources empty",
                        "Gross conversion uses the existing monetary-region contract; the input port named net receives explicitly labeled gross monetary values"],
    }
    (destination / "fixture.json").write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    return fixture
