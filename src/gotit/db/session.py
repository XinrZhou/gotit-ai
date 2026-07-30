"""Async engine / session helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gotit.db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def normalize_database_url(url: str) -> str:
    """Accept common Postgres URLs and coerce to async drivers."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def init_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    global _engine, _session_factory
    url = normalize_database_url(database_url)
    kwargs: dict[str, object] = {"echo": echo}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    _engine = create_async_engine(url, **kwargs)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("database engine not initialized; call init_engine first")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("database session factory not initialized; call init_engine first")
    return _session_factory


async def create_all_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_sqlite_plan_due_time)
        await conn.run_sync(_ensure_sqlite_claim_calibration)


def _ensure_sqlite_plan_due_time(sync_conn: Connection) -> None:
    """Dev sqlite: create_all won't add new columns — ALTER if missing."""
    if sync_conn.dialect.name != "sqlite":
        return
    rows = sync_conn.exec_driver_sql("PRAGMA table_info(plan_items)").fetchall()
    cols = {r[1] for r in rows}
    if "due_time" not in cols and rows:
        sync_conn.exec_driver_sql(
            "ALTER TABLE plan_items ADD COLUMN due_time VARCHAR(5)"
        )


def _ensure_sqlite_claim_calibration(sync_conn: Connection) -> None:
    """Dev sqlite: add claims.calibration JSON if missing."""
    if sync_conn.dialect.name != "sqlite":
        return
    rows = sync_conn.exec_driver_sql("PRAGMA table_info(claims)").fetchall()
    cols = {r[1] for r in rows}
    if "calibration" not in cols and rows:
        sync_conn.exec_driver_sql(
            "ALTER TABLE claims ADD COLUMN calibration JSON DEFAULT '{}'"
        )


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
