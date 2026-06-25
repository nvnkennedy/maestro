import { useApi } from '../../hooks/useApi';
import { adapterHealth } from '../../services/api';
import { Activity, CheckCircle2, XCircle } from 'lucide-react';

export function TelemetryDashboard() {
  const { data, loading } = useApi(adapterHealth, []);

  return (
    <div className="card p-5">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-text-secondary">
        <Activity size={15} /> Adapter health
      </h3>
      {loading && <div className="text-sm text-text-muted">Checking adapters…</div>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {data &&
          Object.entries(data).map(([name, result]) => (
            <div
              key={name}
              className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2"
              title={result.success ? result.output : result.error}
            >
              {result.success ? (
                <CheckCircle2 size={15} className="shrink-0 text-success" />
              ) : (
                <XCircle size={15} className="shrink-0 text-error" />
              )}
              <span className="truncate text-sm font-medium">{name}</span>
            </div>
          ))}
      </div>
    </div>
  );
}
