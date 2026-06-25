import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Activity,
  Clock,
  Download,
  ExternalLink,
  FileBarChart2,
  GitCompareArrows,
  Mail,
  Paperclip,
  Percent,
  RotateCw,
  Search,
  Trash2,
  Upload,
  XCircle,
} from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { Modal } from '../components/common/Modal';
import { Spinner } from '../components/common/Spinner';
import { StatusBadge } from '../components/common/Badge';
import { ActionChip } from '../components/common/ActionChip';
import { StatusCard } from '../components/dashboard/StatusCard';
import { useToast } from '../components/common/Toast';
import { useApi } from '../hooks/useApi';
import {
  compareReports,
  deleteReports,
  getCycles,
  getReportSummary,
  listReports,
  publishReport,
  startExecution,
  type CycleRollup,
} from '../services/api';
import type { ReportSummary } from '../types/domain';
import { formatDuration, formatTimestamp } from '../utils/formatting';

interface ComparisonResult {
  totals_a: Record<string, number>;
  totals_b: Record<string, number>;
  step_diffs: {
    step_number: number;
    changed: boolean;
    a: { status: string } | null;
    b: { status: string } | null;
  }[];
  regressions: number[];
}

export function ReportsPage() {
  const toast = useToast();
  const { data: reports, loading, refetch } = useApi(listReports, []);
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ReportSummary | null>(null);
  const [cycleData, setCycleData] = useState<CycleRollup | null>(null);

  const filtered = useMemo(() => {
    const text = search.toLowerCase();
    return (reports ?? []).filter((report) => {
      const matchesText =
        !text ||
        `run-${report.id}`.includes(text) ||
        (report.test_case_name ?? '').toLowerCase().includes(text) ||
        (report.suite ?? '').toLowerCase().includes(text) ||
        report.status.includes(text);
      const started = report.started_at?.slice(0, 10) ?? '';
      const matchesFrom = !fromDate || started >= fromDate;
      const matchesTo = !toDate || started <= toDate;
      return matchesText && matchesFrom && matchesTo;
    });
  }, [reports, search, fromDate, toDate]);

  const stats = useMemo(() => {
    const total = filtered.length;
    const passed = filtered.filter((r) => r.status === 'passed').length;
    const failedRuns = filtered.filter((r) => ['failed', 'error'].includes(r.status)).length;
    const durations = filtered
      .map((r) => r.duration_seconds)
      .filter((d): d is number => d != null);
    const avg = durations.length
      ? durations.reduce((sum, d) => sum + d, 0) / durations.length
      : null;
    return {
      total,
      passRate: total ? Math.round((passed / total) * 100) : 0,
      avg,
      failedRuns,
    };
  }, [filtered]);

  const toggle = (id: number) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const openDetail = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      setCycleData(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setCycleData(null);
    setDetail(await getReportSummary(id));
    try {
      setCycleData(await getCycles(id));
    } catch {
      /* no cycles for this run */
    }
  };

  // Deep link from the Execution console: /reports?focus=<runId> opens that run.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const focus = searchParams.get('focus');
    if (!focus || !reports) return;
    const id = Number(focus);
    if (reports.some((r) => r.id === id)) {
      setExpandedId(id);
      setDetail(null);
      void getReportSummary(id).then(setDetail);
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reports, searchParams]);

  const bulkDelete = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} report(s) and their executions?`)) return;
    await deleteReports([...selected]);
    setSelected(new Set());
    setSelectMode(false);
    if (expandedId !== null && selected.has(expandedId)) {
      setExpandedId(null);
      setDetail(null);
    }
    toast('success', 'Reports deleted');
    void refetch();
  };

  const compare = async () => {
    const ids = [...selected];
    if (ids.length !== 2) {
      toast('info', 'Select exactly 2 reports to compare');
      return;
    }
    setComparison(await compareReports(ids[0], ids[1]));
  };

  const rerun = async (testCaseId: number) => {
    const execution = await startExecution(testCaseId, 'serial');
    toast('success', `Re-run started — RUN-${execution.id}`);
    setTimeout(() => void refetch(), 1500);
  };

  const publish = async (id: number, channel: string) => {
    const res = await publishReport(id, channel);
    toast(res.ok ? 'success' : 'info', res.detail || (res.ok ? 'Published' : 'Not published'));
  };

  const exportCsv = () => {
    const header = 'run_id,name,suite,scenario,status,mode,started_at,duration_seconds\n';
    const rows = filtered
      .map((r) =>
        [
          `RUN-${r.id}`,
          `"${(r.test_case_name ?? '').replace(/"/g, '""')}"`,
          `"${r.suite ?? ''}"`,
          `"${r.scenario ?? ''}"`,
          r.status,
          r.execution_mode,
          r.started_at ?? '',
          r.duration_seconds ?? '',
        ].join(','),
      )
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'maestro-reports.csv';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <MainLayout
      title="Reports"
      subtitle="Run history, analytics and artifacts"
      icon={<FileBarChart2 size={18} />}
      iconClass="bg-rose-500/15 text-rose-400"
    >
      <div className="space-y-4">
        {/* Stat cards */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatusCard
            label="Total runs"
            value={stats.total}
            icon={<Activity size={20} />}
            accent="#2DD4BF"
          />
          <StatusCard
            label="Overall pass rate"
            value={`${stats.passRate}%`}
            icon={<Percent size={20} />}
            accent="#10B981"
          />
          <StatusCard
            label="Avg duration"
            value={stats.avg != null ? formatDuration(stats.avg) : '—'}
            icon={<Clock size={20} />}
            accent="#F59E0B"
          />
          <StatusCard
            label="Failed runs"
            value={stats.failedRuns}
            icon={<XCircle size={20} />}
            accent="#EF4444"
          />
        </div>

        <div className="card p-5">
          {/* Toolbar */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search size={15} className="absolute left-3 top-2.5 text-text-muted" />
              <input
                className="input w-64 pl-9"
                placeholder="Search runs…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <input
              type="date"
              className="input w-40"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              aria-label="From date"
            />
            <span className="text-xs text-text-muted">to</span>
            <input
              type="date"
              className="input w-40"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              aria-label="To date"
            />
            <div className="ml-auto flex gap-2">
              <button className="btn-outline" onClick={exportCsv}>
                <Download size={15} className="text-emerald-400" /> Export CSV
              </button>
              {!selectMode ? (
                <button className="btn-outline" onClick={() => setSelectMode(true)}>
                  <Trash2 size={15} className="text-text-muted" /> Select…
                </button>
              ) : (
                <>
                  <button
                    className="btn-outline"
                    onClick={compare}
                    disabled={selected.size !== 2}
                    title="Select exactly two reports"
                  >
                    <GitCompareArrows size={15} className="text-violet-400" /> Compare
                  </button>
                  <button
                    className="btn-danger"
                    onClick={bulkDelete}
                    disabled={selected.size === 0}
                  >
                    <Trash2 size={15} /> Delete ({selected.size})
                  </button>
                  <button
                    className="btn-ghost"
                    onClick={() => {
                      setSelectMode(false);
                      setSelected(new Set());
                    }}
                  >
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>

          {loading ? (
            <Spinner label="Loading reports…" />
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-muted">
                    {selectMode && (
                      <th className="px-3 py-2.5">
                        <input
                          type="checkbox"
                          className="accent-primary"
                          checked={selected.size > 0 && selected.size === filtered.length}
                          onChange={(event) =>
                            setSelected(
                              event.target.checked
                                ? new Set(filtered.map((report) => report.id))
                                : new Set(),
                            )
                          }
                          aria-label="Select all"
                        />
                      </th>
                    )}
                    <th className="px-3 py-2.5">Run ID</th>
                    <th className="px-3 py-2.5">Run name</th>
                    <th className="px-3 py-2.5">Suite</th>
                    <th className="px-3 py-2.5">Status</th>
                    <th className="px-3 py-2.5">Duration</th>
                    <th className="px-3 py-2.5">Timestamp</th>
                    <th className="px-3 py-2.5">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((report) => (
                    <>
                      <tr
                        key={report.id}
                        className="border-b border-border/60 transition-colors hover:bg-surface-2"
                      >
                        {selectMode && (
                          <td className="px-3 py-2.5">
                            <input
                              type="checkbox"
                              className="accent-primary"
                              checked={selected.has(report.id)}
                              onChange={() => toggle(report.id)}
                              aria-label={`Select run ${report.id}`}
                            />
                          </td>
                        )}
                        <td className="px-3 py-2.5">
                          <a
                            className="inline-flex items-center gap-1 font-semibold text-indigo-400 hover:underline"
                            href={`/api/reports/${report.id}/html`}
                            target="_blank"
                            rel="noreferrer"
                            title="Open the full HTML report"
                          >
                            RUN-{report.id} <ExternalLink size={12} />
                          </a>
                          {report.suite_run_id && (
                            <a
                              className="mt-0.5 flex items-center gap-1 text-[11px] text-purple-400 hover:underline"
                              href={`/api/reports/suite/${report.suite_run_id}/html`}
                              target="_blank"
                              rel="noreferrer"
                              title="Open the aggregated suite/scenario report for this run"
                            >
                              Suite report <ExternalLink size={10} />
                            </a>
                          )}
                        </td>
                        <td className="px-3 py-2.5 font-medium">{report.test_case_name}</td>
                        <td className="px-3 py-2.5 text-text-secondary">
                          {report.suite || '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={report.status} />
                        </td>
                        <td className="px-3 py-2.5 text-text-secondary">
                          {formatDuration(report.duration_seconds)}
                        </td>
                        <td className="px-3 py-2.5 text-text-secondary">
                          {formatTimestamp(report.started_at)}
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            className="btn-outline px-2.5 py-1 text-xs"
                            onClick={() => void openDetail(report.id)}
                          >
                            {expandedId === report.id ? 'Hide' : 'View'}
                          </button>
                        </td>
                      </tr>
                      {expandedId === report.id && (
                        <tr key={`${report.id}-detail`}>
                          <td colSpan={selectMode ? 8 : 7} className="bg-surface-2/50 px-5 py-4">
                            {detail == null ? (
                              <Spinner label="Loading run detail…" />
                            ) : (
                              <div className="space-y-4">
                                {cycleData?.rollup.is_endurance && (
                                  <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
                                    <div className="mb-2 flex flex-wrap items-center gap-3 text-sm">
                                      <span className="font-semibold text-amber-400">
                                        Endurance roll-up
                                      </span>
                                      <span className="text-text-secondary">
                                        {cycleData.rollup.total} cycles
                                      </span>
                                      <span className="text-success">
                                        {cycleData.rollup.passed} passed
                                      </span>
                                      <span className="text-error">
                                        {cycleData.rollup.failed} failed
                                      </span>
                                      {cycleData.rollup.first_failure_cycle != null && (
                                        <span className="text-amber-400">
                                          first failure: cycle {cycleData.rollup.first_failure_cycle}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex flex-wrap gap-1">
                                      {cycleData.cycles.map((c) => (
                                        <span
                                          key={c.cycle_index}
                                          className={`grid h-6 min-w-[24px] place-items-center rounded px-1 text-[10px] font-bold text-white ${
                                            c.status === 'passed'
                                              ? 'bg-emerald-600'
                                              : c.status === 'stopped'
                                                ? 'bg-amber-600'
                                                : 'bg-red-600'
                                          }`}
                                          title={c.summary}
                                        >
                                          {c.cycle_index}
                                        </span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b border-border text-left text-[11px] uppercase text-text-muted">
                                      <th className="px-2 py-1.5">#</th>
                                      <th className="px-2 py-1.5">Step name</th>
                                      <th className="px-2 py-1.5">Type</th>
                                      <th className="px-2 py-1.5">Status</th>
                                      <th className="px-2 py-1.5">Duration</th>
                                      <th className="px-2 py-1.5">Output</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {detail.steps.map((step) => {
                                      const stepArtifacts = detail.artifacts.filter(
                                        (artifact) =>
                                          artifact.step_number === step.step_number,
                                      );
                                      return (
                                        <tr key={step.id} className="border-b border-border/40">
                                          <td className="px-2 py-1.5">{step.step_number}</td>
                                          <td className="px-2 py-1.5 font-medium">
                                            {step.label || step.action}
                                          </td>
                                          <td className="px-2 py-1.5">
                                            <ActionChip action={step.action} />
                                          </td>
                                          <td className="px-2 py-1.5">
                                            <StatusBadge status={step.status} />
                                          </td>
                                          <td className="px-2 py-1.5 text-text-secondary">
                                            {formatDuration(step.duration_seconds)}
                                          </td>
                                          <td className="max-w-[260px] px-2 py-1.5 font-mono text-[11px] text-text-muted">
                                            <div className="truncate">
                                              {(step.error_message ||
                                                step.actual_output ||
                                                '—')
                                                .split('\n')[0]
                                                .slice(0, 120)}
                                            </div>
                                            {stepArtifacts.length > 0 && (
                                              <div className="mt-1 flex flex-wrap gap-1">
                                                {stepArtifacts.map((artifact) => (
                                                  <span
                                                    key={artifact.id}
                                                    className="inline-flex items-center gap-1 rounded border border-cyan-500/40 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] text-cyan-400"
                                                    title={artifact.file_path}
                                                  >
                                                    📎 {artifact.file_path.split(/[\\/]/).pop()}
                                                  </span>
                                                ))}
                                              </div>
                                            )}
                                          </td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                                {detail.artifacts.length > 0 && (
                                  <div className="flex flex-wrap items-center gap-2 text-xs">
                                    <Paperclip size={13} className="text-cyan-400" />
                                    {detail.artifacts.map((artifact) => (
                                      <span
                                        key={artifact.id}
                                        className="rounded-md border border-border bg-background px-2 py-1 font-mono text-cyan-400"
                                        title={artifact.file_path}
                                      >
                                        [{artifact.artifact_type}]{' '}
                                        {artifact.file_path.split(/[\\/]/).pop()}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                <div className="flex flex-wrap gap-2">
                                  <a
                                    className="btn-primary"
                                    href={`/api/reports/${report.id}/html`}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    <ExternalLink size={14} /> Open report
                                  </a>
                                  <a
                                    className="btn-outline"
                                    href={`/api/reports/${report.id}/download`}
                                  >
                                    <Download size={14} className="text-emerald-400" /> Download HTML
                                  </a>
                                  <a
                                    className="btn-outline"
                                    href={`/api/reports/${report.id}/allure`}
                                    title="Download real allure-results — unzip and run `allure serve` for the genuine Allure report (with trends)"
                                  >
                                    <Download size={14} className="text-amber-400" /> Allure results
                                  </a>
                                  <a
                                    className="btn-outline"
                                    href={`/api/reports/${report.id}/junit`}
                                    title="Download JUnit XML for CI dashboards / Jira-Xray import"
                                  >
                                    <Download size={14} className="text-cyan-400" /> JUnit XML
                                  </a>
                                  <button
                                    className="btn-outline"
                                    onClick={() => void publish(report.id, 'email')}
                                    title="Email this run's summary + JUnit (needs SMTP_* config)"
                                  >
                                    <Mail size={14} className="text-indigo-400" /> Email
                                  </button>
                                  <button
                                    className="btn-outline"
                                    onClick={() => void publish(report.id, 'xray')}
                                    title="Push results to Jira/Xray (needs XRAY_* config)"
                                  >
                                    <Upload size={14} className="text-violet-400" /> Xray
                                  </button>
                                  <button
                                    className="btn-outline"
                                    onClick={() => void rerun(report.test_case_id)}
                                  >
                                    <RotateCw size={14} className="text-sky-400" /> Re-run
                                  </button>
                                </div>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={selectMode ? 8 : 7} className="py-10 text-center text-text-muted">
                        No runs match the filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Modal
        open={comparison !== null}
        title="Report comparison"
        onClose={() => setComparison(null)}
        wide
      >
        {comparison && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              {[comparison.totals_a, comparison.totals_b].map((totals, index) => (
                <div key={index} className="rounded-lg border border-border p-3">
                  <div className="mb-1 text-xs font-semibold uppercase text-text-muted">
                    Execution {index === 0 ? 'A' : 'B'}
                  </div>
                  <span className="text-success">{totals.passed} passed</span> ·{' '}
                  <span className="text-error">{totals.failed} failed</span> ·{' '}
                  <span className="text-text-muted">{totals.skipped} skipped</span>
                </div>
              ))}
            </div>
            {comparison.regressions.length > 0 && (
              <div className="rounded-lg border border-error/40 bg-error/10 p-3 text-sm text-error">
                Regressions in steps: {comparison.regressions.join(', ')}
              </div>
            )}
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase text-text-muted">
                  <th className="px-2 py-1.5">Step</th>
                  <th className="px-2 py-1.5">A</th>
                  <th className="px-2 py-1.5">B</th>
                  <th className="px-2 py-1.5">Changed</th>
                </tr>
              </thead>
              <tbody>
                {comparison.step_diffs.map((diff) => (
                  <tr key={diff.step_number} className="border-b border-border/60">
                    <td className="px-2 py-1.5">{diff.step_number}</td>
                    <td className="px-2 py-1.5">
                      {diff.a ? <StatusBadge status={diff.a.status} /> : '—'}
                    </td>
                    <td className="px-2 py-1.5">
                      {diff.b ? <StatusBadge status={diff.b.status} /> : '—'}
                    </td>
                    <td className="px-2 py-1.5">{diff.changed ? '⚠️' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>
    </MainLayout>
  );
}
