"""Runtime correctness checks; graph doubles are explicitly unit-test-only."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from proofflow.analytics import DEMO_SOURCES
from proofflow.artifacts import ArtifactStore
from proofflow.models import MissingEvidenceError
from proofflow.runtime import ProofFlowRuntime


class UnitTestGraph:
    """A transparent test double, never selected by production code."""
    def __init__(self):
        self.nodes = {}
        self.edges = set()
        self.reads = 0
        self.fail = False

    def put_node(self, node_id, kind, properties):
        if self.fail:
            raise ConnectionError("graph unavailable")
        self.nodes[node_id] = (kind, properties)

    def put_edge(self, source_id, target_id, kind, properties=None):
        if self.fail:
            raise ConnectionError("graph unavailable")
        self.edges.add((source_id, target_id, kind))

    def _walk(self, nodes, reverse, max_depth):
        if self.fail:
            raise ConnectionError("graph unavailable")
        self.reads += 1
        seen = set(nodes)
        frontier = set(nodes)
        for _ in range(max_depth):
            next_frontier = {a if reverse else b for a, b, _ in self.edges
                             if (b if reverse else a) in frontier} - seen
            if not next_frontier:
                return sorted(seen - set(nodes))
            seen.update(next_frontier)
            frontier = next_frontier
        raise RuntimeError("test graph depth exceeded")

    def ancestors(self, node_ids, max_depth=32):
        return self._walk(node_ids, True, max_depth)

    def descendants(self, node_ids, max_depth=32):
        return self._walk(node_ids, False, max_depth)


def build_fixture(runtime):
    sources = {name: runtime.set_source(name, value).current_id for name, value in DEMO_SOURCES.items()}
    nodes = {}
    nodes["gross"] = runtime.execute("gross_by_region", {"orders": sources["orders"]}, logical_id="metric:gross", run_id="run-A")
    nodes["refunds"] = runtime.execute("refunds_by_region", {"orders": sources["orders"], "refunds": sources["refunds"]}, logical_id="metric:refunds", run_id="run-A")
    nodes["net"] = runtime.execute("net_by_region", {"gross": nodes["gross"].id, "refunds": nodes["refunds"].id}, logical_id="metric:net", run_id="run-A")
    nodes["regional"] = runtime.execute("convert_to_usd", {"net": nodes["net"].id, "fx": sources["fx"]}, logical_id="metric:regional", run_id="run-A")
    nodes["company"] = runtime.execute("company_total", {"regional": nodes["regional"].id}, logical_id="metric:company", run_id="run-A")
    nodes["support"] = runtime.execute("support_by_region", {"tickets": sources["tickets"]}, logical_id="metric:support", run_id="run-A")
    nodes["report_a"] = runtime.execute("compose_report", {"revenue": nodes["company"].id, "support": nodes["support"].id}, {
        "title": "Company weekly report", "sections": [
            {"key": "company_revenue", "label": "Company revenue", "input": "revenue", "path": ["usd_cents"], "unit": "USD cents"},
            {"key": "eu_support", "label": "EU support tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
        ]}, logical_id="report:company", run_id="run-A")
    nodes["report_b"] = runtime.execute("compose_report", {"revenue": nodes["regional"].id, "support": nodes["support"].id}, {
        "title": "EU operations brief", "sections": [
            {"key": "eu_revenue", "label": "EU revenue", "input": "revenue", "path": ["regions", "EU", "usd_cents"], "unit": "USD cents"},
            {"key": "eu_support", "label": "EU support tickets", "input": "support", "path": ["regions", "EU", "tickets"], "unit": "tickets"},
        ]}, logical_id="report:eu", run_id="run-B")
    return sources, nodes


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ArtifactStore(self.temp.name)
        self.graph = UnitTestGraph()
        self.runtime = ProofFlowRuntime(self.store, self.graph)
        self.sources, self.nodes = build_fixture(self.runtime)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_cross_run_revalidation_rebinds_new_intermediate_and_preserves_support(self):
        original_support = self.store.read(self.nodes["support"].id)
        change = self.runtime.set_source("fx", {**DEMO_SOURCES["fx"], "EUR": "1.20"})
        affected = {node.logical_id for node in self.runtime.affected([change.previous_id])}
        self.assertEqual(affected, {"metric:regional", "metric:company", "report:company", "report:eu"})
        self.assertEqual(self.runtime.currentness(self.nodes["report_b"].id).state, "stale")
        self.assertTrue(self.runtime.currentness(self.nodes["support"].id).is_current)
        expected = {key: self.runtime.full_recompute(self.nodes[key].id) for key in ["report_a", "report_b"]}
        start = len(self.runtime.calls)
        refreshed = self.runtime.refresh([self.nodes["report_a"].id, self.nodes["report_b"].id])
        self.assertEqual(len(self.runtime.calls) - start, 4)
        for key in ["report_a", "report_b"]:
            output_id = refreshed.replacements[self.nodes[key].id]
            self.assertEqual(self.store.read(output_id), expected[key])
            self.assertTrue(self.runtime.currentness(output_id).is_current)
        new_regional = refreshed.replacements[self.nodes["regional"].id]
        new_report_b = self.store.get(refreshed.replacements[self.nodes["report_b"].id])
        self.assertEqual(new_report_b.metadata["inputs"]["revenue"], new_regional)
        self.assertNotEqual(new_regional, self.nodes["regional"].id)
        self.assertEqual(self.store.get_head("metric:support").id, self.nodes["support"].id)
        self.assertEqual(self.store.read(self.nodes["support"].id), original_support)
        self.assertEqual(self.store.read(new_regional)["regions"]["EU"]["usd_cents"], 228000)

    def test_application_restart_retains_content_and_checks_graph(self):
        self.store.close()
        self.store = ArtifactStore(self.temp.name)
        self.runtime = ProofFlowRuntime(self.store, self.graph)
        reads_before = self.graph.reads
        self.assertTrue(self.runtime.currentness(self.nodes["report_b"].id).is_current)
        self.assertGreater(self.graph.reads, reads_before)
        self.assertEqual(self.store.read(self.nodes["company"].id), {"usd_cents": 556500})

    def test_graph_unavailable_never_falls_back_to_local_manifests(self):
        self.graph.fail = True
        with self.assertRaises(ConnectionError):
            self.runtime.currentness(self.nodes["company"].id)
        with self.assertRaises(ConnectionError):
            self.runtime.affected([self.sources["fx"]])

    def test_failed_graph_write_does_not_publish_new_source_or_artifact(self):
        source_head = self.store.get_head("source:fx").id
        self.graph.fail = True
        with self.assertRaises(ConnectionError):
            self.runtime.set_source("fx", {"USD": "2.0"})
        self.assertEqual(self.store.get_head("source:fx").id, source_head)

    def test_missing_blob_and_missing_lineage_are_unknown(self):
        record = self.nodes["regional"]
        (self.store.blobs / f"{record.content_hash}.json").unlink()
        self.assertEqual(self.runtime.currentness(record.id).state, "unknown")
        with self.assertRaises(MissingEvidenceError):
            self.runtime.refresh([record.id])
        receipt = self.nodes["support"].metadata["receipt_id"]
        self.graph.edges = {edge for edge in self.graph.edges if edge[1] != receipt}
        self.assertEqual(self.runtime.currentness(self.nodes["support"].id).state, "unknown")

    def test_unchanged_numeric_output_still_requires_dependency_revalidation(self):
        # An unrelated currency within the same source is conservatively tracked.
        change = self.runtime.set_source("fx", {**DEMO_SOURCES["fx"], "JPY": "0.006"})
        self.assertTrue(change.changed)
        self.assertEqual(self.runtime.currentness(self.nodes["company"].id).state, "stale")
        original = self.store.read(self.nodes["company"].id)
        self.assertEqual(self.runtime.full_recompute(self.nodes["company"].id), original)
        refreshed = self.runtime.refresh([self.nodes["company"].id])
        self.assertEqual(self.store.read(refreshed.replacements[self.nodes["company"].id]), original)

    def test_tool_version_change_propagates_and_reexecutes(self):
        change = self.runtime.set_tool_version("convert_to_usd", "2")
        affected = {x.logical_id for x in self.runtime.affected([change.previous_id])}
        self.assertEqual(affected, {"metric:regional", "metric:company", "report:company", "report:eu"})
        result = self.runtime.refresh([self.nodes["report_b"].id])
        new_regional = self.store.get(result.replacements[self.nodes["regional"].id])
        self.assertEqual(new_regional.metadata["tool_version_id"], change.current_id)

    def test_missing_source_fails_closed(self):
        self.runtime.remove_source("fx")
        self.assertEqual(self.runtime.currentness(self.nodes["report_b"].id).state, "stale")
        with self.assertRaises(MissingEvidenceError):
            self.runtime.refresh([self.nodes["report_b"].id])
        with self.assertRaises(MissingEvidenceError):
            self.runtime.full_recompute(self.nodes["report_b"].id)

    def test_repeated_refresh_reuses_current_artifacts(self):
        before = len(self.runtime.calls)
        result = self.runtime.refresh([self.nodes["report_b"].id])
        self.assertEqual(result.replacements[self.nodes["report_b"].id], self.nodes["report_b"].id)
        self.assertEqual(len(self.runtime.calls), before)
        self.assertEqual(result.executed, ())

    def test_repeated_old_handle_refresh_after_reopen_reports_reuse(self):
        self.runtime.set_source("fx", {**DEMO_SOURCES["fx"], "EUR": "1.20"})
        old_report = self.nodes["report_b"].id
        first = self.runtime.refresh([old_report])
        current_report = first.replacements[old_report]
        self.store.close()
        self.store = ArtifactStore(self.temp.name)
        self.runtime = ProofFlowRuntime(self.store, self.graph)
        before = len(self.runtime.calls)
        second = self.runtime.refresh([old_report])
        self.assertEqual(len(self.runtime.calls) - before, 0)
        self.assertEqual(second.executed, ())
        self.assertEqual(second.replacements[old_report], current_report)
        self.assertIn(current_report, second.reused)

    def test_failed_tool_never_publishes_output(self):
        bad = self.runtime.set_source("bad-fx", {"EUR": "NaN", "USD": "1", "GBP": "1"})
        with self.assertRaises(ValueError):
            self.runtime.execute("convert_to_usd", {"net": self.nodes["net"].id, "fx": bad.current_id}, logical_id="metric:bad")
        self.assertIsNone(self.store.get_head("metric:bad"))
        self.assertEqual(self.runtime.calls[-1]["status"], "failed")

    def test_changed_implementation_invalidates_before_any_execute_without_mutation(self):
        prior = self.store.get_head("tool:company_total").id
        node_count = len(self.graph.nodes)
        self.runtime._implementation_hash = "new-code-fingerprint"
        status = self.runtime.currentness(self.nodes["company"].id)
        self.assertEqual(status.state, "stale")
        self.assertTrue(any(reason["reason"] == "implementation_changed" for reason in status.reasons))
        self.assertEqual(self.store.get_head("tool:company_total").id, prior)
        self.assertEqual(len(self.graph.nodes), node_count)
        refreshed = self.runtime.refresh([self.nodes["company"].id])
        self.assertTrue(self.runtime.currentness(refreshed.replacements[self.nodes["company"].id]).is_current)
        self.assertNotEqual(self.store.get_head("tool:company_total").id, prior)

    def test_independent_report_claim_remains_current_after_fx_change(self):
        self.runtime.set_source("fx", {**DEMO_SOURCES["fx"], "EUR": "1.20"})
        claims = {claim["key"]: claim for claim in self.runtime.report_claims(self.nodes["report_b"].id)}
        self.assertEqual(claims["eu_revenue"]["state"], "stale")
        self.assertIsNone(claims["eu_revenue"]["value"])
        self.assertEqual(claims["eu_revenue"]["saved_value"], 209000)
        self.assertEqual(claims["eu_support"]["state"], "current")
        self.assertEqual(claims["eu_support"]["value"], 2)


if __name__ == "__main__":
    unittest.main()
