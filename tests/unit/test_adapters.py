"""Adapter and plugin registry unit tests."""

import pytest


@pytest.mark.asyncio
async def test_system_adapter_echo():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute("echo", {"message": "hi maestro"})
    assert result.success
    assert result.output == "hi maestro"


@pytest.mark.asyncio
async def test_system_adapter_assert():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    adapter = SystemAdapter()
    ok = await adapter.execute(
        "assert_contains", {"text": "boot complete", "expected": "complete"}
    )
    assert ok.success
    bad = await adapter.execute(
        "assert_contains", {"text": "boot failed", "expected": "complete"}
    )
    assert not bad.success


@pytest.mark.asyncio
async def test_unknown_action_fails_gracefully():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute("does_not_exist", {})
    assert not result.success
    assert "no action" in result.error


@pytest.mark.asyncio
async def test_action_timeout():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute("wait", {"seconds": 5}, timeout=0.2)
    assert not result.success
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_sandboxed_script():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute(
        "run_script",
        {"interpreter": "python", "script": "print('sandbox-ok')"},
        timeout=90,
    )
    assert result.success, result.error
    assert "sandbox-ok" in result.output


@pytest.mark.asyncio
async def test_system_run_file_any_script(tmp_path):
    """run_file runs an existing script as-is, with args, and checks output."""
    from backend.adapters.system_adapter.adapter import SystemAdapter

    script = tmp_path / "echo_arg.py"
    script.write_text("import sys; print('ran', sys.argv[1])", encoding="utf-8")
    result = await SystemAdapter().execute(
        "run_file",
        {"path": str(script), "args": ["hello"], "expect_contains": "ran hello"},
        timeout=60,
    )
    assert result.success, result.error
    assert "ran hello" in result.output


@pytest.mark.asyncio
async def test_system_run_file_no_args(tmp_path):
    """A custom script with NO arguments runs fine (args omitted entirely)."""
    from backend.adapters.system_adapter.adapter import SystemAdapter

    script = tmp_path / "no_args.py"
    script.write_text("print('hello from script')", encoding="utf-8")
    result = await SystemAdapter().execute(
        "run_file",
        {"path": str(script), "expect_contains": "hello from script"},
        timeout=60,
    )
    assert result.success, result.error
    assert "hello from script" in result.output


@pytest.mark.asyncio
async def test_system_run_file_missing():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute("run_file", {"path": "C:/nope/missing.ps1"})
    assert not result.success and "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_system_run_file_match_and_attach(tmp_path):
    """DLT-style: run a script that writes a log, match a pattern, attach on match."""
    from backend.adapters.system_adapter.adapter import SystemAdapter

    log = tmp_path / "run.dlt"
    script = tmp_path / "make_log.py"
    script.write_text(
        f"open(r'{log}', 'w').write('hdr\\nBootComplete OK\\n'); print('done')",
        encoding="utf-8",
    )
    res = await SystemAdapter().execute(
        "run_file",
        {"path": str(script), "match_file": str(log), "match_pattern": "BootComplete"},
        timeout=60,
    )
    assert res.success, res.error
    assert res.data["match_count"] == 1
    attached = [p["path"] for p in res.data.get("artifact_paths", [])]
    assert str(log) in attached  # matched file attached to the run

    # No match → step fails (match_required default True)
    res2 = await SystemAdapter().execute(
        "run_file",
        {"path": str(script), "match_file": str(log), "match_pattern": "NOPE"},
        timeout=60,
    )
    assert not res2.success and "not found" in res2.error.lower()


@pytest.mark.asyncio
async def test_system_run_command():
    from backend.adapters.system_adapter.adapter import SystemAdapter

    result = await SystemAdapter().execute(
        "run_command", {"command": "echo cmd-ok", "expect_contains": "cmd-ok"}, timeout=30
    )
    assert result.success, result.error
    assert "cmd-ok" in result.output


def test_text_matches_modes():
    from backend.utils.matching import text_matches

    assert text_matches("systemctl status: active", "systemctl")  # contains (default)
    assert not text_matches("nope", "yes")
    assert text_matches("active (running)", "*active*", "wildcard")
    assert text_matches("line1\nBootComplete OK\nline3", "BootComplete*", "wildcard")
    assert text_matches("version v1.2.3 build", r"v\d+\.\d+\.\d+", "regex")
    assert text_matches("DONE", "DONE", "exact")
    assert not text_matches("DONE extra", "DONE", "exact")


def test_check_expectations_multiple():
    from backend.utils.matching import check_expectations

    # single expect_contains (legacy) still works
    ok, _ = check_expectations("service active (running)", {"expect_contains": "active"})
    assert ok
    # multiple via expect_rules — all must match
    ok, _ = check_expectations(
        "version v1.2.3\nstate: active",
        {"expect_rules": [
            {"text": "v\\d+\\.\\d+\\.\\d+", "mode": "regex"},
            {"text": "*active*", "mode": "wildcard"},
        ]},
    )
    assert ok
    # one rule fails → overall fail, message names the failing rule
    ok, msg = check_expectations(
        "only this line",
        {"expect_rules": [
            {"text": "this", "mode": "contains"},
            {"text": "missing", "mode": "contains"},
        ]},
    )
    assert not ok and "missing" in msg
    # expect_contains as a list, sharing match_mode
    ok, _ = check_expectations("a b c", {"expect_contains": ["a", "c"]})
    assert ok
    # no expectations → pass
    assert check_expectations("anything", {})[0]


def test_ssh_wrap_command_sets_path():
    """SSH commands run with a broad PATH (Linux + QNX/embedded) like MobaXterm."""
    from backend.adapters.ssh_adapter.adapter import _wrap_command

    wrapped = _wrap_command("uname -a", {})
    assert "uname -a" in wrapped
    assert "export PATH" in wrapped
    assert "/proc/boot" in wrapped and "/ifs/bin" in wrapped and "/mnt/usr/bin" in wrapped
    # raw_command runs verbatim
    assert _wrap_command("uname -a", {"raw_command": True}) == "uname -a"
    # device-specific dirs are prepended
    assert "/custom/bin" in _wrap_command("x", {"path": "/custom/bin"})


# Domain / UPN login handling moved into turbossh's SSHConfig when the SSH
# adapter migrated to turbossh, so the old `_effective_username` helper (and its
# test) no longer exist here — turbossh owns and tests that behaviour now.


def test_registry_discovers_all_adapters():
    from backend.adapters.adapter_registry import get_registry

    names = {p["name"] for p in get_registry().list_plugins()}
    assert {"ssh", "adb", "power", "etfw", "dlt", "camera", "serial", "system"} <= names


def test_registry_enable_disable():
    from backend.adapters.adapter_registry import get_registry

    registry = get_registry()
    assert registry.set_enabled("system", False)
    assert registry.get("system") is None
    assert registry.set_enabled("system", True)
    assert registry.get("system") is not None


async def test_registry_health_checks():
    from backend.adapters.adapter_registry import get_registry

    results = await get_registry().health_check_all()
    assert "system" in results
    assert results["ssh"]["success"]  # paramiko installed in dev env
