# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==2.3.0", "httpx==0.28.1"]
# ///
"""Local stdio connector for the hosted ProofFlow CSV reports."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from threading import Lock
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


ORIGIN = "https://proofflow.arnavbule.in"
MAX_CSV_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SESSION_COOKIE = "proofflow_session"
RESTART_WORKSPACE = "Restart the connector and explicitly create reports with the full CSV."
CREATE = "/api/import/create"
STATE = "/api/import/state"
UPDATE = "/api/import/update"
REFRESH = "/api/import/refresh"
EXPORT = "/api/import/export"
EVIDENCE = "/api/import/evidence/"
GENERATION_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
RECORD_PATTERN = re.compile(r"([0-9a-f]{32}):(artifact|source|execution|tool):[0-9a-f]{64}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT_LOGICAL_IDS = frozenset({
    "import:report:company", "import:report:region",
    *(f"import:metric:{name}" for name in ("gross", "refunds", "net", "regional", "company", "support")),
})
PRODUCERS = frozenset({"gross_by_region", "refunds_by_region", "net_by_region", "convert_to_usd",
                       "company_total", "support_by_region", "compose_report"})
PATH_SCOPE = ("Native path witnesses from recorded changed-source versions, including earlier corrections; "
              "at most three paths per source, depth at most 15. An empty list is not a currentness verdict.")
CSV_ARGUMENTS = frozenset({"csv_text", "rates", "region"})
TOOL_ARGUMENTS = {
    "create_csv_reports": CSV_ARGUMENTS,
    "inspect_reports": frozenset(),
    "update_csv": CSV_ARGUMENTS,
    "refresh_reports": frozenset(),
    "export_current_reports": frozenset({"generation", "report_ids"}),
    "inspect_evidence": frozenset({"generation", "artifact_id"}),
}
STATUS_ERRORS = {
    400: "The hosted API rejected the input. Check the CSV schema, selected region, and exchange rates.",
    401: "This hosted session is unavailable or expired. Restart the connector and explicitly create reports to begin again.",
    404: "This connector has no active imported reports. Create reports first.",
    409: "Current evidence is unavailable. Inspect reports and resolve any pending CSV update.",
    413: "The hosted API refused an oversized request.",
    429: "The hosted demo action limit was reached. Wait before trying again.",
    503: "The hosted API is at capacity or its HydraDB evidence is unavailable. Try again later.",
}


class HostedCsvServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        if name not in TOOL_ARGUMENTS or arguments.keys() - TOOL_ARGUMENTS[name]:
            raise ToolError("Use one of the six connector tools with only its advertised arguments.")
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            # The SDK's argument validation message can contain rejected inputs.
            if isinstance(exc.__cause__, ValueError):
                raise ToolError("Tool arguments do not match the advertised schema.") from None
            raise


def csv_payload(csv_text: str, rates: dict[str, str] | None, region: str | None) -> dict:
    if not csv_text or len(csv_text) > MAX_CSV_BYTES:
        raise ToolError("Provide CSV text of up to 1 MiB, with at least one order row.")
    try:
        byte_count = len(csv_text.encode("utf-8"))
    except UnicodeEncodeError:
        raise ToolError("Provide valid UTF-8 CSV text.") from None
    if byte_count > MAX_CSV_BYTES:
        raise ToolError("Provide CSV text of up to 1 MiB, measured in UTF-8 bytes.")
    if rates and (rates.keys() - {"USD", "EUR", "GBP"} or any(len(value) > 17 for value in rates.values())):
        raise ToolError("Use explicit decimal rates for USD, EUR, or GBP only.")
    if region is not None and not 1 <= len(region) <= 64:
        raise ToolError("Specify a region name of 1–64 characters from the CSV.")
    payload = {"csv_text": csv_text, "rates": rates or {}}
    if region is not None:
        payload["region"] = region
    return payload


def select(value: dict, *keys: str) -> dict:
    return {key: value[key] for key in keys}


def evidence_state(raw: dict, generation: str, artifact_id: str) -> dict:
    """Validate and project the atomic envelope; never forward stored values."""
    workspace = artifact_id.split(":", 1)[0]

    def record_id(value, kinds):
        match = RECORD_PATTERN.fullmatch(value) if isinstance(value, str) else None
        if match is None or match[1] != workspace or match[2] not in kinds:
            raise ValueError("Invalid evidence identity")
        return value

    def content_hash(value):
        if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
            raise ValueError("Invalid evidence hash")
        return value

    def logical_id(value, kind):
        valid = (value in ARTIFACT_LOGICAL_IDS if kind == "artifact" else
                 value in {f"source:csv:{name}" for name in ("orders", "refunds", "fx", "tickets")}
                 if kind == "source" else
                 isinstance(value, str) and re.fullmatch(r"execution:[0-9a-f]{32}", value) is not None)
        if not valid:
            raise ValueError("Invalid logical identity")
        return value

    try:
        if (type(raw["schema_version"]) is not int or raw["schema_version"] != 1
                or raw["generation"] != generation or raw["incomplete_update"] is not False
                or not isinstance(raw["path_scope"], str)):
            raise ValueError("Unexpected evidence envelope")
        backend = select(raw["backend"], "engine", "native_queries", "fallback")
        if (backend["engine"] != "HydraDB OSS" or backend["fallback"] is not False
                or type(backend["native_queries"]) is not int or backend["native_queries"] < 1):
            raise ValueError("Native evidence unavailable")
        artifact = select(raw["artifact"], "id", "kind", "logical_id", "content_hash", "state", "current_head_id")
        if artifact["id"] != artifact_id or artifact["kind"] != "artifact" or artifact["state"] not in {"current", "stale"}:
            raise ValueError("Unexpected artifact")
        record_id(artifact["id"], {"artifact"})
        record_id(artifact["current_head_id"], {"artifact"})
        logical_id(artifact["logical_id"], "artifact")
        content_hash(artifact["content_hash"])
        reasons = raw["artifact"]["reasons"]
        if not isinstance(reasons, list) or len(reasons) > 64:
            raise ValueError("Invalid currentness reasons")
        artifact["reasons"] = []
        for reason in reasons:
            item = select(reason, "id", "reason")
            record_id(item["id"], {"source", "tool"})
            if item["reason"] not in {"version_changed", "implementation_changed"}:
                raise ValueError("Incomplete currentness")
            if "current_id" in reason:
                item["current_id"] = None if reason["current_id"] is None else record_id(reason["current_id"], {"source", "tool"})
            artifact["reasons"].append(item)
        if (artifact["state"] == "current") != (not artifact["reasons"]):
            raise ValueError("Inconsistent currentness")
        receipt = select(raw["receipt"], "id", "content_hash", "tool", "tool_version_id", "status", "output_id", "output_hash")
        record_id(receipt["id"], {"execution"})
        record_id(receipt["tool_version_id"], {"tool"})
        content_hash(receipt["content_hash"])
        if (receipt["status"] != "success" or receipt["tool"] not in PRODUCERS
                or receipt["output_id"] != artifact_id or receipt["output_hash"] != artifact["content_hash"]):
            raise ValueError("Inconsistent producing receipt")
        if not isinstance(raw["inputs"], list) or not 1 <= len(raw["inputs"]) <= 16:
            raise ValueError("Invalid receipt inputs")
        inputs, names = [], set()
        for source in raw["inputs"]:
            item = select(source, "name", "id", "kind", "logical_id", "content_hash", "inspectable")
            if (item["kind"] not in {"source", "artifact"} or not isinstance(item["name"], str)
                    or re.fullmatch(r"[a-z_]{1,48}", item["name"]) is None or item["name"] in names
                    or item["inspectable"] is not (item["kind"] == "artifact")):
                raise ValueError("Invalid typed input")
            names.add(item["name"])
            record_id(item["id"], {item["kind"]})
            logical_id(item["logical_id"], item["kind"])
            content_hash(item["content_hash"])
            inputs.append(item)
        paths = raw["recorded_changed_source_paths"]
        if not isinstance(paths, list) or len(paths) > 384:
            raise ValueError("Invalid native paths")
        projected_paths, source_counts = [], {}
        for path in paths:
            source_id = record_id(path["source_id"], {"source"})
            if path["target_id"] != artifact_id:
                raise ValueError("Unexpected native path target")
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            if source_counts[source_id] > 3 or not isinstance(path["nodes"], list) or not 2 <= len(path["nodes"]) <= 16:
                raise ValueError("Unbounded native path")
            nodes = []
            for node in path["nodes"]:
                item = select(node, "id", "kind", "logical_id")
                if item["kind"] not in {"source", "artifact", "execution"}:
                    raise ValueError("Invalid native path node")
                record_id(item["id"], {item["kind"]})
                logical_id(item["logical_id"], item["kind"])
                nodes.append(item)
            if (nodes[0]["id"] != source_id or nodes[-1]["id"] != artifact_id
                    or len({node["id"] for node in nodes}) != len(nodes)
                    or not isinstance(path["edges"], list) or len(path["edges"]) != len(nodes) - 1):
                raise ValueError("Discontinuous native path")
            if (nodes[-1] != {key: artifact[key] for key in ("id", "kind", "logical_id")}
                    or nodes[-2]["id"] != receipt["id"] or nodes[-2]["kind"] != "execution"):
                raise ValueError("Native path does not bind the selected artifact's producing receipt")
            edges = []
            for index, edge in enumerate(path["edges"]):
                item = select(edge, "source", "target", "kind")
                left, right = nodes[index], nodes[index + 1]
                expected = "PRODUCED" if left["kind"] == "execution" and right["kind"] == "artifact" else (
                    "CONSUMED" if left["kind"] in {"source", "artifact"} and right["kind"] == "execution" else None)
                if expected is None or item != {"source": left["id"], "target": right["id"], "kind": expected}:
                    raise ValueError("Invalid native path edge")
                edges.append(item)
            projected_paths.append({"source_id": source_id, "target_id": artifact_id, "nodes": nodes, "edges": edges})
        return {"schema_version": 1, "generation": generation, "incomplete_update": False,
                "backend": backend, "artifact": artifact, "receipt": receipt, "inputs": inputs,
                "recorded_changed_source_paths": projected_paths, "path_scope": PATH_SCOPE}
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        raise ToolError("The hosted API returned incomplete or unexpected evidence. No evidence was returned.") from None


def report_state(state: dict) -> dict:
    try:
        if state["mode"] != "guided_csv_import" or len(state["reports"]) != 2:
            raise ValueError("Unexpected report state")
        incomplete = state["incomplete_update"]
        reports = []
        for record in state["reports"]:
            report = select(record, "key", "id", "state")
            if incomplete:
                report["state"] = "unknown"
            report["claims"] = []
            for source in record["claims"]:
                claim = select(source, "key", "unit", "artifact_id", "state")
                claim["reasons"] = [select(reason, "reason", "id") for reason in source["reasons"]]
                if incomplete:
                    claim["state"] = "unknown"
                    claim["reasons"].append({"reason": "incomplete_update", "id": record["id"]})
                claim["value"] = source["value"] if claim["state"] == "current" else None
                report["claims"].append(claim)
            reports.append(report)
        refresh = state["last_refresh"]
        if refresh is not None:
            refresh = select(refresh, "executed_count", "reused_count", "executed_artifact_ids",
                             "reused_artifact_ids", "numeric_parity", "unchanged_support", "graph_queries")
        return {
            **select(state, "generation", "incomplete_update"),
            "dataset": select(state["dataset"], "row_count", "selected_region", "source_csv_sha256"),
            "backend": select(state["backend"], "engine", "native_queries", "fallback"),
            "reports": reports,
            "affected_artifact_ids": [item["id"] for item in state["impact"]["affected_artifacts"]],
            "last_operation": select(state["last_operation"], "kind", "preflight_calculation_count",
                                     "recorded_tool_call_count", "verification_calculation_count",
                                     "total_calculation_count", "changed_source_count", "noop"),
            "last_refresh": refresh,
        }
    except (KeyError, TypeError, ValueError):
        raise ToolError("The hosted API returned an unexpected report state.") from None


@dataclass(frozen=True)
class ConfirmedCsv:
    text: str = field(repr=False)
    digest: str
    generation: str
    region: str


class RequestRefused(ToolError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class HostedCsvAPI:
    """Own one private session and at most one confirmed CSV per process."""

    def __init__(self, client: httpx.Client):
        self.client = client
        self.lock = Lock()
        self.session_attempted = False
        self.session_id: str | None = None
        self.confirmed_csv: ConfirmedCsv | None = None
        self.writes_blocked = False

    def _block_writes(self):
        self.confirmed_csv = None
        self.writes_blocked = True

    @contextmanager
    def _confirm_mutation(self):
        try:
            yield
        except ToolError as error:
            status = error.status if isinstance(error, RequestRefused) else None
            # These two limits are enforced before the hosted write handler.
            # Other failures can occur after source or report heads changed.
            if status in {413, 429}:
                raise
            self._block_writes()
            if status == 401:
                raise
            raise ToolError(f"The connector could not confirm the hosted write. {RESTART_WORKSPACE}") from None

    def _require_writable(self):
        if self.writes_blocked:
            raise ToolError("This connector cannot confirm the workspace for another write or checked export. "
                            + RESTART_WORKSPACE)

    def _cookie_id(self):
        cookies = [cookie for cookie in self.client.cookies.jar if cookie.name == SESSION_COOKIE]
        if len(cookies) == 1:
            cookie = cookies[0]
            if (cookie.secure and cookie.path == "/" and cookie.domain.lstrip(".") == self.client.base_url.host
                    and not cookie.is_expired()):
                return cookie.value or None
        return None

    def _require_session(self, *, create: bool = False):
        if create and not self.session_attempted:
            self.session_attempted = True
            if any(cookie.name == SESSION_COOKIE for cookie in self.client.cookies.jar):
                raise ToolError("Start the connector with a fresh session before creating CSV reports.")
            self._request("POST", "/api/session")
            self.session_id = self._cookie_id()
        if self.session_id is None:
            if self.session_attempted:
                raise ToolError("A hosted session is unavailable. Restart the connector and create reports again.")
            raise ToolError("Create CSV reports to open a fresh hosted session.")
        if self._cookie_id() != self.session_id:
            self._lose_session()
            raise ToolError("The connector's hosted session changed. Restart the connector and create reports again.")

    def _lose_session(self):
        self._block_writes()
        self.session_attempted = True
        self.session_id = None

    def _session_request(self, method, path, payload=None):
        self._require_session()
        try:
            return self._request(method, path, payload)
        except RequestRefused as error:
            if error.status == 401:
                self._lose_session()
                raise
            if error.status == 404 and self.confirmed_csv is not None and not path.startswith(EVIDENCE):
                self._block_writes()
            raise
        finally:
            if self.session_id is not None:
                self._require_session()

    def _state(self, raw):
        if raw.get("session_id") != self.session_id:
            self._lose_session()
            raise ToolError("The hosted response belonged to a different session. Restart the connector.")
        if raw.get("incomplete_update") is True:
            self._block_writes()
        state = report_state(raw)
        if type(state["incomplete_update"]) is not bool:
            raise ToolError("The hosted API returned an unexpected report state.")
        return state

    def _match_confirmed(self, state):
        confirmed = self.confirmed_csv
        if (state["incomplete_update"] or (confirmed is not None and (
                state["generation"], state["dataset"]["source_csv_sha256"], state["dataset"]["selected_region"]
        ) != (confirmed.generation, confirmed.digest, confirmed.region))):
            self._block_writes()
            return False
        return True

    def publish_csv(self, path, csv_text, rates, region):
        with self.lock:
            self._require_writable()
            confirmed = self.confirmed_csv
            reuse = path == UPDATE and csv_text is None
            if reuse:
                if confirmed is None:
                    raise ToolError("No confirmed CSV is available in this process. Create reports with the full CSV first.")
                if rates is None or region is None:
                    raise ToolError("Provide explicit rates and the selected region when omitting csv_text.")
                if region != confirmed.region:
                    raise ToolError("Keep the selected region for a rate-only correction.")
                csv_text = confirmed.text
            payload = csv_payload(csv_text, rates, region)
            if path == CREATE:
                self._require_session(create=True)
            elif confirmed is None:
                raise ToolError("Create reports with the full CSV before updating this workspace.")
            if reuse:
                state = self._state(self._session_request("GET", STATE))
                if not self._match_confirmed(state):
                    self._require_writable()
            digest = sha256(csv_text.encode("utf-8")).hexdigest()
            with self._confirm_mutation():
                state = self._state(self._session_request("POST", path, payload))
                dataset = state["dataset"]
                generation, selected_region = state["generation"], dataset["selected_region"]
                if (state["incomplete_update"] or not isinstance(generation, str) or not generation
                        or not isinstance(selected_region, str) or not selected_region
                        or dataset["source_csv_sha256"] != digest
                        or (region is not None and selected_region != region)
                        or (confirmed is not None and path == UPDATE
                            and (generation, selected_region) != (confirmed.generation, confirmed.region))
                        or (confirmed is not None and path == CREATE and generation == confirmed.generation)
                        or state["last_operation"]["kind"] != ("create" if path == CREATE else "update")):
                    raise ToolError("The hosted response did not confirm the submitted CSV and workspace.")
            self.confirmed_csv = ConfirmedCsv(csv_text, digest, generation, selected_region)
            return state

    def call(self, method: str, path: str, payload: dict | None = None) -> dict:
        with self.lock:
            if path != STATE:
                self._require_writable()
            if path == REFRESH:
                self._require_session()
                if self.confirmed_csv is None:
                    raise ToolError("Create reports with the full CSV before refreshing this workspace.")
                with self._confirm_mutation():
                    state = self._state(self._session_request(method, path, payload))
                    if not self._match_confirmed(state):
                        self._require_writable()
                    if state["last_operation"]["kind"] != "refresh" or state["last_refresh"] is None:
                        raise ToolError("The hosted response did not confirm the refresh.")
                    return state
            response = self._session_request(method, path, payload)
            if path == STATE:
                state = self._state(response)
                self._match_confirmed(state)
                return state
            return response

    def inspect_evidence(self, generation: str, artifact_id: str) -> dict:
        if (GENERATION_PATTERN.fullmatch(generation) is None
                or (match := RECORD_PATTERN.fullmatch(artifact_id)) is None or match[2] != "artifact"):
            raise ToolError("Pass an observed workspace generation and an immutable artifact ID.")
        with self.lock:
            # This read can diagnose an uncertain write, but cannot restore the
            # confirmed CSV or make subsequent writes/exports permissible.
            raw = self._session_request("GET", f"{EVIDENCE}{artifact_id}?generation={generation}")
            return evidence_state(raw, generation, artifact_id)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            with self.client.stream(method, path, json=payload) as response:
                if response.status_code != 200:
                    if response.status_code == 409 and path == EXPORT:
                        raise ToolError("The hosted API refused this report snapshot (409). No export was returned. Inspect reports before choosing current report IDs.")
                    raise RequestRefused(response.status_code, STATUS_ERRORS.get(
                        response.status_code, "The hosted API did not complete the request."))
                if path == "/api/session":
                    return {}  # Only the cookie jar keeps the session credential.
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ToolError("The hosted response exceeded the connector's 2 MiB limit.")
                    data.extend(chunk)
            result = json.loads(data)
        except httpx.RequestError:
            raise ToolError("The hosted API could not be reached or the response was interrupted.") from None
        except (ValueError, RecursionError):
            raise ToolError("The hosted API returned an unexpected response.") from None
        if not isinstance(result, dict):
            raise ToolError("The hosted API returned an unexpected response.")
        return result


def build_server(client: httpx.Client) -> MCPServer:
    api = HostedCsvAPI(client)
    server = HostedCsvServer("ProofFlow Hosted CSV", log_level="WARNING", subscriptions=False, instructions=(
        "Use synthetic or nonsensitive CSV data. The connector sends your CSV to hosted ProofFlow. "
        "Create saves two fixed revenue reports (company and selected region). Update publishes a correction "
        "without recalculating. For a rate-only update in the same process, omit csv_text and pass rates and region. "
        "Stale claims and incomplete updates have no current value. Refresh recalculates affected work. "
        "Inspect evidence for an observed artifact ID to follow its receipt inputs and recorded native changed-source paths; "
        "this read returns no amounts or source contents and does not refresh anything. "
        "Export verifies both selected report IDs and their workspace generation before returning snapshot text."
    ))

    @server.tool()
    def create_csv_reports(csv_text: str, rates: dict[str, str] | None = None,
                           region: str | None = None) -> dict[str, Any]:
        """Send CSV text to hosted ProofFlow and create company and selected-region revenue reports. Required columns: order_id,region,currency,gross_cents. Optional: refund_cents,ticket_count. Provide EUR/GBP USD rates as decimal strings. Creating again replaces the active imported workspace."""
        return api.publish_csv(CREATE, csv_text, rates, region)

    @server.tool()
    def inspect_reports() -> dict[str, Any]:
        """Inspect currentness, impact, and immutable IDs for the two reports in this connector's workspace."""
        return api.call("GET", STATE)

    @server.tool()
    def inspect_evidence(generation: str, artifact_id: str) -> dict[str, Any]:
        """Inspect one observed report or calculation artifact in its observed workspace generation. Return currentness, producing receipt, typed followable artifact inputs and bounded native paths from recorded changed sources, including earlier corrections. No saved numeric values or source contents are returned. An empty path list is not a currentness verdict."""
        return api.inspect_evidence(generation, artifact_id)

    @server.tool()
    def update_csv(csv_text: str | None = None, rates: dict[str, str] | None = None,
                   region: str | None = None) -> dict[str, Any]:
        """Publish a corrected CSV, or omit csv_text for a rate-only correction in this process after a confirmed load. For a rate-only correction pass all needed rates as decimals and the existing region. Refresh is a separate step."""
        return api.publish_csv(UPDATE, csv_text, rates, region)

    @server.tool()
    def refresh_reports() -> dict[str, Any]:
        """Refresh affected calculations for the two saved reports, reusing valid work and returning the actual call count."""
        return api.call("POST", REFRESH)

    @server.tool()
    def export_current_reports(generation: str, report_ids: dict[str, str]) -> dict[str, Any]:
        """Pass the observed generation and exactly two report IDs keyed company and region. Return checked snapshot text only when both selected reports are current."""
        if (not 1 <= len(generation) <= 100 or report_ids.keys() != {"company", "region"}
                or any(not 1 <= len(value) <= 300 for value in report_ids.values())):
            raise ToolError("Pass the report generation and both observed report IDs keyed company and region.")
        result = api.call("POST", EXPORT, {"generation": generation, "report_ids": report_ids})
        try:
            return select(result, "filename", "media_type", "checked_at", "content")
        except KeyError:
            raise ToolError("The hosted API did not return a checked report snapshot.") from None

    return server


def main() -> None:
    with httpx.Client(base_url=ORIGIN, timeout=httpx.Timeout(45, connect=5),
                      headers={"Accept": "application/json", "Accept-Encoding": "identity"},
                      follow_redirects=False, trust_env=False) as client:
        build_server(client).run(transport="stdio")


if __name__ == "__main__":
    main()
