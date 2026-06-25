# 🏁 Maestro — Automotive Test Automation Framework

Maestro consolidates SSH, ADB, bench power control, ETFW, DLT logging, serial
consoles and Windows camera capture into a single browser-based dashboard.
Non-technical users design test cases with drag-and-drop; engineers extend it
through a hot-reloadable plugin system.

## 🚀 Quick start

```bash
# Requirements: Python 3.10+ (3.11.9 recommended), Node.js 18+

cd maestro
pip install -r requirements.txt      # or: pip install poetry && poetry install
python app.py
```

`app.py` installs anything missing, builds the React frontend on first run,
starts the FastAPI backend on **http://localhost:8000** and opens your
browser. That's it.

| URL | What |
|---|---|
| `http://localhost:8000` | Maestro dashboard |
| `http://localhost:8000/api/docs` | Interactive API documentation (Swagger) |
| `http://localhost:8000/metrics` | Prometheus metrics |

## ✨ Highlights

- **Drag-and-drop test designer** (list + visual canvas) with pre-built step
  templates for SSH, ADB, power, ignition, ETFW, DLT, camera and serial console.
  Reorder steps freely — including inside parallel groups and on the canvas.
- **Run Targets**: run a test case / scenario / suite **Local** or on a saved
  **remote (RDP / domain-joined) host** over SSH — chosen per test or at run time.
- **Registered scripts**: register a bench script once (e.g. `power_control.py`)
  with its subcommands; each subcommand becomes a drag-and-drop palette item that
  runs `python power_control.py <subcommand>`.
- **Template Manager**: create, edit and delete your own palette templates and
  register scripts from a dedicated page.
- **Execution engine**: serial / parallel / step-by-step modes, retry with
  exponential backoff, IF/THEN conditional jumps, loops, parallel groups,
  per-device resource locking, sandboxed user scripts.
- **Authorship & integrity**: every test case records who created/last-edited it
  (preserved across import/export); saved cases are read-only until you unlock.
- **Live monitoring** over WebSocket: step status, logs, pause/resume/stop.
- **Reports**: Allure-style HTML per run, **plus one aggregated report per
  suite/scenario run**, with timelines, artifacts and report diffing.
- **Scheduling**: run a test case, scenario or whole suite once / daily / weekly /
  cron, with an optional **start-from / run-until** active window.
- **Enterprise security**: AES-256-GCM credential vault, 5-role RBAC, audit log.
- **Observability**: structured JSON logs, Prometheus metrics, adapter health.
- **Plugin system**: manifest-based adapters, enable/disable, hot reload,
  custom plugins in `data/plugins/`.
- **Self-contained packaging**: bundle `adb` platform-tools + `ffmpeg` into the
  PyPI wheel and a one-folder Windows installer (see [INSTALL.md](docs/INSTALL.md)).

## 🧪 Development

```bash
# Backend tests
python -m pytest tests/

# Frontend dev server (proxies API to :8000)
cd frontend && npm install && npm run dev

# Frontend tests & build
npm run test && npm run build
```

## 🐳 Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

## 📚 Documentation

- [INSTALL.md](docs/INSTALL.md) — **how to install** (installer, PyPI, source, Docker)
- [HOWTO.md](docs/HOWTO.md) — task-oriented guide: build tests, targets, scripts, scheduling, reports
- [USER_GUIDE.md](docs/USER_GUIDE.md) — using the dashboard
- [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) — extending Maestro
- [API_REFERENCE.md](docs/API_REFERENCE.md) — REST/WebSocket API
- [MAESTRO_COMPLETE_ARCHITECTURE.md](MAESTRO_COMPLETE_ARCHITECTURE.md) — full architecture spec
- [PACKAGING.md](PACKAGING.md) — build the wheel / Windows installer

## 📄 License

MIT — see [LICENSE](LICENSE).
