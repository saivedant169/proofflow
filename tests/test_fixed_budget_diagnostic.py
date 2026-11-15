from collections import Counter
from contextlib import closing
from dataclasses import replace

from proofflow.artifacts import ArtifactStore
from proofflow.eval.retrieval import EvidenceRecord, RetrievalQuery, render_context
from proofflow.runtime import ProofFlowRuntime
from scripts import fixed_budget_diagnostic as diagnostic
from scripts.fixed_budget_diagnostic import Cell, publish_receipt_graph, restore_store, schedule, sha, summarize
from scripts.fixed_budget_diagnostic import plan_cell


def test_frozen_schedule_keeps_both_caps_and_one_uncapped_reference_per_case():
    cells = schedule()
    assert len(cells) == len(set(cells)) == 88
    assert Counter(cell.cap for cell in cells) == {4096: 40, 8192: 40, None: 8}
    assert list(dict.fromkeys(cell.case_id for cell in cells)) == [f"M{i:02}" for i in range(1, 9)]
    for index, case_id in enumerate(dict.fromkeys(cell.case_id for cell in cells)):
        cases = [cell for cell in cells if cell.case_id == case_id]
        assert len(cases) == 11
        assert cases[0].arm == ("graph", "exact_flat", "bm25", "dense", "iterative_hybrid", "full_context")[index % 6]
        assert [cell.arm for cell in cases if cell.cap is None] == ["full_context"]


def test_fixed_cap_hashes_exact_joined_context_and_reader_cannot_cross_omitted_record():
    large = EvidenceRecord("a_large", "Large", "artifact:large", "tool", ("root",), description="§" * 1500)
    small = EvidenceRecord("b_small", "Small", "artifact:small", "tool", ("root",))
    indirect = EvidenceRecord("c_indirect", "Indirect", "artifact:indirect", "tool", ("a_large",))
    records = [large, small, indirect]
    query = RetrievalQuery("Correct a source", ("root",))
    context_expected = render_context([small, indirect])

    def counter(text):
        return len(text.encode())

    cap = counter(context_expected)
    native = {record.id for record in records}
    for arm in ("graph", "exact_flat"):
        context, plan = plan_cell(Cell("synthetic", arm, cap), records, query, native, None, None, counter)
        assert context == context_expected
        assert plan["evidence_tokens"] == cap
        assert plan["context_sha256"] == sha(context_expected)
        assert plan["retrieved_aliases"] == ["b_small", "c_indirect"]
        assert plan["selected_aliases"] == ["b_small"]
        assert plan["skipped_aliases"] == ["a_large"]


def test_reconstructed_store_preserves_original_records_and_receipt_edges(tmp_path):
    with closing(ArtifactStore(tmp_path / "original")) as original:
        source = original.prepare("source", "source:a", {"v": 1})
        tool = original.prepare("tool", "tool:test", "v1")
        output = original.prepare("artifact", "artifact:b", 1, identity="invocation")
        inputs = {"a": source.id}
        receipt_value = {"output_id": output.id, "inputs": inputs, "tool_version_id": tool.id}
        receipt = original.prepare("execution", "execution:invocation", receipt_value)
        output = replace(output, metadata={"receipt_id": receipt.id, "inputs": inputs, "tool_version_id": tool.id})
        values = [(source, {"v": 1}), (tool, "v1"), (output, 1), (receipt, receipt_value)]
        anchor = {
            "records": {record.id: {**record.to_dict(), "value": value} for record, value in values},
            "source_heads": {source.logical_id: source.id},
            "tool_heads": {tool.logical_id: tool.id},
            "artifact_heads": {output.logical_id: output.id},
        }

        class Graph:
            def __init__(self):
                self.nodes = set()
                self.edges = set()

            def put_node(self, identifier, kind, properties):
                self.nodes.add(identifier)

            def put_edge(self, source_id, target_id, kind):
                assert {source_id, target_id} <= self.nodes
                self.edges.add((source_id, target_id, kind))

        with closing(ArtifactStore(tmp_path / "restored")) as restored:
            restore_store(restored, anchor)
            assert restored.workspace == original.workspace
            for record, value in values:
                assert restored.get(record.id) == record
                assert restored.read(record.id) == value
            graph = Graph()
            publish_receipt_graph(ProofFlowRuntime(restored, graph))
        assert graph.nodes == set(anchor["records"])
        assert graph.edges == {(source.id, receipt.id, "CONSUMED"), (tool.id, receipt.id, "USED_TOOL"),
                               (receipt.id, output.id, "PRODUCED")}


def test_missing_cells_leave_known_obligations_and_unknown_observations():
    oracles = {cell.case_id: {"affected_names": ["a", "b"]} for cell in schedule()}
    rows = {cell: {**cell.identity(), "status": "unattempted",
                   "planned_report_counts": {"eligible_affected_reports": 1, "unavailable_reports": 0,
                                             "unaffected_reports": 2}} for cell in schedule()}
    summary = summarize(rows, oracles, integrity=True)
    group = next(row for row in summary["groups"] if row["arm"] == "graph" and row["cap"] == 4096)
    assert summary["status_counts"] == {"unattempted": 88}
    assert not summary["complete"]
    assert group["planned_denominators"] == {"eligible_affected": 8, "unavailable": 0, "unaffected": 16,
                                             "affected_artifacts": 16}
    assert group["reports_observed"]["fresh_affected"] is None
    assert group["reports_observed"]["incorrect_current"] is None
    assert not group["absolute_report_gate"]


def test_failed_shared_dependency_does_not_start_dependent_plan(tmp_path, monkeypatch):
    record = EvidenceRecord("one", "One", "artifact:one", "tool", ("root",))
    query = RetrievalQuery("Correct source", ("root",))
    monkeypatch.setattr(diagnostic, "load_case", lambda *args: ({}, [record], query))

    def failed_graph(*args):
        raise RuntimeError("synthetic graph lookup failure")

    monkeypatch.setattr(diagnostic, "native_membership", failed_graph)
    monkeypatch.setattr(diagnostic, "case_indexes", lambda *args: ({}, {}))
    graph = Cell("synthetic", "graph", 4096)
    flat = Cell("synthetic", "exact_flat", 4096)
    rows = {cell: {**cell.identity(), "status": "unattempted"} for cell in (graph, flat)}
    diagnostic.plan_case("synthetic", tmp_path / "public", tmp_path / "private", [graph, flat], rows,
                         "id", None, len, {"affected_aliases": ["one"]})
    assert rows[graph]["status"] == "unattempted"
    assert rows[graph]["dependency_error"]["component"] == "native_discovery"
    assert "planning_started_at" not in rows[graph]
    assert rows[flat]["status"] == "planned"
    setup = diagnostic.load(tmp_path / "public/synthetic/setup.json")
    assert setup["status"] == "partial"
    assert setup["native_error"]["type"] == "RuntimeError"


def test_resource_preflight_failure_preserves_unattempted_rows_and_fails_integrity(tmp_path, monkeypatch):
    root = tmp_path / "root"
    monkeypatch.setattr(diagnostic, "ROOT", root)
    monkeypatch.setattr(diagnostic, "git", lambda *args: b"synthetic")
    monkeypatch.setattr(diagnostic, "verify_frozen_inputs", lambda *args: None)
    monkeypatch.setattr(diagnostic, "verify_local_hydra", lambda: None)

    def missing_cache(*args):
        raise FileNotFoundError("synthetic missing cache")

    monkeypatch.setattr(diagnostic, "local_resources", missing_cache)
    oracles = {cell.case_id: {"affected_names": [], "counts": {
        "eligible_affected_reports": 1, "unavailable_reports": 0, "unaffected_reports": 2,
    }} for cell in schedule()}
    diagnostic.store_json(root / diagnostic.FREEZE, {
        "oracle": oracles, "hydra": {}, "package_versions": {}, "embedding": {}, "embedding_snapshot": {},
    })
    output = root / "public"
    assert not diagnostic.run("synthetic", output, tmp_path / "private", tmp_path / "cache")
    summary = diagnostic.load(output / "summary.json")
    assert summary["source_integrity_verified"]
    assert not summary["resource_integrity_verified"]
    assert not summary["freeze_integrity_verified"]
    assert summary["status_counts"] == {"unattempted": 88}
    row = diagnostic.load(output / schedule()[0].path / "attempt.json")
    assert row["dependency_error"]["component"] == "shared_environment"
