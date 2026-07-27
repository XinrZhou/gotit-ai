from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gotit import __version__
from gotit.api.routes import router
from gotit.api.settings import get_settings
from gotit.db import create_all_tables, dispose_engine, init_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    init_engine(settings.database_url)
    if settings.gotit_db_create_all:
        await create_all_tables()
    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="gotit-ai", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "gotit.api.main:app",
        host=settings.gotit_host,
        port=settings.gotit_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
