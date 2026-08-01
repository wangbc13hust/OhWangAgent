from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


PROVIDER_PRESETS = {
    "zhipu": {
        "env": "ZHIPU_API_KEY",
        "default_model": "glm-5.2",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "context_window": 128_000,
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5-20250929",
        "base_url": None,
        "context_window": 200_000,
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "base_url": None,
        "context_window": 128_000,
    },
    "deepseek": {
        "env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "context_window": 128_000,
    },
    "kimi": {
        "env": "MOONSHOT_API_KEY",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
        "context_window": 8_192,
    },
    "qwen": {
        "env": "DASHSCOPE_API_KEY",
        "default_model": "qwen-max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "context_window": 32_000,
    },
}


@dataclass
class Config:
    provider: str = "zhipu"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 16384
    auto_approve: bool = False
    plan: bool = False
    compact_threshold: Optional[int] = None
    workdir: str = "."
    context_window: Optional[int] = None

    def resolve(self) -> "Config":
        preset = PROVIDER_PRESETS.get(self.provider, {})
        if not self.model:
            self.model = preset.get("default_model", "")
        if not self.api_key:
            env_var = preset.get("env", "")
            self.api_key = os.environ.get(env_var, "")
        if not self.base_url:
            self.base_url = preset.get("base_url") or ""
        if self.context_window is None:
            self.context_window = preset.get("context_window")
        return self
