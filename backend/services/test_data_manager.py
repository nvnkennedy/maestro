"""Test data set management — CSV/JSON datasets for parameterized runs."""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy.orm import Session

from backend.models.report import TestDataSet


def parse_rows(data_type: str, raw: str) -> list[dict]:
    """Parse uploaded CSV or JSON content into a list of row dicts."""
    if data_type == "csv":
        reader = csv.DictReader(io.StringIO(raw))
        return [dict(row) for row in reader]
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise ValueError("JSON dataset must be an array of objects")
    return parsed


def create_dataset(
    db: Session,
    project_id: int,
    name: str,
    data_type: str,
    raw: str,
    description: str = "",
) -> TestDataSet:
    rows = parse_rows(data_type, raw)
    dataset = TestDataSet(
        project_id=project_id,
        name=name,
        description=description,
        data_type=data_type,
        content=json.dumps(rows, default=str),
    )
    db.add(dataset)
    db.flush()
    return dataset


def update_dataset(db: Session, dataset_id: int, raw: str, data_type: str | None = None) -> TestDataSet:
    dataset = db.get(TestDataSet, dataset_id)
    if dataset is None:
        raise ValueError(f"Dataset {dataset_id} not found")
    dtype = data_type or dataset.data_type
    rows = parse_rows(dtype, raw)
    dataset.content = json.dumps(rows, default=str)
    dataset.data_type = dtype
    dataset.version += 1
    return dataset


def inject_data(params: dict, row: dict) -> dict:
    """Substitute {{data.key}} placeholders in step params with dataset values."""
    import re

    pattern = re.compile(r"\{\{\s*data\.([A-Za-z0-9_]+)\s*\}\}")

    def sub(value):
        if isinstance(value, str):
            return pattern.sub(lambda m: str(row.get(m.group(1), "")), value)
        if isinstance(value, dict):
            return {k: sub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [sub(v) for v in value]
        return value

    return {k: sub(v) for k, v in params.items()}
