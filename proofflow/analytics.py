"""Small deterministic analytics tools with explicit, inspectable inputs.

The functions in this module do not discover data or read files. The runtime
supplies all consumed source/artifact values, which lets it record complete
lineage for this supported tool set. Source aggregations execute actual SQLite
queries; monetary calculations use integer cents and Decimal exchange rates.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import math
import sqlite3
from typing import Any, Iterator


class AnalyticsError(ValueError):
    """The supplied data or tool arguments are invalid."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    description: str
    input_names: tuple[str, ...]


TOOL_SPECS: dict[str, ToolSpec] = {
    "gross_by_region": ToolSpec(
        "gross_by_region", "1", "Sum order amounts by region and currency.", ("orders",)
    ),
    "refunds_by_region": ToolSpec(
        "refunds_by_region", "1", "Join refunds to orders and sum refunded amounts by region.",
        ("orders", "refunds"),
    ),
    "net_by_region": ToolSpec(
        "net_by_region", "1", "Subtract regional refunds from gross revenue.", ("gross", "refunds")
    ),
    "convert_to_usd": ToolSpec(
        "convert_to_usd", "1", "Convert net regional amounts to USD cents using explicit rates.",
        ("net", "fx"),
    ),
    "company_total": ToolSpec(
        "company_total", "1", "Sum USD regional revenue into company revenue.", ("regional",)
    ),
    "support_by_region": ToolSpec(
        "support_by_region", "1", "Count support tickets by region.", ("tickets",)
    ),
    "compose_report": ToolSpec(
        "compose_report", "1", "Compose structured numeric claims from explicit artifact inputs.", ()
    ),
}


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise AnalyticsError(f"{where} must be an object with string keys")
    return value


def _rows(value: Any, where: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AnalyticsError(f"{where} must be a list of records")
    return [_mapping(row, f"{where}[{index}]") for index, row in enumerate(value)]


def _text(value: Any, where: str, *, limit: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise AnalyticsError(f"{where} must be a nonempty string of at most {limit} characters")
    return value


def _integer(value: Any, where: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int or not -(2**63) <= value < 2**63:
        raise AnalyticsError(f"{where} must be a signed 64-bit integer")
    if nonnegative and value < 0:
        raise AnalyticsError(f"{where} must be nonnegative")
    return value


def _currency(value: Any, where: str) -> str:
    currency = _text(value, where, limit=3)
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise AnalyticsError(f"{where} must be a three-letter uppercase currency")
    return currency


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(":memory:")
    try:
        yield db
    except (sqlite3.Error, OverflowError) as error:
        raise AnalyticsError(f"Analytics query failed: {error}") from error
    finally:
        db.close()


def _load_orders(db: sqlite3.Connection, value: Any) -> None:
    db.execute(
        "CREATE TABLE orders (order_id TEXT PRIMARY KEY, region TEXT NOT NULL, "
        "currency TEXT NOT NULL, gross_cents INTEGER NOT NULL)"
    )
    records = []
    for index, row in enumerate(_rows(value, "orders")):
        records.append((
            _text(row.get("order_id"), f"orders[{index}].order_id"),
            _text(row.get("region"), f"orders[{index}].region", limit=64),
            _currency(row.get("currency"), f"orders[{index}].currency"),
            _integer(row.get("gross_cents"), f"orders[{index}].gross_cents", nonnegative=True),
        ))
    db.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", records)
    mixed = db.execute(
        "SELECT region FROM orders GROUP BY region HAVING COUNT(DISTINCT currency) > 1 LIMIT 1"
    ).fetchone()
    if mixed:
        raise AnalyticsError(f"Region {mixed[0]!r} contains more than one currency")


def _grouped_rows(rows: list[tuple[str, str, int]]) -> dict[str, Any]:
    return {"regions": {
        region: {"currency": currency, "amount_cents": int(amount)}
        for region, currency, amount in rows
    }}


def _gross_by_region(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    with _database() as db:
        _load_orders(db, inputs["orders"])
        rows = db.execute(
            "SELECT region, currency, SUM(gross_cents) FROM orders "
            "GROUP BY region, currency ORDER BY region"
        ).fetchall()
    return _grouped_rows(rows)


def _refunds_by_region(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    with _database() as db:
        _load_orders(db, inputs["orders"])
        db.execute("CREATE TABLE refunds (order_id TEXT NOT NULL, refund_cents INTEGER NOT NULL)")
        rows = []
        for index, row in enumerate(_rows(inputs["refunds"], "refunds")):
            rows.append((
                _text(row.get("order_id"), f"refunds[{index}].order_id"),
                _integer(row.get("refund_cents"), f"refunds[{index}].refund_cents", nonnegative=True),
            ))
        db.executemany("INSERT INTO refunds VALUES (?, ?)", rows)
        unmatched = db.execute(
            "SELECT refunds.order_id FROM refunds LEFT JOIN orders USING (order_id) "
            "WHERE orders.order_id IS NULL LIMIT 1"
        ).fetchone()
        if unmatched:
            raise AnalyticsError(f"Refund references unknown order {unmatched[0]!r}")
        sums = db.execute(
            "SELECT orders.region, orders.currency, SUM(refunds.refund_cents) "
            "FROM refunds JOIN orders USING (order_id) "
            "GROUP BY orders.region, orders.currency ORDER BY orders.region"
        ).fetchall()
    return _grouped_rows(sums)


def _money_regions(value: Any, where: str) -> dict[str, dict[str, Any]]:
    raw = _mapping(_mapping(value, where).get("regions"), f"{where}.regions")
    regions = {}
    for region, item in raw.items():
        _text(region, f"{where} region", limit=64)
        row = _mapping(item, f"{where}.{region}")
        regions[region] = {
            "currency": _currency(row.get("currency"), f"{where}.{region}.currency"),
            "amount_cents": _integer(row.get("amount_cents"), f"{where}.{region}.amount_cents"),
        }
    return regions


def _net_by_region(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    gross = _money_regions(inputs["gross"], "gross")
    refunds = _money_regions(inputs["refunds"], "refunds")
    unknown = set(refunds) - set(gross)
    if unknown:
        raise AnalyticsError(f"Refund totals refer to unknown gross regions: {sorted(unknown)}")
    result = {}
    for region, amount in sorted(gross.items()):
        refund = refunds.get(region, {"currency": amount["currency"], "amount_cents": 0})
        if refund["currency"] != amount["currency"]:
            raise AnalyticsError(f"Gross/refund currency mismatch for region {region!r}")
        net = _integer(amount["amount_cents"] - refund["amount_cents"], f"net.{region}")
        result[region] = {"currency": amount["currency"], "amount_cents": net}
    return {"regions": result}


def _convert_to_usd(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    net = _money_regions(inputs["net"], "net")
    fx = _mapping(inputs["fx"], "fx")
    result = {}
    for region, amount in sorted(net.items()):
        currency = amount["currency"]
        value = fx.get(currency)
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise AnalyticsError(f"Missing or invalid exchange rate for {currency}")
        try:
            rate = Decimal(str(value))
            if not rate.is_finite() or rate <= 0:
                raise AnalyticsError(f"Exchange rate for {currency} must be finite and positive")
            # Never inherit a caller's process-wide decimal precision. The
            # supported output is int64 cents; fifty digits comfortably cover
            # its arithmetic and fail closed on unreasonable input magnitudes.
            with localcontext() as context:
                context.prec = 50
                converted = int((Decimal(amount["amount_cents"]) * rate).quantize(
                    Decimal("1"), rounding=ROUND_HALF_EVEN
                ))
        except (InvalidOperation, OverflowError, ValueError) as error:
            if isinstance(error, AnalyticsError):
                raise
            raise AnalyticsError(f"Invalid exchange rate for {currency}") from error
        result[region] = {"usd_cents": _integer(converted, f"converted.{region}")}
    return {"regions": result}


def _company_total(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    raw = _mapping(_mapping(inputs["regional"], "regional").get("regions"), "regional.regions")
    total = 0
    for region, item in sorted(raw.items()):
        row = _mapping(item, f"regional.{region}")
        total += _integer(row.get("usd_cents"), f"regional.{region}.usd_cents")
    return {"usd_cents": _integer(total, "company_total")}


def _support_by_region(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    with _database() as db:
        db.execute("CREATE TABLE tickets (ticket_id TEXT PRIMARY KEY, region TEXT, status TEXT)")
        records = []
        for index, row in enumerate(_rows(inputs["tickets"], "tickets")):
            records.append((
                _text(row.get("ticket_id"), f"tickets[{index}].ticket_id"),
                _text(row.get("region"), f"tickets[{index}].region", limit=64),
                _text(row.get("status"), f"tickets[{index}].status", limit=64),
            ))
        db.executemany("INSERT INTO tickets VALUES (?, ?, ?)", records)
        rows = db.execute("SELECT region, COUNT(*) FROM tickets GROUP BY region ORDER BY region").fetchall()
    return {"regions": {region: {"tickets": count} for region, count in rows}}


def _compose_report(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    title = _text(params.get("title"), "report title", limit=300)
    sections = _rows(params.get("sections"), "sections")
    if not sections:
        raise AnalyticsError("A report requires at least one section")
    output = []
    keys = set()
    for index, section in enumerate(sections):
        key = _text(section.get("key"), f"sections[{index}].key", limit=80)
        if key in keys:
            raise AnalyticsError(f"Duplicate report section key {key!r}")
        keys.add(key)
        label = _text(section.get("label"), f"sections[{index}].label", limit=300)
        unit = _text(section.get("unit"), f"sections[{index}].unit", limit=80)
        input_name = _text(section.get("input"), f"sections[{index}].input", limit=100)
        if input_name not in inputs:
            raise AnalyticsError(f"Unknown report input {input_name!r}")
        path = section.get("path")
        if not isinstance(path, list) or not path or len(path) > 16:
            raise AnalyticsError(f"sections[{index}].path must contain 1–16 object keys")
        value = inputs[input_name]
        for part in path:
            if not isinstance(part, str) or not part or part.startswith("__") or "\x00" in part:
                raise AnalyticsError(f"Invalid report path key {part!r}")
            if not isinstance(value, dict) or part not in value:
                raise AnalyticsError(f"Report path {path!r} does not exist in {input_name!r}")
            value = value[part]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AnalyticsError("Report claims must select a numeric value")
        if isinstance(value, float) and not math.isfinite(value):
            raise AnalyticsError("Report claims must be finite")
        output.append({"key": key, "label": label, "value": value, "unit": unit})
    return {"title": title, "sections": output}


_IMPLEMENTATIONS = {
    "gross_by_region": _gross_by_region,
    "refunds_by_region": _refunds_by_region,
    "net_by_region": _net_by_region,
    "convert_to_usd": _convert_to_usd,
    "company_total": _company_total,
    "support_by_region": _support_by_region,
    "compose_report": _compose_report,
}


def execute_tool(name: str, inputs: dict[str, Any], params: dict[str, Any] | None = None) -> Any:
    """Execute one registered tool; all data and dependencies are explicit.

    Runtime callers are responsible for resolving artifact handles and recording
    consumed versions. Extra named inputs are refused for calculation tools so
    accidental or irrelevant bindings cannot silently alter the receipt.
    """
    if name not in TOOL_SPECS:
        raise AnalyticsError(f"Unknown tool {name!r}")
    inputs = _mapping(inputs, "inputs")
    params = _mapping({} if params is None else params, "params")
    if name != "compose_report":
        expected = set(TOOL_SPECS[name].input_names)
        if set(inputs) != expected:
            raise AnalyticsError(
                f"{name} requires exactly inputs {sorted(expected)}, got {sorted(inputs)}"
            )
        if params:
            raise AnalyticsError(f"{name} does not accept parameters")
    elif set(params) != {"title", "sections"}:
        raise AnalyticsError("compose_report requires exactly title and sections parameters")
    return _IMPLEMENTATIONS[name](inputs, params)


DEMO_SOURCES: dict[str, Any] = {
    "orders": [
        {"order_id": "eu-101", "region": "EU", "currency": "EUR", "gross_cents": 120000},
        {"order_id": "eu-102", "region": "EU", "currency": "EUR", "gross_cents": 80000},
        {"order_id": "us-201", "region": "US", "currency": "USD", "gross_cents": 180000},
        {"order_id": "us-202", "region": "US", "currency": "USD", "gross_cents": 60000},
        {"order_id": "uk-301", "region": "UK", "currency": "GBP", "gross_cents": 90000},
    ],
    "refunds": [
        {"order_id": "eu-101", "refund_cents": 10000},
        {"order_id": "us-202", "refund_cents": 5000},
    ],
    "fx": {"EUR": "1.10", "USD": "1.00", "GBP": "1.25"},
    "tickets": [
        {"ticket_id": "t-1", "region": "EU", "status": "open"},
        {"ticket_id": "t-2", "region": "EU", "status": "closed"},
        {"ticket_id": "t-3", "region": "US", "status": "open"},
        {"ticket_id": "t-4", "region": "UK", "status": "closed"},
    ],
}
