"""Secrets vault unit tests."""

import pytest


def test_encrypt_decrypt_roundtrip():
    from backend.security.vault import SecretsVault

    vault = SecretsVault(key=b"0" * 32)
    secret = "p@ssw0rd-with-ünïcode-🔐"
    blob = vault.encrypt(secret)
    assert blob != secret.encode()
    assert vault.decrypt(blob) == secret


def test_unique_nonces():
    from backend.security.vault import SecretsVault

    vault = SecretsVault(key=b"1" * 32)
    assert vault.encrypt("same") != vault.encrypt("same")


def test_b64_roundtrip():
    from backend.security.vault import SecretsVault

    vault = SecretsVault(key=b"2" * 32)
    encoded = vault.encrypt_to_b64("hello")
    assert isinstance(encoded, str)
    assert vault.decrypt_from_b64(encoded) == "hello"


def test_wrong_key_fails():
    from backend.security.vault import SecretsVault

    blob = SecretsVault(key=b"3" * 32).encrypt("secret")
    with pytest.raises(Exception):
        SecretsVault(key=b"4" * 32).decrypt(blob)


def test_key_file_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("MAESTRO_VAULT_KEY_FILE", str(tmp_path / "k.key"))
    monkeypatch.setenv("SECRET_KEY", "")
    from backend.config import get_settings
    from backend.security.vault import SecretsVault

    get_settings.cache_clear()
    try:
        first = SecretsVault()
        blob = first.encrypt("persist-me")
        second = SecretsVault()  # must load the same key file
        assert second.decrypt(blob) == "persist-me"
    finally:
        get_settings.cache_clear()
