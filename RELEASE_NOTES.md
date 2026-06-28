# Maestro v2.1.5

Console fixes + one consistent logo everywhere.

- **Console readable in light mode** — log text used a theme colour that went
  near-black on the dark console; now uses explicit light-on-dark colours.
- **Console shows the full server log** — `log_config=None` lets uvicorn/library
  logs propagate to the shared handlers, so the in-app Console mirrors the cmd window
  (startup, requests-as-warnings, errors), not just app events.
- **One logo across the board** — the app, browser favicon, docs site and the new
  desktop-shortcut icon (`maestro.ico`) now all use the same Maestro mark.

---

# Maestro v2.1.4

Adapters refreshed, in-app console, error popups, auto desktop shortcut.

- **Latest device tooling** — pinned to **turboadb ≥ 1.0.14** and **turbossh ≥ 1.2.31**;
  the Plugins page already shows whatever's installed live.
- **In-app Console** — a new **Console** page streams the server log (activity + errors)
  inside the app, so you no longer need the external cmd window. `GET /api/logs`.
- **Error popups** — server/network failures now raise a toast app-wide (global axios
  interceptor), and an error boundary catches UI crashes with a recoverable fallback.
- **Desktop shortcut** — created/refreshed on every launch (OneDrive-aware) and starts
  Maestro **windowless** (no cmd window). Opt out with `MAESTRO_NO_SHORTCUT=1`.

---

# Maestro v2.1.3

Template delete + correct camera detection.

- **Delete built-in templates** — the read-only built-ins now have a real Delete (removes
  them from the palette, restorable via *Show deleted*), alongside Edit and Clone.
- **Camera detection fixed** — Configuration's camera auto-detect (and `camera.detect`) now
  queries only the Windows `Camera` PnP class and de-duplicates, so scanners and virtual
  imaging devices no longer show up as bogus cameras. The live-feed device list is deduped too.

---

# Maestro v2.1.2

Template Manager polish.

- **Collapsible groups** — click any group header (ADB, SSH, …) to expand/collapse;
  large groups start collapsed so the page isn't a wall. Applies to Custom + Built-in tabs.
- **Edit a built-in** — opens the visual editor and saves your own editable copy in Custom
  templates (the shipped file is never touched), alongside Clone and Hide/Restore.

---

# Maestro v2.1.1

Template management you can actually drive.

## Manage built-in templates
- **Hide** any built-in template to remove it from the palette — and **Restore** it later
  (a "Show hidden" toggle). The shipped files are never modified, so it's upgrade-safe.

## Easy grouping + reuse
- **Move to…** dropdown on every custom template files it under any group (or a new one).
- Custom templates are shown in **grouped sections**; the editor's group field is now a
  dropdown of existing groups (type a new one to create it).
- **Duplicate** a custom template in one click.

---

# Maestro v2.1.0

Workflow polish from real bench use — choose where a test runs once, reuse steps
as templates, and two designer bugs squashed.

## Run location (choose once, not per step)
- The **Run location** picker (Local vs a saved remote/RDP target) is now prominent
  at the top of the designer. Every `ssh.*`/`adb.*` step follows it automatically.
- Per-step target binding is now a clearly-labelled **optional override**, not a
  "required" nag — the editor shows which run location a step defaults to.
- Canvases only flag "⚠ no target" when it actually matters (a local SSH step with
  nothing to connect to), not on every unbound step.

## Templates you can actually read & build
- **Save as template**: turn any configured step into a reusable palette item from
  the step editor.
- **Design a template**: the Templates page now uses the same friendly visual editor
  (pick an action, fill plain-English settings) — no more hand-written JSON.
- Template cards show a readable action chip + a plain-English settings summary.
- The Templates page opens on **your** templates first (not Registered scripts).

## Live feed
- New **Live Feed** page: watch the connected **webcam** or the **desktop** live in the
  browser (MJPEG over `ffmpeg`). Point an RDP client window at a remote host and the
  desktop source shows that session live. Endpoints `/api/camera/sources` and `/live`.

## Plugins show the live tool version
- The Plugins page now features the **actual installed** turboadb/turbossh version
  (e.g. "Powered by turbossh v1.2.24 · live"), resolved from package metadata so it
  tracks upgrades — instead of a static number. All adapter manifests aligned to 2.1.0.

## Bug fixes
- **`system.run_file` "missing script" after choosing one**: file-upload failures were
  swallowed silently, leaving the path empty. Errors now surface, the path is flagged
  required, and `args` respect quotes (a quoted path with spaces stays one argument).
- **Editing parallel steps forced an ungroup**: editing a member of any parallel group
  (B, C, …) now preserves its group instead of collapsing it into group A.

---

# Maestro v2.0.0

The biggest release yet. Adapters now drive **your own tools**, reports are the
real Allure/JUnit artifacts, the test designer is a proper graph canvas, and the
app ships as a clean **wheel** — no installer, no bundled binaries.

## Highlights
- Visual **React Flow** test designer (nodes, branches, parallel, minimap, auto-layout).
- **Real Allure results + JUnit XML** (not a mimic) — with trends/history.
- **Endurance/stability** engine: loop a case for N cycles with stop conditions + roll-up.
- Adapters wrap your tools: **turboadb 1.0.5**, **turbossh 1.2.16**.
- **Camera & RDP capture** over SSH (local webcam + remote desktop screenshot/recording).
- **Email + Jira/Xray** result publishers.
- Wheel-only packaging + a **ruff/mypy/pre-commit** CI gate.

## Adapters
- **Android (ADB)** → `turboadb`: shell, push/pull, install, logcat, screenshot, screen-record, wireless connect, device info.
- **SSH / QNX / RDP** → `turbossh`: commands, SFTP, log capture (domain/UPN logins, legacy ECUs, jump hosts) + `camera_*`, `remote_camera_capture`, `rdp_screenshot`, `rdp_record`.
- **Power / DLT / ETFW** → thin wrappers around your bench scripts, with `[simulated]` fallbacks so test design works hardware-free.

## Reports & integrations
- `allure_export` → real `allure-results` (`allure serve`) + JUnit XML; endpoints `/reports/{id}/allure` and `/junit`, with download buttons.
- Pluggable `ResultPublisher`: **email** (SMTP) + **Jira/Xray** (Cloud v2), config-driven and no-op when unconfigured.
- Retired the cosmetic "Playwright-style" view.

## Designer & endurance
- `FlowCanvasRF` (React Flow) is the default **Flow** view; Classic + List remain.
- New `CycleResult` model + cycle loop; stop conditions (`max_duration`, `consecutive_failures`, `failure_threshold`); per-cycle roll-up in Reports; `/reports/{id}/cycles`.

## Quality & packaging
- `ruff` + `mypy` + `pre-commit`; green CI lint gate.
- Wheel-only: removed the PyInstaller spec, Inno Setup installer and zip packager. A few-MB wheel (UI bundled, no binaries — turboadb/turbossh fetch adb/ffmpeg at runtime).

## Breaking changes
- `?format=playwright` report option removed — use Allure (`/allure`) or JUnit (`/junit`).
- SSH adapter internals changed (now `turbossh`); the `_effective_username` helper moved into turbossh.
- The desktop `.exe` / installer build was removed — install via `pip install maestro-automation`.

## Install
```
pip install maestro-automation
maestro
```

---
Created by **Naveen Daniel Kennedy**.
