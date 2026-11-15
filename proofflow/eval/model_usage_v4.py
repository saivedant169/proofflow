"""Strict, pure accounting for the frozen v4 Claude Code comparison.

``modelUsage`` is the sole authoritative token view. Top-level ``usage`` and
thinking/cache-lifetime subdivisions are deliberately not added to it. Callers
retain the raw envelope and separately decide whether a provider/plan succeeded.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any


DEFAULT_MODEL = "claude-fable-5-2"
COST_ABSOLUTE_TOLERANCE = 0.000001
COST_RELATIVE_TOLERANCE = 1e-9
_TOKEN_FIELDS = {
    "input_tokens": "inputTokens",
    "cache_creation_input_tokens": "cacheCreationInputTokens",
    "cache_read_input_tokens": "cacheReadInputTokens",
    "output_tokens": "outputTokens",
}


class UsageAccountingError(ValueError):
    """Accounting is unknown; the caller must stop further paid invocations."""


def _cost(value: Any, field: str) -> float:
    if type(value) not in (int, float):
        raise UsageAccountingError(f"{field} must be an explicit finite nonnegative number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise UsageAccountingError(f"{field} must be finite") from exc
    if not math.isfinite(result) or result < 0:
        raise UsageAccountingError(f"{field} must be an explicit finite nonnegative number")
    return result


def _counter(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise UsageAccountingError(f"{field} must be an explicit nonnegative integer")
    return value


def known_cost_usd(envelope: Any) -> float | None:
    """Retain a valid reported total even if every other field is malformed.

    This does not assert that accounting reconciles or that the plan succeeded.
    Missing/invalid totals are unknown; no total is inferred from model entries.
    """
    if not isinstance(envelope, Mapping):
        return None
    try:
        return _cost(envelope.get("total_cost_usd"), "total_cost_usd")
    except UsageAccountingError:
        return None


def normalize_usage(envelope: Any, expected_model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Validate aggregate model counters and reconcile reported list costs.

    A missing ``canonicalModel`` uses the exact model entry key as its identity;
    an explicitly supplied canonical identity must be a matching string. All
    entries are validated, including aliases and otherwise unexpected entries.
    Provider errors can still have valid accounting: their status is not changed
    or judged here. No token or turn counter is silently defaulted to zero.
    """
    if not isinstance(expected_model, str) or not expected_model:
        raise UsageAccountingError("expected_model must be a nonempty model identity")
    if not isinstance(envelope, Mapping):
        raise UsageAccountingError("Provider envelope must be a mapping")
    total_cost = _cost(envelope.get("total_cost_usd"), "total_cost_usd")
    num_turns = _counter(envelope.get("num_turns"), "num_turns")
    model_usage = envelope.get("modelUsage")
    if not isinstance(model_usage, Mapping) or not model_usage:
        raise UsageAccountingError("modelUsage must contain at least one model entry")

    per_model: dict[str, dict[str, Any]] = {}
    totals = {field: 0 for field in _TOKEN_FIELDS}
    for key, entry in model_usage.items():
        if not isinstance(key, str) or not key:
            raise UsageAccountingError("Every modelUsage key must be a nonempty string")
        if not isinstance(entry, Mapping):
            raise UsageAccountingError(f"modelUsage[{key}] must be a mapping")
        canonical_model = entry.get("canonicalModel", key)
        if not isinstance(canonical_model, str) or canonical_model != expected_model:
            raise UsageAccountingError(f"modelUsage[{key}] has an unexpected canonical model")
        normalized: dict[str, Any] = {"canonical_model": canonical_model}
        for field, raw_field in _TOKEN_FIELDS.items():
            count = _counter(entry.get(raw_field), f"modelUsage[{key}].{raw_field}")
            normalized[field] = count
            totals[field] += count
        normalized["provider_input_exposure"] = (
            normalized["input_tokens"] + normalized["cache_creation_input_tokens"]
            + normalized["cache_read_input_tokens"]
        )
        normalized["cost_usd"] = _cost(entry.get("costUSD"), f"modelUsage[{key}].costUSD")
        per_model[key] = normalized

    try:
        model_cost = math.fsum(entry["cost_usd"] for entry in per_model.values())
    except OverflowError as exc:
        raise UsageAccountingError("Summed model cost must be finite") from exc
    if not math.isfinite(model_cost):
        raise UsageAccountingError("Summed model cost must be finite")
    tolerance = COST_ABSOLUTE_TOLERANCE + COST_RELATIVE_TOLERANCE * max(total_cost, model_cost)
    if abs(total_cost - model_cost) > tolerance:
        raise UsageAccountingError("total_cost_usd does not reconcile with summed model costUSD")

    return {
        **totals,
        "provider_input_exposure": (totals["input_tokens"] + totals["cache_creation_input_tokens"]
                                    + totals["cache_read_input_tokens"]),
        "cost_usd": total_cost,
        "num_turns": num_turns,
        "per_model": per_model,
    }
