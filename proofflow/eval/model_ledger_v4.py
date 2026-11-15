"""Durable single-study spending and development-run guard, with no model calls."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any


class StudyStopped(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cost(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("A known charge must be a finite nonnegative number")
    return Decimal(str(value))


class StudyLedger:
    """Reserve before launching; any ambiguous/pending invocation blocks reuse.

    This controls harness launches, not remote in-flight billing. Reported
    costs are never clipped, and no retry/reset operation is exposed.
    """
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "ledger.json"
        self.lock_path = self.directory / "ledger.lock"
        with self._locked():
            if not self.path.exists():
                self._write({"version": "model-comparison-v4-ledger", "limit_usd": "10.00",
                             "spent_known_usd": "0", "stopped": False, "stop_reason": None,
                             "attempts": [], "dry_runs": [], "created_at": _now()})

    @contextmanager
    def _locked(self):
        with self.lock_path.open("a+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _read(self) -> dict[str, Any]:
        state = json.loads(self.path.read_text())
        if state.get("version") != "model-comparison-v4-ledger" or state.get("limit_usd") != "10.00":
            raise StudyStopped("Study ledger identity/budget differs from the fixed protocol")
        return state

    def _write(self, state: dict[str, Any]) -> None:
        encoded = json.dumps(state, sort_keys=True, indent=2, allow_nan=False) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=self.directory, prefix="ledger-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.path)
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    def snapshot(self) -> dict[str, Any]:
        with self._locked():
            return self._read()

    def begin_dry_run(self, output: str) -> int:
        with self._locked():
            state = self._read()
            if state["attempts"]:
                raise StudyStopped("Development cannot resume after a model invocation was reserved")
            if len(state["dry_runs"]) >= 2:
                raise StudyStopped("The two permitted no-model development dry runs are already used")
            number = len(state["dry_runs"]) + 1
            state["dry_runs"].append({"number": number, "output": output, "started_at": _now(),
                                      "model_calls_permitted": False})
            self._write(state)
            return number

    def reserve(self, job_id: str, run_identity: str) -> float:
        with self._locked():
            state = self._read()
            if state["stopped"]:
                raise StudyStopped(f"Study is stopped: {state['stop_reason']}")
            if any(item["status"] == "pending" for item in state["attempts"]):
                raise StudyStopped("A pending attempt may already be charged; it must never be retried")
            if any(item["job_id"] == job_id for item in state["attempts"]):
                raise StudyStopped("This planned cell already has an attempt; retries are forbidden")
            if len(state["attempts"]) >= 48:
                raise StudyStopped("All 48 planned invocation slots are already reserved")
            remaining = Decimal(state["limit_usd"]) - Decimal(state["spent_known_usd"])
            if remaining <= 0:
                raise StudyStopped("The reported-cost study allowance is exhausted")
            cap = min(Decimal("1.00"), remaining)
            state["attempts"].append({"job_id": job_id, "run_identity": run_identity, "status": "pending",
                                      "configured_cap_usd": str(cap), "reserved_at": _now(),
                                      "reported_cost_usd": None})
            self._write(state)
            return float(cap)

    def settle(self, job_id: str, reported_cost_usd: float | None, *, usage_known: bool,
               stop_reason: str | None = None) -> dict[str, Any]:
        charge = _cost(reported_cost_usd) if reported_cost_usd is not None else None
        with self._locked():
            state = self._read()
            matches = [item for item in state["attempts"] if item["job_id"] == job_id]
            if len(matches) != 1 or matches[0]["status"] != "pending":
                raise StudyStopped("Only a unique pending attempt can be settled")
            attempt = matches[0]
            attempt.update(status="accounted" if charge is not None and usage_known else "unknown_accounting",
                           reported_cost_usd=str(charge) if charge is not None else None,
                           usage_known=usage_known, settled_at=_now())
            if charge is not None:
                state["spent_known_usd"] = str(Decimal(state["spent_known_usd"]) + charge)
            overshoot = charge is not None and charge > Decimal(attempt["configured_cap_usd"]) + Decimal("0.000001")
            attempt["configured_cap_overshoot"] = bool(overshoot)
            reason = stop_reason
            if charge is None or not usage_known:
                reason = reason or "Unknown billing or provider usage"
            if overshoot:
                reason = reason or "Reported in-flight charge exceeded the configured per-invocation cap"
            if Decimal(state["spent_known_usd"]) >= Decimal(state["limit_usd"]):
                reason = reason or "Reported aggregate study allowance reached or exceeded"
            if reason:
                state.update(stopped=True, stop_reason=reason, stopped_at=_now())
            self._write(state)
            return state

    def stop(self, reason: str) -> None:
        with self._locked():
            state = self._read()
            state.update(stopped=True, stop_reason=reason, stopped_at=_now())
            self._write(state)
