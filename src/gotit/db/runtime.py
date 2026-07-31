"""Lazy DB bootstrap for API-adjacent entrypoints (MCP)."""

from __future__ import annotations

from gotit.api.settings import get_settings
from gotit.db.session import create_all_tables, get_session_factory, init_engine

_ready = False


async def ensure_db() -> None:
    """Idempotent DB init for MCP tools.

    Prefer an engine already created by the API lifespan — never replace a live
    StaticPool ``:memory:`` DB (that would drop in-test / in-process state).
    """
    global _ready
    if _ready:
        try:
            get_session_factory()
            return
        except RuntimeError:
            _ready = False
    try:
        get_session_factory()
        _ready = True
        return
    except RuntimeError:
        pass
    settings = get_settings()
    init_engine(settings.database_url)
    if settings.gotit_db_create_all:
        await create_all_tables()
    _ready = True


def reset_ensure_db_flag() -> None:
    """Test / dispose hook — allow ensure_db to re-bootstrap after engine teardown."""
    global _ready
    _ready = False
