"""Pydantic AI model factory for an OpenAI-compatible endpoint.

Framework-light: this module depends on pydantic-ai only and exposes a pure
`build_model(...)` factory. Orchestration layers (api/mcp) inject settings;
`gotit.core` never imports `gotit.api`.
"""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


def build_model(*, base_url: str, api_key: str, model_name: str) -> OpenAIChatModel:
    """Construct an OpenAI-compatible chat model from explicit config."""
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider)
