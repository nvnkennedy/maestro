import { BookmarkPlus, Paperclip, Plus, Trash2, Upload } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useProject } from '../../context/ProjectContext';
import { useApi } from '../../hooks/useApi';
import {
  listConfigs,
  saveUserTemplate,
  uploadStepAttachment,
  type PlannedAttachment,
} from '../../services/api';
import type { TestStep } from '../../types/domain';
import {
  ACTION_OPTIONS,
  friendlyAction,
  PARAM_HINTS,
  paramsForAction,
  prettyParamName,
} from '../../utils/actions';
import { Modal } from '../common/Modal';

interface StepEditModalProps {
  step: TestStep | null;
  onSave: (step: TestStep) => void;
  onClose: () => void;
  /** The test's chosen Run location (e.g. "Local (this machine)" or an RDP host),
   *  so the step editor can show that ssh/adb steps default to it. */
  runTargetLabel?: string;
  /** Template-design mode: the same friendly editor, but the result is saved as a
   *  reusable palette template instead of applied to a step in a test case. */
  asTemplate?: boolean;
  templateId?: string;
  initialGroup?: string;
  onTemplateSaved?: () => void;
}

type ParamValue = string | number | boolean;
type Expectation = { text: string; mode: string };
const MATCH_MODES = [
  { value: 'contains', label: 'contains' },
  { value: 'wildcard', label: 'matches wildcard' },
  { value: 'regex', label: 'matches regex' },
  { value: 'exact', label: 'equals exactly' },
];

const FLOW_OPTIONS = [
  { value: 'serial', label: 'Sequential — runs after the previous step' },
  { value: 'parallel-A', label: 'Parallel — runs together with adjacent parallel steps' },
  { value: 'pause', label: 'Pause before — waits for you to press Next' },
  { value: 'always', label: 'Always run at the end (collector — runs even after a failure)' },
];

// Parameters that hold a file path — get an Upload button so you pick the file
// up front and the step uses it automatically (e.g. apk_path, local_path, path).
const FILE_PARAM_KEYS = new Set([
  'path', 'script_path', 'local_path', 'apk_path', 'key_file', 'file_path',
  'match_file', 'attach_file', 'output_path', 'remote_path',
]);
const isFileParam = (key: string) =>
  FILE_PARAM_KEYS.has(key) || key.endsWith('_path') || key.endsWith('_file');

// Actions where one setting is essential. We always surface it (even when empty)
// and flag it as required, so a step can't silently run without it — e.g.
// system.run_file needs the script/.exe path, run_command needs the command.
const REQUIRED_PARAM: Record<string, string> = {
  'system.run_file': 'path',
  'system.run_command': 'command',
  'system.run_registered': 'script_id',
  'system.run_script': 'script',
};

export function StepEditModal({
  step,
  onSave,
  onClose,
  runTargetLabel,
  asTemplate = false,
  templateId,
  initialGroup,
  onTemplateSaved,
}: StepEditModalProps) {
  const { activeProjectId } = useProject();
  const { data: configs } = useApi(
    () => (activeProjectId ? listConfigs(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );

  const [label, setLabel] = useState('');
  const [action, setAction] = useState('');
  const [flow, setFlow] = useState('serial');
  const [deviceId, setDeviceId] = useState<string>('');
  const [fields, setFields] = useState<[string, ParamValue][]>([]);
  const [extraParams, setExtraParams] = useState<Record<string, unknown>>({});
  const [timeout, setTimeoutSeconds] = useState(30);
  const [retries, setRetries] = useState(0);
  const [newKey, setNewKey] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedText, setAdvancedText] = useState('{}');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<PlannedAttachment[]>([]);
  const [expects, setExpects] = useState<Expectation[]>([]);
  const [newKeyMode, setNewKeyMode] = useState<'pick' | 'custom'>('pick');
  const [canvasMeta, setCanvasMeta] = useState<Record<string, unknown>>({});
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // "Save as template" — turn the configured step into a reusable palette item.
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateGroup, setTemplateGroup] = useState('My steps');
  const [templateSaved, setTemplateSaved] = useState(false);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const fieldFileRef = useRef<HTMLInputElement>(null);
  const fieldTargetRef = useRef<number | null>(null);

  useEffect(() => {
    if (!step) return;
    const params = { ...(step.parameters as Record<string, unknown>) };
    setLabel(String(params._label ?? ''));
    setFlow(
      params._always_run
        ? 'always'
        : params._pause_before
          ? 'pause'
          : params._parallel_group
            ? `parallel-${params._parallel_group}`
            : 'serial',
    );
    setDeviceId(params.device_config_id != null ? String(params.device_config_id) : '');
    setAttachments(Array.isArray(params._attachments) ? (params._attachments as PlannedAttachment[]) : []);
    // Expectations: support a list (expect_rules) or single expect_contains.
    const loadedExpects: Expectation[] = [];
    if (Array.isArray(params.expect_rules)) {
      for (const rule of params.expect_rules as { text?: unknown; mode?: unknown }[]) {
        if (rule && rule.text) {
          loadedExpects.push({ text: String(rule.text), mode: String(rule.mode ?? 'contains') });
        }
      }
    }
    const mode = String(params.match_mode ?? 'contains');
    const ec = params.expect_contains;
    if (Array.isArray(ec)) ec.forEach((t) => loadedExpects.push({ text: String(t), mode }));
    else if (ec != null && ec !== '') loadedExpects.push({ text: String(ec), mode });
    setExpects(loadedExpects);
    setNewKeyMode('pick');
    delete params.expect_contains;
    delete params.match_mode;
    delete params.expect_rules;
    delete params._label;
    delete params._always_run;
    delete params._pause_before;
    delete params._parallel_group;
    delete params.device_config_id;
    delete params._attachments;
    // Canvas-only metadata: keep out of the form, restore verbatim on save.
    const meta: Record<string, unknown> = {};
    for (const key of ['_pos', '_uid', '_branch', '_if']) {
      if (key in params) {
        meta[key] = params[key];
        delete params[key];
      }
    }
    setCanvasMeta(meta);

    // Simple values become form fields; nested objects stay in "advanced".
    const simple: [string, ParamValue][] = [];
    const complex: Record<string, unknown> = {};
    Object.entries(params).forEach(([key, value]) => {
      if (
        typeof value === 'string' ||
        typeof value === 'number' ||
        typeof value === 'boolean'
      ) {
        simple.push([key, value]);
      } else {
        complex[key] = value;
      }
    });
    // Always surface a required setting (e.g. run_file's path) so it's visible
    // and can be filled in — even on steps created without it.
    const reqKey = REQUIRED_PARAM[step.action];
    if (reqKey && !simple.some(([k]) => k === reqKey)) simple.push([reqKey, '']);
    setFields(simple);
    setExtraParams(complex);
    setAdvancedText(JSON.stringify(complex, null, 2));
    setShowAdvanced(false);
    setAction(step.action);
    setTimeoutSeconds(step.timeout_seconds);
    setRetries(step.retry_count);
    setNewKey('');
    setJsonError(null);
    setUploadError(null);
    setShowTemplateForm(false);
    setTemplateSaved(false);
    setTemplateError(null);
    if (asTemplate) {
      setTemplateGroup(initialGroup ?? 'My steps');
      setTemplateName(String(step.parameters?._label ?? '') || friendlyAction(step.action));
    }
  }, [step, asTemplate, initialGroup]);

  // Configured targets matching this action's adapter (ssh.*, adb.*, ...).
  const adapter = action.split('.')[0] ?? '';
  const targets = useMemo(
    () => (configs ?? []).filter((config) => config.config_type === adapter),
    [configs, adapter],
  );

  // The essential setting for this action (if any) and whether it's still empty.
  const requiredKey = REQUIRED_PARAM[action];
  const requiredMissing =
    !!requiredKey && !fields.some(([k, v]) => k === requiredKey && String(v).trim() !== '');

  // Switching action keeps its required setting visible so the user fills it in.
  const handleActionChange = (next: string) => {
    setAction(next);
    const reqKey = REQUIRED_PARAM[next];
    if (reqKey) {
      setFields((current) =>
        current.some(([k]) => k === reqKey) ? current : [...current, [reqKey, '']],
      );
    }
  };

  // Settings offered in the "add setting" dropdown for this action — minus ones
  // already shown and the keys handled by dedicated UI above.
  const HANDLED_KEYS = new Set([
    'expect_contains', 'expect_rules', 'match_mode', 'device_config_id', '_label',
  ]);
  const availableParams = useMemo(() => {
    const used = new Set(fields.map(([k]) => k));
    return paramsForAction(action).filter((k) => !used.has(k) && !HANDLED_KEYS.has(k));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, fields]);

  const setField = (index: number, value: ParamValue) =>
    setFields((current) =>
      current.map((entry, i) => (i === index ? [entry[0], value] : entry)),
    );

  // Upload a file and set it as a file-path parameter's value, so the step
  // uses that exact file when it runs (no typing paths).
  const pickFileForField = (index: number) => {
    fieldTargetRef.current = index;
    fieldFileRef.current?.click();
  };
  const handleFieldFile = async (files: FileList | null) => {
    const index = fieldTargetRef.current;
    if (!files || files.length === 0 || index == null) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await uploadStepAttachment(files[0]);
      setField(index, uploaded.path);
    } catch (err) {
      // Don't fail silently — a swallowed error here left the path empty, so the
      // step looked configured but ran as "missing script".
      setUploadError(
        err instanceof Error ? err.message : 'Could not upload that file — check it and retry.',
      );
    } finally {
      setUploading(false);
      fieldTargetRef.current = null;
      if (fieldFileRef.current) fieldFileRef.current.value = '';
    }
  };

  // Build the step's parameters from the form. Canvas-only metadata (position,
  // id, branch wiring) is kept for a normal save but dropped when saving a
  // reusable template. Returns null if the advanced JSON is invalid.
  const collectParameters = (includeCanvasMeta: boolean): Record<string, unknown> | null => {
    let advanced: Record<string, unknown> = extraParams;
    if (showAdvanced) {
      try {
        advanced = JSON.parse(advancedText || '{}') as Record<string, unknown>;
      } catch {
        setJsonError('Advanced parameters must be valid JSON');
        return null;
      }
    }
    const parameters: Record<string, unknown> = {
      ...advanced,
      ...(includeCanvasMeta ? canvasMeta : {}),
    };
    fields.forEach(([key, value]) => {
      if (value !== '') parameters[key] = value;
    });
    if (label.trim()) parameters._label = label.trim();
    if (deviceId) parameters.device_config_id = Number(deviceId);
    if (attachments.length) parameters._attachments = attachments;
    const validExpects = expects
      .map((e) => ({ text: e.text.trim(), mode: e.mode }))
      .filter((e) => e.text);
    if (validExpects.length === 1) {
      parameters.expect_contains = validExpects[0].text;
      if (validExpects[0].mode !== 'contains') parameters.match_mode = validExpects[0].mode;
    } else if (validExpects.length > 1) {
      parameters.expect_rules = validExpects;
    }
    if (flow === 'pause') parameters._pause_before = true;
    else if (flow === 'always') parameters._always_run = true;
    else if (flow.startsWith('parallel-'))
      parameters._parallel_group = flow.replace('parallel-', '');
    return parameters;
  };

  const handleSave = () => {
    if (!step) return;
    const parameters = collectParameters(true);
    if (parameters === null) return;
    onSave({ ...step, action, parameters, timeout_seconds: timeout, retry_count: retries });
    onClose();
  };

  // Save the configured step to the user's palette as a reusable template. A
  // template carries no specific device binding or canvas position/branch wiring.
  const saveAsTemplate = async () => {
    const parameters = collectParameters(false);
    if (parameters === null) return;
    delete parameters.device_config_id;
    setTemplateError(null);
    try {
      await saveUserTemplate({
        ...(templateId ? { id: templateId } : {}),
        group: templateGroup.trim() || 'My steps',
        label: templateName.trim() || friendlyAction(action),
        action,
        parameters,
        timeout_seconds: timeout,
      });
      setTemplateSaved(true);
      setShowTemplateForm(false);
      // In the Templates page, saving is the whole point — notify + close.
      if (asTemplate) {
        onTemplateSaved?.();
        onClose();
      }
    } catch (err) {
      setTemplateError(
        err instanceof Error ? err.message : 'Could not save the template — try again.',
      );
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await Promise.all(
        Array.from(files).map((file) => uploadStepAttachment(file)),
      );
      setAttachments((current) => [...current, ...uploaded]);
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : 'Could not upload that file — check it and retry.',
      );
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const groups = [...new Set(ACTION_OPTIONS.map((option) => option.group))];

  return (
    <Modal
      open={step !== null}
      title={asTemplate ? (templateId ? 'Edit template' : 'Design a template') : 'Edit step'}
      onClose={onClose}
      wide
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="label">Step name</label>
            <input
              className="input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. SSH uname -a on QNX"
            />
          </div>
          <div>
            <label className="label">What to do</label>
            <select className="input" value={action} onChange={(e) => handleActionChange(e.target.value)}>
              {!ACTION_OPTIONS.some((option) => option.value === action) && action && (
                <option value={action}>{action}</option>
              )}
              {groups.map((group) => (
                <optgroup key={group} label={group}>
                  {ACTION_OPTIONS.filter((option) => option.group === group).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>

        {!asTemplate && (
          <div>
            <label className="label">
              Target device
              {['ssh', 'adb'].includes(adapter) && (
                <span className="ml-2 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold text-text-muted">
                  optional override
                </span>
              )}
            </label>
            <select className="input" value={deviceId} onChange={(e) => setDeviceId(e.target.value)}>
              <option value="">
                {['ssh', 'adb'].includes(adapter)
                  ? `Use this test's run location${runTargetLabel ? ` — ${runTargetLabel}` : ''}`
                  : targets.length > 0
                    ? 'No specific target — use step parameters'
                    : `No ${adapter || 'matching'} targets configured (see Configuration)`}
              </option>
              {targets.map((config) => (
                <option key={config.id} value={config.id}>
                  {config.label}
                  {config.last_test_ok === true ? ' ● connected' : ''}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-text-muted">
              {['ssh', 'adb'].includes(adapter) ? (
                <>
                  By default this step runs on the test's <b>Run location</b> (chosen at the
                  top of the designer). Pick a target here only to <b>override</b> it for this
                  one step — that injects its credentials and locks the device while it runs.
                </>
              ) : (
                <>Binding a target injects its connection details and locks the device while this step runs.</>
              )}
            </p>
          </div>
        )}

        {/* Parameters as plain form fields — no JSON required */}
        <div>
          <label className="label">
            Step settings
            {requiredMissing && (
              <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-600">
                {prettyParamName(requiredKey)} required
              </span>
            )}
          </label>
          <div className="space-y-2">
            {fields.map(([key, value], index) => (
              <div key={key} className="flex items-center gap-2">
                <span className="w-40 shrink-0 text-sm text-text-secondary">
                  {prettyParamName(key)}
                </span>
                {typeof value === 'boolean' ? (
                  <input
                    type="checkbox"
                    className="accent-primary"
                    checked={value}
                    onChange={(e) => setField(index, e.target.checked)}
                  />
                ) : typeof value === 'number' ? (
                  <input
                    type="number"
                    className="input flex-1"
                    value={value}
                    onChange={(e) => setField(index, Number(e.target.value))}
                  />
                ) : (
                  <div className="flex flex-1 items-center gap-1.5">
                    <input
                      className={`input flex-1 ${
                        key === requiredKey && String(value).trim() === ''
                          ? 'border-amber-500/60'
                          : ''
                      }`}
                      value={value}
                      placeholder={PARAM_HINTS[key] ?? ''}
                      onChange={(e) => setField(index, e.target.value)}
                    />
                    {isFileParam(key) && (
                      <button
                        type="button"
                        className="btn-outline shrink-0 px-2 py-1 text-xs"
                        disabled={uploading}
                        title="Upload a file and use it for this step"
                        onClick={() => pickFileForField(index)}
                      >
                        <Upload size={12} /> {uploading ? '…' : 'File'}
                      </button>
                    )}
                  </div>
                )}
                <button
                  className="btn-ghost p-1 text-error"
                  onClick={() =>
                    setFields((current) => current.filter((_, i) => i !== index))
                  }
                  aria-label={`Remove ${key}`}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
            <input
              ref={fieldFileRef}
              type="file"
              className="hidden"
              onChange={(e) => void handleFieldFile(e.target.files)}
            />
            {uploadError && (
              <p className="rounded-md border border-error/40 bg-error/10 px-2 py-1 text-xs text-error">
                {uploadError}
              </p>
            )}
            {requiredMissing && (
              <p className="text-[11px] text-amber-600">
                Type the path to your script/.exe, or use <b>File</b> to upload one — the
                step won't run without it.
              </p>
            )}
            {fields.length === 0 && (
              <p className="text-xs text-text-muted">This action needs no settings.</p>
            )}
            <div className="flex items-center gap-2">
              {newKeyMode === 'pick' ? (
                <select
                  className="input w-52 text-xs"
                  value=""
                  onChange={(e) => {
                    const choice = e.target.value;
                    if (choice === '__custom__') {
                      setNewKeyMode('custom');
                      setNewKey('');
                    } else if (choice) {
                      setFields((current) => [...current, [choice, '']]);
                    }
                  }}
                >
                  <option value="">+ Add setting…</option>
                  {availableParams.map((key) => (
                    <option key={key} value={key}>
                      {prettyParamName(key)}
                    </option>
                  ))}
                  <option value="__custom__">Custom setting…</option>
                </select>
              ) : (
                <>
                  <input
                    className="input w-40 text-xs"
                    value={newKey}
                    autoFocus
                    onChange={(e) => setNewKey(e.target.value)}
                    placeholder="custom setting name"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newKey.trim() && !fields.some(([k]) => k === newKey.trim())) {
                        setFields((current) => [...current, [newKey.trim(), '']]);
                        setNewKey('');
                        setNewKeyMode('pick');
                      }
                    }}
                  />
                  <button
                    className="btn-outline px-2 py-1 text-xs"
                    disabled={!newKey.trim() || fields.some(([k]) => k === newKey.trim())}
                    onClick={() => {
                      setFields((current) => [...current, [newKey.trim(), '']]);
                      setNewKey('');
                      setNewKeyMode('pick');
                    }}
                  >
                    <Plus size={12} /> Add
                  </button>
                  <button
                    className="btn-ghost px-2 py-1 text-xs"
                    onClick={() => {
                      setNewKey('');
                      setNewKeyMode('pick');
                    }}
                  >
                    Cancel
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        <div>
          <label className="label">Files — input (delivered to target) & output (attached to report)</label>
          <div className="space-y-1.5">
            {attachments.map((att, index) => (
              <div
                key={`${att.path}-${index}`}
                className="rounded-lg border border-border bg-background px-2.5 py-1.5"
              >
                <div className="flex items-center gap-2">
                  <Paperclip size={13} className="shrink-0 text-cyan-400" />
                  <span className="min-w-0 flex-1 truncate text-xs" title={att.name}>
                    {att.name}
                  </span>
                  {att.size != null && (
                    <span className="shrink-0 text-[10px] text-text-muted">
                      {Math.max(1, Math.round(att.size / 1024))} KB
                    </span>
                  )}
                  <button
                    className="btn-ghost p-1 text-error"
                    onClick={() =>
                      setAttachments((current) => current.filter((_, i) => i !== index))
                    }
                    aria-label={`Remove ${att.name}`}
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
                <input
                  className="input mt-1.5 w-full text-xs"
                  placeholder="Deliver before run to… (e.g. /tmp/config.dlt or /sdcard/) — leave blank to only attach to report"
                  value={att.deliver_to ?? ''}
                  onChange={(e) =>
                    setAttachments((current) =>
                      current.map((a, i) =>
                        i === index ? { ...a, deliver_to: e.target.value } : a,
                      ),
                    )
                  }
                />
              </div>
            ))}
            <input
              ref={fileRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => void handleUpload(e.target.files)}
            />
            <button
              className="btn-outline px-2.5 py-1 text-xs"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip size={12} /> {uploading ? 'Uploading…' : 'Attach file'}
            </button>
            <p className="text-[11px] text-text-muted">
              <b>Output:</b> with no destination, a file just attaches to this step
              in the report. <b>Input:</b> add a destination path to <b>deliver</b>
              the file to the step's SSH/ADB target <b>before</b> it runs (e.g.
              push a config or firmware the step then uses).
            </p>
          </div>
        </div>

        <div>
          <label className="label">Pass when the output… (all conditions must match)</label>
          <div className="space-y-2">
            {expects.map((expect, index) => (
              <div key={index} className="flex gap-2">
                <select
                  className="input w-40 shrink-0"
                  value={expect.mode}
                  onChange={(e) =>
                    setExpects((current) =>
                      current.map((x, i) => (i === index ? { ...x, mode: e.target.value } : x)),
                    )
                  }
                >
                  {MATCH_MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
                <input
                  className="input flex-1"
                  value={expect.text}
                  onChange={(e) =>
                    setExpects((current) =>
                      current.map((x, i) => (i === index ? { ...x, text: e.target.value } : x)),
                    )
                  }
                  placeholder={
                    expect.mode === 'wildcard'
                      ? 'e.g. *active* or systemctl*'
                      : expect.mode === 'regex'
                        ? 'e.g. v\\d+\\.\\d+'
                        : expect.mode === 'exact'
                          ? 'the exact expected output'
                          : 'text that must appear'
                  }
                />
                <button
                  className="btn-ghost p-1 text-error"
                  onClick={() => setExpects((current) => current.filter((_, i) => i !== index))}
                  aria-label="Remove condition"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
            <button
              className="btn-outline px-2.5 py-1 text-xs"
              onClick={() => setExpects((current) => [...current, { text: '', mode: 'contains' }])}
            >
              <Plus size={12} /> Add condition
            </button>
          </div>
          <p className="mt-1 text-[11px] text-text-muted">
            Add one or more checks — the step passes only if <b>every</b> condition
            matches. No conditions = pass on a zero exit code. Each expected vs actual
            result is shown in the report.
          </p>
        </div>

        <div>
          <label className="label">Execution flow</label>
          <select className="input" value={flow} onChange={(e) => setFlow(e.target.value)}>
            {/* Preserve the step's actual parallel group (B, C, …) so editing a
                member of any group round-trips losslessly — without this it would
                collapse into group A and you'd have to ungroup and redo. */}
            {flow.startsWith('parallel-') && !FLOW_OPTIONS.some((o) => o.value === flow) && (
              <option value={flow}>
                Parallel — group {flow.replace('parallel-', '')} (runs together)
              </option>
            )}
            {FLOW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {flow.startsWith('parallel-') && (
            <p className="mt-1 text-[11px] text-text-muted">
              This step runs together with the other steps in parallel group{' '}
              <b>{flow.replace('parallel-', '')}</b>. Editing here keeps it in that group.
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Timeout</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                className="input w-24"
                value={timeout}
                min={1}
                onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
              />
              <span className="text-xs text-text-muted">sec</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[
                { label: '15s', v: 15 },
                { label: '30s', v: 30 },
                { label: '1m', v: 60 },
                { label: '2m', v: 120 },
                { label: '5m', v: 300 },
                { label: '10m', v: 600 },
              ].map((preset) => (
                <button
                  key={preset.v}
                  type="button"
                  className={`rounded-md border px-2 py-0.5 text-xs transition-colors ${
                    timeout === preset.v
                      ? 'border-primary bg-primary/15 text-primary'
                      : 'border-border text-text-secondary hover:bg-surface-2'
                  }`}
                  onClick={() => setTimeoutSeconds(preset.v)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">Retry count</label>
            <input
              type="number"
              className="input w-24"
              value={retries}
              min={0}
              onChange={(e) => setRetries(Number(e.target.value))}
            />
          </div>
        </div>

        <button
          className="text-xs text-text-muted underline-offset-2 hover:underline"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? 'Hide' : 'Show'} advanced (raw JSON for conditions, loops…)
        </button>
        {showAdvanced && (
          <div>
            <textarea
              className="input min-h-[100px] font-mono text-xs"
              value={advancedText}
              onChange={(e) => setAdvancedText(e.target.value)}
              spellCheck={false}
            />
            {jsonError && <p className="mt-1 text-xs text-error">{jsonError}</p>}
            <p className="mt-1 text-[11px] text-text-muted">
              Power-user keys: <code>_retry</code>, <code>_loop</code>, <code>_if</code>,{' '}
              <code>{'{{steps.N.output}}'}</code>
            </p>
          </div>
        )}

        {asTemplate ? (
          /* Template-design mode: name + palette group, then save to the palette. */
          <div className="space-y-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div>
                <label className="label text-[11px]">Template name</label>
                <input
                  className="input"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g. Reboot then wait for SSH"
                />
              </div>
              <div>
                <label className="label text-[11px]">Palette group</label>
                <input
                  className="input"
                  value={templateGroup}
                  onChange={(e) => setTemplateGroup(e.target.value)}
                  placeholder="My steps"
                />
              </div>
            </div>
            {templateError && <p className="text-xs text-error">{templateError}</p>}
            <p className="text-[11px] text-text-muted">
              Saves to your palette under <b>{templateGroup.trim() || 'My steps'}</b> — drag it onto
              any test to reuse it.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-outline" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" onClick={() => void saveAsTemplate()}>
                <BookmarkPlus size={14} /> {templateId ? 'Update template' : 'Save template'}
              </button>
            </div>
          </div>
        ) : (
          <>
            {showTemplateForm && (
              <div className="space-y-2 rounded-lg border border-primary/30 bg-primary/5 p-3">
                <p className="text-xs font-semibold text-text-secondary">
                  Save this configured step to your palette so you can reuse it on any test.
                </p>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div>
                    <label className="label text-[11px]">Template name</label>
                    <input
                      className="input"
                      value={templateName}
                      autoFocus
                      onChange={(e) => setTemplateName(e.target.value)}
                      placeholder="e.g. Reboot then wait for SSH"
                    />
                  </div>
                  <div>
                    <label className="label text-[11px]">Palette group</label>
                    <input
                      className="input"
                      value={templateGroup}
                      onChange={(e) => setTemplateGroup(e.target.value)}
                      placeholder="My steps"
                    />
                  </div>
                </div>
                {templateError && <p className="text-xs text-error">{templateError}</p>}
                <div className="flex justify-end gap-2">
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setShowTemplateForm(false)}>
                    Cancel
                  </button>
                  <button className="btn-primary px-2.5 py-1 text-xs" onClick={() => void saveAsTemplate()}>
                    <BookmarkPlus size={13} /> Save template
                  </button>
                </div>
              </div>
            )}
            {templateSaved && !showTemplateForm && (
              <p className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-500">
                ✓ Saved to your palette under “{templateGroup.trim() || 'My steps'}”. Drag it onto
                any test from the palette to reuse it.
              </p>
            )}

            <div className="flex items-center gap-2">
              <button
                className="btn-outline mr-auto text-xs"
                onClick={() => {
                  setTemplateName(label.trim() || friendlyAction(action));
                  setTemplateSaved(false);
                  setTemplateError(null);
                  setShowTemplateForm(true);
                }}
                title="Save this configured step to your palette for reuse"
              >
                <BookmarkPlus size={14} /> Save as template
              </button>
              <button className="btn-outline" onClick={onClose}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleSave}>
                Save step
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
