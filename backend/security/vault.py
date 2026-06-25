"""Secrets vault — AES-256-GCM encryption for device credentials.

The vault key is derived from ``SECRET_KEY`` (if set) or generated once and
persisted to ``data/.vault.key`` with restrictive permissions.
"""

from __future__ import annotations

import base64
import os
import secrets
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from backend.config import get_settings

_NONCE_SIZE = 12
_KEY_SIZE = 32  # 256-bit
_KDF_SALT = b"maestro-vault-v1"
_KDF_ITERATIONS = 480_000


def _restrict_permissions(path) -> None:
    """Lock the key file down to the current user, on POSIX and Windows."""
    try:
        os.chmod(path, 0o600)  # effective on POSIX; a no-op for Windows ACLs
    except OSError:
        pass
    if os.name == "nt":
        import getpass
        import subprocess

        try:
            user = os.getenv("USERNAME") or getpass.getuser()
            # Remove inherited ACEs and grant only this user full control.
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                check=False,
                capture_output=True,
            )
        except Exception:  # icacls missing / locked-down host — best effort
            pass


class SecretsVault:
    """Encrypt/decrypt small secrets with AES-256-GCM."""

    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or self._load_or_create_key()
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def _derive_key(secret: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=_KEY_SIZE,
            salt=_KDF_SALT,
            iterations=_KDF_ITERATIONS,
        )
        return kdf.derive(secret.encode("utf-8"))

    def _load_or_create_key(self) -> bytes:
        settings = get_settings()
        if settings.secret_key:
            return self._derive_key(settings.secret_key)

        key_file = settings.vault_key_file
        if key_file.exists():
            return base64.b64decode(key_file.read_bytes())

        key = secrets.token_bytes(_KEY_SIZE)
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(base64.b64encode(key))
        _restrict_permissions(key_file)
        import warnings

        warnings.warn(
            "SECRET_KEY is not set: a random vault key was written to "
            f"{key_file}. Anyone who can read that file can decrypt stored "
            "credentials. Set SECRET_KEY in .env for a key derived from a "
            "secret you control.",
            stacklevel=2,
        )
        return key

    def encrypt(self, plaintext: str) -> bytes:
        nonce = secrets.token_bytes(_NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + ciphertext

    def decrypt(self, blob: bytes) -> str:
        nonce, ciphertext = blob[:_NONCE_SIZE], blob[_NONCE_SIZE:]
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    def encrypt_to_b64(self, plaintext: str) -> str:
        return base64.b64encode(self.encrypt(plaintext)).decode("ascii")

    def decrypt_from_b64(self, encoded: str) -> str:
        return self.decrypt(base64.b64decode(encoded))


@lru_cache(maxsize=1)
def get_vault() -> SecretsVault:
    return SecretsVault()
