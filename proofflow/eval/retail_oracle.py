"""Independent monetary and impact oracles for the external retail pilot.

Only Python's standard library is used. This module does not import production
analytics, the runtime, Hydra, cached artifacts, the v1 oracle, or case factories.
It shares the explicitly declared tool contracts and rounding rules, not their
implementations. Raw UCI line amounts are independently reconstructed from the
original decimal GBP price and integral quantity before normalized orders are
trusted. Illustrative FX and staged corrections are experiment inputs, not
historical assertions about the UCI transactions.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import math
from typing import Any


class OracleContractError(ValueError):
    """A declaration/data mismatch makes the evaluation invalid."""


class OracleUnavailable(ValueError):
    """An otherwise declared calculation cannot produce a current value."""


def _integer(value: Any, name: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int or not -(2**63) <= value < 2**63 or (nonnegative and value < 0):
        raise OracleUnavailable(f"{name} must be a valid {'nonnegative ' if nonnegative else ''}int64")
    return value


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise OracleUnavailable(f"{name} requires an exact decimal string or integer")
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise OracleUnavailable(f"Invalid {name}") from error
    if not number.is_finite():
        raise OracleUnavailable(f"Non-finite {name}")
    return number


def raw_line_amount_pence(quantity: int, unit_price_gbp: str) -> int:
    """Reconstruct one eligible positive-sales line, without rounding its price.

    The predeclared subset requires the final GBP line amount to be an exact
    integer number of pence. Fractional unit pence are allowed when multiplied
    quantity yields an exact line amount. Fractional line pence are rejected,
    not silently rounded or represented as historical truth.
    """
    count = _integer(quantity, "quantity", nonnegative=True)
    if count == 0 or not isinstance(unit_price_gbp, str):
        raise OracleUnavailable("Raw line needs positive quantity and decimal GBP price text")
    price = _decimal(unit_price_gbp, "unit_price_gbp")
    if price <= 0:
        raise OracleUnavailable("Positive-sales subset requires positive GBP unit price")
    with localcontext() as context:
        context.prec = 80
        amount = Decimal(count) * price * Decimal(100)
        if amount != amount.to_integral_value():
            raise OracleUnavailable("Raw line has fractional pence and is outside the declared subset")
    return _integer(int(amount), "raw line pence", nonnegative=True)


def verify_raw_orders(raw_rows: Iterable[Mapping[str, Any]], normalized_orders: Iterable[Mapping[str, Any]]) -> None:
    """Reject any normalized order differing from independent raw-row facts.

    Raw rows must retain ``invoice_no``, ``source_row``, ``region``, ``quantity``
    and ``unit_price_gbp``. Country is a region label, never a currency guess:
    every UCI Online Retail price in this subset is GBP.
    """
    expected: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        invoice = row.get("invoice_no")
        source_row = row.get("source_row")
        region = row.get("region")
        if (not isinstance(invoice, str) or not invoice or invoice.upper().startswith("C")
                or type(source_row) is not int or source_row < 2
                or not isinstance(region, str) or not region):
            raise OracleContractError("Invalid raw invoice identity/country in positive-sales subset")
        identifier = f"uci:{invoice}:row:{source_row}"
        if identifier in expected:
            raise OracleContractError(f"Duplicate raw row identity: {identifier}")
        # Excel numeric cells are binary64. Preserve the literal XML separately
        # and verify the declared shortest-roundtrip string normalization. This
        # avoids treating serialization tails (2.5499999999999998) as an exact
        # business decimal while keeping that input-format choice auditable.
        if "unit_price_raw_xml" in row:
            raw_price = row["unit_price_raw_xml"]
            try:
                normalized_price = float(raw_price)
            except (TypeError, ValueError, OverflowError) as error:
                raise OracleContractError("Invalid retained raw XLSX price") from error
            if (not isinstance(raw_price, str) or not math.isfinite(normalized_price)
                    or str(normalized_price) != row["unit_price_gbp"]):
                raise OracleContractError("Declared GBP price differs from raw XLSX binary64 normalization")
        if "quantity_raw_xml" in row:
            raw_quantity = _decimal(row["quantity_raw_xml"], "raw XLSX quantity")
            if raw_quantity != raw_quantity.to_integral_value() or int(raw_quantity) != row["quantity"]:
                raise OracleContractError("Declared quantity differs from the raw XLSX quantity")
        expected[identifier] = {
            "order_id": identifier, "region": region, "currency": "GBP",
            "gross_cents": raw_line_amount_pence(row["quantity"], row["unit_price_gbp"]),
        }
    actual: dict[str, dict[str, Any]] = {}
    for row in normalized_orders:
        identifier = row.get("order_id")
        if not isinstance(identifier, str) or identifier in actual:
            raise OracleContractError("Invalid or duplicate normalized order identity")
        actual[identifier] = {key: row.get(key) for key in ("order_id", "region", "currency", "gross_cents")}
        _integer(actual[identifier]["gross_cents"], "normalized gross_cents", nonnegative=True)
    if actual != expected:
        raise OracleContractError("Normalized orders disagree with independent raw GBP line reconstruction")


@dataclass(frozen=True)
class _Contract:
    name: str
    tool: str
    inputs: dict[str, str]
    params: dict[str, Any]


_PORTS = {
    "gross_by_region": {"orders"},
    "refunds_by_region": {"orders", "refunds"},
    "net_by_region": {"gross", "refunds"},
    "convert_to_usd": {"net", "fx"},
    "company_total": {"regional"},
    "support_by_region": {"tickets"},
}


def _contracts(recipes: Iterable[Any]) -> list[_Contract]:
    declarations = []
    names = set()
    for item in recipes:
        def field(key: str, default: Any = None) -> Any:
            return item.get(key, default) if isinstance(item, Mapping) else getattr(item, key, default)
        name, tool, inputs, params = field("name"), field("tool"), field("inputs"), field("params", {})
        if (not isinstance(name, str) or not name or name.startswith("source:") or name in names
                or not isinstance(tool, str)
                or not isinstance(inputs, dict) or not all(isinstance(k, str) and isinstance(v, str) and v for k, v in inputs.items())
                or not isinstance(params, dict)):
            raise OracleContractError("Invalid or duplicate recipe declaration")
        if tool != "compose_report" and (tool not in _PORTS or set(inputs) != _PORTS[tool] or params):
            raise OracleContractError(f"Unsupported tool/ports/parameters: {tool}")
        if tool == "compose_report" and set(params) != {"title", "sections"}:
            raise OracleContractError("Report requires explicit title and sections")
        declarations.append(_Contract(name, tool, dict(inputs), dict(params)))
        names.add(name)
    for contract in declarations:
        for reference in contract.inputs.values():
            if not reference.startswith("source:") and reference not in names:
                raise OracleContractError(f"Unknown declared artifact input: {reference}")
    return declarations


def compute_values(recipes: Iterable[Any], sources: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Evaluate declared contracts from current inputs in independent order.

    Source keys may be bare ``<partition>:orders`` or already ``source:...``.
    Missing/None sources propagate explicit unavailable results. Unknown
    declared recipe references and cycles are evaluation-contract errors.
    """
    contracts = _contracts(recipes)
    values: dict[str, Any] = {}
    source_names = set()
    for name, value in sources.items():
        logical = name if name.startswith("source:") else f"source:{name}"
        if logical in source_names:
            raise OracleContractError(f"Duplicate logical source: {logical}")
        source_names.add(logical)
        if value is not None:
            values[logical] = value
    errors: dict[str, str] = {}
    pending = {contract.name: contract for contract in contracts}
    while pending:
        ready = [contract for contract in pending.values()
                 if not any(reference in pending for reference in contract.inputs.values())]
        if not ready:
            raise OracleContractError("Cycle in declared calculation contracts")
        for contract in sorted(ready, key=lambda item: item.name):
            missing = [reference for reference in contract.inputs.values() if reference not in values]
            if missing:
                errors[contract.name] = "Unavailable inputs: " + ", ".join(sorted(missing))
            else:
                try:
                    values[contract.name] = _calculate(contract, {port: values[reference] for port, reference in contract.inputs.items()})
                except (OracleUnavailable, KeyError, TypeError, InvalidOperation) as error:
                    errors[contract.name] = str(error)
            del pending[contract.name]
    return ({contract.name: values[contract.name] for contract in contracts if contract.name in values}, errors)


def expected_affected_names(recipes: Iterable[Any], changed_sources: Iterable[str],
                            changed_tools: Iterable[str] = (), candidate_names: Iterable[str] | None = None) -> set[str]:
    """Independent fixed-point dependency closure over declared contracts.

    Identity/impact is deliberately independent from numeric equality. Passing
    candidate_names filters the result only after computing the entire closure,
    preserving paths that cross a requested partition/report boundary.
    """
    contracts = _contracts(recipes)
    roots = {name if name.startswith("source:") else f"source:{name}" for name in changed_sources}
    tools = set(changed_tools)
    affected = set(roots)
    while True:
        discovered = {contract.name for contract in contracts
                      if contract.tool in tools or affected.intersection(contract.inputs.values())}
        if discovered <= affected:
            break
        affected.update(discovered)
    result = {contract.name for contract in contracts if contract.name in affected}
    return result if candidate_names is None else result.intersection(candidate_names)


def _orders(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise OracleUnavailable("Orders must be a list")
    orders, currencies = {}, {}
    for row in value:
        identifier, region, currency = row["order_id"], row["region"], row["currency"]
        if not all(isinstance(text, str) and text for text in (identifier, region, currency)) or identifier in orders:
            raise OracleUnavailable("Invalid/duplicate order identity")
        if region in currencies and currencies[region] != currency:
            raise OracleUnavailable("Mixed currencies in a region")
        currencies[region] = currency
        _integer(row["gross_cents"], "order amount", nonnegative=True)
        orders[identifier] = row
    return orders


def _money_groups(rows: Iterable[tuple[str, str, int]]) -> dict[str, Any]:
    groups: dict[str, int] = defaultdict(int)
    currencies = {}
    for region, currency, amount in rows:
        if region in currencies and currencies[region] != currency:
            raise OracleUnavailable("Mixed currencies in aggregate")
        groups[region] += amount
        currencies[region] = currency
    return {"regions": {region: {"currency": currencies[region], "amount_cents": _integer(int(groups[region]), "aggregate")}
                        for region in sorted(groups)}}


def _calculate(contract: _Contract, inputs: dict[str, Any]) -> dict[str, Any]:
    tool = contract.tool
    if tool == "gross_by_region":
        return _money_groups((row["region"], row["currency"], row["gross_cents"])
                             for row in _orders(inputs["orders"]).values())
    if tool == "refunds_by_region":
        orders = _orders(inputs["orders"])
        joined = []
        for row in inputs["refunds"]:
            if row["order_id"] not in orders:
                raise OracleUnavailable("Refund references an absent order")
            order = orders[row["order_id"]]
            joined.append((order["region"], order["currency"], _integer(row["refund_cents"], "refund", nonnegative=True)))
        return _money_groups(joined)
    if tool == "net_by_region":
        gross, refunds = inputs["gross"]["regions"], inputs["refunds"]["regions"]
        if set(refunds) - set(gross):
            raise OracleUnavailable("Refund region absent from gross")
        output = {}
        for region, value in sorted(gross.items()):
            refund = refunds.get(region, {"amount_cents": 0, "currency": value["currency"]})
            if value["currency"] != refund["currency"]:
                raise OracleUnavailable("Gross/refund currency mismatch")
            output[region] = {"currency": value["currency"], "amount_cents": _integer(value["amount_cents"] - refund["amount_cents"], "net")}
        return {"regions": output}
    if tool == "convert_to_usd":
        output = {}
        for region, value in sorted(inputs["net"]["regions"].items()):
            rate = _decimal(inputs["fx"][value["currency"]], "USD conversion rate")
            if rate <= 0:
                raise OracleUnavailable("USD conversion rate must be positive")
            with localcontext() as context:
                context.prec = 80
                cents = (Decimal(value["amount_cents"]) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
            output[region] = {"usd_cents": _integer(int(cents), "USD cents")}
        return {"regions": output}
    if tool == "company_total":
        return {"usd_cents": _integer(sum(_integer(row["usd_cents"], "regional USD")
                                         for row in inputs["regional"]["regions"].values()), "company USD")}
    if tool == "support_by_region":
        tickets = inputs["tickets"]
        identities = [row["ticket_id"] for row in tickets]
        if len(set(identities)) != len(identities):
            raise OracleUnavailable("Duplicate ticket identity")
        counts = Counter(row["region"] for row in tickets)
        return {"regions": {region: {"tickets": counts[region]} for region in sorted(counts)}}
    sections, keys = [], set()
    for section in contract.params["sections"]:
        if section["key"] in keys:
            raise OracleUnavailable("Duplicate report section key")
        keys.add(section["key"])
        value = inputs[section["input"]]
        path = section["path"]
        if not isinstance(path, list) or not path:
            raise OracleUnavailable("Report claim requires a declared object path")
        for key in path:
            value = value[key]
        value = _integer(value, "report numeric claim")
        expected_unit = {"usd_cents": "USD cents", "tickets": "tickets"}.get(path[-1])
        if expected_unit is None or section["unit"] != expected_unit:
            raise OracleUnavailable("Report path/unit does not identify a supported quantity")
        sections.append({"key": section["key"], "label": section["label"], "value": value, "unit": section["unit"]})
    if not sections:
        raise OracleUnavailable("Empty report")
    return {"title": contract.params["title"], "sections": sections}
