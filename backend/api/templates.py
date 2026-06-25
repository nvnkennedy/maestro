"""User-defined step template management (Template Manager page)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.security.rbac import require_role
from backend.services import template_store

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateIn(BaseModel):
    id: str = ""  # empty on create
    group: str = Field(default="Custom", min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1)
    parameters: dict = Field(default_factory=dict)
    timeout_seconds: int = 30


@router.get("")
def list_user_templates(_: str = Depends(require_role("read"))):
    return template_store.list_templates()


@router.post("", status_code=201)
def create_template(body: TemplateIn, _: str = Depends(require_role("design"))):
    return template_store.save_template(body.model_dump())


@router.put("/{template_id}")
def update_template(template_id: str, body: TemplateIn, _: str = Depends(require_role("design"))):
    if template_store.get_template(template_id) is None:
        raise HTTPException(404, "Template not found")
    payload = body.model_dump()
    payload["id"] = template_id
    return template_store.save_template(payload)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, _: str = Depends(require_role("design"))):
    if not template_store.delete_template(template_id):
        raise HTTPException(404, "Template not found")
