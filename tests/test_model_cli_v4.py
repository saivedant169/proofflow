"""No paid calls: every subprocess and signal in these tests is a test double."""
import hashlib
import json
import signal
import subprocess
from pathlib import Path

import pytest

from proofflow.agent import AgentProtocolError, AgentRequest, PLAN_SCHEMA, SYSTEM_PROMPT
from proofflow.eval import model_cli_v4 as cli


def request():
    return AgentRequest("Revalidate after correction", ("source:fx@old",),
                        '{"id":"artifact:revenue@old","inputs":["source:fx@old"]}',
                        ("artifact:revenue@old",))


def envelope(**changes):
    return {"is_error": False, "num_turns": 2, "structured_output": {
        "selected_ids": ["artifact:revenue@old"], "rationale": "Direct dependency", "abstain": False},
        "modelUsage": {"claude-fable-5-2": {"inputTokens": 15, "cacheReadInputTokens": 300,
            "cacheCreationInputTokens": 200, "outputTokens": 100, "costUSD": 0.01}},
        "total_cost_usd": 0.01, **changes}


class FakeProcess:
    pid = 123456

    def __init__(self, kwargs, *, raw=None, stderr=b"", code=0, communicate_error=None, waits=None):
        self.kwargs = kwargs
        self.raw = json.dumps(envelope()).encode() if raw is None else raw
        self.stderr = stderr
        self.code = code
        self.communicate_error = communicate_error
        self.waits = list(waits or [-15])
        self.returncode = None
        self.communications = []
        self.wait_timeouts = []

    def communicate(self, **kwargs):
        self.communications.append(kwargs)
        self.kwargs["stdout"].write(self.raw)
        self.kwargs["stderr"].write(self.stderr)
        if self.communicate_error:
            raise self.communicate_error
        self.returncode = self.code
        return None, None

    def wait(self, *, timeout):
        self.wait_timeouts.append(timeout)
        value = self.waits.pop(0)
        if isinstance(value, BaseException):
            raise value
        self.returncode = value
        return value


def fake_launch(monkeypatch, *, group_survives_term=False, launch_error=None, **config):
    seen = {"launches": [], "signals": [], "process": None}
    group = {"alive": True}

    def launch(argv, **kwargs):
        seen["launches"].append((argv, kwargs))
        if launch_error:
            raise launch_error
        seen["process"] = FakeProcess(kwargs, **config)
        return seen["process"]

    def killpg(pid, sig):
        seen["signals"].append((pid, sig))
        if sig == signal.SIGTERM and not group_survives_term:
            group["alive"] = False
        if sig == signal.SIGKILL:
            group["alive"] = False
        if sig == 0 and not group["alive"]:
            raise ProcessLookupError()

    monkeypatch.setattr(cli.subprocess, "Popen", launch)
    monkeypatch.setattr(cli.os, "killpg", killpg)
    return seen


def test_command_freezes_prompt_model_and_isolation(tmp_path):
    command = cli.build_command(0.25, tmp_path / "settings.json", executable="local claude")
    assert command[0] == "local claude"
    assert command[command.index("--model") + 1] == "claude-fable-5-2"
    assert command[command.index("--effort") + 1] == "high"
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--setting-sources") + 1] == ""
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert command[command.index("--system-prompt") + 1] == SYSTEM_PROMPT
    assert json.loads(command[command.index("--json-schema") + 1]) == PLAN_SCHEMA
    for flag in ("--safe-mode", "--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands", "--no-chrome"):
        assert flag in command
    assert "--fallback-model" not in command


@pytest.mark.parametrize("cap", [True, False, 0, -1, 1.001, float("nan"), float("inf"), "0.5", None])
def test_invalid_cap_never_launches(monkeypatch, tmp_path, cap):
    seen = fake_launch(monkeypatch)
    with pytest.raises(ValueError):
        cli.invoke_cli(request(), tmp_path / "attempt", cap)
    assert seen["launches"] == []
    assert not (tmp_path / "attempt").exists()


@pytest.mark.parametrize("timeout", [True, 0, -1, 90.01, float("nan"), float("inf")])
def test_invalid_timeout_never_launches(monkeypatch, tmp_path, timeout):
    seen = fake_launch(monkeypatch)
    with pytest.raises(ValueError):
        cli.invoke_cli(request(), tmp_path / "attempt", 0.5, timeout_seconds=timeout)
    assert seen["launches"] == []


def test_invalid_request_never_creates_attempt(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch)
    invalid = AgentRequest("Task", (), '{"id":"visible"}', ("hidden",))
    with pytest.raises(AgentProtocolError):
        cli.invoke_cli(invalid, tmp_path / "attempt", 0.5)
    assert seen["launches"] == []
    assert not (tmp_path / "attempt").exists()


def test_success_retains_exact_raw_evidence_and_no_environment_dump(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFFLOW_HYDRA_TOKEN", "fixture-hydra-secret")
    monkeypatch.setenv("PROOFFLOW_HYDRA_TOKEN_FILE", "/fixture/secret-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-auth-secret")
    raw = ("  " + json.dumps(envelope()) + "\n").encode()
    seen = fake_launch(monkeypatch, raw=raw, stderr=b"diagnostic\n")
    path = tmp_path / "attempt"
    result = cli.invoke_cli(request(), path, 0.5)
    assert len(seen["launches"]) == 1
    argv, kwargs = seen["launches"][0]
    assert kwargs["start_new_session"] is True
    assert "shell" not in kwargs
    assert kwargs["cwd"] == path / "cwd"
    assert list((path / "cwd").iterdir()) == []
    assert "PROOFFLOW_HYDRA_TOKEN" not in kwargs["env"]
    assert "PROOFFLOW_HYDRA_TOKEN_FILE" not in kwargs["env"]
    assert kwargs["env"]["ANTHROPIC_API_KEY"] == "fixture-auth-secret"
    assert seen["process"].communications == [{"input": request().prompt(), "timeout": 90.0}]
    assert result["envelope"] == envelope()
    assert result["envelope"]["num_turns"] == 2
    assert result["returncode"] == 0
    assert result["error"] is None and result["parse_error"] is None
    assert (path / "stdout.log").read_bytes() == raw
    assert result["stdout_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["stderr_sha256"] == hashlib.sha256(b"diagnostic\n").hexdigest()
    assert (path / "prompt.json").read_text() == request().prompt()
    assert json.loads((path / "settings.json").read_text()) == cli.ISOLATION_SETTINGS
    saved = (path / "result.json").read_text()
    assert "fixture-auth-secret" not in saved and "fixture-hydra-secret" not in saved
    assert json.loads(saved) == result
    assert result["request_sha256"] == hashlib.sha256(request().prompt().encode()).hexdigest()
    assert result["context_sha256"] == hashlib.sha256(request().context_text.encode()).hexdigest()
    assert seen["signals"] == []


def test_attempt_directory_is_never_reused(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch)
    path = tmp_path / "attempt"
    path.mkdir()
    cli.invoke_cli(request(), path, 0.5)
    with pytest.raises(FileExistsError):
        cli.invoke_cli(request(), path, 0.5)
    assert len(seen["launches"]) == 1
    assert (path / "started.json").is_file()


def test_arbitrary_existing_evidence_also_prevents_launch(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch)
    path = tmp_path / "attempt"
    path.mkdir()
    (path / "stdout.log").write_text("interrupted evidence")
    with pytest.raises(FileExistsError):
        cli.invoke_cli(request(), path, 0.5)
    assert seen["launches"] == []
    assert (path / "stdout.log").read_text() == "interrupted evidence"


def test_launch_failure_is_recorded_without_retry_or_invented_cost(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch, launch_error=FileNotFoundError("fixture CLI missing"))
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert len(seen["launches"]) == 1
    assert result["process_started"] is False
    assert result["returncode"] is None
    assert result["error"]["type"] == "FileNotFoundError"
    assert result["envelope"] is None
    assert "cost_usd" not in result
    assert (tmp_path / "attempt/result.json").is_file()


@pytest.mark.parametrize("raw", [b"not json", b"[]", b'prefix {"total_cost_usd":1}',
    b'{"a":1} trailing', b'{"total_cost_usd":1,"total_cost_usd":0}',
    b'{"usage":{"inputTokens":1,"inputTokens":0}}', b'{"total_cost_usd":NaN}',
    b'{"total_cost_usd":Infinity}', b'{"total_cost_usd":1e309}', b'\xff', b'{"x":"\\ud800"}'])
def test_invalid_envelope_stays_raw_and_never_becomes_a_partial_plan(monkeypatch, tmp_path, raw):
    fake_launch(monkeypatch, raw=raw)
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert result["envelope"] is None
    assert result["parse_error"] is not None
    assert (tmp_path / "attempt/stdout.log").read_bytes() == raw
    assert result["stdout_sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("code,is_error,error_type", [(2, True, "CLIExitError"), (0, True, "ProviderError")])
def test_provider_failure_keeps_all_usage_for_caller_ledger(monkeypatch, tmp_path, code, is_error, error_type):
    payload = envelope(is_error=is_error, subtype="fixture_error", total_cost_usd=0.75)
    seen = fake_launch(monkeypatch, raw=json.dumps(payload).encode(), code=code)
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert len(seen["launches"]) == 1
    assert result["error"]["type"] == error_type
    assert result["envelope"] == payload
    assert result["envelope"]["total_cost_usd"] == 0.75  # Never clip to the configured cap.


def test_timeout_cancels_group_and_preserves_partial_bytes(monkeypatch, tmp_path):
    raw = b'{"type":"partial",'
    seen = fake_launch(monkeypatch, raw=raw, group_survives_term=True,
        communicate_error=subprocess.TimeoutExpired("fixture", 90),
        waits=[subprocess.TimeoutExpired("fixture", 2), -9])
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert result["timed_out"] is True
    assert result["process_started"] is True
    assert result["returncode"] == -9
    assert result["error"]["type"] == "TimeoutExpired"
    assert result["envelope"] is None
    assert result["cancellation"] == {"term_sent": True, "kill_sent": True, "leader_reaped": True, "errors": []}
    assert seen["signals"] == [(123456, signal.SIGTERM), (123456, 0), (123456, signal.SIGKILL)]
    assert seen["process"].wait_timeouts == [2.0, 2.0]
    assert (tmp_path / "attempt/stdout.log").read_bytes() == raw
    assert len(seen["launches"]) == 1


def test_leader_exit_does_not_leave_surviving_group_unhandled(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch, group_survives_term=True,
        communicate_error=subprocess.TimeoutExpired("fixture", 90), waits=[0])
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert result["cancellation"]["leader_reaped"] is True
    assert result["cancellation"]["kill_sent"] is True
    assert seen["signals"][-1] == (123456, signal.SIGKILL)
    assert seen["process"].wait_timeouts == [2.0]


def test_group_that_exited_on_term_needs_no_kill(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch, communicate_error=subprocess.TimeoutExpired("fixture", 90), waits=[-15])
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert result["cancellation"]["term_sent"] is True
    assert result["cancellation"]["kill_sent"] is False
    assert result["cancellation"]["leader_reaped"] is True
    assert seen["signals"] == [(123456, signal.SIGTERM), (123456, 0)]


def test_communication_error_also_cancels_without_retry(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch, communicate_error=BrokenPipeError("fixture broken pipe"), waits=[-15])
    result = cli.invoke_cli(request(), tmp_path / "attempt", 0.5)
    assert result["error"]["type"] == "BrokenPipeError"
    assert result["timed_out"] is False
    assert result["cancellation"]["leader_reaped"] is True
    assert len(seen["launches"]) == 1


def test_interrupt_preserves_marker_and_result_then_propagates(monkeypatch, tmp_path):
    seen = fake_launch(monkeypatch, communicate_error=KeyboardInterrupt(), waits=[-15])
    path = tmp_path / "attempt"
    with pytest.raises(KeyboardInterrupt):
        cli.invoke_cli(request(), path, 0.5)
    result = json.loads((path / "result.json").read_text())
    assert result["error"]["type"] == "KeyboardInterrupt"
    assert result["cancellation"]["leader_reaped"] is True
    with pytest.raises(FileExistsError):
        cli.invoke_cli(request(), path, 0.5)
    assert len(seen["launches"]) == 1
