"""Result publishers — email + Jira/Xray.

Both are optional and config-driven (see ``backend.config.Settings``). With
nothing configured a publisher reports ``configured=False`` and ``publish()`` is
a safe no-op, so the framework can be called unconditionally.

* ``EmailPublisher`` uses only the standard library (``smtplib`` + ``email``).
* ``JiraXrayPublisher`` targets the documented **Xray Cloud REST v2** flow
  (``/api/v2/authenticate`` -> ``/api/v2/import/execution/junit``) via ``urllib``
  — no extra dependency. It is config-gated and has not been exercised against a
  live Xray here, so verify the endpoint against your tenant before relying on it.

Adding another ALM (Zephyr, TestRail) is a new ``ResultPublisher`` subclass —
nothing else changes (product principle: integrations are pluggable).
"""

from __future__ import annotations

import html
import json
import smtplib
import ssl
import urllib.request
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any

from backend.config import get_settings
from backend.database import session_scope
from backend.models.execution import Execution
from backend.models.project import TestCase
from backend.services.allure_export import export_junit_xml
from backend.utils.logger import get_logger

logger = get_logger("maestro.publishers")


def _summary(execution_id: int) -> dict[str, Any]:
    with session_scope() as db:
        ex = db.get(Execution, execution_id)
        if ex is None:
            raise ValueError(f"Execution {execution_id} not found")
        steps = list(ex.steps)
        tc = db.get(TestCase, ex.test_case_id)
        return {
            "id": ex.id,
            "name": tc.name if tc else f"#{ex.test_case_id}",
            "status": ex.status,
            "duration": ex.duration_seconds,
            "started_at": ex.started_at.isoformat() if ex.started_at else "",
            "total": len(steps),
            "passed": sum(1 for s in steps if s.status == "passed"),
            "failed": sum(1 for s in steps if s.status in ("failed", "error")),
            "skipped": sum(1 for s in steps if s.status == "skipped"),
            "steps": [
                {"n": s.step_number, "label": s.label or s.action, "status": s.status}
                for s in steps
            ],
        }


def _html_summary(summary: dict) -> str:
    color = {"passed": "#10B981", "failed": "#EF4444", "error": "#EF4444"}.get(
        summary["status"], "#F59E0B"
    )
    rows = "".join(
        f"<tr><td>{st['n']}</td><td>{html.escape(str(st['label']))}</td>"
        f"<td>{html.escape(st['status'])}</td></tr>"
        for st in summary["steps"]
    )
    return (
        '<html><body style="font-family:Segoe UI,Arial,sans-serif">'
        f"<h2>{html.escape(summary['name'])} — "
        f'<span style="color:{color}">{summary["status"].upper()}</span></h2>'
        f"<p>RUN-{summary['id']} · {summary['passed']}/{summary['total']} passed · "
        f"{summary['failed']} failed · {summary['skipped']} skipped</p>"
        '<table border="1" cellpadding="6" cellspacing="0">'
        "<tr><th>#</th><th>Step</th><th>Status</th></tr>"
        f"{rows}</table></body></html>"
    )


class ResultPublisher(ABC):
    """Pluggable destination for a run's results."""

    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        """True if this publisher has enough config to actually send."""

    @abstractmethod
    def publish(self, execution_id: int) -> dict[str, Any]:
        """Publish one execution's results. Returns {ok, detail, ...}."""


class EmailPublisher(ResultPublisher):
    name = "email"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.smtp_host and s.smtp_from and s.smtp_to)

    def publish(self, execution_id: int) -> dict[str, Any]:
        s = get_settings()
        if not self.configured():
            return {
                "ok": False,
                "skipped": True,
                "detail": "Email not configured (set SMTP_HOST, SMTP_FROM, SMTP_TO).",
            }
        summary = _summary(execution_id)
        msg = EmailMessage()
        msg["Subject"] = (
            f"[Maestro] {summary['name']} — {summary['status'].upper()} (RUN-{summary['id']})"
        )
        msg["From"] = s.smtp_from
        msg["To"] = ", ".join(s.smtp_to)
        msg.set_content(
            f"{summary['name']}: {summary['status']} — "
            f"{summary['passed']}/{summary['total']} passed, {summary['failed']} failed."
        )
        msg.add_alternative(_html_summary(summary), subtype="html")
        try:
            junit = export_junit_xml(execution_id)
            msg.add_attachment(
                junit.encode("utf-8"),
                maintype="application",
                subtype="xml",
                filename=f"junit_{execution_id}.xml",
            )
        except Exception:  # an attachment failure shouldn't block the email
            pass
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as srv:
                if s.smtp_tls:
                    srv.starttls(context=ssl.create_default_context())
                if s.smtp_user:
                    srv.login(s.smtp_user, s.smtp_password)
                srv.send_message(msg)
        except Exception as exc:
            return {"ok": False, "detail": f"SMTP send failed: {exc}"}
        return {"ok": True, "detail": f"Emailed {len(s.smtp_to)} recipient(s)."}


class JiraXrayPublisher(ResultPublisher):
    name = "xray"

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.xray_client_id and s.xray_client_secret and s.xray_project_key)

    def _authenticate(self, s) -> str:
        url = f"{s.xray_base_url.rstrip('/')}/api/v2/authenticate"
        data = json.dumps(
            {"client_id": s.xray_client_id, "client_secret": s.xray_client_secret}
        ).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST", headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Xray returns the token as a quoted JSON string.
            return resp.read().decode("utf-8", "replace").strip().strip('"')

    def publish(self, execution_id: int) -> dict[str, Any]:
        s = get_settings()
        if not self.configured():
            return {
                "ok": False,
                "skipped": True,
                "detail": "Xray not configured (set XRAY_CLIENT_ID, XRAY_CLIENT_SECRET, XRAY_PROJECT_KEY).",
            }
        try:
            token = self._authenticate(s)
        except Exception as exc:
            return {"ok": False, "detail": f"Xray authentication failed: {exc}"}
        junit = export_junit_xml(execution_id).encode("utf-8")
        url = (
            f"{s.xray_base_url.rstrip('/')}/api/v2/import/execution/junit"
            f"?projectKey={s.xray_project_key}"
        )
        req = urllib.request.Request(
            url,
            data=junit,
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/xml"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
        except Exception as exc:
            return {"ok": False, "detail": f"Xray import failed: {exc}"}
        return {
            "ok": True,
            "detail": f"Imported JUnit to Xray project {s.xray_project_key}.",
            "response": body[:500],
        }


_PUBLISHERS: dict[str, ResultPublisher] = {
    EmailPublisher().name: EmailPublisher(),
    JiraXrayPublisher().name: JiraXrayPublisher(),
}


def list_publishers() -> list[dict[str, Any]]:
    """Channels and whether each is configured (for the UI to show buttons)."""
    return [{"name": p.name, "configured": p.configured()} for p in _PUBLISHERS.values()]


def publish_result(execution_id: int, channel: str) -> dict[str, Any]:
    publisher = _PUBLISHERS.get(channel)
    if publisher is None:
        return {"ok": False, "detail": f"Unknown channel '{channel}'"}
    result = publisher.publish(execution_id)
    logger.info(
        "result_published", channel=channel, execution=execution_id, ok=result.get("ok")
    )
    return result


def publish_all_configured(execution_id: int) -> dict[str, Any]:
    """Publish to every configured channel (used by auto-publish)."""
    out: dict[str, Any] = {}
    for name, pub in _PUBLISHERS.items():
        if pub.configured():
            out[name] = publish_result(execution_id, name)
    return out
