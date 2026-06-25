import { useNavigate } from 'react-router-dom';
import {
  Activity,
  CalendarClock,
  CheckCircle2,
  Route,
  PlayCircle,
  XCircle,
} from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { StatusCard } from '../components/dashboard/StatusCard';
import { ExecutionGraphs } from '../components/dashboard/ExecutionGraphs';
import { TelemetryDashboard } from '../components/dashboard/TelemetryDashboard';
import { Spinner } from '../components/common/Spinner';
import { useApi } from '../hooks/useApi';
import { useWebSocket } from '../hooks/useWebSocket';
import { getDashboard } from '../services/api';
import { useProject } from '../context/ProjectContext';
import { formatDuration, formatTimestamp } from '../utils/formatting';

export function DashboardPage() {
  const { activeProjectId } = useProject();
  const navigate = useNavigate();
  const { data: stats, loading, refetch } = useApi(
    () => getDashboard(activeProjectId ?? undefined),
    [activeProjectId],
  );

  useWebSocket((event) => {
    if (event.type === 'execution_finished' || event.type === 'execution_started') {
      void refetch();
    }
  });

  return (
    <MainLayout
      title="Dashboard"
      subtitle="Framework status at a glance"
      icon={<Activity size={18} />}
      iconClass="bg-sky-500/15 text-sky-400"
    >
      {loading && !stats ? (
        <Spinner label="Loading dashboard…" />
      ) : stats ? (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatusCard
              label="Total executions"
              value={stats.total_executions}
              icon={<Activity size={20} />}
              accent="#2DD4BF"
            />
            <StatusCard
              label="Passed"
              value={stats.passed}
              icon={<CheckCircle2 size={20} />}
              accent="#10B981"
              hint={`${stats.pass_rate}% pass rate`}
            />
            <StatusCard
              label="Failed"
              value={stats.failed}
              icon={<XCircle size={20} />}
              accent="#EF4444"
            />
            <StatusCard
              label="Test cases"
              value={stats.test_case_count}
              icon={<Route size={20} />}
              accent="#22D3EE"
            />
            <StatusCard
              label="Next scheduled"
              value={
                stats.next_scheduled
                  ? formatTimestamp(stats.next_scheduled.next_run_at).split(',')[0]
                  : '—'
              }
              icon={<CalendarClock size={20} />}
              accent="#F59E0B"
              hint={stats.next_scheduled?.cron_expression}
            />
          </div>

          <ExecutionGraphs stats={stats} />
          <TelemetryDashboard />

          <div className="card flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <h3 className="text-sm font-semibold">Last execution</h3>
              {stats.last_execution ? (
                <p className="mt-1 text-sm text-text-secondary">
                  #{stats.last_execution.id} — {stats.last_execution.status} in{' '}
                  {formatDuration(stats.last_execution.duration_seconds)} (
                  {formatTimestamp(stats.last_execution.started_at)})
                </p>
              ) : (
                <p className="mt-1 text-sm text-text-muted">
                  No executions yet — design a test case and run it.
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => navigate('/execution')}>
                <PlayCircle size={16} /> Run tests
              </button>
              <button className="btn-outline" onClick={() => navigate('/test-cases')}>
                Design test case
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-text-muted">Could not load dashboard.</div>
      )}
    </MainLayout>
  );
}
