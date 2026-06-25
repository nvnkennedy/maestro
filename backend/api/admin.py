"""Administration endpoints: user roles (RBAC) and audit logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import AuditLog, UserRole
from backend.security.audit import record_audit
from backend.security.rbac import ROLES, require_role

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleIn(BaseModel):
    username: str
    role: str
    project_id: int | None = None


@router.get("/roles")
def list_roles(db: Session = Depends(get_db), _: str = Depends(require_role("admin"))):
    return [r.to_dict() for r in db.query(UserRole).order_by(UserRole.username).all()]


@router.post("/roles", status_code=201)
def assign_role(
    body: RoleIn,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("admin")),
):
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of: {', '.join(ROLES)}")
    existing = (
        db.query(UserRole)
        .filter(
            UserRole.username == body.username, UserRole.project_id == body.project_id
        )
        .first()
    )
    if existing is not None:
        existing.role = body.role
        role = existing
    else:
        role = UserRole(
            username=body.username, role=body.role, project_id=body.project_id
        )
        db.add(role)
        db.flush()
    record_audit(db, user, "update", "user_role", role.id, body.model_dump())
    db.commit()
    return role.to_dict()


@router.delete("/roles/{role_id}", status_code=204)
def remove_role(
    role_id: int,
    db: Session = Depends(get_db),
    user: str = Depends(require_role("admin")),
):
    role = db.get(UserRole, role_id)
    if role is None:
        raise HTTPException(404, "Role assignment not found")
    db.delete(role)
    record_audit(db, user, "delete", "user_role", role_id)
    db.commit()


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_db),
    _: str = Depends(require_role("audit")),
):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [entry.to_dict() for entry in logs]
