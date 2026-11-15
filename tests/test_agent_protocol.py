from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from proofflow.agent import (AgentProtocolError, AgentProviderError, AgentRequest,
                            ClaudeCLIProvider, ProviderResult, execute_plan, plan_refresh)


def request():
    return AgentRequest("Revalidate the EU brief after the rate correction", ("fx@old",),
                        json.dumps({"id": "revenue@v1", "inputs": ["fx@old"]}), ("revenue@v1",))


class StubProvider:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def generate(self, prompt, schema):
        self.prompts.append((prompt, schema))
        return ProviderResult(self.payload, model="stub")


def payload(**updates):
    return {"selected_ids": ["revenue@v1"], "rationale": "Direct dependency on the changed rate", "abstain": False, **updates}


def test_hidden_allowed_ids_cannot_leak_into_or_expand_request():
    provider = StubProvider(payload())
    bad = replace(request(), allowed_artifact_ids=("revenue@v1", "hidden-gold-id"))
    with pytest.raises(AgentProtocolError, match="exactly match"):
        plan_refresh(provider, bad)
    assert provider.prompts == []


@pytest.mark.parametrize("bad", [
    payload(selected_ids=["hidden-gold-id"]),
    payload(selected_ids=["revenue@v1", "revenue@v1"]),
    payload(selected_ids="revenue@v1"),
    payload(abstain="false"),
    payload(abstain=True),
    {**payload(), "tool_command": "unexpected"},
])
def test_malformed_or_unseen_actions_rejected(bad):
    with pytest.raises(AgentProtocolError):
        plan_refresh(StubProvider(bad), request())


def test_prompt_has_only_task_changed_ids_and_selected_context():
    provider = StubProvider(payload())
    plan = plan_refresh(provider, request())
    sent = json.loads(provider.prompts[0][0])
    assert set(sent) == {"task", "changed_ids", "evidence_jsonl"}
    assert "allowed_artifact_ids" not in sent
    assert plan.selected_ids == ("revenue@v1",)


class StubRuntime:
    def __init__(self, kind="artifact"):
        self.calls = []
        self.store = SimpleNamespace(get=lambda _: SimpleNamespace(kind=kind))

    def refresh(self, ids, run_id=None):
        self.calls.append((ids, run_id))
        return SimpleNamespace(to_dict=lambda: {"executed": ids})


def test_executor_maps_only_present_aliases_and_binds_request():
    req = request()
    plan = plan_refresh(StubProvider(payload()), req)
    runtime = StubRuntime()
    result = execute_plan(runtime, plan, req, id_map={"revenue@v1": "raw-immutable-id"})
    assert result["status"] == "executed"
    assert runtime.calls == [(["raw-immutable-id"], None)]
    with pytest.raises(AgentProtocolError, match="does not belong"):
        execute_plan(runtime, plan, replace(req, task="different task"))


def test_abstention_and_invalid_type_execute_nothing():
    req = request()
    plan = plan_refresh(StubProvider(payload(abstain=True, selected_ids=[])), req)
    runtime = StubRuntime()
    assert execute_plan(runtime, plan, req)["status"] == "abstained"
    assert runtime.calls == []
    wrong_kind = StubRuntime(kind="source")
    plan = plan_refresh(StubProvider(payload()), req)
    with pytest.raises(AgentProtocolError, match="Only artifact"):
        execute_plan(wrong_kind, plan, req)
    assert wrong_kind.calls == []


def test_cli_argv_disables_tools_and_preserves_actual_usage(monkeypatch):
    seen = {}
    def run(command, **kwargs):
        seen.update(command=command, kwargs=kwargs)
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "is_error": False, "structured_output": payload(),
            "modelUsage": {"claude-fable-5-2": {"canonicalModel": "claude-fable-5-2", "inputTokens": 123}},
            "total_cost_usd": 0.01,
        }))
    monkeypatch.setattr("proofflow.agent.subprocess.run", run)
    plan = plan_refresh(ClaudeCLIProvider(), request())
    assert seen["command"][seen["command"].index("--tools") + 1] == ""
    assert seen["command"][seen["command"].index("--effort") + 1] == "high"
    assert seen["kwargs"]["input"] == request().prompt()
    assert "shell" not in seen["kwargs"]
    assert plan.provider_result.model_usage["claude-fable-5-2"]["inputTokens"] == 123


def test_cli_auth_failure_or_model_fallback_not_counted_as_success(monkeypatch):
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "is_error": False, "structured_output": payload(),
            "modelUsage": {"different-model": {"canonicalModel": "different-model"}},
        }))
    monkeypatch.setattr("proofflow.agent.subprocess.run", run)
    with pytest.raises(AgentProviderError, match="differs"):
        plan_refresh(ClaudeCLIProvider(), request())


def test_mixed_model_usage_is_not_labeled_as_requested_model(monkeypatch):
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "structured_output": payload(), "modelUsage": {
                "claude-fable-5-2": {"canonicalModel": "claude-fable-5-2"},
                "fallback": {"canonicalModel": "different-model"},
            }, "total_cost_usd": 0.25,
        }))
    monkeypatch.setattr("proofflow.agent.subprocess.run", run)
    with pytest.raises(AgentProviderError) as error:
        plan_refresh(ClaudeCLIProvider(), request())
    assert error.value.evidence["total_cost_usd"] == 0.25


def test_invalid_model_plan_preserves_paid_usage():
    provider = StubProvider(payload(selected_ids=["hidden-gold-id"]))
    with pytest.raises(AgentProtocolError) as error:
        plan_refresh(provider, request())
    assert error.value.provider_result.payload["selected_ids"] == ["hidden-gold-id"]
