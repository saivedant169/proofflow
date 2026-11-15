"""Pilot-v1 settings frozen before evaluation, not chosen from test results."""

DEFAULT_CONFIG = {
    "benchmark_version": "pilot-v1",
    "budgets": [512, 1024, 2048],
    "main_budget": 2048,
    "tokenizer": "cl100k_base",
    "dense_model": "BAAI/bge-small-en-v1.5",
    "dense_chunk_tokens": 384,
    "dense_chunk_overlap": 64,
    "dense_document_score": "maximum cosine across all overlapping chunks",
    "bm25": {"k1": 1.5, "b": 0.75},
    "rrf_constant": 60,
    "iterative_rounds": 4,
    "iterative_round_width": 3,
    "exact_id_seeding": True,
    "record_serialization": "EvidenceRecord.render/v1",
    "evidence_aliases": "human-readable logical_id plus immutable version suffix; all arms identical",
    "reader": "deterministic transitive reader restricted to returned evidence",
    "graph_depth": 15,
    "execution_arms": ["bm25", "dense", "hybrid", "iterative_hybrid", "graph", "exact_flat", "full_context"],
    "heldout_composition_status": "deterministic recipe pilot; not agent-chosen until separate agent run",
    "claim": "small authored retrieval-and-refresh pilot, not universal graph-store superiority",
}
