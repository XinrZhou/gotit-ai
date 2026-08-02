from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gotit_host: str = "127.0.0.1"
    gotit_port: int = 8787
    gotit_api_key: str = "dev-change-me"

    database_url: str = "postgresql+asyncpg://gotit:gotit@127.0.0.1:5432/gotit"
    # Reserved; application code does not read redis_url today.
    redis_url: str = "redis://127.0.0.1:6379/0"
    gotit_user_id: str = "local"
    # When true (default), create tables on API startup (handy for sqlite/dev).
    gotit_db_create_all: bool = True

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"

    # Optional Critic (凯伦) overrides — used when identity.llm_config omits a field.
    critic_model: str = ""
    critic_base_url: str = ""
    critic_api_key: str = ""

    # Optional STT for voice teach-back (OpenAI-compatible /audio/transcriptions).
    # Empty STT_* falls back to LLM_*; no key → text-only teach path.
    stt_api_key: str = ""
    stt_base_url: str = ""
    stt_model: str = ""
    stt_stub: bool = False
    stt_stub_text: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
