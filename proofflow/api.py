"""Same-origin, isolated-session API for the live ProofFlow demonstration."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .analytics import AnalyticsError
from .demo import ActionLimit, SessionCapacity, SessionManager, SessionMissing
from .graph import GraphError, HydraGraph
from .models import InvalidInputError, MissingEvidenceError


COOKIE = "proofflow_session"


def create_app(state_dir: str | Path | None = None, graph_factory: Callable[..., Any] | None = None,
               max_sessions: int | None = None, static_dir: str | Path | None = None,
               session_ttl_seconds: float | None = None) -> FastAPI:
    factory = graph_factory or HydraGraph
    manager = SessionManager(state_dir or os.environ.get("PROOFFLOW_STATE_DIR", ".state/sessions"),
                             factory, max_sessions if max_sessions is not None
                             else int(os.environ.get("PROOFFLOW_MAX_SESSIONS", "16")),
                             session_ttl_seconds if session_ttl_seconds is not None
                             else float(os.environ.get("PROOFFLOW_SESSION_TTL_SECONDS", "3600")))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        manager.close()

    application = FastAPI(title="ProofFlow", version="0.1.0", lifespan=lifespan)
    application.state.manager = manager

    def error(code: str, message: str, status: int):
        return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)

    @application.exception_handler(GraphError)
    async def graph_error(request, exc):
        return error("backend_unavailable", "HydraDB is unavailable or its evidence is incomplete. No fallback answer was served.", 503)

    @application.exception_handler(MissingEvidenceError)
    async def evidence_error(request, exc):
        return error("evidence_unavailable", str(exc), 409)

    @application.exception_handler(SessionMissing)
    async def session_error(request, exc):
        status = 404 if ("Unknown" in str(exc)) else 401
        return error("not_found" if status == 404 else "session_required", str(exc), status)

    @application.exception_handler(SessionCapacity)
    async def capacity_error(request, exc):
        return error("session_capacity", str(exc), 503)

    @application.exception_handler(ActionLimit)
    async def action_error(request, exc):
        return error("action_limit", str(exc), 429)

    @application.exception_handler(InvalidInputError)
    @application.exception_handler(AnalyticsError)
    @application.exception_handler(ValueError)
    async def input_error(request, exc):
        return error("invalid_input", str(exc), 400)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error("invalid_input", "Request body does not match this endpoint's JSON contract", 400)

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error("not_found" if exc.status_code == 404 else "http_error", str(exc.detail), exc.status_code)

    def sid(request: Request) -> str | None:
        return request.cookies.get(COOKIE)

    @application.get("/health")
    def health():
        client = factory(namespace="proofflow-health")
        try:
            client.get_node("__health_probe__")
        finally:
            client.close()
        return {"status": "ok", "backend": "HydraDB OSS"}

    @application.post("/api/session")
    def session(request: Request):
        session_id, state = manager.create_or_resume(sid(request))
        response = JSONResponse(state)
        secure_cookie = os.environ.get("PROOFFLOW_COOKIE_SECURE", os.environ.get("PROOFFLOW_SECURE_COOKIES", "false")).lower() in {"1", "true", "yes"}
        response.set_cookie(COOKIE, session_id, httponly=True, samesite="strict",
                            secure=secure_cookie,
                            max_age=86400, path="/")
        return response

    @application.get("/api/state")
    def state(request: Request):
        with manager.session(sid(request)) as current:
            return current.state()

    @application.post("/api/change")
    def change(request: Request, payload: dict):
        with manager.session(sid(request)) as current:
            return current.change(payload)

    @application.post("/api/refresh")
    def refresh(request: Request, payload: dict | None = None):
        payload = {} if payload is None else payload
        if set(payload) - {"report_ids"}:
            raise InvalidInputError("Refresh only accepts report_ids")
        with manager.session(sid(request)) as current:
            return current.refresh(payload.get("report_ids"))

    @application.post("/api/verify")
    def verify(request: Request, payload: dict | None = None):
        if payload:
            raise InvalidInputError("Verification does not accept parameters")
        with manager.session(sid(request)) as current:
            current.rate_limit()
            return current.verify()

    @application.post("/api/reset")
    def reset(request: Request, payload: dict | None = None):
        if payload:
            raise InvalidInputError("Reset does not accept parameters")
        return manager.reset(sid(request))

    @application.get("/api/evidence/{artifact_id:path}")
    def evidence(request: Request, artifact_id: str):
        with manager.session(sid(request)) as current:
            return current.evidence(artifact_id)

    @application.get("/api/benchmark")
    def benchmark():
        evidence_dir = Path(os.environ.get("PROOFFLOW_EVIDENCE_DIR", str(Path(__file__).resolve().parents[1] / "evidence")))
        published = evidence_dir / "benchmark_summary.json"
        if not published.is_file():
            return error("not_found", "Published benchmark summary is not available yet", 404)
        try:
            data = json.loads(published.read_text())
        except (OSError, ValueError):
            return error("benchmark_unavailable", "The published benchmark summary could not be read", 503)
        return JSONResponse(data)

    directory = Path(static_dir or os.environ.get("PROOFFLOW_STATIC_DIR", "frontend/dist")).resolve()
    if directory.is_dir():
        assets = directory / "assets"
        if assets.is_dir():
            application.mount("/assets", StaticFiles(directory=assets), name="assets")

        @application.get("/{path:path}")
        def spa(path: str):
            if path == "api" or path.startswith("api/"):
                return error("not_found", "API route not found", 404)
            candidate = (directory / path).resolve()
            if candidate.is_relative_to(directory) and candidate.is_file():
                return FileResponse(candidate)
            index = directory / "index.html"
            if index.is_file():
                return FileResponse(index)
            return error("not_found", "Frontend has not been built", 404)

    return application


app = create_app()
