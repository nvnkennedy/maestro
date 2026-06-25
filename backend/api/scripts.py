"""Registered custom-script management (power/etfw/dlt subcommand scripts)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.security.rbac import require_role
from backend.services import script_registry

router = APIRouter(prefix="/scripts", tags=["scripts"])


class CommandIn(BaseModel):
    label: str = ""
    args: list[str] = Field(default_factory=list)


class ScriptIn(BaseModel):
    id: str = ""  # empty on create; the server assigns a slug
    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1)
    interpreter: str = ""  # e.g. python, or a full path; "" = auto by extension
    description: str = ""
    # Each command is a named argument list: python <path> <args…>
    commands: list[CommandIn] = Field(default_factory=list)


@router.get("")
def list_scripts(_: str = Depends(require_role("read"))):
    return script_registry.list_scripts()


@router.post("", status_code=201)
def create_script(body: ScriptIn, _: str = Depends(require_role("configure"))):
    return script_registry.save_script(body.model_dump())


@router.put("/{script_id}")
def update_script(script_id: str, body: ScriptIn, _: str = Depends(require_role("configure"))):
    if script_registry.get_script(script_id) is None:
        raise HTTPException(404, "Script not found")
    payload = body.model_dump()
    payload["id"] = script_id
    return script_registry.save_script(payload)


@router.delete("/{script_id}", status_code=204)
def delete_script(script_id: str, _: str = Depends(require_role("configure"))):
    if not script_registry.delete_script(script_id):
        raise HTTPException(404, "Script not found")
