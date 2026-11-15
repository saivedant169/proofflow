# ProofFlow

**Current evidence for analytics agents.** ProofFlow records the inputs actually consumed by analytics tools, uses HydraDB to find the consequences of a change, and refreshes affected results across agent runs.

Build status: backend and benchmark development. No performance advantage is claimed yet. User-interface work is gated on a fair comparison against BM25 and real dense retrieval.

## Local setup

Requires Docker, Python 3.12 and `uv`.

```sh
python3 scripts/init_local.py
docker compose up -d
uv venv --python 3.12
uv pip install -e '.[test,benchmark]'
.venv/bin/python scripts/hydra_smoke.py --restart
.venv/bin/python -m pytest -q
```

The database is the official HydraDB OSS v0.4.0 image, pinned by digest. Local database listeners bind only to localhost. The generated `.env` and `.state/` credentials/data are excluded from Git. Use a persistent volume and authenticated TLS ingress for a hosted application; do not expose the database listener publicly.

## Evidence, rather than a preselected winning result

- [Benchmark specification](docs/BENCHMARK_SPEC.md): shared information, development/test separation, actual embeddings, exact dependency controls, and independent output checks.
- [HydraDB integration evidence](evidence/hydra_smoke.json): real writes, native multi-hop paths, idempotent edges, persisted reads and new writes after database restart.
- [Delivery research](docs/DELIVERY_RESEARCH.md): exact event identity, verified upstream image, and unresolved organizer details.

The initial workload uses authored commerce data and staged corrections, processed by actual local tools. A graph algorithm implemented in a flat adjacency store may match correctness. The intended experiment tests explicit dependencies versus similarity retrieval; it does not assume a unique storage-engine advantage.

## License

ProofFlow application code is MIT-licensed. HydraDB is a separate upstream dependency; its release license applies independently. We do not relicense the database.
