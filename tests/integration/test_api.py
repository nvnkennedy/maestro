"""End-to-end API integration tests (full app via TestClient)."""

from __future__ import annotations

import time


def _wait_for_execution(client, execution_id: int, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/executions/{execution_id}").json()
        if data["status"] not in ("queued", "running", "paused"):
            return data
        time.sleep(0.2)
    raise AssertionError(f"Execution {execution_id} did not finish in {timeout}s")


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_default_project_created(client):
    projects = client.get("/api/projects").json()
    assert len(projects) >= 1


def test_project_crud(client):
    created = client.post(
        "/api/projects", json={"name": "Infotainment", "description": "HU tests"}
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    assert client.post("/api/projects", json={"name": "Infotainment"}).status_code == 409

    updated = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Infotainment-2", "description": "renamed"},
    )
    assert updated.json()["name"] == "Infotainment-2"

    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_templates_available(client):
    templates = client.get("/api/test-cases/templates").json()
    for key in ("ssh", "adb", "power", "etfw", "dlt", "ignition", "camera", "system"):
        assert key in templates, f"missing template group {key}"
        assert len(templates[key]) > 0


def test_test_case_crud_and_versioning(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    body = {
        "project_id": project_id,
        "name": "Boot check",
        "test_type": "system",
        "scenario": "smoke",
        "steps": [
            {"step_number": 1, "action": "system.echo", "parameters": {"message": "a"}},
            {"step_number": 2, "action": "system.wait", "parameters": {"seconds": 0.01}},
        ],
    }
    created = client.post("/api/test-cases", json=body).json()
    tc_id = created["id"]
    assert created["step_count"] == 2

    body["steps"].append(
        {"step_number": 3, "action": "system.echo", "parameters": {"message": "c"}}
    )
    updated = client.put(f"/api/test-cases/{tc_id}", json=body).json()
    assert updated["step_count"] == 3

    versions = client.get(f"/api/test-cases/{tc_id}/versions").json()
    assert len(versions) == 2

    diff = client.get(
        f"/api/test-cases/{tc_id}/versions/diff", params={"a": 1, "b": 2}
    ).json()
    assert any(d["change"] == "added" for d in diff["diffs"])

    rolled = client.post(f"/api/test-cases/{tc_id}/versions/1/rollback").json()
    assert rolled["step_count"] == 2

    clone = client.post(f"/api/test-cases/{tc_id}/clone")
    assert clone.status_code == 201
    assert "(copy)" in clone.json()["name"]


def test_test_case_export_import_roundtrip(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    body = {
        "project_id": project_id,
        "name": "Portable case",
        "test_type": "system",
        "scenario": "smoke",
        "steps": [
            {"step_number": 1, "action": "system.echo", "parameters": {"message": "hi"}},
        ],
    }
    tc_id = client.post("/api/test-cases", json=body).json()["id"]

    bundle = client.get(f"/api/test-cases/{tc_id}/export").json()
    assert bundle["format"] == "maestro.testcase/v1"
    assert bundle["name"] == "Portable case"
    assert len(bundle["steps"]) == 1

    # Import the bundle into the same project — a new, independent case.
    imported = client.post(
        "/api/test-cases/import", json={**bundle, "project_id": project_id}
    )
    assert imported.status_code == 201
    new_case = imported.json()
    assert new_case["id"] != tc_id
    assert new_case["step_count"] == 1

    # A bad format is rejected.
    assert (
        client.post(
            "/api/test-cases/import",
            json={"project_id": project_id, "format": "nope", "name": "x"},
        ).status_code
        == 422
    )


def test_execution_serial_pass(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Serial pass",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "one"}},
                {
                    "step_number": 2,
                    "action": "system.assert_contains",
                    "parameters": {"text": "{{steps.1.output}}", "expected": "one"},
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    assert started.status_code == 201
    final = _wait_for_execution(client, started.json()["id"])
    assert final["status"] == "passed", final
    assert all(s["status"] == "passed" for s in final["steps"])


def test_execution_conditional_branch_skips(client):
    """A `_if` branch (what the flow canvas emits) jumps past skipped steps."""
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Branch flow",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "GOLD"}},
                {
                    # Branch node: if step 1's output contains GOLD, jump to step 4.
                    "step_number": 2,
                    "action": "system.echo",
                    "parameters": {
                        "message": "branch",
                        "_if": {"source_step": 1, "contains": "GOLD", "skip_to": 4},
                    },
                },
                {"step_number": 3, "action": "system.echo", "parameters": {"message": "SKIP_ME"}},
                {"step_number": 4, "action": "system.echo", "parameters": {"message": "END"}},
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    final = _wait_for_execution(client, started.json()["id"])
    by_number = {s["step_number"]: s for s in final["steps"]}
    assert final["status"] == "passed", final
    assert by_number[1]["status"] == "passed"
    assert by_number[3]["status"] == "skipped", final  # jumped over
    assert by_number[4]["status"] == "passed"


def test_report_format_choice(client):
    """Reports can render in Allure or Playwright format on demand."""
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Fmt",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "hi"}},
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    rid = started.json()["id"]
    _wait_for_execution(client, rid)

    allure = client.get(f"/api/reports/{rid}/html?format=allure")
    assert allure.status_code == 200
    assert "Step timeline" in allure.text  # allure-specific
    # The cosmetic "playwright" format was retired in favour of real Allure
    # results + JUnit, so it is now rejected.
    pw = client.get(f"/api/reports/{rid}/html?format=playwright")
    assert pw.status_code == 422
    # default is allure
    assert "Step timeline" in client.get(f"/api/reports/{rid}/html").text
    assert client.get(f"/api/reports/{rid}/html?format=bogus").status_code == 422


def test_step_planned_attachment(client):
    """A file attached to a step is stored and surfaces as a report artifact."""
    up = client.post(
        "/api/test-cases/attachments", params={"filename": "plan.txt"}, content=b"hello-plan"
    )
    assert up.status_code == 201
    att = up.json()
    assert att["size"] == len(b"hello-plan") and att["name"] == "plan.txt"

    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Att",
            "steps": [
                {
                    "step_number": 1,
                    "action": "system.echo",
                    "parameters": {
                        "message": "hi",
                        "_attachments": [{"name": att["name"], "path": att["path"]}],
                    },
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    rid = started.json()["id"]
    _wait_for_execution(client, rid)
    summary = client.get(f"/api/reports/{rid}").json()
    assert any(a.get("artifact_type") == "planned" for a in summary.get("artifacts", []))


def test_run_file_step_matches_and_attaches(client, tmp_path):
    """End-to-end: a run_file step matches a pattern in a produced file and
    attaches it to the run (DLT match mode)."""
    log = tmp_path / "out.dlt"
    script = tmp_path / "s.py"
    script.write_text(
        f"open(r'{log}', 'w').write('READY signal'); print('went')", encoding="utf-8"
    )
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "RunFile",
            "steps": [
                {
                    "step_number": 1,
                    "action": "system.run_file",
                    "parameters": {
                        "path": str(script),
                        "match_file": str(log),
                        "match_pattern": "READY",
                    },
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    rid = started.json()["id"]
    final = _wait_for_execution(client, rid)
    assert final["status"] == "passed", final
    summary = client.get(f"/api/reports/{rid}").json()
    assert any(str(log) == a["file_path"] for a in summary.get("artifacts", []))


def test_execution_records_triggering_user(client):
    """triggered_by is persisted from the X-Maestro-User header."""
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Whodunit",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "hi"}},
            ],
        },
    ).json()
    started = client.post(
        "/api/executions",
        json={"test_case_id": tc["id"]},
        headers={"X-Maestro-User": "naveen"},
    )
    assert started.json()["triggered_by"] == "naveen"
    final = _wait_for_execution(client, started.json()["id"])
    assert final["triggered_by"] == "naveen"


def test_execution_failure_skips_remaining(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Fails mid-run",
            "steps": [
                {"step_number": 1, "action": "system.fail", "parameters": {"message": "boom"}},
                {"step_number": 2, "action": "system.echo", "parameters": {"message": "never"}},
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "failed"
    statuses = {s["step_number"]: s["status"] for s in final["steps"]}
    assert statuses[1] == "failed"
    assert statuses[2] == "skipped"


def test_execution_conditional_branch(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Conditional",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "ERROR found"}},
                {
                    "step_number": 2,
                    "action": "system.echo",
                    "parameters": {
                        "message": "remediation-skipped",
                        "_if": {"source_step": 1, "contains": "ERROR", "skip_to": 3},
                    },
                },
                {"step_number": 3, "action": "system.echo", "parameters": {"message": "final"}},
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "passed"
    statuses = {s["step_number"]: s["status"] for s in final["steps"]}
    assert statuses[2] == "skipped"
    assert statuses[3] == "passed"


def test_execution_parallel_mode(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Parallel",
            "steps": [
                {"step_number": i, "action": "system.wait", "parameters": {"seconds": 0.2}}
                for i in range(1, 4)
            ],
        },
    ).json()
    started = client.post(
        "/api/executions", json={"test_case_id": tc["id"], "mode": "parallel"}
    ).json()
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "passed"
    # Three 0.2s steps in parallel must finish well under 0.6s serial time.
    assert final["duration_seconds"] < 0.55, final["duration_seconds"]


def test_execution_retry(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Retry",
            "steps": [
                {
                    "step_number": 1,
                    "action": "system.fail",
                    "parameters": {"message": "always fails"},
                    "retry_count": 2,
                }
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    final = _wait_for_execution(client, started["id"], timeout=60)
    assert final["status"] == "failed"
    assert final["steps"][0]["attempts"] == 3  # 1 try + 2 retries


def test_step_pause_before_gate(client):
    """A step flagged _pause_before waits for /next even in serial mode."""
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Checkpoint run",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "a"}},
                {
                    "step_number": 2,
                    "action": "system.echo",
                    "parameters": {"message": "b", "_pause_before": True},
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    time.sleep(0.8)
    # Execution must still be running, gated before step 2.
    mid = client.get(f"/api/executions/{started['id']}").json()
    assert mid["status"] == "running"
    statuses = {s["step_number"]: s["status"] for s in mid["steps"]}
    assert statuses.get(1) == "passed"
    assert 2 not in statuses  # not executed yet
    # Release the gate.
    assert client.post(f"/api/executions/{started['id']}/next").status_code == 200
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "passed"


def test_always_run_collectors_after_failure(client):
    """Steps flagged _always_run execute even when an earlier step fails."""
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Collector run",
            "steps": [
                {"step_number": 1, "action": "system.fail", "parameters": {"message": "boom"}},
                {"step_number": 2, "action": "system.echo", "parameters": {"message": "normal"}},
                {
                    "step_number": 3,
                    "action": "system.echo",
                    "parameters": {"message": "collected logs", "_always_run": True},
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "failed"
    statuses = {s["step_number"]: s["status"] for s in final["steps"]}
    assert statuses[1] == "failed"
    assert statuses[2] == "skipped"
    assert statuses[3] == "passed"  # collector still ran


def test_project_export_backup(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    response = client.get(f"/api/projects/{project_id}/export")
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    backup = response.json()
    assert backup["project"]["id"] == project_id
    assert isinstance(backup["test_cases"], list)
    # Credentials must never be exported.
    assert "credentials_vault" not in response.text
    for config in backup["device_configs"]:
        assert "encrypted_value" not in config


def test_move_and_rename_groups(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Movable case",
            "test_type": "OldSuite",
            "scenario": "OldScenario",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "x"}}
            ],
        },
    ).json()

    moved = client.post(
        "/api/test-cases/move",
        json={"ids": [tc["id"]], "suite": "Retest", "scenario": "Round 2"},
    )
    assert moved.status_code == 200 and moved.json()["moved"] == 1
    fetched = client.get(f"/api/test-cases/{tc['id']}").json()
    assert fetched["test_type"] == "Retest" and fetched["scenario"] == "Round 2"

    renamed = client.post(
        "/api/test-cases/rename-group",
        json={"project_id": project_id, "suite": "Retest", "new_name": "Retest Phase 1"},
    )
    assert renamed.status_code == 200 and renamed.json()["renamed"] >= 1
    assert client.get(f"/api/test-cases/{tc['id']}").json()["test_type"] == "Retest Phase 1"

    scenario_renamed = client.post(
        "/api/test-cases/rename-group",
        json={
            "project_id": project_id,
            "suite": "Retest Phase 1",
            "scenario": "Round 2",
            "new_name": "Round 3",
        },
    )
    assert scenario_renamed.status_code == 200
    assert client.get(f"/api/test-cases/{tc['id']}").json()["scenario"] == "Round 3"


def test_suite_schedule(client):
    from datetime import datetime, timedelta

    project_id = client.get("/api/projects").json()[0]["id"]
    client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Suite sched member",
            "test_type": "SchedSuite",
            "scenario": "G",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "y"}}
            ],
        },
    )
    future = (datetime.now() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/schedules",
        json={
            "suite": "SchedSuite",
            "project_id": project_id,
            "schedule_type": "once",
            "run_at": future,
        },
    )
    assert created.status_code == 201, created.text
    schedule = created.json()
    assert schedule["target_label"] == "Suite: SchedSuite"

    listed = client.get("/api/schedules").json()
    entry = next(s for s in listed if s["id"] == schedule["id"])
    assert entry["test_case_name"].startswith("Suite:")
    client.delete(f"/api/schedules/{schedule['id']}")

    missing = client.post(
        "/api/schedules",
        json={"suite": "NoSuchSuite", "schedule_type": "once", "run_at": future},
    )
    assert missing.status_code == 404


def test_suite_run_executes_all_cases(client):
    """Running a suite executes every test case in it as one grouped run."""
    project_id = client.get("/api/projects").json()[0]["id"]
    for name in ("Suite case A", "Suite case B"):
        client.post(
            "/api/test-cases",
            json={
                "project_id": project_id,
                "name": name,
                "test_type": "SuiteRunDemo",
                "scenario": "Group",
                "steps": [
                    {"step_number": 1, "action": "system.echo", "parameters": {"message": name}}
                ],
            },
        )

    started = client.post(
        "/api/executions/suite",
        json={"project_id": project_id, "suite": "SuiteRunDemo"},
    )
    assert started.status_code == 201, started.text
    suite_run = started.json()
    assert suite_run["total"] == 2

    deadline = time.time() + 30
    members = []
    while time.time() < deadline:
        executions = client.get("/api/executions").json()
        members = [
            e for e in executions if e.get("suite_run_id") == suite_run["suite_run_id"]
        ]
        if len(members) == 2 and all(e["status"] == "passed" for e in members):
            break
        time.sleep(0.3)
    assert len(members) == 2, members
    assert all(e["status"] == "passed" for e in members)

    # Unknown suite -> 404
    missing = client.post(
        "/api/executions/suite", json={"project_id": project_id, "suite": "Nope"}
    )
    assert missing.status_code == 404


def test_reports_generated_and_compare(client):
    reports = client.get("/api/reports").json()
    finished = [r for r in reports if r["status"] in ("passed", "failed")]
    assert len(finished) >= 2

    html = client.get(f"/api/reports/{finished[0]['id']}/html")
    assert html.status_code == 200
    assert "Maestro Report" in html.text  # report title
    assert "Environment" in html.text  # Allure-style environment section
    assert "Steps" in html.text

    comparison = client.post(
        "/api/reports/compare",
        json={"execution_a": finished[0]["id"], "execution_b": finished[1]["id"]},
    )
    assert comparison.status_code == 200
    assert "step_diffs" in comparison.json()


def test_device_config_with_encrypted_credentials(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    created = client.post(
        "/api/configs",
        json={
            "project_id": project_id,
            "config_type": "ssh",
            "label": "Bench target",
            "settings": {"host": "192.168.1.50", "port": 22, "username": "root"},
            "credentials": {"password": "super-secret"},
        },
    )
    assert created.status_code == 201
    config = created.json()
    # The password must never appear in API responses.
    assert "super-secret" not in created.text
    assert "password" in config["credential_keys"]

    listed = client.get("/api/configs", params={"project_id": project_id}).json()
    assert any(c["label"] == "Bench target" for c in listed)


def test_ssh_credentials_flow_from_bound_target(client):
    """A step bound to an SSH target must send that target's saved password —
    paramiko should attempt the connection, not report 'no credentials'."""
    project_id = client.get("/api/projects").json()[0]["id"]
    cfg = client.post(
        "/api/configs",
        json={
            "project_id": project_id,
            "config_type": "ssh",
            "label": "Cred target",
            "settings": {"host": "192.0.2.1", "port": 22, "username": "tester"},
            "credentials": {"password": "pw123"},
        },
    ).json()
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "SSHbind",
            "steps": [
                {
                    "step_number": 1,
                    "action": "ssh.execute_command",
                    "parameters": {
                        "command": "echo hi",
                        "device_config_id": cfg["id"],
                        "connect_timeout": 1,
                        "allow_agent": False,
                        "look_for_keys": False,
                    },
                },
            ],
        },
    ).json()
    started = client.post("/api/executions", json={"test_case_id": tc["id"]})
    rid = started.json()["id"]
    final = _wait_for_execution(client, rid, timeout=25)
    step = final["steps"][0]
    # If the password flowed, paramiko tried to connect (timeout/refused) — it
    # did NOT short-circuit with the "no credentials" message.
    assert step["status"] == "failed"
    assert "No SSH credentials" not in (step["error_message"] or ""), step["error_message"]


def test_schedule_crud_date_based(client):
    from datetime import datetime, timedelta

    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "Scheduled tc",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "tick"}}
            ],
        },
    ).json()

    # once without run_at -> 422
    bad = client.post(
        "/api/schedules", json={"test_case_id": tc["id"], "schedule_type": "once"}
    )
    assert bad.status_code == 422

    # once in the past -> 422
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    bad = client.post(
        "/api/schedules",
        json={"test_case_id": tc["id"], "schedule_type": "once", "run_at": past},
    )
    assert bad.status_code == 422

    # once in the future -> ok
    future = (datetime.now() + timedelta(days=1)).isoformat()
    created = client.post(
        "/api/schedules",
        json={"test_case_id": tc["id"], "schedule_type": "once", "run_at": future},
    )
    assert created.status_code == 201
    schedule = created.json()
    assert schedule["next_run_at"] is not None
    assert schedule["description"].startswith("Once on")

    # weekly with day + time
    weekly = client.post(
        "/api/schedules",
        json={
            "test_case_id": tc["id"],
            "schedule_type": "weekly",
            "time_of_day": "09:00",
            "weekday": 0,
        },
    ).json()
    assert "Monday" in weekly["description"]

    # daily missing time -> 422
    bad = client.post(
        "/api/schedules", json={"test_case_id": tc["id"], "schedule_type": "daily"}
    )
    assert bad.status_code == 422

    toggled = client.post(f"/api/schedules/{schedule['id']}/toggle").json()
    assert toggled["enabled"] is False

    assert client.delete(f"/api/schedules/{schedule['id']}").status_code == 204
    assert client.delete(f"/api/schedules/{weekly['id']}").status_code == 204


def test_delete_test_case_with_history_cascades(client):
    """Regression: deleting a test case with executions/versions/schedules
    used to fail with a FOREIGN KEY constraint error."""
    from datetime import datetime, timedelta

    project_id = client.get("/api/projects").json()[0]["id"]
    tc = client.post(
        "/api/test-cases",
        json={
            "project_id": project_id,
            "name": "To be deleted",
            "steps": [
                {"step_number": 1, "action": "system.echo", "parameters": {"message": "x"}}
            ],
        },
    ).json()

    # Build up history: an execution (with report), and a schedule.
    started = client.post("/api/executions", json={"test_case_id": tc["id"]}).json()
    final = _wait_for_execution(client, started["id"])
    assert final["status"] == "passed"
    client.post(
        "/api/schedules",
        json={
            "test_case_id": tc["id"],
            "schedule_type": "once",
            "run_at": (datetime.now() + timedelta(days=1)).isoformat(),
        },
    )

    # Bulk delete must succeed despite versions/executions/schedules.
    response = client.post("/api/test-cases/bulk-delete", json={"ids": [tc["id"]]})
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] == 1
    assert client.get(f"/api/test-cases/{tc['id']}").status_code == 404
    # Execution history is gone too.
    assert client.get(f"/api/executions/{started['id']}").status_code == 404


def test_plugins_listing_and_toggle(client):
    plugins = client.get("/api/plugins").json()
    names = {p["name"] for p in plugins}
    assert {"ssh", "adb", "system"} <= names

    disabled = client.post("/api/plugins/dlt/disable")
    assert disabled.status_code == 200
    plugins = {p["name"]: p for p in client.get("/api/plugins").json()}
    assert plugins["dlt"]["enabled"] is False
    client.post("/api/plugins/dlt/enable")


def test_datasets_crud(client):
    project_id = client.get("/api/projects").json()[0]["id"]
    created = client.post(
        "/api/datasets",
        json={
            "project_id": project_id,
            "name": "login-data",
            "data_type": "csv",
            "raw": "user,pin\nalice,1234\nbob,5678",
        },
    )
    assert created.status_code == 201
    dataset = created.json()
    assert dataset["content"] == [
        {"user": "alice", "pin": "1234"},
        {"user": "bob", "pin": "5678"},
    ]


def test_audit_logs_recorded(client):
    logs = client.get("/api/admin/audit-logs").json()
    assert len(logs) > 0
    actions = {entry["action"] for entry in logs}
    assert "create" in actions
    assert "run" in actions


def test_dashboard_stats(client):
    stats = client.get("/api/dashboard").json()
    assert stats["total_executions"] >= 4
    assert "pass_rate" in stats
    assert "trend" in stats


def test_adapter_health_endpoint(client):
    health = client.get("/api/connections/health").json()
    assert health["system"]["success"]
