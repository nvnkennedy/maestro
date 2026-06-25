import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DashboardStats } from '../../types/domain';
import { STATUS_COLORS } from '../../utils/constants';

const TYPE_PALETTE = ['#2DD4BF', '#22D3EE', '#10B981', '#F59E0B', '#38BDF8', '#A3E635', '#0EA5E9'];

export function ExecutionGraphs({ stats }: { stats: DashboardStats }) {
  const pieData = Object.entries(stats.status_counts).map(([status, count]) => ({
    name: status,
    value: count,
  }));
  const barData = Object.entries(stats.executions_by_type).map(([type, count]) => ({
    type,
    count,
  }));
  const trendData = stats.trend.map((point) => ({
    id: `#${point.execution_id}`,
    duration: point.duration_seconds ?? 0,
  }));

  const tooltipStyle = {
    background: 'rgb(var(--color-surface))',
    border: '1px solid rgb(var(--color-border))',
    borderRadius: 8,
    color: 'rgb(var(--color-text-primary))',
    fontSize: 12,
  };
  const mutedTick = { fill: 'rgb(var(--color-text-muted))', fontSize: 12 };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Pass / Fail split</h3>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
              {pieData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={STATUS_COLORS[entry.name] ?? 'rgb(var(--color-text-muted))'}
                  stroke="none"
                />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="mt-1 flex flex-wrap justify-center gap-3 text-xs text-text-secondary">
          {pieData.map((entry) => (
            <span key={entry.name} className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: STATUS_COLORS[entry.name] ?? 'rgb(var(--color-text-muted))' }}
              />
              {entry.name} ({entry.value})
            </span>
          ))}
        </div>
      </div>

      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Executions by test type</h3>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
            <XAxis dataKey="type" tick={mutedTick} />
            <YAxis allowDecimals={false} tick={mutedTick} />
            <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgb(var(--color-surface-2))' }} />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {barData.map((entry, index) => (
                <Cell key={entry.type} fill={TYPE_PALETTE[index % TYPE_PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-text-secondary">Duration trend (last runs)</h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={trendData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgb(var(--color-border))" />
            <XAxis dataKey="id" tick={mutedTick} />
            <YAxis tick={mutedTick} unit="s" />
            <Tooltip contentStyle={tooltipStyle} />
            <Line
              type="monotone"
              dataKey="duration"
              stroke="rgb(var(--color-primary))"
              strokeWidth={2.5}
              dot={{ r: 3, fill: 'rgb(var(--color-primary))' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
