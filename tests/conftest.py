from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

# Use a fresh in-memory SQLite DB for tests before app import side effects.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["GOTIT_DB_CREATE_ALL"] = "true"
os.environ["GOTIT_API_KEY"] = "dev-change-me"
os.environ["GOTIT_USER_ID"] = "local"
# Force stub agent path in tests (ignore developer .env LLM keys).
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_MODEL"] = "gpt-4.1-mini"

from gotit.api.settings import get_settings

get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from gotit.api.main import create_app
    from gotit.db import dispose_engine

    get_settings.cache_clear()
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    await dispose_engine()
    get_settings.cache_clear()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer dev-change-me"}
