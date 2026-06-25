"""FastAPI application factory for Maestro."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api.router import api_router, metrics_router, ws_router
from backend.config import FRONTEND_DIST, get_settings
from backend.database import init_db, session_scope
from backend.security_middleware import install_security
from backend.services.plugin_manager import sync_plugins_to_db
from backend.services.project_service import ensure_default_project
from backend.services.scheduler_service import scheduler_service
from backend.utils.logger import get_logger, setup_logging

logger = get_logger("maestro.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    with session_scope() as db:
        ensure_default_project(db)
        sync_plugins_to_db(db)
        from backend.services.seed_data import seed_demo_data

        seed_demo_data(db)
    scheduler_service.start(asyncio.get_running_loop())
    logger.info("maestro_started", version=__version__)
    yield
    scheduler_service.shutdown()
    from backend.adapters.adapter_registry import get_registry

    await get_registry().cleanup_all()
    logger.info("maestro_stopped")


def create_app(serve_frontend: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Maestro",
        description="Automotive Test Automation Framework",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    install_security(app, settings.cors_origins, settings.api_token)
    app.include_router(api_router)
    app.include_router(ws_router)
    app.include_router(metrics_router)

    if serve_frontend and FRONTEND_DIST.exists():
        from fastapi.responses import FileResponse, HTMLResponse

        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_DIST / "assets")),
            name="assets",
        )

        def _index_response() -> HTMLResponse:
            # Inject the API token (when configured) so the same-origin SPA can
            # authenticate without the user pasting it anywhere.
            html = (FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
            if settings.api_token:
                tag = f'<meta name="maestro-token" content="{settings.api_token}">'
                html = html.replace("</head>", f"  {tag}\n</head>", 1)
            return HTMLResponse(html)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            # Serve real files (logo, favicon); everything else falls back to
            # index.html so client-side routes survive a browser refresh.
            candidate = (FRONTEND_DIST / full_path).resolve()
            if (
                full_path
                and candidate.is_file()
                and str(candidate).startswith(str(FRONTEND_DIST.resolve()))
            ):
                return FileResponse(candidate)
            if full_path == "favicon.ico":
                return FileResponse(
                    FRONTEND_DIST / "maestro-logo.svg", media_type="image/svg+xml"
                )
            return _index_response()

    return app


def run() -> None:
    """Run the backend standalone (development)."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
