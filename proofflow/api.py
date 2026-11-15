"""Same-origin, isolated-session API for the live ProofFlow demonstration."""
from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictStr
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from .analytics import AnalyticsError
from .browser_import import active_import, create_import, preview as preview_import
from .demo import ActionLimit, SessionCapacity, SessionManager, SessionMissing
from .graph import GraphError, HydraGraph
from .models import InvalidInputError, MissingEvidenceError


COOKIE = "proofflow_session"
REPORT_EXPORT_PATH = "/api/import/export"


class ExportReportIds(BaseModel, extra="forbid"):
    company: StrictStr = Field(min_length=1)
    region: StrictStr = Field(min_length=1)


class ExportRequest(BaseModel, extra="forbid"):
    generation: StrictStr = Field(min_length=1)
    report_ids: ExportReportIds


class ReportExportResponses:
    """Keep the snapshot and its errors out of caches, including an unexpected 500."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != REPORT_EXPORT_PATH:
            return await self.app(scope, receive, send)

        started = False

        async def send_uncached(message):
            nonlocal started
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_uncached)
        except Exception:
            if not started:
                response = JSONResponse({"error": {"code": "export_unavailable",
                    "message": "The report snapshot could not be prepared"}}, status_code=500)
                await response(scope, receive, send_uncached)
            raise


class ImportBodyLimit:
    """Bound JSON transport before FastAPI buffers it; CSV has a tighter limit."""

    def __init__(self, app, max_bytes: int = 8 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or not scope.get("path", "").startswith("/api/import/")):
            return await self.app(scope, receive, send)

        async def reject():
            response = JSONResponse({"error": {"code": "invalid_input",
                "message": "Import request exceeds the 8 MiB JSON transport limit"}}, status_code=413)
            await response(scope, receive, send)

        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        return await reject()
                except ValueError:
                    pass
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                return await reject()
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


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
    application.add_middleware(ImportBodyLimit)
    application.add_middleware(ReportExportResponses)
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

    @application.post("/api/import/preview")
    def import_preview(request: Request, payload: dict):
        with manager.session(sid(request)) as current:
            current.rate_limit()
            return preview_import(payload)

    @application.post("/api/import/create")
    def import_create(request: Request, payload: dict):
        with manager.session(sid(request)) as current:
            current.rate_limit()
            return create_import(current, payload, factory)

    @application.get("/api/import/state")
    def import_state(request: Request):
        with manager.session(sid(request)) as current, active_import(current, factory) as imported:
            return imported.state()

    @application.post("/api/import/update")
    def import_update(request: Request, payload: dict):
        with manager.session(sid(request)) as current:
            current.rate_limit()
            with active_import(current, factory) as imported:
                return imported.update(payload)

    @application.post("/api/import/refresh")
    def import_refresh(request: Request, payload: dict | None = None):
        if payload:
            raise InvalidInputError("Imported refresh does not accept parameters")
        with manager.session(sid(request)) as current:
            current.rate_limit()
            with active_import(current, factory) as imported:
                return imported.refresh()

    @application.post("/api/import/verify")
    def import_verify(request: Request, payload: dict | None = None):
        if payload:
            raise InvalidInputError("Imported verification does not accept parameters")
        with manager.session(sid(request)) as current:
            current.rate_limit()
            with active_import(current, factory) as imported:
                return imported.verify()

    @application.post(REPORT_EXPORT_PATH)
    def import_export(request: Request, payload: ExportRequest):
        with manager.session(sid(request)) as current:
            current.rate_limit()
            with active_import(current, factory) as imported:
                return imported.export_reports(payload.generation, payload.report_ids.model_dump())

    @application.get("/api/import/evidence/{artifact_id:path}")
    def import_evidence(request: Request, artifact_id: str):
        with manager.session(sid(request)) as current, active_import(current, factory) as imported:
            return imported.evidence(artifact_id)

    directory = Path(static_dir or os.environ.get("PROOFFLOW_STATIC_DIR", "frontend/dist")).resolve()
    if directory.is_dir():
        assets = directory / "assets"
        if assets.is_dir():
            application.mount("/assets", StaticFiles(directory=assets), name="assets")

        evidence = directory / "evidence"
        if evidence.is_dir():
            @application.get("/evidence", include_in_schema=False)
            def public_evidence_index():
                return RedirectResponse("/evidence/", status_code=308)

            application.mount("/evidence", StaticFiles(directory=evidence, html=True), name="public-evidence")

        @application.get("/{path:path}")
        def spa(path: str):
            if path == "api" or path.startswith("api/"):
                return error("not_found", "API route not found", 404)
            if path == "evidence" or path.startswith("evidence/"):
                return error("not_found", "Evidence package has not been built", 404)
            candidate = (directory / path).resolve()
            if candidate.is_relative_to(directory) and candidate.is_file():
                return FileResponse(candidate)
            index = directory / "index.html"
            if index.is_file():
                return FileResponse(index)
            return error("not_found", "Frontend has not been built", 404)

    return application


app = create_app()
