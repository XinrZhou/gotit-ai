"""Pydantic AI model factory for an OpenAI-compatible endpoint.

Framework-light: this module depends on pydantic-ai only and exposes a pure
`build_model(...)` factory plus `resolve_llm_binding` for per-agent overlays.
Orchestration layers (api/mcp) inject settings; `gotit.core` never imports
`gotit.api`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


@dataclass(frozen=True)
class LlmBinding:
    """Resolved OpenAI-compatible endpoint + model id."""

    base_url: str
    api_key: str
    model_name: str


def _nonempty(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _pick(cfg: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        found = _nonempty(cfg.get(key))
        if found is not None:
            return found
    return None


def _resolve_api_key(
    cfg: Mapping[str, Any],
    *,
    getenv: Callable[[str], str | None],
) -> str | None:
    literal = _pick(cfg, "api_key")
    if literal is not None:
        return literal
    env_name = _pick(cfg, "api_key_env")
    if env_name is None:
        return None
    return _nonempty(getenv(env_name))


def resolve_llm_binding(
    llm_config: Mapping[str, Any] | None,
    *,
    default_base_url: str,
    default_api_key: str,
    default_model: str,
    overlay: Mapping[str, Any] | None = None,
    getenv: Callable[[str], str | None] | None = None,
) -> LlmBinding:
    """Merge per-agent `llm_config` onto global defaults.

    Precedence (high → low) for each field:
      identity `llm_config` → `overlay` (e.g. CRITIC_* env) → global defaults.

    Supported `llm_config` / overlay keys:
      - `model` or `model_name`
      - `base_url`
      - `api_key` (literal) or `api_key_env` (env var name; preferred in DB)
    """
    getenv_fn = getenv or os.getenv
    cfg = dict(llm_config or {})
    over = dict(overlay or {})

    model_name = (
        _pick(cfg, "model", "model_name")
        or _pick(over, "model", "model_name")
        or default_model
    )
    base_url = _pick(cfg, "base_url") or _pick(over, "base_url") or default_base_url
    api_key = (
        _resolve_api_key(cfg, getenv=getenv_fn)
        or _resolve_api_key(over, getenv=getenv_fn)
        or default_api_key
        or ""
    )
    return LlmBinding(base_url=base_url, api_key=api_key, model_name=model_name)


def build_model(*, base_url: str, api_key: str, model_name: str) -> OpenAIChatModel:
    """Construct an OpenAI-compatible chat model from explicit config."""
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider)


def build_model_from_binding(binding: LlmBinding) -> OpenAIChatModel:
    return build_model(
        base_url=binding.base_url,
        api_key=binding.api_key,
        model_name=binding.model_name,
    )
