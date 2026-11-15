from proofflow.eval.retrieval import (
    EvidenceRecord, direct_ids, exact_seed, lexical_tokens, pack_records,
    rank_exact_closure, read_affected, reciprocal_rank_fusion, score_sets,
)


def record(rid, inputs=(), **kwargs):
    return EvidenceRecord(rid, rid, rid, "calculate", tuple(inputs), **kwargs)


def test_reader_cannot_cross_missing_intermediate():
    a = record("regional", ["source.fx.v1"])
    b = record("company", ["regional"])
    c = record("brief", ["company"])
    assert read_affected([a, c], ["source.fx.v1"]) == {"regional": 1}
    assert read_affected([c, b, a], ["source.fx.v1"]) == {"regional": 1, "company": 2, "brief": 3}


def test_tool_versions_and_entity_binding_are_dependencies():
    records = [record("eu", ["orders.eu.v1"], tool_version_id="gross.v1"),
               record("us", ["orders.us.v1"], tool_version_id="gross.v1")]
    assert direct_ids(records, ["orders.eu.v1"]) == ["eu"]
    assert direct_ids(records, ["gross.v1"]) == ["eu", "us"]


def test_packer_skips_large_record_and_counts_actual_context():
    # A simple byte counter is injected to exercise accounting and packing;
    # production uses the specified real tokenizer.
    counter = len
    large = record("large", description="x" * 5000)
    a, b = record("a"), record("b")
    budget = len(a.render()) + len(b.render()) + 1
    packed = pack_records([large, a, a, b], budget, counter)
    assert [r.id for r in packed.records] == ["a", "b"]
    assert packed.tokens == budget
    assert packed.skipped_ids == ["large"]


def test_full_identifier_and_readable_words_are_available():
    tokens = lexical_tokens("EUR_USD source.fx.v1 customer-revenue")
    assert "source.fx.v1" in tokens
    assert "fx" in tokens
    assert "eur_usd" in tokens
    assert "customer" in tokens


def test_empty_gold_does_not_hide_false_alarms():
    assert score_sets([], ["unrelated"])["exact_match"] is False
    assert score_sets([], ["unrelated"])["fp"] == 1
    assert score_sets([], [])["f1"] == 1.0


def test_exact_seed_cannot_add_unknown_records():
    records = [record("x", ["changed"]), record("y", ["other"])]
    assert exact_seed(["y", "x"], records, ["changed"]) == ["x", "y"]
    assert rank_exact_closure(records, ["changed"]) == ["x"]


def test_rrf_is_deterministic_with_ties():
    assert reciprocal_rank_fusion([["b", "a"], ["a", "b"]]) == ["a", "b"]
