from __future__ import annotations

import os
from dataclasses import dataclass


PROVIDER_PRESETS = {
    "zhipu": {
        "env": "ZHIPU_API_KEY",
        "default_model": "glm-5.2",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5-20250929",
        "base_url": None,
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "base_url": None,
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
    compact_threshold: int = 100_000
    workdir: str = "."

    def resolve(self) -> "Config":
        preset = PROVIDER_PRESETS.get(self.provider, {})
        if not self.model:
            self.model = preset.get("default_model", "")
        if not self.api_key:
            env_var = preset.get("env", "")
            self.api_key = os.environ.get(env_var, "")
        if not self.base_url:
            self.base_url = preset.get("base_url") or ""
        return self
