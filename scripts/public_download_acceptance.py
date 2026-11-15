"""Verify the anonymous public downloads against a clean checkout."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import ssl
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
HOST = "proofflow.arnavbule.in"
ORIGIN = f"https://{HOST}"
ARCHIVE = "proofflow-model-evidence.zip"
DELIVERY_ARCHIVE = "proofflow-delivery-evidence.zip"
FIXED_ARCHIVE = "proofflow-fixed-budget-evidence.zip"
CONNECTOR = "proofflow_csv_mcp.py"
MCP_VERSION = "2.3.0"
TOOLS = {
    "create_csv_reports", "inspect_reports", "update_csv", "refresh_reports", "export_current_reports",
}
EVIDENCE_FILES = {
    "/evidence/": ("evidence/index.html", "text/html"),
    "/evidence/evidence.css": ("evidence/evidence.css", "text/css"),
    f"/evidence/{ARCHIVE}": (f"evidence/{ARCHIVE}", "application/zip"),
    f"/evidence/{ARCHIVE}.sha256": (f"evidence/{ARCHIVE}.sha256", None),
}
DELIVERY_FILES = {
    f"/evidence/{DELIVERY_ARCHIVE}": (f"evidence/{DELIVERY_ARCHIVE}", "application/zip"),
    f"/evidence/{DELIVERY_ARCHIVE}.sha256": (f"evidence/{DELIVERY_ARCHIVE}.sha256", None),
}
FIXED_FILES = {
    f"/evidence/{FIXED_ARCHIVE}": (f"evidence/{FIXED_ARCHIVE}", "application/zip"),
    f"/evidence/{FIXED_ARCHIVE}.sha256": (f"evidence/{FIXED_ARCHIVE}.sha256", None),
}
DELIVERY_RELEASES = [
    "0535ba672b4b31c563c13d95df03285a73a4d736",
    "fdee9c999a1a5c62de4cf624f9bcc42ba6c124a6",
    "92da58c806a07d2577aef27bf5c967e7751325a0",
]
DELIVERY_RESULTS = {
    "real_partition": {
        "rows": 642, "invoices": 25, "initial_usd_cents": 905258,
        "corrected_usd_cents": 941468, "verified_phases": 6,
    },
    "paired_workflow": {
        "phases": 3, "stale_refusals_per_method": 4, "current_handoffs_per_method": 3,
        "proofflow_new_outputs": [8, 4, 6], "proofflow_retained_heads_and_receipts": [0, 4, 2],
        "proofflow_warm_analytics_calls": 64,
    },
    "interrupted_update": {"checks_passed": 15},
    "fixed_budget_diagnostic": {
        "planned_cells": 88, "original_completed": False, "original_wrapper_execution_errors": 88,
        "recovered_scored_cells": 88,
        "fresh_affected": {
            "fixed_4096": {"graph": 15, "exact_flat": 15, "bm25": 5, "dense": 2, "iterative_hybrid": 15},
            "fixed_8192": {"graph": 27, "exact_flat": 27, "bm25": 25, "dense": 10, "iterative_hybrid": 28},
            "uncapped_reference": {"full_context": 32},
        },
    },
}
AGENT_FILES = {
    "/agent/": ("agent/index.html", "text/html"),
    "/agent/index.html": ("agent/index.html", "text/html"),
    f"/agent/{CONNECTOR}": (f"agent/{CONNECTOR}", None),
    f"/agent/{CONNECTOR}.sha256": (f"agent/{CONNECTOR}.sha256", None),
}
RECEIPT_MIME_TYPES = {
    "application/json", "application/octet-stream", "application/zip",
    "text/css", "text/html", "text/plain", "text/x-python", "text/x-python-script",
}


class CheckFailure(Exception):
    """An assertion label safe to store in public-delivery receipts."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def require(condition, label):
    if not condition:
        raise CheckFailure(label)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return sha256(data).hexdigest()


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, timeout=30,
    ).stdout


def network():
    hosts = Path("/etc/hosts").read_text()
    names = {name.rstrip(".").lower() for line in hosts.splitlines()
             for name in line.split("#", 1)[0].split()[1:]}
    require(HOST not in names, "Canonical hostname has no hosts-file override")
    families = sorted({item[0].name for item in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)})
    require(families, "Canonical hostname resolves through the system resolver")
    tls = ssl.create_default_context()
    require(tls.check_hostname and tls.verify_mode == ssl.CERT_REQUIRED, "HTTPS validates the certificate and hostname")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls), NoRedirect())
    return opener, {
        "resolver": "System DNS", "address_families": families, "hosts_file_override": False,
        "proxy_enabled": False, "certificate_and_hostname_validation": True, "anonymous": True,
    }


def public_get(opener, path):
    request = Request(f"{ORIGIN}{path}", headers={"Accept-Encoding": "identity"})
    try:
        return opener.open(request, timeout=30)
    except HTTPError as response:
        return response


def response_observation(response, path, expected_mime=None):
    mime = response.headers.get_content_type() if "Content-Type" in response.headers else None
    return {
        "status": response.status,
        "mime_type": mime if mime is None or mime in RECEIPT_MIME_TYPES else "other",
        "expected_mime_matches": mime == expected_mime if expected_mime else None,
        "canonical_url_matches": response.url == ORIGIN + path,
        "set_cookie_present": "Set-Cookie" in response.headers,
    }


def download_files(opener, source_sha, files, receipt):
    downloads = {}
    for path, (filename, content_type) in files.items():
        expected = git("show", f"{source_sha}:frontend/public/{filename}")
        with public_get(opener, path) as response:
            observed = response_observation(response, path, content_type)
            receipt["files"][path] = observed
            require(observed["status"] == 200 and observed["canonical_url_matches"], f"{path} returns canonical HTTPS 200")
            require(not observed["set_cookie_present"], f"{path} does not set a session cookie")
            require(observed["expected_mime_matches"] is not False, f"{path} returns expected MIME type")
            downloaded = response.read(len(expected) + 1)
        observed.update({
            "bytes": len(downloaded), "sha256": digest(downloaded),
            "checkout_sha256": digest(expected), "byte_match": downloaded == expected,
        })
        require(downloaded == expected, f"{path} matches checked-out public file bytes")
        downloads[filename] = downloaded
    return downloads


def verify_sidecar(data, sidecar, filename):
    require(sidecar == f"{digest(data)}  {filename}\n".encode(), f"{filename} matches its published SHA-256 sidecar")


def extract_bundle(data, directory):
    directory.mkdir()
    with ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        require(entries and len(entries) <= 1000 and sum(entry.file_size for entry in entries) <= 128 * 1024**2,
                "Evidence archive inventory and extracted bytes are bounded")
        seen = set()
        for entry in entries:
            member = PurePosixPath(entry.filename)
            require(
                member.parts and not member.is_absolute() and ".." not in member.parts
                and "\\" not in entry.filename and member not in seen and stat.S_ISREG(entry.external_attr >> 16),
                "Evidence archive contains unique, relative regular files",
            )
            seen.add(member)
            target = directory.joinpath(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))


def offline_python():
    # Ubuntu hosted runners have passwordless sudo. Drop back to the runner's
    # UID/GID inside the fresh network namespace before starting the verifier.
    uid, gid = os.getuid(), os.getgid()
    require(uid != 0 and os.geteuid() == uid and os.getegid() == gid, "Verifier caller has the runner's non-root identity")
    namespace = os.readlink("/proc/self/ns/net")
    launcher = (
        'actual=$(readlink /proc/self/ns/net) && test -n "$actual" && test "$actual" != "$1" '
        '&& test "$(id -u)" = "$2" && test "$(id -g)" = "$3" && shift 3 && exec "$@"'
    )
    return [
        "sudo", "-n", "unshare", "--net", "--setgid", str(gid), "--setuid", str(uid),
        "--", "/bin/sh", "-c", launcher, "proofflow-offline", namespace, str(uid), str(gid),
        sys.executable, "-E", "-s", "-S", "-B",
    ]


def run_bundled_verifier(data, directory, python, verifier):
    extract_bundle(data, directory)
    result = subprocess.run(
        [*python, verifier], cwd=directory, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=90, check=False,
    )
    require(result.returncode == 0, f"{verifier} passed in isolated extraction")
    return json.loads(result.stdout)


def verify_bundle(data, directory, python):
    verifier = "scripts/verify_public_evidence.py"
    report = run_bundled_verifier(data, directory, python, verifier)
    model = report["model_study"]
    study_revision = json.loads((directory / "manifest.json").read_bytes())["frozen_study_revision"]
    require(report["bundle_files_verified"] == 346 and model["passed"] is True
            and model["published_files_verified"] == 152 and model["scored_cells"] == 48
            and model["reconstructed_source_rows"] == 4681 and re.fullmatch(r"[0-9a-f]{40}", study_revision),
            "Expected model study and bundle inventory verified")
    return {
        "bundle_files_verified": report["bundle_files_verified"], "model_study_payloads_verified": model["published_files_verified"],
        "scored_cells": model["scored_cells"], "reconstructed_source_rows": model["reconstructed_source_rows"],
        "bundled_verifier": verifier, "frozen_study_revision": study_revision,
    }


def verify_delivery_bundle(data, directory, python):
    verifier = "verify_delivery_evidence.py"
    report = run_bundled_verifier(data, directory, python, verifier)
    inventory = json.loads((directory / "manifest.json").read_bytes())["files"]
    require(report["bundle_files_verified"] == len(inventory) == 52, "Delivery bundle inventory verified")
    releases = report["hosted"]["releases"]
    require(releases == DELIVERY_RELEASES, "Expected historical hosted release receipts verified")
    observed = {}
    for section, expected in DELIVERY_RESULTS.items():
        observed[section] = {key: report[section][key] for key in expected}
        require(observed[section] == expected, f"Expected delivery evidence verified for {section}")
    return {
        "bundle_files_verified": report["bundle_files_verified"], "bundled_verifier": verifier,
        "historical_hosted_release_revisions": releases, **observed,
    }


def verify_fixed_budget_bundle(data, directory, python):
    verifier = "scripts/verify_fixed_budget_evidence.py"
    report = run_bundled_verifier(data, directory, python, verifier)
    inventory = json.loads((directory / "manifest.json").read_bytes())["files"]
    expected = DELIVERY_RESULTS["fixed_budget_diagnostic"]
    require(report["bundle_files_verified"] == len(inventory) == 249
            and report["verified_cells"] == len(report["cells"]) == expected["recovered_scored_cells"]
            and report["reconstructed_source_rows"] == 4681
            and report["original_completed"] is False
            and report["original_wrapper_execution_errors"] == expected["original_wrapper_execution_errors"],
            "Fixed-budget per-cell inventory and original failed wrapper verified")
    groups = report["groups"]
    by_condition = {condition: {row["arm"]: row["reports_observed"]["fresh_affected"]
                                for row in groups if row["condition"] == condition}
                    for condition in expected["fresh_affected"]}
    require(len(groups) == 11 and by_condition == expected["fresh_affected"] and all(
        row["reports_observed"]["unavailable_blocked"] == 4
        and row["reports_observed"]["unaffected_preserved"] == 52
        and row["reports_observed"]["incorrect_current"] == 0 for row in groups
    ), "Independent fixed-budget outcomes and safety counts verified")
    parity = report["graph_exact_flat_context_parity"]
    require(parity == {str(cap): {"planned": 8, "observed": 8, "matching_contexts": 8} for cap in (4096, 8192)},
            "All saved graph and exact-flat contexts match at each cap")
    return {
        "bundle_files_verified": report["bundle_files_verified"], "bundled_verifier": verifier,
        "frozen_study_revision": report["frozen_study_revision"], "verified_cells": report["verified_cells"],
        "reconstructed_source_rows": report["reconstructed_source_rows"], "graph_exact_flat_context_parity": parity,
        "original_completed": report["original_completed"],
        "original_wrapper_execution_errors": report["original_wrapper_execution_errors"], "fresh_affected": by_condition,
    }


async def cold_connector(script, scratch):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    require(version("mcp") == MCP_VERSION, "Stock MCP client has the expected dependency version")
    uv = shutil.which("uv")
    require(uv is not None, "uv is installed")
    run_dir = scratch / "empty-working-directory"
    cache = scratch / "cache"
    for directory in (run_dir, cache):
        directory.mkdir()
    params = StdioServerParameters(
        command=uv,
        args=["run", "--no-project", "--no-config", "--default-index", "https://pypi.org/simple",
              "--python", sys.executable, "--script", str(script)],
        cwd=run_dir,
        env={"UV_CACHE_DIR": str(cache), "UV_PYTHON_DOWNLOADS": "never", "UV_NO_PROGRESS": "1"},
    )
    with open(os.devnull, "w") as stderr:
        async with asyncio.timeout(180):
            async with stdio_client(params, errlog=stderr) as streams:
                async with ClientSession(*streams) as session:
                    initialized = await session.initialize()
                    listed = await session.list_tools()
    require(initialized.server_info.name == "ProofFlow Hosted CSV", "Downloaded connector identifies the expected MCP server")
    names = sorted(tool.name for tool in listed.tools)
    require(names == sorted(TOOLS) and listed.next_cursor is None, "Downloaded connector advertises exactly five expected tools")
    protocol = initialized.protocol_version
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}", protocol), "MCP negotiates a date-based protocol version")
    responses = (initialized.model_dump_json() + listed.model_dump_json()).lower()
    require(not any(marker in responses for marker in ("proofflow_session", "session_id", "set-cookie", "bearer ")),
            "MCP handshake and catalog expose no session or cookie fields")
    return {
        "mcp_client_version": MCP_VERSION, "negotiated_protocol": protocol, "tools": names,
        "fresh_uv_cache": True, "empty_working_directory": True, "pep723_uv_launch": True,
        "methods": ["initialize", "notifications/initialized", "tools/list"],
        "tool_calls": 0, "session_or_cookie_fields_in_output": False,
    }


def runner_context(receipt):
    env = os.environ
    source_sha = git("rev-parse", "HEAD").decode().strip()
    clean = not git("status", "--porcelain")
    receipt["source_sha"] = source_sha
    receipt["source_worktree_clean"] = clean
    receipt["runner"] = {
        "provider": "GitHub Actions", "environment": env.get("RUNNER_ENVIRONMENT"), "image_os": env.get("ImageOS"),
        "image_version": env.get("ImageVersion"), "arch": env.get("RUNNER_ARCH"), "event": env.get("GITHUB_EVENT_NAME"),
        "repository": env.get("GITHUB_REPOSITORY"), "run_id": env.get("GITHUB_RUN_ID"),
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT"), "workflow_ref": env.get("GITHUB_WORKFLOW_REF"),
    }
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted"
            and env.get("RUNNER_OS") == "Linux" and env.get("ImageOS") == "ubuntu24"
            and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "Manual GitHub-hosted Ubuntu 24.04 run")
    require(clean and source_sha == env.get("GITHUB_SHA"), "Clean checkout matches workflow source SHA")
    return source_sha


def main():
    os.umask(0o077)
    # Keep SDK transport diagnostics and subprocess output out of workflow logs.
    logging.disable(logging.CRITICAL)
    output = Path(os.environ["PROOFFLOW_PUBLIC_DOWNLOAD_OUTPUT"])
    output.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": 1, "origin": ORIGIN, "started_at_utc": utc_now(), "files": {}, "passed": False,
        "scope": "Public evidence bundles and connector static bytes, offline verification, and MCP initialization and tool discovery.",
        "revision_scope": "Checkout SHA identifies the expected static files. The model and fixed-budget bundles pin their study revisions. The delivery bundle lists historical releases.",
    }
    stage = "runner_provenance"
    try:
        source_sha = runner_context(receipt)
        stage = "network"
        opener, receipt["network"] = network()
        with TemporaryDirectory(prefix="proofflow-cold-download-") as temp:
            temporary = Path(temp)
            stage = "evidence_download"
            evidence = download_files(opener, source_sha, EVIDENCE_FILES, receipt)
            archive = evidence[f"evidence/{ARCHIVE}"]
            verify_sidecar(archive, evidence[f"evidence/{ARCHIVE}.sha256"], ARCHIVE)
            stage = "offline_bundle_verification"
            receipt[stage] = verify_bundle(archive, temporary / "extracted", offline_python())
            receipt[stage]["isolated_linux_network_namespace"] = True

            stage = "delivery_evidence_download"
            delivery = download_files(opener, source_sha, DELIVERY_FILES, receipt)
            archive = delivery[f"evidence/{DELIVERY_ARCHIVE}"]
            verify_sidecar(archive, delivery[f"evidence/{DELIVERY_ARCHIVE}.sha256"], DELIVERY_ARCHIVE)
            stage = "offline_delivery_verification"
            receipt[stage] = verify_delivery_bundle(archive, temporary / "delivery-extracted", offline_python())
            receipt[stage]["isolated_linux_network_namespace"] = True

            stage = "fixed_budget_evidence_download"
            fixed = download_files(opener, source_sha, FIXED_FILES, receipt)
            archive = fixed[f"evidence/{FIXED_ARCHIVE}"]
            verify_sidecar(archive, fixed[f"evidence/{FIXED_ARCHIVE}.sha256"], FIXED_ARCHIVE)
            stage = "offline_fixed_budget_verification"
            receipt[stage] = verify_fixed_budget_bundle(archive, temporary / "fixed-budget-extracted", offline_python())
            receipt[stage]["isolated_linux_network_namespace"] = True

            stage = "connector_download"
            with public_get(opener, "/agent") as response:
                redirect = response_observation(response, "/agent")
                redirect["location_matches"] = response.headers.get("Location") == "/agent/"
                receipt["agent_redirect"] = redirect
                require(redirect["status"] == 308 and redirect["canonical_url_matches"] and redirect["location_matches"]
                        and not redirect["set_cookie_present"], "Connector entry redirects to canonical /agent/")
                redirect["location"] = "/agent/"
            downloads = download_files(opener, source_sha, AGENT_FILES, receipt)
            source = downloads[f"agent/{CONNECTOR}"]
            verify_sidecar(source, downloads[f"agent/{CONNECTOR}.sha256"], CONNECTOR)
            script = temporary / CONNECTOR
            script.write_bytes(source)
            stage = "cold_connector_handshake"
            receipt[stage] = asyncio.run(cold_connector(script, temporary))
        receipt["passed"] = True
    except Exception as error:
        reason = str(error) if isinstance(error, CheckFailure) else "Request, subprocess, or assertion did not complete"
        receipt["failure"] = {"stage": stage, "reason": reason}
        print(f"Public download acceptance failed in {stage}: {reason}")
    finally:
        receipt["finished_at_utc"] = utc_now()
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    if receipt["passed"]:
        print("Public payload bytes, all three offline evidence verifiers, and cold MCP handshake passed")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
