# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==2.3.0", "httpx==0.28.1"]
# ///
"""Local stdio connector for the hosted ProofFlow CSV reports."""
from __future__ import annotations

import json
from threading import Lock
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


ORIGIN = "https://proofflow.arnavbule.in"
MAX_CSV_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SESSION_COOKIE = "proofflow_session"
CREATE = "/api/import/create"
STATE = "/api/import/state"
UPDATE = "/api/import/update"
REFRESH = "/api/import/refresh"
EXPORT = "/api/import/export"
CSV_ARGUMENTS = frozenset({"csv_text", "rates", "region"})
TOOL_ARGUMENTS = {
    "create_csv_reports": CSV_ARGUMENTS,
    "inspect_reports": frozenset(),
    "update_csv": CSV_ARGUMENTS,
    "refresh_reports": frozenset(),
    "export_current_reports": frozenset({"generation", "report_ids"}),
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
            raise ToolError("Use one of the five connector tools with only its advertised arguments.")
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


class HostedCsvAPI:
    """Own one private browser session for the lifetime of a connector process."""

    def __init__(self, client: httpx.Client):
        self.client = client
        self.lock = Lock()
        self.session_attempted = False
        self.session_ready = False

    def call(self, method: str, path: str, payload: dict | None = None) -> dict:
        with self.lock:
            if path == CREATE and not self.session_attempted:
                self.session_attempted = True
                self._request("POST", "/api/session")
                self.session_ready = any(cookie.name == SESSION_COOKIE and cookie.secure
                                         for cookie in self.client.cookies.jar)
            if not self.session_ready:
                if self.session_attempted:
                    raise ToolError("A hosted session could not be opened. Restart the connector before creating reports again.")
                raise ToolError("Create CSV reports to open a fresh hosted session.")
            return self._request(method, path, payload)

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            with self.client.stream(method, path, json=payload) as response:
                if response.status_code != 200:
                    if response.status_code == 409 and path == EXPORT:
                        raise ToolError("The hosted API refused this report snapshot (409). No export was returned. Inspect reports before choosing current report IDs.")
                    raise ToolError(STATUS_ERRORS.get(response.status_code, "The hosted API did not complete the request. Inspect reports before repeating a write."))
                if path == "/api/session":
                    return {}  # Only the cookie jar keeps the session credential.
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(data) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ToolError("The hosted response exceeded the connector's 2 MiB limit.")
                    data.extend(chunk)
            result = json.loads(data)
        except httpx.RequestError:
            raise ToolError("The hosted API could not be reached or the response was interrupted. Inspect reports before repeating a write.") from None
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
        "without recalculating. Stale claims and incomplete updates have no current value. Refresh recalculates affected work. "
        "Export verifies both selected report IDs and their workspace generation before returning snapshot text."
    ))

    @server.tool()
    def create_csv_reports(csv_text: str, rates: dict[str, str] | None = None,
                           region: str | None = None) -> dict[str, Any]:
        """Send CSV text to hosted ProofFlow and create company and selected-region revenue reports. Required columns: order_id,region,currency,gross_cents. Optional: refund_cents,ticket_count. Provide EUR/GBP USD rates as decimal strings. Creating again replaces the active imported workspace."""
        return report_state(api.call("POST", CREATE, csv_payload(csv_text, rates, region)))

    @server.tool()
    def inspect_reports() -> dict[str, Any]:
        """Inspect currentness, impact, and immutable IDs for the two reports in this connector's workspace."""
        return report_state(api.call("GET", STATE))

    @server.tool()
    def update_csv(csv_text: str, rates: dict[str, str] | None = None, region: str | None = None) -> dict[str, Any]:
        """Publish the full corrected CSV or exchange rates for the existing region and inspect the affected reports. This does not refresh saved calculations."""
        return report_state(api.call("POST", UPDATE, csv_payload(csv_text, rates, region)))

    @server.tool()
    def refresh_reports() -> dict[str, Any]:
        """Refresh affected calculations for the two saved reports, reusing valid work and returning the actual call count."""
        return report_state(api.call("POST", REFRESH))

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
