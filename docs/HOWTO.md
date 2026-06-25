# Maestro How-To

1. [Run your existing scripts (PowerShell / batch / cmd / Python / .exe)](#1-run-your-existing-scripts)
2. [Use your Power / DLT / ETFW scripts](#2-use-your-power--dlt--etfw-scripts)
3. [Build a whole suite from scripts](#3-build-a-whole-suite-from-scripts)
4. [Build the installer (setup.exe)](#4-build-the-installer)

---

## 1. Run your existing scripts

The framework runs **any existing script or executable as-is** — you do **not**
have to change your scripts or match any naming convention. Use the **Script**
group in the palette:

### `system.run_file` — run a script/exe file

Drag **"Run PowerShell file (.ps1)"** (or batch/cmd/python/exe) onto the canvas,
double-click it, and set:

| Parameter | What it is |
|-----------|------------|
| `path` | Full path to your file: `C:\scripts\power.ps1`, `...\capture.bat`, `...\run.py`, `tool.exe` |
| `args` | Your arguments — a **list** `["on", "--verbose"]` (or a space-separated string) |
| `cwd` | Working directory (defaults to the script's folder) |
| `env` | Extra environment variables, e.g. `{ "TARGET": "ECU1" }` |
| `timeout` | Seconds before it's killed |
| `expect_contains` | Optional text that must appear in output → pass/fail |
| `attach_output` | `true` to attach the full stdout to the report |

The **interpreter is auto-detected** from the extension:
`.ps1`→PowerShell, `.bat`/`.cmd`→cmd, `.py`→Python, `.sh`→bash, `.exe`/other→run
directly. Output, stderr and exit code are captured; non-zero exit = step fails.
These run with your **full environment** (not sandboxed) — they're your scripts.

### `system.run_command` — run any command line

Drag **"Run a command line"**, set `command` to anything you'd type in a shell,
e.g. `C:\scripts\power.ps1 cycle && timeout /t 3`. Runs through cmd on Windows.

> There's also **"Run sandboxed Python script"** (`system.run_script`) for
> pasting inline code that runs isolated — use that only when you want a quick
> throwaway snippet, not for your real scripts.

---

## 2. Use your Power / DLT / ETFW scripts

**You already have scripts → just use `run_file` (§1).** Point it at your
`power.ps1` / DLT capture script / ETFW script with whatever arguments they take.
Nothing to conform to. Examples:

- Power on:  `run_file` `path=C:\bench\power.ps1` `args=["on"]`
- Power cycle: `run_file` `path=C:\bench\power.ps1` `args=["cycle"]`
- Start DLT capture (your tool): `run_file` `path=C:\bench\dlt_capture.py` `args=["--out","run.dlt"]`
- ETFW bus sleep: `run_file` `path=C:\bench\etfw.bat` `args=["bus-sleep-on"]`

To attach your DLT trace to the report afterwards, add a **`dlt.save_file`**
step with `file_path` = your script's `.dlt` output.

> The built-in **`power.*` / `etfw.*` / `dlt.*`** adapters are *optional
> conveniences* for people who don't have their own scripts (they assume
> on/off/cycle-style verbs). If you have full scripts, ignore them and use
> `run_file`.

---

## 3. Build a whole suite from scripts

A **suite** is just a named group of test cases.

1. In the Designer set **Suite** (e.g. `Smoke`) and **Scenario** (e.g. `Boot`).
2. Create a test case. It can be:
   - **one `run_file` step** that runs your entire script, **or**
   - **several steps** (e.g. `power.run_file on` → `run_file boot_check.py` →
     `dlt.save_file`) chained with **`{{steps.N.output}}`** to pass an earlier
     step's output into a later one.
3. Save, then create more test cases under the **same Suite**.
4. Run everything: Execution → scope **"Run: whole suite"** → pick the suite →
   **Start**. All cases run in order into one combined report.

For a script you want available everywhere as a named action, make it a
**plugin adapter** under `data/plugins/<name>/` (`manifest.json` +
`adapter.py` subclassing `BaseAdapter`) and Reload from the Plugins page.

---

## 4. Attach an input file to a step (delivered *before* it runs)

Open a step → **Attachments (planned)** → **Attach file**. The file always
appears in the report. To make the step *use* it, fill the **"Deliver before
run to…"** box with a destination on the step's target:

- **SSH step** → e.g. `/tmp/config.dlt` — uploaded by SFTP before the command.
- **ADB step** → e.g. `/sdcard/` — pushed before the shell action.

The upload uses the step's bound device, so the step must target an SSH/ADB
device. Leave the box blank to only attach the file to the report.

---

## 5. Run for hours — stability / soak (cycles)

Execution → choose **This case / Scenario / Suite**, then set **Cycles** to how
many times to repeat it back-to-back (e.g. `200` over a weekend). Every cycle is
a real execution, so the combined report shows pass/fail per cycle and you can
spot the run where something first broke.

---

## 6. Wildcards & exact match on output

In a step, **"Pass when the output…"** picks how `expect_contains` is matched:

- **contains** (default) — substring.
- **wildcard** — shell globs, e.g. `systemctl*` or `*active (running)*`.
- **regex** — full regular expression, e.g. `v\d+\.\d+\.\d+`.
- **exact** — the whole output must equal the text.

You can add **multiple conditions** in one step (each with its own mode) — the
step passes only if **every** condition matches. Each is shown separately in the
report with its own ✔/✘.

A custom Python script with **no arguments** works too — just set `path` and
leave `args` empty.

---

## 7. Move a test case to another machine (export / import)

In the designer toolbar:

- **Export** downloads the selected test case as a `*.maestro.json` bundle.
- **Import** (on the other machine) loads that file into the current project as
  a new test case.

The bundle carries the steps, settings, suite/scenario and author. Two things
are machine-specific and need re-pointing after import: **device bindings**
(pick the local SSH/ADB target again) and **uploaded-file paths** (re-attach the
file). Each test case also records **created by** (the tester name from the
header) — shown in the designer and on the report.

> **Where pip puts your data:** when installed with `pip install maestro-automation`,
> the database, reports and artifacts live under `~/.maestro` (i.e.
> `C:\Users\<you>\.maestro` on Windows). Copy that folder to move *everything*;
> use export/import to move a *single* test case.

---

## 8. Build the installer (setup.exe)

(Full reference: `PACKAGING.md`.)

```powershell
python scripts\package.py        # → build\maestro\ + build\maestro-<ver>.zip (clean, runnable)
# install Inno Setup 6 once: https://jrsoftware.org/isinfo.php
iscc installer\maestro.iss       # → installer\Output\MaestroSetup.exe
```

The zip is already a portable app (unzip → double-click `Maestro.cmd`). The
installer adds shortcuts, installs Python deps on first run, and offers to
launch. Target PC needs Python 3.10+ (or bundle the Python embeddable — see
`PACKAGING.md`).

---

## 9. Run Targets — Local vs Remote (RDP / domain host)

A **Run Target** decides *where* a test runs. Without one, steps run on the
machine hosting Maestro (**Local**). To run on a remote, domain-joined Windows
host (the kind you'd reach over RDP):

1. **Configuration → Targets → Add Target.**
   - *Where does this target run?* → **Remote host**
   - *Remote OS* → **Windows** (uses cmd/PowerShell over OpenSSH) or **Linux/QNX** (bash)
   - Fill in **Hostname/IP**, **Username**, **Windows domain** (e.g. `CORP`) and **Password**.
   - **Test Connection** verifies the SSH login and reports whether `adb` is present there.
2. In the **Test Designer**, pick the target from the **Run on** dropdown (or
   leave it **Local**). You can also override the target at run time.

On a remote target, `system.run_command` / `system.run_file` execute **on that
host**, and unbound SSH steps use the target's host + credentials. (RDP is a
screen protocol, so command execution goes over SSH/WinRM — the target stores the
`DOMAIN\user` login.) ADB steps still talk to USB devices on the Maestro host.

## 10. Register your power / ETFW / DLT scripts

Bench scripts that run as `python power_control.py <subcommand>` are first-class:

1. **Templates → Registered scripts → Register script.**
   - **Name**: `Power control`
   - **Script path**: `C:/bench/power_control.py`
   - **Subcommands** (one per line):
     ```
     normal_power_cycle
     edl_power_cycle
     power_off_edl_off
     power_on_edl_off
     power_on_edl_on
     ```
2. Each subcommand now appears in the designer palette under **Scripts**. Drag one
   in and it runs `python power_control.py normal_power_cycle`. Pass extra
   arguments via the step's `args` setting, and attach produced files / match a
   `.dlt` pattern exactly like `run_file`.

## 11. Create your own palette templates

**Templates → Custom templates → New template**: choose a palette **group**, a
**label**, an **action** and its **parameters** (JSON). Your template then shows
up in the designer palette under that group, next to the built-ins. Delete or
edit them any time from the same page.

## 12. Run and report on a whole suite or scenario

From the designer's **Run ▾** menu (or the Scheduler), run a **scenario** or a
**whole suite**. Every member test case runs as part of one grouped *suite run*,
and Maestro produces a **single aggregated report** (pass/fail per case, totals,
durations) in addition to each case's own report. Open it from **Reports** via the
**Suite report** link on any member run.

## 13. Schedule a suite / scenario with a time window

**Scheduler**: choose **What to run** (test case, scenario or whole suite), the
repeat (once / daily / weekly), and — for recurring schedules — an optional
**Start from** and **Run until** window. The schedule auto-disables after the
*until* date.

## 14. Authorship & locking

Each test case records **created by** and **last edited by** (preserved through
export/import; imported cases are tagged *imported*). A saved case opens
**read-only** — click **Unlock to edit** to take ownership before changing it, so
shared designs aren't altered by accident.
