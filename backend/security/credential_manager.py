"""Credential management on top of the secrets vault.

Stores per-device credentials encrypted in the ``credentials_vault`` table
and exposes typed get/set helpers used by adapters at execution time.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.device_config import CredentialVaultEntry, DeviceConfig
from backend.security.vault import get_vault
from backend.utils.helpers import utcnow


def set_credentials(db: Session, config_id: int, credentials: dict[str, str]) -> None:
    """Encrypt and upsert credentials for a device config."""
    vault = get_vault()
    existing = {
        row.credential_key: row
        for row in db.execute(
            select(CredentialVaultEntry).where(
                CredentialVaultEntry.config_id == config_id
            )
        ).scalars()
    }
    for key, value in credentials.items():
        if value is None or value == "":
            continue
        encrypted = vault.encrypt(str(value))
        if key in existing:
            existing[key].encrypted_value = encrypted
            existing[key].rotated_at = utcnow()
        else:
            db.add(
                CredentialVaultEntry(
                    config_id=config_id, credential_key=key, encrypted_value=encrypted
                )
            )
    db.flush()


def get_credentials(db: Session, config_id: int) -> dict[str, str]:
    """Decrypt all credentials for a device config."""
    vault = get_vault()
    rows = db.execute(
        select(CredentialVaultEntry).where(CredentialVaultEntry.config_id == config_id)
    ).scalars()
    return {row.credential_key: vault.decrypt(row.encrypted_value) for row in rows}


def resolve_target(db: Session, config_id: int) -> dict:
    """Resolve a Run Target (DeviceConfig of type ``target``) for execution.

    Returns a normalised dict describing where steps should run:
    ``kind`` (``local``/``remote``), connection details and decrypted secrets.
    Remote targets are reached over SSH (the embedded/WinRM-OpenSSH channel),
    so the same fields the SSH adapter expects are produced here.
    """
    import json

    config = db.get(DeviceConfig, config_id)
    if config is None:
        raise ValueError(f"Run target {config_id} not found")
    try:
        settings = json.loads(config.settings_json or "{}")
    except ValueError:
        settings = {}
    creds = get_credentials(db, config_id)
    kind = str(settings.get("kind", "remote")).lower()
    return {
        "id": config.id,
        "label": config.label,
        # Full saved settings — includes one-time dependency paths (power_script,
        # dlt_script, etfw_script, adb_path, ffmpeg_path, scrcpy_path) so steps
        # on this machine can reference them via {{target.KEY}} placeholders.
        "settings": settings,
        "kind": "local" if kind == "local" else "remote",
        "transport": settings.get("transport", "ssh"),
        "os": str(settings.get("os", "")).lower(),  # windows | linux | "" (auto)
        "host": settings.get("hostname") or settings.get("host", ""),
        "port": int(settings.get("port", 22) or 22),
        "username": settings.get("username", ""),
        "domain": settings.get("domain", ""),
        "domain_format": settings.get("domain_format", ""),
        "password": creds.get("password", ""),
        "key_file": settings.get("key_file") or creds.get("key_file", ""),
    }


def resolve_device(db: Session, config_id: int) -> dict:
    """Return merged settings + decrypted credentials for adapter use."""
    import json

    config = db.get(DeviceConfig, config_id)
    if config is None:
        raise ValueError(f"Device config {config_id} not found")
    try:
        settings = json.loads(config.settings_json or "{}")
    except ValueError:
        settings = {}
    merged = dict(settings)
    merged.update(get_credentials(db, config_id))
    merged["_config_type"] = config.config_type
    merged["_label"] = config.label
    return merged
