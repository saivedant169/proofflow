"""Composition protocol tests; the in-memory graph is a unit double only."""
from copy import deepcopy
from dataclasses import replace
import json
import subprocess

import pytest

from proofflow.agent import AgentProviderError, ProviderResult
from proofflow.analytics import DEMO_SOURCES
from proofflow.artifacts import ArtifactStore
from proofflow.composition import (COMPOSITION_SCHEMA, COMPOSITION_SYSTEM_PROMPT, CompositionCLIProvider,
                                   CompositionError, CompositionPlan, execute_composition, make_request,
                                   plan_composition, validate_plan)
from proofflow.runtime import ProofFlowRuntime
from test_runtime import UnitTestGraph, build_fixture


class StubProvider:
    def __init__(self, payload):
        self.payload = payload
        self.prompt = None

    def generate(self, prompt, schema):
        self.prompt = prompt
        assert schema == COMPOSITION_SCHEMA
        return ProviderResult(self.payload, reported_cost_usd=0.1, model="unit-test-stub")


@pytest.fixture
def runtime(tmp_path):
    store = ArtifactStore(tmp_path / "state")
    result = ProofFlowRuntime(store, UnitTestGraph())
    yield result
    store.close()


def report_plan(company="metric:company", support="metric:support"):
    return {"steps": [{"id": "brief", "tool": "compose_report", "inputs": [
        {"name": "company", "ref": company}, {"name": "support", "ref": support}],
        "title": "Model chosen company brief", "sections": [
            {"key": "revenue", "label": "Company revenue", "input": "company", "path": ["usd_cents"], "unit": "USD cents"},
            {"key": "tickets", "label": "EU tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"}]}],
        "output": "brief", "abstain": False, "rationale": "Reuse current typed artifacts."}


def first_plan():
    steps = []
    def calc(sid, tool, inputs):
        steps.append({"id": sid, "tool": tool, "inputs": [{"name": k, "ref": v} for k, v in inputs.items()],
                      "title": None, "sections": []})
    calc("gross", "gross_by_region", {"orders": "source:orders"})
    calc("refunds", "refunds_by_region", {"orders": "source:orders", "refunds": "source:refunds"})
    calc("net", "net_by_region", {"gross": "gross", "refunds": "refunds"})
    calc("regional", "convert_to_usd", {"net": "net", "fx": "source:fx"})
    calc("company", "company_total", {"regional": "regional"})
    calc("support", "support_by_region", {"tickets": "source:tickets"})
    plan = report_plan("company", "support")
    plan["steps"] = steps + plan["steps"]
    return plan


def test_typed_plan_executes_real_tools_and_preserves_report_provenance(runtime):
    for name, value in DEMO_SOURCES.items():
        runtime.set_source(name, value)
    request = make_request(runtime, "Compute company net revenue in USD and EU tickets")
    provider = StubProvider(first_plan())
    plan = plan_composition(provider, request)
    result = execute_composition(runtime, request, plan, run_id="unit-model-first")
    assert [claim["value"] for claim in result["claims"]] == [556500, 2]
    assert len(result["calls"]) == 7
    assert runtime.currentness(result["report_id"]).is_current
    assert "556500" not in provider.prompt and "209000" not in provider.prompt
    assert "steps" not in json.loads(provider.prompt)  # no supplied gold recipe


def test_new_report_reuses_existing_immutable_artifacts(runtime):
    _, nodes = build_fixture(runtime)
    request = make_request(runtime, "Create company brief")
    result = execute_composition(runtime, request, plan_composition(StubProvider(report_plan()), request), run_id="new-run")
    assert len(result["calls"]) == 1
    assert runtime.store.get(result["report_id"]).metadata["inputs"] == {"company": nodes["company"].id, "support": nodes["support"].id}


@pytest.mark.parametrize("edit", [
    lambda p: p["steps"][0].update(tool=[]),
    lambda p: p.update(output=[]),
    lambda p: p["steps"][0]["sections"][0].update(input=[]),
    lambda p: p["steps"][0]["sections"][0].update(value=556500),
    lambda p: p["steps"][0]["sections"][0].update(unit="tickets"),
    lambda p: p["steps"][0]["inputs"][0].update(ref="future_step"),
    lambda p: p["steps"][0].update(tool="run_sql"),
])
def test_invalid_plans_are_rejected_before_calls_and_preserve_provider_evidence(runtime, edit):
    build_fixture(runtime)
    request = make_request(runtime, "Create company brief")
    payload = report_plan()
    edit(payload)
    calls = len(runtime.calls)
    with pytest.raises(CompositionError) as raised:
        plan_composition(StubProvider(payload), request)
    assert raised.value.provider_result.reported_cost_usd == 0.1
    assert len(runtime.calls) == calls


def test_all_steps_validated_before_first_tool(runtime):
    for name, value in DEMO_SOURCES.items():
        runtime.set_source(name, value)
    request = make_request(runtime, "Compute company revenue")
    payload = first_plan()
    payload["steps"][-1]["sections"][0]["unit"] = "tickets"
    plan = CompositionPlan(payload, request.execution_sha256(), ProviderResult(payload))
    with pytest.raises(CompositionError):
        execute_composition(runtime, request, plan, run_id="must-not-start")
    assert runtime.calls == []


def test_changed_mapping_cannot_replay_approved_plan(runtime):
    _, nodes = build_fixture(runtime)
    request = make_request(runtime, "Create company brief")
    plan = plan_composition(StubProvider(report_plan()), request)
    altered = replace(request, handles={**request.handles, "metric:company": nodes["regional"].id})
    assert altered.prompt() == request.prompt()
    with pytest.raises(CompositionError, match="another request"):
        execute_composition(runtime, altered, plan, run_id="must-not-start")


def test_descriptor_content_and_type_verified_before_execution(runtime):
    build_fixture(runtime)
    request = make_request(runtime, "Create company brief")
    descriptors = deepcopy(request.descriptors)
    descriptors[0]["content_sha256"] = "incorrect"
    altered = replace(request, descriptors=descriptors)
    plan = plan_composition(StubProvider(report_plan()), altered)
    with pytest.raises(CompositionError, match="descriptor"):
        execute_composition(runtime, altered, plan, run_id="must-not-start")


def test_changed_source_snapshot_requires_new_plan(runtime):
    build_fixture(runtime)
    request = make_request(runtime, "Create company brief")
    plan = plan_composition(StubProvider(report_plan()), request)
    runtime.set_source("fx", {"EUR": "1.20", "USD": "1.00", "GBP": "1.25"})
    with pytest.raises(CompositionError, match="changed after planning"):
        execute_composition(runtime, request, plan, run_id="must-not-start")


def test_mixed_model_usage_rejected_and_usage_preserved(monkeypatch):
    envelope = {"structured_output": {}, "modelUsage": {"one": {"canonicalModel": "claude-fable-5-2"},
                                                       "two": {"canonicalModel": "other"}}, "total_cost_usd": 0.2}
    def fake_run(command, **kwargs):
        assert command[command.index("--system-prompt") + 1] == COMPOSITION_SYSTEM_PROMPT
        assert command[command.index("--tools") + 1] == ""
        assert "--safe-mode" in command and "--strict-mcp-config" in command
        return subprocess.CompletedProcess(command, 0, json.dumps(envelope), "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentProviderError) as raised:
        CompositionCLIProvider().generate("task", COMPOSITION_SCHEMA)
    assert raised.value.evidence["total_cost_usd"] == 0.2
