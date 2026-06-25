"""Security modules: secrets vault, RBAC, audit logging, credential management."""

from backend.security.audit import record_audit
from backend.security.rbac import ROLES, get_current_user, require_role
from backend.security.vault import SecretsVault, get_vault

__all__ = [
    "SecretsVault",
    "get_vault",
    "ROLES",
    "get_current_user",
    "require_role",
    "record_audit",
]
