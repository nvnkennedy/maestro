"""Test execution engine.

Supports serial, parallel and step-by-step modes plus advanced control flow
declared in step parameters:

- ``_retry``: overrides the step's retry count (exponential backoff 2^n s)
- ``_loop``: repeat the step N times (all iterations must pass)
- ``_if``: {"source_step": N, "contains": "txt", "skip_to": M, "else_skip_to": K}
  evaluates against a previous step's output and jumps accordingly
- ``_parallel_group``: consecutive steps sharing a group name run concurrently
  even in serial mode
- ``device_config_id``: binds the step to a configured device; its decrypted
  credentials are merged into the adapter parameters and the device is locked
  for the duration of the step
- ``{{steps.N.output}}`` placeholders in string parameters are substituted
  with the output of step N
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Optional

from backend.adapters.adapter_registry import get_registry
from backend.adapters.base_adapter import AdapterResult
from backend.database import session_scope
from backend.models.artifact import ExecutionArtifact
from backend.models.execution import Execution, ExecutionStep
from backend.models.project import TestCase
from backend.security.credential_manager import resolve_device, resolve_target
from backend.services.live_log import set_execution
from backend.services.observability import metrics
from backend.services.resource_lock_mgr import lock_manager
from backend.services.ws_manager import ws_manager
from backend.utils.helpers import new_correlation_id, truncate, utcnow
from backend.utils.logger import get_logger

logger = get_logger("maestro.executor")

_PLACEHOLDER_RE = re.compile(r"\{\{\s*steps\.(\d+)\.output\s*\}\}")
# {{target.power_script}} → the Run Target machine's saved dependency path.
_TARGET_RE = re.compile(r"\{\{\s*target\.([A-Za-z0-9_]+)\s*\}\}")


class ExecutionController:
    """Pause/stop/step-gate signals for one running execution."""

    def __init__(self) -> None:
        self.stop_requested = asyncio.Event()
        self.pause_requested = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.step_gate = asyncio.Event()  # step-by-step mode: released by /next
        self.task: Optional[asyncio.Task] = None
        # Resolved Run Target for this execution (None / local = run here).
        self.target: Optional[dict] = None
        # Endurance/stability: repeat the whole case N cycles with stop conditions.
        self.cycles: int = 1
        self.stop_conditions: dict = {}
        self.cycle: int = 0


class SuiteRunState:
    """Progress tracking for a suite/scenario run (a sequence of executions)."""

    def __init__(self, suite_run_id: str, label: str, test_case_ids: list[int]) -> None:
        self.suite_run_id = suite_run_id
        self.label = label
        self.test_case_ids = test_case_ids
        self.cancel_requested = False
        self.current_execution_id: int | None = None
        self.results: list[str] = []
        self.target_id: int | None = None


class TestExecutor:
    def __init__(self) -> None:
        self._controllers: dict[int, ExecutionController] = {}
        self._suite_runs: dict[str, SuiteRunState] = {}

    # ------------------------------------------------------------------ API

    async def start(
        self,
        test_case_id: int,
        mode: str = "serial",
        triggered_by: str = "admin",
        suite_run_id: str = "",
        target_id: int | None = None,
        cycles: int = 1,
        stop_conditions: dict | None = None,
    ) -> dict:
        """Create an execution record and launch the run task."""
        target = None
        with session_scope() as db:
            test_case = db.get(TestCase, test_case_id)
            if test_case is None:
                raise ValueError(f"Test case {test_case_id} not found")
            # Resolve the Run Target: explicit override, else the case default.
            effective_target_id = target_id or test_case.default_target_id
            if effective_target_id:
                try:
                    target = resolve_target(db, int(effective_target_id))
                except ValueError:
                    target = None
            execution = Execution(
                test_case_id=test_case_id,
                status="running",
                execution_mode=mode,
                triggered_by=triggered_by,
                correlation_id=new_correlation_id(),
                suite_run_id=suite_run_id,
                target_id=target["id"] if target else None,
                target_label=target["label"] if target else "",
            )
            db.add(execution)
            db.flush()
            execution_id = execution.id
            payload = execution.to_dict()
            payload["test_case_name"] = test_case.name

        controller = ExecutionController()
        # Keep the full target (any kind): remote routing uses kind=="remote",
        # while dependency paths / {{target.*}} placeholders apply to local too.
        controller.target = target
        controller.cycles = max(1, int(cycles or 1))
        controller.stop_conditions = stop_conditions or {}
        self._controllers[execution_id] = controller
        controller.task = asyncio.create_task(self._run(execution_id, mode))
        metrics.set_queue_length(len(self._controllers))
        await ws_manager.broadcast(
            {"type": "execution_started", "execution": payload}
        )
        return payload

    async def start_suite(
        self,
        test_case_ids: list[int],
        mode: str = "serial",
        triggered_by: str = "admin",
        label: str = "Suite run",
        target_id: int | None = None,
    ) -> dict:
        """Run a list of test cases sequentially as one grouped suite run."""
        if not test_case_ids:
            raise ValueError("No test cases to run")
        suite_run_id = new_correlation_id()
        state = SuiteRunState(suite_run_id, label, test_case_ids)
        state.target_id = target_id
        self._suite_runs[suite_run_id] = state
        # Resolve names up front so clients can render the run queue.
        with session_scope() as db:
            names = {
                tc.id: tc.name
                for tc in db.query(TestCase)
                .filter(TestCase.id.in_(test_case_ids))
                .all()
            }
        queue = [
            {"id": tc_id, "name": names.get(tc_id, f"#{tc_id}")}
            for tc_id in test_case_ids
        ]
        asyncio.create_task(self._run_suite(state, mode, triggered_by))
        payload = {
            "suite_run_id": suite_run_id,
            "label": label,
            "total": len(test_case_ids),
            "test_case_ids": test_case_ids,
            "test_cases": queue,
            "mode": mode,
        }
        await ws_manager.broadcast({"type": "suite_run_started", **payload})
        return payload

    async def _run_suite(
        self, state: SuiteRunState, mode: str, triggered_by: str
    ) -> None:
        total = len(state.test_case_ids)
        for index, test_case_id in enumerate(state.test_case_ids):
            if state.cancel_requested:
                break
            try:
                payload = await self.start(
                    test_case_id,
                    mode,
                    triggered_by,
                    suite_run_id=state.suite_run_id,
                    target_id=state.target_id,
                )
            except ValueError:
                state.results.append("error")
                continue
            state.current_execution_id = payload["id"]
            await ws_manager.broadcast(
                {
                    "type": "suite_run_update",
                    "suite_run_id": state.suite_run_id,
                    "label": state.label,
                    "current_index": index + 1,
                    "total": total,
                    "execution_id": payload["id"],
                    "test_case_id": test_case_id,
                    "test_case_name": payload.get("test_case_name", ""),
                }
            )
            controller = self._controllers.get(payload["id"])
            if controller is not None and controller.task is not None:
                try:
                    await controller.task
                except Exception:
                    pass
            with session_scope() as db:
                execution = db.get(Execution, payload["id"])
                state.results.append(execution.status if execution else "error")

        totals = {
            "passed": state.results.count("passed"),
            "failed": state.results.count("failed") + state.results.count("error"),
            "stopped": state.results.count("stopped"),
        }
        self._suite_runs.pop(state.suite_run_id, None)

        # Roll the member runs up into ONE aggregated suite report (best effort).
        try:
            from backend.services.report_generator import generate_suite_report

            generate_suite_report(state.suite_run_id)
        except Exception:
            logger.exception("suite_report_failed", suite_run_id=state.suite_run_id)

        await ws_manager.broadcast(
            {
                "type": "suite_run_finished",
                "suite_run_id": state.suite_run_id,
                "label": state.label,
                "total": total,
                "completed": len(state.results),
                "cancelled": state.cancel_requested,
                **totals,
            }
        )

    def request_stop_suite(self, suite_run_id: str) -> bool:
        state = self._suite_runs.get(suite_run_id)
        if state is None:
            return False
        state.cancel_requested = True
        if state.current_execution_id is not None:
            self.request_stop(state.current_execution_id)
        return True

    def running_suites(self) -> list[dict]:
        return [
            {
                "suite_run_id": s.suite_run_id,
                "label": s.label,
                "total": len(s.test_case_ids),
                "completed": len(s.results),
                "current_execution_id": s.current_execution_id,
            }
            for s in self._suite_runs.values()
        ]

    def request_stop(self, execution_id: int) -> bool:
        ctl = self._controllers.get(execution_id)
        if ctl is None:
            return False
        ctl.stop_requested.set()
        ctl.resume_event.set()
        ctl.step_gate.set()
        return True

    def request_pause(self, execution_id: int) -> bool:
        ctl = self._controllers.get(execution_id)
        if ctl is None:
            return False
        ctl.pause_requested.set()
        ctl.resume_event.clear()
        return True

    def request_resume(self, execution_id: int) -> bool:
        ctl = self._controllers.get(execution_id)
        if ctl is None:
            return False
        ctl.pause_requested.clear()
        ctl.resume_event.set()
        return True

    def request_next_step(self, execution_id: int) -> bool:
        ctl = self._controllers.get(execution_id)
        if ctl is None:
            return False
        ctl.step_gate.set()
        return True

    def running_ids(self) -> list[int]:
        return list(self._controllers)

    # ------------------------------------------------------------ internals

    async def _run(self, execution_id: int, mode: str) -> None:
        started = utcnow()
        status = "error"
        # Bind this async context so adapters can stream lines to the live log.
        set_execution(execution_id)
        try:
            with session_scope() as db:
                execution = db.get(Execution, execution_id)
                test_case = db.get(TestCase, execution.test_case_id)
                steps = [s.to_dict() for s in test_case.steps]

            ctl = self._controllers.get(execution_id)
            cycles = getattr(ctl, "cycles", 1) if ctl else 1
            if cycles > 1:
                status = await self._run_endurance(execution_id, steps, mode, cycles)
            elif mode == "parallel":
                status = await self._run_parallel(execution_id, steps)
            else:
                status = await self._run_serial(
                    execution_id, steps, step_by_step=(mode == "step")
                )
        except Exception as exc:
            logger.exception("execution_crashed", execution_id=execution_id)
            status = "error"
            await self._emit_log(execution_id, f"Executor error: {exc}", "error")
        finally:
            set_execution(None)
            ended = utcnow()
            duration = (ended - started).total_seconds()
            with session_scope() as db:
                execution = db.get(Execution, execution_id)
                execution.status = status
                execution.ended_at = ended
                execution.duration_seconds = round(duration, 3)
                payload = execution.to_dict()
            self._controllers.pop(execution_id, None)
            metrics.set_queue_length(len(self._controllers))
            metrics.record_execution(status, duration)

            # Generate the HTML report for this run (best effort).
            try:
                from backend.services.report_generator import generate_report

                generate_report(execution_id)
            except Exception:
                logger.exception("report_generation_failed", execution_id=execution_id)

            await ws_manager.broadcast(
                {"type": "execution_finished", "execution": payload}
            )

    async def _run_endurance(
        self, execution_id: int, steps: list[dict], mode: str, cycles: int
    ) -> str:
        """Run the whole case ``cycles`` times, recording a CycleResult per cycle
        and honouring stop conditions. Returns the aggregate run status."""
        ctl = self._controllers[execution_id]
        stop_conditions = ctl.stop_conditions or {}
        started = utcnow()
        statuses: list[str] = []
        for cycle_index in range(1, cycles + 1):
            if ctl.stop_requested.is_set():
                break
            ctl.cycle = cycle_index
            await self._emit_log(execution_id, f"——— Cycle {cycle_index}/{cycles} ———")
            cstart = utcnow()
            if mode == "parallel":
                cstatus = await self._run_parallel(execution_id, steps)
            else:
                cstatus = await self._run_serial(execution_id, steps)
            cend = utcnow()
            statuses.append(cstatus)
            self._record_cycle(execution_id, cycle_index, cstatus, cstart, cend)
            await ws_manager.broadcast(
                {
                    "type": "cycle_finished",
                    "execution_id": execution_id,
                    "cycle_index": cycle_index,
                    "total": cycles,
                    "status": cstatus,
                }
            )
            if cstatus == "stopped":
                break
            if self._should_stop_endurance(statuses, stop_conditions, started):
                await self._emit_log(
                    execution_id, f"Endurance stop condition met after cycle {cycle_index}"
                )
                break
        if not statuses:
            return "error"
        if any(s in ("failed", "error") for s in statuses):
            return "failed"
        if "stopped" in statuses:
            return "stopped"
        return "passed"

    def _record_cycle(
        self, execution_id: int, cycle_index: int, status: str, started_at, ended_at
    ) -> None:
        from backend.models.execution import CycleResult

        duration = round((ended_at - started_at).total_seconds(), 3)
        with session_scope() as db:
            db.add(
                CycleResult(
                    execution_id=execution_id,
                    cycle_index=cycle_index,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    duration_seconds=duration,
                    summary=f"cycle {cycle_index}: {status} in {duration}s",
                )
            )

    @staticmethod
    def _should_stop_endurance(statuses: list[str], sc: dict, started) -> bool:
        """Endurance stop conditions: max_duration, consecutive_failures, failure_threshold."""
        if not sc:
            return False
        max_duration = sc.get("max_duration")
        if max_duration and (utcnow() - started).total_seconds() >= float(max_duration):
            return True
        consecutive = sc.get("consecutive_failures")
        if consecutive:
            trailing = 0
            for s in reversed(statuses):
                if s in ("failed", "error"):
                    trailing += 1
                else:
                    break
            if trailing >= int(consecutive):
                return True
        threshold = sc.get("failure_threshold")
        if threshold and sum(1 for s in statuses if s in ("failed", "error")) >= int(threshold):
            return True
        return False

    async def _run_serial(
        self, execution_id: int, steps: list[dict], step_by_step: bool = False
    ) -> str:
        ctl = self._controllers[execution_id]
        outputs: dict[int, str] = {}
        any_failed = False
        # After a failure we enter teardown mode: only steps flagged
        # "_always_run" (collectors like logs/screenshots) still execute.
        aborted = False
        index = 0

        while index < len(steps):
            if ctl.stop_requested.is_set():
                return "stopped"
            await self._wait_if_paused(execution_id, ctl)

            step = steps[index]
            params = dict(step.get("parameters") or {})

            if aborted:
                group = params.get("_parallel_group")
                if group:
                    j = index
                    batch = []
                    while j < len(steps) and (
                        steps[j].get("parameters") or {}
                    ).get("_parallel_group") == group:
                        batch.append(steps[j])
                        j += 1
                    if any((s.get("parameters") or {}).get("_always_run") for s in batch):
                        await asyncio.gather(
                            *(self._execute_step(execution_id, s, outputs) for s in batch)
                        )
                    else:
                        for skipped in batch:
                            self._record_step(execution_id, skipped, "skipped", "", "", 0, 0.0)
                    index = j
                    continue
                if not params.get("_always_run"):
                    self._record_step(execution_id, step, "skipped", "", "", 0, 0.0)
                    index += 1
                    continue
                await self._emit_log(
                    execution_id,
                    f"Collector step {step.get('step_number')} runs despite earlier failure",
                )
                await self._execute_step(execution_id, step, outputs)
                index += 1
                continue

            # Conditional jump based on a previous step's output.
            condition = params.get("_if")
            if isinstance(condition, dict):
                jump = self._evaluate_condition(condition, outputs)
                if jump is not None:
                    target = self._index_for_step_number(steps, jump)
                    if target is not None:
                        await self._emit_log(
                            execution_id,
                            f"Condition on step {step['step_number']} jumps to step {jump}",
                        )
                        # Forward jump: record the leaped-over steps (including
                        # this branch step) as skipped. Backward jump (loop):
                        # steps[index:target] is empty, so nothing is recorded.
                        for skipped in steps[index:target]:
                            self._record_step(
                                execution_id, skipped, "skipped", "", "", 0, 0.0
                            )
                        index = target
                        continue

            # Parallel group: gather consecutive steps with the same group tag.
            group = params.get("_parallel_group")
            if group:
                batch = [step]
                j = index + 1
                while j < len(steps):
                    nxt = (steps[j].get("parameters") or {}).get("_parallel_group")
                    if nxt == group:
                        batch.append(steps[j])
                        j += 1
                    else:
                        break
                results = await asyncio.gather(
                    *(self._execute_step(execution_id, s, outputs) for s in batch)
                )
                if not all(results):
                    any_failed = True
                    # A failed parallel batch aborts the run just like a failed
                    # serial step, unless a member opts into continue-on-failure.
                    if not any(
                        (s.get("parameters") or {}).get("_continue_on_failure")
                        for s in batch
                    ):
                        aborted = True
                index = j
            else:
                # Pause before this step when running step-by-step, or when the
                # step itself is flagged with "_pause_before" (manual checkpoint).
                if step_by_step or params.get("_pause_before"):
                    await self._emit_log(
                        execution_id,
                        f"Waiting for 'Next' before step {step['step_number']}",
                        "info",
                        event_type="step_gate",
                    )
                    ctl.step_gate.clear()
                    await ctl.step_gate.wait()
                    if ctl.stop_requested.is_set():
                        return "stopped"
                passed = await self._execute_step(execution_id, step, outputs)
                if not passed:
                    any_failed = True
                    if not (step.get("parameters") or {}).get("_continue_on_failure"):
                        # Teardown mode: remaining steps are skipped except
                        # "_always_run" collectors (logs, screenshots, DLT...).
                        aborted = True
                index += 1

        return "failed" if any_failed else "passed"

    async def _run_parallel(self, execution_id: int, steps: list[dict]) -> str:
        outputs: dict[int, str] = {}
        results = await asyncio.gather(
            *(self._execute_step(execution_id, step, outputs) for step in steps)
        )
        return "passed" if all(results) else "failed"

    async def _execute_step(
        self, execution_id: int, step: dict, outputs: dict[int, str]
    ) -> bool:
        """Run a single step with loop, retry and resource locking. Returns pass/fail."""
        ctl = self._controllers.get(execution_id)
        params = dict(step.get("parameters") or {})
        label = str(params.pop("_label", "") or "")
        loop_count = max(1, int(params.pop("_loop", 1)))
        retry_count = int(params.pop("_retry", step.get("retry_count", 0)))
        params.pop("_if", None)
        params.pop("_parallel_group", None)
        params.pop("_pause_before", None)
        params.pop("_continue_on_failure", None)
        params.pop("_always_run", None)
        # Files planned for this step (uploaded in the designer) — surfaced as
        # the step's attachments in the report. Canvas-only keys are dropped too.
        planned_attachments = params.pop("_attachments", None) or []
        params.pop("_pos", None)
        params.pop("_uid", None)
        params.pop("_branch", None)
        timeout = float(step.get("timeout_seconds") or 30)
        action = step.get("action", "")
        adapter_name, _, action_name = action.partition(".")

        await ws_manager.broadcast(
            {
                "type": "step_update",
                "execution_id": execution_id,
                "step_number": step.get("step_number"),
                "action": action,
                "label": label,
                "status": "running",
            }
        )

        # Deliver any planned input files to the target BEFORE the step runs,
        # so a step can consume them (e.g. push a .dlt/config to the device).
        await self._deliver_attachments(
            execution_id, adapter_name, params, outputs, planned_attachments
        )

        start = utcnow()
        result = AdapterResult(success=False, error="not executed")
        attempts_used = 0

        for iteration in range(loop_count):
            if ctl is not None and ctl.stop_requested.is_set():
                result = AdapterResult(success=False, error="Execution stopped by user")
                break
            attempt = 0
            while True:
                attempt += 1
                attempts_used += 1
                result = await self._dispatch(
                    execution_id, adapter_name, action_name, params, outputs, timeout
                )
                if result.success or attempt > retry_count:
                    break
                backoff = min(2 ** attempt, 30)
                await self._emit_log(
                    execution_id,
                    f"Step {step.get('step_number')} attempt {attempt} failed "
                    f"({truncate(result.error, 200)}); retrying in {backoff}s",
                    "warning",
                )
                await asyncio.sleep(backoff)
            if not result.success:
                break
            if loop_count > 1:
                await self._emit_log(
                    execution_id,
                    f"Step {step.get('step_number')} loop {iteration + 1}/{loop_count} passed",
                )

        duration = (utcnow() - start).total_seconds()
        status = "passed" if result.success else "failed"
        outputs[int(step.get("step_number") or 0)] = result.output

        self._record_step(
            execution_id,
            step,
            status,
            truncate(result.output),
            truncate(result.error),
            attempts_used,
            duration,
            label=label,
        )

        artifact_path = result.data.get("artifact_path") if result.data else None
        if artifact_path:
            with session_scope() as db:
                db.add(
                    ExecutionArtifact(
                        execution_id=execution_id,
                        artifact_type=result.data.get("artifact_type", "log"),
                        file_path=str(artifact_path),
                        step_number=step.get("step_number"),
                    )
                )

        for attachment in planned_attachments:
            if isinstance(attachment, dict) and attachment.get("path"):
                with session_scope() as db:
                    db.add(
                        ExecutionArtifact(
                            execution_id=execution_id,
                            artifact_type="planned",
                            file_path=str(attachment["path"]),
                            step_number=step.get("step_number"),
                        )
                    )

        # Files the adapter produced/attached (e.g. a script's .dlt output).
        for extra in (result.data.get("artifact_paths") or []) if result.data else []:
            path = extra.get("path") if isinstance(extra, dict) else extra
            if not path:
                continue
            kind = extra.get("artifact_type", "log") if isinstance(extra, dict) else "log"
            with session_scope() as db:
                db.add(
                    ExecutionArtifact(
                        execution_id=execution_id,
                        artifact_type=kind,
                        file_path=str(path),
                        step_number=step.get("step_number"),
                    )
                )

        await ws_manager.broadcast(
            {
                "type": "step_update",
                "execution_id": execution_id,
                "step_number": step.get("step_number"),
                "action": action,
                "label": label,
                "status": status,
                "output": truncate(result.output, 2000),
                "error": truncate(result.error, 2000),
                "duration_seconds": round(duration, 3),
            }
        )
        return result.success

    async def _deliver_attachments(
        self,
        execution_id: int,
        adapter_name: str,
        params: dict,
        outputs: dict[int, str],
        attachments: list,
    ) -> None:
        """Push planned input files to the step's target before it executes.

        Each planned attachment may carry a ``deliver_to`` (remote destination).
        When present and the step targets a device, the file is uploaded first
        (SSH sftp / adb push) so the step can use it as input. Attachments with
        no destination are left alone — they simply attach to the report.
        """
        from pathlib import Path

        for att in attachments:
            if not isinstance(att, dict):
                continue
            local = att.get("path")
            remote = att.get("deliver_to") or att.get("remote_path")
            if not (local and remote):
                continue  # report-only attachment; nothing to deliver
            if adapter_name == "ssh":
                action = "upload_file"
            elif adapter_name == "adb":
                action = "push"
            else:
                await self._emit_log(
                    execution_id,
                    f"Cannot deliver {Path(str(local)).name}: the '{adapter_name}' "
                    "adapter has no file transfer — remove the destination or use "
                    "an SSH/ADB step.",
                    "warning",
                )
                continue
            transfer = {**params, "local_path": str(local), "remote_path": str(remote)}
            result = await self._dispatch(
                execution_id, adapter_name, action, transfer, outputs, timeout=120
            )
            if result.success:
                await self._emit_log(
                    execution_id, f"Delivered {Path(str(local)).name} → {remote}"
                )
            else:
                await self._emit_log(
                    execution_id,
                    f"Failed to deliver {Path(str(local)).name} → {remote}: "
                    f"{truncate(result.error, 200)}",
                    "warning",
                )

    async def _dispatch(
        self,
        execution_id: int,
        adapter_name: str,
        action_name: str,
        params: dict,
        outputs: dict[int, str],
        timeout: float,
    ) -> AdapterResult:
        """Resolve adapter + device, apply placeholders, lock resource, execute."""
        registry = get_registry()
        adapter = registry.get(adapter_name)
        if adapter is None:
            return AdapterResult(
                success=False,
                error=f"Unknown or disabled adapter '{adapter_name}'",
            )

        resolved = self._substitute_placeholders(params, outputs)

        # Apply the Run Target's machine config: substitute {{target.KEY}} from
        # its saved dependency paths and inject adb/ffmpeg paths as defaults.
        ctl = self._controllers.get(execution_id)
        target = ctl.target if ctl else None
        if target:
            resolved = self._apply_target_settings(resolved, target)

        device_id = resolved.pop("device_config_id", None)

        # Remote Run Target: when this run targets a remote host and the step
        # isn't explicitly bound to a device, route it to that host over SSH.
        if target and target.get("kind") == "remote" and not device_id:
            routed = await self._dispatch_remote(
                adapter_name, action_name, resolved, target, timeout
            )
            if routed is not None:
                return routed

        if device_id:
            try:
                with session_scope() as db:
                    device = resolve_device(db, int(device_id))
                merged = {
                    k: v for k, v in device.items() if not k.startswith("_")
                }
                merged.update(resolved)
                resolved = merged
            except ValueError as exc:
                return AdapterResult(success=False, error=str(exc))
            # Only device-bound steps contend for hardware — lock per device.
            try:
                async with lock_manager.acquire(f"device:{device_id}", execution_id):
                    return await adapter.execute(action_name, resolved, timeout=timeout)
            except TimeoutError as exc:
                return AdapterResult(success=False, error=str(exc))

        return await adapter.execute(action_name, resolved, timeout=timeout)

    @staticmethod
    def _apply_target_settings(resolved: dict, target: dict) -> dict:
        """Bake a Run Target's machine config into a step's params.

        - Substitute ``{{target.KEY}}`` in any string param with the machine's
          saved setting (e.g. ``{{target.power_script}}`` → its configured path).
        - Inject ``adb_path`` / ``ffmpeg_path`` defaults from the machine config so
          tools resolve to that machine's copies when the step doesn't set them.
        """
        settings = target.get("settings") or {}

        def sub(value: Any) -> Any:
            if isinstance(value, str):
                return _TARGET_RE.sub(lambda m: str(settings.get(m.group(1), "")), value)
            if isinstance(value, list):
                return [sub(v) for v in value]
            if isinstance(value, dict):
                return {k: sub(v) for k, v in value.items()}
            return value

        out = {k: sub(v) for k, v in resolved.items()}
        for key in ("adb_path", "ffmpeg_path"):
            if not out.get(key) and settings.get(key):
                out[key] = settings[key]
        return out

    @staticmethod
    def _target_conn(target: dict) -> dict:
        """SSH connection kwargs for a remote Run Target."""
        conn = {
            "host": target.get("host", ""),
            "port": target.get("port", 22),
            "username": target.get("username", ""),
            "domain": target.get("domain", ""),
            "domain_format": target.get("domain_format", ""),
            "password": target.get("password", ""),
            "key_file": target.get("key_file", ""),
        }
        # Windows OpenSSH runs cmd/powershell, not bash — don't bash-wrap the PATH.
        if target.get("os") == "windows":
            conn["raw_command"] = True
        return conn

    @staticmethod
    def _remote_command(adapter_name: str, action_name: str, params: dict) -> Optional[str]:
        """Translate a local step to a shell command to run on the remote host.

        Returns the command string, or None when the step should run locally
        regardless of the target (e.g. control-flow steps like wait/echo).
        """
        if adapter_name != "system":
            return None
        if action_name == "run_command":
            return str(params.get("command", "")).strip() or None
        if action_name == "run_file":
            raw = str(params.get("path") or params.get("script_path") or "").strip()
            if not raw:
                return None
            args = params.get("args")
            if isinstance(args, list):
                arg_str = " ".join(str(a) for a in args)
            else:
                arg_str = str(args or "")
            ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
            if ext == "ps1":
                base = f'powershell -NoProfile -ExecutionPolicy Bypass -File "{raw}"'
            elif ext == "py":
                base = f'python "{raw}"'
            elif ext == "sh":
                base = f'bash "{raw}"'
            else:  # .bat/.cmd/.exe or extensionless — run directly
                base = f'"{raw}"'
            return (base + (" " + arg_str if arg_str else "")).strip()
        return None

    async def _dispatch_remote(
        self,
        adapter_name: str,
        action_name: str,
        resolved: dict,
        target: dict,
        timeout: float,
    ) -> Optional[AdapterResult]:
        """Run an unbound step on the remote target over SSH (or None = local).

        - ``ssh`` steps inherit the target's host/credentials when unset.
        - ``system.run_command`` / ``system.run_file`` execute on the remote host.
        - ``system.run_script`` (inline sandbox) can't run remotely — clear error.
        - Everything else (wait/echo/assert, adb to local USB, …) runs locally.
        """
        registry = get_registry()
        if adapter_name == "ssh":
            ssh = registry.get("ssh")
            if ssh is None:
                return AdapterResult(success=False, error="SSH adapter unavailable")
            merged = {**self._target_conn(target), **resolved}
            return await ssh.execute(action_name, merged, timeout=timeout)

        if adapter_name == "system" and action_name == "run_script":
            return AdapterResult(
                success=False,
                error="Inline run_script can't run on a remote target — use "
                "run_command/run_file (which run on the remote host) or set the "
                "test's target to Local.",
            )

        command = self._remote_command(adapter_name, action_name, resolved)
        if command is None:
            return None  # not routable — run locally as usual

        ssh = registry.get("ssh")
        if ssh is None:
            return AdapterResult(success=False, error="SSH adapter unavailable")
        ssh_params = {
            **self._target_conn(target),
            "command": command,
            "command_timeout": timeout,
        }
        # Carry over expectation/attachment knobs so remote runs still match/attach.
        for key in (
            "expect_contains", "expect", "expectations", "match_mode",
            "attach_output", "attach_name", "raw_command", "source_profile",
        ):
            if key in resolved:
                ssh_params[key] = resolved[key]
        return await ssh.execute("execute_command", ssh_params, timeout=timeout)

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _substitute_placeholders(params: dict, outputs: dict[int, str]) -> dict:
        def sub_value(value: Any) -> Any:
            if isinstance(value, str):
                return _PLACEHOLDER_RE.sub(
                    lambda m: outputs.get(int(m.group(1)), ""), value
                )
            if isinstance(value, dict):
                return {k: sub_value(v) for k, v in value.items()}
            if isinstance(value, list):
                return [sub_value(v) for v in value]
            return value

        return {k: sub_value(v) for k, v in params.items()}

    @staticmethod
    def _evaluate_condition(
        condition: dict, outputs: dict[int, str]
    ) -> Optional[int]:
        """Return the step number to jump to, or None to continue normally."""
        source = int(condition.get("source_step", 0))
        needle = str(condition.get("contains", ""))
        matched = needle in outputs.get(source, "")
        if matched and condition.get("skip_to") is not None:
            return int(condition["skip_to"])
        if not matched and condition.get("else_skip_to") is not None:
            return int(condition["else_skip_to"])
        return None

    @staticmethod
    def _index_for_step_number(steps: list[dict], step_number: int) -> Optional[int]:
        for i, step in enumerate(steps):
            if step.get("step_number") == step_number:
                return i
        return None

    def _record_step(
        self,
        execution_id: int,
        step: dict,
        status: str,
        output: str,
        error: str,
        attempts: int,
        duration: float,
        label: str = "",
    ) -> None:
        if not label:
            label = str((step.get("parameters") or {}).get("_label", "") or "")
        with session_scope() as db:
            db.add(
                ExecutionStep(
                    execution_id=execution_id,
                    test_step_id=step.get("id"),
                    step_number=step.get("step_number") or 0,
                    action=step.get("action", ""),
                    label=label,
                    status=status,
                    actual_output=output,
                    error_message=error,
                    attempts=attempts,
                    duration_seconds=round(duration, 3),
                )
            )

    async def _wait_if_paused(self, execution_id: int, ctl: ExecutionController) -> None:
        if ctl.pause_requested.is_set():
            with session_scope() as db:
                execution = db.get(Execution, execution_id)
                execution.status = "paused"
            await self._emit_log(execution_id, "Execution paused", "info")
            await ctl.resume_event.wait()
            if not ctl.stop_requested.is_set():
                with session_scope() as db:
                    execution = db.get(Execution, execution_id)
                    execution.status = "running"
                await self._emit_log(execution_id, "Execution resumed", "info")

    async def _emit_log(
        self,
        execution_id: int,
        message: str,
        level: str = "info",
        event_type: str = "log",
    ) -> None:
        logger.info(message, execution_id=execution_id)
        await ws_manager.broadcast(
            {
                "type": event_type,
                "execution_id": execution_id,
                "level": level,
                "message": message,
                "timestamp": utcnow().isoformat(),
            }
        )


executor = TestExecutor()
