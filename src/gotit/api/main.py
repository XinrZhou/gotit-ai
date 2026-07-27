from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gotit import __version__
from gotit.api.routes import router
from gotit.api.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="gotit-ai", version=__version__)
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
