from ohwang.config import Config
from ohwang.services.window import DEFAULT_CONTEXT_WINDOW, effective_context_window


def test_effective_window_from_preset():
    config = Config(provider="deepseek").resolve()
    assert effective_context_window(config) == 128_000


def test_effective_window_config_override():
    # explicit config wins over the provider preset
    config = Config(provider="deepseek", context_window=64_000).resolve()
    assert effective_context_window(config) == 64_000


def test_effective_window_env_override(monkeypatch):
    monkeypatch.setenv("OHWANG_MAX_CONTEXT_TOKENS", "32000")
    config = Config(provider="deepseek", context_window=128_000).resolve()
    assert effective_context_window(config) == 32_000


def test_effective_window_default():
    # unknown provider / no preset window -> fixed default
    config = Config(provider="unknown_provider").resolve()
    assert effective_context_window(config) == DEFAULT_CONTEXT_WINDOW
