import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  ChevronRight,
  Circle,
  FileBarChart2,
  Loader2,
  MinusCircle,
  Pause,
  Play,
  PlayCircle,
  RefreshCw,
  Square,
  Terminal,
  XCircle,
} from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { StatusBadge } from '../components/common/Badge';
import { ActionChip } from '../components/common/ActionChip';
import { useToast } from '../components/common/Toast';
import { useApi } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';
import { useProject } from '../context/ProjectContext';
import {
  controlExecution,
  createSchedule,
  getExecution,
  listConfigs,
  listExecutions,
  listTestCases,
  startExecution,
  startSuiteRun,
  stopSuiteRun,
} from '../services/api';
import type { Execution, SchedulePayload, WsEvent } from '../types/domain';
import { formatDuration, formatTimestamp } from '../utils/formatting';

interface LogLine {
  timestamp: string;
  level: string;
  message: string;
  kind?: 'divider';
}

const STEP_ICONS: Record<string, JSX.Element> = {
  passed: <CheckCircle2 size={16} className="text-success" />,
  failed: <XCircle size={16} className="text-error" />,
  skipped: <MinusCircle size={16} className="text-text-muted" />,
  running: <Loader2 size={16} className="animate-spin text-info" />,
  pending: <Circle size={16} className="text-text-muted" />,
};

const LOG_COLORS: Record<string, string> = {
  error: 'text-red-400',
  warning: 'text-amber-400',
  success: 'text-emerald-400',
  info: 'text-sky-400',
};

function elapsedSince(startIso: string | null): string {
  if (!startIso) return '00:00:00';
  const start = new Date(startIso.endsWith('Z') ? startIso : `${startIso}Z`).getTime();
  const total = Math.max(0, Math.floor((Date.now() - start) / 1000));
  const h = String(Math.floor(total / 3600)).padStart(2, '0');
  const m = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const s = String(total % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

export function ExecutionPage() {
  const { activeProjectId } = useProject();
  const toast = useToast();
  const navigate = useNavigate();

  /** Jump to the Reports screen focused on a finished run. */
  const viewReport = (id: number) => navigate(`/reports?focus=${id}`);

  const { data: testCases } = useApi(
    () => (activeProjectId ? listTestCases(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );
  const { data: executions, refetch: refetchExecutions } = useApi(
    () => listExecutions({ project_id: activeProjectId ?? undefined, limit: 30 }),
    [activeProjectId],
  );
  const { data: allConfigs } = useApi(
    () => (activeProjectId ? listConfigs(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );
  const machines = useMemo(
    () => (allConfigs ?? []).filter((c) => c.config_type === 'target'),
    [allConfigs],
  );

  // ---- run target: pick a case, choose scope -------------------------------

  const [caseId, setCaseId] = useState<number | ''>('');
  const [scope, setScope] = useState<'case' | 'scenario' | 'suite'>('case');
  const [when, setWhen] = useState<'now' | 'later'>('now');
  const [runAt, setRunAt] = useState('');
  const [cycles, setCycles] = useState(1); // repeat N times (stability/soak)
  // Where to run: '' = Local (this machine), or a saved RDP/remote machine id.
  // Defaults to the selected case's saved machine when one is set.
  const [machineId, setMachineId] = useState<number | ''>('');

  const cases = testCases ?? [];
  const selectedCase = cases.find((c) => c.id === caseId) ?? null;
  const activeSuite = selectedCase?.test_type || 'Ungrouped';
  const activeScenario = selectedCase?.scenario || 'General';

  // Default-select the first case once cases load.
  useEffect(() => {
    if (caseId === '' && cases.length > 0) setCaseId(cases[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases.length]);

  // When the selected case changes, default the machine to its saved target.
  useEffect(() => {
    setMachineId(selectedCase?.default_target_id ?? '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // Cases grouped by suite → for the grouped <optgroup> picker.
  const casesBySuite = useMemo(() => {
    const map = new Map<string, typeof cases>();
    for (const tc of cases) {
      const s = tc.test_type || 'Ungrouped';
      if (!map.has(s)) map.set(s, []);
      map.get(s)!.push(tc);
    }
    return [...map.entries()];
  }, [cases]);

  // ---- live execution state --------------------------------------------------

  const [activeExecution, setActiveExecution] = useState<Execution | null>(null);
  const [suiteRun, setSuiteRun] = useState<{
    id: string;
    label: string;
    total: number;
    index: number;
    caseName: string;
    finished: boolean;
  } | null>(null);
  const [queue, setQueue] = useState<{ id: number; name: string; status: string }[]>([]);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [logFilter, setLogFilter] = useState('all');
  const [logSearch, setLogSearch] = useState('');
  const [runningStep, setRunningStep] = useState<{ number: number; at: number } | null>(null);
  const [stepGateOpen, setStepGateOpen] = useState(false);
  const [elapsed, setElapsed] = useState('00:00:00');
  const logEndRef = useRef<HTMLDivElement>(null);
  const logBoxRef = useRef<HTMLDivElement>(null);
  const activeIdRef = useRef<number | null>(null);
  activeIdRef.current = activeExecution?.id ?? null;
  const suiteRunIdRef = useRef<string | null>(null);
  suiteRunIdRef.current = suiteRun && !suiteRun.finished ? suiteRun.id : null;

  const isRunning =
    activeExecution != null &&
    ['queued', 'running', 'paused'].includes(activeExecution.status);
  const suiteActive = suiteRun != null && !suiteRun.finished;

  // On mount: follow the most recent running execution, if any.
  useEffect(() => {
    const latestRunning = (executions ?? []).find((e) =>
      ['queued', 'running', 'paused'].includes(e.status),
    );
    if (latestRunning && !activeExecution) void refreshActive(latestRunning.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executions]);

  // Auto-scroll the log box only (never the page), and only when already at the
  // bottom — so scrolling up to read isn't yanked back down.
  useEffect(() => {
    const box = logBoxRef.current;
    if (!box) return;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    if (atBottom) box.scrollTop = box.scrollHeight;
  }, [logs]);

  useEffect(() => {
    if (!isRunning) return;
    const timer = setInterval(
      () => setElapsed(elapsedSince(activeExecution?.started_at ?? null)),
      1000,
    );
    return () => clearInterval(timer);
  }, [isRunning, activeExecution?.started_at]);

  const pushLog = (level: string, message: string, kind?: 'divider') =>
    setLogs((current) => [
      ...current,
      { timestamp: new Date().toLocaleTimeString(), level, message, kind },
    ]);

  const refreshActive = async (id: number) => {
    setActiveExecution(await getExecution(id));
  };

  useWebSocket((event: WsEvent) => {
    if (event.type === 'execution_started' || event.type === 'execution_finished') {
      void refetchExecutions();
    }

    // ---- suite run lifecycle ------------------------------------------------
    if (event.type === 'suite_run_started' && event.suite_run_id) {
      setSuiteRun({
        id: event.suite_run_id,
        label: event.label ?? 'Suite run',
        total: event.total ?? 0,
        index: 0,
        caseName: '',
        finished: false,
      });
      setQueue(
        (event.test_cases ?? []).map((tc) => ({ ...tc, status: 'pending' })),
      );
      setLogs([]);
      pushLog('info', `Suite run started: ${event.label} (${event.total} test cases)`);
      return;
    }
    if (event.type === 'suite_run_update' && event.suite_run_id === suiteRunIdRef.current) {
      setSuiteRun((current) =>
        current
          ? {
              ...current,
              index: event.current_index ?? current.index,
              caseName: event.test_case_name ?? '',
            }
          : current,
      );
      setQueue((current) =>
        current.map((entry) =>
          entry.id === event.test_case_id ? { ...entry, status: 'running' } : entry,
        ),
      );
      pushLog(
        'info',
        `▶ Test case ${event.current_index}/${event.total}: ${event.test_case_name}`,
      );
      if (event.execution_id) void refreshActive(event.execution_id);
      return;
    }
    if (event.type === 'suite_run_finished' && event.suite_run_id === suiteRunIdRef.current) {
      setSuiteRun((current) => (current ? { ...current, finished: true } : current));
      setQueue((current) =>
        current.map((entry) =>
          entry.status === 'pending' || entry.status === 'running'
            ? { ...entry, status: event.cancelled ? 'stopped' : entry.status }
            : entry,
        ),
      );
      pushLog(
        (event.failed ?? 0) > 0 ? 'warning' : 'success',
        `Suite run finished: ${event.passed} passed, ${event.failed} failed` +
          (event.cancelled ? ' (cancelled)' : ''),
      );
      return;
    }

    // Track per-test-case outcomes for the queue panel.
    if (
      event.type === 'execution_finished' &&
      event.execution?.suite_run_id &&
      event.execution.suite_run_id === suiteRunIdRef.current
    ) {
      const finished = event.execution;
      setQueue((current) =>
        current.map((entry) =>
          entry.id === finished.test_case_id && entry.status === 'running'
            ? { ...entry, status: finished.status }
            : entry,
        ),
      );
    }

    // Auto-follow executions that belong to the active suite run.
    if (
      event.type === 'execution_started' &&
      event.execution?.suite_run_id &&
      event.execution.suite_run_id === suiteRunIdRef.current
    ) {
      setActiveExecution(event.execution);
      return;
    }

    const id = event.execution_id ?? event.execution?.id;
    if (activeIdRef.current == null || id !== activeIdRef.current) return;

    if (event.type === 'step_update') {
      const name = event.label || event.action || '';
      if (event.status === 'running') {
        setRunningStep({ number: event.step_number ?? 0, at: Date.now() });
        // Visual partition between steps in the log stream.
        pushLog('info', `STEP ${event.step_number} · ${name}`, 'divider');
        pushLog('info', 'started');
      } else {
        setRunningStep((cur) =>
          cur && cur.number === event.step_number ? null : cur,
        );
        pushLog(
          event.status === 'passed' ? 'success' : event.status === 'failed' ? 'error' : 'info',
          `${event.status?.toUpperCase()}${
            event.duration_seconds != null ? ` in ${event.duration_seconds}s` : ''
          }` +
            (event.error ? ` — ${event.error}` : '') +
            (event.output ? `\n${event.output}` : ''),
        );
      }
      void refreshActive(activeIdRef.current);
    } else if (event.type === 'log' || event.type === 'step_gate') {
      if (event.type === 'step_gate') setStepGateOpen(true);
      pushLog(event.level ?? 'info', event.message ?? '');
    } else if (event.type === 'execution_finished') {
      pushLog(
        event.execution?.status === 'passed' ? 'success' : 'warning',
        `Execution finished: ${event.execution?.status}`,
      );
      setStepGateOpen(false);
      setRunningStep(null);
      void refreshActive(activeIdRef.current);
    }
  });

  const run = async () => {
    if (!selectedCase) {
      toast('info', 'Pick a test case to run');
      return;
    }
    try {
      // "Run later" creates a one-time schedule instead of starting now.
      if (when === 'later') {
        if (!runAt) {
          toast('info', 'Pick a date and time first');
          return;
        }
        const payload: SchedulePayload = { schedule_type: 'once', run_at: runAt };
        if (scope === 'case') {
          payload.test_case_id = selectedCase.id;
        } else {
          payload.suite = activeSuite;
          if (scope === 'scenario') payload.scenario = activeScenario;
          payload.project_id = activeProjectId ?? undefined;
        }
        const schedule = await createSchedule(payload);
        toast('success', `Scheduled: ${schedule.description}`);
        setWhen('now');
        return;
      }

      const cycleCount = Math.max(1, Math.min(1000, Math.floor(cycles) || 1));

      // Single case, single cycle → fast path: one execution.
      if (scope === 'case' && cycleCount === 1) {
        setSuiteRun(null);
        setQueue([]);
        const execution = await startExecution(
          selectedCase.id,
          'serial',
          machineId === '' ? null : Number(machineId),
        );
        setActiveExecution(execution);
        setLogs([]);
        setElapsed('00:00:00');
        pushLog('info', `Execution started — Run ID: RUN-${execution.id}`);
        toast('success', `Run RUN-${execution.id} started`);
        return;
      }

      // Stability / soak: resolve the scope to a list of case ids, then repeat
      // that list `cycleCount` times so the engine runs them back-to-back.
      const baseIds =
        scope === 'case'
          ? [selectedCase.id]
          : cases
              .filter(
                (c) =>
                  (c.test_type || 'Ungrouped') === activeSuite &&
                  (scope === 'suite' ||
                    (c.scenario || 'General') === activeScenario),
              )
              .map((c) => c.id);
      if (baseIds.length === 0) {
        toast('info', 'No test cases match this scope');
        return;
      }
      const repeated: number[] = [];
      for (let i = 0; i < cycleCount; i++) repeated.push(...baseIds);

      setActiveExecution(null);
      setElapsed('00:00:00');
      const result = await startSuiteRun({
        project_id: activeProjectId ?? undefined,
        test_case_ids: repeated,
        mode: 'serial',
        target_id: machineId === '' ? null : Number(machineId),
      });
      const cycleNote = cycleCount > 1 ? ` (${cycleCount} cycles)` : '';
      toast('success', `Run started — ${result.total} executions${cycleNote}`);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      toast('error', detail ?? `Failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const control = async (action: 'stop' | 'pause' | 'resume' | 'next') => {
    if (action === 'stop' && suiteRun && !suiteRun.finished) {
      // Cancelling a suite run stops the current execution and the queue.
      try {
        await stopSuiteRun(suiteRun.id);
        pushLog('warning', 'Suite run cancellation requested');
      } catch {
        toast('error', 'Suite run already finished');
      }
      return;
    }
    if (!activeExecution) return;
    try {
      await controlExecution(activeExecution.id, action);
      if (action === 'next') setStepGateOpen(false);
    } catch {
      toast('error', `Cannot ${action} — execution may have finished`);
    }
  };

  const steps = activeExecution?.steps ?? [];
  const doneSteps = steps.filter((s) => s.status !== 'pending').length;
  const totalSteps = steps.length;
  const passed = steps.filter((s) => s.status === 'passed').length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const skipped = steps.filter((s) => s.status === 'skipped').length;
  const progress = totalSteps > 0 ? Math.round((doneSteps / totalSteps) * 100) : 0;

  const logQuery = logSearch.trim().toLowerCase();
  const visibleLogs = logs.filter(
    (line) =>
      (logFilter === 'all' || line.level === logFilter) &&
      (!logQuery || line.message.toLowerCase().includes(logQuery)),
  );

  return (
    <MainLayout
      title="Execution Console"
      subtitle="Run suites live with full control"
      icon={<Terminal size={18} />}
      iconClass="bg-emerald-500/15 text-emerald-400"
    >
      <div className="space-y-4">
        {/* Launch bar */}
        <div className="card flex flex-wrap items-center gap-3 p-4">
          <p className="w-full text-xs text-text-muted">
            Choose <b>what</b> to run (a test case, its scenario, or the whole suite),
            <b> where</b> to run it (this machine or a saved RDP machine), and
            <b> when</b> — then press Start.
          </p>
          {/* 1. Pick a test case (grouped by suite) */}
          <label className="flex min-w-[260px] flex-1 flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              Test case
            </span>
            <select
              className="input font-medium"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value === '' ? '' : Number(e.target.value))}
              aria-label="Test case"
            >
              {cases.length === 0 && (
                <option value="">No test cases yet — create one in the Designer</option>
              )}
              {casesBySuite.map(([suiteName, list]) => (
                <optgroup key={suiteName} label={suiteName}>
                  {list.map((tc) => (
                    <option key={tc.id} value={tc.id}>
                      {(tc.scenario || 'General')} · {tc.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          {/* 2. Scope: just this case, its scenario, or its whole suite */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              Run
            </span>
            <div className="inline-flex overflow-hidden rounded-lg border border-border text-sm">
              {([
                ['case', 'This case'],
                ['scenario', 'Scenario'],
                ['suite', 'Suite'],
              ] as const).map(([val, lbl]) => (
                <button
                  key={val}
                  type="button"
                  disabled={!selectedCase}
                  className={`px-3 py-2 font-medium transition-colors disabled:opacity-40 ${
                    scope === val
                      ? 'bg-primary text-white'
                      : 'bg-surface text-text-secondary hover:bg-surface-2'
                  }`}
                  onClick={() => setScope(val)}
                >
                  {lbl}
                </button>
              ))}
            </div>
          </div>

          {/* 3. Where: Local or a saved RDP machine */}
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              Run on
            </span>
            <select
              className="input"
              value={machineId}
              onChange={(e) => setMachineId(e.target.value === '' ? '' : Number(e.target.value))}
              title="Where the test runs: this machine (Local) or a saved RDP / remote machine"
            >
              <option value="">Local (this machine)</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                  {m.settings?.kind === 'remote' ? ` — ${m.settings?.hostname ?? 'RDP'}` : ' (local)'}
                </option>
              ))}
            </select>
          </label>

          {/* 4. When */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
              When
            </span>
            <div className="flex items-center gap-2">
              <div className="inline-flex overflow-hidden rounded-lg border border-border text-sm">
                {(['now', 'later'] as const).map((w) => (
                  <button
                    key={w}
                    type="button"
                    className={`px-3 py-2 font-medium capitalize transition-colors ${
                      when === w
                        ? 'bg-primary text-white'
                        : 'bg-surface text-text-secondary hover:bg-surface-2'
                    }`}
                    onClick={() => setWhen(w)}
                  >
                    {w}
                  </button>
                ))}
              </div>
              {when === 'later' && (
                <input
                  type="datetime-local"
                  className="input w-48"
                  value={runAt}
                  onChange={(e) => setRunAt(e.target.value)}
                  aria-label="Scheduled date and time"
                />
              )}
            </div>
          </div>

          {/* 4. Cycles (stability / soak) — only meaningful for an immediate run */}
          {when === 'now' && (
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                Cycles
              </span>
              <input
                type="number"
                min={1}
                max={1000}
                className="input w-24"
                value={cycles}
                onChange={(e) => setCycles(Math.max(1, Number(e.target.value) || 1))}
                title="Repeat the selected scope this many times back-to-back (soak / stability run)"
                aria-label="Number of cycles"
              />
            </div>
          )}

          <div className="ml-auto flex gap-2">
            {activeExecution && !isRunning && !suiteActive && (
              <button
                className="btn bg-indigo-600 text-white hover:opacity-90"
                onClick={() => viewReport(activeExecution.id)}
                title="Open the report for this run"
              >
                <FileBarChart2 size={15} /> View report
              </button>
            )}
            {stepGateOpen && isRunning && (
              <button className="btn-primary" onClick={() => void control('next')}>
                <ChevronRight size={15} /> Next step
              </button>
            )}
            <button
              className="btn bg-emerald-600 text-white hover:opacity-90"
              onClick={run}
              disabled={when === 'now' && (isRunning || suiteActive)}
            >
              <PlayCircle size={15} /> {when === 'later' ? 'Schedule' : 'Start'}
            </button>
            {activeExecution?.status === 'paused' ? (
              <button
                className="btn bg-sky-600 text-white hover:opacity-90"
                onClick={() => void control('resume')}
                disabled={!isRunning}
              >
                <Play size={15} /> Resume
              </button>
            ) : (
              <button
                className="btn bg-amber-500 text-white hover:opacity-90"
                onClick={() => void control('pause')}
                disabled={!isRunning}
              >
                <Pause size={15} /> Pause
              </button>
            )}
            <button
              className="btn-danger"
              onClick={() => void control('stop')}
              disabled={!isRunning && !suiteActive}
            >
              <Square size={15} /> Cancel
            </button>
          </div>
          <div className="w-full border-t border-border/60 pt-2 text-xs text-text-secondary">
            {selectedCase ? (
              <>
                <span className="font-semibold text-text-primary">▶ Will run </span>
                {scope === 'case' ? (
                  <>
                    test case <b>{selectedCase.name}</b>
                  </>
                ) : scope === 'scenario' ? (
                  <>
                    every case in scenario <b>{activeScenario}</b> (suite <b>{activeSuite}</b>)
                  </>
                ) : (
                  <>
                    the whole suite <b>{activeSuite}</b>
                  </>
                )}
                {' '}· on{' '}
                <b>
                  {machineId === ''
                    ? 'Local'
                    : machines.find((m) => m.id === machineId)?.label ?? 'machine'}
                </b>
                {when === 'now' && cycles > 1 && (
                  <>
                    {' '}· <b>{cycles}×</b> back-to-back (soak)
                  </>
                )}
                {when === 'later' && runAt && (
                  <>
                    {' '}· scheduled for <b>{runAt.replace('T', ' ')}</b>
                  </>
                )}
              </>
            ) : (
              <span>Pick a test case above to run.</span>
            )}
          </div>
        </div>

        {/* Suite run progress banner */}
        {suiteRun && (
          <div className="card flex flex-wrap items-center gap-4 border-violet-500/40 bg-violet-500/5 px-5 py-3.5">
            <span className="badge bg-violet-500/15 text-violet-400">SUITE RUN</span>
            <span className="font-semibold">{suiteRun.label}</span>
            <span className="text-sm text-text-secondary">
              {suiteRun.finished
                ? 'finished'
                : `Test case ${suiteRun.index || 1} of ${suiteRun.total}` +
                  (suiteRun.caseName ? ` — ${suiteRun.caseName}` : '')}
            </span>
            <div className="ml-auto h-2 w-48 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-500"
                style={{
                  width: `${
                    suiteRun.finished
                      ? 100
                      : Math.round(
                          ((Math.max(suiteRun.index, 1) - 1) / Math.max(suiteRun.total, 1)) * 100,
                        )
                  }%`,
                }}
              />
            </div>
            {/* Run queue: every test case in this suite run with live status */}
            {queue.length > 0 && (
              <div className="flex w-full flex-wrap gap-1.5 pt-1">
                {queue.map((entry, index) => (
                  <span
                    key={entry.id}
                    className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium ${
                      entry.status === 'running'
                        ? 'border-info/50 bg-info/10 text-info'
                        : entry.status === 'passed'
                          ? 'border-success/40 bg-success/10 text-success'
                          : ['failed', 'error'].includes(entry.status)
                            ? 'border-error/40 bg-error/10 text-error'
                            : entry.status === 'stopped'
                              ? 'border-warning/40 bg-warning/10 text-warning'
                              : 'border-border bg-surface text-text-muted'
                    }`}
                  >
                    {entry.status === 'running' ? (
                      <Loader2 size={11} className="animate-spin" />
                    ) : entry.status === 'passed' ? (
                      <CheckCircle2 size={11} />
                    ) : ['failed', 'error'].includes(entry.status) ? (
                      <XCircle size={11} />
                    ) : (
                      <Circle size={11} />
                    )}
                    {index + 1}. {entry.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
          {/* Execution progress */}
          <div className="card p-5 xl:col-span-3">
            {activeExecution ? (
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <button
                  className="badge bg-indigo-500/15 font-mono text-indigo-400 hover:bg-indigo-500/30"
                  onClick={() => viewReport(activeExecution.id)}
                  title="Open this run's report"
                >
                  RUN-{activeExecution.id} ↗
                </button>
                <h3 className="text-sm font-bold">
                  {activeExecution.test_case_name ?? `Test case #${activeExecution.test_case_id}`}
                </h3>
                {(activeExecution.suite || activeExecution.scenario) && (
                  <span className="badge bg-purple-500/15 text-purple-400">
                    {activeExecution.suite}
                    {activeExecution.scenario ? ` / ${activeExecution.scenario}` : ''}
                  </span>
                )}
                {activeExecution.target_label && (
                  <span className="badge bg-orange-500/15 text-orange-400" title="Ran on this machine">
                    🖥 {activeExecution.target_label}
                  </span>
                )}
                <StatusBadge status={activeExecution.status} />
                {totalSteps > 0 && (
                  <span className="ml-auto text-xs text-text-muted">
                    Step {Math.min(doneSteps + 1, totalSteps)} of {totalSteps}
                  </span>
                )}
              </div>
            ) : (
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Execution Progress</h3>
              </div>
            )}
            <div className="mb-4 h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="space-y-1.5">
              {steps.map((step) => (
                <div
                  key={step.id}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
                    step.status === 'running'
                      ? 'border-info bg-info/10 ring-1 ring-info/40'
                      : step.status === 'passed'
                        ? 'border-success/30 bg-success/5'
                        : step.status === 'failed'
                          ? 'border-error/40 bg-error/5'
                          : 'border-border bg-background'
                  }`}
                >
                  <span className="w-5 text-center text-xs font-bold text-text-muted">
                    {step.step_number}
                  </span>
                  {STEP_ICONS[step.status] ?? STEP_ICONS.pending}
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">
                    {step.label || step.action}
                  </span>
                  <ActionChip action={step.action} />
                  <span
                    className={`w-16 text-right font-mono text-xs ${
                      step.status === 'running' && runningStep?.number === step.step_number
                        ? 'font-bold text-info'
                        : 'text-text-muted'
                    }`}
                  >
                    {step.status === 'running' && runningStep?.number === step.step_number
                      ? `${((Date.now() - runningStep.at) / 1000).toFixed(1)}s`
                      : step.duration_seconds != null
                        ? formatDuration(step.duration_seconds)
                        : '—'}
                  </span>
                </div>
              ))}
              {!activeExecution && (
                <p className="py-10 text-center text-sm text-text-muted">
                  Pick a suite, scenario and test case above, then press Start —
                  or load a previous run from the history below.
                </p>
              )}
            </div>
          </div>

          {/* Live logs */}
          <div className="card flex flex-col p-5 xl:col-span-2">
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-semibold">Live Logs</h3>
              {visibleLogs.length > 0 && (
                <span className="rounded-full bg-surface-2 px-2 text-[10px] text-text-muted">
                  {visibleLogs.length}
                </span>
              )}
              <input
                className="ml-auto w-40 rounded-md border border-border bg-background px-2 py-1 text-xs"
                placeholder="Search logs…"
                value={logSearch}
                onChange={(e) => setLogSearch(e.target.value)}
                aria-label="Search logs"
              />
              <select
                className="rounded-md border border-border bg-background px-2 py-1 text-xs"
                value={logFilter}
                onChange={(e) => setLogFilter(e.target.value)}
                aria-label="Filter logs"
              >
                <option value="all">All</option>
                <option value="info">Info</option>
                <option value="success">Success</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
            </div>
            <div
              ref={logBoxRef}
              className="min-h-[460px] flex-1 overflow-auto rounded-lg bg-[#0b1220] p-3 font-mono text-xs leading-relaxed"
            >
              {visibleLogs.length === 0 && (
                <span className="text-slate-500">Logs stream here in real time…</span>
              )}
              {visibleLogs.map((line, index) =>
                line.kind === 'divider' ? (
                  <div key={index} className="my-2 flex items-center gap-2">
                    <span className="h-px flex-1 bg-violet-500/40" />
                    <span className="rounded-md border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[11px] font-bold tracking-wide text-violet-300">
                      {line.message}
                    </span>
                    <span className="h-px flex-1 bg-violet-500/40" />
                  </div>
                ) : (
                  <div key={index} className="whitespace-pre-wrap pl-2">
                    <span className="text-slate-500">[{line.timestamp}]</span>{' '}
                    <span className={LOG_COLORS[line.level] ?? 'text-slate-300'}>
                      [{line.level.toUpperCase()}]
                    </span>{' '}
                    <span className="text-slate-200">{line.message}</span>
                  </div>
                ),
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>

        {/* Run summary bar */}
        {activeExecution && (
          <div className="card flex flex-wrap items-center gap-x-10 gap-y-3 px-6 py-4">
            {[
              {
                label: 'Run ID',
                value: (
                  <button
                    className="font-bold text-indigo-400 underline-offset-2 hover:underline"
                    onClick={() => viewReport(activeExecution.id)}
                    title="Open this run's report"
                  >
                    RUN-{activeExecution.id} ↗
                  </button>
                ),
              },
              { label: 'Status', value: <StatusBadge status={activeExecution.status} /> },
              {
                label: 'Triggered by',
                value: (
                  <span className="font-semibold text-emerald-400">
                    {activeExecution.triggered_by || 'admin'}
                  </span>
                ),
              },
              { label: 'Total steps', value: totalSteps },
              {
                label: 'Passed',
                value: <span className="font-bold text-success">{passed}</span>,
              },
              {
                label: 'Failed',
                value: <span className="font-bold text-error">{failed}</span>,
              },
              {
                label: 'Skipped',
                value: <span className="font-bold text-text-muted">{skipped}</span>,
              },
              {
                label: 'Elapsed',
                value: (
                  <span className="font-mono font-bold text-amber-400">
                    {isRunning
                      ? elapsed
                      : formatDuration(activeExecution.duration_seconds)}
                  </span>
                ),
              },
            ].map((item) => (
              <div key={item.label}>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                  {item.label}
                </div>
                <div className="text-sm">{item.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* History */}
        <div className="card p-5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold">Recent runs</h3>
            <button
              className="btn-ghost p-1.5"
              onClick={() => void refetchExecutions()}
              aria-label="Refresh"
            >
              <RefreshCw size={14} className="text-sky-400" />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2 xl:grid-cols-3">
            {(executions ?? []).map((execution) => (
              <button
                key={execution.id}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors ${
                  activeExecution?.id === execution.id
                    ? 'border-primary/60 bg-primary/10'
                    : 'border-border bg-background hover:border-primary/30'
                }`}
                onClick={() => {
                  setLogs([]);
                  void refreshActive(execution.id);
                }}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    RUN-{execution.id} · {execution.test_case_name}
                  </div>
                  <div className="text-[11px] text-text-muted">
                    {formatTimestamp(execution.started_at)} ·{' '}
                    {formatDuration(execution.duration_seconds)} · by{' '}
                    {execution.triggered_by || 'admin'}
                  </div>
                </div>
                <StatusBadge status={execution.status} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
