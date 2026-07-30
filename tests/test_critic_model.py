"""Critic may bind a distinct LLM via identity.llm_config / CRITIC_* env."""

from __future__ import annotations

from gotit.api.deps import get_critic_model, get_model, resolve_critic_binding
from gotit.api.settings import Settings, get_settings
from gotit.core.agents.llm import resolve_llm_binding


def test_resolve_llm_binding_falls_back_to_defaults() -> None:
    binding = resolve_llm_binding(
        {},
        default_base_url="https://api.example/v1",
        default_api_key="global-key",
        default_model="global-model",
    )
    assert binding.model_name == "global-model"
    assert binding.base_url == "https://api.example/v1"
    assert binding.api_key == "global-key"


def test_resolve_llm_binding_identity_wins_over_overlay() -> None:
    binding = resolve_llm_binding(
        {"model": "critic-special", "base_url": "https://critic.example/v1"},
        default_base_url="https://api.example/v1",
        default_api_key="global-key",
        default_model="global-model",
        overlay={"model": "env-critic", "base_url": "https://env.example/v1"},
    )
    assert binding.model_name == "critic-special"
    assert binding.base_url == "https://critic.example/v1"


def test_resolve_llm_binding_overlay_when_identity_empty() -> None:
    binding = resolve_llm_binding(
        {},
        default_base_url="https://api.example/v1",
        default_api_key="global-key",
        default_model="global-model",
        overlay={"model": "env-critic"},
    )
    assert binding.model_name == "env-critic"
    assert binding.api_key == "global-key"


def test_resolve_llm_binding_api_key_env() -> None:
    calls: dict[str, str] = {"CRITIC_SECRET": "from-env"}

    def fake_getenv(name: str) -> str | None:
        return calls.get(name)

    binding = resolve_llm_binding(
        {"model": "m2", "api_key_env": "CRITIC_SECRET"},
        default_base_url="https://api.example/v1",
        default_api_key="global-key",
        default_model="global-model",
        getenv=fake_getenv,
    )
    assert binding.api_key == "from-env"
    assert binding.model_name == "m2"


def test_resolve_critic_binding_uses_settings_overlay() -> None:
    settings = Settings(
        llm_base_url="https://api.example/v1",
        llm_api_key="global-key",
        llm_model="axiom-shared",
        critic_model="critic-alt",
        critic_base_url="",
        critic_api_key="",
    )
    binding = resolve_critic_binding({}, settings=settings)
    assert binding.model_name == "critic-alt"
    assert binding.api_key == "global-key"

    # identity wins
    binding2 = resolve_critic_binding({"model": "db-critic"}, settings=settings)
    assert binding2.model_name == "db-critic"


def test_get_critic_model_differs_from_global_when_configured(
    monkeypatch: object,
) -> None:
    get_settings.cache_clear()
    get_model.cache_clear()
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example/v1")  # type: ignore[attr-defined]
    monkeypatch.setenv("LLM_API_KEY", "global-key")  # type: ignore[attr-defined]
    monkeypatch.setenv("LLM_MODEL", "axiom-shared")  # type: ignore[attr-defined]
    monkeypatch.setenv("CRITIC_MODEL", "critic-alt")  # type: ignore[attr-defined]
    get_settings.cache_clear()
    get_model.cache_clear()

    try:
        axiom = get_model()
        critic = get_critic_model({})
        assert axiom.model_name == "axiom-shared"
        assert critic.model_name == "critic-alt"
        assert critic.model_name != axiom.model_name

        # no identity / no CRITIC_* → same as global
        monkeypatch.delenv("CRITIC_MODEL", raising=False)  # type: ignore[attr-defined]
        get_settings.cache_clear()
        critic_default = get_critic_model({})
        assert critic_default.model_name == "axiom-shared"
        assert critic_default is get_model()
    finally:
        get_settings.cache_clear()
        get_model.cache_clear()


def test_get_critic_model_from_identity_llm_config(monkeypatch: object) -> None:
    get_settings.cache_clear()
    get_model.cache_clear()
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example/v1")  # type: ignore[attr-defined]
    monkeypatch.setenv("LLM_API_KEY", "global-key")  # type: ignore[attr-defined]
    monkeypatch.setenv("LLM_MODEL", "axiom-shared")  # type: ignore[attr-defined]
    monkeypatch.delenv("CRITIC_MODEL", raising=False)  # type: ignore[attr-defined]
    get_settings.cache_clear()
    get_model.cache_clear()

    try:
        axiom = get_model()
        critic = get_critic_model({"model": "karen-model", "base_url": "https://k/v1"})
        assert axiom.model_name == "axiom-shared"
        assert critic.model_name == "karen-model"
        assert critic.model_name != axiom.model_name
    finally:
        get_settings.cache_clear()
        get_model.cache_clear()
