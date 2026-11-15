"""Cookie-owned browser CSV workspaces using the existing guided import recipe."""
from __future__ import annotations

from contextlib import contextmanager
import json
import shutil
import time
from typing import Any
import uuid

from .artifacts import ArtifactStore, digest
from .demo import DemoSession, ID_PATTERN, SessionMissing, now, unwrap_native
from .graph import GraphError
from .importing import (COMPANY_REPORT, REGION_REPORT, SUPPORT_ARTIFACT, CSVImportError,
                        MAX_BYTES, ImportedDataset, _apply_preflighted_import,
                        parse_csv, recipe_calculation_count)
from .models import InvalidInputError, MissingEvidenceError
from .runtime import ProofFlowRuntime


JS_MAX_SAFE_INTEGER = 2**53 - 1


def _browser_cents(value: int | None) -> int | str | None:
    # Keep full precision when the browser parses JSON numbers as IEEE 754 doubles.
    return str(value) if type(value) is int and abs(value) > JS_MAX_SAFE_INTEGER else value


def _browser_claim(claim: dict[str, Any]) -> dict[str, Any]:
    if claim.get("unit") != "USD cents":
        return claim
    return {**claim, **{key: _browser_cents(claim[key]) for key in ("value", "saved_value") if key in claim}}


def validated_csv(payload: dict) -> ImportedDataset:
    if not isinstance(payload, dict) or set(payload) - {"csv_text", "rates", "region"} or "csv_text" not in payload:
        raise CSVImportError("CSV request accepts csv_text, rates and region only")
    text = payload["csv_text"]
    if not isinstance(text, str) or len(text) > MAX_BYTES:
        raise CSVImportError("CSV must contain at most 1 MiB of UTF-8 text")
    region = payload.get("region")
    if region is not None and (not isinstance(region, str) or not region):
        raise CSVImportError("Region must be an existing nonempty region name")
    rates = payload.get("rates", {})
    if not isinstance(rates, dict):
        raise CSVImportError("Rates must map EUR/GBP currencies to explicit USD decimal strings")
    try:
        encoded = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CSVImportError("CSV must contain valid UTF-8 text") from exc
    return parse_csv(encoded, rates=rates, region=region)


def dataset_metadata(dataset: ImportedDataset) -> dict[str, Any]:
    return {"selected_region": dataset.region, "row_count": dataset.row_count,
            "source_csv_sha256": dataset.content_sha256,
            "regions": sorted({row["region"] for row in dataset.sources["orders"]}),
            "currencies": sorted({row["currency"] for row in dataset.sources["orders"]})}


def preview(payload: dict) -> dict[str, Any]:
    dataset = validated_csv(payload)
    metadata = dataset_metadata(dataset)
    return {"valid": True, "persisted": False, "content_sha256": dataset.content_sha256,
            "row_count": dataset.row_count, "regions": metadata["regions"],
            "currencies": metadata["currencies"], "selected_region": dataset.region,
            "rates": dataset.sources["fx"],
            "supported_ticket_regions": sorted({row["region"] for row in dataset.sources["tickets"]}),
            "preflight_calculation_count": 8, "recorded_tool_calls": 0,
            "accounting": {"preflight_calculation_count": 8, "recorded_tool_call_count": 0,
                           "verification_calculation_count": 0, "total_calculation_count": 8}}


class BrowserImport:
    # Reuse native-edge verification from the authored demonstration.
    _graph_state = DemoSession._graph_state

    def __init__(self, owner: DemoSession, metadata: dict, graph_factory):
        self.owner = owner
        self.metadata = metadata
        workspace_id = metadata.get("workspace_id")
        if not isinstance(workspace_id, str) or not ID_PATTERN.fullmatch(workspace_id):
            raise SessionMissing("Unknown imported workspace")
        self.directory = owner.directory / "imports" / workspace_id
        self.store = ArtifactStore(self.directory)
        try:
            self.graph = graph_factory(namespace=f"browser-import-{self.store.workspace}")
        except Exception:
            self.store.close()
            raise
        self.runtime = ProofFlowRuntime(self.store, self.graph)

    def close(self):
        self.store.close()
        self.graph.close()

    def save(self):
        self.owner.save()

    def reports(self):
        return [("company", self.store.get_head(COMPANY_REPORT)),
                ("region", self.store.get_head(REGION_REPORT))]

    @staticmethod
    def label(record):
        labels = {"import:metric:gross": "Gross regional revenue", "import:metric:refunds": "Regional refunds",
                  "import:metric:net": "Net regional revenue", "import:metric:regional": "Regional USD revenue",
                  "import:metric:company": "Company revenue", SUPPORT_ARTIFACT: "Imported support counts",
                  "source:csv:orders": "Imported orders", "source:csv:refunds": "Imported refunds",
                  "source:csv:fx": "Explicit exchange rates", "source:csv:tickets": "Imported ticket counts"}
        return labels.get(record.logical_id, record.metadata.get("title", record.logical_id))

    def evidence(self, artifact_id: str, generation: str | None = None) -> dict:
        # The API holds the owning session lock across this entire read. A
        # generation-bound request receives only the agent's restricted envelope.
        if generation is not None:
            return self._agent_evidence(artifact_id, generation)
        evidence = DemoSession.evidence(self, artifact_id)
        artifact = evidence["artifact"]
        saved = artifact["saved_value"]
        display = saved
        tool = artifact["metadata"].get("tool")
        if tool == "compose_report":
            display = {**saved, "sections": [_browser_claim(section) for section in saved["sections"]]}
        elif tool == "company_total":
            display = {**saved, "usd_cents": _browser_cents(saved["usd_cents"])}
        elif tool == "convert_to_usd":
            display = {**saved, "regions": {
                name: {**row, "usd_cents": _browser_cents(row["usd_cents"])}
                for name, row in saved["regions"].items()
            }}
        if display != saved:
            # The immutable artifact payload and its content hash stay canonical.
            evidence["display_saved_value"] = display
        return evidence

    def _agent_evidence(self, artifact_id: str, generation: str) -> dict:
        if generation != self.metadata["workspace_id"]:
            raise MissingEvidenceError("The imported workspace has changed since this artifact was selected")
        if self.metadata.get("incomplete_update"):
            raise MissingEvidenceError("Complete the CSV update before inspecting report evidence")
        record = self.store.get(artifact_id, required=False)
        if record is None or record.kind != "artifact":
            raise SessionMissing("Unknown artifact in this session")
        try:
            return self._checked_agent_evidence(record, generation)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise MissingEvidenceError("The selected artifact's evidence is malformed") from exc

    def _checked_agent_evidence(self, record, generation: str) -> dict:
        artifact_id = record.id
        validity = self.runtime.currentness(artifact_id)
        if validity.state not in {"current", "stale"}:
            raise MissingEvidenceError("The selected artifact has incomplete evidence")
        receipt_record, receipt = self._agent_receipt(record)
        head = self.store.get_head(record.logical_id)
        if head is None:
            raise MissingEvidenceError("The selected artifact has no current head")
        inputs = []
        for name, node_id in sorted(receipt["inputs"].items()):
            source = self.store.get(node_id)
            if source.kind not in {"source", "artifact"}:
                raise MissingEvidenceError("The selected artifact has an invalid input record")
            inputs.append({"name": name, "id": source.id, "kind": source.kind,
                           "logical_id": source.logical_id, "content_hash": source.content_hash,
                           "inspectable": source.kind == "artifact"})
        # Reverse ancestor discovery alone cannot establish forward receipt edges.
        # Validate all discovered artifact producers, including untouched ancestors.
        ancestors = set(self.graph.ancestors([artifact_id], max_depth=15))
        expected_edges = set()
        for node_id in sorted(ancestors | {artifact_id}):
            ancestor = self.store.get(node_id)
            if ancestor.kind != "artifact":
                continue
            producer, produced = self._agent_receipt(ancestor)
            expected_edges.add((producer.id, ancestor.id, "PRODUCED"))
            expected_edges.add((produced["tool_version_id"], producer.id, "USED_TOOL"))
            expected_edges.update((source, producer.id, "CONSUMED") for source in produced["inputs"].values())
        for source, target, kind in sorted(expected_edges):
            paths = self._agent_paths(source, target, max_depth=1)
            if not paths or any(path["edges"] != [{"source": source, "target": target, "kind": kind}]
                                for path in paths):
                raise GraphError("The selected receipt has incomplete native edges")
        changed_paths = []
        for source_id in self.metadata.get("changed_source_ids", []):
            paths = self._agent_paths(source_id, artifact_id)
            if source_id in ancestors and not paths:
                raise GraphError("A changed-source ancestor has no native path witness")
            changed_paths.extend(paths)
        reasons = []
        for reason in validity.reasons:
            if reason["reason"] not in {"version_changed", "implementation_changed"}:
                raise MissingEvidenceError("The selected artifact has incomplete currentness evidence")
            reasons.append({key: reason[key] for key in ("id", "reason", "current_id") if key in reason})
        return {
            "schema_version": 1, "generation": generation, "incomplete_update": False,
            "backend": {"engine": "HydraDB OSS", "native_queries": self.graph.queries, "fallback": False},
            "artifact": {"id": record.id, "kind": record.kind, "logical_id": record.logical_id,
                         "content_hash": record.content_hash, "state": validity.state,
                         "current_head_id": head.id, "reasons": reasons},
            "receipt": {"id": receipt_record.id, "content_hash": receipt_record.content_hash,
                        **{key: receipt[key] for key in ("tool", "tool_version_id", "status", "output_id", "output_hash")}},
            "inputs": inputs,
            "recorded_changed_source_paths": changed_paths,
            "path_scope": "Native path witnesses from recorded changed-source versions, including earlier corrections; "
                          "at most three paths per source, depth at most 15. An empty list is not a currentness verdict.",
        }

    def _agent_receipt(self, record):
        receipt_record = self.store.get(record.metadata["receipt_id"])
        receipt = self.store.read(receipt_record.id)
        if (receipt_record.kind != "execution" or receipt["status"] != "success"
                or receipt["output_id"] != record.id or receipt["output_hash"] != record.content_hash
                or any(receipt[key] != record.metadata[key]
                       for key in ("inputs", "tool", "tool_version_id", "params"))
                or receipt_record.metadata["tool"] != receipt["tool"]):
            raise MissingEvidenceError("The selected artifact's producing receipt is incomplete")
        return receipt_record, receipt

    def _agent_paths(self, source_id: str, target_id: str, *, max_depth: int = 15) -> list[dict]:
        """Project only native path witnesses whose keys, direction and receipts agree."""
        try:
            return self._validated_agent_paths(source_id, target_id, max_depth=max_depth)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise GraphError("The native path response is incomplete") from exc

    def _validated_agent_paths(self, source_id: str, target_id: str, *, max_depth: int) -> list[dict]:
        results = []
        native_paths = self.graph.paths(source_id, target_id, max_depth=max_depth)
        if not isinstance(native_paths, list) or len(native_paths) > 3:
            raise GraphError("Unexpected native path response")
        for native in native_paths:
            nodes, by_native_id = [], {}
            for item in native["nodes"]:
                properties = item["properties"]
                key = unwrap_native(properties["key"])
                record = self.store.get(key, required=False) if isinstance(key, str) else None
                if (record is None or item["id"] != self.graph.vertex_id(key)
                        or unwrap_native(properties["kind"]) != record.kind
                        or unwrap_native(properties["workspace"]) != self.graph.namespace
                        or item["id"] in by_native_id):
                    raise GraphError("Native path vertex does not match this workspace")
                payload = json.loads(unwrap_native(properties["payload"]))
                expected_payload = {"logical_id": record.logical_id, "content_hash": record.content_hash,
                                    "created_at": record.created_at, **record.metadata}
                if payload != expected_payload:
                    raise GraphError("Native path vertex content does not match its immutable record")
                by_native_id[item["id"]] = record
                nodes.append({"id": record.id, "kind": record.kind, "logical_id": record.logical_id})
            if (not 2 <= len(nodes) <= max_depth + 1 or nodes[0]["id"] != source_id
                    or nodes[-1]["id"] != target_id
                    or len(native["relationships"]) != len(nodes) - 1):
                raise GraphError("Native path endpoints or length do not match")
            edges = []
            for index, edge in enumerate(native["relationships"]):
                source, target = by_native_id[edge["src"]], by_native_id[edge["dst"]]
                kind = unwrap_native(edge["properties"]["kind"])
                if (edge["edge_type"] != "FLOW" or source.id != nodes[index]["id"]
                        or target.id != nodes[index + 1]["id"]):
                    raise GraphError("Native path direction or relationship is invalid")
                if kind == "PRODUCED" and source.kind == "execution" and target.kind == "artifact":
                    receipt_record, _ = self._agent_receipt(target)
                    valid = receipt_record.id == source.id
                elif kind == "CONSUMED" and source.kind in {"source", "artifact"} and target.kind == "execution":
                    valid = source.id in self.store.read(target.id)["inputs"].values()
                elif kind == "USED_TOOL" and source.kind == "tool" and target.kind == "execution":
                    valid = self.store.read(target.id)["tool_version_id"] == source.id
                else:
                    valid = False
                if not valid:
                    raise GraphError("Native path relationship does not match its execution receipt")
                edges.append({"source": source.id, "target": target.id, "kind": kind})
            results.append({"source_id": source_id, "target_id": target_id, "nodes": nodes, "edges": edges})
        return results

    def _operation(self, kind: str, *, started: float, preflight: int = 0, verification: int = 0,
                   changed: int = 0, noop: bool = False, calls: list[dict] | None = None) -> dict:
        calls = list(self.runtime.calls if calls is None else calls)
        return {"kind": kind, "preflight_calculation_count": preflight,
                "recorded_tool_call_count": len(calls), "verification_calculation_count": verification,
                "total_calculation_count": preflight + len(calls) + verification,
                "changed_source_count": changed, "noop": noop,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
                "tool_calls": [{key: call.get(key) for key in ("tool", "status", "elapsed_ms", "output_id")} for call in calls]}

    def state(self) -> dict:
        statuses, reports = {}, []
        for key, record in self.reports():
            if record is None:
                raise MissingEvidenceError("Imported report is unavailable")
            status = self.runtime.currentness(record.id)
            statuses[record.id] = status.state
            reports.append({"key": key, "id": record.id, "title": self.label(record),
                            "run_id": record.metadata["run_id"], "state": status.state,
                            "claims": [_browser_claim(claim) for claim in self.runtime.report_claims(record.id)]})
        sources = []
        for record in self.store.heads("source"):
            value = self.store.read(record.id)
            sources.append({"name": record.metadata["name"].removeprefix("csv:"), "id": record.id,
                            "content_hash": record.content_hash, "removed": bool(record.metadata.get("deleted")),
                            "summary": {"rows": len(value)} if isinstance(value, list) else value})
        graph = self._graph_state(statuses)
        return {"session_id": self.owner.id, "generation": self.metadata["workspace_id"],
                "created_at": self.metadata["created_at"], "mode": "guided_csv_import",
                "backend": {"engine": "HydraDB OSS", "native_queries": self.graph.queries, "fallback": False},
                "dataset": {"label": "Imported CSV", **self.metadata["dataset"], "sources": sources},
                "reports": reports, "graph": graph,
                "executions": [{"id": record.id, **self.store.read(record.id)} for record in self.store.list_records("execution")],
                "impact": {"change": self.metadata.get("change"),
                           "affected_artifacts": self.metadata.get("affected_artifacts", []),
                           "changed_source_ids": self.metadata.get("changed_source_ids", [])},
                "last_operation": self.metadata["last_operation"],
                "last_refresh": self.metadata.get("last_refresh"),
                "incomplete_update": bool(self.metadata.get("incomplete_update")),
                "notices": ["User-supplied CSV; guided company and selected-region money reports. No browser model call.",
                            "Ticket counts expand into synthetic counting rows; no missing zero-ticket claim is fabricated.",
                            "Counters separate input preflight, recorded execution and fresh-recipe verification.",
                            "CSV source versions publish individually; an incomplete update must be resubmitted before refresh."]}

    def export_reports(self, generation: str, report_ids: dict[str, str]) -> dict[str, str]:
        if generation != self.metadata["workspace_id"]:
            raise MissingEvidenceError("The imported workspace has changed since these reports were shown")
        if self.metadata.get("incomplete_update"):
            raise MissingEvidenceError("Complete the CSV update before preparing a report snapshot")

        unavailable = "Both imported reports and their revenue claims must be current and complete"
        try:
            company, region = (record for _, record in self.reports())
            if (company is None or region is None
                    or company.id != report_ids["company"] or region.id != report_ids["region"]):
                raise MissingEvidenceError(unavailable)
            selected_region = self.metadata["dataset"]["selected_region"]
            if not isinstance(selected_region, str) or not selected_region:
                raise MissingEvidenceError(unavailable)

            lines = []
            for record, claim_key, label in (
                (company, "company_revenue", "Company net revenue"),
                (region, "regional_revenue", f"Regional net revenue ({selected_region!r})"),
            ):
                if not self.runtime.currentness(record.id).is_current:
                    raise MissingEvidenceError(unavailable)
                claims = [claim for claim in self.runtime.report_claims(record.id) if claim["key"] == claim_key]
                if len(claims) != 1:
                    raise MissingEvidenceError(unavailable)
                claim = claims[0]
                cents = claim.get("value")
                artifact_id = record.metadata["inputs"]["revenue"]
                if (claim.get("state") != "current" or claim.get("unit") != "USD cents"
                        or type(cents) is not int or claim.get("artifact_id") != artifact_id):
                    raise MissingEvidenceError(unavailable)
                dollars, remainder = divmod(abs(cents), 100)
                sign = "-" if cents < 0 else ""
                lines.extend((f"{label}: {sign}${dollars:,}.{remainder:02d} USD",
                              f"Report artifact ID: {record.id}",
                              f"Claim artifact ID: {artifact_id}", ""))
        except (MissingEvidenceError, InvalidInputError, KeyError, TypeError, ValueError) as exc:
            raise MissingEvidenceError(unavailable) from exc

        checked_at = now()
        content = "\n".join((
            "ProofFlow current revenue reports",
            f"Checked at (UTC): {checked_at}",
            "Snapshot only. Both reports and their revenue claims were current at the check time.",
            "This file will not update after subsequent changes.",
            "",
            *lines,
        ))
        return {"filename": "proofflow-current-reports.txt", "media_type": "text/plain;charset=utf-8",
                "checked_at": checked_at, "content": content}

    def update(self, payload: dict) -> dict:
        started = time.perf_counter()
        dataset = validated_csv(payload)
        if dataset.region != self.metadata["dataset"]["selected_region"]:
            raise CSVImportError("Keep the selected region for corrections, or create a new imported workspace")
        roots = list(self.metadata.get("changed_source_ids", []))
        # Save all planned old versions before the first durable source write.
        # If any later write/read fails, a retry retains the original lineage.
        planned = [record.id for name, value in dataset.sources.items()
                   if (record := self.store.get_head(f"source:csv:{name}")) is not None
                   and record.content_hash != digest(value)]
        for source_id in [*self.metadata.get("pending_roots", []), *planned]:
            if source_id not in roots:
                roots.append(source_id)
        was_incomplete = bool(self.metadata.get("incomplete_update"))
        self.metadata.update(incomplete_update=True, pending_roots=roots)
        self.save()
        changed = 0
        for name, value in dataset.sources.items():
            change = self.runtime.set_source(f"csv:{name}", value,
                "Imported CSV count expansion; generated IDs are not original ticket IDs"
                if name == "tickets" else f"User-supplied CSV {name}; FX supplied explicitly")
            changed += int(change.changed)
        affected = self.runtime.affected(roots) if roots else []
        operation = self._operation("update", started=started, preflight=8, changed=changed,
                                    noop=changed == 0 and not was_incomplete)
        self.metadata.update(dataset=dataset_metadata(dataset), incomplete_update=False, pending_roots=[],
            changed_source_ids=roots,
            affected_artifacts=[{"id": record.id, "logical_id": record.logical_id,
                                 "title": self.label(record), "kind": record.kind} for record in affected],
            change={"kind": "csv", "label": "CSV unchanged" if operation["noop"] else "CSV sources updated",
                    "previous_source_id": None, "current_source_id": None, "timestamp": now()},
            last_operation=operation, last_refresh=None)
        self.save()
        return self.state()

    def _verification(self):
        result = DemoSession.verify(self)
        if any(row["error"] is not None for row in result["reports"]):
            # A failed recipe may already have evaluated some prerequisites.
            # Its partial count is unknown; never present a fabricated zero.
            raise MissingEvidenceError("Imported verification could not complete because required source evidence is unavailable")
        count = sum(recipe_calculation_count(self.runtime, row["id"])
                    for row in result["reports"])
        return result, count

    def refresh(self) -> dict:
        if self.metadata.get("incomplete_update"):
            raise MissingEvidenceError("CSV update was incomplete; resubmit the full corrected CSV before refreshing")
        started = time.perf_counter()
        support_before = self.store.get_head(SUPPORT_ARTIFACT)
        targets = [record.id for _, record in self.reports()] + [support_before.id]
        queries_before = self.graph.queries
        result = self.runtime.refresh(targets)
        verification, verification_count = self._verification()
        support_after = self.store.get_head(SUPPORT_ARTIFACT)
        self.metadata["last_operation"] = self._operation("refresh", started=started,
            verification=verification_count, noop=not self.runtime.calls)
        self.metadata["last_refresh"] = {
            "executed_count": len(self.runtime.calls), "reused_count": len(set(result.reused)),
            "executed_artifact_ids": list(result.executed), "reused_artifact_ids": list(dict.fromkeys(result.reused)),
            "elapsed_ms": result.elapsed_ms,
            "tool_calls": self.metadata["last_operation"]["tool_calls"],
            "numeric_parity": verification["passed"],
            "unchanged_support": support_before.id == support_after.id and support_before.content_hash == support_after.content_hash,
            "graph_queries": self.graph.queries - queries_before,
        }
        self.save()
        return self.state()

    def verify(self):
        if self.metadata.get("incomplete_update"):
            raise MissingEvidenceError("CSV update was incomplete; resubmit the full corrected CSV before verification")
        started = time.perf_counter()
        result, count = self._verification()
        self.metadata["last_operation"] = self._operation("verify", started=started, verification=count)
        self.save()
        return {**result, "accounting": self.metadata["last_operation"]}


@contextmanager
def active_import(owner: DemoSession, graph_factory):
    metadata = owner.metadata.get("import")
    if not isinstance(metadata, dict) or not metadata.get("ready"):
        raise SessionMissing("Unknown imported workspace; create one first")
    imported = BrowserImport(owner, metadata, graph_factory)
    try:
        yield imported
    finally:
        imported.close()


def create_import(owner: DemoSession, payload: dict, graph_factory) -> dict:
    started = time.perf_counter()
    dataset = validated_csv(payload)
    metadata = {"workspace_id": uuid.uuid4().hex, "created_at": now(), "ready": False,
                "dataset": dataset_metadata(dataset), "changed_source_ids": [], "affected_artifacts": [],
                "change": None, "last_refresh": None, "incomplete_update": False}
    imported = BrowserImport(owner, metadata, graph_factory)
    previous = owner.metadata.get("import")
    success = False
    try:
        result = _apply_preflighted_import(imported.runtime, dataset)
        metadata.update(ready=True, last_operation=imported._operation("create", started=started,
            preflight=8, verification=result["verification_calculation_count"], changed=4))
        state = imported.state()
        owner.metadata["import"] = metadata
        owner.save()
        success = True
        return state
    finally:
        imported.close()
        if not success:
            if previous is None:
                owner.metadata.pop("import", None)
            else:
                owner.metadata["import"] = previous
            shutil.rmtree(imported.directory)
