"""Validator unit tests."""

from backend.utils.validators import (
    is_valid_cron,
    is_valid_hostname,
    is_valid_port,
    sanitize_filename,
)


def test_valid_cron():
    assert is_valid_cron("0 9 * * MON")
    assert is_valid_cron("*/5 * * * *")
    assert is_valid_cron("0 0 1 1 0")


def test_invalid_cron():
    assert not is_valid_cron("not a cron")
    assert not is_valid_cron("0 9 * *")
    assert not is_valid_cron("")


def test_hostname():
    assert is_valid_hostname("192.168.1.10")
    assert is_valid_hostname("device.local")
    assert not is_valid_hostname("-bad-")
    assert not is_valid_hostname("")


def test_port():
    assert is_valid_port(22)
    assert is_valid_port("8080")
    assert not is_valid_port(0)
    assert not is_valid_port(70000)
    assert not is_valid_port("abc")


def test_sanitize_filename():
    assert sanitize_filename('bad/name<>:"') == "bad_name____"
    assert sanitize_filename("") == "unnamed"
