"""Fresh complete-date retail fixtures for prospective model comparison v4.

Data preparation never calls a selector, execution runtime, or model. Prior
fixtures and production code remain unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .retail_data import (RetailCase, RetailMutation, RetailRecipe, SOURCE_PAGE,
                          SOURCE_URL, XLSX_SHA256, canonical, iter_source_rows, sha_file)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "fixtures" / "model_comparison_v4"
MONTHS = {"dev": "2011-06", "test": "2011-03"}
DATES_PER_SPLIT = {"dev": 2, "test": 4}
VERSION = "model-comparison-retail-v4-1"
MAX_QUANTITY = 10**9
MAX_LINE_PENCE = 10**12
MAX_SQLITE_INTEGER = 2**63 - 1


def normalize_row(source_row: int, raw: dict[str, str], month: str
                  ) -> tuple[str | None, dict[str, Any] | None, str]:
    """Apply the frozen binary64 numeric-cell policy, without sampling."""
    try:
        serial = float(raw["InvoiceDate"])
        if not math.isfinite(serial):
            return None, None, "invalid_date"
        stamp = datetime(1899, 12, 30) + timedelta(days=serial)
        date = stamp.strftime("%Y-%m-%d")
    except (ValueError, OverflowError, KeyError):
        return None, None, "invalid_date"
    if date[:7] != month:
        return date, None, "outside_declared_month"
    invoice, country = raw["InvoiceNo"].strip(), raw["Country"].strip()
    if invoice.upper().startswith("C"):
        return date, None, "cancellation_invoice"
    if (not invoice or not country or len(country) > 64 or country.startswith("__")
            or any(ord(c) < 32 for c in country)):
        return date, None, "invalid_identifier_or_country"
    try:
        q, p = float(raw["Quantity"]), float(raw["UnitPrice"])
        if not math.isfinite(q) or not q.is_integer() or q <= 0:
            return date, None, "nonpositive_or_noninteger_quantity"
        if not math.isfinite(p) or p <= 0:
            return date, None, "nonpositive_or_invalid_price"
        quantity = int(q)
        if quantity > MAX_QUANTITY:
            return date, None, "quantity_bound"
        price = str(p)
        amount = Decimal(price) * quantity * 100
        if amount != amount.to_integral_value():
            return date, None, "fractional_line_pence"
        gross = int(amount)
        if not 0 < gross <= MAX_LINE_PENCE:
            return date, None, "amount_bound"
    except (ValueError, OverflowError, KeyError):
        return date, None, "invalid_numeric_cell"
    return date, {
        "order_id": f"uci:{invoice}:row:{source_row}", "region": country,
        "currency": "GBP", "gross_cents": gross, "quantity": quantity,
        "unit_price_gbp": price, "unit_price_raw_xml": raw["UnitPrice"],
        "quantity_raw_xml": raw["Quantity"], "source_row": source_row,
        "invoice_no": invoice, "stock_code": raw["StockCode"],
        "invoice_date": stamp.replace(microsecond=0).isoformat(),
    }, "eligible"

def select_dates(workbook: Path, split: str) -> tuple[dict[str, list[dict]], dict]:
    if split not in MONTHS:
        raise ValueError("split must be dev or test")
    by_date, counts = defaultdict(list), defaultdict(Counter)
    invalid_dates = 0
    for source_row, raw in iter_source_rows(workbook):
        date, row, reason = normalize_row(source_row, raw, MONTHS[split])
        if date is None:
            invalid_dates += 1
        elif date[:7] == MONTHS[split]:
            counts[date][reason] += 1
        if row is not None:
            by_date[date].append(row)
    required = DATES_PER_SPLIT[split]
    selected = sorted(by_date)[:required]
    if len(selected) != required:
        raise ValueError("Declared month has too few eligible dates")
    rows = {d: sorted(by_date[d], key=lambda r: r["source_row"]) for d in selected}
    for date, values in rows.items():
        if "United Kingdom" not in {r["region"] for r in values}:
            raise ValueError(f"No UK transactions on preregistered date {date}")
        if sum(r["gross_cents"] for r in values) > MAX_SQLITE_INTEGER:
            raise ValueError(f"SQLite aggregate bound exceeded on {date}")
    invoice_dates = defaultdict(set)
    for date, values in rows.items():
        for row in values:
            invoice_dates[row["invoice_no"]].add(date)
    return rows, {
        "selected_dates": selected,
        "selection": f"All eligible rows in first {required} distinct nonempty dates; no row sampling",
        "all_date_exclusive_counts": {d: dict(c) for d, c in sorted(counts.items())},
        "workbook_invalid_dates": invalid_dates,
        "selected_rows": sum(map(len, rows.values())),
        "selected_invoices": len(invoice_dates),
        "cross_date_invoice_ids": sorted(k for k, v in invoice_dates.items() if len(v) > 1),
        "countries_by_date": {d: sorted({r["region"] for r in rs}) for d, rs in rows.items()},
    }

def _section(key: str, label: str, port: str, path: list[str]) -> dict:
    return {"key": key, "label": label, "input": port, "path": path, "unit": "USD cents"}

def recipe_definitions(dates: tuple[str, ...]) -> list[RetailRecipe]:
    recipes = []
    for d in dates:
        for name, tool, inputs, description in [
            ("gross", "gross_by_region", {"orders": f"source:{d}:orders"}, "Eligible positive gross sales by country in GBP"),
            ("refunds", "refunds_by_region", {"orders": f"source:{d}:orders", "refunds": f"source:{d}:refunds"}, "Authored refunds by country in GBP, initially empty"),
            ("net", "net_by_region", {"gross": f"{d}:gross", "refunds": f"{d}:refunds"}, "Eligible gross sales less authored refunds by country in GBP"),
            ("gross_usd", "convert_to_usd", {"net": f"{d}:gross", "fx": f"source:{d}:fx"}, "Gross sales in USD, independent of the net branch"),
            ("net_usd", "convert_to_usd", {"net": f"{d}:net", "fx": f"source:{d}:fx"}, "Sales less authored refunds in USD"),
            ("gross_total", "company_total", {"regional": f"{d}:gross_usd"}, "All-country total eligible gross sales in USD"),
            ("net_total", "company_total", {"regional": f"{d}:net_usd"}, "All-country total sales less authored refunds in USD"),
        ]:
            recipes.append(RetailRecipe(f"{d}:{name}", tool, inputs,
                                        description=f"{description}; {d}.", run=f"snapshot-{d}"))
        recipes.append(RetailRecipe(f"{d}:daily_close", "compose_report",
            {"gross": f"{d}:gross_total", "net": f"{d}:net_total"},
            {"title": f"Daily eligible-sales close for {d}", "sections": [
                _section("gross", "Eligible gross sales", "gross", ["usd_cents"]),
                _section("net", "Eligible sales less authored refunds", "net", ["usd_cents"])]},
            f"Daily gross and net totals for every eligible transaction on {d}.", f"close-{d}"))
        recipes.append(RetailRecipe(f"{d}:uk_brief", "compose_report",
            {"gross": f"{d}:gross_usd", "net": f"{d}:net_usd"},
            {"title": f"UK home-market sales for {d}", "sections": [
                _section("gross", "UK eligible gross sales", "gross", ["regions", "United Kingdom", "usd_cents"]),
                _section("net", "UK sales less authored refunds", "net", ["regions", "United Kingdom", "usd_cents"])]},
            f"UK-specific gross and net sales on {d}, reusing the dated monetary calculations.", f"uk-{d}"))
    for prior, current in zip(dates, dates[1:]):
        recipes.append(RetailRecipe(f"cross:{prior}:{current}:daily_brief", "compose_report",
            {"previous_net": f"{prior}:net_total", "current_gross": f"{current}:gross_total",
             "current_uk_net": f"{current}:net_usd"},
            {"title": f"Sales comparison for {prior} and {current}", "sections": [
                _section("previous_net", f"{prior} eligible net sales", "previous_net", ["usd_cents"]),
                _section("current_gross", f"{current} eligible gross sales", "current_gross", ["usd_cents"]),
                _section("current_uk_net", f"{current} UK net sales", "current_uk_net", ["regions", "United Kingdom", "usd_cents"])]},
            "Three stated sales values reused from two distinct dated runs; not a computed difference.",
            f"comparison-{prior}-{current}"))
    return recipes


def case_definitions(rows: dict[str, list[dict]], split: str) -> list[RetailCase]:
    dates = tuple(sorted(rows))

    def quantity(date, delta=1):
        row = next((r for r in rows[date]
                    if Decimal(r["unit_price_gbp"]) * 100 == (Decimal(r["unit_price_gbp"]) * 100).to_integral_value()
                    and r["quantity"] + delta <= MAX_QUANTITY
                    and r["gross_cents"] + int(Decimal(r["unit_price_gbp"]) * 100) * delta <= MAX_LINE_PENCE), None)
        if row is None:
            raise ValueError("No valid preregistered exact-pence quantity target; do not substitute a date")
        new_amount = row["gross_cents"] + int(Decimal(row["unit_price_gbp"]) * 100) * delta
        return RetailMutation(f"{date}:orders", "quantity_delta", {
            "order_id": row["order_id"], "unit_price_gbp": row["unit_price_gbp"],
            "delta_quantity": delta, "raw_quantity": row["quantity"],
            "new_quantity": row["quantity"] + delta,
            "old_gross_cents": row["gross_cents"], "new_gross_cents": new_amount})

    def refund(date):
        row = rows[date][0]
        return RetailMutation(f"{date}:refunds", "refund_add", {
            "order_id": row["order_id"], "refund_cents": max(1, row["gross_cents"] // 10)})

    def fx(date, rate):
        return RetailMutation(f"{date}:fx", "fx_set", {"GBP": rate})

    def case(case_id, description, mutations, category):
        return RetailCase(case_id, split, description, tuple(mutations), category, dates)

    if split == "dev":
        a, b = dates
        return [
            case("MD01", f"An order quantity and the illustrative FX rate were corrected on {a}. Refresh affected saved reports and retain reusable evidence.",
                 [quantity(a, 2), fx(a, "1.28")], "joint_source"),
            case("MD02", f"The FX source for {b} is unavailable. Serve current evidence and identify saved reports that cannot be safely refreshed.",
                 [RetailMutation(f"{b}:fx", "remove")], "missing_source"),
        ]
    a, b, c, d = dates
    pair = next(((x, y) for i, x in enumerate(rows[b]) for y in rows[b][i + 1:]
                 if x["region"] == y["region"] and 3 < x["gross_cents"] <= MAX_LINE_PENCE - 3
                 and y["gross_cents"] > 3), None)
    if pair is None:
        raise ValueError("No valid same-country offset pair; do not substitute a date")
    return [
        case("M01", f"A partial refund was recorded for one {b} order. Refresh affected saved reports and retain reusable evidence.",
             [refund(b)], "local_refund"),
        case("M02", f"The illustrative GBP/USD rate for {a} was corrected from 1.25 to 1.29. Refresh affected saved reports.",
             [fx(a, "1.29")], "local_fx"),
        case("M03", f"An order quantity and the illustrative FX rate were corrected on {c}. Refresh affected saved reports and retain reusable evidence.",
             [quantity(c, 2), fx(c, "1.28")], "joint_source"),
        case("M04", f"A partial refund on {a} and an order quantity on {d} were corrected. Refresh affected saved reports across the saved runs.",
             [refund(a), quantity(d)], "multiple_dates"),
        case("M05", "The global conversion tool version changed. Reassess saved evidence before reusing the affected reports.",
             [RetailMutation(operation="tool_version", tool="convert_to_usd",
                 parameters={"version": "model-v4-convert-2"})], "global_tool_version"),
        case("M06", f"Two line-total corrections on {b} preserve that country's aggregate sales value. Reassess saved evidence validity and refresh affected reports.",
             [RetailMutation(f"{b}:orders", "offset_gross", {
                 "first": pair[0]["order_id"], "second": pair[1]["order_id"], "delta_cents": 3,
                 "first_old_gross_cents": pair[0]["gross_cents"], "second_old_gross_cents": pair[1]["gross_cents"]})],
             "same_value_revalidation"),
        case("M07", f"The FX source for {c} is unavailable. Serve current evidence and identify saved reports that cannot be safely refreshed.",
             [RetailMutation(f"{c}:fx", "remove")], "missing_source"),
        case("M08", "All four daily order sources were republished with reordered rows. Determine whether any saved evidence needs refreshing.",
             [RetailMutation(f"{date}:orders", "reorder") for date in dates], "canonical_noop"),
    ]


def mutate_value(value: Any, mutation: RetailMutation) -> Any:
    """Apply a frozen data patch; no dependency inference or scoring."""
    if mutation.operation == "remove":
        return None
    result, p = deepcopy(value), mutation.parameters
    if mutation.operation == "quantity_delta":
        amount = Decimal(p["unit_price_gbp"]) * p["delta_quantity"] * 100
        if amount != amount.to_integral_value():
            raise ValueError("Quantity correction has fractional pence")
        row = next(r for r in result if r["order_id"] == p["order_id"])
        if row["gross_cents"] != p["old_gross_cents"]:
            raise ValueError("Quantity patch before-value mismatch")
        row["gross_cents"] += int(amount)
        if row["gross_cents"] != p["new_gross_cents"]:
            raise ValueError("Quantity patch after-value mismatch")
    elif mutation.operation == "refund_add":
        result.append(dict(p))
    elif mutation.operation == "fx_set":
        result.update(p)
    elif mutation.operation == "offset_gross":
        first = next(r for r in result if r["order_id"] == p["first"])
        second = next(r for r in result if r["order_id"] == p["second"])
        if (first["gross_cents"], second["gross_cents"]) != (p["first_old_gross_cents"], p["second_old_gross_cents"]):
            raise ValueError("Offset patch before-values mismatch")
        first["gross_cents"] += p["delta_cents"]
        second["gross_cents"] -= p["delta_cents"]
    elif mutation.operation == "reorder":
        result.reverse()
    else:
        raise ValueError(f"Unsupported v4 source mutation: {mutation.operation}")
    if isinstance(result, list):
        result.sort(key=lambda r: r["order_id"])
    return result


def patch_audit(sources: dict[str, Any], cases: list[RetailCase]) -> dict:
    """Freeze concrete changed values/hashes alongside declarations, not scores."""
    output = {}
    for case in cases:
        current, patches = deepcopy(sources), []
        for mutation in case.mutations:
            if mutation.operation == "tool_version":
                patches.append({"tool": mutation.tool, "old_declared_version": "1",
                                "new_declared_version": mutation.parameters["version"]})
                continue
            before = current[mutation.source]
            after = mutate_value(before, mutation)
            record = {"source": mutation.source, "operation": mutation.operation,
                      "before_sha256": hashlib.sha256(canonical(before).encode()).hexdigest(),
                      "after_sha256": hashlib.sha256(canonical(after).encode()).hexdigest(),
                      "semantic_change": before != after}
            if isinstance(before, list) and isinstance(after, list):
                old, new = {r["order_id"]: r for r in before}, {r["order_id"]: r for r in after}
                record["changed_rows"] = [{"order_id": key, "before": old.get(key), "after": new.get(key)}
                                          for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)]
            else:
                record.update(before=before, after=after)
            patches.append(record)
            current[mutation.source] = after
        output[case.id] = patches
    return output


def manifest_data(split: str = "dev") -> dict[str, Any]:
    if split not in MONTHS:
        raise ValueError("split must be dev or test")
    return json.loads((FIXTURE_DIR / split / "fixture.json").read_text())


def fixture_sources(split: str = "dev") -> dict[str, Any]:
    return deepcopy(manifest_data(split)["sources"])


def recipes(split: str = "dev") -> list[RetailRecipe]:
    return [RetailRecipe(**r) for r in manifest_data(split)["recipes"]]


def scenarios(split: str = "dev") -> list[RetailCase]:
    return [RetailCase(**{**c, "mutations": tuple(RetailMutation(**m) for m in c["mutations"]),
                         "scope_partitions": tuple(c["scope_partitions"])})
            for c in manifest_data(split)["cases"]]


def candidate_names(case: RetailCase, declarations: list[RetailRecipe]) -> set[str]:
    return {r.name for r in declarations}


def fixture_file_hashes(split: str = "dev") -> list[dict[str, str]]:
    return [{"path": str(p.relative_to(ROOT)), "sha256": sha_file(p)}
            for p in sorted((FIXTURE_DIR / split).iterdir()) if p.is_file()]


def prepare_fixture(workbook: Path, split: str, destination: Path | None = None) -> dict:
    target = destination or FIXTURE_DIR / split
    if target.exists() and any(target.iterdir()):
        raise ValueError("Refusing to overwrite an existing model-comparison fixture")
    rows, profile = select_dates(workbook, split)
    dates = tuple(rows)
    declarations, cases = recipe_definitions(dates), case_definitions(rows, split)
    n = DATES_PER_SPLIT[split]
    if len(declarations) != 10 * n - 1 or sum(r.tool == "compose_report" for r in declarations) != 3 * n - 1:
        raise AssertionError("Declared reporting-pack size changed")
    target.mkdir(parents=True, exist_ok=True)
    sources, files = {}, {}
    for date, values in rows.items():
        orders = sorted(({k: r[k] for k in ("order_id", "region", "currency", "gross_cents")}
                         for r in values), key=lambda r: r["order_id"])
        sources.update({f"{date}:orders": orders, f"{date}:refunds": [],
                        f"{date}:fx": {"GBP": "1.25", "USD": "1"}})
        csv_path, provenance = target / f"{date}.csv", target / f"{date}.provenance.json"
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["order_id", "region", "currency", "gross_cents"])
            writer.writeheader()
            writer.writerows(orders)
        provenance.write_text(json.dumps(values, indent=2, ensure_ascii=False) + "\n")
        files[date] = {"csv": csv_path.name, "csv_sha256": sha_file(csv_path),
                       "provenance": provenance.name, "provenance_sha256": sha_file(provenance),
                       "rows": len(orders)}
    fixture = {
        "version": VERSION, "split": split, "month": MONTHS[split], "dates": list(dates),
        "source": {"page": SOURCE_PAGE, "download": SOURCE_URL, "xlsx_sha256": XLSX_SHA256,
                   "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33",
                   "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"},
        "numeric_policy": "finite IEEE binary64 -> shortest round-trip decimal string -> exact Decimal line pence; no monetary rounding",
        "bounds": {"quantity": MAX_QUANTITY, "line_pence": MAX_LINE_PENCE,
                   "table_total_pence": MAX_SQLITE_INTEGER, "country_max_characters": 64},
        "profile": profile, "files": files, "sources": sources,
        "recipes": [asdict(r) for r in declarations], "cases": [asdict(c) for c in cases],
        "queries_by_case": {c.id: c.description for c in cases},
        "concrete_patch_audit": patch_audit(sources, cases),
        "scope": "Complete eligible positive rows within selected dates; staged refunds/FX/corrections; not complete merchant accounts or observed historical errors",
        "representation": "Original full retail-v2 receipt representation; no compact encoding",
        "candidate_scope": "All declared artifacts; not an oracle affected subset",
    }
    (target / "fixture.json").write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
    (target / "DATASET_NOTICE.md").write_text(
        "# Dataset attribution\n\nChen, D. (2015), Online Retail, UCI Machine Learning Repository, "
        "https://doi.org/10.24432/C5BW33, licensed CC BY 4.0: https://creativecommons.org/licenses/by/4.0/.\n\n"
        "All eligible positive transaction lines on the declared dates are retained. Numeric spreadsheet cells "
        "follow the fixture's explicit normalization policy; line totals are exact integer GBP pence. "
        "Cancellations and invalid/bounded-out rows are excluded. CustomerID/product descriptions are omitted; "
        "original row identities and numeric XML provenance remain. Refunds, FX rates and corrections are "
        "authored evaluation inputs, not observed historical errors. This is not a complete merchant ledger. "
        "No original dataset endorsement is implied.\n")
    return fixture
