from ohwang.services.compact import microcompact


def _tool_result(content: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": content}
        ],
    }


def test_microcompact_trims_oversized_tool_result():
    msgs = [_tool_result("x" * 50_000)]
    freed = microcompact(msgs, max_tool_result_chars=30_000)
    block = msgs[0]["content"][0]
    assert "Old tool result content cleared" in block["content"]
    assert block["content"] != "x" * 50_000
    assert freed == 50_000 - len(block["content"])


def test_microcompact_leaves_small_untouched():
    msgs = [_tool_result("hi")]
    assert microcompact(msgs, max_tool_result_chars=30_000) == 0
    assert msgs[0]["content"][0]["content"] == "hi"


def test_microcompact_returns_total_freed():
    big1 = "a" * 40_000
    big2 = "b" * 60_000
    small = "ok"
    msgs = [_tool_result(big1), _tool_result(small), _tool_result(big2)]
    freed = microcompact(msgs, max_tool_result_chars=30_000)
    # both oversized blocks were trimmed, the small one left alone
    trimmed = [b["content"] for m in msgs for b in m["content"] if "Old tool result" in b["content"]]
    assert len(trimmed) == 2
    kept = [b["content"] for m in msgs for b in m["content"] if "Old tool result" not in b["content"]]
    assert kept == [small]
    assert freed == (40_000 - len(trimmed[0])) + (60_000 - len(trimmed[1]))


def test_microcompact_ignores_non_tool_result_blocks():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "z" * 50_000}]},
    ]
    assert microcompact(msgs, max_tool_result_chars=30_000) == 0
    assert len(msgs[0]["content"][0]["text"]) == 50_000
