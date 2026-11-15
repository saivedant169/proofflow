"""Record actual HydraDB graph operations and optional persistent restart proof."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
import uuid

from proofflow.graph import HydraGraph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--output", default="evidence/hydra_smoke.json")
    args = parser.parse_args()
    namespace = "smoke-" + uuid.uuid4().hex[:12]
    start = time.monotonic()
    checks = {}
    with HydraGraph(namespace=namespace) as graph:
        for key, kind in [("source", "source"), ("run1", "execution"), ("metric", "artifact"),
                          ("run2", "execution"), ("report", "artifact"), ("unrelated", "artifact")]:
            graph.put_node(key, kind, {"label": key, "probe": namespace})
        edges = [("source", "run1"), ("run1", "metric"), ("metric", "run2"), ("run2", "report")]
        for _ in range(2):
            for a, b in edges:
                graph.put_edge(a, b, "DEPENDENCY")
        descendants = graph.descendants(["source"])
        ancestors = graph.ancestors(["report"])
        checks["multi_hop_descendants"] = descendants == ["metric", "report", "run1", "run2"]
        checks["multi_hop_ancestors"] = ancestors == ["metric", "run1", "run2", "source"]
        paths = graph.paths("source", "report")
        checks["native_path_evidence"] = bool(paths) and len(paths[0]["relationships"]) == 4
        count = graph.query("MATCH (a {id: $id})-[:FLOW]->(b) RETURN count(b.id) AS count",
                            {"id": graph.vertex_id("source")})[0]["count"]
        checks["idempotent_edge_write"] = count == 1
        checks["unrelated_output_excluded"] = "unrelated" not in descendants
        before = graph.get_node("report")
        queries_before_restart = graph.queries
    if args.restart:
        subprocess.run(["docker", "compose", "restart", "-t", "5", "hydradb"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 45
        while True:
            try:
                with HydraGraph(namespace=namespace, timeout=5) as fresh:
                    after = fresh.get_node("report")
                    if after != before:
                        raise RuntimeError("Persisted artifact metadata changed after restart")
                    checks["restart_metadata"] = True
                    checks["restart_traversal"] = fresh.descendants(["source"]) == descendants
                    fresh.put_node("post-restart", "artifact", {"created_after_restart": True})
                    checks["write_after_restart"] = fresh.get_node("post-restart") is not None
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.25)
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "namespace": namespace,
              "backend": "HydraDB OSS 0.4.0", "commit": "916637477f3f34766b4905b270bd4292109d77e6",
              "image_digest": "sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880",
              "storage": "CLOUD_PROVIDER=local, Docker named persistent volume",
              "restart_requested": args.restart, "graph_replayed_from_application": False,
              "checks": checks, "passed": all(checks.values()), "native_queries": queries_before_restart,
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "descendants": descendants, "ancestors": ancestors, "example_native_path": paths[0]}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": checks, "evidence": str(output),
                      "elapsed_seconds": result["elapsed_seconds"]}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
