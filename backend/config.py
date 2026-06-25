"""Configuration loader for Maestro.

Reads settings from environment variables and an optional ``.env`` file.
Everything has a sensible default so ``python app.py`` works with zero setup.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

# Path layout works in three modes: source checkout, PyInstaller bundle, and
# pip-installed wheel.
#   * BUNDLE_DIR  — read-only resources (frontend/dist, templates, adapters).
#   * ROOT_DIR    — writable base for runtime data/logs/reports.
_PKG = Path(__file__).resolve().parent          # .../backend
_PARENT = _PKG.parent                            # repo root, or site-packages


def _first(paths: list[Path], fallback: Path) -> Path:
    for p in paths:
        if p.exists():
            return p
    return fallback


def _writable(path: Path) -> bool:
    """True if we can actually create/write under ``path`` (Program Files is not)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


if getattr(sys, "frozen", False):                # PyInstaller build
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    # Resources live next to the exe (read-only ok), but runtime data must go
    # somewhere writable. Installed under Program Files the exe dir is NOT
    # writable, so fall back to %LOCALAPPDATA%\Maestro (per-user, no admin).
    _exe_dir = Path(sys.executable).resolve().parent
    _env_data = os.getenv("MAESTRO_DATA_DIR")
    if _env_data:
        ROOT_DIR = Path(_env_data)
    elif _writable(_exe_dir):                     # portable / writable folder
        ROOT_DIR = _exe_dir
    else:                                         # installed to Program Files
        ROOT_DIR = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "Maestro"
elif (_PARENT / "app.py").exists():              # source checkout
    BUNDLE_DIR = _PARENT
    ROOT_DIR = _PARENT
else:                                            # pip-installed wheel
    BUNDLE_DIR = _PARENT
    ROOT_DIR = Path(os.getenv("MAESTRO_DATA_DIR", Path.home() / ".maestro"))

DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
REPORTS_DIR = DATA_DIR / "reports"
ARTIFACTS_DIR = DATA_DIR / "artifacts"

# Resources: prefer the bundle/checkout layout; fall back to package data that
# ships inside the wheel (built UI under backend/_bundled, templates/adapters
# already inside the backend package).
FRONTEND_DIST = _first(
    [BUNDLE_DIR / "frontend" / "dist", _PKG / "_bundled" / "frontend" / "dist"],
    BUNDLE_DIR / "frontend" / "dist",
)
TEMPLATES_DIR = _first([BUNDLE_DIR / "backend" / "templates", _PKG / "templates"], _PKG / "templates")
ADAPTERS_DIR = _first([BUNDLE_DIR / "backend" / "adapters", _PKG / "adapters"], _PKG / "adapters")

# Bundled binaries (adb platform-tools, ffmpeg). Looked up across all run modes:
# source/frozen bundle, wheel package data, and the writable runtime dir (so a
# user can also drop a binary into <install>/bin without rebuilding).
BIN_DIR = _first(
    [BUNDLE_DIR / "bin", _PKG / "_bundled" / "bin", ROOT_DIR / "bin"],
    ROOT_DIR / "bin",
)


_BIN_BASES = [BUNDLE_DIR / "bin", _PKG / "_bundled" / "bin", ROOT_DIR / "bin"]


def find_bundled_binary(*relative: str) -> Path | None:
    """Return the first existing bundled binary path, trying every known bin dir.

    ``relative`` is the path under bin/, e.g. ("platform-tools", "adb.exe").
    """
    for base in _BIN_BASES:
        candidate = base.joinpath(*relative)
        if candidate.exists():
            return candidate
    return None


def find_bundled_executable(name: str) -> Path | None:
    """Find an executable by filename anywhere under any bin/ dir (recursive).

    Tools are often shipped in their own subfolder (e.g. ``ffmpeg-8.1.2/bin/
    ffmpeg.exe`` or ``scrcpy-win64/scrcpy.exe``), so we search recursively rather
    than assuming a fixed layout. A direct top-level hit is preferred.
    """
    for base in _BIN_BASES:
        direct = base / name
        if direct.exists():
            return direct
    for base in _BIN_BASES:
        if base.exists():
            match = next(base.rglob(name), None)
            if match is not None:
                return match
    return None


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (no external dependency required)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(ROOT_DIR / ".env")


class Settings:
    """Application settings resolved from the environment."""

    def __init__(self) -> None:
        self.app_name: str = "Maestro"
        self.version: str = "1.0.0"
        self.environment: str = os.getenv("ENVIRONMENT", "production")
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
        self.host: str = os.getenv("MAESTRO_HOST", "127.0.0.1")
        # MAESTRO_PORT wins; generic PORT (set by hosts/launchers) is the fallback.
        self.port: int = int(os.getenv("MAESTRO_PORT", os.getenv("PORT", "8000")))
        self.database_url: str = os.getenv(
            "DATABASE_URL", f"sqlite:///{(DATA_DIR / 'maestro.db').as_posix()}"
        )
        self.secret_key: str = os.getenv("SECRET_KEY", "")
        # Optional shared token. When set, every /api and /ws request must
        # present it (Authorization: Bearer / X-Maestro-Token / ?token=).
        # Unset = zero-config local mode (loopback only is strongly advised).
        self.api_token: str = os.getenv("MAESTRO_API_TOKEN", "")
        self.vault_key_file: Path = Path(
            os.getenv("MAESTRO_VAULT_KEY_FILE", str(DATA_DIR / ".vault.key"))
        )
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:8000"
            ).split(",")
            if o.strip()
        ]
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

        # --- result publishing (all optional, env-driven; secrets via env) ----
        # Email (SMTP). Configured when host + at least one recipient are set.
        self.smtp_host: str = os.getenv("SMTP_HOST", "")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user: str = os.getenv("SMTP_USER", "")
        self.smtp_password: str = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from: str = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")
        self.smtp_to: list[str] = [
            a.strip() for a in os.getenv("SMTP_TO", "").split(",") if a.strip()
        ]
        self.smtp_tls: bool = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")
        # Jira / Xray Cloud (REST v2). Configured when client id + secret + project set.
        self.xray_base_url: str = os.getenv("XRAY_BASE_URL", "https://xray.cloud.getxray.app")
        self.xray_client_id: str = os.getenv("XRAY_CLIENT_ID", "")
        self.xray_client_secret: str = os.getenv("XRAY_CLIENT_SECRET", "")
        self.xray_project_key: str = os.getenv("XRAY_PROJECT_KEY", "")
        self.open_browser: bool = os.getenv("MAESTRO_OPEN_BROWSER", "true").lower() in (
            "1",
            "true",
            "yes",
        )

        for directory in (DATA_DIR, LOGS_DIR, REPORTS_DIR, ARTIFACTS_DIR):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
