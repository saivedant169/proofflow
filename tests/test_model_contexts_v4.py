"""Pure v4 context-contract tests: no source fixture, Hydra or model calls."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from proofflow.agent import AgentRequest
from proofflow.eval import model_contexts_v4 as contexts
from proofflow.eval.retail_data import RetailCase, RetailMutation, RetailRecipe
from proofflow.eval.retrieval import EvidenceRecord, RetrievalQuery, canonical, render_context
from proofflow.models import ArtifactRecord, SourceChange


ROOT = "source:day:orders@old"


def records():
    return [
        EvidenceRecord("artifact:day:gross@a", "Gross", "artifact:day:gross", "gross", (ROOT,),
                       description="Actual gross input dependency", tool_version_id="tool:gross@one", result={"saved": 1}),
        EvidenceRecord("artifact:day:report@b", "Report", "artifact:day:report", "report", ("artifact:day:gross@a",),
                       description="Actual saved report", tool_version_id="tool:report@one", result={"saved": 2}),
        EvidenceRecord("artifact:other:report@c", "Other report", "artifact:other:report", "report", ("source:other@old",),
                       description="Independent other-date report", tool_version_id="tool:report@one", result={"saved": 3}),
    ]


@pytest.fixture
def fake_indexes(monkeypatch):
    seen = []

    class Index:
        def __init__(self, corpus, *args, **kwargs):
            self.corpus = list(corpus)
            self.document_model_token_lengths = [len(record.render()) for record in corpus]
            self.chunk_count = len(corpus)
            seen.append({"renders": [record.render() for record in corpus], "queries": [], "kwargs": kwargs})
            self.observation = seen[-1]

        def rank(self, query):
            self.observation["queries"].append(query)
            return [record.id for record in reversed(self.corpus)]

    monkeypatch.setattr(contexts, "BM25Index", Index)
    monkeypatch.setattr(contexts, "DenseIndex", Index)
    return seen


def test_same_corpus_shared_budget_and_graph_flat_prompt_twins(fake_indexes):
    corpus = records()
    encoder = SimpleNamespace(memo={"earlier-case": "cached"})
    query = RetrievalQuery("Revalidate saved reports", (ROOT,))
    requests, metadata = contexts.prepare_evidence_requests(corpus, query,
        [corpus[0].id, corpus[1].id], encoder, len)
    assert set(requests) == set(contexts.ARMS)
    expected_budget = len(render_context(corpus[:2]))
    assert metadata["evidence_allowance"] == expected_budget
    assert metadata["graph_exact_flat_prompt_hashes_match"]
    assert metadata["native_flat_membership_equal"]
    assert requests["graph"].prompt() == requests["exact_flat"].prompt()
    assert encoder.memo == {}
    assert fake_indexes[0]["renders"] == fake_indexes[1]["renders"] == [record.render() for record in corpus]
    assert fake_indexes[0]["kwargs"] == {"k1": 1.5, "b": 0.75}
    for arm in contexts.ARMS:
        request = requests[arm]
        request.validate()
        assert request.task == query.text
        assert request.changed_ids == query.changed_ids
        assert set(json.loads(request.prompt())) == {"task", "changed_ids", "evidence_jsonl"}
        assert metadata["requests_by_arm"][arm]["context_sha256"] == hashlib.sha256(request.context_text.encode()).hexdigest()
        if arm != "full_context":
            assert len(request.context_text) <= expected_budget
    assert metadata["requests_by_arm"]["full_context"]["evidence_budget"] is None
    assert len(requests["full_context"].context_text) > expected_budget


def test_noop_has_zero_allowance_for_all_capped_arms_without_skipping_full_context(fake_indexes):
    requests, metadata = contexts.prepare_evidence_requests(records(), RetrievalQuery("Check republished inputs", ()),
                                                            [], SimpleNamespace(memo={}), len)
    assert metadata["evidence_allowance"] == 0
    for arm in contexts.ARMS:
        if arm != "full_context":
            assert requests[arm].context_text == ""
            assert requests[arm].allowed_artifact_ids == ()
    assert len(requests["full_context"].allowed_artifact_ids) == 3


def test_native_missing_bridge_is_not_repaired_by_flat_or_gold_routing(fake_indexes):
    corpus = records()
    requests, metadata = contexts.prepare_evidence_requests(corpus, RetrievalQuery("Revalidate", (ROOT,)),
        [corpus[1].id], SimpleNamespace(memo={}), len)
    assert requests["graph"].allowed_artifact_ids == (corpus[1].id,)
    assert metadata["native_graph_ids"] == [corpus[1].id]
    assert metadata["exact_flat_ids"] == [corpus[0].id, corpus[1].id]
    assert not metadata["native_flat_membership_equal"]


def test_input_order_does_not_change_frozen_prompts(fake_indexes):
    corpus = records()
    query = RetrievalQuery("Revalidate", (ROOT,))
    first, _ = contexts.prepare_evidence_requests(corpus, query, [corpus[0].id, corpus[1].id], SimpleNamespace(memo={}), len)
    second, _ = contexts.prepare_evidence_requests(list(reversed(corpus)), query, [corpus[1].id, corpus[0].id], SimpleNamespace(memo={}), len)
    assert {arm: req.prompt() for arm, req in first.items()} == {arm: req.prompt() for arm, req in second.items()}


@pytest.mark.parametrize("corpus,native", [([], []), ([records()[0], records()[0]], []), (records(), ["hidden-artifact"])])
def test_invalid_candidate_or_native_identity_fails_before_indexing(fake_indexes, corpus, native):
    with pytest.raises(ValueError):
        contexts.prepare_evidence_requests(corpus, RetrievalQuery("Task", (ROOT,)), native, SimpleNamespace(memo={}), len)
    assert fake_indexes == []


class ToyStore:
    def __init__(self, value, *, kind="source", logical_id="source:day:fx"):
        self.value = deepcopy(value)
        self.record = ArtifactRecord("old", kind, logical_id, "old-content", "now", {})

    def get_head(self, _):
        return self.record

    def read(self, _):
        return deepcopy(self.value)


class ToyRuntime:
    def __init__(self, store, *, false_flag=False, corrupt_value=False):
        self.store = store
        self.false_flag, self.corrupt_value = false_flag, corrupt_value
        self.calls = []

    def set_source(self, name, value, *_):
        old = self.store.record
        changed = canonical(self.store.value) != canonical(value)
        self.calls.append((name, deepcopy(value)))
        if changed:
            self.store.record = ArtifactRecord("new", old.kind, old.logical_id, "new-content", "later", {})
        if not self.corrupt_value:
            self.store.value = deepcopy(value)
        return SourceChange(old.logical_id, old.id, self.store.record.id, False if self.false_flag else changed)

    def remove_source(self, name):
        return self.set_source(name, None)

    def set_tool_version(self, name, version):
        return self.set_source(name, {**self.store.value, "version": version})


def case(mutation, category="source_change"):
    return RetailCase("MD-unit", "dev", "Fixed task", (mutation,), category, ("day",))


def test_independent_change_audit_rejects_false_runtime_flag():
    runtime = ToyRuntime(ToyStore({"GBP": "1.25"}), false_flag=True)
    workload = SimpleNamespace(runtime=runtime, sources={"day:fx": {"GBP": "1.25"}})
    with pytest.raises(AssertionError, match="independent canonical"):
        contexts.audit_and_apply_mutations(workload, case(RetailMutation("day:fx", "fx_set", {"GBP": "1.29"})))


def test_independent_change_audit_rejects_wrong_published_value():
    runtime = ToyRuntime(ToyStore({"GBP": "1.25"}), corrupt_value=True)
    workload = SimpleNamespace(runtime=runtime, sources={"day:fx": {"GBP": "1.25"}})
    with pytest.raises(AssertionError, match="Published input"):
        contexts.audit_and_apply_mutations(workload, case(RetailMutation("day:fx", "fx_set", {"GBP": "1.29"})))


def test_noop_roots_come_from_independent_values_and_noop_remains_audited():
    original = [{"order_id": "a", "gross_cents": 10}, {"order_id": "b", "gross_cents": 20}]
    runtime = ToyRuntime(ToyStore(original, logical_id="source:day:orders"))
    workload = SimpleNamespace(runtime=runtime, sources={"day:orders": deepcopy(original)})
    roots, sources, audit = contexts.audit_and_apply_mutations(workload, case(RetailMutation("day:orders", "reorder"), "canonical_noop"))
    assert roots == []
    assert sources["day:orders"] == original
    assert audit[0]["before_sha256"] == audit[0]["after_sha256"]
    assert not audit[0]["expected_changed"] and not audit[0]["observed_changed"]


def test_tool_version_uses_exact_declared_version_and_preserves_implementation():
    value = {"name": "convert_to_usd", "version": "1", "implementation_hash": "frozen-code"}
    runtime = ToyRuntime(ToyStore(value, kind="tool", logical_id="tool:convert_to_usd"))
    workload = SimpleNamespace(runtime=runtime, sources={})
    roots, sources, audit = contexts.audit_and_apply_mutations(workload,
        case(RetailMutation(operation="tool_version", tool="convert_to_usd", parameters={"version": "declared-v4-version"}), "tool_version"))
    assert roots == ["old"] and sources == {}
    assert runtime.store.value == {**value, "version": "declared-v4-version"}
    assert audit[0]["kind"] == "tool"


def test_unexpected_noop_is_rejected_before_publication():
    runtime = ToyRuntime(ToyStore({"GBP": "1.25"}))
    workload = SimpleNamespace(runtime=runtime, sources={"day:fx": {"GBP": "1.25"}})
    with pytest.raises(ValueError, match="undeclared no-op"):
        contexts.audit_and_apply_mutations(workload, case(RetailMutation("day:fx", "fx_set", {"GBP": "1.25"})))
    assert runtime.calls == []


def test_prepare_failure_preserved_and_output_cannot_be_reused(monkeypatch, tmp_path):
    from proofflow.eval import model_comparison_data
    sample = case(RetailMutation("day:fx", "fx_set", {"GBP": "1.29"}))
    monkeypatch.setattr(model_comparison_data, "manifest_data", lambda _: {"queries_by_case": {sample.id: sample.description}})
    def fail(*_):
        raise ConnectionError("native service unavailable")
    monkeypatch.setattr(contexts, "_build_workload", fail)
    output = tmp_path / "attempt"
    with pytest.raises(ConnectionError):
        contexts.prepare_case(output, sample, SimpleNamespace(memo={}), len)
    assert json.loads((output / "preparation_error.json").read_text())["type"] == "ConnectionError"
    with pytest.raises(FileExistsError):
        contexts.prepare_case(output, sample, SimpleNamespace(memo={}), len)


def test_query_must_match_frozen_manifest_before_runtime_creation(monkeypatch, tmp_path):
    from proofflow.eval import model_comparison_data
    sample = case(RetailMutation("day:fx", "fx_set", {"GBP": "1.29"}))
    monkeypatch.setattr(model_comparison_data, "manifest_data", lambda _: {"queries_by_case": {sample.id: "different frozen text"}})
    monkeypatch.setattr(contexts, "_build_workload", lambda *_: pytest.fail("Must not create runtime before query validation"))
    with pytest.raises(ValueError, match="frozen query"):
        contexts.prepare_case(tmp_path / "attempt", sample, SimpleNamespace(memo={}), len)


def test_prepare_persists_exact_requests_and_separate_closed_snapshot(monkeypatch, tmp_path, fake_indexes):
    """Exercise file/metadata boundaries without preparing data or connecting Hydra."""
    from proofflow.eval import model_comparison_data

    corpus = records()
    sample = case(RetailMutation("day:fx", "fx_set", {"GBP": "1.29"}))
    declarations = [RetailRecipe(record.logical_id.removeprefix("artifact:"), record.tool, {}, {},
                               record.description, "unit") for record in corpus]
    raw = [ArtifactRecord(f"raw-{i}", "artifact", record.logical_id, f"hash-{i}", "now", {})
           for i, record in enumerate(corpus)]
    old = ArtifactRecord("raw-old", "source", "source:day:orders", "old-hash", "now", {})
    saved = {record.id: record for record in [*raw, old]}
    closed = []
    store = SimpleNamespace(
        get=lambda key: saved[key], list_records=lambda: list(saved.values()),
        read=lambda key: {"private_snapshot_value": key},
        heads=lambda kind: [record for record in saved.values() if record.kind == kind])
    graph = SimpleNamespace(queries=0, mutations=0)
    runtime = SimpleNamespace(store=store, graph=graph, calls=[{"seed": "only"}],
                              affected=lambda _: raw[:2])
    workload = SimpleNamespace(runtime=runtime, recipes=declarations, graph_namespace="unit-namespace",
                               close=lambda: closed.append(True))
    fixture = {"queries_by_case": {sample.id: sample.description}, "fixture_marker": "scorer-only"}
    monkeypatch.setattr(model_comparison_data, "manifest_data", lambda _: fixture)
    monkeypatch.setattr(model_comparison_data, "candidate_names", lambda *_: {recipe.name for recipe in declarations})
    def build(directory, _):
        directory.mkdir()
        (directory / "manifest.sqlite3").write_bytes(b"closed fake SQLite bytes")
        return workload
    monkeypatch.setattr(contexts, "_build_workload", build)
    monkeypatch.setattr(contexts, "audit_and_apply_mutations", lambda *_: ([old.id], {"day:fx": {"GBP": "1.29"}}, []))
    monkeypatch.setattr(contexts, "export_evidence", lambda _: (corpus, {record.id: raw[i].id for i, record in enumerate(corpus)}))
    monkeypatch.setattr(contexts, "evidence_alias", lambda *_: ROOT)

    output = tmp_path / "attempt"
    metadata = contexts.prepare_case(output, sample, SimpleNamespace(memo={}), len)
    assert closed == [True]
    assert metadata["provider_calls"] == metadata["refresh_calls"] == 0
    snapshot_path = output / "initial_records.json"
    snapshot = json.loads(snapshot_path.read_text())
    assert snapshot["source_heads"] == {old.logical_id: old.id}
    assert snapshot["artifact_heads"] == {record.logical_id: record.id for record in raw}
    assert snapshot["records"][old.id] == {**old.to_dict(), "value": {"private_snapshot_value": old.id}}
    assert metadata["initial_records_sha256"] == hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    analytics = contexts.Path(contexts.__file__).resolve().parents[1] / "analytics.py"
    assert metadata["analytics_sha256"] == hashlib.sha256(analytics.read_bytes()).hexdigest()
    assert json.loads((output / "current_sources.json").read_text()) == {"day:fx": {"GBP": "1.29"}}
    for arm in contexts.ARMS:
        entry = metadata["requests_by_arm"][arm]
        request_data = json.loads(contexts.Path(entry["request_path"]).read_text())
        request = AgentRequest(**request_data)
        prompt = contexts.Path(entry["prompt_path"]).read_text()
        assert prompt == request.prompt()
        assert entry["request_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
        assert "private_snapshot_value" not in prompt
        assert "fixture_marker" not in prompt
        assert "initial_records" not in prompt
