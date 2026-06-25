import { useMemo, useState } from 'react';
import { CalendarClock, CalendarPlus, Trash2 } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { Spinner } from '../components/common/Spinner';
import { useToast } from '../components/common/Toast';
import { useApi } from '../hooks/useApi';
import { useProject } from '../context/ProjectContext';
import {
  createSchedule,
  deleteSchedule,
  listSchedules,
  listTestCases,
  toggleSchedule,
} from '../services/api';
import type { SchedulePayload } from '../types/domain';
import { formatTimestamp } from '../utils/formatting';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

const TYPE_OPTIONS = [
  { value: 'once', label: 'Run once' },
  { value: 'daily', label: 'Every day' },
  { value: 'weekly', label: 'Every week' },
] as const;

export function SchedulesPage() {
  const { activeProjectId } = useProject();
  const toast = useToast();
  const { data: schedules, loading, refetch } = useApi(listSchedules, []);
  const { data: testCases } = useApi(
    () => (activeProjectId ? listTestCases(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );

  // What to run: a single test case, a whole scenario, or a whole suite.
  const [targetKind, setTargetKind] = useState<'case' | 'scenario' | 'suite'>('case');
  const [testCaseId, setTestCaseId] = useState<number | ''>('');
  const [suite, setSuite] = useState('');
  const [scenario, setScenario] = useState('');
  const [type, setType] = useState<'once' | 'daily' | 'weekly'>('once');
  const [runAt, setRunAt] = useState('');
  const [timeOfDay, setTimeOfDay] = useState('09:00');
  const [weekday, setWeekday] = useState(0);
  const [startAt, setStartAt] = useState('');
  const [endAt, setEndAt] = useState('');

  const suites = useMemo(
    () => [...new Set((testCases ?? []).map((tc) => tc.test_type || 'Ungrouped'))],
    [testCases],
  );
  const scenarios = useMemo(
    () => [
      ...new Set(
        (testCases ?? [])
          .filter((tc) => (tc.test_type || 'Ungrouped') === suite)
          .map((tc) => tc.scenario || 'General'),
      ),
    ],
    [testCases, suite],
  );

  const add = async () => {
    const payload: SchedulePayload = {
      schedule_type: type,
      project_id: activeProjectId ?? undefined,
    };
    if (targetKind === 'case') {
      if (testCaseId === '') {
        toast('info', 'Select a test case');
        return;
      }
      payload.test_case_id = Number(testCaseId);
    } else {
      if (!suite) {
        toast('info', 'Select a suite');
        return;
      }
      payload.suite = suite;
      if (targetKind === 'scenario') {
        if (!scenario) {
          toast('info', 'Select a scenario');
          return;
        }
        payload.scenario = scenario;
      }
    }
    if (type === 'once') {
      if (!runAt) {
        toast('info', 'Pick a date and time');
        return;
      }
      payload.run_at = runAt;
    } else {
      payload.time_of_day = timeOfDay;
      if (type === 'weekly') payload.weekday = weekday;
      // Optional active window for recurring schedules.
      if (startAt) payload.start_at = startAt;
      if (endAt) payload.end_at = endAt;
    }
    try {
      await createSchedule(payload);
      toast('success', 'Schedule created');
      void refetch();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast('error', detail ?? 'Could not create the schedule');
    }
  };

  return (
    <MainLayout
      title="Scheduler"
      subtitle="Plan test runs by date and time — no cron knowledge needed"
      icon={<CalendarClock size={18} />}
      iconClass="bg-violet-500/15 text-violet-400"
    >
      <div className="space-y-4">
        <div className="card flex flex-wrap items-end gap-3 p-5">
          <div>
            <label className="label">What to run</label>
            <select
              className="input w-36"
              value={targetKind}
              onChange={(e) => setTargetKind(e.target.value as typeof targetKind)}
            >
              <option value="case">Test case</option>
              <option value="scenario">Scenario</option>
              <option value="suite">Whole suite</option>
            </select>
          </div>
          {targetKind === 'case' ? (
            <div className="min-w-[220px] flex-1">
              <label className="label">Test case</label>
              <select
                className="input"
                value={testCaseId}
                onChange={(event) =>
                  setTestCaseId(event.target.value === '' ? '' : Number(event.target.value))
                }
              >
                <option value="">Select…</option>
                {(testCases ?? []).map((testCase) => (
                  <option key={testCase.id} value={testCase.id}>
                    {testCase.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <>
              <div className="min-w-[160px]">
                <label className="label">Suite</label>
                <select
                  className="input"
                  value={suite}
                  onChange={(e) => {
                    setSuite(e.target.value);
                    setScenario('');
                  }}
                >
                  <option value="">Select…</option>
                  {suites.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
              {targetKind === 'scenario' && (
                <div className="min-w-[160px]">
                  <label className="label">Scenario</label>
                  <select
                    className="input"
                    value={scenario}
                    onChange={(e) => setScenario(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {scenarios.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
          <div>
            <label className="label">Repeat</label>
            <select
              className="input w-36"
              value={type}
              onChange={(e) => setType(e.target.value as typeof type)}
            >
              {TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          {type === 'once' ? (
            <div>
              <label className="label">Date &amp; time</label>
              <input
                type="datetime-local"
                className="input w-56"
                value={runAt}
                onChange={(e) => setRunAt(e.target.value)}
              />
            </div>
          ) : (
            <>
              {type === 'weekly' && (
                <div>
                  <label className="label">Day</label>
                  <select
                    className="input w-36"
                    value={weekday}
                    onChange={(e) => setWeekday(Number(e.target.value))}
                  >
                    {WEEKDAYS.map((day, index) => (
                      <option key={day} value={index}>
                        {day}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="label">Time</label>
                <input
                  type="time"
                  className="input w-32"
                  value={timeOfDay}
                  onChange={(e) => setTimeOfDay(e.target.value)}
                />
              </div>
              <div>
                <label className="label">Start from (optional)</label>
                <input
                  type="datetime-local"
                  className="input w-52"
                  value={startAt}
                  onChange={(e) => setStartAt(e.target.value)}
                  title="Don't run before this date/time"
                />
              </div>
              <div>
                <label className="label">Run until (optional)</label>
                <input
                  type="datetime-local"
                  className="input w-52"
                  value={endAt}
                  onChange={(e) => setEndAt(e.target.value)}
                  title="Auto-disable the schedule after this date/time"
                />
              </div>
            </>
          )}
          <button className="btn-primary" onClick={add}>
            <CalendarPlus size={15} /> Schedule
          </button>
        </div>

        <div className="card p-5">
          {loading ? (
            <Spinner />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                  <th className="px-3 py-2.5">Test case</th>
                  <th className="px-3 py-2.5">When</th>
                  <th className="px-3 py-2.5">Last run</th>
                  <th className="px-3 py-2.5">Next run</th>
                  <th className="px-3 py-2.5">Enabled</th>
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {(schedules ?? []).map((schedule) => (
                  <tr key={schedule.id} className="border-b border-border/60 hover:bg-surface-2">
                    <td className="px-3 py-2.5 font-medium">{schedule.test_case_name}</td>
                    <td className="px-3 py-2.5">
                      <span className="badge bg-violet-500/15 text-violet-400">
                        {schedule.description}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary">
                      {formatTimestamp(schedule.last_run_at)}
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary">
                      {formatTimestamp(schedule.next_run_at)}
                    </td>
                    <td className="px-3 py-2.5">
                      <button
                        role="switch"
                        aria-checked={schedule.enabled}
                        className={`relative h-5 w-9 rounded-full transition-colors ${
                          schedule.enabled ? 'bg-success' : 'bg-border'
                        }`}
                        onClick={async () => {
                          await toggleSchedule(schedule.id);
                          void refetch();
                        }}
                      >
                        <span
                          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                            schedule.enabled ? 'left-[18px]' : 'left-0.5'
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        className="btn-ghost p-1.5 text-error"
                        onClick={async () => {
                          await deleteSchedule(schedule.id);
                          void refetch();
                        }}
                        aria-label="Delete schedule"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
                {(schedules ?? []).length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center text-text-muted">
                      No schedules yet — pick a test case and a date above.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </MainLayout>
  );
}
