"""Test data set endpoints (CSV/JSON datasets for parameterized runs)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.report import TestDataSet
from backend.security.audit import record_audit
from backend.security.rbac import require_role
from backend.services.test_data_manager import create_dataset, update_dataset

router = APIRouter(prefix="/datasets", tags=["test-data"])


class DatasetIn(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    data_type: str = "json"  # json | csv
    raw: str = "[]"


@router.get("")
def list_datasets(
    project_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    query = db.query(TestDataSet)
    if project_id:
        query = query.filter(TestDataSet.project_id == project_id)
    return [d.to_dict() for d in query.order_by(TestDataSet.id.desc()).all()]


@router.post("", status_code=201)
def create(
    body: DatasetIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    try:
        dataset = create_dataset(
            db, body.project_id, body.name, body.data_type, body.raw, body.description
        )
    except ValueError as exc:
        raise HTTPException(422, f"Invalid dataset content: {exc}")
    record_audit(db, user, "create", "dataset", dataset.id, {"name": body.name})
    db.commit()
    return dataset.to_dict(include_content=True)


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("read")),
):
    dataset = db.get(TestDataSet, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    return dataset.to_dict(include_content=True)


@router.put("/{dataset_id}")
def update(
    dataset_id: int,
    body: DatasetIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    try:
        dataset = update_dataset(db, dataset_id, body.raw, body.data_type)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    dataset.name = body.name
    dataset.description = body.description
    record_audit(db, user, "update", "dataset", dataset_id, {"name": body.name})
    db.commit()
    return dataset.to_dict(include_content=True)


@router.delete("/{dataset_id}", status_code=204)
def delete(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("design")),
):
    dataset = db.get(TestDataSet, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    db.delete(dataset)
    record_audit(db, user, "delete", "dataset", dataset_id)
    db.commit()
