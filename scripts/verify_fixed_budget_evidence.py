#!/usr/bin/env python3
"""Recheck all 88 saved fixed-budget cells using the Python standard library."""

from argparse import ArgumentParser
from collections import Counter, defaultdict, deque
from datetime import datetime
from hashlib import sha256
from itertools import product
import json
import re
from pathlib import Path
import sys

# The exact extracted inventory excludes interpreter bytecode.
sys.dont_write_bytecode = True
_HELPER_SHA256 = {
    "audit_model_comparison_v4.py": "705a897868e1bdef21b1da597481899f5078c5c6a231272505711315bc125db6",
    "fixed_budget_tokenizer.py": "6c20632488add20f70a96b16db3c37b4cb0ebc046769c1b7ec852c63453aede7",
}
for name, expected in _HELPER_SHA256.items():
    helper = Path(__file__).resolve().with_name(name)
    if helper.is_symlink() or not helper.is_file() or sha256(helper.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Fixed-budget evidence helper verification failed: {name}")

import audit_model_comparison_v4 as audit
from fixed_budget_tokenizer import VOCABULARY_SHA256, token_counter


RUN = Path("results/fixed-budget-diagnostic-v1")
PUBLICATION = RUN / "publication"
FREEZE = Path("fixtures/fixed_budget_diagnostic/freeze.json")
VOCABULARY = FREEZE.with_name("cl100k_base.tiktoken")
VOCABULARY_LICENSE = FREEZE.with_name("TIKTOKEN_LICENSE")
EVIDENCE = Path("evidence/fixed_budget_witnesses_v1.jsonl")
AUDITOR = Path("scripts/audit_model_comparison_v4.py")
TOKENIZER = Path("scripts/fixed_budget_tokenizer.py")
VERIFIER = Path("scripts/verify_fixed_budget_evidence.py")
MANIFEST = Path("manifest.json")
PROTOCOL = Path("docs/FIXED_BUDGET_DIAGNOSTIC_PROTOCOL.md")
SUMMARY = RUN / "summary.json"
RUN_MANIFEST = RUN / "run_manifest.json"
RECOVERED = PUBLICATION / "recovered_cells.jsonl"
RECOVERED_SUMMARY = PUBLICATION / "recovered_summary.json"
ORIGINAL_INVENTORY = PUBLICATION / "original_evidence_sha256.json"
REVISION = "4f43dd497a05078edf226de62070778b17d91498"
FREEZE_SHA256 = "cd609ff71f8f74162fb2ae911e8f7cae6d1429db347debff79a1e69fd857f92f"
RECOVERED_CELLS_SHA256 = "69f05f6d063f0e4417ffeacc4aac3795572844d9241eb48536bd439589ab415a"
PINS = {
    FREEZE: FREEZE_SHA256,
    RUN_MANIFEST: "d3579815f2f2c6d8c7f1948c86badd2e7104288ced930447703b3aee20a3cbb7",
    SUMMARY: "19b100a8bb4892408b4620c3582ac97cf4327c5dd27940707b722cbfcf67cc8b",
    ORIGINAL_INVENTORY: "0756e6f1cb859fb0979c42557490f656b7c3b976521e533d2b06fa3f8cb1bb51",
    RECOVERED_SUMMARY: "01b843c0c0f851b8a71293a10cdd8f9a4ae8d95b14c6008a51ce326022fdf027",
}
# The byte binding of the public copies of the redacted freeze, run and case
# metadata is checked separately from the recorded historic path-bearing digests.
PUBLIC_INPUTS_SHA256 = "f5a26ecaadb5d2ae55c0eeacd26b874bf165feb54d01c8fcf025631db84aaca6"
WITNESS_SHA256 = "7e42c1aea2056ed2d579c7ab47cad9574b706c7e1da39ff6edf8935f61bb48eb"
WRAPPER_ERROR = {"type": "KeyError", "message": "'verified_report_counts'"}
KNOWN_SCORE_REDACTIONS = ("/independent_audit_path", "/post_snapshot_path")
BUDGETS = (4096, 8192)
ARMS = audit.ARMS
CASES = audit.CASES
ARTIFACT_FILES = ("case.json", "initial_records.json", "current_sources.json", "corpus.jsonl")
SAFETY_KEYS = {
    "fresh_affected": "fresh_affected",
    "unavailable_blocked": "correctly_blocked",
    "unaffected_preserved": "unaffected_artifacts_preserved",
    "incorrect_current": "incorrect_current",
}


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def binding(data):
    return {"bytes": len(data), "sha256": audit.sha(data)}


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line, object_pairs_hook=audit.unique_dict, parse_constant=audit.reject_constant)
                for line in stream]


def cells():
    for index, case in enumerate(CASES):
        offset = index % len(ARMS)
        for arm in ARMS[offset:] + ARMS[:offset]:
            for cap in ((None,) if arm == "full_context" else BUDGETS):
                condition = f"fixed_{cap}" if cap else "uncapped_reference"
                yield {"cell_id": f"{case}/{condition}/{arm}", "case_id": case, "arm": arm,
                       "condition": condition, "cap": cap}


def original_paths():
    return (
        {RUN_MANIFEST, SUMMARY}
        | {RUN / case / name for case, name in product(CASES, ("case.json", "setup.json"))}
        | {RUN / cell["cell_id"] / name for cell, name in product(cells(), ("attempt.json", "context.jsonl"))}
    )


def march_paths():
    days = tuple(f"2011-03-{day:02}" for day in range(1, 5))
    return (
        {audit.FIXTURE / f"{day}.{extension}" for day, extension in product(days, ("csv", "provenance.json"))}
        | {audit.FIXTURE / "fixture.json", audit.FIXTURE / "DATASET_NOTICE.md"}
        | {audit.PREPARED / case / filename for case, filename in product(CASES, ARTIFACT_FILES)}
    )


def redacted_paths():
    return {FREEZE, RUN_MANIFEST} | {audit.PREPARED / case / "case.json" for case in CASES}


def source_paths():
    return original_paths() | march_paths() | {
        FREEZE, VOCABULARY, VOCABULARY_LICENSE, AUDITOR, TOKENIZER, VERIFIER, EVIDENCE,
        RECOVERED, RECOVERED_SUMMARY, ORIGINAL_INVENTORY, PROTOCOL, Path("LICENSE"),
    }


def original_digest(inventory, path):
    entry = inventory[path.as_posix()]
    return entry.get("original", entry)["sha256"]


def valid_binding(info):
    return (set(info) == {"bytes", "sha256"} and type(info["bytes"]) is int
            and info["bytes"] > 0 and re.fullmatch(r"[0-9a-f]{64}", info["sha256"]) is not None)


def named_index(rows, key, label):
    records = {row[key]: row for row in rows}
    audit.check(len(records) == len(rows), label, "duplicate record identity")
    return records


def verify_inventory(root):
    expected = source_paths() | {Path("README.md")}
    directories = {parent for path in expected for parent in path.parents if parent != Path(".")}
    entries = {path.relative_to(root) for path in root.rglob("*")}
    audit.check(entries == expected | directories | {MANIFEST}, "exact extracted fixed-budget inventory")
    for path in expected | {MANIFEST}:
        target = root / path
        audit.check(target.resolve() == target and target.is_file(), path, "regular bundle file")
    for path in directories:
        target = root / path
        audit.check(target.resolve() == target and target.is_dir(), path, "regular bundle directory")
    manifest = audit.load(root / MANIFEST)
    inventory = manifest["files"]
    audit.check(manifest["schema_version"] == 1 and manifest["frozen_study_revision"] == REVISION
                and set(inventory) == {name.as_posix() for name in expected}, "fixed-budget manifest scope")
    inputs = {}
    redacted = redacted_paths()
    for path in expected:
        info = inventory[path.as_posix()]
        actual = binding((root / path).read_bytes())
        audit.check(actual == {key: info[key] for key in ("bytes", "sha256")}, path, "bundle bytes and SHA-256")
        if path in redacted:
            audit.check(set(info) == {"bytes", "sha256", "original", "changed_fields"}
                        and info["changed_fields"] == redaction_fields(path) and valid_binding(info["original"])
                        and info["original"]["sha256"] != actual["sha256"], path, "declared public-copy transformation")
            inputs[path.as_posix()] = actual["sha256"]
        else:
            audit.check(set(info) == {"bytes", "sha256"}, path, "regular digest entry")
    audit.check(audit.sha(audit.canon(inputs)) == PUBLIC_INPUTS_SHA256, "reviewed public copy of frozen inputs")
    for path, expected_hash in PINS.items():
        audit.check(original_digest(inventory, path) == expected_hash, path, "historical audit digest")
    return inventory


def redaction_fields(path):
    if path in {FREEZE, RUN_MANIFEST}:
        return ["/hydra/url"]
    fields = [f"/{key}" for key in ("case_path", "corpus_path", "initial_records_path", "source_values_path",
                                    "initial_store_path")]
    fields.extend(f"/requests_by_arm/{arm}/{key}" for arm in sorted(ARMS)
                  for key in ("context_path", "prompt_path", "request_path"))
    return fields


def reachable(records, changed):
    children = defaultdict(list)
    for record in records:
        dependencies = [*record["inputs"], record["tool_version_id"]]
        for version in dict.fromkeys(dep for dep in dependencies if dep):
            children[version].append(record["id"])
    depths = dict.fromkeys(changed, 0)
    queue = deque(changed)
    selected = {}
    while queue:
        version = queue.popleft()
        for child in children[version]:
            depth = depths[version] + 1
            if child not in depths or depth < depths[child]:
                depths[child] = selected[child] = depth
                queue.append(child)
    return selected


def set_counts(expected, observed):
    predicted = set(observed)
    tp, fp, fn = len(expected & predicted), len(predicted - expected), len(expected - predicted)
    precision = tp / len(predicted) if predicted else float(not expected)
    recall = tp / len(expected) if expected else float(not predicted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1,
                exact_match=predicted == expected, missing_ids=sorted(expected - predicted),
                extra_ids=sorted(predicted - expected))


def verify_cases(root, frozen, count):
    fixture = audit.load(root / audit.FIXTURE / "fixture.json")
    base, raw_rows = audit.baseline_sources(root, fixture)
    output = {}
    for case_id in CASES:
        directory = root / audit.PREPARED / case_id
        metadata = audit.load(directory / "case.json")
        truth = audit.case_truth(directory, metadata, fixture, base, raw_rows)
        oracle = frozen["oracle"][case_id]
        anchor = truth["anchor"]
        dataset = (directory / "corpus.jsonl").read_text(encoding="utf-8").removesuffix("\n")
        records = named_index([json.loads(line, object_pairs_hook=audit.unique_dict)
                               for line in dataset.splitlines()], "id", case_id)
        canonical_lines = {alias: audit.canon(record) for alias, record in records.items()}
        audit.check(len(records) == 39 and dataset == "\n".join(canonical_lines.values()), case_id, "canonical frozen corpus")
        affected = {alias for alias in records
                    if anchor["records"][metadata["alias_to_raw"][alias]]["logical_id"].removeprefix("artifact:")
                    in truth["affected"]}
        unaffected = {name: anchor["artifact_heads"][f"artifact:{name}"]
                      for name in truth["reports"] - truth["affected"]}
        planned = dict(eligible_affected_reports=len(truth["eligible_affected"]),
                       eligible_reports=len(truth["reports"] - truth["unavailable"]), reports=len(truth["reports"]),
                       unaffected_reports=len(unaffected), unavailable_reports=len(truth["unavailable"]))
        audit.check(audit.sha(audit.canon(truth["values"])) == oracle["expected_values_sha256"]
                    and truth["affected"] == set(oracle["affected_names"]) and affected == set(oracle["affected_aliases"])
                    and truth["eligible_affected"] == set(oracle["eligible_affected_reports"])
                    and truth["unavailable"] == set(oracle["unavailable_reports"])
                    and truth["numeric_change"] == set(oracle["numerically_changed_reports"])
                    and unaffected == oracle["unaffected_report_heads"] and planned == oracle["counts"],
                    case_id, "frozen oracle matches independent source and Decimal arithmetic")
        changed = metadata["query"]["changed_ids"]
        query = metadata["query"]["text"]
        fact = audit.load(root / RUN / case_id / "case.json")
        setup = audit.load(root / RUN / case_id / "setup.json")
        entire = reachable(records.values(), changed)
        audit.check(set(entire) == affected == set(fact["native"]["native_membership_aliases"])
                    and set(entire) == set(metadata["native_graph_ids"])
                    and setup["status"] == "ready" and not fact["index_build_errors"]
                    and fact["changed_aliases"] == changed and fact["query"] == query
                    and fact["corpus_sha256"] == audit.sha(dataset) and fact["corpus_tokens"] == count(dataset)
                    and fact["query_tokens"] == count(query + "\nChanged version identifiers: " + " ".join(changed))
                    and fact["corpus_records"] == len(records), case_id, "reconstruction and recorded case setup")
        output[case_id] = dict(truth=truth, planned=planned, records=records, lines=canonical_lines, affected=affected,
                               changed=changed, ranking=sorted(entire, key=lambda alias: (entire[alias], alias)))
    return output, len(raw_rows)


def verify_context(root, cell, attempt, case, count):
    job = cell["cell_id"]
    plan = attempt["plan"]
    aliases = plan["retrieved_aliases"]
    lines = case["lines"]
    text = (root / RUN / job / "context.jsonl").read_bytes().decode("ascii")
    audit.check(len(aliases) == len(set(aliases)) and text == "\n".join(lines[alias] for alias in aliases)
                and audit.sha(text) == plan["context_sha256"], job, "exact canonical ordered context bytes")
    tokens = count(text)
    cap = cell["cap"]
    audit.check(tokens == plan["evidence_tokens"] and (cap is None or tokens <= cap), job, "independent cl100k receipt cap")
    if cap is None:
        audit.check(aliases == list(lines) and not plan["skipped_aliases"], job, "complete uncapped reference")
    elif cell["arm"] in {"graph", "exact_flat"}:
        packed, skipped = [], []
        for alias in case["ranking"]:
            if count("\n".join(lines[x] for x in [*packed, alias])) <= cap:
                packed.append(alias)
            else:
                skipped.append(alias)
        audit.check(aliases == packed and plan["skipped_aliases"] == skipped, job, "graph/flat whole-record packing")
    selected = reachable([case["records"][alias] for alias in aliases], case["changed"])
    observed = {
        "retrieved_affected": set_counts(case["affected"], aliases),
        "reader_affected": set_counts(case["affected"], selected),
        "tokens": tokens,
        "context_sha256": audit.sha(text),
    }
    audit.check(list(selected) == plan["selected_aliases"] and selected == plan["selected_depths"]
                and all(observed[key] == plan[key] for key in ("retrieved_affected", "reader_affected")),
                job, "context-only deterministic selection and coverage")
    return observed, list(selected)


def reconstruct_snapshot(witness, anchor):
    delta = witness["new_records"]
    audit.check(not (anchor["records"].keys() & delta.keys()), witness["cell_id"], "delta preserves every anchored record")
    return {"artifact_heads": witness["artifact_heads"], "records": {**anchor["records"], **delta},
            "source_heads": anchor["source_heads"], "tool_heads": anchor["tool_heads"]}


def scope_counts(verified, affected):
    group = set(verified)
    eligible = {name for name, row in verified.items() if row["oracle_available"]}
    fresh = {name for name, row in verified.items() if row["fresh_complete"]}
    preserved = {name for name, row in verified.items() if row["preserved_original_artifact"]}
    return dict(total=len(group), eligible=len(eligible), fresh=len(fresh),
                eligible_affected=len(eligible & affected), fresh_affected=len(fresh & affected),
                unavailable=len(group - eligible), correctly_blocked=sum(row["correctly_blocked"] for row in verified.values()),
                unaffected=len(group - affected), unaffected_artifacts_preserved=len(preserved - affected),
                incorrect_current=sum(row["incorrect_current"] for row in verified.values()))


def verify_endstate(cell, witness, recovered, truth, selected):
    job = cell["cell_id"]
    stored, audit_doc = witness["score"], witness["audit"]
    retained = recovered["score"]
    anchor = truth["anchor"]
    post = reconstruct_snapshot(witness, anchor)
    scope = set(truth["recipes"])
    affected, reports = truth["affected"], truth["reports"]
    audit.check(witness["score_redactions"] == list(KNOWN_SCORE_REDACTIONS)
                and not ({"post_snapshot_path", "independent_audit_path", "verified_report_counts",
                          "verified_artifact_counts"} & stored.keys()),
                job, "two withheld scorer paths and original wrapper field mismatch")
    raw = stored["raw_execution"]
    observed = named_index(raw["artifacts"], "name", job)
    saved = named_index(retained["verified_artifacts"], "name", job)
    audit.check(raw["selected_aliases"] == selected and set(observed) == set(saved) == scope
                and stored["expected_affected_names"] == sorted(affected)
                and set(audit_doc["artifacts"]) == scope, job, "execution used fixed reader selection and full scope")
    eligible = {name for name, value in truth["values"].items() if value is not None}
    matches = {}
    for name in scope:
        actual = post["records"][post["artifact_heads"][f"artifact:{name}"]]["value"]
        matches[name] = name in eligible and audit.canon(actual) == audit.canon(truth["values"][name])
        audit.check(matches[name] == saved[name]["numeric_match"], job, name, "independent Decimal output mismatch")
    stale = audit.independent_provenance(post, truth, job)

    hashes = witness["original"]
    audit.check(set(hashes) == {"post_snapshot", "scoring_result", "independent_audit"}
                and all(valid_binding(value) for value in hashes.values())
                and hashes["post_snapshot"] == binding(json_bytes(post))
                and hashes["independent_audit"] == binding(json_bytes(audit_doc))
                and hashes["post_snapshot"]["sha256"] == stored["post_snapshot_sha256"]
                and hashes["independent_audit"]["sha256"] == stored["independent_audit_sha256"],
                job, "reconstructed poststate and unchanged audit digest")
    audit.check(audit_doc["head_validation_pass"] is True and audit_doc["immutable_anchor_pass"] is True
                and audit_doc["immutable_anchor_provided"] is True and not audit_doc["head_errors"]
                and not audit_doc["immutable_anchor_errors"] and audit_doc["immutable_anchor_records"] == len(anchor["records"])
                and audit_doc["immutable_anchor_sha256"] == audit.sha(audit.canon(anchor["records"])),
                job, "recorded full immutable-anchor integrity")
    audit.check(witness["public_score"] == binding(json_bytes(stored)), job, "published scorer copy fingerprint")
    unavailable_sources = {name for name, value in truth["sources"].items() if value is None}
    missing = {f"source_unavailable:{name}" for name in unavailable_sources}
    independently_verified = {}
    for name in sorted(scope):
        logical = f"artifact:{name}"
        head_id = post["artifact_heads"][logical]
        original_id = anchor["artifact_heads"][logical]
        head = post["records"][head_id]
        runtime = observed[name]
        witness_audit = audit_doc["artifacts"][name]
        state = runtime["state"]
        numeric = matches[name]
        reasons = stale[name]
        current = not reasons
        available = name in eligible
        fresh = available and numeric and state == "current" and current
        blocked = not available and state in {"stale", "unknown"} and bool(reasons & missing) and all(
            reason in missing or reason.startswith(("source_version_stale:", "tool_version_stale:")) for reason in reasons
        )
        audit.check(state in {"current", "stale", "unknown"} and "inspection_error" not in runtime
                    and runtime["head_id"] == witness_audit["head_id"] == head_id
                    and runtime["head_content_hash"] == head["content_hash"]
                    and runtime["actual_stored_value"] == head["value"] and runtime["expected_value"] == truth["values"][name]
                    and witness_audit["provenance_current"] == current and set(witness_audit["reasons"]) == reasons,
                    job, name, "saved observation matches reconstructed values and independent receipt lineage")
        independently_verified[name] = {
            "name": name, "is_report": name in reports, "expected_revalidation": name in affected,
            "oracle_available": available, "head_id": head_id, "original_id": original_id, "runtime_state": state,
            "numeric_match": numeric, "provenance_current": current, "provenance_reasons": witness_audit["reasons"],
            "inspection_matches_snapshot": True, "fresh_complete": fresh, "correctly_blocked": blocked,
            "preserved_original_artifact": head_id == original_id, "incorrect_current": state == "current" and not fresh,
        }
    verified_rows = list(independently_verified.values())
    report_counts = scope_counts({name: independently_verified[name] for name in reports}, affected)
    artifact_counts = scope_counts(independently_verified, affected)
    error = raw["refresh_error"]
    expected_refusal = bool(error and error["type"] == "MissingEvidenceError"
                            and error["message"] in {f"Source no longer available: {name}" for name in unavailable_sources}
                            and eligible != scope)
    unexpected = bool(error and not expected_refusal)
    audit.check(raw["expected_source_unavailable_refusal"] == expected_refusal and raw["unexpected_refresh_error"] == unexpected,
                job, "saved refresh refusal classification")
    errors = ["Refresh or runtime inspection has an unexpected error"] if unexpected or raw["inspection_errors"] else []
    absolute = (artifact_counts["fresh"] == artifact_counts["eligible"]
                and artifact_counts["correctly_blocked"] == artifact_counts["unavailable"]
                and artifact_counts["unaffected_artifacts_preserved"] == artifact_counts["unaffected"]
                and artifact_counts["incorrect_current"] == 0 and not errors)
    audit.check(verified_rows == stored["verified_artifacts"]
                and stored["verified_reports_counts"] == report_counts and stored["verified_artifacts_counts"] == artifact_counts
                and stored["absolute_correct"] == stored["semantic_endstate_correct"] == absolute
                and stored["independent_global_validation"] is True and stored["scoring_errors"] == errors,
                job, "retained scorer matches independently aggregated endstate")
    score = {
        "whole_case_correct": absolute and (cell["case_id"] != "M08" or not selected),
        "verified_report_counts": report_counts, "verified_artifact_counts": artifact_counts,
        "verified_artifacts": verified_rows, "independent_global_validation": True, "scoring_errors": errors,
        "refresh_error": error, "inspection_errors": raw["inspection_errors"], "refresh_tool_calls": raw["tool_calls"],
        "refresh_graph_queries": raw["refresh_graph_queries"], "expected_missing_source_refusal": expected_refusal,
        "safe_empty_missing_selection": cell["case_id"] == "M07" and not selected and absolute,
        "retained_scoring_result_sha256": hashes["scoring_result"]["sha256"],
        "post_snapshot_sha256": hashes["post_snapshot"]["sha256"], "independent_audit_sha256": hashes["independent_audit"]["sha256"],
    }
    audit.check(score == retained, job, "independent endstate counts match published recovery")
    return score


def summarize(verified):
    groups = []
    for arm, cap in [*product(ARMS[:-1], BUDGETS), ("full_context", None)]:
        group = [item for item in verified if (item["arm"], item["cap"]) == (arm, cap)]
        whole = sum(item["whole_case_correct"] for item in group)
        obligations = {field: sum(item["counts"][field] for item in group)
                       for field in ("eligible_affected", "unavailable", "unaffected")}
        obligations["affected_artifacts"] = sum(item["affected_artifacts"] for item in group)
        observed = {label: sum(item["counts"][key] for item in group) for label, key in SAFETY_KEYS.items()}
        matches = {key: {metric: sum(item[key][metric] for item in group) for metric in ("tp", "fp", "fn")}
                   for key in ("retrieved_affected", "reader_affected")}
        audit.check(len(group) == 8 and obligations == {"eligible_affected": 32, "unavailable": 4,
                                                       "unaffected": 52, "affected_artifacts": 89},
                    cap, arm, "report obligations came from all eight case inputs")
        absolute = (whole == 8 and observed == {"fresh_affected": obligations["eligible_affected"],
                    "unavailable_blocked": obligations["unavailable"], "unaffected_preserved": obligations["unaffected"],
                    "incorrect_current": 0})
        groups.append({
            "arm": arm, "cap": cap, "condition": group[0]["condition"], "planned_cells": len(group),
            "status_counts": {"recovered_observation": len(group)}, "scored_cells": len(group),
            "planned_denominators": obligations, "reports_observed": observed, "whole_cases_correct": whole,
            "expected_missing_source_refusals": sum(item["expected_missing_source_refusal"] for item in group),
            "safe_empty_missing_selections": sum(item["safe_empty_missing_selection"] for item in group),
            "evidence_tokens_observed": sum(item["tokens"] for item in group), "planned_contexts_observed": len(group),
            **matches, "absolute_report_conditions_met_in_retained_scores": absolute,
        })
    return groups


def verify_original(inventory, original_inventory, schedule, run, original, recovered):
    expected = {path.relative_to(RUN).as_posix(): original_digest(inventory, path) for path in original_paths()}
    audit.check(original_inventory == expected, "exact preserved original attempt and context bindings")
    audit.check(run["finished"] is True and run["generative_provider_invocations"] == 0
                and run["approved_frozen_revision"] == REVISION and run["freeze_sha256"] == FREEZE_SHA256
                and all(doc["source_integrity_verified"] and doc["resource_integrity_verified"] and doc["stop_error"] is None
                        for doc in (run, original))
                and original["freeze_integrity_verified"] and original["complete"] is False
                and original["status_counts"] == {"execution_failed": len(schedule)} and original["planned_cells"] == len(schedule),
                "frozen run identity and original incomplete wrapper outcome")
    for cell, planned in zip(schedule, run["planned_cells"], strict=True):
        audit.check(all(planned[key] == value for key, value in cell.items()) and planned["status"] == "unattempted",
                    cell["cell_id"], "original planned cell")
    audit.check(recovered["all_retained_scores_verified"] is True and recovered["freeze_integrity_verified"] is True
                and recovered["approved_frozen_revision"] == REVISION and recovered["frozen_manifest_sha256"] == FREEZE_SHA256
                and recovered["original_run_manifest_sha256"] == PINS[RUN_MANIFEST]
                and recovered["original_run_summary_sha256"] == PINS[SUMMARY] and recovered["original_frozen_run_complete"] is False
                and recovered["original_status_counts"] == original["status_counts"] and recovered["original_wrapper_error"] == WRAPPER_ERROR
                and recovered["status_counts"] == {"recovered_observation": len(schedule)},
                "subsequent recovery remains separate from original failed publication")


def verify(root):
    inventory = verify_inventory(root)
    schedule = list(cells())
    frozen = audit.load(root / FREEZE)
    run = audit.load(root / RUN_MANIFEST)
    summary = audit.load(root / SUMMARY)
    recovered = audit.load(root / RECOVERED_SUMMARY)
    verify_original(inventory, audit.load(root / ORIGINAL_INVENTORY), schedule, run, summary, recovered)
    audit.check(frozen["planned_cells"] == schedule and frozen["budgets"] == list(BUDGETS)
                and frozen["tokenizer"] == {"encoding": "cl100k_base", "vocabulary_sha256": VOCABULARY_SHA256},
                "frozen schedule, caps and tokenizer")
    frozen_inputs = frozen["historical_input_sha256"]
    for path in march_paths():
        audit.check(original_digest(inventory, path) == frozen_inputs[path.as_posix()], path, "historical March input digest")
    audit.require_hash(root / PROTOCOL, frozen["code_sha256"][PROTOCOL.as_posix()])
    count = token_counter(root / VOCABULARY)
    cases, source_rows = verify_cases(root, frozen, count)
    verified, plan_ends, execution_starts = [], [], []
    for cell, row, witness, original_plan in zip(schedule, read_jsonl(root / RECOVERED), read_jsonl(root / EVIDENCE),
                                                  run["planned_cells"], strict=True):
        job = cell["cell_id"]
        attempt_path = RUN / job / "attempt.json"
        attempt = audit.load(root / attempt_path)
        case = cases[cell["case_id"]]
        expected = {**attempt, "status": "recovered_observation", "frozen_wrapper_status": "execution_failed",
                    "original_attempt_sha256": original_digest(inventory, attempt_path)}
        audit.check({key: value for key, value in row.items() if key != "score"} == expected
                    and all(attempt[key] == value for key, value in cell.items()) and witness["cell_id"] == job
                    and attempt["status"] == "execution_failed" and attempt["execution_error"] == WRAPPER_ERROR
                    and attempt["planned_report_counts"] == case["planned"] == original_plan["planned_report_counts"],
                    job, "original attempt, wrapper failure and recovered row identity")
        times = [datetime.fromisoformat(attempt[key]) for key in ("planning_started_at", "planning_finished_at",
                                                                 "execution_started_at", "execution_finished_at")]
        audit.check(times == sorted(times), job, "saved planning precedes execution")
        plan_ends.append(times[1])
        execution_starts.append(times[2])
        context, selected = verify_context(root, cell, attempt, case, count)
        score = verify_endstate(cell, witness, row, case["truth"], selected)
        verified.append({**cell, **context, "counts": score["verified_report_counts"],
                         "affected_artifacts": len(case["truth"]["affected"]),
                         **{key: score[key] for key in ("whole_case_correct", "expected_missing_source_refusal",
                                                         "safe_empty_missing_selection")}})
    audit.check(max(plan_ends) <= min(execution_starts), "all 88 contexts fixed before the first refresh")
    audit.require_hash(root / RECOVERED, RECOVERED_CELLS_SHA256)
    audit.require_hash(root / EVIDENCE, WITNESS_SHA256)

    contexts = {(row["case_id"], row["arm"], row["cap"]): row["context_sha256"] for row in verified}
    parity = {str(cap): {"planned": len(CASES), "observed": len(CASES), "matching_contexts": sum(
        contexts[case, "graph", cap] == contexts[case, "exact_flat", cap] for case in CASES
    )} for cap in BUDGETS}
    audit.check(parity == summary["graph_exact_flat_context_parity"] == recovered["graph_exact_flat_context_parity"]
                and all(item["matching_contexts"] == 8 for item in parity.values()), "graph/exact-flat identical contexts")
    groups = summarize(verified)
    keys = lambda row: (row["condition"], row["arm"])
    audit.check(sorted(groups, key=keys) == sorted(recovered["groups"], key=keys), "recomputed group outcomes and safety counts")
    audit.check(len(verified) == recovered["planned_cells"] == 88, "88 independently verified endstates")
    return {
        "bundle_files_verified": len(inventory), "frozen_study_revision": REVISION, "verified_cells": len(verified),
        "reconstructed_source_rows": source_rows, "original_completed": False,
        "original_wrapper_execution_errors": len(verified), "graph_exact_flat_context_parity": parity,
        "groups": groups,
        "cells": [{"id": row["cell_id"], "receipt_tokens": row["tokens"], **row["counts"],
                   "whole_case_correct": row["whole_case_correct"]} for row in verified],
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    try:
        result = verify(parser.parse_args().bundle.resolve())
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration, ArithmeticError) as error:
        parser.exit(1, f"Fixed-budget evidence verification failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
