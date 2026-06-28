import { Cpu, Puzzle } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { Spinner } from '../components/common/Spinner';
import { useToast } from '../components/common/Toast';
import { useApi } from '../hooks/useApi';
import { listPlugins, togglePlugin } from '../services/api';

export function PluginsPage() {
  const toast = useToast();
  const { data: plugins, loading, refetch } = useApi(listPlugins, []);

  return (
    <MainLayout
      title="Plugins"
      subtitle="Adapters powering your test steps — and the tools behind them"
      icon={<Puzzle size={18} />}
      iconClass="bg-cyan-500/15 text-cyan-400"
    >
      {loading ? (
        <Spinner label="Loading plugins…" />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(plugins ?? []).map((plugin) => (
            <div key={plugin.name} className="card flex flex-col p-5">
              <div className="mb-2 flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary/15 text-secondary">
                    <Puzzle size={17} />
                  </span>
                  <div>
                    <div className="font-semibold">{plugin.display_name ?? plugin.name}</div>
                    <div className="font-mono text-xs text-text-muted">
                      {plugin.name} · adapter v{plugin.version ?? '2.1.0'} · {plugin.type ?? 'adapter'}
                    </div>
                  </div>
                </div>
                <button
                  role="switch"
                  aria-checked={plugin.enabled}
                  className={`relative mt-1 h-5 w-9 shrink-0 rounded-full transition-colors ${
                    plugin.enabled ? 'bg-success' : 'bg-border'
                  }`}
                  onClick={async () => {
                    await togglePlugin(plugin.name, !plugin.enabled);
                    toast('success', `${plugin.display_name ?? plugin.name} ${plugin.enabled ? 'disabled' : 'enabled'}`);
                    void refetch();
                  }}
                >
                  <span
                    className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                      plugin.enabled ? 'left-[18px]' : 'left-0.5'
                    }`}
                  />
                </button>
              </div>

              {plugin.powered_by && (
                <div
                  className="mb-3 inline-flex items-center gap-1.5 self-start rounded-md bg-surface-2 px-2 py-1 text-xs text-text-secondary"
                  title="The actual tool version installed right now — it updates whenever you upgrade the tool (pip install -U)."
                >
                  <Cpu size={13} className="text-secondary" />
                  <span>
                    Powered by{' '}
                    <span className="font-medium text-text-primary">{plugin.powered_by.tool}</span>
                    {plugin.tool_version ? (
                      <>
                        {' '}
                        <span className="font-semibold text-secondary">v{plugin.tool_version}</span>
                        <span className="ml-1.5 rounded bg-success/15 px-1 py-px text-[9px] font-bold uppercase tracking-wide text-success">
                          live
                        </span>
                      </>
                    ) : (
                      <span className="ml-1 text-text-muted">(not installed)</span>
                    )}
                  </span>
                </div>
              )}

              <p className="mb-3 flex-1 text-sm text-text-secondary">{plugin.description}</p>

              {plugin.capability_groups ? (
                <div className="space-y-2">
                  {Object.entries(plugin.capability_groups).map(([group, acts]) => (
                    <div key={group}>
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                        {group}
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {acts.map((action) => (
                          <span key={action} className="badge bg-surface-2 font-mono text-text-secondary">
                            {action}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {plugin.actions.map((action) => (
                    <span key={action} className="badge bg-surface-2 font-mono text-text-secondary">
                      {action}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </MainLayout>
  );
}
