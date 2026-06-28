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


# ---- built-in templates (read-only) — list + hide/restore --------------------


@router.get("/builtin")
def list_builtin_templates(_: str = Depends(require_role("read"))):
    """All built-in templates by group, each tagged with a stable key + hidden flag."""
    hidden = set(template_store.list_hidden_builtins())
    out: dict[str, list] = {}
    for group, items in template_store.load_builtins().items():
        out[group] = [
            {**item, "key": key, "hidden": key in hidden}
            for item in items
            if (key := template_store.builtin_key(group, item))
        ]
    return out


class BuiltinHiddenIn(BaseModel):
    key: str = Field(min_length=1)
    hidden: bool = True


@router.post("/builtin/hidden")
def set_builtin_hidden(body: BuiltinHiddenIn, _: str = Depends(require_role("design"))):
    """Hide a built-in template from the palette (or restore it)."""
    template_store.set_builtin_hidden(body.key, body.hidden)
    return {"key": body.key, "hidden": body.hidden}
