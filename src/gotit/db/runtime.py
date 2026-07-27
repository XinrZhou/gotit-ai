"""Lazy DB bootstrap for API-adjacent entrypoints (MCP)."""

from __future__ import annotations

from gotit.api.settings import get_settings
from gotit.db.session import create_all_tables, get_session_factory, init_engine

_ready = False


async def ensure_db() -> None:
    global _ready
    if _ready:
        try:
            get_session_factory()
            return
        except RuntimeError:
            _ready = False
    settings = get_settings()
    init_engine(settings.database_url)
    if settings.gotit_db_create_all:
        await create_all_tables()
    _ready = True
