# ProofFlow deployment

The packaged application runs locally at **http://127.0.0.1:18080**. Its production frontend build, FastAPI API, pinned HydraDB container and persistent application volume passed **16/16 HTTP deployment checks**, including an application-container restart. [Deployment evidence](../evidence/deployment_smoke.json) records the run at 2026-11-15 10:18 UTC. Public deployment is pending the user's existing hosting target; no public URL is claimed here.

The [source repository](https://github.com/saivedant169/proofflow) remains **private until the user explicitly directs release**. Deploying the app does not require changing repository visibility.

## Start the complete local stack

From the project root, with Docker Compose available:

```sh
python3 scripts/init_local.py
docker compose -f docker-compose.yml -f compose.app.yml up -d --build
```

Open http://127.0.0.1:18080. The application builds React, Vite and TypeScript into static assets and serves them from the same FastAPI process as the JSON API. The actual container command is:

```sh
/app/.venv/bin/uvicorn proofflow.api:app --host 0.0.0.0 --port 8000 --workers 1
```

Use **one worker and one application replica**. Session mutation locks are process-local; multi-worker and multi-instance operation are not supported by this deployment. `GET /health` performs a real authenticated HydraDB read and returns 503 when that dependency is unavailable. There is no in-memory graph fallback.

`init_local.py` creates `.state/hydra-token` and `.env` only if absent, without printing credentials. The Compose secret mounts that token read-only at `/run/secrets/hydra_token` in both services. Keep the token readable by UID 10001. The generated local files are excluded from Git and the application image.

## Runtime configuration and storage

| Component | Actual configuration | Operational requirement |
|---|---|---|
| HydraDB OSS | Official v0.4.0 image pinned below; `CLOUD_PROVIDER=local`; `/state/store` and `/state/cache` | Persist the `hydra-state` volume mounted at `/state` |
| API and frontend | Python 3.12, `proofflow.api:app`; built assets at `/app/frontend/dist` | One worker/replica; application port 8000 |
| Graph connection | `PROOFFLOW_HYDRA_URL=http://hydradb:8443`; `PROOFFLOW_HYDRA_TOKEN_FILE=/run/secrets/hydra_token` | Private service network and matching database token |
| Application state | `PROOFFLOW_STATE_DIR=/data/sessions`; `app-state` volume at `/data` | Persist SQLite manifests and artifact blobs together, with UID/GID 10001 ownership |
| Session capacity | `PROOFFLOW_MAX_SESSIONS=16`; `PROOFFLOW_SESSION_TTL_SECONDS=3600` | Sixteen active sessions by default; idle sessions expire after one hour |
| Cookie | HttpOnly, SameSite=Strict; local HTTP defaults to non-Secure | Set `PROOFFLOW_COOKIE_SECURE=true` on the **app service** for HTTPS hosting |
| Model mode | Guided browser workflow plus separately labeled recorded local model evidence | No public model endpoint or provider credentials required |

The `store-init` and `app-state-init` services create their directories and set UID/GID 10001 ownership before the non-root services start. Preserve these initialization steps on another host.

Session expiry reclaims owned application session directories when capacity is checked, while protecting active and waiting requests. Last-seen timestamps survive app restart. Expired browsers can start a new session. **Historical HydraDB namespaces are retained and are not garbage-collected.** The active-session cap therefore does not bound lifetime database storage; monitor volume growth and retain the current demo scope.

The pinned database image is:

```text
ghcr.io/hydra-db/hydradb:0.4.0@sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880
```

The official image includes Linux ARM64 and AMD64 manifests, allowing the Docker-based stack on the development Mac and a compatible Linux host. The project uses the upstream image directly.

## Use the existing host

1. Transfer or build the private source through the user's existing hosting access. Keep `.env`, `.state`, provider login material and other local credentials out of the image and source distribution.
2. Provision persistent `hydra-state` and `app-state` storage and retain the ownership initializers. Mount a host-managed Hydra token at the same secret path in both containers.
3. Keep HydraDB query, Bolt and admin listeners private. The supplied Compose file binds host ports 18443, 17687 and 19090 to `127.0.0.1`; the app reaches HydraDB over the internal service network. Do not copy the local `.env` loopback URL into the app container.
4. Route the host's existing HTTPS ingress or reverse proxy to the app. A proxy on the same Docker host can use `127.0.0.1:18080`; a managed ingress should target the app's internal port 8000. Set `PROOFFLOW_COOKIE_SECURE=true` on the app service. Cookie security does not rely on unverified forwarded headers.
5. Keep one app worker/replica, attach both durable volumes, and verify `/health` before routing visitors. The static frontend and API share an origin, so no browser-side Hydra or provider key is needed.
6. Run the HTTP checks against the final HTTPS URL, then inspect the app from a fresh browser. Verify the FX correction, stale-value withholding, four-call refresh, numerical verification, missing-source refusal and reset.

The [120-second 1080p walkthrough](../video/proofflow-walkthrough.mp4) is bundled into the application image at `/walkthrough.mp4`, with its poster at `/walkthrough-poster.jpg`. The final HTTPS origin will provide the shareable video URL without a separate video-hosting account.

The browser workflow is real tool execution on authored data. Its “Recorded agent workflow” panel displays two saved local Fable 5.2 calls; clicking it does not make a hosted model call. The benchmark view displays frozen results rather than rerunning a benchmark for each visitor.

## Verify the packaged stack

With the local stack running and `uv` available:

```sh
uv sync --frozen --extra test
uv run python scripts/deployment_smoke.py --restart-app --output .state/checks/deployment-smoke.json
```

This creates an isolated browser session, makes real HTTP requests, restarts the local app service, and verifies preserved session and artifact identities. It then verifies missing-source refusal and reset. Use it when restarting this local instance is acceptable. For the final host, use `--url` with its HTTPS origin and omit `--restart-app`; coordinate that host's restart separately because the flag always restarts the **local Compose app**.

The saved deployment run passes all sixteen checks. Separate evidence covers [native Hydra persistence and new writes after database restart](../evidence/hydra_smoke.json), [core execution and recovery](../evidence/core_smoke.json), and [desktop/mobile browser verification](UI_FIDELITY.md). Application restart evidence and database restart evidence are distinct.

The local CSV integration also uses real HydraDB. Its entry point is `scripts/import_csv.py`; required fields are `order_id,region,currency,gross_cents`, with optional `refund_cents,ticket_count`. Monetary inputs are integer cents; EUR and GBP need explicit USD rates. With an existing file matching that schema:

```sh
uv run python scripts/import_csv.py orders.csv --workspace my-orders --region APAC --fx EUR=1.10
```

Rerunning the same workspace refreshes affected reports. CSV input stays local and does not call a model. The authored non-EU [integration check](../results/import-smoke-v1/verification.json) verified a correction, four recorded refresh calls, unchanged support identity and zero recorded refresh calls after row reordering. Each successful two-report CLI invocation separately performs **16 preflight calculations** (parse eight + public-import eight) and **11 verification calculations**, including an unchanged import. Recorded runtime calls remain a separate count; a row-order replay with zero recorded refresh calls still has 27 validation/verification calculations. This is a CLI integration, not a browser upload feature.

**Accounting correction:** the earlier generic eight-preflight-per-load wording was incomplete for this CLI. Both validation passes and report verification already existed; the counters now disclose them. MCP `load_csv` remains eight preflight calculations per load and does not automatically verify report recipes. The CLI exposes `preflight_calculation_count`, `recorded_tool_call_count`, `verification_calculation_count` and their sum as `total_calculation_count`. Original raw captures, benchmark measurements and the two-load MCP accounting remain unchanged.

## Recovery and delivery status

Back up database state and the complete application state, including manifests, blobs and workspace identity. Retain the prior application image/revision before updating. A graph-only backup cannot restore missing artifact content. Routine restarts and updates must preserve named volumes; `docker compose down -v` deletes them.

Missing sources remain unknown/blocked, and failed graph access remains visible as an error. Recovery must not invent replacement values or silently reconstruct a graph while claiming a durable read. The core-smoke workspace intentionally ends with a missing source; it is separate from each new browser session's clean fixture.

Hosted verification covers deployed revision `b13f23892405efb856c8d4ca0e6abc94a1eca77c` and the live walkthrough. The organizer posted the submission form and set a deadline of **16 November 2026 at 09:00 IST**. The organizer requires an open-source repository, while this repository remains private. Submission is deferred. [Hosted verification](HOSTED_DELIVERY.md) · [Submission status](SUBMISSION_DRAFT.md) · [Organizer’s submission form](https://forms.gle/9brHhy7BC229tw868).

## References

- [Application Dockerfile](../Dockerfile), [database Compose](../docker-compose.yml), [application Compose](../compose.app.yml), and [API contract](API_CONTRACT.md)
- [Official HydraDB package](https://github.com/hydra-db/hydradb/pkgs/container/hydradb), [upstream runtime documentation](https://github.com/hydra-db/hydradb/blob/main/README.md), and [official image publication workflow](https://github.com/hydra-db/hydradb/blob/main/.github/workflows/container.yml)
- [Exact hackathon event](https://luma.com/bqwllms4)
