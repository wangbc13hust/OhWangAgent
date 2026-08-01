from __future__ import annotations

from typing import Optional

from .base import BaseProvider
from ..config import Config


def create_provider(config: Config, base_url: Optional[str] = None) -> BaseProvider:
    if config.provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(config.api_key, config.model)
    if config.provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(config.api_key, config.model, base_url=base_url)
    raise ValueError(f"Unknown provider: {config.provider!r}")


__all__ = ["BaseProvider", "create_provider"]
