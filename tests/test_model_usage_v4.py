"""Pure fixtures only: these accounting checks never invoke a provider."""
from copy import deepcopy
import math

import pytest

from proofflow.eval.model_usage_v4 import (
    DEFAULT_MODEL, UsageAccountingError, known_cost_usd, normalize_usage,
)


def usage_entry(**updates):
    return {
        "canonicalModel": DEFAULT_MODEL, "inputTokens": 10,
        "cacheCreationInputTokens": 20, "cacheReadInputTokens": 30,
        "outputTokens": 7, "costUSD": 0.25, **updates,
    }


def envelope(**updates):
    return {"modelUsage": {DEFAULT_MODEL: usage_entry()},
            "total_cost_usd": 0.25, "num_turns": 2, **updates}


def test_normalizes_only_authoritative_aggregate_view_without_mutation():
    raw = envelope(usage={
        "input_tokens": 1000, "cache_creation_input_tokens": 2000,
        "cache_read_input_tokens": 3000, "output_tokens": 7000,
    })
    raw["modelUsage"][DEFAULT_MODEL].update({
        "thinkingTokens": 6,
        "cacheCreation": {"ephemeral5mInputTokens": 20, "ephemeral1hInputTokens": 0},
    })
    before = deepcopy(raw)
    result = normalize_usage(raw)
    assert result == {
        "input_tokens": 10, "cache_creation_input_tokens": 20,
        "cache_read_input_tokens": 30, "provider_input_exposure": 60,
        "output_tokens": 7, "cost_usd": 0.25, "num_turns": 2,
        "per_model": {DEFAULT_MODEL: {
            "canonical_model": DEFAULT_MODEL, "input_tokens": 10,
            "cache_creation_input_tokens": 20, "cache_read_input_tokens": 30,
            "provider_input_exposure": 60, "output_tokens": 7, "cost_usd": 0.25,
        }},
    }
    assert raw == before


def test_every_matching_entry_is_counted_once_and_preserved():
    raw = envelope(modelUsage={
        "first-alias": usage_entry(costUSD=0.1),
        "second-alias": usage_entry(inputTokens=100, outputTokens=9, costUSD=0.15),
    })
    result = normalize_usage(raw)
    assert result["input_tokens"] == 110
    assert result["cache_creation_input_tokens"] == 40
    assert result["cache_read_input_tokens"] == 60
    assert result["provider_input_exposure"] == 210
    assert result["output_tokens"] == 16
    assert set(result["per_model"]) == {"first-alias", "second-alias"}
    assert result["cost_usd"] == 0.25


def test_exact_model_key_is_identity_only_when_canonical_field_absent():
    raw = envelope()
    del raw["modelUsage"][DEFAULT_MODEL]["canonicalModel"]
    assert normalize_usage(raw)["per_model"][DEFAULT_MODEL]["canonical_model"] == DEFAULT_MODEL
    raw["modelUsage"]["unversioned-alias"] = raw["modelUsage"].pop(DEFAULT_MODEL)
    with pytest.raises(UsageAccountingError, match="canonical model"):
        normalize_usage(raw)


@pytest.mark.parametrize("identity", [None, "", False, [], "claude-fable-5-1"])
def test_explicit_canonical_identity_must_match(identity):
    raw = envelope()
    raw["modelUsage"][DEFAULT_MODEL]["canonicalModel"] = identity
    with pytest.raises(UsageAccountingError, match="canonical model"):
        normalize_usage(raw)


@pytest.mark.parametrize("extra", [None, 5, [], {"canonicalModel": "different-model"}])
def test_extra_malformed_or_mixed_model_entries_are_never_ignored(extra):
    raw = envelope()
    raw["modelUsage"]["extra"] = extra
    with pytest.raises(UsageAccountingError):
        normalize_usage(raw)
    assert known_cost_usd(raw) == 0.25


@pytest.mark.parametrize("field", ["inputTokens", "cacheCreationInputTokens",
                                    "cacheReadInputTokens", "outputTokens"])
def test_each_counter_is_required_even_when_zero(field):
    raw = envelope()
    del raw["modelUsage"][DEFAULT_MODEL][field]
    with pytest.raises(UsageAccountingError, match=field):
        normalize_usage(raw)
    assert known_cost_usd(raw) == 0.25


@pytest.mark.parametrize("invalid", [True, False, -1, 1.0, float("nan"), float("inf"), "1", None])
def test_counter_is_nonnegative_integer_not_bool_float_or_text(invalid):
    raw = envelope()
    raw["modelUsage"][DEFAULT_MODEL]["inputTokens"] = invalid
    with pytest.raises(UsageAccountingError, match="inputTokens"):
        normalize_usage(raw)


@pytest.mark.parametrize("turns", [None, True, False, -1, 2.0, float("nan"), float("inf"), "2"])
def test_num_turns_is_required_explicit_nonnegative_integer(turns):
    raw = envelope(num_turns=turns)
    with pytest.raises(UsageAccountingError, match="num_turns"):
        normalize_usage(raw)
    assert known_cost_usd(raw) == 0.25


def test_missing_turns_is_unknown_but_real_zero_counts_remain_zero():
    raw = envelope()
    del raw["num_turns"]
    with pytest.raises(UsageAccountingError, match="num_turns"):
        normalize_usage(raw)
    zero = envelope(num_turns=0, total_cost_usd=0,
                    modelUsage={DEFAULT_MODEL: usage_entry(inputTokens=0, cacheCreationInputTokens=0,
                                                          cacheReadInputTokens=0, outputTokens=0, costUSD=0)})
    result = normalize_usage(zero)
    assert result["num_turns"] == result["provider_input_exposure"] == result["output_tokens"] == 0
    assert result["cost_usd"] == known_cost_usd(zero) == 0.0


@pytest.mark.parametrize("invalid", [None, True, False, -0.01, float("nan"),
                                     float("inf"), -float("inf"), "0.25", 10 ** 400])
def test_invalid_top_level_cost_is_never_known_or_accepted(invalid):
    raw = envelope(total_cost_usd=invalid)
    assert known_cost_usd(raw) is None
    with pytest.raises(UsageAccountingError, match="total_cost_usd"):
        normalize_usage(raw)


@pytest.mark.parametrize("invalid", [None, True, -0.01, float("nan"), float("inf"), "0.25"])
def test_malformed_model_cost_still_retains_independently_valid_total(invalid):
    raw = envelope()
    raw["modelUsage"][DEFAULT_MODEL]["costUSD"] = invalid
    assert known_cost_usd(raw) == 0.25
    with pytest.raises(UsageAccountingError, match="costUSD"):
        normalize_usage(raw)


def test_missing_costs_are_not_inferred_or_silently_zeroed():
    raw = envelope()
    del raw["total_cost_usd"]
    assert known_cost_usd(raw) is None
    with pytest.raises(UsageAccountingError, match="total_cost_usd"):
        normalize_usage(raw)
    raw = envelope()
    del raw["modelUsage"][DEFAULT_MODEL]["costUSD"]
    assert known_cost_usd(raw) == 0.25
    with pytest.raises(UsageAccountingError, match="costUSD"):
        normalize_usage(raw)


def test_inconsistent_or_double_counted_model_costs_fail_without_erasing_total():
    raw = envelope(modelUsage={"first": usage_entry(), "duplicate": usage_entry()})
    assert known_cost_usd(raw) == 0.25
    with pytest.raises(UsageAccountingError, match="reconcile"):
        normalize_usage(raw)


def test_cost_tolerance_adds_absolute_and_relative_terms():
    # Difference exceeds either separate tolerance, but fits their specified sum.
    raw = envelope(total_cost_usd=1000.0000015,
                   modelUsage={DEFAULT_MODEL: usage_entry(costUSD=1000.0)})
    assert normalize_usage(raw)["cost_usd"] == raw["total_cost_usd"]
    raw["total_cost_usd"] = 1000.0000025
    with pytest.raises(UsageAccountingError, match="reconcile"):
        normalize_usage(raw)


def test_cost_sum_overflow_fails_closed_with_known_total_retained():
    raw = envelope(total_cost_usd=1e308,
                   modelUsage={"first": usage_entry(costUSD=1e308),
                               "second": usage_entry(costUSD=1e308)})
    assert math.isfinite(known_cost_usd(raw))
    with pytest.raises(UsageAccountingError, match="Summed model cost"):
        normalize_usage(raw)


def test_integer_token_sums_do_not_round_through_floats():
    count = 2 ** 60 + 1
    raw = envelope(modelUsage={DEFAULT_MODEL: usage_entry(inputTokens=count)})
    result = normalize_usage(raw)
    assert result["provider_input_exposure"] == count + 50
    assert type(result["provider_input_exposure"]) is int


def test_error_envelope_can_have_known_accounting_without_becoming_success():
    raw = envelope(is_error=True, subtype="error_max_budget_usd", result="Failed to produce a plan")
    assert known_cost_usd(raw) == 0.25
    assert normalize_usage(raw)["cost_usd"] == 0.25
    assert raw["is_error"] is True
    raw["modelUsage"] = None
    assert known_cost_usd(raw) == 0.25
    with pytest.raises(UsageAccountingError):
        normalize_usage(raw)


@pytest.mark.parametrize("raw", [None, [], "not an envelope", {},
                                  {"modelUsage": {DEFAULT_MODEL: usage_entry()}}])
def test_non_envelopes_and_missing_total_are_unknown(raw):
    assert known_cost_usd(raw) is None
    with pytest.raises(UsageAccountingError):
        normalize_usage(raw)


@pytest.mark.parametrize("model_usage", [None, {}, [], "bad", {"": usage_entry()}, {1: usage_entry()}])
def test_missing_empty_or_malformed_model_usage_fails(model_usage):
    raw = envelope(modelUsage=model_usage)
    with pytest.raises(UsageAccountingError):
        normalize_usage(raw)
    assert known_cost_usd(raw) == 0.25


def test_caller_can_pin_another_exact_model_without_silent_fallback():
    raw = envelope(modelUsage={"another-version": usage_entry(canonicalModel="another-version")})
    with pytest.raises(UsageAccountingError, match="canonical model"):
        normalize_usage(raw)
    assert normalize_usage(raw, expected_model="another-version")["cost_usd"] == 0.25
