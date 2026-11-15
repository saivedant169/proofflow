# ProofFlow

**Current evidence for analytics agents.** ProofFlow records the inputs actually consumed by analytics tools, uses HydraDB to find the consequences of a change, and refreshes affected results across agent runs.

The core runs against real HydraDB and passes persisted write/traversal/restart checks. In a frozen pilot of 12 authored changing-data scenarios at 2,048 evidence tokens, it refreshed **16/29 affected reports**, compared with **6/29 for BM25**, **1/29 for dense BGE**, and **9/29 for iterative hybrid**. Interface and delivery work is in progress.

The exact flat dependency-traversal control ties ProofFlow. All retrieval methods use the same Hydra-assisted safe executor; this establishes a useful dependency-selection advantage in this workload, not a unique storage-engine advantage or universal graph superiority. The all-record context completes 29/29. See the [complete results, failures and budget ladder](docs/BENCHMARK_RESULTS.md).

## Local setup

Requires Docker, Python 3.12 and `uv`.

```sh
python3 scripts/init_local.py
docker compose up -d
uv venv --python 3.12
uv pip install -e '.[test,benchmark]'
.venv/bin/python scripts/hydra_smoke.py --restart
.venv/bin/python scripts/core_smoke.py
.venv/bin/python -m pytest -q
```

The database is the official HydraDB OSS v0.4.0 image, pinned by digest. Local database listeners bind only to localhost. The generated `.env` and `.state/` credentials/data are excluded from Git. Use a persistent volume and authenticated TLS ingress for a hosted application; do not expose the database listener publicly.

## Evidence, rather than a preselected winning result

- [Benchmark specification](docs/BENCHMARK_SPEC.md): shared information, development/test separation, actual embeddings, exact dependency controls, and independent output checks.
- [HydraDB integration evidence](evidence/hydra_smoke.json): real writes, native multi-hop paths, idempotent edges, persisted reads and new writes after database restart.
- [Core execution evidence](evidence/core_smoke.json): actual calculations, cross-run reuse, version rebinding, unchanged work preservation, and missing-source refusal.
- [Held-out results](docs/BENCHMARK_RESULTS.md): frozen fixtures, exact input records, real dense embeddings, actual refreshes, and independent numeric checks.

The initial workload uses authored commerce data and staged corrections, processed by actual local tools. A graph algorithm implemented in a flat adjacency store may match correctness. The intended experiment tests explicit dependencies versus similarity retrieval; it does not assume a unique storage-engine advantage.

## License

ProofFlow application code is MIT-licensed. HydraDB is a separate upstream dependency; its release license applies independently. We do not relicense the database.
