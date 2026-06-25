"""Main API router aggregator."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend import __version__
from backend.api import (
    admin,
    configuration,
    connections,
    datasets,
    execution,
    plugins,
    projects,
    reports,
    scheduling,
    scripts,
    templates,
    test_cases,
    websocket,
)
from backend.database import get_db
from backend.security.rbac import require_role
from backend.services.observability import metrics
from backend.services.project_service import dashboard_stats

api_router = APIRouter(prefix="/api")

api_router.include_router(projects.router)
api_router.include_router(test_cases.router)
api_router.include_router(execution.router)
api_router.include_router(scheduling.router)
api_router.include_router(configuration.router)
api_router.include_router(reports.router)
api_router.include_router(connections.router)
api_router.include_router(plugins.router)
api_router.include_router(datasets.router)
api_router.include_router(scripts.router)
api_router.include_router(templates.router)
api_router.include_router(admin.router)

ws_router = websocket.router


@api_router.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": "maestro", "version": __version__}


@api_router.get("/dashboard", tags=["system"])
def dashboard(
    project_id: int | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    return dashboard_stats(db, project_id)


metrics_router = APIRouter()


@metrics_router.get("/metrics", tags=["system"])
def prometheus_metrics():
    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)
