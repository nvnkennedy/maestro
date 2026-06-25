# Maestro Tutorials

Hands-on walkthroughs. Each takes under 10 minutes.

## Tutorial 1 — Your first test (no hardware needed)

1. Start Maestro: `python app.py`
2. Go to **Test Cases**, select test type **system**, click **New**.
3. Click these actions in order: *Echo message*, *Assert previous output
   contains*, *Wait (seconds)*.
4. Edit step 2 (pencil icon) and set parameters to:
   ```json
   {"text": "{{steps.1.output}}", "expected": "Hello"}
   ```
5. **Save**, switch to **Execution**, select the case, click
   **Start execution** — watch the live logs and step badges.
6. Open the report from the **Reports** page.

## Tutorial 2 — SSH smoke test on a real target

1. **Configuration → SSH → Add device**: settings
   `{"host": "<ip>", "port": 22, "username": "root"}`, credentials
   `{"password": "<pwd>"}`. Click **Test** until it shows *reachable*.
   Note the device id shown next to the label.
2. Build a test case with *Run command, expect text* and add
   `"device_config_id": <id>` to its parameters.
3. Run it. The password is decrypted only at execution time and never leaves
   the server.

## Tutorial 3 — Power cycle with verification

1. Configure a **POWER** device with
   `{"script_path": "C:/scripts/power.ps1"}`.
2. Steps: *Power cycle* → *Wait (seconds)* (give the unit time to boot) →
   an SSH *Run command, expect text* step asserting the system is up.
3. Set `retry_count` (or `_retry`) on the SSH step so transient boot delays
   retry automatically with backoff.

## Tutorial 4 — Conditional remediation

Steps:
1. `ssh.execute_command` → `dmesg | tail -50`
2. `system.echo` with parameters:
   ```json
   {"message": "remediating...", "_if": {"source_step": 1, "contains": "ERROR", "else_skip_to": 4}}
   ```
   If step 1's output has no "ERROR", execution jumps straight to step 4.
3. Remediation step (only runs when "ERROR" was found).
4. Final verification step.

## Tutorial 5 — Nightly scheduled run

1. **Schedules** page → pick the test case → cron `0 2 * * *` → **Schedule**.
2. Maestro runs it at 02:00 every night (server must be running — install it
   as a service with `scripts/install-service-windows.bat` or
   `scripts/install-service-linux.sh`).
3. Inspect results on the **Reports** page; use **Compare** between two
   nights to spot regressions.

## Tutorial 6 — Writing a custom plugin

See the step-by-step in
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md#writing-a-new-adapter-plugin), then
drop your plugin folder into `data/plugins/` and press **reload** via
`POST /api/plugins/reload`.
