# Development pilot results

**Scope:** six predeclared development scenarios, not held-out results and not an LLM-agent experiment. All calculations and refreshes executed through the real HydraDB-backed runtime. Dense retrieval used real BAAI/bge-small-en-v1.5 ONNX embeddings with complete overlapping chunks.

| Arm | Evidence budget | Mean affected recall | Exact affected sets | Fresh affected reports | Cases with all eligible reports fresh | Mean evidence tokens |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 2048 | 38.7% | 1/6 | 3/17 | 1/6 | 1,980 |
| dense | 2048 | 28.0% | 0/6 | 0/17 | 0/6 | 2,012 |
| hybrid | 2048 | 37.3% | 0/6 | 2/17 | 0/6 | 1,950 |
| iterative_hybrid | 2048 | 56.9% | 1/6 | 4/17 | 1/6 | 1,965 |
| graph | 2048 | 84.1% | 3/6 | 9/17 | 3/6 | 1,709 |
| exact_flat | 2048 | 84.1% | 3/6 | 9/17 | 3/6 | 1,709 |
| full_context | all | 100.0% | 6/6 | 17/17 | 6/6 | 8,466 |

The full native Hydra closure matched the independently authored dependency oracle in all six cases before context packing. Under the same finite evidence budget, broad changes can exceed the pack size; the graph is not perfect at 2,048 tokens. Exact flat traversal ties its correctness. Full context makes all complete retrieval conditions tie, at roughly 8,466 tokens.

All arms use the same Hydra-assisted currentness and recursive refresh executor. Unselected stale reports remain unresolved/blocked rather than being counted as stale answers served. This comparison isolates evidence selection; standalone BM25/vector-store safety is not evaluated.

The numeric oracle uses independent Python calculations over current fixture inputs; it does not call runtime SQLite arithmetic or graph queries. All baseline indexes receive the same direct provenance, readable identifiers and current version metadata. Standard exact-ID seeding and iterative hybrid retrieval are included.

Run fixture/config manifest: `408255c4a93185b7124fe1f213fe76c448eceeae2323fa5bba1f7e7725d21ff4`. The later manifest adds an explicit shared-executor disclosure; it does not change the algorithms or scenarios used here.

Reproduction command:

```sh
.venv/bin/python -m proofflow.eval.runner --split dev --output results/dev-reproduction
```

Raw files: `results/dev-v1/retrieval.jsonl`, `results/dev-v1/execution.jsonl`, `results/dev-v1/run_manifest.json`, and per-case frozen contexts/receipt mappings. A reproduction records its own current frozen manifest and must use a new output directory. No development result establishes a broad win or a held-out claim.
