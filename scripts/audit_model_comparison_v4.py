#!/usr/bin/env python3
"""Verify saved v4 model-study evidence using only the Python standard library.

Run from a checkout containing the published artifacts:
    python3 scripts/audit_model_comparison_v4.py .

This audit independently implements staged arithmetic and receipt tracing. It
does not run the benchmark, replay refresh, contact the provider, or inspect raw
provider stdout, SQLite stores or the original workbook. It checks consistency
of exported evidence from the published snapshot boundary.
"""
from argparse import ArgumentParser
from collections import Counter
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path
import csv
import json

REVISION = "3fa9f850bbecdccf068bbda7e90cd0497e79b460"
PREPARED_SHA256 = "7f5af0c2214e5d758787ae1bda216bf91c778e2daadc8901c72fe668da3f86c0"
RUN = Path("results/model-v4-test-run-1")
PREPARED = Path("results/model-v4-test-prepared")
FIXTURE = Path("fixtures/model_comparison_v4/test")
ARMS = ("graph", "exact_flat", "bm25", "dense", "iterative_hybrid", "full_context")
CASES = tuple(f"M{i+1:02}" for i in range(8))
MODEL = "claude-fable-5-2"
TOKENS = dict(input_tokens="inputTokens", cache_creation_input_tokens="cacheCreationInputTokens",
              cache_read_input_tokens="cacheReadInputTokens", output_tokens="outputTokens")


class AuditError(ValueError):
    pass


def check(ok, *context):
    if not ok:
        raise AuditError(" / ".join(map(str, context)))


def unique_dict(pairs):
    output = dict(pairs)
    check(len(output) == len(pairs), "duplicate JSON key")
    return output

def reject_constant(token):
    raise ValueError(token)

def load(path, exact=False):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_dict, parse_constant=reject_constant,
                      parse_float=Decimal if exact else float)

def canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def sha(value):
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()

def file_sha(path):
    return sha(Path(path).read_bytes())

def verify_identity(record, identity):
    kind, record_id = record["kind"], record["id"]
    workspace, sep, suffix = record_id.partition(f":{kind}:")
    return workspace and sep and suffix == sha(canon(dict(logical_id=record["logical_id"],
                                                            content_hash=record["content_hash"], identity=identity)))

def fiscal_values(recipes, sources):
    def aggregate(rows):
        cents = Counter()
        for country, amount in rows:
            cents[country] += amount
        return {"regions": {country: {"currency": "GBP", "amount_cents": value} for country, value in cents.items()}}

    values = {f"source:{name}": value for name, value in sources.items()}
    for recipe in recipes:
        name, tool = recipe["name"], recipe["tool"]
        inp = {port: values[ref] for port, ref in recipe["inputs"].items()}
        if any(value is None for value in inp.values()):
            values[name] = None
        elif tool == "gross_by_region":
            values[name] = aggregate((row["region"], row["gross_cents"]) for row in inp["orders"])
        elif tool == "refunds_by_region":
            regions = {item["order_id"]: item["region"] for item in inp["orders"]}
            values[name] = aggregate((regions[row["order_id"]], row["refund_cents"]) for row in inp["refunds"])
        elif tool == "net_by_region":
            refund_map = inp["refunds"]["regions"]
            values[name] = aggregate((country, item["amount_cents"] - refund_map.get(country, {}).get("amount_cents", 0))
                                     for country, item in inp["gross"]["regions"].items())
        elif tool == "convert_to_usd":
            values[name] = {"regions": {country: {"usd_cents": int((Decimal(item["amount_cents"]) *
                Decimal(inp["fx"][item["currency"]])).to_integral_value(rounding=ROUND_HALF_EVEN))}
                for country, item in inp["net"]["regions"].items()}}
        elif tool == "company_total":
            values[name] = {"usd_cents": sum(item["usd_cents"] for item in inp["regional"]["regions"].values())}
        elif tool == "compose_report":
            params = recipe["params"]
            claims = []
            for section in params["sections"]:
                value = inp[section["input"]]
                for component in section["path"]:
                    value = value[component]
                assert type(value) is int and section["unit"] == "USD cents"
                claims.append(dict(key=section["key"], label=section["label"], unit=section["unit"], value=value))
            values[name] = dict(title=params["title"], sections=claims)
        else:
            raise ValueError(tool)
    return {recipe["name"]: values[recipe["name"]] for recipe in recipes}

def independent_provenance(post, t, job):
    records = post["records"]
    anchor = t["anchor"]
    check(all(k in records and canon(records[k]) == canon(v) for k,v in anchor["records"].items()),
          job, "all prior immutable records preserved")
    check(post["source_heads"].keys() == t["sources"].keys()
          and post["tool_heads"].keys() == t["tools"].keys(), job, "head scope")
    artifact_heads = post["artifact_heads"]
    check(set(artifact_heads) == {f"artifact:{n}" for n in t["recipes"]}, job, "artifact scope")
    for kind, entities in (("source", t["sources"]), ("tool", t["tools"])):
        for logical, value in entities.items():
            record_id = post[f"{kind}_heads"][logical]
            record = records[record_id]
            deleted = kind == "source" and value is None
            check(record["id"] == record_id and record["kind"] == kind and record["logical_id"] == logical
                  and record["value"] == value and record["content_hash"] == sha(canon(value))
                  and verify_identity(record, {"deleted": True} if deleted else None)
                  and (kind != "source" or bool(record["metadata"].get("deleted")) == deleted),
                  job, logical, "current version identity/hash")
    memo = {}
    def roots(record_id, name, pending):
        check(record_id not in pending, job, name, "receipt cycle")
        if record_id in pending:
            return {"cycle"}
        if (record_id, name) in memo:
            return memo[record_id, name]
        actual = records[record_id]
        source = name.startswith("source:")
        expected_logical = name if source else f"artifact:{name}"
        stale = set()
        check(actual["id"] == record_id and actual["kind"] == ("source" if source else "artifact")
              and actual["logical_id"] == expected_logical and actual["content_hash"] == sha(canon(actual["value"])),
              job, name, "record identity/content hash")
        if source:
            check(verify_identity(actual, {"deleted":True} if actual["metadata"].get("deleted") else None),
                  job, name, "dependency source content-addressed identity")
            if t["sources"][name] is None:
                stale.add(f"source_unavailable:{name}")
            elif post["source_heads"][name] != record_id:
                stale.add(f"source_version_stale:{name}")
        else:
            r = t["recipes"][name]
            meta = actual["metadata"]
            check(meta["tool"] == r["tool"] and meta["params"] == r["params"]
                  and meta["inputs"].keys() == r["inputs"].keys(), job, name, "artifact contract")
            tool_name = f"tool:{r['tool']}"
            tool_record = records[meta["tool_version_id"]]
            check(tool_record["id"] == meta["tool_version_id"] and tool_record["logical_id"] == tool_name
                  and tool_record["kind"] == "tool" and verify_identity(tool_record, None)
                  and tool_record["content_hash"] == sha(canon(tool_record["value"])), job, name, "tool identity")
            if post["tool_heads"][tool_name] != meta["tool_version_id"]:
                stale.add(f"tool_version_stale:{tool_name}")
            receipt = records[meta["receipt_id"]]
            witness = {key: meta[key] for key in ("tool", "tool_version_id", "params", "inputs", "run_id")}
            witness.update(output_id=record_id, output_hash=actual["content_hash"], status="success")
            logical = receipt["logical_id"]
            check(receipt["id"] == meta["receipt_id"] and receipt["kind"] == "execution"
                  and logical.startswith("execution:") and verify_identity(receipt, None)
                  and verify_identity(actual, logical.removeprefix("execution:"))
                  and receipt["content_hash"] == sha(canon(receipt["value"]))
                  and all(receipt["value"][k] == v for k,v in witness.items()), job, name, "receipt chain witness")
            for port, child in r["inputs"].items():
                stale |= roots(meta["inputs"][port], child, pending | {record_id})
        memo[record_id, name] = stale
        return stale
    return {name: roots(artifact_heads[f"artifact:{name}"], name, set()) for name in t["recipes"]}


def baseline_sources(repo, fixture):
    fixture_path = repo / FIXTURE
    base_sources, raw_rows = {}, {}
    for day in fixture["dates"]:
        published = load(fixture_path / f"{day}.provenance.json")
        with (fixture_path / f"{day}.csv").open(newline="") as stream:
            csv_rows = {r["order_id"]: {**r, "gross_cents": int(r["gross_cents"])} for r in csv.DictReader(stream)}
        raw = {}
        for row in published:
            identifier = f"uci:{row['invoice_no']}:row:{row['source_row']}"
            price = Decimal(str(float(row["unit_price_raw_xml"])))
            count = Decimal(str(float(row["quantity_raw_xml"])))
            total = price * count * 100
            check(row["order_id"] == identifier and identifier not in raw_rows and count.is_finite()
                  and count == count.to_integral_value() and int(count) == row["quantity"]
                  and price == Decimal(row["unit_price_gbp"]) and total == total.to_integral_value()
                  and int(total) == row["gross_cents"] and 0 < total <= 10**12,
                  day, identifier, "raw provenance")
            raw[identifier] = dict(order_id=identifier, region=row["region"], currency="GBP", gross_cents=int(total))
            raw_rows[identifier] = row
        data = [raw[key] for key in sorted(raw)]
        check(raw == csv_rows and data == sorted(fixture["sources"][f"{day}:orders"], key=lambda r:r["order_id"]),
              day, "provenance, CSV and fixture agree")
        base_sources.update({f"{day}:orders": data, f"{day}:refunds": [], f"{day}:fx": {"GBP": "1.25", "USD": "1"}})
    check(len(raw_rows) == fixture["profile"]["selected_rows"] == 4681, "test row count")
    check(len({r["invoice_no"] for r in raw_rows.values()}) == 203, "test invoice count")
    return base_sources, raw_rows


def case_truth(root, case, fixture, base_sources, raw_rows):
    case_id = case["case_id"]
    anchor = load(root / "initial_records.json")
    recipes = {r["name"]: r for r in case["recipes"]}
    check(case["recipes"] == fixture["recipes"] and set(case["candidate_names"]) == recipes.keys()
          and len(recipes) == 39, case_id, "all recipes")
    scenario = next(v for v in fixture["cases"] if v["id"] == case_id)
    check(scenario == case["scenario"], case_id, "frozen fixture scenario")
    report_names = {n for n,r in recipes.items() if r["tool"] == "compose_report"}
    check(len(report_names) == 11, case_id, "all reports")
    baseline = fiscal_values(case["recipes"], base_sources)
    staged = deepcopy(base_sources)
    tools = {f"tool:{r['tool']}": {"name":r["tool"], "version":"1",
             "implementation_hash":case["analytics_sha256"]} for r in case["recipes"]}
    expected_roots = []
    dirt = set()
    for patch, observed in zip(scenario["mutations"], case["mutation_audit"], strict=True):
        op, param = patch["operation"], patch["parameters"]
        if op == "tool_version":
            logical = f"tool:{patch['tool']}"
            before = deepcopy(tools[logical])
            tools[logical]["version"] = param["version"]
            after = tools[logical]
        else:
            name = patch["source"]
            logical = f"source:{name}"
            before = deepcopy(staged[name])
            rows = staged[name]
            if op == "refund_add":
                order = next(row for row in staged[name.removesuffix(":refunds")+":orders"]
                             if row["order_id"] == param["order_id"])
                check(0 < param["refund_cents"] <= order["gross_cents"], case_id, logical, "declared patch")
                rows.append(dict(order_id=param["order_id"], refund_cents=param["refund_cents"]))
            elif op == "fx_set":
                rows.update(param)
            elif op == "quantity_delta":
                row = next(r for r in rows if r["order_id"] == param["order_id"])
                raw = raw_rows[row["order_id"]]
                unit = Decimal(raw["unit_price_gbp"])
                check(raw["quantity"] == param["raw_quantity"] and unit == Decimal(param["unit_price_gbp"]),
                      case_id, logical, "frozen original quantity and price")
                check(int(unit * raw["quantity"] * 100) == row["gross_cents"] == param["old_gross_cents"], case_id, logical, "declared patch")
                new = raw["quantity"] + param["delta_quantity"]
                exact_line = unit * new * 100
                check(new == param["new_quantity"] and exact_line == exact_line.to_integral_value(),
                      case_id, logical, "exact amended quantity and price")
                check(int(exact_line) == param["new_gross_cents"], case_id, logical, "declared patch")
                row["gross_cents"] = int(exact_line)
            elif op == "offset_gross":
                first, second = [next(r for r in rows if r["order_id"] == param[k]) for k in ("first","second")]
                check(first["region"] == second["region"] and first["gross_cents"] == param["first_old_gross_cents"], case_id, logical, "declared patch")
                check(second["gross_cents"] == param["second_old_gross_cents"], case_id, logical, "declared patch")
                first["gross_cents"] += param["delta_cents"]
                second["gross_cents"] -= param["delta_cents"]
                check(first["gross_cents"] > 0 and second["gross_cents"] > 0, case_id, logical, "declared patch")
            elif op == "remove":
                staged[name] = None
            elif op == "reorder":
                rows.reverse()
            else:
                raise ValueError(op)
            if isinstance(staged[name], list):
                staged[name].sort(key=lambda r:r["order_id"])
            after = staged[name]
        changed = canon(before) != canon(after)
        old_id, new_id = observed["original_id"], observed["current_id"]
        check(observed["logical_id"] == logical and observed["expected_changed"] == observed["observed_changed"] == changed
              and (old_id != new_id) == changed and anchor["records"][old_id]["value"] == before
              and anchor["records"][new_id]["value"] == after and observed["deleted"] == (op == "remove")
              and observed["before_sha256"] == sha(canon(before)) and observed["after_sha256"] == sha(canon(after)),
              case_id, logical, "independent mutation roots")
        if changed:
            dirt.add(logical)
            expected_roots.append(old_id)
    check(load(root/"current_sources.json") == staged, case_id, "independently staged inputs")
    check(case["changed_raw_ids"] == expected_roots == [case["alias_to_raw"][alias] for alias in case["query"]["changed_ids"]],
          case_id, "prompt notifications agree with staging")
    affected = set()
    for name, recipe in recipes.items():
        if f"tool:{recipe['tool']}" in dirt or any(ref in dirt or ref in affected for ref in recipe["inputs"].values()):
            affected.add(name)
    values = fiscal_values(case["recipes"], staged)
    native = {anchor["records"][case["alias_to_raw"][i]]["logical_id"].removeprefix("artifact:")
              for i in case["requests_by_arm"]["graph"]["retrieved_ids"]}
    check(native == affected, case_id, "native context covers independent affected closure")
    check(set(case["native_graph_ids"]) == set(case["exact_flat_ids"]), case_id, "native versus exact-flat closure membership")
    expected_affected = {n for n in report_names & affected if values[n] is not None}
    unavailable_reports = {n for n in report_names if values[n] is None}
    return dict(case=case, anchor=anchor, sources={f"source:{k}":v for k,v in staged.items()},
                         tools=tools, recipes=recipes, values=values, affected=affected, reports=report_names,
                         eligible_affected=expected_affected, unavailable=unavailable_reports,
                         numeric_change={n for n in expected_affected if values[n] != baseline[n]})

def require_hash(path, expected):
    check(file_sha(path) == expected, path, "SHA-256 mismatch")


def normalized_usage(provider, result, job_id):
    entries = provider["modelUsage"]
    check(bool(entries) and not provider["is_error"], job_id, "successful accounting")
    counts = Counter()
    model_cost = Decimal(0)
    for key, entry in entries.items():
        check(entry.get("canonicalModel", key) == MODEL and entry["costBasis"] == "list", job_id, "canonical model identity and cost basis")
        for name, field in TOKENS.items():
            value = entry[field]
            check(type(value) is int and value >= 0, job_id, field, "explicit nonnegative integer")
            counts[name] += value
        check(type(entry["costUSD"]) is str, job_id, "explicit model cost text")
        charge = Decimal(entry["costUSD"])
        check(charge.is_finite() and charge >= 0, job_id, "known model cost")
        model_cost += charge
    check(type(provider["total_cost_usd"]) is str, job_id, "explicit envelope cost text")
    charge = Decimal(provider["total_cost_usd"])
    check(charge.is_finite() and charge >= 0
          and abs(charge-model_cost) <= Decimal("0.000001")+Decimal("1e-9")*max(charge,model_cost),
          job_id, "envelope/model usage cost reconciliation")
    counts["provider_input_exposure"] = sum(counts[name] for name in TOKENS if name != "output_tokens")
    turns = provider["num_turns"]
    check(type(turns) is int and turns >= 0, job_id, "explicit CLI turns")
    counts["num_turns"] = turns
    check(all(result["usage"][key] == count for key,count in counts.items())
          and float(charge) == result["usage"]["cost_usd"] == result["known_cost_usd"],
          job_id, "recomputed accounting differs from result")
    return counts, charge


def verify_request(root, prepared, case, job):
    job_id, case_id, arm = job["job_id"], job["case_id"], job["arm"]
    prefix = f"{case_id}/requests/{arm}"
    for name in ("request.json", "context.jsonl", "prompt.txt"):
        relative = f"{prefix}/{name}"
        require_hash(root / relative, prepared["artifact_sha256"][relative])
    request = load(root / prefix / "request.json")
    text = request["context_text"]
    lines = [json.loads(line) for line in text.splitlines()]
    ids = [row["id"] for row in lines]
    corpus = [json.loads(line) for line in (root / case_id / "corpus.jsonl").read_text().splitlines()]
    corpus_by_id = {row["id"]:row for row in corpus}
    arm_request = case["requests_by_arm"][arm]
    check(set(request) == {"task", "changed_ids", "allowed_artifact_ids", "context_text"}
          and request["task"] == case["query"]["text"] and request["changed_ids"] == case["query"]["changed_ids"]
          and len(ids) == len(set(ids)) and set(ids) == set(request["allowed_artifact_ids"])
          and ids == arm_request["retrieved_ids"] and all(row == corpus_by_id[row["id"]] for row in lines),
          job_id, "frozen model context")
    prompt = canon(dict(task=request["task"], changed_ids=request["changed_ids"], evidence_jsonl=text))
    check(sha(prompt) == job["request_sha256"] == file_sha(root / prefix / "prompt.txt")
          and sha(text) == job["context_sha256"]
          and file_sha(root / prefix / "request.json") == job["request_file_sha256"],
          job_id, "bound prompt and request bytes")
    if arm == "full_context":
        check(set(ids) == set(corpus_by_id) and len(ids) == 39 and job["evidence_budget"] is None,
              job_id, "uncapped full corpus")
    else:
        check(job["evidence_tokens"] <= job["evidence_budget"] == case["evidence_allowance"],
              job_id, "capped whole-record allowance")
    if arm == "graph":
        flat = case["requests_by_arm"]["exact_flat"]
        check(job["request_sha256"] == flat["request_sha256"] and job["context_sha256"] == flat["context_sha256"],
              job_id, "native/exact-flat prompt identity")
    return set(ids)


def verify_plan(provider, result, request_ids, truth, job):
    job_id = job["job_id"]
    process, plan = result["process"], result["plan"]
    check(result["status"] in ("planned", "abstained") and process["process_started"] is True
          and process["returncode"] == 0 and not process["timed_out"] and process["error"] is None
          and process["harness_attempts"] == 1 and process["harness_retries"] == 0 and not process["fallback"]
          and process["model"] == MODEL and process["effort"] == "high" and process["configured_timeout_seconds"] == 90,
          job_id, "one settled frozen CLI invocation")
    for key in ("request_sha256","context_sha256"):
        check(job[key] == provider[key] == result[key] == plan[key] == process[key], job_id, key, "request binding")
    payload = plan["provider_result"]["payload"]
    selected, abstain = provider["selected_ids"], provider["abstain"]
    check(set(payload) == {"selected_ids", "rationale", "abstain"} and payload["selected_ids"] == plan["selected_ids"] == selected
          and payload["abstain"] == plan["abstain"] == abstain and type(abstain) is bool
          and isinstance(payload["rationale"], str) and payload["rationale"] == plan["rationale"] and len(plan["rationale"]) <= 12000
          and type(selected) is list and all(isinstance(x, str) for x in selected) and len(selected) == len(set(selected))
          and set(selected) <= request_ids and not (abstain and selected),
          job_id, "bounded schema-valid plan")
    aliases = truth["case"]["alias_to_raw"]
    check(all(aliases[alias] in truth["anchor"]["artifact_heads"].values() for alias in selected),
          job_id, "execution only accepts shown artifact aliases")
    return selected, abstain


def verify_endstate(directory, result, truth, selected, abstain, job_id):
    score = result["score"]
    post_path = directory / "execution/post_snapshot.json"
    audit_path = directory / "execution/independent_audit.json"
    post, audit = load(post_path), load(audit_path)
    prior = truth["anchor"]["records"]
    check(audit["head_validation_pass"] is True and audit["immutable_anchor_pass"] is True
          and audit["immutable_anchor_provided"] is True and not audit["immutable_anchor_errors"]
          and audit["immutable_anchor_records"] == len(prior) and audit["immutable_anchor_sha256"] == sha(canon(prior)),
          job_id, "complete recorded immutable anchor")
    runtime = score["raw_execution"]
    reported = {r["name"]:r for r in runtime["artifacts"]}
    verified = {r["name"]:r for r in score["verified_artifacts"]}
    scope = set(truth["recipes"])
    check(len(runtime["artifacts"]) == len(score["verified_artifacts"]) == len(scope)
          and scope == set(reported) == set(verified) == set(audit["artifacts"])
          and set(score["expected_affected_names"]) == truth["affected"]
          and runtime["selected_aliases"] == selected, job_id, "complete execution scope")
    eligible = {n for n,v in truth["values"].items() if v is not None}
    numeric_match = {}
    for name in scope:
        head = post["artifact_heads"][f"artifact:{name}"]
        numeric_match[name] = (name in eligible
                               and canon(post["records"][head]["value"]) == canon(truth["values"][name]))
        check(numeric_match[name] == verified[name]["numeric_match"], job_id, name, "independent Decimal output mismatch")
    provenance = independent_provenance(post, truth, job_id)
    require_hash(post_path, score["post_snapshot_sha256"])
    require_hash(audit_path, score["independent_audit_sha256"])
    unaffected, fresh, blocked, incorrect, preserved = scope-truth["affected"], set(), set(), set(), set()
    for name in scope:
        logical = f"artifact:{name}"
        identifier = post["artifact_heads"][logical]
        record = post["records"][identifier]
        observed = reported[name]
        currentness = observed["state"]
        reasons = provenance[name]
        numeric = numeric_match[name]
        is_fresh = numeric and not reasons and currentness == "current"
        is_blocked = name not in eligible and currentness in {"stale","unknown"} and any(
            reason.startswith("source_unavailable:") for reason in reasons)
        preserved_id = identifier == truth["anchor"]["artifact_heads"][logical]
        is_incorrect = currentness == "current" and not is_fresh
        check(identifier == observed["head_id"] == verified[name]["head_id"] == audit["artifacts"][name]["head_id"]
              and observed["actual_stored_value"] == record["value"] and observed["head_content_hash"] == record["content_hash"]
              and observed["expected_value"] == truth["values"][name]
              and verified[name]["numeric_match"] == numeric and verified[name]["fresh_complete"] == is_fresh
              and verified[name]["preserved_original_artifact"] == preserved_id
              and verified[name]["correctly_blocked"] == is_blocked and verified[name]["incorrect_current"] == is_incorrect
              and audit["artifacts"][name]["provenance_current"] == (not reasons)
              and set(audit["artifacts"][name]["reasons"]) == reasons,
              job_id, name, "arithmetic, provenance or inspection mismatch")
        if is_fresh:
            fresh.add(name)
        if is_blocked:
            blocked.add(name)
        if is_incorrect:
            incorrect.add(name)
        if preserved_id:
            preserved.add(name)
    affected = truth["affected"]
    for label, names in (("reports",truth["reports"]),("artifacts",scope)):
        counts = dict(total=len(names), eligible=len(names&eligible), fresh=len(names&fresh),
                      eligible_affected=len(names&eligible&affected), fresh_affected=len(names&fresh&affected),
                      unavailable=len(names-eligible), correctly_blocked=len(names&blocked), unaffected=len(names&unaffected),
                      unaffected_artifacts_preserved=len(names&unaffected&preserved), incorrect_current=len(names&incorrect))
        check(score[f"verified_{label}_counts"] == counts, job_id, label, "all reported counts")
        if label == "reports":
            report_counts = counts
    absolute = (eligible == fresh and scope-eligible == blocked and not incorrect and unaffected <= preserved
                and not runtime["unexpected_refresh_error"] and not runtime["inspection_errors"])
    case_id = result["case_id"]
    safe_abstention = bool(case_id == "M07" and absolute and abstain and not selected)
    safe_refusal = bool(case_id == "M07" and absolute and not abstain and selected
                       and runtime["expected_source_unavailable_refusal"])
    if case_id == "M07":
        decision = safe_abstention or safe_refusal
    elif case_id == "M08":
        decision = not abstain and not selected
    else:
        decision = not abstain and bool(selected)
    check(score["absolute_correct"] == score["semantic_endstate_correct"] == absolute, job_id, "whole-case endstate")
    task = dict(schema_valid_plan=True, semantic_endstate_correct=absolute, model_task_success=absolute and decision,
                safe_explicit_abstention=safe_abstention, safe_execution_refusal=safe_refusal)
    return report_counts, task

def verify(repo):
    run = repo / RUN
    prepared_dir = repo / PREPARED
    publication = run / "publication"
    jobs = [f"{case}:{arm}" for i,case in enumerate(CASES) for arm in ARMS[i%6:]+ARMS[:i%6]]
    required = {str(RUN / job.replace(":", "/") / name) for job in jobs
                for name in ("result.json", "execution/independent_audit.json", "execution/post_snapshot.json")}
    required |= {str(RUN / name) for name in ("summary.json", "started.json")}
    required |= {str(RUN / "publication" / name) for name in
                 ("audit.json", "poststate_manifest.json", "prelaunch_resolution.json", "prelaunch_stop.json",
                  "provider_metrics.json", "raw_sha256.json")}
    manifest = load(publication / "publication_manifest.json")
    check(manifest["source_revision"] == REVISION and set(manifest["files"]) == required,
          "exact publication file allowlist")
    for name, info in manifest["files"].items():
        path = repo / name
        check(path.stat().st_size == info["bytes"], name, "publication bytes")
        require_hash(path, info["sha256"])

    require_hash(prepared_dir / "prepared.json", PREPARED_SHA256)
    prepared = load(prepared_dir / "prepared.json")
    freeze_path = repo / FIXTURE.parent / "study_freeze.json"
    require_hash(freeze_path, prepared["freeze_sha256"])
    freeze = load(freeze_path)
    fixture = load(repo / FIXTURE / "fixture.json")
    days = tuple(f"2011-03-{i:02}" for i in range(1, 5))
    check(tuple(fixture["dates"]) == days, "fixed test dates")
    fixture_hashes = {item["path"]:item["sha256"] for item in freeze["fixture_files"]["test"]}
    for name in ("fixture.json", *(f"{day}.{extension}" for day in days for extension in ("csv","provenance.json"))):
        relative = FIXTURE / name
        require_hash(repo / relative, fixture_hashes[str(relative)])
    base, raw_rows = baseline_sources(repo, fixture)
    truths = {}
    check([case["case_id"] for case in prepared["cases"]] == list(CASES), "fixed case order")
    for case in prepared["cases"]:
        case_id = case["case_id"]
        for name in ("case.json", "initial_records.json", "current_sources.json", "corpus.jsonl"):
            relative = f"{case_id}/{name}"
            require_hash(prepared_dir / relative, prepared["artifact_sha256"][relative])
        check(load(prepared_dir / case_id / "case.json") == case, case_id, "frozen case")
        truths[case_id] = case_truth(prepared_dir / case_id, case, fixture, base, raw_rows)

    summary = load(run / "summary.json")
    start = load(run / "started.json")
    check(start["revision"] == REVISION and start["planned_cells"] == 48 and start["prepared_sha256"] == PREPARED_SHA256,
          "run start and frozen preparation")
    check(summary["integrity_verified"] and not summary["integrity_error"] and not summary["stop_reason"], "saved end-integrity")
    stop = load(publication / "prelaunch_stop.json")
    resolution = load(publication / "prelaunch_resolution.json")
    check(stop["paid_reservations"] == resolution["paid_reservations"] == 0
          and Decimal(stop["reported_cost_usd"]) == Decimal(resolution["reported_cost_usd"]) == 0
          and stop["expected_files_unchanged"] and len(stop["extra_files"]) == 16
          and resolution["model_outcomes_observed"] is False, "zero-call prelaunch integrity stop")
    provider_file = load(publication / "provider_metrics.json")
    audit_file = load(publication / "audit.json")
    raw_index = load(publication / "raw_sha256.json")
    for published in (provider_file, audit_file, raw_index):
        check(published["frozen_revision"] == REVISION and published["prepared_sha256"] == PREPARED_SHA256,
              "publication artifact identity")
    require_hash(run / "summary.json", audit_file["actual_run_summary_sha256"])
    require_hash(run / "summary.json", raw_index["run_files"]["summary.json"])
    require_hash(run / "started.json", raw_index["run_files"]["started.json"])
    ledger = summary["ledger"]
    attempts = ledger["attempts"]
    ordered = (prepared["jobs"], summary["cells"], provider_file["cells"], audit_file["cells"], attempts)
    check(all([r["job_id"] for r in rows] == jobs for rows in ordered) and set(raw_index["cells"]) == set(jobs),
          "48 fixed planned, scored and settled cells")
    check(ledger["limit_usd"] == "10.00" and not ledger["stopped"] and ledger["stop_reason"] is None
          and len(ledger["dry_runs"]) == 1 and not ledger["dry_runs"][0]["model_calls_permitted"],
          "fixed ledger limit, no stop and unpaid development start")
    accum = {arm:Counter() for arm in ARMS}
    providers, receipts = Counter(), Counter()
    spend = Decimal(0)
    previous_settlement = datetime.fromisoformat(start["started_at"])
    for job, cell, provider, audit_row, attempt in zip(*ordered, strict=True):
        job_id, case_id, arm = job["job_id"], job["case_id"], job["arm"]
        check(job_id == f"{case_id}:{arm}" and all(cell[key] == value for key,value in job.items()), job_id, "fixed job details")
        truth = truths[case_id]
        directory = run / case_id / arm
        result = load(directory / "result.json")
        check(result == {key:value for key,value in cell.items() if key != "model_task"}, job_id, "saved result vs. summary")
        for stream in ("stdout", "stderr"):
            check(provider[f"{stream}_sha256"] == result["process"][f"{stream}_sha256"]
                  == raw_index["cells"][job_id][f"{case_id}/{arm}/cli/{stream}.log"], job_id, stream, "original log digest binding")
        request_ids = verify_request(prepared_dir, prepared, truth["case"], job)
        selected, abstain = verify_plan(provider, result, request_ids, truth, job)
        counts, cost = normalized_usage(provider, result, job_id)
        cap = Decimal(attempt["configured_cap_usd"])
        reservation = datetime.fromisoformat(attempt["reserved_at"])
        launched = datetime.fromisoformat(result["process"]["started_at"])
        finished = datetime.fromisoformat(result["process"]["finished_at"])
        settlement = datetime.fromisoformat(attempt["settled_at"])
        check(cap == min(Decimal(1), Decimal(10)-spend) and float(cap) == result["process"]["configured_cap_usd"]
              and cost <= cap+Decimal("0.000001") and attempt["configured_cap_overshoot"] is False
              and attempt["usage_known"] is True and attempt["status"] == "accounted"
              and attempt["run_identity"] == PREPARED_SHA256
              and Decimal(attempt["reported_cost_usd"]) == Decimal(str(result["known_cost_usd"]))
              and previous_settlement <= reservation <= launched <= finished <= settlement,
              job_id, "ordered reservations, settled charges and soft cap")
        previous_settlement = settlement
        spend += Decimal(attempt["reported_cost_usd"])
        reports, task = verify_endstate(directory, result, truth, selected, abstain, job_id)
        for tail in ("result.json", "execution/independent_audit.json", "execution/post_snapshot.json"):
            relative = f"{case_id}/{arm}/{tail}"
            require_hash(run / relative, raw_index["cells"][job_id][relative])
        check(task == cell["model_task"], job_id, "model decision and semantic endstate")
        check(audit_row["fresh_affected"] == reports["fresh_affected"]
              and audit_row["correct_blocks"] == reports["correctly_blocked"]
              and audit_row["unaffected_report_ids_preserved"] == reports["unaffected_artifacts_preserved"]
              and audit_row["incorrect_current"] == reports["incorrect_current"]
              and audit_row["whole_case"] == task["semantic_endstate_correct"]
              and audit_row["model_task_success"] == task["model_task_success"]
              and audit_row["provider_input_exposure"] == counts["provider_input_exposure"]
              and Decimal(audit_row["raw_list_cost_usd"]) == cost,
              job_id, "independent audit row")
        totals = accum[arm]
        totals.update(counts)
        totals.update(reports)
        totals.update(task)
        totals["cost_usd"] += cost
        totals["correction_case_success"] += int(case_id <= "M06" and task["model_task_success"])
        providers[arm, case_id] = counts["provider_input_exposure"]
        receipts[arm, case_id] = job["evidence_tokens"]
    exact_cost = sum((totals["cost_usd"] for totals in accum.values()),Decimal(0))
    check(spend == Decimal(ledger["spent_known_usd"]) == Decimal(audit_file["reported_ledger_cost_usd"])
          and exact_cost == Decimal(audit_file["raw_cost_usd"])
          and abs(exact_cost-spend) < Decimal("0.000000000001") and spend < 10, "study cost and ledger total")

    for arm, actual in accum.items():
        expected = next(row for row in summary["arms"] if row["arm"] == arm)
        planned = dict(reports=88, eligible_reports=84, eligible_affected_reports=32, unavailable_reports=4, unaffected_reports=52)
        check(expected["planned_report_counts"] == planned and {key:actual[key] for key in
              ("total","eligible","eligible_affected","unavailable","unaffected")} == dict(
              total=88,eligible=84,eligible_affected=32,unavailable=4,unaffected=52), arm, "fixed report denominators")
        names = {"fresh_affected_reports_observed":"fresh_affected", "incorrect_current_reports_observed":"incorrect_current",
                 "absolute_correct_cases":"semantic_endstate_correct", "model_task_success_cases":"model_task_success",
                 "safe_execution_refusals":"safe_execution_refusal", "safe_explicit_abstentions":"safe_explicit_abstention",
                 "provider_input_exposure_known":"provider_input_exposure", "uncached_input_tokens_known":"input_tokens",
                 "cache_creation_tokens_known":"cache_creation_input_tokens", "cache_read_tokens_known":"cache_read_input_tokens",
                 "output_tokens_known":"output_tokens", "cli_turns_known":"num_turns"}
        check(all(expected[key] == actual[value] for key,value in names.items())
              and all(expected[key] == 8 for key in ("planned_cells","attempted_cells","usage_known_cells","scored_cells"))
              and abs(Decimal(str(expected["reported_cost_usd_known"]))-actual["cost_usd"]) < Decimal("0.000000000001"),
              arm, "all published aggregate counts and billing")
    def comparison(counts, cases):
        graph = sum(counts["graph", case] for case in cases)
        full = sum(counts["full_context", case] for case in cases)
        return {"graph":graph, "full_context":full, "ratio":graph/full}

    graph = accum["graph"]
    reliability = (graph["schema_valid_plan"] == graph["model_task_success"] == 8
                   and graph["eligible_affected"] == graph["fresh_affected"]
                   and graph["unavailable"] == graph["correctly_blocked"]
                   and graph["unaffected"] == graph["unaffected_artifacts_preserved"]
                   and graph["incorrect_current"] == 0)
    provider_primary = comparison(providers,CASES[:-1])
    provider_all = comparison(providers,CASES)
    receipt_primary = comparison(receipts,CASES[:-1])
    receipt_all = comparison(receipts,CASES)
    passed = reliability and provider_primary["ratio"] <= 0.5
    check(summary["complete_study"] is True and summary["primary"] == dict(absolute_graph_reliability=reliability,
          maximum_ratio=0.5, non_noop_provider_input_ratio=provider_primary["ratio"], passed=passed), "primary gate")
    check(summary["secondary"] == dict(including_noop_provider_input_ratio=provider_all["ratio"],
          graph_fresh_at_least_full_context=graph["fresh_affected"] >= accum["full_context"]["fresh_affected"],
          non_noop_receipt_only_ratio=receipt_primary["ratio"], including_noop_receipt_only_ratio=receipt_all["ratio"]),
          "secondary outcomes")
    check(audit_file["gates"] == dict(provider_non_noop=provider_primary, provider_including_noop=provider_all,
          receipts_non_noop=receipt_primary, receipts_including_noop=receipt_all, absolute_graph_reliability=reliability,
          complete_known_scored=True, passed=passed), "published independent gate results")
    return dict(published_files_verified=len(required), invocations=len(jobs), scored_cells=len(jobs),
                reconstructed_source_rows=len(raw_rows), provider_cli_turns=sum(row["num_turns"] for row in accum.values()),
                reported_list_cost_usd=str(exact_cost), provider_input_non_noop=provider_primary, passed=passed,
                fresh_affected={arm:counts["fresh_affected"] for arm,counts in accum.items()},
                correction_case_success={arm:counts["correction_case_success"] for arm,counts in accum.items()})


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("checkout", nargs="?", default=".", type=Path, help="root containing results and fixtures")
    try:
        result = verify(parser.parse_args().checkout.resolve())
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration, ArithmeticError) as error:
        parser.exit(1, f"Evidence verification failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
