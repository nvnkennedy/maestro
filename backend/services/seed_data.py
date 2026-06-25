"""First-run seed data — realistic automotive suites, scenarios and test cases.

Test cases are grouped Suite → Scenario → Test Case (suite is stored in
``test_type``, scenario in ``scenario``). Seeding only happens when the
database has no test cases yet.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from backend.models.project import Project, TestCase, TestStep
from backend.services.versioning_service import snapshot_version
from backend.utils.logger import get_logger

logger = get_logger("maestro.seed")


def _step(number: int, label: str, action: str, params: dict, timeout: int = 30,
          retries: int = 0) -> dict:
    return {
        "step_number": number,
        "action": action,
        "parameters": {"_label": label, **params},
        "timeout_seconds": timeout,
        "retry_count": retries,
    }


_SEED_CASES: list[dict] = [
    {
        "suite": "Smoke Tests",
        "scenario": "System Health Check",
        "name": "System Health Check",
        "description": "End-to-end health sweep across QNX, Android and bench hardware",
        "steps": [
            _step(1, "SSH uname -a on QNX", "ssh.execute_command",
                  {"command": "uname -a", "expect_contains": "QNX"}),
            _step(2, "SSH uptime on RichOS", "ssh.execute_command",
                  {"command": "uptime"}),
            _step(3, "ADB get build ID", "adb.shell",
                  {"command": "getprop ro.build.id"}),
            _step(4, "Capture webcam image", "camera.screenshot", {}, timeout=60),
            _step(5, "SCP download syslog", "ssh.download_file",
                  {"remote_path": "/var/log/syslog", "local_path": "data/artifacts/syslog.txt"},
                  timeout=120),
            _step(6, "Power cycle DUT", "power.power_cycle", {"cycle_delay": 3},
                  timeout=120),
            _step(7, "Wait 10s for boot", "system.wait", {"seconds": 10}, timeout=30),
        ],
    },
    {
        "suite": "Smoke Tests",
        "scenario": "Boot Validation",
        "name": "QNX Boot Check",
        "description": "Power cycle the unit and verify boot markers in DLT and serial logs",
        "steps": [
            _step(1, "Start DLT capture", "dlt.start_capture",
                  {"host": "192.168.1.10", "port": 3490}),
            _step(2, "Power cycle DUT", "power.power_cycle", {"cycle_delay": 3},
                  timeout=120),
            _step(3, "Wait for boot banner on serial", "serial.wait_for_pattern",
                  {"port": "COM3", "baudrate": 115200, "pattern": "Boot complete",
                   "duration": 60}, timeout=90, retries=1),
            _step(4, "Verify BOOT_COMPLETE in DLT", "dlt.verify_pattern",
                  {"pattern": "BOOT_COMPLETE"}),
            _step(5, "Stop DLT capture", "dlt.stop_capture", {}),
        ],
    },
    {
        "suite": "Smoke Tests",
        "scenario": "Connectivity",
        "name": "Verify QNX SSH",
        "description": "Confirm the QNX target is reachable and responsive over SSH",
        "steps": [
            _step(1, "Connect to QNX and verify", "ssh.execute_command",
                  {"command": "echo maestro-ok", "expect_contains": "maestro-ok"}),
            _step(2, "Run uname -a", "ssh.execute_command", {"command": "uname -a"}),
            _step(3, "Wait 3 seconds", "system.wait", {"seconds": 3}),
            _step(4, "Assert exit code is 0", "system.assert_contains",
                  {"text": "{{steps.1.output}}", "expected": "maestro-ok"}),
            _step(5, "Capture verification photo", "camera.screenshot", {}, timeout=60),
        ],
    },
    {
        "suite": "Smoke Tests",
        "scenario": "Connectivity",
        "name": "Check ADB Device",
        "description": "Validate the Android side is online and debuggable",
        "steps": [
            _step(1, "List ADB devices", "adb.list_devices", {}),
            _step(2, "Read Android version", "adb.shell",
                  {"command": "getprop ro.build.version.release"}),
            _step(3, "Dump recent logcat", "adb.logcat_dump", {"lines": 200}, timeout=60),
        ],
    },
    {
        "suite": "Regression",
        "scenario": "Power Cycle Endurance",
        "name": "Power Cycle 10x",
        "description": "Repeated power cycles with SSH liveness verification after each",
        "steps": [
            _step(1, "Power cycle (looped 10x)", "power.power_cycle",
                  {"cycle_delay": 3, "_loop": 10}, timeout=120),
            _step(2, "Wait for system to settle", "system.wait", {"seconds": 10}),
            _step(3, "Verify SSH is back", "ssh.execute_command",
                  {"command": "echo alive", "expect_contains": "alive"}, retries=2),
        ],
    },
    {
        "suite": "Regression",
        "scenario": "Camera Capture",
        "name": "Camera Capture Test",
        "description": "Capture a frame from the bench camera and archive it",
        "steps": [
            _step(1, "List capture devices", "camera.list_devices", {}),
            _step(2, "Capture frame", "camera.screenshot", {}, timeout=60),
            _step(3, "Record 5s clip", "camera.record_video", {"duration": 5},
                  timeout=60),
        ],
    },
    {
        "suite": "Sanity Tests",
        "scenario": "Self Test",
        "name": "Maestro Self Test",
        "description": "Runs without any bench hardware — try this one first!",
        "steps": [
            _step(1, "Emit greeting", "system.echo", {"message": "MAESTRO READY"}),
            _step(2, "Verify greeting", "system.assert_contains",
                  {"text": "{{steps.1.output}}", "expected": "READY"}),
            _step(3, "Simulate boot wait", "system.wait", {"seconds": 1}),
            _step(4, "Run sandboxed script", "system.run_script",
                  {"interpreter": "python", "script": "print('sandbox alive')"},
                  timeout=90),
        ],
    },
]


def seed_demo_data(db: Session) -> int:
    """Insert sample suites/test cases when the database is empty."""
    if db.query(TestCase.id).first() is not None:
        return 0
    project = db.query(Project).first()
    if project is None:
        return 0

    created = 0
    for case in _SEED_CASES:
        test_case = TestCase(
            project_id=project.id,
            name=case["name"],
            description=case["description"],
            test_type=case["suite"],
            scenario=case["scenario"],
            created_by="maestro",
        )
        db.add(test_case)
        db.flush()
        for step in case["steps"]:
            db.add(
                TestStep(
                    test_case_id=test_case.id,
                    step_number=step["step_number"],
                    action=step["action"],
                    parameters=json.dumps(step["parameters"]),
                    timeout_seconds=step["timeout_seconds"],
                    retry_count=step["retry_count"],
                )
            )
        db.flush()
        db.refresh(test_case)
        snapshot_version(db, test_case, created_by="maestro")
        created += 1
    logger.info("demo_data_seeded", test_cases=created)
    return created
