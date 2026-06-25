# Maestro User Guide

This guide covers everyday use of the Maestro dashboard. No coding required.

## 1. Starting Maestro

```bash
python app.py
```

Your browser opens at `http://localhost:8000`. The first run creates a
**Default Project** automatically.

## 2. Projects

Maestro isolates test cases, devices and reports per project. Switch the
active project from the dropdown in the top-right header. New projects can be
created through the API (`POST /api/projects`) or by an admin.

## 3. Configuring devices (Configuration page)

1. Pick the tab matching your device type: **SSH, ADB, POWER, ETFW, DLT,
   CAMERA, SERIAL**.
2. Click **Add device**, give it a label, and fill in:
   - **Connection settings** — non-secret values such as host, port, serial
     number, script path. Example for SSH:
     `{"host": "192.168.1.50", "port": 22, "username": "root"}`
   - **Credentials** — secrets such as `{"password": "..."}`. These are
     encrypted with AES-256-GCM before touching the database and are never
     returned by the API.
3. Click **Test** to run a connectivity probe. The result badge shows
   `reachable` / `unreachable`.

## 4. Designing a test case (Test Designer page)

The designer organises work in four columns:

1. **Suites** — top-level groups such as *Smoke Tests* or *Regression*.
2. **Scenarios** — functional areas inside a suite, e.g. *System Health
   Check* or *Boot Validation*.
3. **Test Cases** — the cases inside the selected scenario. Click to open,
   use the checkboxes + delete button for bulk delete, the copy icon to
   clone, and **New** to create one (you pick its suite and scenario).
4. **Steps** — the steps of the open test case.
   - **Add Step** opens the action library (SSH, ADB, power, DLT, camera…);
     click a template to append it.
   - **Drag the grip handle** to reorder steps.
   - **Pencil icon** edits the step name, action, JSON parameters, timeout
     and retries.
   - **Trash icon** removes a step.
   - Click **Save** when done (every save creates a new version).

A first run seeds realistic sample suites — try **Demo (no hardware) →
Self Test → Maestro Self Test**, which runs without any bench attached.

### Step parameters worth knowing

| Key | Effect |
|---|---|
| `device_config_id` | Bind the step to a configured device; its credentials are injected and the device is locked while the step runs |
| `_retry: 2` | Retry the step up to 2 times with exponential backoff |
| `_loop: 5` | Repeat the step 5 times (all must pass) |
| `_if: {"source_step": 1, "contains": "ERROR", "skip_to": 4}` | Jump to step 4 if step 1's output contains "ERROR" (`else_skip_to` for the other branch) |
| `_parallel_group: "g1"` | Consecutive steps with the same group run concurrently |
| `_continue_on_failure: true` | Don't abort the run if this step fails |
| `{{steps.1.output}}` | Replaced with the output of step 1 |

## 5. Running tests (Execution page)

1. Select a test case and an execution mode:
   - **Serial** — steps run one after another (default).
   - **Parallel** — all steps run concurrently.
   - **Step-by-step** — Maestro pauses before each step until you click
     **Next step**.
2. Click **Start execution**. Step statuses and logs stream live.
3. Use **Pause / Resume / Stop** at any time.
4. Click any execution in the history list to inspect it.

## 6. Reports (Reports page)

- Every finished execution gets an HTML report — click **Open**.
- Select two reports and click **Compare** to see step-level differences and
  regressions.
- Multi-select + **Delete** removes reports and their execution records.
- The search box filters by id, test case name or status.

## 7. Scheduling (Scheduler page)

Scheduling is date-based — no cron knowledge needed:

- **Run once** — pick a date and time. The schedule disables itself after firing.
- **Every day** — pick a time of day.
- **Every week** — pick a weekday and a time.

Toggle schedules on/off with the switch; the next run time is shown.
(Advanced users can still POST `schedule_type: "cron"` with a cron
expression through the API.)

## 8. Plugins (Plugins page)

Each adapter is a plugin. Toggle plugins on/off; disabled plugins refuse
execution. Custom plugins dropped into `data/plugins/<name>/` (with a
`manifest.json`) are loaded on startup or via `POST /api/plugins/reload`.

## 9. Dark / light mode

Use the sun/moon button in the header. Your preference is remembered.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Browser doesn't open | Navigate to http://localhost:8000 manually, or set `MAESTRO_OPEN_BROWSER=true` |
| `adb` health check fails | Install Android platform-tools and add `adb` to PATH (or set `adb_path` on the device) |
| SSH steps time out | Verify host/port/credentials with the **Test** button on the device config |
| Port 8000 in use | Set `MAESTRO_PORT=8001` in `.env` |
| Logs | `data/logs/maestro.log` (structured JSON) |
