# Installing Maestro

Maestro can be installed four ways. Pick the one that matches you:

| Method | Best for | Needs Python? | Needs Node? |
|---|---|---|---|
| **Windows installer** (`MaestroSetup.exe`) | End users on Windows | No (bundled) | No |
| **PyPI wheel** (`pip install`) | Python users / servers | Yes (3.10+) | No |
| **Source checkout** (`python app.py`) | Developers | Yes (3.10+) | Yes (first build) |
| **Docker** | Containerised deploys | No | No |

After install, open **http://localhost:8000** (the desktop app/installer opens it
for you). First launch creates a default project and a writable data directory.

---

## 1. Windows installer (recommended for end users)

A single `MaestroSetup.exe` installs Maestro into one folder with a **bundled
Python runtime** — the target machine needs nothing pre-installed. The bundled
`adb` platform-tools and `ffmpeg` (if included at build time) are installed
alongside, so Android and webcam steps work out of the box.

1. Run `MaestroSetup.exe` and follow the wizard (installs to `Program Files\Maestro`).
2. Launch **Maestro** from the Start menu / desktop shortcut.
3. Your browser opens to the dashboard automatically.

Runtime data (database, reports, logs) is written to a per-user, writable
location: next to the exe when that folder is writable (portable installs), or
`%LOCALAPPDATA%\Maestro` when installed under `Program Files`. Override with the
`MAESTRO_DATA_DIR` environment variable.

> Building this installer yourself: see [PACKAGING.md](../PACKAGING.md).

---

## 2. PyPI wheel

```bash
# Requirements: Python 3.10+ (3.11.9 recommended)
pip install maestro-automation
maestro                      # starts the server and opens the dashboard
```

**Install into a dedicated folder (recommended):** instead of sharing your
Python environment, run the built-in setup once to provision a self-contained
folder (its own virtual environment + data + launcher):

```bash
maestro setup                # or: maestro-setup
```

It asks for an install folder (default `~/Maestro`), creates a venv there,
installs Maestro into it, and writes a `Maestro.cmd` launcher you can
double-click. All runtime data stays inside that folder.

The wheel ships the built frontend, so no Node.js is required. If the wheel was
built with binaries bundled, `adb` and `ffmpeg` resolve automatically; otherwise
install them yourself (see **Bundled tools** below).

Override the data location or port with environment variables:

```bash
set MAESTRO_DATA_DIR=D:\maestro-data   # where the DB/reports/logs live
set MAESTRO_PORT=8200
maestro
```

---

## 3. Source checkout (developers)

```bash
# Requirements: Python 3.10+ and Node.js 18+ (first run builds the UI)
cd maestro
pip install -r requirements.txt
python app.py
```

`app.py` installs missing dependencies, builds the React frontend on first run,
starts the backend on **http://localhost:8000** and opens your browser.

Frontend dev server with hot reload (proxies the API to :8000):

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## 4. Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

---

## Prerequisites by feature

Most features work with no extra setup. These need an external tool:

| Feature | Needs |
|---|---|
| Android steps (`adb.*`) | Android **platform-tools** (`adb`) |
| Webcam capture (`camera.*`) | **ffmpeg** |
| Remote Run Targets | An SSH server on the remote host (OpenSSH on Windows, sshd on Linux/QNX) |
| Power / ETFW / DLT | Your own bench scripts (register them under **Templates → Scripts**) |

### Bundled tools (`bin/`)

Maestro looks in its `bin/` folder **before** your system `PATH`:

```
bin/platform-tools/adb.exe     # Android platform-tools
bin/ffmpeg.exe                 # ffmpeg
```

- The installer and (optionally) the wheel ship these automatically.
- For a source checkout, download them and drop them in `bin/` as shown above
  (see [bin/README.md](../bin/README.md)).

---

## Security note

Credentials (SSH/target passwords, keys) are encrypted at rest with AES-256-GCM.
Set a stable `SECRET_KEY` in a `.env` file (next to the app) so the vault key is
derived from a secret you control; otherwise a random key is generated and stored
in `data/.vault.key`.

```
SECRET_KEY=change-me-to-a-long-random-string
```
