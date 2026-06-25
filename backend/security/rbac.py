"""Role-Based Access Control.

Maestro runs as a local dashboard, so authentication is intentionally light:
the acting user is taken from the ``X-Maestro-User`` header (default
``admin``) and authorisation is enforced against the ``user_roles`` table.
A user with no role rows is treated as ``admin`` on first run so the
out-of-the-box experience requires zero setup; once any role row exists,
enforcement is strict.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import UserRole

ROLES = ("admin", "designer", "executor", "viewer", "auditor")

# role -> set of permissions
_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"read", "design", "execute", "configure", "audit", "admin"},
    "designer": {"read", "design"},
    "executor": {"read", "execute"},
    "viewer": {"read"},
    "auditor": {"read", "audit"},
}


def get_current_user(request: Request) -> str:
    return request.headers.get("X-Maestro-User", "admin")


def _roles_for(db: Session, username: str) -> list[str]:
    rows = db.execute(
        select(UserRole.role).where(UserRole.username == username)
    ).scalars().all()
    return list(rows)


def user_permissions(db: Session, username: str) -> set[str]:
    any_roles = db.execute(select(UserRole.id).limit(1)).first()
    if any_roles is None:
        # No RBAC configured yet -> open mode (single-user local install).
        return _PERMISSIONS["admin"]
    perms: set[str] = set()
    for role in _roles_for(db, username):
        perms |= _PERMISSIONS.get(role, set())
    return perms


def require_role(permission: str):
    """FastAPI dependency factory: require a permission for the endpoint."""

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
    ) -> str:
        username = get_current_user(request)
        perms = user_permissions(db, username)
        if permission not in perms:
            raise HTTPException(
                status_code=403,
                detail=f"User '{username}' lacks '{permission}' permission",
            )
        return username

    return dependency
