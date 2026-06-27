import { useState } from 'react';
import { Copy, FileCode2, Pencil, Plus, Save, Terminal, Trash2 } from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { ActionChip } from '../components/common/ActionChip';
import { Modal } from '../components/common/Modal';
import { Spinner } from '../components/common/Spinner';
import { useToast } from '../components/common/Toast';
import { StepEditModal } from '../components/test-cases/StepEditModal';
import { useApi } from '../hooks/useApi';
import {
  deleteScript,
  deleteUserTemplate,
  getTemplates,
  listScripts,
  listUserTemplates,
  saveScript,
  saveUserTemplate,
  type RegisteredScript,
  type UserTemplate,
} from '../services/api';
import type { StepTemplate, TestStep } from '../types/domain';
import { prettyParamName } from '../utils/actions';

/** A short plain-English preview of a template's settings (no JSON dump). */
function summarizeParams(params: Record<string, unknown>): string {
  const entries = Object.entries(params || {}).filter(
    ([k]) => !k.startsWith('_') && k !== 'device_config_id',
  );
  if (!entries.length) return 'No extra settings';
  const parts = entries
    .slice(0, 4)
    .map(([k, v]) => `${prettyParamName(k)}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`);
  return parts.join(' · ') + (entries.length > 4 ? ' …' : '');
}

// ---- Registered scripts (power/etfw/dlt subcommand scripts) -------------------

function ScriptsPanel() {
  const toast = useToast();
  const { data: scripts, loading, refetch } = useApi(listScripts, []);
  const [editing, setEditing] = useState<RegisteredScript | 'new' | null>(null);
  const [form, setForm] = useState<RegisteredScript>({
    id: '',
    name: '',
    path: '',
    interpreter: '',
    description: '',
    commands: [],
  });
  const [cmdsText, setCmdsText] = useState('');

  const open = (script: RegisteredScript | 'new') => {
    if (script === 'new') {
      setForm({ id: '', name: '', path: '', interpreter: '', description: '', commands: [] });
      setCmdsText('');
    } else {
      setForm(script);
      setCmdsText(script.commands.map((c) => c.args.join(' ')).join('\n'));
    }
    setEditing(script);
  };

  const save = async () => {
    // Each line is one command; its words become the script's argument list.
    const commands = cmdsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const args = line.split(/\s+/);
        return { label: line, args };
      });
    try {
      await saveScript({ ...form, commands });
      toast('success', 'Script saved');
      setEditing(null);
      void refetch();
    } catch (err) {
      toast('error', `Save failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm('Delete this registered script?')) return;
    await deleteScript(id);
    toast('success', 'Deleted');
    void refetch();
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Register a bench script once (e.g. <code>power_control.py</code>) with its
        subcommands. Each subcommand becomes a ready-to-drop palette item under{' '}
        <b>Scripts</b> that runs <code>&lt;interpreter&gt; &lt;path&gt; &lt;subcommand&gt;</code>.
      </p>
      {loading ? (
        <Spinner />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(scripts ?? []).map((script) => (
            <div key={script.id} className="card flex flex-col p-4">
              <div className="mb-1 flex items-center gap-2">
                <Terminal size={15} className="text-pink-400" />
                <span className="font-semibold">{script.name}</span>
              </div>
              <div className="mb-2 truncate font-mono text-[11px] text-text-muted" title={script.path}>
                {script.path}
              </div>
              <div className="mb-3 flex flex-wrap gap-1">
                {script.commands.map((c, i) => (
                  <span
                    key={i}
                    className="rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono text-text-secondary"
                  >
                    {c.label || c.args.join(' ')}
                  </span>
                ))}
                {script.commands.length === 0 && (
                  <span className="text-[11px] text-text-muted">no commands</span>
                )}
              </div>
              <div className="mt-auto flex gap-2">
                <button className="btn-outline flex-1 justify-center text-xs" onClick={() => open(script)}>
                  Edit
                </button>
                <button className="btn-danger text-xs" onClick={() => void remove(script.id)}>
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
          <button
            className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-text-muted transition-colors hover:border-primary/50 hover:text-primary"
            onClick={() => open('new')}
          >
            <Plus size={24} />
            <span className="text-sm font-medium">Register script</span>
          </button>
        </div>
      )}

      <Modal
        open={editing !== null}
        title={editing === 'new' ? 'Register a script' : 'Edit script'}
        onClose={() => setEditing(null)}
      >
        <div className="space-y-3">
          <div>
            <label className="label">Name</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Power control"
            />
          </div>
          <div>
            <label className="label">Script path</label>
            <input
              className="input"
              value={form.path}
              onChange={(e) => setForm({ ...form, path: e.target.value })}
              placeholder="C:/bench/power_control.py"
            />
          </div>
          <div>
            <label className="label">Interpreter (optional)</label>
            <input
              className="input"
              value={form.interpreter ?? ''}
              onChange={(e) => setForm({ ...form, interpreter: e.target.value })}
              placeholder="python (leave empty to auto-detect by extension)"
            />
          </div>
          <div>
            <label className="label">Commands — one per line (the words become the script's args)</label>
            <textarea
              className="input min-h-[120px] font-mono text-xs"
              value={cmdsText}
              onChange={(e) => setCmdsText(e.target.value)}
              placeholder={'normal_power_cycle\nedl_power_cycle\nset_state normal_operation\n--mode edl --retries 3'}
            />
            <p className="mt-1 text-[11px] text-text-muted">
              Each line runs <code>&lt;interpreter&gt; &lt;path&gt; &lt;the words on that line&gt;</code>.
              e.g. <code>set_state normal_operation</code> → <code>python power_control.py set_state normal_operation</code>.
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <button className="btn-outline" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={save} disabled={!form.name || !form.path}>
              <Save size={14} /> Save
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// ---- User templates -----------------------------------------------------------

function TemplatesPanel() {
  const toast = useToast();
  const { data: templates, loading, refetch } = useApi(listUserTemplates, []);
  // Design templates with the same friendly editor used for real steps — no JSON.
  const [designing, setDesigning] = useState<
    { step: TestStep; id?: string; group: string } | null
  >(null);

  const blankStep = (): TestStep => ({
    step_number: 1,
    action: 'system.echo',
    parameters: { _label: '' },
    timeout_seconds: 30,
    retry_count: 0,
  });
  const stepFromTemplate = (tpl: UserTemplate): TestStep => ({
    step_number: 1,
    action: tpl.action,
    parameters: { ...(tpl.parameters as Record<string, unknown>), _label: tpl.label },
    timeout_seconds: tpl.timeout_seconds,
    retry_count: 0,
  });

  const remove = async (id?: string) => {
    if (!id || !window.confirm('Delete this template?')) return;
    await deleteUserTemplate(id);
    toast('success', 'Deleted');
    void refetch();
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Build your own palette items with the same visual editor as a test step — pick an
        action and fill in plain-English settings (no JSON). They appear in the designer
        palette under the group you choose.
      </p>
      {loading ? (
        <Spinner />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(templates ?? []).map((tpl) => (
            <div key={tpl.id} className="card flex flex-col p-4">
              <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary">
                  {tpl.group}
                </span>
                <ActionChip action={tpl.action} />
              </div>
              <div className="font-semibold">{tpl.label}</div>
              <div className="mb-3 mt-0.5 line-clamp-2 text-xs text-text-muted">
                {summarizeParams(tpl.parameters)}
              </div>
              <div className="mt-auto flex gap-2">
                <button
                  className="btn-outline flex-1 justify-center text-xs"
                  onClick={() =>
                    setDesigning({ step: stepFromTemplate(tpl), id: tpl.id, group: tpl.group })
                  }
                >
                  <Pencil size={13} /> Edit
                </button>
                <button
                  className="btn-danger text-xs"
                  onClick={() => void remove(tpl.id)}
                  aria-label="Delete template"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
          <button
            className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-text-muted transition-colors hover:border-primary/50 hover:text-primary"
            onClick={() => setDesigning({ step: blankStep(), group: 'My steps' })}
          >
            <Plus size={24} />
            <span className="text-sm font-medium">Design a template</span>
          </button>
        </div>
      )}

      <StepEditModal
        step={designing?.step ?? null}
        asTemplate
        templateId={designing?.id}
        initialGroup={designing?.group}
        onSave={() => {}}
        onClose={() => setDesigning(null)}
        onTemplateSaved={() => {
          toast('success', 'Template saved');
          void refetch();
        }}
      />
    </div>
  );
}

// ---- Built-in templates (clone one to edit it) -------------------------------

function BuiltinPanel() {
  const toast = useToast();
  const { data: groups, loading } = useApi(getTemplates, []);

  const clone = async (group: string, tpl: StepTemplate) => {
    try {
      await saveUserTemplate({
        group,
        label: `${tpl.label} (copy)`,
        action: tpl.action,
        parameters: (tpl.parameters as Record<string, unknown>) ?? {},
        timeout_seconds: tpl.timeout_seconds ?? 30,
      });
      toast('success', `Cloned to “Custom templates” → edit it there`);
    } catch (err) {
      toast('error', `Clone failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        These ship with Maestro and are read-only. <b>Clone</b> any one to make an
        editable copy under <b>Custom templates</b> (built-ins are never overwritten,
        so they survive upgrades).
      </p>
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-3">
          {Object.entries(groups ?? {}).map(([group, items]) => (
            <div key={group} className="card p-4">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                {group} ({items.length})
              </div>
              <div className="space-y-1">
                {items.map((tpl, i) => (
                  <div
                    key={`${group}-${i}`}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium">{tpl.label}</span>
                        <ActionChip action={tpl.action} />
                      </div>
                      <div className="truncate text-[11px] text-text-muted">
                        {summarizeParams((tpl.parameters as Record<string, unknown>) ?? {})}
                      </div>
                    </div>
                    <button
                      className="btn-ghost shrink-0 px-2 py-0.5 text-xs text-cyan-400"
                      onClick={() => void clone(group, tpl)}
                    >
                      <Copy size={12} /> Clone
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function TemplateManagerPage() {
  const [tab, setTab] = useState<'scripts' | 'templates' | 'builtin'>('scripts');
  return (
    <MainLayout
      title="Template Manager"
      subtitle="Register your scripts and manage custom palette templates"
      icon={<FileCode2 size={18} />}
      iconClass="bg-pink-500/15 text-pink-400"
    >
      <div className="space-y-4">
        <div className="flex gap-1.5">
          {(['scripts', 'templates', 'builtin'] as const).map((t) => (
            <button
              key={t}
              className={`rounded-lg px-4 py-2 text-sm font-semibold uppercase tracking-wide transition-all ${
                tab === t
                  ? 'bg-primary/15 text-primary ring-1 ring-primary/40'
                  : 'bg-surface text-text-secondary hover:bg-surface-2'
              }`}
              onClick={() => setTab(t)}
            >
              {t === 'scripts'
                ? 'Registered scripts'
                : t === 'templates'
                  ? 'Custom templates'
                  : 'Built-in templates'}
            </button>
          ))}
        </div>
        {tab === 'scripts' ? (
          <ScriptsPanel />
        ) : tab === 'templates' ? (
          <TemplatesPanel />
        ) : (
          <BuiltinPanel />
        )}
      </div>
    </MainLayout>
  );
}
