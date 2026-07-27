from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gotit_host: str = "127.0.0.1"
    gotit_port: int = 8787
    gotit_api_key: str = "dev-change-me"

    database_url: str = "postgresql+asyncpg://gotit:gotit@127.0.0.1:5432/gotit"
    redis_url: str = "redis://127.0.0.1:6379/0"

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
