"""Report generation, retrieval, comparison and export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import REPORTS_DIR
from backend.database import get_db
from backend.models.execution import Execution
from backend.models.project import TestCase
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.allure_export import (
    export_allure_zip,
    export_junit_xml,
    maybe_generate_allure_html,
)
from backend.services.cleanup import cascade_delete_execution
from backend.services.report_generator import (
    compare_reports,
    generate_report,
    generate_suite_report,
    load_report_summary,
    render_report_html,
)

# The bespoke HTML reporter; "playwright" was a cosmetic mimic and has been
# retired in favour of real Allure results + JUnit (see /allure and /junit).
REPORT_FORMATS = ("allure",)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def list_reports(
    db: Session = Depends(get_db), _: str = Depends(require_role("read"))
):
    """All executions that have (or can have) a report."""
    executions = (
        db.query(Execution)
        .filter(Execution.status.notin_(["queued", "running", "paused"]))
        .order_by(Execution.id.desc())
        .limit(500)
        .all()
    )
    tc_info = {
        tc.id: tc
        for tc in db.query(TestCase)
        .filter(TestCase.id.in_({e.test_case_id for e in executions}))
        .all()
    }
    reports = []
    for e in executions:
        data = e.to_dict()
        tc = tc_info.get(e.test_case_id)
        data["test_case_name"] = tc.name if tc else f"#{e.test_case_id}"
        data["suite"] = tc.test_type if tc else ""
        data["scenario"] = tc.scenario if tc else ""
        data["report_available"] = (REPORTS_DIR / f"execution_{e.id}.html").exists()
        reports.append(data)
    return reports


@router.get("/publishers")
def list_result_publishers(_: str = Depends(require_role("read"))):
    """Available result-publish channels (email, xray) and whether each is configured."""
    from backend.services.publishers import list_publishers

    return list_publishers()


class PublishIn(BaseModel):
    channel: str = "email"


@router.get("/{execution_id}")
def get_report(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    summary = load_report_summary(execution_id)
    if summary is None:
        if db.get(Execution, execution_id) is None:
            raise HTTPException(404, "Execution not found")
        generate_report(execution_id)
        summary = load_report_summary(execution_id)
    return summary


@router.get("/{execution_id}/html", response_class=HTMLResponse)
def get_report_html(
    execution_id: int,
    format: str = Query(default="allure"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    if format not in REPORT_FORMATS:
        raise HTTPException(422, f"format must be one of {REPORT_FORMATS}")
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    return HTMLResponse(render_report_html(execution_id, format))


@router.get("/{execution_id}/download")
def download_report(
    execution_id: int,
    format: str = Query(default="allure"),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    if format not in REPORT_FORMATS:
        raise HTTPException(422, f"format must be one of {REPORT_FORMATS}")
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    html = render_report_html(execution_id, format)
    filename = f"maestro_{format}_report_{execution_id}.html"
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{execution_id}/allure")
def download_allure_results(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Download a real ``allure-results`` bundle (zip).

    Unzip it and run ``allure serve <dir>`` (or ``allure generate``) to get the
    genuine Allure report — overview, timeline, graphs and history/trends.
    """
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    zip_path = export_allure_zip(execution_id)
    return FileResponse(
        str(zip_path), media_type="application/zip", filename=f"allure-results-{execution_id}.zip"
    )


@router.get("/{execution_id}/allure-html")
def render_allure_html(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Render the real Allure HTML on the server (needs the Allure CLI installed)."""
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    html_dir = maybe_generate_allure_html(execution_id)
    if html_dir is None:
        raise HTTPException(
            503,
            "Allure CLI not found on the server. Install it (e.g. scoop install allure) "
            "or download the allure-results zip from /allure and run `allure serve` locally.",
        )
    return {"report_dir": str(html_dir), "index": str(html_dir / "index.html")}


@router.get("/{execution_id}/junit")
def download_junit(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Download a standard JUnit XML for the execution (CI / Jira-Xray import)."""
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    xml = export_junit_xml(execution_id)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="junit_{execution_id}.xml"'},
    )


@router.post("/{execution_id}/publish")
def publish_report(
    execution_id: int,
    body: PublishIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    """Publish a run's results to email or Jira/Xray. No-op (with a clear reason)
    if that channel isn't configured."""
    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    from backend.services.publishers import publish_result

    result = publish_result(execution_id, body.channel)
    record_audit(
        db, user, "publish", "report", execution_id,
        {"channel": body.channel, "ok": result.get("ok")},
    )
    if not result.get("ok") and not result.get("skipped"):
        raise HTTPException(502, result.get("detail", "Publish failed"))
    return result


@router.get("/{execution_id}/cycles")
def get_cycles(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Per-cycle results for an endurance run, plus a roll-up (first-failure cycle)."""
    from backend.models.execution import CycleResult

    if db.get(Execution, execution_id) is None:
        raise HTTPException(404, "Execution not found")
    cycles = (
        db.query(CycleResult)
        .filter(CycleResult.execution_id == execution_id)
        .order_by(CycleResult.cycle_index)
        .all()
    )
    rows = [c.to_dict() for c in cycles]
    failed = sum(1 for c in rows if c["status"] in ("failed", "error"))
    first_failure = next(
        (c["cycle_index"] for c in rows if c["status"] in ("failed", "error")), None
    )
    return {
        "execution_id": execution_id,
        "cycles": rows,
        "rollup": {
            "total": len(rows),
            "passed": sum(1 for c in rows if c["status"] == "passed"),
            "failed": failed,
            "first_failure_cycle": first_failure,
            "is_endurance": len(rows) > 0,
        },
    }


@router.get("/suite/{suite_run_id}")
def get_suite_report(
    suite_run_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    """Aggregated JSON summary for a whole suite/scenario run."""
    import json as _json

    path = REPORTS_DIR / f"suite_{suite_run_id}.json"
    if not path.exists():
        generate_suite_report(suite_run_id)
    if not path.exists():
        raise HTTPException(404, "Suite run not found")
    return _json.loads(path.read_text(encoding="utf-8"))


@router.get("/suite/{suite_run_id}/html", response_class=HTMLResponse)
def get_suite_report_html(
    suite_run_id: str,
    _: str = Depends(require_role("read")),
):
    """Single rolled-up HTML report for a suite/scenario run."""
    path = REPORTS_DIR / f"suite_{suite_run_id}.html"
    if not path.exists():
        generated = generate_suite_report(suite_run_id)
        if generated is None:
            raise HTTPException(404, "Suite run not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


class CompareIn(BaseModel):
    execution_a: int
    execution_b: int


@router.post("/compare")
def compare(
    body: CompareIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    # Ensure both summaries exist (generate lazily).
    for execution_id in (body.execution_a, body.execution_b):
        if load_report_summary(execution_id) is None:
            if db.get(Execution, execution_id) is None:
                raise HTTPException(404, f"Execution {execution_id} not found")
            generate_report(execution_id)
    try:
        return compare_reports(body.execution_a, body.execution_b)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


class BulkDeleteIn(BaseModel):
    ids: list[int]


@router.post("/bulk-delete")
def bulk_delete_reports(
    body: BulkDeleteIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    deleted = 0
    for execution_id in body.ids:
        execution = db.get(Execution, execution_id)
        if execution is not None:
            cascade_delete_execution(db, execution)
            deleted += 1
    record_audit(db, user, "delete", "report", None, {"bulk_ids": body.ids})
    db.commit()
    return {"deleted": deleted}
