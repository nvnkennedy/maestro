"""Test execution control endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.execution import Execution
from backend.models.project import TestCase
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.cleanup import cascade_delete_execution
from backend.services.test_executor import executor

router = APIRouter(prefix="/executions", tags=["execution"])


class ExecutionIn(BaseModel):
    test_case_id: int
    mode: str = "serial"  # serial | parallel | step
    # Optional Run Target override (else the test case's default_target_id).
    target_id: int | None = None
    # Endurance / stability: run the case repeatedly. cycles > 1 records one
    # CycleResult per cycle plus a roll-up. stop_conditions accepts
    # {max_duration (s), consecutive_failures, failure_threshold}.
    cycles: int = 1
    stop_conditions: dict | None = None


class SuiteRunIn(BaseModel):
    """Run a whole suite, a scenario, or an explicit list of test cases."""

    project_id: int | None = None
    suite: str | None = None
    scenario: str | None = None
    test_case_ids: list[int] | None = None
    mode: str = "serial"
    target_id: int | None = None  # optional Run Target override for the run


@router.get("")
def list_executions(
    test_case_id: Optional[int] = Query(default=None),
    project_id: Optional[int] = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    query = db.query(Execution)
    if test_case_id:
        query = query.filter(Execution.test_case_id == test_case_id)
    if project_id:
        query = query.join(TestCase).filter(TestCase.project_id == project_id)
    executions = query.order_by(Execution.id.desc()).limit(limit).all()
    tc_info = {
        tc.id: tc
        for tc in db.query(TestCase)
        .filter(TestCase.id.in_({e.test_case_id for e in executions}))
        .all()
    }
    results = []
    for e in executions:
        data = e.to_dict()
        tc = tc_info.get(e.test_case_id)
        data["test_case_name"] = tc.name if tc else f"#{e.test_case_id}"
        data["suite"] = tc.test_type if tc else ""
        data["scenario"] = tc.scenario if tc else ""
        results.append(data)
    return results


@router.post("", status_code=201)
async def start_execution(
    body: ExecutionIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    if body.mode not in ("serial", "parallel", "step"):
        raise HTTPException(422, "mode must be one of: serial, parallel, step")
    try:
        payload = await executor.start(
            body.test_case_id,
            body.mode,
            triggered_by=user,
            target_id=body.target_id,
            cycles=body.cycles,
            stop_conditions=body.stop_conditions,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    record_audit(db, user, "run", "execution", payload["id"], {"mode": body.mode})
    db.commit()
    return payload


@router.post("/suite", status_code=201)
async def start_suite_run(
    body: SuiteRunIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    """Execute every test case in a suite/scenario as one grouped run."""
    if body.mode not in ("serial", "parallel", "step"):
        raise HTTPException(422, "mode must be one of: serial, parallel, step")

    if body.test_case_ids:
        ids = body.test_case_ids
        label = f"{len(ids)} selected test cases"
    else:
        if not body.suite:
            raise HTTPException(422, "Provide a suite name or test_case_ids")
        query = db.query(TestCase).filter(TestCase.test_type == body.suite)
        if body.project_id:
            query = query.filter(TestCase.project_id == body.project_id)
        if body.scenario:
            query = query.filter(TestCase.scenario == body.scenario)
        ids = [tc.id for tc in query.order_by(TestCase.id).all()]
        label = f"{body.suite}{' / ' + body.scenario if body.scenario else ''}"
    if not ids:
        raise HTTPException(404, "No test cases found for this suite/scenario")

    payload = await executor.start_suite(
        ids, body.mode, triggered_by=user, label=label, target_id=body.target_id
    )
    record_audit(
        db, user, "run", "suite_run", None,
        {"label": label, "test_case_ids": ids, "mode": body.mode},
    )
    db.commit()
    return payload


@router.post("/suite/{suite_run_id}/stop")
def stop_suite_run(suite_run_id: str, user: str = Depends(require_role("execute"))):
    if not executor.request_stop_suite(suite_run_id):
        raise HTTPException(409, "Suite run is not active")
    return {"suite_run_id": suite_run_id, "action": "stop", "accepted": True}


@router.get("/running")
def running_executions(_: str = Depends(require_role("read"))):
    return {
        "running_ids": executor.running_ids(),
        "suite_runs": executor.running_suites(),
    }


@router.get("/{execution_id}")
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    data = execution.to_dict(include_steps=True)
    test_case = db.get(TestCase, execution.test_case_id)
    data["test_case_name"] = test_case.name if test_case else None
    data["suite"] = test_case.test_type if test_case else ""
    data["scenario"] = test_case.scenario if test_case else ""
    return data


def _control(execution_id: int, ok: bool, action: str) -> dict:
    if not ok:
        raise HTTPException(409, f"Execution {execution_id} is not running")
    return {"execution_id": execution_id, "action": action, "accepted": True}


@router.post("/{execution_id}/stop")
def stop_execution(execution_id: int, user: str = Depends(require_role("execute"))):
    return _control(execution_id, executor.request_stop(execution_id), "stop")


@router.post("/{execution_id}/pause")
def pause_execution(execution_id: int, user: str = Depends(require_role("execute"))):
    return _control(execution_id, executor.request_pause(execution_id), "pause")


@router.post("/{execution_id}/resume")
def resume_execution(execution_id: int, user: str = Depends(require_role("execute"))):
    return _control(execution_id, executor.request_resume(execution_id), "resume")


@router.post("/{execution_id}/next")
def next_step(execution_id: int, user: str = Depends(require_role("execute"))):
    """Advance one step in step-by-step mode."""
    return _control(execution_id, executor.request_next_step(execution_id), "next")


@router.delete("/{execution_id}", status_code=204)
def delete_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("execute")),
):
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(404, "Execution not found")
    if execution_id in executor.running_ids():
        raise HTTPException(409, "Cannot delete a running execution")
    cascade_delete_execution(db, execution)
    record_audit(db, user, "delete", "execution", execution_id)
    db.commit()
