"""Real Allure results + JUnit XML export for Maestro executions.

Maestro doesn't run on pytest, so it can't use ``allure-pytest`` directly — but
the Allure *report* is just the Allure CLI rendering an ``allure-results/``
folder of JSON files. This module emits that documented format straight from the
execution records in the DB, so the genuine Allure UI (overview, timeline,
graphs, and history/trends across runs) works via::

    allure generate <results_dir> -o <html_dir> --clean
    allure serve   <results_dir>

It also emits a standard JUnit XML for CI dashboards and Jira/Xray import.

Nothing here mimics Allure's look (unlike the legacy HTML reporter) — it
produces the real artifacts the official tools consume.
"""

from __future__ import annotations

import json
import mimetypes
import platform
import shutil
import socket
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterable, Optional
from xml.sax.saxutils import escape, quoteattr

from backend import __version__
from backend.config import ARTIFACTS_DIR
from backend.database import session_scope
from backend.models.artifact import ExecutionArtifact
from backend.models.execution import Execution
from backend.models.project import TestCase

# Maestro status -> Allure status. Allure knows: passed, failed, broken,
# skipped, unknown. We map a tooling/infra "error" to "broken" (Allure's term
# for "the test couldn't run"), and a manual stop to "broken" as well.
_ALLURE_STATUS = {
    "passed": "passed",
    "failed": "failed",
    "error": "broken",
    "stopped": "broken",
    "skipped": "skipped",
    "pending": "skipped",
    "running": "unknown",
}

_EXTRA_MIME = {
    ".dlt": "application/octet-stream",
    ".log": "text/plain",
    ".txt": "text/plain",
    ".mp4": "video/mp4",
    ".webp": "image/webp",
}


def _ms(dt) -> Optional[int]:
    """Epoch milliseconds for a datetime (Allure uses ms), or None."""
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def _mime_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in _EXTRA_MIME:
        return _EXTRA_MIME[suffix]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _copy_attachment(src: str, results_dir: Path) -> Optional[dict[str, str]]:
    """Copy an artifact into the results dir under an Allure attachment name."""
    source = Path(src)
    if not source.exists() or not source.is_file():
        return None
    dest_name = f"{uuid.uuid4().hex}-attachment{source.suffix}"
    shutil.copy2(source, results_dir / dest_name)
    return {"name": source.name, "source": dest_name, "type": _mime_for(src)}


def _step_dict(step, artifacts: Iterable, results_dir: Path) -> dict[str, Any]:
    start = _ms(step.started_at)
    stop = None
    if start is not None and step.duration_seconds:
        stop = start + int(step.duration_seconds * 1000)
    attachments = []
    for art in artifacts:
        copied = _copy_attachment(art.file_path, results_dir)
        if copied:
            attachments.append(copied)
    name = f"{step.step_number}. {step.label or step.action}".strip(". ")
    detail: dict[str, str] = {}
    if step.error_message:
        detail["message"] = step.error_message
    if step.actual_output:
        detail["trace"] = step.actual_output
    return {
        "name": name or step.action or "step",
        "status": _ALLURE_STATUS.get(step.status, "unknown"),
        "statusDetails": detail,
        "stage": "finished",
        "start": start,
        "stop": stop if stop is not None else start,
        "steps": [],
        "attachments": attachments,
        "parameters": [{"name": "action", "value": step.action}],
    }


def _build_result(execution, steps, artifacts, tc, results_dir: Path) -> dict[str, Any]:
    by_step: dict[Optional[int], list] = {}
    for art in artifacts:
        by_step.setdefault(art.step_number, []).append(art)

    tc_name = tc.name if tc else f"Test case #{execution.test_case_id}"
    suite = (getattr(tc, "test_type", "") or "Maestro") if tc else "Maestro"
    scenario = (getattr(tc, "scenario", "") or "") if tc else ""

    allure_steps = [_step_dict(s, by_step.get(s.step_number, []), results_dir) for s in steps]

    first_failure = next(
        (s for s in steps if s.status in ("failed", "error")), None
    )
    status_details: dict[str, str] = {}
    if first_failure is not None:
        status_details["message"] = (
            first_failure.error_message or f"Step {first_failure.step_number} failed"
        )
        if first_failure.actual_output:
            status_details["trace"] = first_failure.actual_output

    labels = [
        {"name": "suite", "value": suite},
        {"name": "framework", "value": "maestro"},
        {"name": "host", "value": socket.gethostname()},
        {"name": "thread", "value": execution.correlation_id or f"run-{execution.id}"},
    ]
    if scenario:
        labels.append({"name": "feature", "value": scenario})
    if execution.triggered_by:
        labels.append({"name": "owner", "value": execution.triggered_by})

    start = _ms(execution.started_at)
    stop = _ms(execution.ended_at)
    if stop is None and start is not None and execution.duration_seconds:
        stop = start + int(execution.duration_seconds * 1000)

    # Run-level attachments (artifacts not tied to a specific step).
    run_attachments = []
    for art in by_step.get(None, []):
        copied = _copy_attachment(art.file_path, results_dir)
        if copied:
            run_attachments.append(copied)

    return {
        "uuid": uuid.uuid4().hex,
        # Stable across runs of the same test case -> Allure history/trends line up.
        "historyId": f"maestro-tc-{execution.test_case_id}",
        "name": tc_name,
        "fullName": f"{suite} / {tc_name}",
        "status": _ALLURE_STATUS.get(execution.status, "unknown"),
        "statusDetails": status_details,
        "stage": "finished",
        "start": start,
        "stop": stop if stop is not None else start,
        "labels": labels,
        "parameters": [
            {"name": "execution", "value": f"RUN-{execution.id}"},
            {"name": "mode", "value": execution.execution_mode},
            {"name": "target", "value": execution.target_label or "local"},
        ],
        "steps": allure_steps,
        "attachments": run_attachments,
    }


def _write_side_files(results_dir: Path, execution) -> None:
    """environment.properties, executor.json and categories.json for Allure."""
    env = {
        "Host": socket.gethostname(),
        "Platform": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "Maestro": __version__,
        "Execution.mode": execution.execution_mode,
        "Target": execution.target_label or "local",
    }
    (results_dir / "environment.properties").write_text(
        "\n".join(f"{k}={v}" for k, v in env.items()), encoding="utf-8"
    )
    (results_dir / "executor.json").write_text(
        json.dumps(
            {
                "name": "Maestro",
                "type": "maestro",
                "buildName": f"RUN-{execution.id}",
                "reportName": f"Maestro execution {execution.id}",
            }
        ),
        encoding="utf-8",
    )
    (results_dir / "categories.json").write_text(
        json.dumps(
            [
                {"name": "Failed steps", "matchedStatuses": ["failed"]},
                {"name": "Broken / infrastructure", "matchedStatuses": ["broken"]},
                {"name": "Skipped", "matchedStatuses": ["skipped"]},
            ]
        ),
        encoding="utf-8",
    )


def export_allure_results(execution_id: int, out_dir: Optional[Path] = None) -> Path:
    """Write an ``allure-results/`` folder for one execution and return its path."""
    results_dir = out_dir or (ARTIFACTS_DIR / "allure" / f"execution_{execution_id}")
    if results_dir.exists():
        shutil.rmtree(results_dir, ignore_errors=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    with session_scope() as db:
        execution = db.get(Execution, execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")
        steps = list(execution.steps)
        artifacts = (
            db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_id == execution_id)
            .all()
        )
        tc = db.get(TestCase, execution.test_case_id)
        result = _build_result(execution, steps, artifacts, tc, results_dir)
        _write_side_files(results_dir, execution)

    (results_dir / f"{result['uuid']}-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return results_dir


def export_allure_zip(execution_id: int) -> Path:
    """Zip an execution's allure-results so it can be downloaded and rendered."""
    results_dir = export_allure_results(execution_id)
    zip_path = ARTIFACTS_DIR / "allure" / f"allure_results_{execution_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in results_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(results_dir))
    return zip_path


def maybe_generate_allure_html(execution_id: int) -> Optional[Path]:
    """If the Allure CLI is installed, render the real HTML report and return it."""
    allure = shutil.which("allure")
    if not allure:
        return None
    import subprocess

    results_dir = export_allure_results(execution_id)
    html_dir = ARTIFACTS_DIR / "allure" / f"report_{execution_id}"
    subprocess.run(
        [allure, "generate", str(results_dir), "-o", str(html_dir), "--clean"],
        check=False,
        capture_output=True,
    )
    index = html_dir / "index.html"
    return html_dir if index.exists() else None


# ---- JUnit XML -------------------------------------------------------------

_JUNIT_STATUS = {"passed": "passed", "failed": "failed", "error": "error", "skipped": "skipped"}


def _junit_testcase(step, classname: str) -> str:
    name = quoteattr(f"{step.step_number}. {step.label or step.action}".strip(". ") or step.action)
    time = f"{step.duration_seconds or 0:.3f}"
    inner = ""
    if step.status in ("failed", "error"):
        tag = "error" if step.status == "error" else "failure"
        msg = quoteattr((step.error_message or "step failed")[:500])
        body = escape(step.actual_output or step.error_message or "")
        inner = f"<{tag} message={msg}>{body}</{tag}>"
    elif step.status == "skipped":
        inner = "<skipped/>"
    elif step.actual_output:
        inner = f"<system-out>{escape(step.actual_output)}</system-out>"
    return f'    <testcase name={name} classname={quoteattr(classname)} time="{time}">{inner}</testcase>'


def build_junit_xml(execution, steps, tc) -> str:
    tc_name = tc.name if tc else f"Test case #{execution.test_case_id}"
    tests = len(steps)
    failures = sum(1 for s in steps if s.status == "failed")
    errors = sum(1 for s in steps if s.status == "error")
    skipped = sum(1 for s in steps if s.status == "skipped")
    total_time = f"{execution.duration_seconds or 0:.3f}"
    ts = execution.started_at.isoformat() if execution.started_at else ""
    cases = "\n".join(_junit_testcase(s, tc_name) for s in steps)
    suite_attrs = (
        f'name={quoteattr(tc_name)} tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}" time="{total_time}" timestamp={quoteattr(ts)}'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuites name="Maestro" tests="{tests}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}" time="{total_time}">\n'
        f"  <testsuite {suite_attrs}>\n{cases}\n  </testsuite>\n</testsuites>\n"
    )


def export_junit_xml(execution_id: int) -> str:
    """Return a JUnit XML string for an execution (each step is a testcase)."""
    with session_scope() as db:
        execution = db.get(Execution, execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")
        steps = list(execution.steps)
        tc = db.get(TestCase, execution.test_case_id)
        return build_junit_xml(execution, steps, tc)
