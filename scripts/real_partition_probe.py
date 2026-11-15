"""Prepare and check one prospective hosted CSV workflow on UCI retail data."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from hashlib import sha256
from io import StringIO
from itertools import groupby
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from time import monotonic
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/real_partition_v1"
PROBE = "real-partition-v1"
ORIGIN = "https://proofflow.arnavbule.in"
FROZEN_PATHS = ("docs/REAL_PARTITION_PROTOCOL.md", "fixtures/real_partition_v1",
                "scripts/real_partition_probe.py", "tests/test_real_partition_probe.py",
                ".github/workflows/real-partition-acceptance.yml")
RELEASE_PATHS = (".dockerignore", "Dockerfile", "frontend", "proofflow", "pyproject.toml", "uv.lock",
                 "evidence/benchmark_summary.json", "evidence/agent_composition.json", "evidence/retail_v2_summary.json",
                 "evidence/model_comparison_v4_summary.json", "video/proofflow-walkthrough.mp4", "video/poster.jpg")
WORKBOOK_SHA = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
MAX_ROWS = 1000
MAX_CSV_BYTES = 1024 * 1024
MAX_PENCE = 10**12
RESERVED_MONTHS = ("2010-12", "2011-02", "2011-05", "2011-08", "2011-11")
COMPACT_DATES = ("2011-01-04", "2011-01-05", "2011-01-06", "2011-01-07", "2011-01-09",
                 "2011-09-01", "2011-09-02", "2011-09-04", "2011-09-05", "2011-09-06")
MODEL_DATES = ("2011-03-01", "2011-03-02", "2011-03-03", "2011-03-04", "2011-06-01", "2011-06-02")
RATES = {"initial": "1.25", "corrected": "1.30"}
UPLOAD_FIELDS = ("order_id", "region", "currency", "gross_cents")
RAW_FIELDS = ("source_row", "invoice_no", "invoice_date_raw_xml", "quantity_raw_xml", "unit_price_raw_xml", "country")
STATE = "/api/import/state"
EXPORT = "/api/import/export"
POST_PLAN = (("/api/session", 200), ("/api/import/preview", 200), ("/api/import/create", 200), (EXPORT, 200),
             ("/api/import/preview", 200), ("/api/import/update", 200), (EXPORT, 409), ("/api/import/refresh", 200), (EXPORT, 200))
REPORT_KEYS = ("company", "region")
INDEPENDENT_HEADS = frozenset(("import:metric:gross", "import:metric:refunds", "import:metric:net",
                               "import:metric:support"))
FX_HEADS = frozenset(("import:metric:regional", "import:metric:company",
                      "import:report:company", "import:report:region"))
TIMEOUT_MS = 30_000
STEPS = ("release_preflight", "upload_preview_create", "initial_checked_download",
         "correction_and_old_export_refusal", "refresh_and_checked_download", "reload_persisted_heads")


class CheckFailure(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CheckFailure(message)


def digest(payload):
    return sha256(payload).hexdigest()


def json_bytes(payload):
    return (json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def csv_bytes(fields, rows):
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def parse_csv(payload, fields):
    reader = csv.DictReader(StringIO(payload.decode("utf-8"), newline=""))
    require(tuple(reader.fieldnames or ()) == fields, "Unexpected fixture CSV headers")
    rows = list(reader)
    require(all(set(row) == set(fields) and None not in row.values() for row in rows), "Malformed fixture CSV row")
    return rows


def source_day(serial):
    # The original workbook uses the Excel 1900 date system. Take the day from
    # its serial calendar value without inferring a time zone or rounding time.
    whole_days = int(Decimal(serial))
    return (date(1899, 12, 30) + timedelta(days=whole_days)).isoformat()


def eligible_line(index, raw):
    invoice = raw["InvoiceNo"].strip()
    country = raw["Country"].strip()
    key = f"uci:{invoice}:row:{index}"
    if invoice.upper().startswith("C"):
        return None, "cancellation_invoice"
    if (not invoice or not country or len(country) > 64 or country.startswith("__") or len(key) > 200
            or any(ord(char) < 32 or ord(char) == 127 for char in country + key)):
        return None, "invalid_invoice_or_country"
    try:
        quantity = Decimal(str(float(raw["Quantity"])))
        price = Decimal(str(float(raw["UnitPrice"])))
        if not quantity.is_finite() or not 0 < quantity <= 10**9 or quantity != quantity.to_integral_value():
            return None, "invalid_quantity"
        if not price.is_finite() or price <= 0:
            return None, "invalid_price"
        pence = quantity * price * 100
        if pence != pence.to_integral_value():
            return None, "fractional_line_pence"
        if not 0 < pence <= MAX_PENCE:
            return None, "line_amount_outside_bounds"
    except (ValueError, InvalidOperation, OverflowError):
        return None, "invalid_numeric_cells"
    original = dict(zip(RAW_FIELDS, (index, invoice, raw["InvoiceDate"], raw["Quantity"], raw["UnitPrice"], country)))
    return (original, dict(zip(UPLOAD_FIELDS, (key, country, "GBP", int(pence))))), "eligible"


def original_rows(workbook):
    # Reuse the existing hash-checked XML reader. Product and customer fields
    # are neither persisted as provenance nor sent to the hosted app.
    sys.path.insert(0, str(ROOT))
    from proofflow.eval.retail_data import iter_source_rows

    previous = ""
    for index, raw in iter_source_rows(workbook):
        day = source_day(raw["InvoiceDate"])
        require(day >= previous, "Pinned workbook rows are not chronological")
        previous = day
        yield day, index, raw


def money_oracle(raw_rows, region):
    """Recompute amounts from the raw cells, independently of the upload CSV and app."""
    pounds = Counter()
    for row in raw_rows:
        units = int(Decimal(row["quantity_raw_xml"]))
        price = Decimal(repr(float(row["unit_price_raw_xml"])))
        pounds[row["country"]] += units * price
    results = {}
    for stage, rate in RATES.items():
        usd = {country: int((gbp * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN) * 100)
               for country, gbp in sorted(pounds.items())}
        results[stage] = {"by_region_usd_cents": usd, "company_usd_cents": sum(usd.values()),
                          "region_usd_cents": usd[region]}
    return {"gross_gbp_by_region": {country: format(value, ".2f") for country, value in sorted(pounds.items())},
            **results}


def prepare(workbook):
    overlap_invoices = set()
    candidate_profiles = []
    reserved_days = set(COMPACT_DATES) | set(MODEL_DATES)
    selected = None
    total_source_rows = 0
    for day, group in groupby(original_rows(workbook), key=lambda entry: entry[0]):
        counts = Counter()
        lines = []
        reserved = day[:7] in RESERVED_MONTHS or day in reserved_days
        for _, index, raw in group:
            total_source_rows += 1
            if reserved:
                overlap_invoices.add(raw["InvoiceNo"].strip())
            elif selected is None:
                line, category = eligible_line(index, raw)
                counts[category] += 1
                if line is not None and len(lines) < MAX_ROWS:
                    lines.append(line)
        if reserved or selected is not None:
            continue
        candidate_profiles.append({"date": day, "rows": sum(counts.values()), "counts": dict(counts)})
        if 0 < counts["eligible"] <= MAX_ROWS:
            selected = day, lines
    require(total_source_rows == 541_909, "Unexpected original workbook row count")
    require(selected is not None, "No eligible unused daily partition fits the frozen cap")
    day, lines = selected
    source_rows, upload_rows = tuple(zip(*lines))
    invoices = {row["invoice_no"] for row in source_rows}
    require(not invoices.intersection(overlap_invoices), "Selected invoices overlap earlier reserved partitions")
    counts_by_region = Counter(row["country"] for row in source_rows)
    region = min(counts_by_region, key=lambda name: (-counts_by_region[name], name))
    uploads = csv_bytes(UPLOAD_FIELDS, upload_rows)
    require(len(uploads) <= MAX_CSV_BYTES, "First eligible date exceeds the CSV byte limit")
    provenance = csv_bytes(RAW_FIELDS, source_rows)
    files = {"orders.csv": uploads, "source_cells.csv": provenance}
    manifest = {
        "schema_version": 1,
        "probe": PROBE,
        "source": {"doi": "10.24432/C5BW33", "license": "CC BY 4.0", "workbook_sha256": WORKBOOK_SHA,
                   "workbook_rows": total_source_rows},
        "reserved": {"retail_v2_months": RESERVED_MONTHS, "compact_v3_dates": COMPACT_DATES,
                     "model_v4_dates": MODEL_DATES},
        "candidate_profiles_through_selected_date": candidate_profiles,
        "selected_date": day,
        "selected_region": region,
        "rows": len(source_rows),
        "invoices": len(invoices),
        "invoice_overlap_with_reserved_partitions": 0,
        "rows_by_region": dict(counts_by_region),
        "authored_gbp_to_usd": RATES,
        "oracle": money_oracle(source_rows, region),
        "files": {key: {"sha256": digest(content), "bytes": len(content)} for key, content in files.items()},
    }
    return {**files, "fixture.json": json_bytes(manifest)}


def check_fixture(directory):
    manifest = json.loads((directory / "fixture.json").read_bytes())
    require(manifest["schema_version"] == 1 and manifest["probe"] == PROBE, "Unexpected fixture schema")
    require(manifest["source"]["workbook_sha256"] == WORKBOOK_SHA and manifest["authored_gbp_to_usd"] == RATES,
            "Unexpected workbook or authored rate")
    require(set(manifest["files"]) == {"orders.csv", "source_cells.csv"}, "Unexpected fixture file inventory")
    payloads = {}
    for filename, recorded in manifest["files"].items():
        content = (directory / filename).read_bytes()
        require(recorded == {"sha256": digest(content), "bytes": len(content)}, f"Fixture hash or size mismatch for {filename}")
        payloads[filename] = content
    original = parse_csv(payloads["source_cells.csv"], RAW_FIELDS)
    uploaded = parse_csv(payloads["orders.csv"], UPLOAD_FIELDS)
    require(0 < len(original) == len(uploaded) == manifest["rows"] <= MAX_ROWS, "Fixture row count mismatch")
    require(len(payloads["orders.csv"]) <= MAX_CSV_BYTES, "Fixture exceeds CSV byte limit")
    numbers = [int(line["source_row"]) for line in original]
    require(numbers == sorted(set(numbers)), "Original worksheet rows are unordered or duplicated")
    require(len({line["invoice_no"] for line in original}) == manifest["invoices"], "Invoice count mismatch")
    region_counts = Counter(line["country"] for line in original)
    region = min(region_counts, key=lambda name: (-region_counts[name], name))
    require(manifest["selected_region"] == region and manifest["rows_by_region"] == dict(region_counts), "Region selection mismatch")
    for line, order in zip(original, uploaded, strict=True):
        require(source_day(line["invoice_date_raw_xml"]) == manifest["selected_date"], "Unexpected source day")
        raw_quantity = Decimal(line["quantity_raw_xml"])
        quantity = int(raw_quantity)
        pence = Decimal(repr(float(line["unit_price_raw_xml"]))) * (100 * quantity)
        require(1 <= quantity <= 10**9 and quantity == raw_quantity and 0 < pence <= MAX_PENCE and pence == int(pence),
                "Provenance has an unsupported quantity or line amount")
        expected = (f"uci:{line['invoice_no']}:row:{line['source_row']}", line["country"], "GBP", str(int(pence)))
        require(tuple(order[k] for k in UPLOAD_FIELDS) == expected, "Upload row differs from its original worksheet cells")
    oracle = money_oracle(original, region)
    require(oracle == manifest["oracle"], "Independent oracle differs from the frozen arithmetic")
    return manifest, payloads["orders.csv"]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def check_revisions(freeze, release, image_id):
    require(re.fullmatch(r"[0-9a-f]{40}", freeze) and re.fullmatch(r"[0-9a-f]{40}", release)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id), "Invalid freeze, release or image ID")
    require(not git("status", "--porcelain"), "The hosted probe checkout must be clean")
    for revision, paths in ((freeze, FROZEN_PATHS), (release, RELEASE_PATHS)):
        git("merge-base", "--is-ancestor", revision, "HEAD")
        require(not git("diff", "--name-only", revision, "HEAD", "--", *paths), "Checkout differs from the supplied freeze or release")
    return git("rev-parse", "HEAD")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def asset_paths(index):
    paths = sorted({path.decode("ascii") for path in re.findall(rb'''/assets/[\w.-]+\.(?:js|css)(?=["'])''', index)})
    require(any(path.endswith(".js") for path in paths) and any(path.endswith(".css") for path in paths),
            "Build HTML lacks its bundled script or stylesheet")
    return paths


def release_preflight(playwright, build, receipt):
    host = urlsplit(ORIGIN).hostname
    require(not any(host in line.split("#", 1)[0].lower().split()[1:] for line in Path("/etc/hosts").read_text().splitlines()),
            "Canonical hostname has a hosts-file override")
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    require(bool(addresses), "System DNS did not resolve the public host")
    local_index = (build / "index.html").read_bytes()
    paths = asset_paths(local_index)
    context = playwright.request.new_context(ignore_https_errors=False)
    try:
        health = context.get(f"{ORIGIN}/health", timeout=TIMEOUT_MS, max_redirects=0, max_retries=0)
        require(health.status == 200 and health.json() == {"status": "ok", "backend": "HydraDB OSS"},
                "Public health check did not report a healthy HydraDB backend")
        served_build = {}
        for route in ["/", *paths]:
            response = context.get(f"{ORIGIN}{route}", timeout=TIMEOUT_MS, max_redirects=0, max_retries=0)
            require(response.status == 200, f"Public build request {route} returned {response.status}")
            local_bytes = local_index if route == "/" else (build / route.lstrip("/")).read_bytes()
            served = response.body()
            served_build[route] = {"sha256": digest(served), "bytes": len(served)}
            require(served == local_bytes, f"Public build bytes at {route} differ from the release rebuild")
        receipt["preflight"] = {"origin": ORIGIN, "health_http_status": 200, "backend": "HydraDB OSS",
                                "system_dns_address_families": sorted({item[0].name for item in addresses}),
                                "frontend_byte_match": True, "served_build": served_build}
    finally:
        context.dispose()


def get_button(page, name):
    return page.get_by_role("button", name=name, exact=True)


def wait_response(page, method, path):
    return page.expect_response(lambda response: response.url == f"{ORIGIN}{path}" and response.request.method == method,
                                timeout=TIMEOUT_MS)


def response_json(response, status, label):
    require(response.status == status, f"{label} returned HTTP {response.status}, expected {status}")
    require(response.headers.get("content-type", "").startswith("application/json"), f"{label} did not return JSON")
    return response.json()


def click_post(page, path, name):
    with wait_response(page, "POST", path) as pending:
        get_button(page, name).click()
    return response_json(pending.value, 200, name)


def dataset_match(dataset, manifest, sha_key):
    return (dataset.get("row_count") == manifest["rows"] and dataset.get("currencies") == ["GBP"]
            and dataset.get("regions") == sorted(manifest["rows_by_region"])
            and dataset.get("selected_region") == manifest["selected_region"]
            and dataset.get(sha_key) == manifest["files"]["orders.csv"]["sha256"])


def previews(page, expect, orders, manifest, stage):
    creating = stage == "initial"
    get_button(page, "Use your data" if creating else "Update CSV").click()
    page.get_by_label("Upload UTF-8 CSV", exact=True).set_input_files({"name": "orders.csv", "mimeType": "text/csv", "buffer": orders})
    page.get_by_label("GBP → USD", exact=True).fill(RATES[stage])
    if creating:
        page.get_by_label("Region for the second report", exact=True).fill(manifest["selected_region"])
    preview = click_post(page, "/api/import/preview", "Validate CSV")
    require(dataset_match(preview, manifest, "content_sha256"), "Preview did not validate all frozen rows, region and currency")
    expected = {"preflight_calculation_count": 8, "recorded_tool_call_count": 0,
                "verification_calculation_count": 0, "total_calculation_count": 8}
    require(preview.get("valid") is True and preview.get("persisted") is False and preview.get("accounting") == expected
            and preview.get("supported_ticket_regions") == [] and preview.get("rates", {}).get("GBP") == str(Decimal(RATES[stage]).normalize()),
            "Preview did not return expected validation-only accounting, support input or FX")
    expect(page.get_by_role("region", name="Validated CSV preview")).to_contain_text("8 validation calculations · 0 recorded tool calls")
    return expected


def current_reports(state, status, expected):
    reports = {item["key"]: item for item in state["reports"]}
    require(set(reports) == set(REPORT_KEYS) and len(state["reports"]) == 2, "Workspace did not contain both reports")
    for key in REPORT_KEYS:
        report = reports[key]
        require(len(report["claims"]) == 1 and report["state"] == status, f"{key} report did not have expected state and claim count")
        claim = report["claims"][0]
        require(claim["state"] == status and claim["value"] == expected[key] and claim["unit"] == "USD cents",
                f"{key} report claim did not match the independently calculated state or value")
        require(type(claim["value"]) is (type(None) if status == "stale" else int), f"{key} report claim value had an unexpected type")
    return reports


def backend_and_dataset(state, manifest):
    backend = state["backend"]
    require(backend["engine"] == "HydraDB OSS" and backend["fallback"] is False and backend["native_queries"] > 0,
            "Imported workspace did not use native HydraDB queries")
    require(state["mode"] == "guided_csv_import" and state["incomplete_update"] is False
            and dataset_match(state["dataset"], manifest, "source_csv_sha256"), "Published state does not match frozen CSV")
    return backend["native_queries"]


def operation(state, kind, expected, changed_source_count=0):
    op = state["last_operation"]
    keys = ("preflight_calculation_count", "recorded_tool_call_count", "verification_calculation_count")
    require(op["kind"] == kind and tuple(op[key] for key in keys) == expected and op["total_calculation_count"] == sum(expected)
            and op["changed_source_count"] == changed_source_count and op["noop"] is False
            and len(op["tool_calls"]) == expected[1], f"Unexpected operation accounting for {kind}")
    return {key: op[key] for key in (*keys, "total_calculation_count", "changed_source_count")}


def source_ids(state):
    sources = {item["name"]: item["id"] for item in state["dataset"]["sources"]}
    require(set(sources) == {"orders", "refunds", "fx", "tickets"}, "Source version inventory differs")
    return sources


def artifact_heads(state):
    heads = {node["logical_id"]: node["id"] for node in state["graph"]["nodes"]
             if node["kind"] == "artifact" and node["current_head"]}
    require(set(heads) == INDEPENDENT_HEADS | FX_HEADS, "Unexpected current artifact inventory")
    return heads


def export_selection(state):
    return {"generation": state["generation"], "report_ids": {item["key"]: item["id"] for item in state["reports"]}}


def display_usd(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"


def metric_values(page):
    return page.locator(".report-panel .metric strong")


def check_export_headers(response):
    headers = response.all_headers()
    require(headers.get("cache-control") == "no-store" and "set-cookie" not in headers,
            "Checked export was cacheable or issued a session cookie")


def checked_download(page, expect, state, reports, expected, region, orders):
    started = datetime.now(timezone.utc)
    with wait_response(page, "POST", EXPORT) as pending, page.expect_download(timeout=TIMEOUT_MS) as download_info:
        get_button(page, "Download current reports").click()
    response, download = pending.value, download_info.value
    exported = response_json(response, 200, "Checked export")
    check_export_headers(response)
    require(response.request.post_data_json == export_selection(state), "Export did not send the visible report heads")
    filename = "proofflow-current-reports.txt"
    require(exported["filename"] == download.suggested_filename == filename
            and exported["media_type"] == "text/plain;charset=utf-8", "Unexpected checked download filename or media type")
    downloaded = Path(download.path())
    content = downloaded.read_bytes()
    require(content == exported["content"].encode("utf-8"), "Downloaded bytes differ from the server-checked snapshot")
    text = content.decode("utf-8")
    timestamp = exported["checked_at"]
    check_time = datetime.fromisoformat(timestamp)
    require(check_time.utcoffset() == timedelta(0) and abs((check_time - started).total_seconds()) < 120
            and f"Checked at (UTC): {timestamp}" in text, "Snapshot lacks the current UTC check time")
    company, regional = reports["company"], reports["region"]
    lines = (
        f"Company net revenue: {display_usd(expected['company'])} USD\nReport artifact ID: {company['id']}\nClaim artifact ID: {company['claims'][0]['artifact_id']}",
        f"Regional net revenue ({region!r}): {display_usd(expected['region'])} USD\nReport artifact ID: {regional['id']}\nClaim artifact ID: {regional['claims'][0]['artifact_id']}",
    )
    require(all(line in text for line in lines), "Checked export did not pair correct amounts with both report and claim IDs")
    cookie = next((item["value"] for item in page.context.cookies() if item["name"] == "proofflow_session"), None)
    excluded = [cookie, state["session_id"], state["generation"], *orders.decode("utf-8").splitlines()]
    require(all(item and item not in text for item in excluded), "Checked file disclosed CSV text or private session identifiers")
    expect(page.get_by_role("status").filter(has_text="Snapshot checked at").locator("time")).to_have_attribute("datetime", timestamp)
    return downloaded, {"http_status": response.status, "bytes": len(content), "sha256": digest(content), "checked_at_utc": timestamp,
                        "matches_server_bytes": True, "both_amounts_and_report_claim_ids_match": True, "no_store": True}


def screenshot(page, output, receipt, name, state):
    require(page.get_by_role("dialog").count() == 0, "An open dialog would reveal input data in the screenshot")
    visible = page.locator("body").inner_text(timeout=TIMEOUT_MS)
    cookie = next((item["value"] for item in page.context.cookies(ORIGIN) if item["name"] == "proofflow_session"), None)
    require(all(value and value not in visible for value in (cookie, state["session_id"], state["generation"])),
            "Screenshot blocked because session identifiers could be visible")
    filename = f"{name}.png"
    data = page.screenshot(path=output / filename, animations="disabled", timeout=TIMEOUT_MS)
    receipt["screenshots"].append({"file": filename, "sha256": digest(data), "bytes": len(data)})


def guard_browser_writes(context, receipt):
    plan = [path for path, _ in POST_PLAN]
    attempts = receipt["write_request_attempts"]

    def guard(route):
        request = route.request
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            route.continue_()
            return
        path = urlsplit(request.url).path
        next_index = len(attempts)
        allowed = (request.method == "POST" and next_index < len(plan)
                   and all(previous["allowed"] for previous in attempts)
                   and request.url == f"{ORIGIN}{plan[next_index]}")
        attempts.append({"method": request.method, "path": path if path in plan else "unplanned_api_route", "allowed": allowed})
        if allowed:
            route.continue_()
        else:
            route.abort()

    context.route(f"{ORIGIN}/api/**", guard)


def check_chrome(playwright, build, output, receipt, manifest, orders, step):
    from playwright.sync_api import expect

    expect.set_options(timeout=TIMEOUT_MS)
    browser = playwright.chromium.launch(channel="chrome", headless=True, timeout=TIMEOUT_MS)
    receipt["browser"] = {"channel": "chrome", "version": browser.version, "headless": True,
                          "viewport": {"width": 1536, "height": 1024}}
    try:
        context = browser.new_context(accept_downloads=True, service_workers="block", locale="en-US",
                                      viewport=receipt["browser"]["viewport"], ignore_https_errors=False)
        context.set_default_timeout(TIMEOUT_MS)
        receipt["browser"]["opened_contexts"] = 1
        try:
            exercise_ui(context, expect, build, output, receipt, manifest, orders, step)
        finally:
            context.close()
            receipt["browser"]["closed_contexts"] = 1
    finally:
        browser.close()


def exercise_ui(context, expect, build, output, receipt, manifest, orders, step):
    page = context.new_page()
    downloads = []
    page_errors = []
    report_region = manifest["selected_region"]
    expectations = {
        stage: {"company": manifest["oracle"][stage]["company_usd_cents"], "region": manifest["oracle"][stage]["region_usd_cents"]}
        for stage in RATES
    }
    display = {stage: [display_usd(values[key]) for key in REPORT_KEYS] for stage, values in expectations.items()}
    withheld = dict.fromkeys(REPORT_KEYS)
    monitored = {path for path, _ in POST_PLAN} | {STATE}

    def observe(response):
        url = urlsplit(response.url)
        if url.netloc == urlsplit(ORIGIN).netloc and url.path in monitored:
            receipt["http"].append({"method": response.request.method, "path": url.path, "status": response.status})

    guard_browser_writes(context, receipt)
    context.on("response", observe)
    page.on("download", lambda _: downloads.append(True))
    page.on("pageerror", lambda _: page_errors.append("primary_tab"))

    with step("upload_preview_create"):
        require(context.cookies() == [], "Initial Chrome context is not fresh")
        home = page.goto(ORIGIN, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        require(home.status == 200 and page.url == f"{ORIGIN}/" and home.request.redirected_from is None,
                "Chrome did not open the canonical site directly")
        protocol = (home.security_details() or {}).get("protocol")
        require(isinstance(protocol, str) and protocol.startswith("TLS"), "Browser did not report a validated TLS connection")
        receipt["browser"]["tls_protocol"] = protocol
        paths = page.locator('script[src^="/assets/"], link[href^="/assets/"]').evaluate_all(
            "nodes => Array.from(new Set(nodes.map(node => node.getAttribute('src') || node.getAttribute('href')))).sort()")
        require(paths == asset_paths((build / "index.html").read_bytes()), "Loaded Chrome page differs from preflight verified build")
        expect(get_button(page, "Use your data")).to_be_enabled()
        cookie = next((item for item in context.cookies(ORIGIN) if item["name"] == "proofflow_session"), {})
        require(cookie.get("secure") is True and cookie.get("httpOnly") is True and cookie.get("sameSite") == "Strict",
                "Expected secure session cookie attributes")
        receipt["browser"]["cookie_attributes"] = {"secure": True, "http_only": True, "same_site": "Strict"}
        preview = previews(page, expect, orders, manifest, "initial")
        state_before_create = page.request.get(f"{ORIGIN}{STATE}", timeout=TIMEOUT_MS, max_redirects=0, max_retries=0)
        require(state_before_create.status == 404, "Preview unexpectedly left an imported workspace")
        initial = click_post(page, "/api/import/create", "Create reports")
        native = backend_and_dataset(initial, manifest)
        initial_reports = current_reports(initial, "current", expectations["initial"])
        initial_heads = artifact_heads(initial)
        create_accounting = operation(initial, "create", (8, 8, 11), changed_source_count=4)
        expect(metric_values(page)).to_have_text(display["initial"])
        expect(page.get_by_role("dialog")).to_have_count(0)
        screenshot(page, output, receipt, "initial-reports", initial)
        receipt["initial"] = {"preview_accounting": preview, "create_accounting": create_accounting,
                              "native_queries": native, "revenue_usd_cents": expectations["initial"]}

    with step("initial_checked_download"):
        initial_file, receipt["initial"]["export"] = checked_download(
            page, expect, initial, initial_reports, expectations["initial"], report_region, orders)
        require(len(downloads) == 1, "Expected one initial browser download")
        screenshot(page, output, receipt, "initial-checked-download", initial)

    with step("correction_and_old_export_refusal"):
        # A popup inherits the opener's selected workspace preference and
        # retains a separate document with independently updated React state.
        with page.expect_popup(timeout=TIMEOUT_MS) as popup:
            page.evaluate("window.open(location.href, '_blank')")
        second = popup.value
        second.on("pageerror", lambda _: page_errors.append("correction_tab"))
        try:
            expect(metric_values(second)).to_have_text(display["initial"])
            preview = previews(second, expect, orders, manifest, "corrected")
            stale = click_post(second, "/api/import/update", "Publish correction")
            backend_and_dataset(stale, manifest)
            update_accounting = operation(stale, "update", (8, 0, 0), changed_source_count=1)
            require(stale["session_id"] == initial["session_id"] and export_selection(stale) == export_selection(initial),
                    "Correction did not retain the same session and pending report IDs")
            old_sources, new_sources = source_ids(initial), source_ids(stale)
            require({name for name in old_sources if old_sources[name] != new_sources[name]} == {"fx"}
                    and stale["impact"]["changed_source_ids"] == [old_sources["fx"]], "Correction changed source versions beyond FX")
            require(artifact_heads(stale) == initial_heads, "Correction published artifact heads before explicit refresh")
            affected = stale["impact"]["affected_artifacts"]
            require({(item["logical_id"], item["id"]) for item in affected} == {(key, initial_heads[key]) for key in FX_HEADS}
                    and len(affected) == len(FX_HEADS), "FX correction did not identify exactly the four dependent artifact heads")
            stale_reports = current_reports(stale, "stale", withheld)
            require(all(stale_reports[key]["claims"][0]["saved_value"] == expectations["initial"][key] for key in REPORT_KEYS),
                    "Stale report omitted or altered its labeled historical amount")
            expect(metric_values(second)).to_have_text(["Awaiting refresh"] * 2)
            expect(get_button(second, "Download current reports")).to_be_disabled()
            expect(metric_values(page)).to_have_text(display["initial"])
            expect(get_button(page, "Download current reports")).to_be_enabled()
            with wait_response(page, "POST", EXPORT) as refusal, wait_response(page, "GET", STATE) as reconciliation:
                get_button(page, "Download current reports").click()
            rejected = refusal.value
            error = response_json(rejected, 409, "Old-head export")
            check_export_headers(rejected)
            require(rejected.request.post_data_json == export_selection(initial) and set(error) == {"error"}
                    and error["error"]["code"] == "evidence_unavailable", "Old-head export did not fail closed on the original report IDs")
            current_reports(response_json(reconciliation.value, 200, "Old-tab reconciliation"), "stale", withheld)
            expect(page.get_by_role("alert")).to_contain_text("No report file was downloaded.")
            expect(metric_values(page)).to_have_text(["Awaiting refresh"] * 2)
            expect(page.locator(".report-panel .historical")).to_have_text([f"Previously {amount}" for amount in display["initial"]])
            expect(get_button(page, "Download current reports")).to_be_disabled()
            require(len(downloads) == 1, "Old-head rejection must produce no browser download")
            screenshot(page, output, receipt, "old-heads-refused", stale)
            receipt["correction"] = {"preview_accounting": preview, "update_accounting": update_accounting,
                                     "changed_sources": ["fx"], "affected_artifact_logical_ids": sorted(FX_HEADS),
                                     "current_revenue_usd_cents": withheld, "old_head_export_http_status": rejected.status,
                                     "old_head_export_error": error["error"]["code"], "old_head_export_downloads": 0,
                                     "reconciliation_http_status": reconciliation.value.status}
        finally:
            second.close()

    with step("refresh_and_checked_download"):
        fresh = click_post(page, "/api/import/refresh", "Refresh affected")
        native = backend_and_dataset(fresh, manifest)
        refresh_accounting = operation(fresh, "refresh", (0, 4, 11))
        fresh_reports = current_reports(fresh, "current", expectations["corrected"])
        fresh_heads = artifact_heads(fresh)
        require(fresh["session_id"] == initial["session_id"] and fresh["generation"] == initial["generation"]
                and source_ids(fresh) == new_sources, "Refresh unexpectedly changed session, workspace or source versions")
        require({key for key, old in initial_heads.items() if fresh_heads[key] != old} == FX_HEADS,
                "Refresh changed an unaffected head or failed to replace an affected one")
        summary = fresh["last_refresh"]
        require(summary["numeric_parity"] is True and summary["unchanged_support"] is True
                and summary["executed_count"] == 4 and set(summary["executed_artifact_ids"]) == {fresh_heads[k] for k in FX_HEADS},
                "Refresh verification, executed artifacts or support preservation differs")
        tool_counts = Counter(call["tool"] for call in fresh["last_operation"]["tool_calls"])
        require(tool_counts == {"convert_to_usd": 1, "company_total": 1, "compose_report": 2}, "Refresh executed an unexpected tool")
        expect(metric_values(page)).to_have_text(display["corrected"])
        _, fresh_export = checked_download(page, expect, fresh, fresh_reports, expectations["corrected"], report_region, orders)
        require(len(downloads) == 2 and digest(initial_file.read_bytes()) == receipt["initial"]["export"]["sha256"],
                "Expected two checked files and unchanged initial snapshot bytes")
        screenshot(page, output, receipt, "refreshed-checked-download", fresh)
        receipt["refresh"] = {"accounting": refresh_accounting, "native_queries": native,
                              "recorded_tools": dict(tool_counts), "unchanged_artifact_logical_ids": sorted(INDEPENDENT_HEADS),
                              "revenue_usd_cents": expectations["corrected"], "initial_file_remained_unchanged": True,
                              "refresh_verification_passed": True, "export": fresh_export}

    with step("reload_persisted_heads"):
        with wait_response(page, "GET", STATE) as reloaded:
            response = page.reload(wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        require(response.status == 200, "Chrome did not reload the application")
        reopened = response_json(reloaded.value, 200, "Reloaded workspace")
        backend_and_dataset(reopened, manifest)
        current_reports(reopened, "current", expectations["corrected"])
        require(reopened["session_id"] == initial["session_id"] and export_selection(reopened) == export_selection(fresh)
                and artifact_heads(reopened) == fresh_heads and source_ids(reopened) == new_sources,
                "Reload did not retain the corrected workspace evidence")
        expect(metric_values(page)).to_have_text(display["corrected"])
        require(not page_errors, "Unexpected JavaScript runtime error")
        expected_attempts = [{"method": "POST", "path": path, "allowed": True} for path, _ in POST_PLAN]
        actual_posts = [(item["path"], item["status"]) for item in receipt["http"] if item["method"] == "POST"]
        require(receipt["write_request_attempts"] == expected_attempts and actual_posts == list(POST_PLAN),
                "Browser write requests or responses did not match the frozen plan")
        receipt["reload"] = {"same_session_source_and_artifact_heads": True, "revenue_usd_cents": expectations["corrected"],
                             "unexpected_javascript_runtime_errors": len(page_errors), "checked_files_downloaded": len(downloads)}


def run_hosted(args):
    from contextlib import contextmanager
    from importlib.metadata import version
    from playwright.sync_api import sync_playwright

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema_version": 1, "probe": PROBE, "scope": "Automated hosted Chrome acceptance on one UCI trading date",
        "started_at_utc": utc_now(), "origin": ORIGIN, "passed": False,
        "steps": {name: {"status": "not_run"} for name in STEPS},
        "screenshots": [], "http": [], "write_request_attempts": [],
    }
    current_step = None

    def save_receipt():
        pending = output / ".receipt.json.tmp"
        pending.write_bytes(json_bytes(receipt))
        pending.replace(output / "receipt.json")

    @contextmanager
    def step(name):
        nonlocal current_step
        current_step = name
        started = monotonic()
        receipt["steps"][name] = {"status": "started", "started_at_utc": utc_now()}
        save_receipt()
        try:
            yield
        except BaseException:
            receipt["steps"][name]["status"] = "fail"
            raise
        else:
            receipt["steps"][name]["status"] = "pass"
            print(f"{name} passed", flush=True)
        finally:
            receipt["steps"][name]["elapsed_ms"] = round((monotonic() - started) * 1000)
            save_receipt()

    try:
        with step("release_preflight"):
            env = os.environ
            require(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
                    and env.get("RUNNER_OS") == "Linux" and env.get("ImageOS") == "ubuntu24"
                    and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_RUN_ATTEMPT") == "1",
                    "Measured probe requires a first-attempt manual run on GitHub-hosted Ubuntu 24.04")
            proxy_env = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
            require(not any(env.get(key) for key in proxy_env) and env.get("NODE_TLS_REJECT_UNAUTHORIZED") != "0",
                    "Probe must use direct network access and standard TLS verification")
            checkout = check_revisions(args.freeze_revision, args.release_revision, args.image_id)
            receipt["freeze_revision"] = args.freeze_revision
            receipt["operator_verified_release"] = {"source_revision": args.release_revision, "image_id": args.image_id}
            require(checkout == env.get("GITHUB_SHA") and env.get("GITHUB_SERVER_URL") == "https://github.com",
                    "Clean checkout does not match GitHub run revision")
            require(version("playwright") == "1.56.0", "The hosted Playwright package is outside the frozen version")
            receipt["checkout_revision"] = checkout
            receipt["runner"] = {"provider": "GitHub Actions", "environment": env["RUNNER_ENVIRONMENT"], "image_os": env["ImageOS"],
                                 "image_version": env.get("ImageVersion"), "playwright_version": version("playwright"),
                                 "run_attempt": env["GITHUB_RUN_ATTEMPT"],
                                 "run_url": f"https://github.com/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"}
            manifest, orders = check_fixture(FIXTURES)
            receipt["fixture"] = {"manifest_sha256": digest((FIXTURES / "fixture.json").read_bytes()),
                                  "protocol_sha256": digest((ROOT / FROZEN_PATHS[0]).read_bytes()),
                                  "probe_sha256": digest(Path(__file__).read_bytes()),
                                  "date": manifest["selected_date"], "rows": manifest["rows"], "invoices": manifest["invoices"],
                                  "report_region": manifest["selected_region"], "files": manifest["files"],
                                  "authored_gbp_to_usd": RATES, "oracle": manifest["oracle"]}
            with sync_playwright() as playwright:
                release_preflight(playwright, args.build, receipt)
        with sync_playwright() as playwright:
            check_chrome(playwright, args.build, output, receipt, manifest, orders, step)
        receipt["passed"] = all(item["status"] == "pass" for item in receipt["steps"].values())
    except Exception as error:
        # Raw browser assertion messages may contain request payloads and IDs.
        failure = str(error) if isinstance(error, CheckFailure) else type(error).__name__
        receipt["failure"] = {"step": current_step, "reason": failure}
        print(f"Probe failed in {current_step}: {failure}", file=sys.stderr, flush=True)
    finally:
        receipt["finished_at_utc"] = utc_now()
        save_receipt()
    return 0 if receipt["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare", help="Regenerate the inputs into a new directory without running the app")
    preparation.add_argument("--workbook", type=Path, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    audit = commands.add_parser("audit", help="Recompute oracles and optionally re-scan the workbook without running the app")
    audit.add_argument("--workbook", type=Path)
    hosted = commands.add_parser("hosted", help="Run once in the reviewed GitHub Actions workflow")
    hosted.add_argument("--build", type=Path, default=ROOT / "frontend/dist")
    hosted.add_argument("--output", type=Path, required=True)
    hosted.add_argument("--freeze-revision", required=True)
    hosted.add_argument("--release-revision", required=True)
    hosted.add_argument("--image-id", required=True)
    args = parser.parse_args()
    if args.command == "hosted":
        return run_hosted(args)
    if args.command == "prepare":
        rebuilt = prepare(args.workbook)
        args.output.mkdir(parents=True, exist_ok=False)
        for name, payload in rebuilt.items():
            (args.output / name).write_bytes(payload)
        directory = args.output
    else:
        directory = FIXTURES
        if args.workbook:
            for name, payload in prepare(args.workbook).items():
                require(payload == (directory / name).read_bytes(), f"Workbook-derived {name} differs from the freeze")
    manifest, _ = check_fixture(directory)
    print(f"Audited {manifest['rows']} rows from {manifest['selected_date']} and both independent rate calculations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
