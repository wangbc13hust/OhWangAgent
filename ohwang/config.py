from __future__ import annotations

import os
from dataclasses import dataclass


PROVIDER_PRESETS = {
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-5-20250929",
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
    },
}


@dataclass
class Config:
    provider: str = "anthropic"
    model: str = ""
    api_key: str = ""
    max_tokens: int = 8192
    auto_approve: bool = False
    workdir: str = "."

    def resolve(self) -> "Config":
        preset = PROVIDER_PRESETS.get(self.provider, {})
        if not self.model:
            self.model = preset.get("default_model", "")
        if not self.api_key:
            env_var = preset.get("env", "")
            self.api_key = os.environ.get(env_var, "")
        return self
