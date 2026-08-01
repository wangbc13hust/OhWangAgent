import json

from ohwang.providers.openai_provider import _convert_messages, _convert_tools


def test_convert_plain_string_message():
    out = _convert_messages([{"role": "user", "content": "hi"}])
    assert out == [{"role": "user", "content": "hi"}]


def test_convert_assistant_text_and_tool_calls():
    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "let me check"},
                {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
            ],
        }
    ]
    out = _convert_messages(msgs)
    assert len(out) == 1
    msg = out[0]
    assert msg["role"] == "assistant"
    assert msg["content"] == "let me check"
    tc = msg["tool_calls"][0]
    assert tc["id"] == "t1"
    assert tc["function"]["name"] == "bash"
    assert json.loads(tc["function"]["arguments"]) == {"command": "ls"}


def test_convert_assistant_tool_calls_only():
    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "grep", "input": {"pattern": "x"}}
            ],
        }
    ]
    out = _convert_messages(msgs)
    msg = out[0]
    assert msg["content"] is None
    assert msg["tool_calls"][0]["function"]["name"] == "grep"


def test_convert_user_tool_result_and_text():
    msgs = [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": "output",
                    "is_error": False,
                },
                {"type": "text", "text": "continue"},
            ],
        }
    ]
    out = _convert_messages(msgs)
    assert out[0] == {"role": "tool", "tool_call_id": "t1", "content": "output"}
    assert out[1] == {"role": "user", "content": [{"type": "text", "text": "continue"}]}


def test_convert_skips_non_list_content():
    out = _convert_messages([{"role": "user", "content": None}])
    assert out == []


def test_convert_tools_wraps_schema():
    specs = [
        {
            "name": "bash",
            "description": "run",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
        }
    ]
    out = _convert_tools(specs)
    assert out[0]["type"] == "function"
    f = out[0]["function"]
    assert f["name"] == "bash"
    assert f["description"] == "run"
    assert f["parameters"] == specs[0]["input_schema"]


def test_convert_tools_default_schema_when_missing():
    specs = [{"name": "x", "description": "", "input_schema": None}]
    out = _convert_tools(specs)
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}
