# Packaging — wheel only

Maestro ships as a single **PyPI wheel** (backend + bundled React UI). There is
no PyInstaller exe / Inno Setup installer anymore — those were removed.

## Build & publish

```bash
python scripts/build_pypi.py          # builds the UI + the wheel -> dist/*.whl
python -m twine upload dist/*          # publish (use your PyPI token; never commit it)
```

The wheel is small (a few MB): it contains the backend and the built UI, but
**no binaries** (adb / ffmpeg / scrcpy are provisioned at runtime — see below).

## Install & run

```bash
pip install maestro-automation        # pulls turboadb + turbossh automatically
maestro                               # starts the server and opens the browser
```

`pip install` upgrades in place; nothing else to manage.

---

## Accommodating your own scripts (CLI args and all)

You do **not** edit Maestro to add a script. Drop any script in and drive it
through the built-in **system** adapter or the bench-tool adapters. All of these
take your own arguments, working directory and environment, and stream output
live to the run console.

| You have… | Use this step | Example `parameters` |
|---|---|---|
| Any `.py/.ps1/.bat/.cmd/.sh/.exe` with args | `system.run_file` | `{ "path": "C:/bench/tool.py", "args": ["start", "--port", "COM5"] }` |
| A full command line | `system.run_command` | `{ "command": "C:/bench/etfw.bat bus-sleep-on" }` |
| A script you run a lot | `system.run_registered` | register it once under **Templates → Scripts**, then `{ "script_id": "my_tool", "args": ["status"] }` |
| Power / DLT / ETFW bench scripts | `power.* / dlt.* / etfw.*` | `{ "script_path": "C:/bench/power_control.py" }` (+ `com_port`, `channel`, `extra_args`) |

Notes:
- **Interpreter is auto-detected** from the file extension (`.py` → Python,
  `.ps1` → PowerShell, `.bat/.cmd` → cmd, `.sh` → bash, anything else run
  directly). Override Python with `python_path`.
- **Args** accept a list (`["a","b"]`) or a string (`"a b"`).
- Optional on every script step: `cwd`, `env` (dict), `timeout`,
  `expect_contains` (+ `match_mode`: contains/wildcard/regex) to pass/fail on the
  output, and `attach_output` / `attach_file` / `attach_files` to attach files
  (e.g. a produced `.dlt`) to the report. `match_file` + `match_pattern` pass the
  step only if a regex is found in a produced file.
- Scripts run with the **full environment** (not sandboxed) because they're your
  trusted bench scripts. (`system.run_script` runs *inline* pasted code in a
  sandbox instead.)

So: **no framework change to add a tool — just point a step at it.**

## ffmpeg (and adb / scrcpy)

Nothing is bundled in the wheel. Each tool is resolved at runtime, in order:

- **adb** — `turboadb` finds a system `adb` (PATH / `ANDROID_HOME`) or downloads
  platform-tools on demand (`turboadb fetch-tools`). Or set `adb_path` on a step.
- **ffmpeg** —
  1. an explicit `ffmpeg_path` on the step (highest priority), else
  2. `ffmpeg` on **PATH** (`winget install Gyan.FFmpeg`, or choco/scoop), else
  3. for the **SSH adapter's camera / RDP capture**, `turbossh` auto-downloads
     and caches ffmpeg under `~/.turbossh/ffmpeg/` on first use (and pushes it to
     the remote box for remote capture).
- **scrcpy** — not required by any step; `turboadb` can fetch it if you add
  mirroring later.

Offline benches: install ffmpeg once (winget / a zip on PATH) or set
`ffmpeg_path`. You can also drop binaries into a local `bin/` folder next to the
install and they'll be found — but that folder is **not** part of the wheel
(it's gitignored) and isn't needed for a normal `pip install`. Delete `bin/` to
reclaim disk; the app fetches what it needs.
