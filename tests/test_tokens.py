from ohwang.services import tokens
from ohwang.services.compact import Compactor
from ohwang.services.tokens import estimate_messages_tokens, estimate_text_tokens


# --- Heuristic fallback path (tiktoken unavailable / BPE download fails) --

def test_text_estimate_heuristic(monkeypatch):
    monkeypatch.setattr(tokens, "_tiktoken", None)
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("abcd") == 1
    assert estimate_text_tokens("a" * 100) == 25


def test_cjk_text_estimated_denser_heuristic(monkeypatch):
    monkeypatch.setattr(tokens, "_tiktoken", None)
    # CJK counts ~1 char/token instead of ~4, so Chinese prompts are not
    # grossly underestimated for the compaction trigger.
    assert estimate_text_tokens("中" * 4) == 4
    assert estimate_text_tokens("abcd" * 100) == 100


def test_heuristic_fallback_ascii(monkeypatch):
    monkeypatch.setattr(tokens, "_tiktoken", None)
    text = "hello world this is a test"  # 26 chars -> 26 // 4 = 6
    assert estimate_text_tokens(text) == 6


# --- tiktoken path (encoding loads, exact BPE counts) ---------------------

def test_estimate_english_text():
    text = "Hello world, this is a token counting test."
    n = estimate_text_tokens(text)
    assert n > 0
    # BPE is tighter than 1 char/token for ordinary English prose.
    assert n <= len(text)


def test_estimate_cjk_text():
    n = estimate_text_tokens("你好，世界。这是一个精确计数的测试。")
    assert n > 0


def test_estimate_model_param_does_not_break():
    n = estimate_text_tokens("Hello", model="gpt-4o")
    assert n > 0


def test_empty_text_is_zero():
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("", model="gpt-4o") == 0


# --- message-level estimation ---------------------------------------------

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


def test_estimate_messages_with_model_nonnegative():
    msgs = [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {"role": "assistant", "content": "hi"},
    ]
    assert estimate_messages_tokens(msgs, model="gpt-4o") >= 0


def test_estimate_messages_includes_overhead():
    msgs = [{"role": "user", "content": [{"type": "text", "text": ""}]}]
    floor = tokens._PER_MESSAGE_OVERHEAD + tokens._PER_BLOCK_OVERHEAD
    assert estimate_messages_tokens(msgs) >= floor


# --- compactor threshold behavior with model-aware token estimates ---------

def test_should_compact_not_triggered_with_model():
    compactor = Compactor(threshold_tokens=100_000)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "x"}]}] * 20
    assert compactor.should_compact(msgs, model="gpt-4o") is False


def test_should_compact_triggered_with_model():
    compactor = Compactor(threshold_tokens=50)
    msgs = [{"role": "user", "content": [{"type": "text", "text": "word " * 200}]}] * 10
    assert compactor.should_compact(msgs, model="gpt-4o") is True
