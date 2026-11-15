"""Verify the packaged app over HTTP, including optional container restart."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18080")
    parser.add_argument("--restart-app", action="store_true")
    parser.add_argument("--output", default="evidence/deployment_smoke.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks: dict[str, bool] = {}
    started = time.perf_counter()
    failure = None

    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)

    def values(state):
        return {claim["key"]: claim["value"] for report in state["reports"] for claim in report["claims"]}

    with httpx.Client(base_url=args.url, timeout=45) as client:
        def ready():
            for _ in range(50):
                try:
                    response = client.get("/health")
                    if response.status_code == 200:
                        return response.json()
                except httpx.HTTPError:
                    pass
                time.sleep(.2)
            raise AssertionError("Packaged app did not become healthy")

        def post(path, body=None):
            response = client.post(path, json=body or {})
            response.raise_for_status()
            return response.json()

        try:
            check("health_reads_real_hydra", ready()["backend"] == "HydraDB OSS")
            page = client.get("/")
            check("built_interface_served", page.status_code == 200 and "ProofFlow" in page.text)
            assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
            check("compiled_assets_load", bool(assets) and all(client.get(path).status_code == 200 for path in assets))
            check("unknown_api_is_not_spa", client.get("/api/unknown-route").status_code == 404)
            state = post("/api/session")
            initial_generation = state["generation"]
            check("initial_actual_values", values(state) == {"company_revenue": 556500, "eu_revenue": 209000, "eu_support": 2})
            state = post("/api/change", {"kind": "fx", "value": "1.20"})
            check("changed_claims_withheld", values(state) == {"company_revenue": None, "eu_revenue": None, "eu_support": 2})
            check("native_impact_four_artifacts", len(state["impact"]["affected_artifacts"]) == 4)
            state = post("/api/refresh")
            report_ids = [report["id"] for report in state["reports"]]
            check("correct_refreshed_values", values(state) == {"company_revenue": 575500, "eu_revenue": 228000, "eu_support": 2})
            check("four_actual_tools_and_support_preserved", state["last_refresh"]["executed_count"] == 4 and state["last_refresh"]["unchanged_support"])
            check("independent_refresh_parity", post("/api/verify")["passed"])
            if args.restart_app:
                subprocess.run(["docker", "compose", "-f", "docker-compose.yml", "-f", "compose.app.yml", "restart", "app"],
                               cwd=root, check=True, timeout=60, capture_output=True, text=True)
                ready()
                response = client.get("/api/state")
                response.raise_for_status()
                state = response.json()
                check("app_restart_preserves_browser_session", state["generation"] == initial_generation)
                check("app_restart_preserves_artifact_ids", [report["id"] for report in state["reports"]] == report_ids)
                check("app_restart_reads_current_values", values(state) == {"company_revenue": 575500, "eu_revenue": 228000, "eu_support": 2})
            post("/api/change", {"kind": "remove", "source": "fx"})
            check("missing_source_refresh_refused", client.post("/api/refresh", json={}).status_code == 409)
            response = client.get("/api/state")
            response.raise_for_status()
            check("missing_source_never_serves_current_revenue", values(response.json()) == {"company_revenue": None, "eu_revenue": None, "eu_support": 2})
            state = post("/api/reset")
            check("reset_recovers_new_generation", state["generation"] != initial_generation and values(state)["company_revenue"] == 556500)
        except Exception as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}

    result = {"passed": failure is None and all(checks.values()), "checks": checks, "failure": failure,
              "tested_at": datetime.now(timezone.utc).isoformat(), "url": args.url,
              "app_restart_requested": args.restart_app, "elapsed_seconds": round(time.perf_counter() - started, 3),
              "scope": "Actual HTTP requests to the built application container, pinned HydraDB, persistent app volume; no model calls."}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
