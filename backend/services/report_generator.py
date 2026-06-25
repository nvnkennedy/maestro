"""Allure-style HTML report generation for executions.

Reports are fully self-contained: collapsible step cards with parameters,
full output, retry info and attachments. Image attachments (screenshots)
are embedded inline as base64 so the report can be shared as a single file.
"""

from __future__ import annotations

import base64
import html
import json
import platform
import socket
from datetime import datetime
from pathlib import Path

from backend import __version__
from backend.config import FRONTEND_DIST, REPORTS_DIR, ROOT_DIR
from backend.database import session_scope
from backend.models.artifact import ExecutionArtifact
from backend.models.execution import Execution
from backend.models.project import Project, TestCase, TestStep
from backend.utils.helpers import safe_json_loads
from backend.utils.matching import expectation_rules, text_matches

_STATUS_COLORS = {
    "passed": "#10B981",
    "failed": "#EF4444",
    "error": "#EF4444",
    "skipped": "#94A3B8",
    "stopped": "#F59E0B",
    "running": "#3B82F6",
    "pending": "#94A3B8",
    "paused": "#F59E0B",
}

_STATUS_ICONS = {"passed": "✔", "failed": "✘", "skipped": "➖", "error": "✘", "stopped": "■"}

_ADAPTER_COLORS = {
    "ssh": "#F97316", "adb": "#10B981", "power": "#EF4444", "camera": "#A855F7",
    "dlt": "#06B6D4", "serial": "#EAB308", "etfw": "#EC4899", "system": "#0EA5E9",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_MAX_IMAGE_BYTES = 12 * 1024 * 1024  # embed screenshots up to ~12 MB
_MAX_FILE_BYTES = 20 * 1024 * 1024   # embed other attachments up to ~20 MB
_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
}

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Maestro Report — RUN-{execution_id}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Inter, sans-serif; background: #0F172A; color: #F1F5F9; padding: 32px; max-width: 1100px; margin: 0 auto; }}
  a {{ color: #818CF8; }}
  h1 {{ font-size: 24px; }}
  h2 {{ font-size: 16px; margin-bottom: 10px; color: #CBD5E1; }}
  .muted {{ color: #94A3B8; font-size: 13px; }}
  .grid {{ display: flex; gap: 14px; margin: 22px 0; flex-wrap: wrap; }}
  .card {{ background: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 14px 22px; min-width: 130px; }}
  .card .value {{ font-size: 26px; font-weight: 700; }}
  .card .label {{ color: #94A3B8; font-size: 11px; text-transform: uppercase; letter-spacing: .08em; margin-top: 2px; }}
  .badge {{ display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; color: #fff; }}
  .chip {{ display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; font-family: Consolas, monospace; border: 1px solid; }}
  table.env {{ border-collapse: collapse; width: 100%; }}
  table.env td {{ padding: 6px 10px; border-bottom: 1px solid #334155; font-size: 13px; }}
  table.env td:first-child {{ color: #94A3B8; width: 220px; }}
  .timeline {{ display: flex; height: 14px; border-radius: 7px; overflow: hidden; margin: 14px 0 4px; border: 1px solid #334155; }}
  .timeline div {{ height: 100%; }}
  .section {{ margin-top: 30px; }}
  details.step {{ background: #1E293B; border: 1px solid #334155; border-radius: 10px; margin-bottom: 8px; overflow: hidden; }}
  details.step[open] {{ border-color: #475569; }}
  details.step > summary {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; list-style: none; }}
  details.step > summary::-webkit-details-marker {{ display: none; }}
  .step-num {{ width: 26px; height: 26px; border-radius: 50%; background: #334155; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }}
  .step-name {{ flex: 1; font-weight: 600; font-size: 14px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .step-meta {{ color: #94A3B8; font-size: 12px; white-space: nowrap; }}
  .step-body {{ padding: 4px 18px 16px 54px; }}
  .kv {{ font-size: 12px; color: #94A3B8; margin: 8px 0 4px; text-transform: uppercase; letter-spacing: .06em; }}
  pre {{ background: #0B1220; border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; font-family: 'Fira Code', Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; max-height: 320px; overflow: auto; }}
  pre.error {{ border-color: #7F1D1D; background: #1A0B0B; color: #FCA5A5; }}
  .attachment {{ margin-top: 10px; }}
  .attachment img {{ max-width: 100%; border-radius: 8px; border: 1px solid #334155; }}
  .attachment .file {{ display: inline-block; background: #0B1220; border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; font-family: Consolas, monospace; font-size: 12px; color: #67E8F9; }}
  footer {{ margin-top: 40px; color: #475569; font-size: 12px; text-align: center; }}
</style>
</head>
<body>
  <div style="display:flex;align-items:center;gap:14px">
    <div style="flex-shrink:0">{logo_svg}</div>
    <div>
      <h1>{test_case_name}</h1>
      <div class="muted">RUN-{execution_id} &middot; {suite} / {scenario} &middot; started {started_at}</div>
    </div>
    <div style="margin-left:auto"><span class="badge" style="background:{status_color};font-size:14px;padding:6px 18px">{status}</span></div>
  </div>

  <div class="grid">
    <div class="card"><div class="value">{total_steps}</div><div class="label">Steps</div></div>
    <div class="card"><div class="value" style="color:#10B981">{passed_steps}</div><div class="label">Passed</div></div>
    <div class="card"><div class="value" style="color:#EF4444">{failed_steps}</div><div class="label">Failed</div></div>
    <div class="card"><div class="value" style="color:#94A3B8">{skipped_steps}</div><div class="label">Skipped</div></div>
    <div class="card"><div class="value" style="color:#F59E0B">{duration}</div><div class="label">Duration</div></div>
    <div class="card"><div class="value" style="color:#A855F7">{retries}</div><div class="label">Retries</div></div>
    <div class="card"><div class="value" style="color:#06B6D4">{attachment_count}</div><div class="label">Attachments</div></div>
  </div>

  <div class="timeline">{timeline}</div>
  <div class="muted">Step timeline (width proportional to duration)</div>

  <div class="section">
    <h2>Steps</h2>
    {step_cards}
  </div>

  {global_attachments}

  <div class="section">
    <h2>Environment</h2>
    <table class="env">{env_rows}</table>
  </div>

  <footer>Generated by Maestro v{version} &middot; mode: {mode} &middot; correlation: {correlation_id}</footer>
</body>
</html>
"""


def _load_logo(size: int = 46) -> str:
    """Inline the app logo so the report uses the same brand as the dashboard."""
    for candidate in (
        FRONTEND_DIST / "maestro-logo.svg",
        ROOT_DIR / "frontend" / "public" / "maestro-logo.svg",
    ):
        if candidate.exists():
            svg = candidate.read_text(encoding="utf-8")
            return svg.replace('width="64" height="64"', f'width="{size}" height="{size}"')
    return ""  # graceful: header just renders without a mark


def _fmt_dt(value: str | None) -> str:
    """ISO timestamp -> human readable, e.g. '16 Jun 2026, 21:56:50'."""
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    return dt.strftime("%d %b %Y, %H:%M:%S")


def _chip(action: str) -> str:
    adapter = action.split(".")[0]
    color = _ADAPTER_COLORS.get(adapter, "#6366F1")
    return (
        f'<span class="chip" style="color:{color};border-color:{color}55;'
        f'background:{color}1f">{html.escape(action)}</span>'
    )


def _data_uri(path: Path, mime: str) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _embed_attachment(artifact: dict) -> str:
    """Render an attachment self-contained: images shown full + clickable,
    every other existing file embedded as a downloadable link so it opens
    straight from the report regardless of where the HTML is viewed."""
    path = Path(artifact["file_path"])
    name = html.escape(path.name)
    kind = html.escape(str(artifact.get("artifact_type", "file")))

    if not path.exists():
        return (
            f'<div class="attachment"><span class="file">📎 [{kind}] '
            f"{html.escape(str(path))} (missing)</span></div>"
        )

    size = path.stat().st_size
    size_text = f"{size // 1024} KB" if size >= 1024 else f"{size} B"
    ext = path.suffix.lower()

    # Images: embed inline, full size, and click to open the original in a tab.
    if ext in _IMAGE_EXTS and size <= _MAX_IMAGE_BYTES:
        uri = _data_uri(path, _MIME_BY_EXT.get(ext, "image/png"))
        return (
            f'<div class="attachment"><div class="kv">📎 {kind}: {name} ({size_text})</div>'
            f'<a href="{uri}" target="_blank" rel="noopener" title="Open full image in a new tab">'
            f'<img src="{uri}" alt="{name}"></a></div>'
        )

    # Everything else: a real download link (data URI) when small enough to embed.
    if size <= _MAX_FILE_BYTES:
        uri = _data_uri(path, "application/octet-stream")
        return (
            f'<div class="attachment"><a class="file" href="{uri}" download="{name}" '
            f'title="Download {name}">📎 [{kind}] {name} ({size_text}) ⬇</a></div>'
        )

    # Too large to embed — show the path so it can be located on the runner.
    return (
        f'<div class="attachment"><span class="file">📎 [{kind}] '
        f"{html.escape(str(path))} ({size_text} — too large to embed)</span></div>"
    )


def _step_card(step: dict, params: dict, attachments: list[dict]) -> str:
    status = step["status"]
    color = _STATUS_COLORS.get(status, "#64748B")
    icon = _STATUS_ICONS.get(status, "·")
    label = step.get("label") or step["action"]
    duration = step.get("duration_seconds")
    meta = f"{duration:.2f}s" if duration is not None else "—"
    if step.get("attempts", 0) > 1:
        meta += f" · {step['attempts']} attempts"

    body_parts: list[str] = []
    shown_params = {k: v for k, v in params.items() if k != "_label"}
    if shown_params:
        body_parts.append(
            '<div class="kv">Parameters</div><pre>'
            + html.escape(json.dumps(shown_params, indent=2, default=str))
            + "</pre>"
        )
    # Expected-vs-actual comparison when the step asserts on output. Supports
    # multiple expectations — each shown with its own matched/not-matched badge.
    actual = step.get("actual_output", "")
    for rule in expectation_rules(params):
        matched = text_matches(actual, rule["text"], rule["mode"])
        badge = (
            '<span style="color:#10B981">✔ matched</span>'
            if matched
            else '<span style="color:#EF4444">✘ not matched</span>'
        )
        body_parts.append(
            f'<div class="kv">Expected ({html.escape(rule["mode"])}) — {badge}</div>'
            f'<pre>{html.escape(rule["text"])}</pre>'
        )
    if step.get("actual_output"):
        body_parts.append(
            '<div class="kv">Actual output</div><pre>'
            + html.escape(step["actual_output"])
            + "</pre>"
        )
    if step.get("error_message"):
        body_parts.append(
            '<div class="kv">Error</div><pre class="error">'
            + html.escape(step["error_message"])
            + "</pre>"
        )
    for artifact in attachments:
        body_parts.append(_embed_attachment(artifact))
    if not body_parts:
        body_parts.append('<div class="muted">No output recorded.</div>')

    return (
        '<details class="step">'
        "<summary>"
        f'<span class="step-num">{step["step_number"]}</span>'
        f'<span style="color:{color};font-weight:900">{icon}</span>'
        f'<span class="step-name">{html.escape(label)}</span>'
        f"{_chip(step['action'])}"
        f'<span class="step-meta">{meta}</span>'
        f'<span class="badge" style="background:{color}">{status}</span>'
        "</summary>"
        f'<div class="step-body">{"".join(body_parts)}</div>'
        "</details>"
    )


def _collect(execution_id: int) -> dict:
    """Gather everything a report needs from the DB (format-agnostic)."""
    with session_scope() as db:
        execution = db.get(Execution, execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")
        test_case = db.get(TestCase, execution.test_case_id)
        project = db.get(Project, test_case.project_id) if test_case else None
        steps = [s.to_dict() for s in execution.steps]
        step_ids = [s["test_step_id"] for s in steps if s.get("test_step_id")]
        test_steps = {
            ts.id: safe_json_loads(ts.parameters, {})
            for ts in db.query(TestStep).filter(TestStep.id.in_(step_ids)).all()
        }
        artifacts = [
            a.to_dict()
            for a in db.query(ExecutionArtifact)
            .filter(ExecutionArtifact.execution_id == execution_id)
            .all()
        ]
        exec_data = execution.to_dict()
        tc_name = test_case.name if test_case else f"Test case {execution.test_case_id}"
        suite = test_case.test_type if test_case else ""
        scenario = test_case.scenario if test_case else ""
        authored_by = test_case.created_by if test_case else ""
        project_name = project.name if project else ""

    by_step: dict[int, list[dict]] = {}
    unassigned: list[dict] = []
    for artifact in artifacts:
        if artifact.get("step_number"):
            by_step.setdefault(int(artifact["step_number"]), []).append(artifact)
        else:
            unassigned.append(artifact)

    return {
        "execution_id": execution_id,
        "exec_data": exec_data,
        "tc_name": tc_name,
        "suite": suite,
        "scenario": scenario,
        "authored_by": authored_by,
        "project_name": project_name,
        "steps": steps,
        "test_steps": test_steps,
        "artifacts": artifacts,
        "by_step": by_step,
        "unassigned": unassigned,
        "passed": sum(1 for s in steps if s["status"] == "passed"),
        "failed": sum(1 for s in steps if s["status"] == "failed"),
        "skipped": sum(1 for s in steps if s["status"] == "skipped"),
        "retries": sum(max(0, (s.get("attempts") or 1) - 1) for s in steps),
    }


def _env_of(data: dict) -> dict:
    exec_data = data["exec_data"]
    return {
        "Project": data["project_name"],
        "Suite / Scenario": f"{data['suite']} / {data['scenario']}",
        "Authored by": data.get("authored_by") or "—",
        "Execution mode": exec_data.get("execution_mode", "serial"),
        "Triggered by": exec_data.get("triggered_by") or "admin",
        "Started": _fmt_dt(exec_data.get("started_at")),
        "Ended": _fmt_dt(exec_data.get("ended_at")),
        "Host": socket.gethostname(),
        "Platform": f"{platform.system()} {platform.release()}",
        "Python": platform.python_version(),
        "Maestro": __version__,
        "Correlation ID": exec_data.get("correlation_id", ""),
    }


def _render_allure(data: dict) -> str:
    steps = data["steps"]
    exec_data = data["exec_data"]
    total_duration = sum(s.get("duration_seconds") or 0 for s in steps) or 1
    timeline = "".join(
        f'<div style="width:{max(1, (s.get("duration_seconds") or 0) / total_duration * 100):.2f}%;'
        f'background:{_STATUS_COLORS.get(s["status"], "#64748B")}"'
        f' title="Step {s["step_number"]}: {html.escape(s.get("label") or s["action"])} ({s["status"]})"></div>'
        for s in steps
    )
    step_cards = "".join(
        _step_card(
            step,
            data["test_steps"].get(step.get("test_step_id"), {}),
            data["by_step"].get(int(step["step_number"]), []),
        )
        for step in steps
    ) or '<div class="muted">No steps recorded.</div>'
    global_attachments = ""
    if data["unassigned"]:
        global_attachments = (
            '<div class="section"><h2>Run attachments</h2>'
            + "".join(_embed_attachment(a) for a in data["unassigned"])
            + "</div>"
        )
    env_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in _env_of(data).items()
    )
    duration = exec_data.get("duration_seconds")
    return _PAGE.format(
        logo_svg=_load_logo(),
        execution_id=data["execution_id"],
        test_case_name=html.escape(data["tc_name"]),
        suite=html.escape(data["suite"]),
        scenario=html.escape(data["scenario"]),
        started_at=_fmt_dt(exec_data.get("started_at")),
        status=exec_data.get("status", "unknown"),
        status_color=_STATUS_COLORS.get(exec_data.get("status", ""), "#64748B"),
        total_steps=len(steps),
        passed_steps=data["passed"],
        failed_steps=data["failed"],
        skipped_steps=data["skipped"],
        duration=f"{duration:.1f}s" if duration else "—",
        retries=data["retries"],
        attachment_count=len(data["artifacts"]),
        timeline=timeline or '<div style="width:100%;background:#334155"></div>',
        step_cards=step_cards,
        global_attachments=global_attachments,
        env_rows=env_rows,
        version=__version__,
        mode=exec_data.get("execution_mode", "serial"),
        correlation_id=exec_data.get("correlation_id", ""),
    )


def render_report_html(execution_id: int, fmt: str = "allure") -> str:
    """Render an execution's report in the requested format (allure | playwright)."""
    data = _collect(execution_id)
    if fmt == "playwright":
        return _render_playwright(data)
    return _render_allure(data)


def generate_report(execution_id: int) -> Path:
    """Render the default (Allure) HTML report and JSON summary for an execution."""
    data = _collect(execution_id)
    report_path = REPORTS_DIR / f"execution_{execution_id}.html"
    report_path.write_text(_render_allure(data), encoding="utf-8")

    summary = {
        "execution": data["exec_data"],
        "test_case_name": data["tc_name"],
        "suite": data["suite"],
        "scenario": data["scenario"],
        "steps": data["steps"],
        "artifacts": data["artifacts"],
        "totals": {
            "passed": data["passed"],
            "failed": data["failed"],
            "skipped": data["skipped"],
        },
    }
    (REPORTS_DIR / f"execution_{execution_id}.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    return report_path


_SUITE_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Maestro Suite Report — {label}</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family:'Segoe UI',Inter,sans-serif; background:#0F172A; color:#F1F5F9; padding:32px; max-width:1100px; margin:0 auto; }}
  a {{ color:#818CF8; }}
  h1 {{ font-size:24px; }}
  h2 {{ font-size:16px; margin-bottom:10px; color:#CBD5E1; }}
  .muted {{ color:#94A3B8; font-size:13px; }}
  .grid {{ display:flex; gap:14px; margin:22px 0; flex-wrap:wrap; }}
  .card {{ background:#1E293B; border:1px solid #334155; border-radius:12px; padding:14px 22px; min-width:120px; }}
  .card .value {{ font-size:26px; font-weight:700; }}
  .card .label {{ color:#94A3B8; font-size:11px; text-transform:uppercase; letter-spacing:.08em; margin-top:2px; }}
  .badge {{ display:inline-block; padding:3px 12px; border-radius:999px; font-size:12px; font-weight:700; color:#fff; }}
  table.cases {{ border-collapse:collapse; width:100%; margin-top:8px; }}
  table.cases th, table.cases td {{ padding:9px 12px; border-bottom:1px solid #334155; font-size:13px; text-align:left; }}
  table.cases th {{ color:#94A3B8; font-size:11px; text-transform:uppercase; letter-spacing:.06em; }}
  footer {{ margin-top:40px; color:#475569; font-size:12px; text-align:center; }}
</style></head><body>
  <div style="display:flex;align-items:center;gap:14px">
    <div style="flex-shrink:0">{logo_svg}</div>
    <div>
      <h1>{label}</h1>
      <div class="muted">Suite run &middot; {member_count} test case(s) &middot; started {started_at}</div>
    </div>
    <div style="margin-left:auto"><span class="badge" style="background:{status_color};font-size:14px;padding:6px 18px">{status}</span></div>
  </div>
  <div class="grid">
    <div class="card"><div class="value">{member_count}</div><div class="label">Test cases</div></div>
    <div class="card"><div class="value" style="color:#10B981">{passed}</div><div class="label">Passed</div></div>
    <div class="card"><div class="value" style="color:#EF4444">{failed}</div><div class="label">Failed</div></div>
    <div class="card"><div class="value" style="color:#F59E0B">{other}</div><div class="label">Other</div></div>
    <div class="card"><div class="value" style="color:#F59E0B">{duration}</div><div class="label">Duration</div></div>
  </div>
  <div class="section">
    <h2>Test cases</h2>
    <table class="cases">
      <tr><th>#</th><th>Test case</th><th>Scenario</th><th>Status</th><th>Duration</th><th>Report</th></tr>
      {rows}
    </table>
  </div>
  <footer>Generated by Maestro v{version} &middot; suite run {suite_run_id}</footer>
</body></html>
"""


def generate_suite_report(suite_run_id: str) -> Path | None:
    """Aggregate all member executions of a suite/scenario run into ONE report.

    Produces ``suite_{id}.html`` (a roll-up of per-case pass/fail with links to
    each member's full report) plus ``suite_{id}.json``. Returns the HTML path.
    """
    if not suite_run_id:
        return None
    with session_scope() as db:
        members = (
            db.query(Execution)
            .filter(Execution.suite_run_id == suite_run_id)
            .order_by(Execution.id)
            .all()
        )
        if not members:
            return None
        tc_info = {
            tc.id: tc
            for tc in db.query(TestCase)
            .filter(TestCase.id.in_({m.test_case_id for m in members}))
            .all()
        }
        cases = []
        for m in members:
            tc = tc_info.get(m.test_case_id)
            cases.append(
                {
                    "execution_id": m.id,
                    "name": tc.name if tc else f"#{m.test_case_id}",
                    "scenario": tc.scenario if tc else "",
                    "suite": tc.test_type if tc else "",
                    "status": m.status,
                    "duration_seconds": m.duration_seconds,
                    "started_at": m.started_at.isoformat() if m.started_at else None,
                }
            )
        started_at = members[0].started_at.isoformat() if members[0].started_at else None
        label = (cases[0]["suite"] or "Suite") + (
            f" / {cases[0]['scenario']}" if cases[0]["scenario"] else ""
        )

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] in ("failed", "error"))
    other = len(cases) - passed - failed
    overall = "passed" if failed == 0 and other == 0 else ("failed" if failed else "partial")
    total_duration = sum(c["duration_seconds"] or 0 for c in cases)

    row_parts: list[str] = []
    for i, c in enumerate(cases):
        dur = f"{c['duration_seconds']:.1f}s" if c["duration_seconds"] else "—"
        color = _STATUS_COLORS.get(c["status"], "#64748B")
        row_parts.append(
            "<tr>"
            f"<td>{i + 1}</td>"
            f"<td>{html.escape(c['name'])}</td>"
            f"<td>{html.escape(c['scenario'])}</td>"
            f'<td><span class="badge" style="background:{color}">{html.escape(c["status"])}</span></td>'
            f"<td>{dur}</td>"
            f'<td><a href="execution_{c["execution_id"]}.html" target="_blank">RUN-{c["execution_id"]}</a></td>'
            "</tr>"
        )
    rows = "".join(row_parts)

    page = _SUITE_PAGE.format(
        logo_svg=_load_logo(),
        label=html.escape(label),
        member_count=len(cases),
        started_at=_fmt_dt(started_at),
        status=overall,
        status_color=_STATUS_COLORS.get(
            "passed" if overall == "passed" else "failed", "#64748B"
        ),
        passed=passed,
        failed=failed,
        other=other,
        duration=f"{total_duration:.1f}s" if total_duration else "—",
        rows=rows,
        version=__version__,
        suite_run_id=html.escape(suite_run_id),
    )
    report_path = REPORTS_DIR / f"suite_{suite_run_id}.html"
    report_path.write_text(page, encoding="utf-8")
    (REPORTS_DIR / f"suite_{suite_run_id}.json").write_text(
        json.dumps(
            {
                "suite_run_id": suite_run_id,
                "label": label,
                "status": overall,
                "totals": {"passed": passed, "failed": failed, "other": other},
                "duration_seconds": total_duration,
                "cases": cases,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return report_path


_PW_STYLE = """<style>
:root{color-scheme:light}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Inter,system-ui,sans-serif;background:#f6f8fb;color:#1f2937;padding:28px;max-width:1000px;margin:0 auto}
.pw-top{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.pw-title{font-size:20px;font-weight:700}
.pw-sub{color:#6b7280;font-size:13px;margin-top:2px}
.pw-status{margin-left:auto;color:#fff;padding:6px 16px;border-radius:8px;font-weight:700;font-size:13px;text-transform:capitalize}
.pw-summary{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.pw-pill{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px 14px;font-size:13px;color:#6b7280}
.pw-pill b{color:#111827;font-size:15px;margin-left:6px}
.pw-pass b{color:#16a34a}
.pw-fail b{color:#dc2626}
.pw-list{display:flex;flex-direction:column;gap:6px}
details.pw-test{background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}
details.pw-test>summary{display:flex;align-items:center;gap:12px;padding:12px 16px;cursor:pointer;list-style:none}
details.pw-test>summary::-webkit-details-marker{display:none}
.pw-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.pw-name{font-weight:600;font-size:14px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pw-chip{font-family:Consolas,monospace;font-size:11px;color:#2563eb;background:#eff6ff;border:1px solid #bfdbfe;border-radius:6px;padding:2px 8px}
.pw-time{color:#9ca3af;font-size:12px;font-variant-numeric:tabular-nums}
.pw-body{padding:6px 18px 16px 38px;border-top:1px solid #f1f5f9}
.pw-kv{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;margin:10px 0 4px}
.pw-body pre{background:#0b1220;color:#e5e7eb;border-radius:8px;padding:10px 12px;font-family:'Fira Code',Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word;max-height:320px;overflow:auto}
.pw-body pre.pw-err{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca}
.pw-muted{color:#9ca3af;font-size:13px}
.attachment{margin-top:10px}
.attachment img{max-width:100%;border-radius:8px;border:1px solid #e5e7eb}
.attachment .file{display:inline-block;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:8px 12px;font-family:Consolas,monospace;font-size:12px;color:#2563eb}
.kv{font-size:11px;color:#9ca3af;margin:8px 0 4px}
details.pw-env{margin-top:24px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:8px 16px}
details.pw-env>summary{cursor:pointer;font-weight:600;font-size:13px;color:#374151}
details.pw-env table{border-collapse:collapse;width:100%;margin-top:8px}
details.pw-env td{padding:6px 10px;border-bottom:1px solid #f1f5f9;font-size:13px}
details.pw-env td:first-child{color:#9ca3af;width:200px}
.pw-foot{margin-top:30px;text-align:center;color:#9ca3af;font-size:12px}
</style>"""


def _pw_step(step: dict, params: dict, attachments: list[dict]) -> str:
    status = step["status"]
    color = _STATUS_COLORS.get(status, "#64748b")
    label = step.get("label") or step["action"]
    dur = step.get("duration_seconds")
    meta = f"{dur:.2f}s" if dur is not None else ""
    if step.get("attempts", 0) > 1:
        meta += f" · {step['attempts']}x"
    body: list[str] = []
    shown = {k: v for k, v in params.items() if k != "_label"}
    if shown:
        body.append(
            '<div class="pw-kv">Parameters</div><pre>'
            + html.escape(json.dumps(shown, indent=2, default=str))
            + "</pre>"
        )
    actual = step.get("actual_output", "")
    for rule in expectation_rules(params):
        matched = text_matches(actual, rule["text"], rule["mode"])
        badge = (
            '<span style="color:#16a34a">✔ matched</span>'
            if matched
            else '<span style="color:#dc2626">✘ not matched</span>'
        )
        body.append(
            f'<div class="pw-kv">Expected ({html.escape(rule["mode"])}) — {badge}</div>'
            f'<pre>{html.escape(rule["text"])}</pre>'
        )
    if step.get("actual_output"):
        body.append('<div class="pw-kv">Output</div><pre>' + html.escape(step["actual_output"]) + "</pre>")
    if step.get("error_message"):
        body.append(
            '<div class="pw-kv">Error</div><pre class="pw-err">'
            + html.escape(step["error_message"])
            + "</pre>"
        )
    for artifact in attachments:
        body.append(_embed_attachment(artifact))
    body_html = "".join(body) or '<div class="pw-muted">No details recorded.</div>'
    return (
        '<details class="pw-test"><summary>'
        f'<span class="pw-dot" style="background:{color}"></span>'
        f'<span class="pw-name">{html.escape(label)}</span>'
        f'<span class="pw-chip">{html.escape(step["action"])}</span>'
        f'<span class="pw-time">{meta}</span></summary>'
        f'<div class="pw-body">{body_html}</div></details>'
    )


def _render_playwright(data: dict) -> str:
    """A Playwright-HTML-reporter-style view of the same run."""
    steps = data["steps"]
    exec_data = data["exec_data"]
    status = exec_data.get("status", "unknown")
    status_color = _STATUS_COLORS.get(status, "#64748b")
    rows = "".join(
        _pw_step(
            s,
            data["test_steps"].get(s.get("test_step_id"), {}),
            data["by_step"].get(int(s["step_number"]), []),
        )
        for s in steps
    ) or '<div class="pw-muted">No steps recorded.</div>'
    env_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in _env_of(data).items()
    )
    duration = exec_data.get("duration_seconds")
    dur_text = f"{duration:.1f}s" if duration else "—"
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f"<title>Playwright report — RUN-{data['execution_id']}</title>"
        + _PW_STYLE
        + "</head><body>"
        + '<div class="pw-top">'
        + f'<div>{_load_logo(34)}</div>'
        + f'<div><div class="pw-title">{html.escape(data["tc_name"])}</div>'
        + f'<div class="pw-sub">RUN-{data["execution_id"]} · {html.escape(data["suite"])}'
        + f' / {html.escape(data["scenario"])} · {_fmt_dt(exec_data.get("started_at"))}</div></div>'
        + f'<span class="pw-status" style="background:{status_color}">{html.escape(status)}</span></div>'
        + '<div class="pw-summary">'
        + f'<span class="pw-pill">Total <b>{len(steps)}</b></span>'
        + f'<span class="pw-pill pw-pass">Passed <b>{data["passed"]}</b></span>'
        + f'<span class="pw-pill pw-fail">Failed <b>{data["failed"]}</b></span>'
        + f'<span class="pw-pill">Skipped <b>{data["skipped"]}</b></span>'
        + f'<span class="pw-pill">Duration <b>{dur_text}</b></span></div>'
        + f'<div class="pw-list">{rows}</div>'
        + f'<details class="pw-env"><summary>Environment</summary><table>{env_rows}</table></details>'
        + f'<div class="pw-foot">Generated by Maestro v{__version__} · Playwright-style report</div>'
        + "</body></html>"
    )


def load_report_summary(execution_id: int) -> dict | None:
    path = REPORTS_DIR / f"execution_{execution_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_reports(execution_id_a: int, execution_id_b: int) -> dict:
    """Compare two execution reports step-by-step."""
    a = load_report_summary(execution_id_a)
    b = load_report_summary(execution_id_b)
    if a is None or b is None:
        missing = execution_id_a if a is None else execution_id_b
        raise ValueError(f"No report found for execution {missing}")

    steps_a = {s["step_number"]: s for s in a["steps"]}
    steps_b = {s["step_number"]: s for s in b["steps"]}
    diffs = []
    for num in sorted(set(steps_a) | set(steps_b)):
        sa, sb = steps_a.get(num), steps_b.get(num)
        entry = {
            "step_number": num,
            "a": {"status": sa["status"], "duration": sa.get("duration_seconds")} if sa else None,
            "b": {"status": sb["status"], "duration": sb.get("duration_seconds")} if sb else None,
        }
        entry["changed"] = (sa is None) != (sb is None) or (
            sa is not None and sb is not None and sa["status"] != sb["status"]
        )
        diffs.append(entry)

    return {
        "execution_a": a["execution"],
        "execution_b": b["execution"],
        "totals_a": a["totals"],
        "totals_b": b["totals"],
        "step_diffs": diffs,
        "regressions": [
            d["step_number"]
            for d in diffs
            if d["changed"]
            and d["a"] is not None
            and d["b"] is not None
            and d["a"]["status"] == "passed"
            and d["b"]["status"] != "passed"
        ],
    }
