"""Independent arithmetic audit for the fresh multi-country study.

Only the Python standard library is used. Original sanitized worksheet cells,
not the imported gross_cents column, determine the expected values. Call this
on study data only after the prospective selection rules have been frozen.
Refund and support observations are absent; empty maps represent the agreed
zero defaults, not evidence that no refunds or support activity occurred.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import io
from pathlib import Path
import re
from typing import Mapping


SOURCE_FIELDS = (
    "source_row", "invoice_no", "invoice_date_raw_xml", "quantity_raw_xml",
    "unit_price_raw_xml", "country",
)
ORDER_FIELDS = ("order_id", "region", "currency", "gross_cents")
DEFAULT_RATES = {"initial": "1.25", "fx-correction": "1.30"}
FX_OUTPUTS = ("regional", "company", "company_report", "region_report")


class OracleError(ValueError):
    """The uploaded bytes or provenance do not meet the frozen input contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def _read_csv(path: Path, fields: tuple[str, ...]) -> tuple[bytes, list[dict[str, str]]]:
    payload = path.read_bytes()
    require(0 < len(payload) <= 1024 * 1024, f"{path.name}: byte bound")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8"), newline=""), strict=True)
        require(tuple(next(reader, [])) == fields, f"{path.name}: exact header required")
        rows = []
        for cells in reader:
            require(len(cells) == len(fields), f"{path.name}: row shape")
            require(all(cell != "" for cell in cells), f"{path.name}: missing value")
            rows.append(dict(zip(fields, cells)))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise OracleError(f"{path.name}: malformed CSV") from exc
    require(0 < len(rows) <= 1000, f"{path.name}: row bound")
    return payload, rows


def _positive_integer(text: str, label: str, maximum: int) -> int:
    # Canonical unsigned decimal excludes a textual negative zero and leading zeros.
    require(bool(re.fullmatch(r"[1-9][0-9]*", text)), f"{label}: positive canonical integer required")
    number = int(text)
    require(number <= maximum, f"{label}: bound")
    return number


def _text(value: str, limit: int, label: str) -> None:
    require(bool(value) and value == value.strip() and len(value) <= limit and value.isprintable(),
            f"{label}: invalid identifier")


def _source_line(row: dict[str, str]) -> tuple[int, str, str, int, str]:
    index = _positive_integer(row["source_row"], "source_row", 1_048_576)
    require(index >= 2, "source_row: header is not a transaction")
    invoice, country = row["invoice_no"], row["country"]
    identifier = f"uci:{invoice}:row:{index}"
    _text(identifier, 200, "order_id")
    _text(invoice, 200, "invoice_no")
    _text(country, 64, "country")
    require(not invoice.upper().startswith("C") and not country.startswith("__"),
            "source: cancellation or reserved country")
    try:
        units = Decimal(repr(float(row["quantity_raw_xml"])))
        # The extraction contract decodes numeric Excel cells as binary64,
        # then uses its shortest round-trip decimal spelling before arithmetic.
        price = Decimal(repr(float(row["unit_price_raw_xml"])))
        serial = Decimal(row["invoice_date_raw_xml"])
        require(units.is_finite() and units == units.to_integral_value()
                and 0 < units <= 10**9, "source: invalid quantity")
        require(price.is_finite() and price > 0, "source: invalid price")
        require(serial.is_finite() and 1 <= serial < 2_958_466, "source: invalid date")
        day = (date(1899, 12, 30) + timedelta(days=int(serial))).isoformat()
        with localcontext() as context:
            context.prec = 60
            pence = units * price * 100
        require(pence == pence.to_integral_value() and 0 < pence <= 10**12,
                "source: nonintegral or out-of-bounds line pence")
    except (InvalidOperation, ValueError, OverflowError) as exc:
        if isinstance(exc, OracleError):
            raise
        raise OracleError("source: invalid numeric cell") from exc
    return index, identifier, country, int(pence), day


def audit_fixture(fixture_dir: Path | str, selected_region: str) -> dict:
    """Reconcile every upload row to the original sanitized numeric cells."""
    directory = Path(fixture_dir)
    original_bytes, originals = _read_csv(directory / "source_cells.csv", SOURCE_FIELDS)
    order_bytes, orders = _read_csv(directory / "orders.csv", ORDER_FIELDS)
    require(len(originals) == len(orders), "source and upload row counts differ")
    previous_index = 1
    invoice_ids, countries, days, gross = set(), Counter(), set(), Counter()
    for source, order in zip(originals, orders, strict=True):
        index, identifier, country, line_pence, day = _source_line(source)
        require(index > previous_index, "source rows must be unique and in worksheet order")
        previous_index = index
        uploaded_pence = _positive_integer(order["gross_cents"], "gross_cents", 10**12)
        require((order["order_id"], order["region"], order["currency"], uploaded_pence)
                == (identifier, country, "GBP", line_pence),
                "upload line differs from original worksheet cells")
        gross[country] += line_pence
        countries[country] += 1
        days.add(day)
        invoice_ids.add(source["invoice_no"])
    require(len(days) == 1, "fixture must contain exactly one original calendar date")
    require(selected_region in gross, "selected region absent")
    return {
        "rows": len(originals), "invoices": len(invoice_ids), "selected_date": next(iter(days)),
        "selected_region": selected_region, "rows_by_region": dict(sorted(countries.items())),
        "gross_gbp_cents_by_region": dict(sorted(gross.items())),
        "region_currencies": {country: "GBP" for country in sorted(countries)},
        "missing_observations": ["refund_cents", "ticket_count"],
        "missing_observation_policy": "Omitted fields use zero defaults; zero activity is not observed.",
        "files": {
            "orders.csv": {"bytes": len(order_bytes), "sha256": hashlib.sha256(order_bytes).hexdigest()},
            "source_cells.csv": {"bytes": len(original_bytes), "sha256": hashlib.sha256(original_bytes).hexdigest()},
        },
    }


def _rate(text: str) -> Decimal:
    require(isinstance(text, str) and bool(re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]{1,12})?", text)),
            "rate: unsigned decimal string required")
    result = Decimal(text)
    require(0 < result <= 1000, "rate: positive value within bounds required")
    return result


def build_cases(fixture_dir: Path | str, selected_region: str,
                rates: Mapping[str, str] | None = None) -> list[dict]:
    """Return initial and FX-corrected cases for the existing paired runner.

    Sum native pence by country, round each country's converted amount to even
    once, then sum the integer USD cents. The oracle never reads app outputs.
    """
    stage_rates = dict(DEFAULT_RATES if rates is None else rates)
    require(set(stage_rates) == set(DEFAULT_RATES), "exact initial and fx-correction stages required")
    audit = audit_fixture(fixture_dir, selected_region)
    gross = audit["gross_gbp_cents_by_region"]
    cases = []
    for phase in DEFAULT_RATES:
        rate = _rate(stage_rates[phase])
        with localcontext() as context:
            context.prec = 60
            # int() produces a canonical integer zero, never a signed -0 value.
            regional = {country: int((Decimal(pence) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
                        for country, pence in gross.items()}
        company = sum(regional.values())
        cases.append({
            "id": phase, "csv": "orders.csv", "rates": {"GBP": stage_rates[phase]},
            "changed_source": None if phase == "initial" else "fx",
            "affected_outputs": [] if phase == "initial" else list(FX_OUTPUTS),
            "expected": {
                "gross": dict(gross), "refunds": {}, "net": dict(gross), "regional": regional,
                "company": company, "support": {}, "company_report": company,
                "region_report": regional[selected_region],
            },
        })
    return cases
