"""One isolated CLI invocation, with raw evidence and no retry or billing inference.

The caller owns authorization, the study spend ledger and strict usage parsing.
This adapter never executes a returned plan. Claude Code may perform internal
turns; one harness invocation is not a guarantee of one provider request.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any

from proofflow.agent import AgentRequest, PLAN_SCHEMA, SYSTEM_PROMPT


MODEL = "claude-fable-5-2"
EFFORT = "high"
TERMINATION_GRACE_SECONDS = 2.0
ISOLATION_SETTINGS = {
    "disableAllHooks": True,
    "claudeMdExcludes": ["**"],
    "autoMemoryEnabled": False,
    "syncClaudeAiPlugins": False,
    "syncClaudeAiSkills": False,
    "disableWorkflows": True,
    "enabledPlugins": {},
}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _positive_bounded(value: float, name: str, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f"{name} must be finite, positive, and at most {maximum}")


def _write_new(path: Path, text: str) -> None:
    # Exclusive, durable creation protects the attempt evidence from reuse.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def build_command(cap_usd: float, settings_path: Path | str, executable: str = "claude") -> list[str]:
    """Construct the same fixed planner interface for every retrieval arm."""
    _positive_bounded(cap_usd, "cap_usd", 1.0)
    if not isinstance(executable, str) or not executable.strip():
        raise ValueError("A nonempty CLI executable is required")
    return [executable, "-p", "--model", MODEL, "--effort", EFFORT,
            "--safe-mode", "--tools", "", "--setting-sources", "",
            "--settings", str(Path(settings_path).resolve()),
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--disable-slash-commands", "--no-session-persistence", "--no-chrome",
            "--permission-mode", "dontAsk", "--output-format", "json",
            "--max-budget-usd", str(cap_usd), "--system-prompt", SYSTEM_PROMPT,
            "--json-schema", _json(PLAN_SCHEMA)]


def _client_environment() -> dict[str, str]:
    # Existing CLI authentication is inherited, never read from credential
    # files or persisted. A planner has no reason to inherit Hydra credentials.
    env = dict(os.environ)
    env.pop("PROOFFLOW_HYDRA_TOKEN", None)
    env.pop("PROOFFLOW_HYDRA_TOKEN_FILE", None)
    return env


def _error(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _cancel_process_group(process: subprocess.Popen) -> dict[str, Any]:
    """Bounded group cancellation; no launch/retry and no remote billing claim."""
    result: dict[str, Any] = {"term_sent": False, "kill_sent": False,
                              "leader_reaped": False, "errors": []}
    try:
        os.killpg(process.pid, signal.SIGTERM)
        result["term_sent"] = True
    except ProcessLookupError:
        pass
    except OSError as exc:
        result["errors"].append(_error(exc))
    try:
        process.wait(timeout=TERMINATION_GRACE_SECONDS)
        result["leader_reaped"] = True
    except subprocess.TimeoutExpired:
        pass
    except OSError as exc:
        result["errors"].append(_error(exc))
    # The direct CLI may exit while another process in its session survives.
    # Check the group itself instead of assuming leader exit killed children.
    group_exists = True
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        group_exists = False
    except OSError as exc:
        result["errors"].append(_error(exc))
    if group_exists:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            result["kill_sent"] = True
        except ProcessLookupError:
            pass
        except OSError as exc:
            result["errors"].append(_error(exc))
    if not result["leader_reaped"]:
        try:
            process.wait(timeout=TERMINATION_GRACE_SECONDS)
            result["leader_reaped"] = True
        except (subprocess.TimeoutExpired, OSError) as exc:
            result["errors"].append(_error(exc))
    return result


def _parse_envelope(raw: bytes) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    def reject_constant(value: str):
        raise ValueError(f"Nonstandard JSON constant: {value}")

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def finite_float(value: str):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("JSON number exceeds finite float range")
        return number

    def verify_strings(value):
        if isinstance(value, str):
            value.encode("utf-8")
        elif isinstance(value, dict):
            for key, child in value.items():
                verify_strings(key)
                verify_strings(child)
        elif isinstance(value, list):
            for child in value:
                verify_strings(child)

    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant,
                           parse_float=finite_float, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError("CLI output must be one entire JSON object")
        verify_strings(value)
        return value, None
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, _error(exc)


def invoke_cli(request: AgentRequest, output: Path | str, cap_usd: float,
               timeout_seconds: float = 90.0, executable: str = "claude") -> dict[str, Any]:
    """Invoke once and retain all output without normalizing usage or billing.

    ``output`` must be new or empty. An exclusive started.json marker is created
    before process launch. Existing evidence is never overwritten or resumed.
    Validation failures happen before launch; subprocess failures return raw
    evidence for the caller's fail-stop ledger. KeyboardInterrupt/SystemExit are
    re-raised after group cancellation and result preservation.
    """
    _positive_bounded(cap_usd, "cap_usd", 1.0)
    _positive_bounded(timeout_seconds, "timeout_seconds", 90.0)
    prompt = request.prompt()  # Validates that allowed IDs equal presented IDs.
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(output.iterdir()):
        raise FileExistsError(f"Refusing to reuse a CLI attempt directory: {output}")
    settings_path = output / "settings.json"
    command = build_command(cap_usd, settings_path, executable)
    metadata = {"started_at": datetime.now(timezone.utc).isoformat(), "model": MODEL,
                "effort": EFFORT, "configured_cap_usd": cap_usd,
                "configured_timeout_seconds": timeout_seconds,
                "request_sha256": _sha(prompt), "context_sha256": _sha(request.context_text),
                "system_prompt_sha256": _sha(SYSTEM_PROMPT), "schema_sha256": _sha(_json(PLAN_SCHEMA)),
                "settings_sha256": _sha(_json(ISOLATION_SETTINGS)),
                "harness_attempts": 1, "harness_retries": 0, "fallback": False,
                "billing_note": "Configured CLI budget is soft; raw reported costs must be reconciled by the caller.",
                "internal_turns_note": "One harness invocation may contain multiple provider turns or internal retries."}
    _write_new(output / "started.json", _json(metadata) + "\n")
    _write_new(settings_path, _json(ISOLATION_SETTINGS))
    _write_new(output / "prompt.json", prompt)
    _write_new(output / "system-prompt.txt", SYSTEM_PROMPT)
    _write_new(output / "schema.json", _json(PLAN_SCHEMA))
    _write_new(output / "command.json", _json(command) + "\n")
    cwd = output / "cwd"
    cwd.mkdir(mode=0o700)
    result: dict[str, Any] = {**metadata, "argv": command, "cwd": str(cwd),
                              "process_started": False, "returncode": None,
                              "timed_out": False, "envelope": None,
                              "parse_error": None, "error": None, "cancellation": None}
    process = None
    interrupted: BaseException | None = None
    started = time.monotonic()
    # Binary logs preserve exact bytes, including malformed/partial responses.
    with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
        os.chmod(output / "stdout.log", 0o600)
        os.chmod(output / "stderr.log", 0o600)
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       text=True, encoding="utf-8", errors="strict", cwd=cwd,
                                       env=_client_environment(), start_new_session=True)
            result["process_started"] = True
            process.communicate(input=prompt, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            result["timed_out"] = True
            result["error"] = _error(exc)
            if process is not None:
                result["cancellation"] = _cancel_process_group(process)
        except BaseException as exc:
            result["error"] = _error(exc)
            if process is not None:
                result["cancellation"] = _cancel_process_group(process)
            if not isinstance(exc, Exception):
                interrupted = exc
        finally:
            result["returncode"] = process.returncode if process is not None else None
            result["elapsed_seconds"] = time.monotonic() - started
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())
    raw_stdout, raw_stderr = (output / "stdout.log").read_bytes(), (output / "stderr.log").read_bytes()
    result["stdout_sha256"], result["stderr_sha256"] = _sha(raw_stdout), _sha(raw_stderr)
    result["stdout_bytes"], result["stderr_bytes"] = len(raw_stdout), len(raw_stderr)
    result["envelope"], result["parse_error"] = _parse_envelope(raw_stdout)
    if result["error"] is None and result["returncode"] != 0:
        result["error"] = {"type": "CLIExitError", "message": f"CLI exited with status {result['returncode']}"}
    if result["error"] is None and result["envelope"] is not None and result["envelope"].get("is_error"):
        result["error"] = {"type": "ProviderError", "message": "CLI returned an error envelope; raw details and billing are preserved"}
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_new(output / "result.json", _json(result) + "\n")
    if interrupted is not None:
        raise interrupted
    return result
