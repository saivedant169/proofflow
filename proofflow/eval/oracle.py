"""Independent value oracle for the authored workload.

This evaluates recipe declarations over current fixture sources using Python
arithmetic, not runtime.execute_tool, SQLite queries, Hydra, or cached outputs.
It intentionally shares the stated monetary rounding/business rules, not code.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any

from .cases import Recipe


class OracleUnavailable(ValueError):
    pass


def compute_values(recipes: list[Recipe], sources: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    values: dict[str, Any] = {f"source:{name}": value for name, value in sources.items() if value is not None}
    errors: dict[str, str] = {}
    for recipe in recipes:
        missing = [key for key in recipe.inputs.values() if key not in values]
        if missing:
            errors[recipe.name] = "Unavailable inputs: " + ", ".join(missing)
            continue
        inputs = {key: values[name] for key, name in recipe.inputs.items()}
        try:
            values[recipe.name] = _calculate(recipe, inputs)
        except (KeyError, ValueError, TypeError) as exc:
            errors[recipe.name] = str(exc)
    return {r.name: values[r.name] for r in recipes if r.name in values}, errors


def _calculate(recipe: Recipe, inputs: dict[str, Any]) -> Any:
    tool = recipe.tool
    if tool == "gross_by_region":
        sums: dict[str, int] = defaultdict(int)
        currencies: dict[str, str] = {}
        for row in inputs["orders"]:
            region = row["region"]
            sums[region] += row["gross_cents"]
            if region in currencies and currencies[region] != row["currency"]:
                raise OracleUnavailable("Mixed region currencies")
            currencies[region] = row["currency"]
        return {"regions": {key: {"currency": currencies[key], "amount_cents": sums[key]} for key in sorted(sums)}}
    if tool == "refunds_by_region":
        orders = {row["order_id"]: row for row in inputs["orders"]}
        sums: dict[str, int] = defaultdict(int)
        currencies = {}
        for refund in inputs["refunds"]:
            order = orders[refund["order_id"]]
            sums[order["region"]] += refund["refund_cents"]
            currencies[order["region"]] = order["currency"]
        return {"regions": {key: {"currency": currencies[key], "amount_cents": sums[key]} for key in sorted(sums)}}
    if tool == "net_by_region":
        return {"regions": {region: {"currency": item["currency"],
                "amount_cents": item["amount_cents"] - inputs["refunds"]["regions"].get(region, {}).get("amount_cents", 0)}
                for region, item in inputs["gross"]["regions"].items()}}
    if tool == "convert_to_usd":
        result = {}
        for region, item in inputs["net"]["regions"].items():
            with localcontext() as context:
                context.prec = 50
                value = (Decimal(item["amount_cents"]) * Decimal(inputs["fx"][item["currency"]])).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
            result[region] = {"usd_cents": int(value)}
        return {"regions": result}
    if tool == "company_total":
        return {"usd_cents": sum(row["usd_cents"] for row in inputs["regional"]["regions"].values())}
    if tool == "support_by_region":
        counts = Counter(row["region"] for row in inputs["tickets"])
        return {"regions": {region: {"tickets": counts[region]} for region in sorted(counts)}}
    if tool == "compose_report":
        sections = []
        for spec in recipe.params["sections"]:
            value = inputs[spec["input"]]
            for part in spec["path"]:
                value = value[part]
            sections.append({"key": spec["key"], "label": spec["label"], "value": value, "unit": spec["unit"]})
        return {"title": recipe.params["title"], "sections": sections}
    raise OracleUnavailable(f"Unknown oracle tool: {tool}")
