"""Authored pilot workloads and mutations, declared before benchmark runs.

The recipe declarations below independently specify expected direct inputs.
Gold labels never enter runtime traversal or retrieval. The deterministic pilot
is not an evaluation of a language model's ability to invent these workflows.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from proofflow.analytics import DEMO_SOURCES


PERIODS = ("2026-W44", "2026-W45", "2026-W46")


@dataclass(frozen=True)
class Recipe:
    name: str
    tool: str
    inputs: dict[str, str]
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    run: str = "company"


def recipes(period: str) -> list[Recipe]:
    """Three ordinary saved briefs share real financial/support calculations."""
    p = period
    return [
        Recipe(f"{p}:gross", "gross_by_region", {"orders": f"source:orders:{p}"},
               description=f"Gross sales before customer refunds for {p}, by region and currency."),
        Recipe(f"{p}:refunds", "refunds_by_region", {"orders": f"source:orders:{p}", "refunds": f"source:refunds:{p}"},
               description=f"Customer refunds matched to their orders for {p}, grouped by region."),
        Recipe(f"{p}:net", "net_by_region", {"gross": f"{p}:gross", "refunds": f"{p}:refunds"},
               description=f"Regional net revenue after refunds in local currencies for {p}."),
        Recipe(f"{p}:usd", "convert_to_usd", {"net": f"{p}:net", "fx": f"source:fx:{p}"},
               description=f"Regional net revenue converted to US dollars for {p}."),
        Recipe(f"{p}:company", "company_total", {"regional": f"{p}:usd"},
               description=f"Company-wide net revenue in USD for {p}."),
        Recipe(f"{p}:support", "support_by_region", {"tickets": f"source:tickets:{p}"},
               description=f"Support ticket volumes by region for {p}, independent of revenue calculations."),
        Recipe(f"{p}:company_brief", "compose_report", {"revenue": f"{p}:company", "support": f"{p}:support"},
               {"title": f"Company performance brief — {p}", "sections": [
                   {"key": "revenue", "label": "Company net revenue", "input": "revenue", "path": ["usd_cents"], "unit": "USD cents"},
                   {"key": "eu_support", "label": "EU support tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
               ]}, f"Weekly company report covering net revenue and EU support demand for {p}."),
        Recipe(f"{p}:eu_brief", "compose_report", {"regional": f"{p}:usd", "support": f"{p}:support"},
               {"title": f"EU operations brief — {p}", "sections": [
                   {"key": "net_revenue", "label": "EU net revenue in USD", "input": "regional", "path": ["regions", "EU", "usd_cents"], "unit": "USD cents"},
                   {"key": "tickets", "label": "EU support tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
               ]}, f"EU operations report for {p}, reusing the regional revenue artifact from the company run.", "eu_operations"),
        Recipe(f"{p}:support_brief", "compose_report", {"support": f"{p}:support"},
               {"title": f"Customer support brief — {p}", "sections": [
                   {"key": "eu", "label": "EU customer support volume", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
                   {"key": "us", "label": "US customer support volume", "input": "support", "path": ["regions", "US", "tickets"], "unit": "tickets"},
               ]}, f"Support operations report for {p}; contains no revenue or exchange-rate calculation.", "support_operations"),
    ]


def heldout_recipe() -> Recipe:
    return Recipe("cross_period:comparison", "compose_report",
                  {"prior": "2026-W45:company", "current": "2026-W46:company", "support": "2026-W46:support"},
                  {"title": "Two-week revenue comparison with current support", "sections": [
                      {"key": "prior", "label": "Prior week company revenue", "input": "prior", "path": ["usd_cents"], "unit": "USD cents"},
                      {"key": "current", "label": "Current week company revenue", "input": "current", "path": ["usd_cents"], "unit": "USD cents"},
                      {"key": "support", "label": "Current EU tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
                  ]}, "New report composition combines artifacts from two earlier independent weekly runs.", "heldout_composition")


def fixture_sources() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for week, period in enumerate(PERIODS):
        for name, data in DEMO_SOURCES.items():
            value = deepcopy(data)
            if name == "orders":
                for index, row in enumerate(value):
                    row["gross_cents"] += 1000 * week * (index + 1)
            if name == "fx":
                value["EUR"] = ("1.08", "1.09", "1.10")[week]
            sources[f"{name}:{period}"] = value
    return sources


@dataclass(frozen=True)
class Mutation:
    source: str = ""
    operation: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    tool: str = ""


@dataclass(frozen=True)
class Scenario:
    id: str
    split: str
    description: str
    mutations: tuple[Mutation, ...]
    category: str
    scope_periods: tuple[str, ...] = PERIODS
    restart: bool = False
    additional_composition: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCENARIOS: tuple[Scenario, ...] = (
    Scenario("D01", "dev", "Correct the EU order eu-101 amount in week 44; identify saved calculations and briefs requiring revalidation.",
             (Mutation("orders:2026-W44", "order_delta", {"order_id": "eu-101", "delta": 2500}),), "direct_and_transitive"),
    Scenario("D02", "dev", "Restate the EUR-to-USD exchange rate for week 44 and refresh dependent saved reports.",
             (Mutation("fx:2026-W44", "rate", {"currency": "EUR", "value": "1.12"}),), "multi_hop"),
    Scenario("D03", "dev", "Add a refund against eu-102 in week 44; both company and EU briefs may share the result.",
             (Mutation("refunds:2026-W44", "refund", {"order_id": "eu-102", "refund_cents": 3000}),), "cross_run"),
    Scenario("D04", "dev", "A new EU support ticket arrived in week 44; preserve reusable revenue calculations.",
             (Mutation("tickets:2026-W44", "ticket", {"ticket_id": "late-dev", "region": "EU", "status": "open"}),), "independent_branch"),
    Scenario("D05", "dev", "Correct two week-44 EU orders by opposite amounts without changing their regional total.",
             (Mutation("orders:2026-W44", "offset_orders", {"first": "eu-101", "second": "eu-102", "delta": 1000}),), "unchanged_value"),
    Scenario("D06", "dev", "The gross-sales calculation implementation version changed; revalidate dependent artifacts.",
             (Mutation(operation="tool_version", tool="gross_by_region"),), "tool_version"),
    Scenario("T01", "test", "Correct the US order us-201 amount in week 46 and find every affected saved calculation and report.",
             (Mutation("orders:2026-W46", "order_delta", {"order_id": "us-201", "delta": -1700}),), "direct_and_transitive"),
    Scenario("T02", "test", "A late week-46 UK refund changes evidence reused by later company and EU operations runs.",
             (Mutation("refunds:2026-W46", "refund", {"order_id": "uk-301", "refund_cents": 4200}),), "cross_run"),
    Scenario("T03", "test", "Correct both EUR and GBP conversion rates for week 46; locate all dependent USD metrics and briefs.",
             (Mutation("fx:2026-W46", "rates", {"EUR": "1.14", "GBP": "1.28"}),), "multi_hop"),
    Scenario("T04", "test", "Restate a week-45 EU order used by the already composed company summary.",
             (Mutation("orders:2026-W45", "order_delta", {"order_id": "eu-102", "delta": 4700}),), "fan_in"),
    Scenario("T05", "test", "A US customer support ticket arrives in week 46; financial revenue evidence should remain reusable.",
             (Mutation("tickets:2026-W46", "ticket", {"ticket_id": "late-us", "region": "US", "status": "closed"}),), "independent_branch"),
    Scenario("T06", "test", "An old week-44 order is corrected. Determine whether week-46 reports require revalidation.",
             (Mutation("orders:2026-W44", "order_delta", {"order_id": "uk-301", "delta": 1800}),), "other_scope", ("2026-W46",)),
    Scenario("T07", "test", "A week-45 refund and a week-46 support ticket arrive together; identify their combined impact.",
             (Mutation("refunds:2026-W45", "refund", {"order_id": "us-201", "refund_cents": 2500}),
              Mutation("tickets:2026-W46", "ticket", {"ticket_id": "late-joint", "region": "EU", "status": "open"})), "multiple_sources"),
    Scenario("T08", "test", "Two week-45 US order corrections offset, leaving the regional aggregate equal while its inputs changed.",
             (Mutation("orders:2026-W45", "offset_orders", {"first": "us-201", "second": "us-202", "delta": 1300}),), "unchanged_value"),
    Scenario("T09", "test", "The currency conversion tool version was replaced. Its code-defined arithmetic is unchanged but prior receipts need revalidation.",
             (Mutation(operation="tool_version", tool="convert_to_usd"),), "tool_version"),
    Scenario("T10", "test", "The week-46 exchange-rate source is unavailable. Dependent reports must block instead of serving stale numbers.",
             (Mutation("fx:2026-W46", "remove"),), "missing_source"),
    Scenario("T11", "test", "After correcting the week-45 EUR exchange rate, restart the application before deciding what to refresh.",
             (Mutation("fx:2026-W45", "rate", {"currency": "EUR", "value": "1.16"}),), "restart", restart=True),
    Scenario("T12", "test", "A newly composed two-week comparison reuses past artifacts. A week-45 refund correction must reach that new report.",
             (Mutation("refunds:2026-W45", "refund", {"order_id": "eu-101", "refund_cents": 1100}),), "unseen_composition", additional_composition=True),
)


def mutate_value(value: Any, mutation: Mutation) -> Any:
    value = deepcopy(value)
    p = mutation.parameters
    if mutation.operation == "order_delta":
        next(row for row in value if row["order_id"] == p["order_id"])["gross_cents"] += p["delta"]
    elif mutation.operation == "offset_orders":
        next(row for row in value if row["order_id"] == p["first"])["gross_cents"] += p["delta"]
        next(row for row in value if row["order_id"] == p["second"])["gross_cents"] -= p["delta"]
    elif mutation.operation == "rate":
        value[p["currency"]] = p["value"]
    elif mutation.operation == "rates":
        value.update(p)
    elif mutation.operation in {"refund", "ticket"}:
        value.append(dict(p))
    else:
        raise ValueError(f"Not a data mutation: {mutation.operation}")
    return value


def expected_affected_names(scenario: Scenario, recipe_list: list[Recipe]) -> set[str]:
    """Independent authored recipe oracle, without runtime records or Hydra."""
    roots = {f"source:{m.source}" for m in scenario.mutations if m.source}
    changed_tools = {m.tool for m in scenario.mutations if m.tool}
    impacted = set(roots)
    remaining = list(recipe_list)
    while remaining:
        next_remaining: list[Recipe] = []
        for recipe in remaining:
            if recipe.tool in changed_tools or set(recipe.inputs.values()) & impacted:
                impacted.add(recipe.name)
            else:
                next_remaining.append(recipe)
        if len(next_remaining) == len(remaining):
            break
        remaining = next_remaining
    return {recipe.name for recipe in recipe_list if recipe.name in impacted and
            (recipe.name.startswith(scenario.scope_periods) or recipe.name.startswith("cross_period:"))}


def manifest_data() -> dict[str, Any]:
    return {"version": "pilot-v1", "periods": list(PERIODS),
            "sources": fixture_sources(),
            "recipes": [asdict(recipe) for period in PERIODS for recipe in recipes(period)],
            "heldout_recipe": asdict(heldout_recipe()),
            "scenarios": [scenario.to_dict() for scenario in SCENARIOS]}
