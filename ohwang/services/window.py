from __future__ import annotations

import os


DEFAULT_CONTEXT_WINDOW = 128_000


def effective_context_window(config) -> int:
    """Resolve the model context window, mirroring Claude Code's
    getContextWindowForModel(): env override wins over config, which wins
    over the provider preset, which wins over a fixed default.
    """
    env = os.environ.get("OHWANG_MAX_CONTEXT_TOKENS")
    if env and env.strip().isdigit():
        return int(env)
    return config.context_window or DEFAULT_CONTEXT_WINDOW
