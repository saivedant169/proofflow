"""Independent numeric and receipt provenance interfaces for model comparison v4.

This module accepts plain snapshots, never a runtime/store/graph object. It does
not use production currentness, retrieval output, or cached values as numeric
truth. The separate ``retail_oracle.compute_values`` remains the numeric oracle.
Expected sources are the independently staged canonical publication values;
expected tools include the frozen implementation hash and declared version.
Snapshot reads belong to scorer-only I/O, never selector-visible evidence.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from typing import Any

from .retail_oracle import (OracleContractError, compute_values, expected_affected_names,
                            verify_raw_orders)

__all__ = ["audit_provenance", "compute_values", "expected_affected_names", "verify_raw_orders", "stage_sources"]


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _logical(name: str, kind: str) -> str:
    return name if name.startswith(kind + ":") else kind + ":" + name


def _names(values: Mapping[str, Any], kind: str) -> dict[str, Any]:
    if not isinstance(values, Mapping) or not all(isinstance(k, str) and k for k in values):
        raise OracleContractError(f"Invalid {kind} logical-name mapping")
    result = {_logical(name, kind): value for name, value in values.items()}
    if len(result) != len(values):
        raise OracleContractError(f"Duplicate {kind} names after normalization")
    return result


def _identity_matches(record: Mapping[str, Any], identity: Any) -> bool:
    """Reconstruct the immutable ID without importing the production store."""
    kind, identifier = record.get("kind"), record.get("id")
    if not isinstance(kind, str) or not isinstance(identifier, str):
        return False
    marker = f":{kind}:"
    workspace, separator, _ = identifier.partition(marker)
    suffix = _digest({"logical_id": record.get("logical_id"),
                      "content_hash": record.get("content_hash"), "identity": identity})
    return bool(separator and workspace and identifier == workspace + marker + suffix)


def stage_sources(sources: Mapping[str, Any], mutations: Iterable[Any]) -> dict[str, Any]:
    """Independently apply the preregistered v4 source-patch contracts.

    Does not import the fixture's mutation helper, runtime or arithmetic tools.
    Tool-version notifications have no source-value effect. The caller derives
    expected changed source names from canonical before/after values, then
    checks actual publication and notifications against this result.
    """
    staged = deepcopy(dict(sources))
    normalized = _names(staged, "source")

    def integer(value: Any, label: str, *, positive: bool = False) -> int:
        if type(value) is not int or not -(2**63) <= value < 2**63 or (positive and value <= 0):
            raise OracleContractError(f"Invalid integer in source patch: {label}")
        return value

    for mutation in mutations:
        def field(name: str, default: Any = None) -> Any:
            return mutation.get(name, default) if isinstance(mutation, Mapping) else getattr(mutation, name, default)
        operation, parameters = field("operation"), field("parameters", {})
        if not isinstance(parameters, dict):
            raise OracleContractError("Source patch parameters must be a dictionary")
        if operation == "tool_version":
            if (not isinstance(field("tool"), str) or not field("tool")
                    or not isinstance(parameters.get("version"), str) or not parameters["version"].strip()):
                raise OracleContractError("Invalid declared tool-version patch")
            continue
        name = field("source")
        if not isinstance(name, str) or _logical(name, "source") not in normalized:
            raise OracleContractError("Source patch refers to an undeclared source")
        logical = _logical(name, "source")
        key = logical if logical in staged else logical.removeprefix("source:")
        value = staged[key]
        if value is None:
            raise OracleContractError("V4 has no source mutation after withdrawal")
        if operation == "remove":
            staged[key] = None
            continue
        if operation == "fx_set":
            if not isinstance(value, dict) or not parameters:
                raise OracleContractError("FX patch requires an existing rate mapping")
            for currency, rate in parameters.items():
                try:
                    number = Decimal(rate) if isinstance(rate, str) else Decimal("NaN")
                except InvalidOperation as error:
                    raise OracleContractError("Invalid declared FX rate") from error
                if currency not in value or not number.is_finite() or number <= 0:
                    raise OracleContractError("FX patch has an undeclared currency or invalid rate")
            value.update(parameters)
            continue
        if not isinstance(value, list) or not all(isinstance(row, dict) and isinstance(row.get("order_id"), str) for row in value):
            raise OracleContractError("Row patch requires named source rows")
        rows = {row["order_id"]: row for row in value}
        if len(rows) != len(value):
            raise OracleContractError("Duplicate row identity in staged source")
        try:
            if operation == "refund_add":
                identifier, amount = parameters["order_id"], integer(parameters["refund_cents"], "refund", positive=True)
                orders_name = logical.removesuffix(":refunds") + ":orders"
                orders_key = orders_name if orders_name in staged else orders_name.removeprefix("source:")
                orders = {row["order_id"]: row for row in staged[orders_key]}
                if identifier in rows or amount > orders[identifier]["gross_cents"]:
                    raise OracleContractError("Refund patch exceeds its order or repeats a row")
                value.append({"order_id": identifier, "refund_cents": amount})
            elif operation == "quantity_delta":
                row = rows[parameters["order_id"]]
                old_quantity = integer(parameters["raw_quantity"], "raw quantity", positive=True)
                delta = integer(parameters["delta_quantity"], "quantity delta", positive=True)
                new_quantity = integer(parameters["new_quantity"], "new quantity", positive=True)
                if old_quantity + delta != new_quantity or new_quantity > 10**9:
                    raise OracleContractError("Declared quantity patch is inconsistent")
                price = parameters["unit_price_gbp"]
                if not isinstance(price, str):
                    raise OracleContractError("Quantity patch needs exact decimal price text")
                with localcontext() as context:
                    context.prec = 80
                    unit = Decimal(price)
                    old_amount, new_amount = unit * old_quantity * 100, unit * new_quantity * 100
                if (not unit.is_finite() or unit <= 0 or old_amount != old_amount.to_integral_value()
                        or new_amount != new_amount.to_integral_value() or not 0 < new_amount <= 10**12
                        or integer(parameters["old_gross_cents"], "old amount") != int(old_amount)
                        or integer(parameters["new_gross_cents"], "new amount") != int(new_amount)
                        or row["gross_cents"] != int(old_amount)):
                    raise OracleContractError("Declared quantity amounts disagree with raw arithmetic")
                row["gross_cents"] = int(new_amount)
            elif operation == "offset_gross":
                first, second = rows[parameters["first"]], rows[parameters["second"]]
                delta = integer(parameters["delta_cents"], "offset", positive=True)
                if (first is second or first["region"] != second["region"]
                        or first["gross_cents"] != integer(parameters["first_old_gross_cents"], "first old amount")
                        or second["gross_cents"] != integer(parameters["second_old_gross_cents"], "second old amount")):
                    raise OracleContractError("Offset patch needs distinct same-country matching rows")
                first["gross_cents"] += delta
                second["gross_cents"] -= delta
                if not 0 < first["gross_cents"] <= 10**12 or not 0 < second["gross_cents"] <= 10**12:
                    raise OracleContractError("Offset patch violates supported amount bounds")
            elif operation == "reorder":
                value.reverse()
            else:
                raise OracleContractError(f"Unsupported v4 source patch: {operation}")
        except (KeyError, TypeError, InvalidOperation) as error:
            raise OracleContractError(f"Invalid declared source patch: {operation}") from error
        value.sort(key=lambda row: row["order_id"])
    return staged


def _contracts(recipes: Iterable[Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for recipe in recipes:
        def field(name: str, default: Any = None) -> Any:
            return recipe.get(name, default) if isinstance(recipe, Mapping) else getattr(recipe, name, default)
        name, tool, inputs, params = field("name"), field("tool"), field("inputs"), field("params", {})
        if (not isinstance(name, str) or not name or not isinstance(tool, str) or not tool
                or not isinstance(inputs, dict) or not isinstance(params, dict)
                or not all(isinstance(k, str) and isinstance(v, str) for k, v in inputs.items())):
            raise OracleContractError("Invalid provenance recipe declaration")
        logical = _logical(name, "artifact")
        if logical in result:
            raise OracleContractError("Duplicate provenance recipe declaration")
        result[logical] = {"name": name, "tool": tool, "params": params,
                           "inputs": {port: ref if ref.startswith("source:") else _logical(ref, "artifact")
                                      for port, ref in inputs.items()}}
    for contract in result.values():
        for reference in contract["inputs"].values():
            if reference.startswith("artifact:") and reference not in result:
                raise OracleContractError(f"Undeclared artifact reference: {reference}")
    return result


def audit_provenance(
    recipes: Iterable[Any], records: Mapping[str, Mapping[str, Any]],
    artifact_heads: Mapping[str, str], source_heads: Mapping[str, str | None],
    tool_heads: Mapping[str, str | None], expected_sources: Mapping[str, Any],
    expected_tools: Mapping[str, Mapping[str, Any]],
    prior_records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Audit current heads and their entire consumed receipt chains.

    ``records[id]`` contains ``id, kind, logical_id, content_hash, metadata,
    value``. Head mappings can use bare or namespace-prefixed logical names.
    Expected source ``None`` means unavailable; either an absent head or an
    explicit tombstone is accepted. Expected live source/tool identities are
    reconstructed from their declared immutable-ID contract, not trusted from
    runtime notifications. Every supplied recipe is scored, including missing
    heads. An older consumed artifact need not be today's artifact head: it is
    valid if its own recursive provenance still reaches current sources/tools.

    A missing source deliberately makes dependent provenance noncurrent. The
    caller combines that result with independent numeric availability to score
    a correct refusal, and records the runtime-claimed currentness separately.
    ``head_validation_pass`` must also hold for a valid scored snapshot.

    A scored v4 execution must supply an immutable copy of ``prior_records``
    captured before execution. Every pre-existing ID must retain exactly its
    old record/value; new records are permitted. This anchor detects rewriting
    an old artifact into a different, internally consistent receipt chain.
    Omitting it is supported for isolated unit snapshots, but returns an
    explicit unchecked/None anchor result and cannot satisfy the scored gate.
    """
    immutable_errors = {}
    if prior_records is not None:
        if not isinstance(prior_records, Mapping) or not prior_records:
            raise OracleContractError("Prior immutable snapshot must be a nonempty complete record mapping")
        for identifier, original in prior_records.items():
            if identifier not in records:
                immutable_errors[identifier] = "previous_immutable_record_missing"
                continue
            try:
                if _digest(original) != _digest(records[identifier]):
                    immutable_errors[identifier] = "previous_immutable_record_changed"
            except (ValueError, TypeError) as error:
                raise OracleContractError("Immutable snapshots must contain canonical JSON") from error
    contracts = _contracts(recipes)
    artifacts = _names(artifact_heads, "artifact")
    source_ids, tool_ids = _names(source_heads, "source"), _names(tool_heads, "tool")
    sources, tools = _names(expected_sources, "source"), _names(expected_tools, "tool")
    try:
        for value in [*sources.values(), *tools.values()]:
            _digest(value)
    except (ValueError, TypeError) as error:
        raise OracleContractError("Expected source/tool values must be canonical JSON") from error
    required_sources = {ref for c in contracts.values() for ref in c["inputs"].values()
                        if ref.startswith("source:")}
    required_tools = {_logical(c["tool"], "tool") for c in contracts.values()}
    if required_sources - sources.keys() or required_tools - tools.keys():
        raise OracleContractError("Expected current source/tool declarations are incomplete")
    if source_ids.keys() - sources.keys() or tool_ids.keys() - tools.keys():
        raise OracleContractError("Head snapshot includes an undeclared source/tool")

    def read(identifier: str | None) -> tuple[Mapping[str, Any] | None, list[str]]:
        if identifier is not None and not isinstance(identifier, str):
            return None, ["invalid_record_identifier"]
        if identifier is None or identifier not in records:
            return None, [f"missing_record:{identifier}"]
        record = records[identifier]
        if not isinstance(record, Mapping):
            return None, [f"invalid_record:{identifier}"]
        reasons = []
        if record.get("id") != identifier:
            reasons.append(f"record_identity_mismatch:{identifier}")
        if "value" not in record:
            reasons.append(f"missing_value:{identifier}")
        else:
            try:
                if _digest(record["value"]) != record.get("content_hash"):
                    reasons.append(f"content_hash_mismatch:{identifier}")
            except (ValueError, TypeError):
                reasons.append(f"invalid_json_value:{identifier}")
        if not isinstance(record.get("metadata"), dict):
            reasons.append(f"invalid_metadata:{identifier}")
        return record, reasons

    head_errors: dict[str, list[str]] = {}
    for kind, expected, heads in (("source", sources, source_ids), ("tool", tools, tool_ids)):
        for logical, value in expected.items():
            identifier = heads.get(logical)
            if kind == "source" and value is None and identifier is None:
                continue
            record, reasons = read(identifier)
            if record is not None:
                metadata = record.get("metadata")
                metadata = metadata if isinstance(metadata, Mapping) else {}
                deleted = kind == "source" and value is None
                if record.get("kind") != kind or record.get("logical_id") != logical:
                    reasons.append(f"head_kind_or_logical_mismatch:{logical}")
                if record.get("value") != value:
                    reasons.append(f"head_value_differs_from_declared_stage:{logical}")
                if kind == "source" and bool(metadata.get("deleted")) != deleted:
                    reasons.append(f"head_deletion_mismatch:{logical}")
                if kind == "tool" and (not isinstance(value, Mapping)
                        or value.get("name") != logical.removeprefix("tool:")
                        or not isinstance(value.get("version"), str)
                        or not isinstance(value.get("implementation_hash"), str)):
                    reasons.append(f"invalid_expected_tool_contract:{logical}")
                # Published sources/tools use deterministic identity=None;
                # source tombstones use identity={deleted: True}.
                declared_record = {**record, "logical_id": logical, "content_hash": _digest(value)}
                if not _identity_matches(declared_record, {"deleted": True} if deleted else None):
                    reasons.append(f"head_immutable_identity_mismatch:{logical}")
            if reasons:
                head_errors[logical] = sorted(set(reasons))

    memo: dict[str, tuple[set[str], set[str]]] = {}

    def visit(identifier: str, logical: str, stack: frozenset[str]) -> tuple[set[str], set[str]]:
        if not isinstance(identifier, str):
            return {"invalid_artifact_head_identifier"}, set()
        if identifier in stack:
            return {f"receipt_cycle:{identifier}"}, {identifier}
        if identifier in memo:
            record = records.get(identifier, {})
            reasons, visited = memo[identifier]
            return (reasons | ({f"input_logical_mismatch:{identifier}"}
                              if record.get("logical_id") != logical else set()), set(visited))
        record, initial = read(identifier)
        reasons, visited = set(initial), {identifier}
        if identifier in immutable_errors:
            reasons.add(f"{immutable_errors[identifier]}:{identifier}")
        if record is None:
            return reasons, visited
        if record.get("logical_id") != logical:
            reasons.add(f"input_logical_mismatch:{identifier}")
        if logical.startswith("source:"):
            if record.get("kind") != "source":
                reasons.add(f"input_kind_mismatch:{identifier}")
            if logical in head_errors:
                reasons.update(head_errors[logical])
            if sources.get(logical) is None:
                reasons.add(f"source_unavailable:{logical}")
            elif identifier != source_ids.get(logical):
                reasons.add(f"source_version_stale:{logical}")
            memo[identifier] = (set(reasons), set(visited))
            return reasons, visited
        contract = contracts.get(logical)
        if record.get("kind") != "artifact" or contract is None:
            reasons.add(f"undeclared_or_wrong_kind_artifact:{identifier}")
            return reasons, visited
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            return reasons, visited
        actual_inputs = metadata.get("inputs")
        if metadata.get("tool") != contract["tool"] or metadata.get("params") != contract["params"]:
            reasons.add(f"recipe_tool_or_params_mismatch:{identifier}")
        if not isinstance(actual_inputs, dict) or actual_inputs.keys() != contract["inputs"].keys():
            reasons.add(f"recipe_input_ports_mismatch:{identifier}")
        else:
            for port, target_logical in contract["inputs"].items():
                target_id = actual_inputs[port]
                if not isinstance(target_id, str):
                    reasons.add(f"invalid_input_id:{identifier}:{port}")
                    continue
                child_reasons, child_ids = visit(target_id, target_logical, stack | {identifier})
                reasons.update(child_reasons)
                visited.update(child_ids)
        tool_logical = _logical(contract["tool"], "tool")
        tool_id = metadata.get("tool_version_id")
        tool_record, tool_reasons = read(tool_id)
        reasons.update(tool_reasons)
        if isinstance(tool_id, str):
            visited.add(tool_id)
            if tool_id in immutable_errors:
                reasons.add(f"{immutable_errors[tool_id]}:{tool_id}")
        if tool_record is not None and (tool_record.get("kind") != "tool"
                                      or tool_record.get("logical_id") != tool_logical):
            reasons.add(f"tool_kind_or_logical_mismatch:{identifier}")
        if tool_id != tool_ids.get(tool_logical):
            reasons.add(f"tool_version_stale:{tool_logical}")
        reasons.update(head_errors.get(tool_logical, []))
        receipt_id = metadata.get("receipt_id")
        receipt, receipt_reasons = read(receipt_id)
        reasons.update(receipt_reasons)
        if isinstance(receipt_id, str):
            visited.add(receipt_id)
            if receipt_id in immutable_errors:
                reasons.add(f"{immutable_errors[receipt_id]}:{receipt_id}")
        if receipt is not None:
            value = receipt.get("value")
            signature = {"tool": metadata.get("tool"), "tool_version_id": tool_id,
                         "inputs": actual_inputs, "params": metadata.get("params"),
                         "output_id": identifier, "output_hash": record.get("content_hash"),
                         "run_id": metadata.get("run_id"), "status": "success"}
            if (receipt.get("kind") != "execution" or not isinstance(value, Mapping)
                    or any(value.get(key) != wanted for key, wanted in signature.items())):
                reasons.add(f"execution_receipt_mismatch:{identifier}")
            if not _identity_matches(receipt, None):
                reasons.add(f"execution_receipt_immutable_identity_mismatch:{identifier}")
            receipt_logical = receipt.get("logical_id")
            if not isinstance(receipt_logical, str) or not receipt_logical.startswith("execution:") or not receipt_logical.removeprefix("execution:"):
                reasons.add(f"execution_invocation_missing:{identifier}")
            elif not _identity_matches(record, receipt_logical.removeprefix("execution:")):
                reasons.add(f"artifact_invocation_identity_mismatch:{identifier}")
        memo[identifier] = (set(reasons), set(visited))
        return reasons, visited

    outcomes = {}
    for logical, contract in sorted(contracts.items()):
        identifier = artifacts.get(logical)
        if identifier is None:
            reasons, visited = {f"missing_artifact_head:{logical}"}, set()
        else:
            reasons, visited = visit(identifier, logical, frozenset())
        outcomes[contract["name"]] = {"head_id": identifier, "provenance_current": not reasons,
                                     "reasons": sorted(reasons), "checked_ids": sorted(visited)}
    return {"head_validation_pass": not head_errors, "head_errors": head_errors,
            "immutable_anchor_provided": prior_records is not None,
            "immutable_anchor_pass": not immutable_errors if prior_records is not None else None,
            "immutable_anchor_records": len(prior_records) if prior_records is not None else None,
            "immutable_anchor_sha256": _digest(prior_records) if prior_records is not None else None,
            "immutable_anchor_errors": immutable_errors,
            "all_provenance_current": not head_errors and not immutable_errors and all(v["provenance_current"] for v in outcomes.values()),
            "artifacts": outcomes}
