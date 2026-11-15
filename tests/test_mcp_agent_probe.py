import json

from scripts import mcp_agent_probe as probe


def test_client_prompt_has_source_data_but_no_gold_answers_or_recipe():
    prompt = probe.prompt("client-test")
    assert probe.CSV in prompt
    for answer in ("30800", "31700", "10800", "11700"):
        assert answer not in prompt
        assert answer not in probe.SYSTEM
    for operation in ("gross_by_region", "refunds_by_region", "net_by_region", "company_total"):
        assert operation not in prompt
    assert "1.20" in prompt and "1.30" in prompt


def test_cli_allows_only_explicit_five_mcp_tools(tmp_path):
    command = probe.command(tmp_path)
    assert command[command.index("--tools") + 1] == ""
    assert set(command[command.index("--allowedTools") + 1].split(",")) == set(probe.TOOLS)
    assert len(probe.TOOLS) == 5
    assert command[command.index("--mcp-config") + 1] == str(tmp_path / "mcp-config.json")
    assert "--strict-mcp-config" in command and "--safe-mode" in command
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert command[command.index("--model") + 1] == "claude-fable-5-2"
    assert command[command.index("--max-budget-usd") + 1] == "4"
    assert command[command.index("--output-format") + 1] == "stream-json"


def test_stream_keeps_actual_tool_arguments_responses_failures_and_usage(tmp_path):
    body = {"workspace": "client-test", "source_versions": [], "executed_count": 0}
    events = [
        {"type": "system", "message": "diagnostic status"},
        {"type": "system", "message": {"content": ["diagnostic", None]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "u1", "name": probe.TOOLS[0],
             "input": {"workspace": "client-test", "csv_text": probe.CSV}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "u1", "is_error": False,
             "content": [{"type": "text", "text": json.dumps(body)}]}]}},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "u2", "name": probe.TOOLS[2], "input": {"workspace": "client-test"}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "u2", "is_error": True, "content": "Plan rejected"}]}},
        {"type": "result", "subtype": "success", "modelUsage": {probe.MODEL: {"inputTokens": 10}}, "total_cost_usd": 0.1},
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n")
    transcript = probe.parse_events(path)
    assert transcript["calls"][0]["input"]["csv_text"] == probe.CSV
    assert transcript["calls"][0]["response"]["body"] == body
    assert transcript["calls"][1]["response"]["is_error"] is True
    assert transcript["calls"][1]["response"]["body"] is None
    assert transcript["final"]["total_cost_usd"] == 0.1


def test_body_parser_handles_mcp_envelopes_without_extracting_prose():
    body = {"workspace": "client-test", "artifacts": []}
    assert probe.decoded_body({"structuredContent": body}) == body
    assert probe.decoded_body(json.dumps([{"type": "text", "text": json.dumps(body)}])) == body
    assert probe.decoded_body("Here is the result: " + json.dumps(body)) is None


def test_oracle_uses_semantic_paths_not_model_chosen_keys():
    claims = [
        {"key": "arbitrary1", "path": ["usd_cents"], "value": 30800, "saved_value": 30800},
        {"key": "arbitrary2", "path": ["regions", "NORTH", "usd_cents"], "value": None, "saved_value": 10800},
        {"key": "arbitrary3", "path": ["regions", "NORTH", "tickets"], "value": 3, "saved_value": 3},
    ]
    assert probe.metric_values(claims) == {"company_usd_cents": 30800, "north_usd_cents": None, "north_tickets": 3}
    assert probe.metric_values(claims, historical=True)["north_usd_cents"] == 10800


def test_equivalent_csv_and_rates_are_accepted_without_accepting_changed_data():
    assert probe.csv_rows(probe.CSV.rstrip("\n").replace("\n", "\r\n")) == probe.csv_rows(probe.CSV)
    assert probe.csv_rows(probe.CSV.replace("10000", "010000")) == probe.csv_rows(probe.CSV)
    assert probe.csv_rows(probe.CSV.replace("10000", "10001")) != probe.csv_rows(probe.CSV)
    assert probe.csv_rows(probe.CSV + "c,NORTH,EUR,1,0,0\n") != probe.csv_rows(probe.CSV)
    assert probe.rate_matches({"EUR": "1.2", "USD": "1.0"}, "1.20")
    assert not probe.rate_matches({"EUR": "1.3"}, "1.20")
    assert not probe.rate_matches({"EUR": "1.2", "GBP": "1"}, "1.20")
