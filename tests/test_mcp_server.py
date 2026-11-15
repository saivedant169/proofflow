"""MCP facade integration using real persisted tools and an explicit graph fake.

The stock SDK/live-Hydra transport smoke is separate. These tests call no model.
"""
from contextlib import contextmanager
import copy
import fcntl
import json
import time
from unittest.mock import patch

import pytest

from proofflow import importing
from proofflow.composition import CompositionError
from proofflow.mcp_server import MCPInputError, ProofFlowMCP
from test_api import TestGraphFactory


CSV = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
       "n1,NORTH,EUR,10000,1000,3\n"
       "s1,SOUTH,USD,20000,0,1\n")
REORDERED = ("order_id,region,currency,gross_cents,refund_cents,ticket_count\n"
             "s1,SOUTH,USD,20000,0,1\n"
             "n1,NORTH,EUR,10000,1000,3\n")


class ManagedGraphFactory(TestGraphFactory):
    @contextmanager
    def __call__(self, *, namespace):
        graph = super().__call__(namespace=namespace)
        try:
            yield graph
        finally:
            graph.close()

    @property
    def mutation_count(self):
        return sum(graph.mutations for graph in self.clients)


@pytest.fixture
def graph_factory():
    return ManagedGraphFactory()


@pytest.fixture
def facade(tmp_path, graph_factory):
    return ProofFlowMCP(tmp_path / "mcp", graph_factory=graph_factory)


def step(name, tool, inputs, sections=None, title=None):
    return {"id": name, "tool": tool,
            "inputs": [{"name": key, "ref": ref} for key, ref in inputs.items()],
            "title": title, "sections": sections or []}


def section(key, input_name, path, unit="USD cents"):
    return {"key": key, "label": key, "input": input_name, "path": path, "unit": unit}


def plan(steps):
    return {"steps": steps, "output": steps[-1]["id"], "abstain": False,
            "rationale": "Test client independently selects typed analytics and existing inputs."}


def company_plan():
    return plan([
        step("gross", "gross_by_region", {"orders": "source:orders"}),
        step("refunds", "refunds_by_region", {"orders": "source:orders", "refunds": "source:refunds"}),
        step("net", "net_by_region", {"gross": "gross", "refunds": "refunds"}),
        step("usd", "convert_to_usd", {"net": "net", "fx": "source:fx"}),
        step("company", "company_total", {"regional": "usd"}),
        step("support", "support_by_region", {"tickets": "source:tickets"}),
        step("report", "compose_report", {"revenue": "company", "support": "support"}, [
            section("company_revenue", "revenue", ["usd_cents"]),
            section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")],
            "Company report"),
    ])


def north_plan(prepared):
    handles = {item["producing_tool"]: item["handle"]
               for item in prepared["request"]["available"] if item["kind"] == "artifact"}
    return plan([step("brief", "compose_report", {
        "regional": handles["convert_to_usd"], "company": handles["company_total"],
        "support": handles["support_by_region"]}, [
            section("north_revenue", "regional", ["regions", "NORTH", "usd_cents"]),
            section("company_context", "company", ["usd_cents"]),
            section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")],
        "NORTH operations report")])


def values(claims):
    return {claim["key"]: claim["value"] for claim in claims}


def load(facade, workspace="commerce", csv_text=CSV, rate="1.20"):
    return facade.load_csv(workspace, csv_text, rates={"EUR": rate}, region="NORTH")


def first_report(facade, workspace="commerce"):
    load(facade, workspace)
    prepared = facade.prepare(workspace, "Calculate company net USD revenue and NORTH support")
    return facade.execute_plan(workspace, prepared["snapshot_token"], company_plan(), "request-A")


def test_independent_plans_reuse_then_refresh_only_fx_dependents(facade):
    first = first_report(facade)
    assert first["executed_count"] == 7
    assert values(first["claims"]) == {"company_revenue": 30800, "north_support": 3}
    assert first["planner"] == {"provider": "external-mcp-client", "model": "unreported", "model_calls": 0}

    prepared = facade.prepare("commerce", "Create a NORTH operations report using existing calculations")
    second = facade.execute_plan("commerce", prepared["snapshot_token"], north_plan(prepared), "request-B")
    assert second["executed_count"] == 1
    assert values(second["claims"]) == {"north_revenue": 10800, "company_context": 30800, "north_support": 3}
    original_ids = [first["report_id"], second["report_id"]]
    before = facade.inspect("commerce")["artifacts"]
    support_before = next(item for item in before if item["metadata"]["tool"] == "support_by_region")

    changed = load(facade, rate="1.30")
    assert len(changed["changed_source_version_ids"]) == 1
    assert len(changed["affected_artifact_ids"]) == 4
    assert set(original_ids) <= set(changed["affected_artifact_ids"])
    stale = facade.inspect("commerce", original_ids)["artifacts"]
    assert all(item["state"] == "stale" and item["value"] is None and item["saved_value"] for item in stale)
    assert values(stale[0]["claims"]) == {"company_revenue": None, "north_support": 3}

    refreshed = facade.refresh("commerce", original_ids)
    assert refreshed["executed_count"] == len(refreshed["tool_calls"]) == 4
    assert [values(item["claims"]) for item in refreshed["artifacts"]] == [
        {"company_revenue": 31700, "north_support": 3},
        {"north_revenue": 11700, "company_context": 31700, "north_support": 3},
    ]
    support_after = facade.inspect("commerce", [support_before["id"]])["artifacts"][0]
    assert support_after["state"] == "current"
    assert support_after["content_hash"] == support_before["content_hash"]
    assert all(call["tool"] != "support_by_region" for call in refreshed["tool_calls"])
    repeated = facade.refresh("commerce", original_ids)
    assert repeated["executed_count"] == 0 and repeated["tool_calls"] == []
    assert len(repeated["result"]["executed"]) == 0
    reordered = load(facade, csv_text=REORDERED, rate="1.30")
    assert reordered["changed_source_version_ids"] == reordered["affected_artifact_ids"] == []
    assert facade.refresh("commerce", original_ids)["executed_count"] == 0


def test_load_accounts_for_preflight_separately_from_recorded_execution(facade):
    with patch("proofflow.importing.execute_tool", wraps=importing.execute_tool) as calculation:
        loaded = load(facade)
    assert calculation.call_count == loaded["preflight_calculation_count"] == 8
    assert loaded["executed_count"] == 0
    assert "excludes" in loaded["execution_count_scope"]
    assert len(loaded["source_versions"]) == 4
    assert facade.inspect("commerce")["artifacts"] == []


def test_changed_snapshot_is_rejected_before_any_artifact_or_graph_write(facade, graph_factory):
    load(facade)
    prepared = facade.prepare("commerce", "Calculate company revenue")
    load(facade, rate="1.30")
    before = graph_factory.mutation_count
    with pytest.raises(CompositionError, match="changed after planning"):
        facade.execute_plan("commerce", prepared["snapshot_token"], company_plan(), "stale-run")
    assert graph_factory.mutation_count == before
    assert facade.inspect("commerce")["artifacts"] == []


def test_foreign_handles_unknown_tools_and_invalid_workspaces_do_not_execute(facade, graph_factory):
    first = first_report(facade, "owner")
    load(facade, "other")
    prepared = facade.prepare("other", "Calculate company revenue")
    before = graph_factory.mutation_count
    for operation in (facade.inspect, facade.refresh):
        with pytest.raises(MCPInputError, match="Unknown artifact"):
            operation("other", [first["report_id"]])
    for tool, ref in (("execute_sql", None), (None, first["report_id"]), (None, "missing:handle")):
        invalid = copy.deepcopy(company_plan())
        if tool:
            invalid["steps"][0]["tool"] = tool
        else:
            invalid["steps"][0]["inputs"][0]["ref"] = ref
        with pytest.raises(CompositionError):
            facade.execute_plan("other", prepared["snapshot_token"], invalid, "invalid-run")
    with pytest.raises(MCPInputError, match="Unknown or consumed"):
        facade.execute_plan("owner", prepared["snapshot_token"], company_plan(), "foreign-snapshot")
    for workspace in ("../escape", "UPPER", "", [], "a" * 49):
        with pytest.raises(MCPInputError, match="Workspace must"):
            facade.inspect(workspace)
    assert graph_factory.mutation_count == before
    assert facade.inspect("other")["artifacts"] == []


def test_snapshot_and_artifacts_survive_new_facade_and_consumption_is_final(facade, graph_factory):
    load(facade)
    prepared = facade.prepare("commerce", "Calculate company revenue")
    reopened = ProofFlowMCP(facade.directory, graph_factory=graph_factory)
    executed = reopened.execute_plan("commerce", prepared["snapshot_token"], company_plan(), "after-reopen")
    assert executed["executed_count"] == 7
    with pytest.raises(MCPInputError, match="consumed"):
        reopened.execute_plan("commerce", prepared["snapshot_token"], company_plan(), "duplicate")
    final = ProofFlowMCP(facade.directory, graph_factory=graph_factory)
    record = final.inspect("commerce", [executed["report_id"]])["artifacts"][0]
    assert record["state"] == "current"
    assert values(record["claims"]) == {"company_revenue": 30800, "north_support": 3}
    assert record["receipt"]["run_id"] == "after-reopen"
    assert final.refresh("commerce", [record["id"]])["executed_count"] == 0


@pytest.mark.parametrize("csv_text", [
    "order_id,region,currency,gross_cents,ticket_count\nn1,NORTH,USD,10000,0\n",
    "order_id,region,currency,gross_cents\nn1,NORTH,USD,10000\n",
])
def test_absent_ticket_region_is_rejected_before_partial_execution(facade, graph_factory, csv_text):
    facade.load_csv("zero-support", csv_text, region="NORTH")
    prepared = facade.prepare("zero-support", "Report NORTH support tickets")
    assert prepared["supported_ticket_regions"] == []
    requested = plan([
        step("support", "support_by_region", {"tickets": "source:tickets"}),
        step("report", "compose_report", {"support": "support"}, [
            section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")], "Support"),
    ])
    before = graph_factory.mutation_count
    with pytest.raises(CompositionError, match="absent zero-ticket region"):
        facade.execute_plan("zero-support", prepared["snapshot_token"], requested, "unsupported")
    assert graph_factory.mutation_count == before
    assert facade.inspect("zero-support")["artifacts"] == []

    # The same unsupported path must be rejected when the empty aggregate already exists.
    with facade._runtime("zero-support") as (runtime, _):
        support = runtime.execute("support_by_region", {"tickets": runtime.store.get_head("source:tickets").id},
                                  logical_id="empty:support", run_id="existing-empty-support")
    prepared = facade.prepare("zero-support", "Report NORTH support from the saved aggregate")
    requested = plan([step("report", "compose_report", {"support": "empty:support"}, [
        section("north_support", "support", ["regions", "NORTH", "tickets"], "tickets")], "Support")])
    before = graph_factory.mutation_count
    with pytest.raises(CompositionError, match="absent zero-ticket region"):
        facade.execute_plan("zero-support", prepared["snapshot_token"], requested, "unsupported-reuse")
    assert graph_factory.mutation_count == before
    assert [item["id"] for item in facade.inspect("zero-support")["artifacts"]] == [support.id]


def test_workspace_lock_refuses_busy_operations_and_snapshot_expiry(facade, graph_factory):
    load(facade)
    prepared = facade.prepare("commerce", "Calculate company revenue")
    before = graph_factory.mutation_count
    with (facade.directory / "commerce" / ".workspace.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(MCPInputError, match="busy"):
            facade.inspect("commerce")
    assert graph_factory.mutation_count == before
    snapshot_path = facade.directory / "commerce" / "snapshots" / f"{prepared['snapshot_token']}.json"
    snapshot = json.loads(snapshot_path.read_text())
    snapshot["created_unix"] = time.time() - 601
    snapshot_path.write_text(json.dumps(snapshot))
    with pytest.raises(MCPInputError, match="expired"):
        facade.execute_plan("commerce", prepared["snapshot_token"], company_plan(), "expired")
    assert not snapshot_path.exists()
    assert graph_factory.mutation_count == before
    assert facade.inspect("commerce")["artifacts"] == []
