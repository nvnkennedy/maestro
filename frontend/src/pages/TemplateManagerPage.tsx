import { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Copy,
  Eye,
  FileCode2,
  FolderOpen,
  Pencil,
  Plus,
  Save,
  Terminal,
  Trash2,
} from 'lucide-react';
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
  getBuiltinTemplates,
  listScripts,
  listUserTemplates,
  saveScript,
  saveUserTemplate,
  setBuiltinHidden,
  type BuiltinTemplate,
  type RegisteredScript,
  type UserTemplate,
} from '../services/api';
import type { TestStep } from '../types/domain';
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

/** Per-group open/closed state for the accordions: small groups open by default,
 *  large ones collapsed, and every group toggles on click. */
function useGroupAccordion(threshold = 10) {
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const isOpen = (group: string, count: number) => overrides[group] ?? count <= threshold;
  const toggle = (group: string, count: number) =>
    setOverrides((o) => ({ ...o, [group]: !isOpen(group, count) }));
  return { isOpen, toggle };
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
  const { isOpen, toggle } = useGroupAccordion();
  // Design templates with the same friendly editor used for real steps — no JSON.
  const [designing, setDesigning] = useState<
    { step: TestStep; id?: string; group: string } | null
  >(null);

  // All groups in use — powers the "move to group" dropdown + the editor datalist.
  const groups = useMemo(
    () => Array.from(new Set((templates ?? []).map((t) => t.group))).sort(),
    [templates],
  );
  // Templates bucketed into sections by group.
  const sections = useMemo(() => {
    const map = new Map<string, UserTemplate[]>();
    for (const t of templates ?? []) {
      if (!map.has(t.group)) map.set(t.group, []);
      map.get(t.group)!.push(t);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [templates]);

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

  const moveToGroup = async (tpl: UserTemplate, group: string) => {
    const next = group.trim();
    if (!next || next === tpl.group) return;
    await saveUserTemplate({ ...tpl, group: next });
    toast('success', `Moved to “${next}”`);
    void refetch();
  };
  const duplicate = async (tpl: UserTemplate) => {
    await saveUserTemplate({
      group: tpl.group,
      label: `${tpl.label} (copy)`,
      action: tpl.action,
      parameters: tpl.parameters,
      timeout_seconds: tpl.timeout_seconds,
    });
    toast('success', 'Duplicated');
    void refetch();
  };
  const remove = async (id?: string) => {
    if (!id || !window.confirm('Delete this template?')) return;
    await deleteUserTemplate(id);
    toast('success', 'Deleted');
    void refetch();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-text-secondary">
          Build your own palette items with the visual editor (no JSON) and organise them
          into groups. Use <b>Move to…</b> to file a template under any group.
        </p>
        <button
          className="btn-primary shrink-0 text-xs"
          onClick={() => setDesigning({ step: blankStep(), group: groups[0] ?? 'My steps' })}
        >
          <Plus size={14} /> Design a template
        </button>
      </div>
      {loading ? (
        <Spinner />
      ) : sections.length === 0 ? (
        <div className="card p-8 text-center text-sm text-text-muted">
          No custom templates yet — click <b>Design a template</b>, or clone a built-in from
          the next tab.
        </div>
      ) : (
        <div className="space-y-3">
          {sections.map(([group, items]) => (
            <div key={group} className="card p-4">
              <button
                className="flex w-full items-center gap-1.5 text-left text-xs font-bold uppercase tracking-wide text-primary"
                onClick={() => toggle(group, items.length)}
              >
                {isOpen(group, items.length) ? (
                  <ChevronDown size={14} />
                ) : (
                  <ChevronRight size={14} />
                )}
                <FolderOpen size={13} /> {group}
                <span className="text-text-muted">({items.length})</span>
              </button>
              {isOpen(group, items.length) && (
              <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {items.map((tpl) => (
                  <div key={tpl.id} className="rounded-lg border border-border bg-background p-3">
                    <div className="mb-1 flex items-center gap-1.5">
                      <ActionChip action={tpl.action} />
                    </div>
                    <div className="font-medium">{tpl.label}</div>
                    <div className="mb-2 mt-0.5 line-clamp-2 text-[11px] text-text-muted">
                      {summarizeParams(tpl.parameters)}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <select
                        className="input h-7 flex-1 py-0 text-xs"
                        value=""
                        title="Move to another group"
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === '__new__') {
                            const name = window.prompt('New group name', tpl.group);
                            if (name) void moveToGroup(tpl, name);
                          } else if (v) {
                            void moveToGroup(tpl, v);
                          }
                        }}
                      >
                        <option value="">Move to…</option>
                        {groups
                          .filter((g) => g !== tpl.group)
                          .map((g) => (
                            <option key={g} value={g}>
                              {g}
                            </option>
                          ))}
                        <option value="__new__">＋ New group…</option>
                      </select>
                      <button
                        className="btn-ghost p-1 text-indigo-400"
                        title="Duplicate"
                        onClick={() => void duplicate(tpl)}
                      >
                        <Copy size={13} />
                      </button>
                      <button
                        className="btn-ghost p-1 text-sky-400"
                        title="Edit"
                        onClick={() =>
                          setDesigning({ step: stepFromTemplate(tpl), id: tpl.id, group: tpl.group })
                        }
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        className="btn-ghost p-1 text-error"
                        title="Delete"
                        onClick={() => void remove(tpl.id)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              )}
            </div>
          ))}
        </div>
      )}

      <StepEditModal
        step={designing?.step ?? null}
        asTemplate
        templateId={designing?.id}
        initialGroup={designing?.group}
        groupOptions={groups}
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
  const { data: groups, loading, refetch } = useApi(getBuiltinTemplates, []);
  const { isOpen, toggle } = useGroupAccordion();
  const [showHidden, setShowHidden] = useState(false);
  // Edit a built-in → opens the visual editor; saving makes your own editable copy
  // (the shipped file is never touched).
  const [designing, setDesigning] = useState<{ step: TestStep; group: string } | null>(null);

  const stepFromBuiltin = (tpl: BuiltinTemplate): TestStep => ({
    step_number: 1,
    action: tpl.action,
    parameters: { ...tpl.parameters, _label: tpl.label },
    timeout_seconds: tpl.timeout_seconds ?? 30,
    retry_count: 0,
  });

  const clone = async (tpl: BuiltinTemplate) => {
    try {
      await saveUserTemplate({
        group: 'My steps',
        label: `${tpl.label} (copy)`,
        action: tpl.action,
        parameters: tpl.parameters ?? {},
        timeout_seconds: tpl.timeout_seconds ?? 30,
      });
      toast('success', 'Cloned to “My steps” — find it in Custom templates');
    } catch (err) {
      toast('error', `Clone failed: ${err instanceof Error ? err.message : err}`);
    }
  };
  const setHidden = async (tpl: BuiltinTemplate, hidden: boolean) => {
    if (hidden && !window.confirm(`Delete “${tpl.label}” from the palette? You can restore it later.`))
      return;
    await setBuiltinHidden(tpl.key, hidden);
    toast('success', hidden ? 'Deleted from the palette' : 'Restored to the palette');
    void refetch();
  };

  const allGroups = Object.keys(groups ?? {});
  const hiddenCount = Object.values(groups ?? {})
    .flat()
    .filter((t) => t.hidden).length;

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-text-secondary">
          These ship with Maestro. <b>Edit</b> or <b>Clone</b> one to get your own editable
          copy, or <b>Delete</b> it to remove it from the palette. The shipped files are never
          changed, so deleted items can be restored any time via <b>Show deleted</b>.
        </p>
        <label className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-xs text-text-secondary">
          <input
            type="checkbox"
            className="accent-primary"
            checked={showHidden}
            onChange={(e) => setShowHidden(e.target.checked)}
          />
          Show deleted{hiddenCount > 0 ? ` (${hiddenCount})` : ''}
        </label>
      </div>
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-3">
          {Object.entries(groups ?? {}).map(([group, items]) => {
            const visible = items.filter((t) => showHidden || !t.hidden);
            if (!visible.length) return null;
            const activeCount = items.filter((t) => !t.hidden).length;
            const open = isOpen(group, visible.length);
            return (
              <div key={group} className="card p-4">
                <button
                  className="flex w-full items-center gap-1.5 text-left text-xs font-semibold uppercase tracking-wide text-text-muted"
                  onClick={() => toggle(group, visible.length)}
                >
                  {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  {group} ({activeCount})
                </button>
                {open && (
                  <div className="mt-2 space-y-1">
                    {visible.map((tpl) => (
                      <div
                        key={tpl.key}
                        className={`flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2 ${
                          tpl.hidden ? 'opacity-50' : ''
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium">{tpl.label}</span>
                            <ActionChip action={tpl.action} />
                            {tpl.hidden && (
                              <span className="shrink-0 rounded bg-surface-2 px-1 text-[9px] font-bold uppercase text-text-muted">
                                deleted
                              </span>
                            )}
                          </div>
                          <div className="truncate text-[11px] text-text-muted">
                            {summarizeParams(tpl.parameters ?? {})}
                          </div>
                        </div>
                        <button
                          className="btn-ghost shrink-0 px-2 py-0.5 text-xs text-sky-400"
                          title="Edit — saves as your own copy in Custom templates"
                          onClick={() => setDesigning({ step: stepFromBuiltin(tpl), group })}
                        >
                          <Pencil size={12} /> Edit
                        </button>
                        <button
                          className="btn-ghost shrink-0 px-2 py-0.5 text-xs text-cyan-400"
                          onClick={() => void clone(tpl)}
                        >
                          <Copy size={12} /> Clone
                        </button>
                        {tpl.hidden ? (
                          <button
                            className="btn-ghost shrink-0 px-2 py-0.5 text-xs text-emerald-400"
                            onClick={() => void setHidden(tpl, false)}
                          >
                            <Eye size={12} /> Restore
                          </button>
                        ) : (
                          <button
                            className="btn-ghost shrink-0 px-2 py-0.5 text-xs text-error"
                            title="Remove from palette — restorable via Show deleted"
                            onClick={() => void setHidden(tpl, true)}
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <StepEditModal
        step={designing?.step ?? null}
        asTemplate
        initialGroup={designing?.group}
        groupOptions={allGroups}
        onSave={() => {}}
        onClose={() => setDesigning(null)}
        onTemplateSaved={() => toast('success', 'Saved as your editable copy in Custom templates')}
      />
    </div>
  );
}

export function TemplateManagerPage() {
  const [tab, setTab] = useState<'scripts' | 'templates' | 'builtin'>('templates');
  return (
    <MainLayout
      title="Template Manager"
      subtitle="Register your scripts and manage custom palette templates"
      icon={<FileCode2 size={18} />}
      iconClass="bg-pink-500/15 text-pink-400"
    >
      <div className="space-y-4">
        <div className="flex gap-1.5">
          {(['templates', 'builtin', 'scripts'] as const).map((t) => (
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
