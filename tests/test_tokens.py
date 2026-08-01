from ohwang.services.tokens import estimate_messages_tokens, estimate_text_tokens


def test_text_estimate():
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcd") == 1
    assert estimate_text_tokens("a" * 100) == 25


def test_messages_estimate_positive_and_growing():
    m1 = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    m2 = m1 + [{"role": "assistant", "content": [{"type": "text", "text": "hi there"}]}]
    assert estimate_messages_tokens(m1) > 0
    assert estimate_messages_tokens(m2) > estimate_messages_tokens(m1)


def test_tool_use_and_result_counted():
    msgs = [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "1", "name": "file_read", "input": {"file_path": "x"}}
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "1", "content": "data"}],
        },
    ]
    assert estimate_messages_tokens(msgs) > 0
