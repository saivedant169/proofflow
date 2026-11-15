#!/usr/bin/env python3
"""Run the frozen application for browser tests against the real HydraDB.

This is test infrastructure, not an application entry point. It never exposes a
fault-control HTTP route. The optional fault exists only in this Python process
and fires once, after an existing CSV orders source has actually been replaced.

Invoke with the worktree root explicitly on PYTHONPATH and the existing Hydra
URL/token-file environment inherited. Credentials are handled by HydraGraph;
this harness neither reads nor prints credential values. State and fault logs
must live outside this worktree. Uvicorn runs in the foreground so the test
runner's SIGTERM reaches its normal lifespan shutdown and closes session stores.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
import json
import os
from pathlib import Path
import subprocess
import threading
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
MAX_FAULT_LOG_BYTES = 64 * 1024
MAX_FAULT_EVENT_BYTES = 4096


def port_number(value: str) -> int:
    port = int(value)
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("Use an unprivileged port between 1024 and 65535")
    return port


def in_checkout(path: Path) -> bool:
    checkouts = [ROOT]
    if (ROOT / ".git").exists():
        listing = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain", "-z"], cwd=ROOT, text=True
        )
        checkouts.extend(Path(entry.removeprefix("worktree ")) for entry in listing.split("\0")
                         if entry.startswith("worktree "))
    # samefile handles case aliases on case-insensitive volumes, and checks
    # the nearest existing ancestor when a state directory is not yet created.
    return any(ancestor.samefile(checkout) for ancestor in (path, *path.parents) if ancestor.exists()
               for checkout in checkouts if checkout.exists())


def append_fault_event(path: Path, event: dict[str, Any]) -> None:
    """Append bounded, credential-free evidence of the committed boundary."""
    data = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(data) > MAX_FAULT_EVENT_BYTES:
        raise RuntimeError("Fault evidence exceeds its bounded event size")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if os.fstat(descriptor).st_size + len(data) > MAX_FAULT_LOG_BYTES:
            raise RuntimeError("Fault evidence log is full; use a fresh external test directory")
        # One event per process and one writer per port; a single small append
        # avoids emitting a partially assembled JSON record under normal I/O.
        if os.write(descriptor, data) != len(data):
            raise RuntimeError("Could not write complete fault evidence")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def fault_after_changed_orders(event_path: Path) -> Iterator[None]:
    from proofflow.graph import GraphError, HydraGraph
    from proofflow.runtime import ProofFlowRuntime

    original = ProofFlowRuntime.set_source
    fired = False
    lock = threading.Lock()

    @wraps(original)
    def set_source(runtime: ProofFlowRuntime, name: str, value: Any, description: str = ""):
        nonlocal fired
        change = original(runtime, name, value, description)
        # Initial creation has no previous ID. An FX-only update leaves orders
        # unchanged. Neither may consume the one-shot fault.
        if name != "csv:orders" or not change.changed or not change.previous_id:
            return change
        with lock:
            if fired:
                return change
            if not isinstance(runtime.graph, HydraGraph):
                raise RuntimeError("This browser fault test requires the real HydraDB adapter")
            head = runtime.store.get_head(change.logical_id)
            if head is None or head.id != change.current_id:
                raise RuntimeError("The expected source commit was not observed; fault was not injected")
            fired = True
            append_fault_event(event_path, {
                "event": "injected_failure_after_committed_csv_orders",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "logical_id": change.logical_id,
                "previous_source_id": change.previous_id,
                "committed_source_id": change.current_id,
                "committed_content_hash": head.content_hash,
                "source_head_verified": True,
                "original_set_source_returned": True,
                "graph_adapter": "HydraGraph",
                "fault_scope": "test_process_only",
            })
            raise GraphError("Injected test-process failure after committed CSV orders replacement")

    ProofFlowRuntime.set_source = set_source
    try:
        yield
    finally:
        ProofFlowRuntime.set_source = original


@contextmanager
def perturb_corrected_fx() -> Iterator[None]:
    """Mutation control: a one-cent arithmetic error in this server only."""
    from proofflow import analytics

    name = "convert_to_usd"
    original = analytics._IMPLEMENTATIONS[name]

    @wraps(original)
    def convert(inputs, params):
        result = original(inputs, params)
        if Decimal(str(inputs["fx"].get("EUR", "0"))) == Decimal("1.30") and "NORTH" in result["regions"]:
            result["regions"]["NORTH"]["usd_cents"] += 1
        return result

    analytics._IMPLEMENTATIONS[name] = convert
    try:
        yield
    finally:
        analytics._IMPLEMENTATIONS[name] = original


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, required=True)
    parser.add_argument("--state-dir", type=Path, required=True,
                        help="Dedicated test session directory outside the worktree")
    parser.add_argument("--static-dir", type=Path, required=True,
                        help="Compiled frontend directory containing index.html")
    simulation = parser.add_mutually_exclusive_group()
    simulation.add_argument("--fault-after-orders", action="store_true",
                            help="Inject one post-commit source failure in this test process only")
    simulation.add_argument("--negative-fx-cent", action="store_true",
                            help="Add a cent to corrected EUR conversion for the browser arithmetic control")
    args = parser.parse_args()

    paths = [Path(part).resolve() for part in os.environ.get("PYTHONPATH", "").split(os.pathsep) if part]
    if ROOT not in paths:
        parser.error("Set PYTHONPATH explicitly to this worktree root")
    state_dir = args.state_dir.resolve()
    static_dir = args.static_dir.resolve()
    if in_checkout(state_dir):
        parser.error("Test state and fault evidence must be outside all ProofFlow worktrees")
    if not (static_dir / "index.html").is_file():
        parser.error("Build the frontend first; --static-dir must contain index.html")
    state_dir.mkdir(parents=True, exist_ok=True)
    # api.py also creates its conventional module-level app while importing.
    # Point that otherwise unused manager at the same external test directory
    # so importing the production module cannot create .state in the worktree.
    os.environ["PROOFFLOW_STATE_DIR"] = str(state_dir)
    os.environ["PROOFFLOW_STATIC_DIR"] = str(static_dir)

    import proofflow
    if Path(proofflow.__file__).resolve().parent != ROOT / "proofflow":
        parser.error("Python imported a different checkout of ProofFlow")

    import uvicorn
    from proofflow.api import create_app
    from proofflow.graph import HydraGraph

    application = create_app(state_dir=state_dir, static_dir=static_dir, graph_factory=HydraGraph)
    event_path = state_dir.parent / f"fault-events-{args.port}.jsonl"
    control = (fault_after_changed_orders(event_path) if args.fault_after_orders else
               perturb_corrected_fx() if args.negative_fx_cent else nullcontext())
    with control:
        uvicorn.run(application, host="127.0.0.1", port=args.port, workers=1,
                    access_log=False, log_level="warning", lifespan="on")


if __name__ == "__main__":
    main()
