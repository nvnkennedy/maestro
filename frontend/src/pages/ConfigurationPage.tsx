import { useEffect, useMemo, useState } from 'react';
import {
  Camera,
  FolderKanban,
  Pencil,
  PlugZap,
  Plus,
  RefreshCw,
  ScanSearch,
  Settings2,
  Smartphone,
  Trash2,
  Usb,
} from 'lucide-react';
import { MainLayout } from '../components/layout/MainLayout';
import { Modal } from '../components/common/Modal';
import { Spinner } from '../components/common/Spinner';
import { ActionChip } from '../components/common/ActionChip';
import { useToast } from '../components/common/Toast';
import { useApi } from '../hooks/useApi';
import { useProject } from '../context/ProjectContext';
import {
  createConfig,
  createProject,
  deleteConfigs,
  deleteProject,
  detectDevices,
  listConfigs,
  testConfigConnection,
  updateConfig,
  updateProject,
  type DetectedDevice,
} from '../services/api';
import type { DeviceConfig, Project } from '../types/domain';

// ---- typed per-adapter forms (no raw JSON for users) -------------------------

interface FieldDef {
  key: string;
  label: string;
  placeholder: string;
  type?: 'text' | 'number' | 'password' | 'select';
  required?: boolean;
  hint?: string;
  options?: { value: string; label: string }[];
}

interface FormDef {
  fields: FieldDef[];
  credentials: FieldDef[];
  intro: string;
  /** kind passed to the detection endpoint, when this type is detectable */
  detect?: 'adb' | 'camera' | 'serial';
}

const FORM_DEFS: Record<string, FormDef> = {
  target: {
    intro:
      'A Run Target decides WHERE a test runs: this machine (Local) or a remote ' +
      'domain-joined / RDP host reached over SSH (DOMAIN\\user). Pick a target on ' +
      'each test case, scenario or at run time. Remote run_command/run_file steps ' +
      'execute on that host.',
    fields: [
      {
        key: 'kind',
        label: 'Where does this target run?',
        placeholder: '',
        type: 'select',
        required: true,
        options: [
          { value: 'remote', label: 'Remote host (RDP / domain-joined, via SSH)' },
          { value: 'local', label: 'Local (this machine)' },
        ],
      },
      {
        key: 'os',
        label: 'Remote OS',
        placeholder: '',
        type: 'select',
        options: [
          { value: 'windows', label: 'Windows (cmd/PowerShell over OpenSSH)' },
          { value: 'linux', label: 'Linux / QNX (bash)' },
        ],
        hint: 'Only used for remote targets — picks the right shell behaviour',
      },
      { key: 'hostname', label: 'Hostname / IP', placeholder: 'PC-BENCH-07 or 192.168.1.10' },
      { key: 'port', label: 'SSH port', placeholder: '22', type: 'number' },
      { key: 'username', label: 'Username', placeholder: 'tester' },
      {
        key: 'domain',
        label: 'Windows domain (optional)',
        placeholder: 'CORP',
        hint: 'Domain / RDP hosts log in as DOMAIN\\username with the password below',
      },
      {
        key: 'power_script',
        label: 'Power script path (one-time)',
        placeholder: 'C:/bench/power_control.py',
        hint: 'Reference it in a step with {{target.power_script}}',
      },
      {
        key: 'etfw_script',
        label: 'ETFW script path (one-time)',
        placeholder: 'C:/bench/etfw.py',
        hint: 'Reference with {{target.etfw_script}}',
      },
      {
        key: 'dlt_script',
        label: 'DLT script path (one-time)',
        placeholder: 'C:/bench/dlt.py',
        hint: 'Reference with {{target.dlt_script}}',
      },
      {
        key: 'adb_path',
        label: 'adb path (optional)',
        placeholder: 'C:/platform-tools/adb.exe',
        hint: 'Injected into adb steps run on this machine',
      },
      {
        key: 'ffmpeg_path',
        label: 'ffmpeg path (optional)',
        placeholder: 'C:/ffmpeg/bin/ffmpeg.exe',
        hint: 'Injected into camera steps run on this machine',
      },
      {
        key: 'scrcpy_path',
        label: 'scrcpy path (optional)',
        placeholder: 'C:/scrcpy/scrcpy.exe',
        hint: 'Reference with {{target.scrcpy_path}}',
      },
    ],
    credentials: [
      { key: 'password', label: 'Password', placeholder: '••••••', type: 'password' },
    ],
  },
  ssh: {
    intro:
      'SSH targets need a password OR a private key. IP, port and login plus a ' +
      'password (or key file). For a domain/RDP host, add the Windows domain.',
    fields: [
      { key: 'host', label: 'Host / IP address', placeholder: '192.168.1.10', required: true },
      { key: 'port', label: 'Port', placeholder: '22', type: 'number' },
      { key: 'username', label: 'Username', placeholder: 'root', required: true },
      {
        key: 'domain',
        label: 'Windows domain (optional)',
        placeholder: 'CORP',
        hint: 'For domain / RDP hosts — logs in as DOMAIN\\username with the password below',
      },
      {
        key: 'key_file',
        label: 'Private key file (optional)',
        placeholder: 'C:/keys/id_rsa',
        hint: 'Use a key instead of a password (e.g. passwordless QNX/embedded root)',
      },
      { key: 'working_dir', label: 'Working directory', placeholder: '/tmp' },
    ],
    credentials: [
      { key: 'password', label: 'Password', placeholder: '••••••', type: 'password' },
    ],
  },
  adb: {
    intro:
      'ADB is path-based: point Maestro at adb.exe (leave empty to auto-find on PATH / platform-tools). Connected devices are detected automatically below.',
    fields: [
      {
        key: 'adb_path',
        label: 'ADB executable path',
        placeholder: 'C:/platform-tools/adb.exe (empty = auto-detect)',
      },
      {
        key: 'serial',
        label: 'Device serial (optional)',
        placeholder: 'pick from detected devices below',
        hint: 'Leave empty to use the only connected device',
      },
    ],
    credentials: [],
    detect: 'adb',
  },
  power: {
    intro: 'Power control is script-based: the path to your power.ps1 / power.py.',
    fields: [
      {
        key: 'script_path',
        label: 'Power script path',
        placeholder: 'C:/scripts/power.ps1',
        required: true,
      },
    ],
    credentials: [],
  },
  etfw: {
    intro: 'ETFW is path-based: the path to the ETFW tool executable.',
    fields: [
      {
        key: 'etfw_path',
        label: 'ETFW tool path',
        placeholder: 'C:/tools/etfw.exe',
        required: true,
      },
    ],
    credentials: [],
  },
  dlt: {
    intro:
      'DLT is path-based: the DLT tool and/or an existing .dlt trace file. Host/port are only needed for live TCP capture.',
    fields: [
      { key: 'dlt_path', label: 'DLT tool path', placeholder: 'C:/tools/dlt-viewer.exe' },
      { key: 'file_path', label: 'DLT file path', placeholder: 'C:/dlt/trace.dlt' },
      { key: 'host', label: 'Live capture host (optional)', placeholder: '192.168.1.10' },
      { key: 'port', label: 'Live capture port (optional)', placeholder: '3490', type: 'number' },
    ],
    credentials: [],
  },
  camera: {
    intro:
      'Cameras on this machine are detected automatically — no manual setup. Save a detected camera as a target to use it in test steps.',
    fields: [
      { key: 'camera_name', label: 'Camera name', placeholder: 'Integrated Camera' },
    ],
    credentials: [],
    detect: 'camera',
  },
  serial: {
    intro:
      'COM ports on this machine are detected automatically. Save a detected port as a target, then set the baudrate.',
    fields: [
      { key: 'port', label: 'COM port', placeholder: 'COM3', required: true },
      { key: 'baudrate', label: 'Baudrate', placeholder: '115200', type: 'number' },
    ],
    credentials: [],
    detect: 'serial',
  },
};

const TAB_ICONS: Record<string, JSX.Element> = {
  target: <PlugZap size={13} />,
  adb: <Smartphone size={13} />,
  camera: <Camera size={13} />,
  serial: <Usb size={13} />,
};

// Friendlier tab labels (the key is the config_type).
const TAB_LABELS: Record<string, string> = {
  target: 'Machines (Local / RDP)',
};

function statusOf(config: DeviceConfig): { dot: string; text: string; cls: string } {
  if (config.last_test_ok === true)
    return { dot: 'bg-emerald-400', text: 'Connected', cls: 'text-emerald-400' };
  if (config.last_test_ok === false)
    return { dot: 'bg-red-400', text: 'Unreachable', cls: 'text-red-400' };
  return { dot: 'bg-slate-400', text: 'Not tested', cls: 'text-text-muted' };
}

function ProjectsPanel() {
  const { projects, activeProjectId, setActiveProjectId, refreshProjects } = useProject();
  const toast = useToast();
  const [editing, setEditing] = useState<Project | 'new' | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const openEditor = (project: Project | 'new') => {
    setName(project === 'new' ? '' : project.name);
    setDescription(project === 'new' ? '' : project.description);
    setEditing(project);
  };

  const save = async () => {
    try {
      if (editing === 'new') {
        const created = await createProject({ name, description });
        setActiveProjectId(created.id);
      } else if (editing) {
        await updateProject(editing.id, { name, description });
      }
      setEditing(null);
      toast('success', 'Project saved');
      await refreshProjects();
    } catch {
      toast('error', 'Save failed — the project name may already exist');
    }
  };

  // Deleting the last remaining project requires downloading a backup first.
  const [backupTarget, setBackupTarget] = useState<Project | null>(null);
  const [backupDownloaded, setBackupDownloaded] = useState(false);

  const performDelete = async (project: Project) => {
    try {
      await deleteProject(project.id);
      toast('success', 'Project deleted');
      await refreshProjects();
    } catch {
      toast('error', 'Delete failed');
    }
  };

  const remove = async (project: Project) => {
    if (projects.length <= 1) {
      setBackupDownloaded(false);
      setBackupTarget(project);
      return;
    }
    if (
      !window.confirm(
        `Delete project "${project.name}" with ALL its test cases, targets and run history? This cannot be undone.`,
      )
    )
      return;
    await performDelete(project);
  };

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => (
          <div
            key={project.id}
            className={`card flex flex-col p-5 ${
              project.id === activeProjectId ? 'ring-1 ring-primary/50' : ''
            }`}
          >
            <div className="mb-2 flex items-start justify-between">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/15 text-indigo-400">
                  <FolderKanban size={16} />
                </span>
                <div>
                  <div className="font-semibold">{project.name}</div>
                  <div className="text-[11px] text-text-muted">
                    {project.test_case_count} test cases
                  </div>
                </div>
              </div>
              {project.id === activeProjectId && (
                <span className="badge bg-primary/15 text-primary">active</span>
              )}
            </div>
            <p className="mb-4 flex-1 text-xs text-text-secondary">
              {project.description || 'No description'}
            </p>
            <div className="flex gap-2">
              {project.id !== activeProjectId && (
                <button
                  className="btn-outline flex-1 justify-center text-xs"
                  onClick={() => setActiveProjectId(project.id)}
                >
                  Switch to
                </button>
              )}
              <button className="btn-outline text-xs" onClick={() => openEditor(project)}>
                <Pencil size={13} className="text-amber-400" /> Edit
              </button>
              <button
                className="btn-danger text-xs"
                onClick={() => void remove(project)}
                title="Delete project"
              >
                <Trash2 size={13} />
              </button>
            </div>
          </div>
        ))}
        <button
          className="flex min-h-[150px] flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-text-muted transition-colors hover:border-primary/50 hover:text-primary"
          onClick={() => openEditor('new')}
        >
          <Plus size={26} />
          <span className="text-sm font-medium">New Project</span>
        </button>
      </div>

      <Modal
        open={backupTarget !== null}
        title="Backup required before deleting"
        onClose={() => setBackupTarget(null)}
      >
        {backupTarget && (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">
              <b className="text-text-primary">"{backupTarget.name}"</b> is your only
              project. Before deleting it, download a backup of its test cases,
              targets and schedules. A fresh empty project will be created after
              deletion.
            </p>
            <a
              className="btn-primary w-full justify-center"
              href={`/api/projects/${backupTarget.id}/export`}
              onClick={() => setBackupDownloaded(true)}
            >
              1. Download backup (JSON)
            </a>
            <button
              className="btn-danger w-full justify-center"
              disabled={!backupDownloaded}
              title={!backupDownloaded ? 'Download the backup first' : ''}
              onClick={async () => {
                const target = backupTarget;
                setBackupTarget(null);
                await performDelete(target);
              }}
            >
              <Trash2 size={14} /> 2. Delete project permanently
            </button>
          </div>
        )}
      </Modal>

      <Modal
        open={editing !== null}
        title={editing === 'new' ? 'New project' : 'Edit project'}
        onClose={() => setEditing(null)}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Project name</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. i3 Platform"
              autoFocus
            />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea
              className="input min-h-[70px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is tested in this project?"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button className="btn-outline" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={save} disabled={!name.trim()}>
              Save project
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}

export function ConfigurationPage() {
  const { activeProjectId } = useProject();
  const toast = useToast();
  const [tab, setTab] = useState<string>('projects');
  const [editing, setEditing] = useState<DeviceConfig | 'new' | null>(null);
  const [testing, setTesting] = useState<number | null>(null);

  const { data: configs, loading, refetch } = useApi(
    () => (activeProjectId ? listConfigs(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );

  const def = FORM_DEFS[tab];
  const tabConfigs = useMemo(
    () => (configs ?? []).filter((config) => config.config_type === tab),
    [configs, tab],
  );

  // ---- detection panel -------------------------------------------------------

  const [detected, setDetected] = useState<DetectedDevice[]>([]);
  const [detectError, setDetectError] = useState('');
  const [detecting, setDetecting] = useState(false);

  const runDetect = async (kind: 'adb' | 'camera' | 'serial') => {
    setDetecting(true);
    setDetectError('');
    try {
      const result = await detectDevices(kind);
      setDetected(result.devices ?? []);
      if (!result.success && result.error) setDetectError(result.error);
    } catch {
      setDetectError('Detection failed');
    } finally {
      setDetecting(false);
    }
  };

  useEffect(() => {
    setDetected([]);
    setDetectError('');
    if (def?.detect) void runDetect(def.detect);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // ---- form state -------------------------------------------------------------

  const [label, setLabel] = useState('');
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [credValues, setCredValues] = useState<Record<string, string>>({});

  const openEditor = (config: DeviceConfig | 'new', preset?: Record<string, string>) => {
    if (config === 'new') {
      setLabel(preset?._label ?? '');
      const values: Record<string, string> = {};
      def.fields.forEach((field) => {
        values[field.key] = preset?.[field.key] ?? '';
      });
      if (tab === 'ssh') values.port = values.port || '22';
      if (tab === 'serial') values.baudrate = values.baudrate || '115200';
      if (tab === 'target') {
        values.kind = values.kind || 'remote';
        values.os = values.os || 'windows';
        values.port = values.port || '22';
      }
      setFieldValues(values);
      setCredValues({});
    } else {
      setLabel(config.label);
      const values: Record<string, string> = {};
      def.fields.forEach((field) => {
        values[field.key] = String(config.settings[field.key] ?? '');
      });
      setFieldValues(values);
      setCredValues({});
    }
    setEditing(config);
  };

  const save = async () => {
    if (!activeProjectId || !def) return;
    const missing = def.fields.filter((f) => f.required && !fieldValues[f.key]?.trim());
    if (missing.length > 0) {
      toast('error', `Please fill in: ${missing.map((f) => f.label).join(', ')}`);
      return;
    }
    const settings: Record<string, unknown> = {};
    def.fields.forEach((field) => {
      const raw = (fieldValues[field.key] ?? '').trim();
      if (!raw) return;
      settings[field.key] = field.type === 'number' ? Number(raw) : raw;
    });
    const credentials: Record<string, string> = {};
    def.credentials.forEach((field) => {
      const raw = credValues[field.key] ?? '';
      if (raw) credentials[field.key] = raw;
    });
    // SSH with no password/key is allowed — for passwordless embedded/QNX root
    // Maestro tries empty-password and the SSH 'none' method (like MobaXterm).
    if (tab === 'ssh' && editing === 'new' && !credentials.password && !settings.key_file) {
      toast('info', 'No password/key — will connect passwordless (empty / none auth).');
    }
    try {
      const payload = { project_id: activeProjectId, config_type: tab, label, settings, credentials };
      if (editing === 'new') await createConfig(payload);
      else if (editing) await updateConfig(editing.id, payload);
      setEditing(null);
      toast('success', 'Target saved');
      void refetch();
    } catch (err) {
      toast('error', `Save failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const testConnection = async (id: number) => {
    setTesting(id);
    try {
      const result = await testConfigConnection(id);
      if (result.success) toast('success', `Connection OK: ${result.label}`);
      else toast('error', `Connection failed: ${result.error || 'unknown error'}`);
    } finally {
      setTesting(null);
      void refetch();
    }
  };

  const remove = async (config: DeviceConfig) => {
    if (!window.confirm(`Delete target "${config.label}"?`)) return;
    await deleteConfigs([config.id]);
    toast('success', 'Target deleted');
    void refetch();
  };

  const saveDetectedAsTarget = (device: DetectedDevice) => {
    if (tab === 'adb') {
      openEditor('new', { _label: `adb_${device.serial}`, serial: device.serial ?? '' });
    } else if (tab === 'camera') {
      openEditor('new', { _label: device.name ?? 'camera', camera_name: device.name ?? '' });
    } else if (tab === 'serial') {
      openEditor('new', {
        _label: `${device.device} (${device.description ?? 'serial'})`,
        port: device.device ?? '',
        baudrate: '115200',
      });
    }
  };

  return (
    <MainLayout
      title="Configuration"
      subtitle="Targets, tool paths and auto-detected devices"
      icon={<Settings2 size={18} />}
      iconClass="bg-orange-500/15 text-orange-400"
    >
      <div className="space-y-4">
        {/* Type tabs */}
        <div className="flex flex-wrap gap-1.5">
          {['projects', ...Object.keys(FORM_DEFS)].map((type) => (
            <button
              key={type}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold uppercase tracking-wide transition-all ${
                tab === type
                  ? 'bg-primary/15 text-primary ring-1 ring-primary/40'
                  : 'bg-surface text-text-secondary hover:bg-surface-2'
              }`}
              onClick={() => setTab(type)}
            >
              {type === 'projects' ? <FolderKanban size={13} /> : TAB_ICONS[type]}
              {TAB_LABELS[type] ?? type}
            </button>
          ))}
        </div>

        {tab === 'projects' && <ProjectsPanel />}

        {tab !== 'projects' && <p className="text-sm text-text-secondary">{def?.intro}</p>}

        {/* Auto-detection panel */}
        {tab !== 'projects' && def?.detect && (
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <ScanSearch size={15} className="text-cyan-400" />
                Detected on this machine
              </h3>
              <button
                className="btn-outline px-2.5 py-1 text-xs"
                onClick={() => def.detect && void runDetect(def.detect)}
                disabled={detecting}
              >
                <RefreshCw size={13} className={detecting ? 'animate-spin' : ''} />
                {detecting ? 'Scanning…' : 'Rescan'}
              </button>
            </div>
            {detectError && <p className="mb-2 text-xs text-error">{detectError}</p>}
            <div className="flex flex-wrap gap-2">
              {detected.map((device, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2"
                >
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span className="text-sm font-medium">
                    {device.name ?? device.serial ?? device.device}
                  </span>
                  {(device.state || device.description) && (
                    <span className="text-xs text-text-muted">
                      {device.state ?? device.description}
                    </span>
                  )}
                  <button
                    className="btn-ghost px-1.5 py-0.5 text-xs text-primary"
                    onClick={() => saveDetectedAsTarget(device)}
                  >
                    <Plus size={12} /> Save as target
                  </button>
                </div>
              ))}
              {!detecting && detected.length === 0 && !detectError && (
                <span className="text-sm text-text-muted">
                  Nothing detected — connect a device and rescan.
                </span>
              )}
            </div>
          </div>
        )}

        {/* Saved targets */}
        {tab === 'projects' ? null : loading ? (
          <Spinner />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {tabConfigs.map((config) => {
              const status = statusOf(config);
              return (
                <div key={config.id} className="card flex flex-col p-5">
                  <div className="mb-3 flex items-start justify-between">
                    <div>
                      <div className="font-semibold">{config.label}</div>
                      <div className={`mt-1 flex items-center gap-1.5 text-xs ${status.cls}`}>
                        <span className={`h-2 w-2 rounded-full ${status.dot}`} />
                        {status.text}
                      </div>
                    </div>
                    <ActionChip action={`${config.config_type}.target`} />
                  </div>
                  <div className="mb-4 flex-1 space-y-1.5">
                    {Object.entries(config.settings).map(([key, value]) => (
                      <div key={key} className="flex justify-between gap-3 text-xs">
                        <span className="capitalize text-text-muted">
                          {key.replace(/_/g, ' ')}
                        </span>
                        <span className="truncate font-mono font-medium">{String(value)}</span>
                      </div>
                    ))}
                    {config.credential_keys.length > 0 && (
                      <div className="flex justify-between gap-3 text-xs">
                        <span className="text-text-muted">Credentials</span>
                        <span className="font-mono font-medium text-violet-400">
                          •••••• ({config.credential_keys.join(', ')})
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn-outline flex-1 justify-center text-xs"
                      onClick={() => void testConnection(config.id)}
                      disabled={testing === config.id}
                    >
                      <PlugZap size={13} className="text-sky-400" />
                      {testing === config.id ? 'Testing…' : 'Test Connection'}
                    </button>
                    <button className="btn-outline text-xs" onClick={() => openEditor(config)}>
                      <Pencil size={13} className="text-amber-400" /> Edit
                    </button>
                    <button className="btn-danger text-xs" onClick={() => void remove(config)}>
                      <Trash2 size={13} /> Delete
                    </button>
                  </div>
                </div>
              );
            })}

            <button
              className="flex min-h-[170px] flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border text-text-muted transition-colors hover:border-primary/50 hover:text-primary"
              onClick={() => openEditor('new')}
            >
              <Plus size={26} />
              <span className="text-sm font-medium">Add Target</span>
            </button>
          </div>
        )}
      </div>

      {/* Typed editor modal */}
      <Modal
        open={editing !== null}
        title={editing === 'new' ? `Add ${tab.toUpperCase()} target` : 'Edit target'}
        onClose={() => setEditing(null)}
      >
        <div className="space-y-4">
          <div>
            <label className="label">Label</label>
            <input
              className="input"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder={`e.g. i3_${tab}`}
            />
          </div>
          {def?.fields.map((field) => (
            <div key={field.key}>
              <label className="label">
                {field.label}
                {field.required && <span className="text-error"> *</span>}
              </label>
              {field.type === 'select' ? (
                <select
                  className="input"
                  value={fieldValues[field.key] ?? ''}
                  onChange={(event) =>
                    setFieldValues((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                >
                  {(field.options ?? []).map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  type={field.type === 'number' ? 'number' : 'text'}
                  value={fieldValues[field.key] ?? ''}
                  onChange={(event) =>
                    setFieldValues((current) => ({
                      ...current,
                      [field.key]: event.target.value,
                    }))
                  }
                  placeholder={field.placeholder}
                />
              )}
              {field.hint && <p className="mt-1 text-[11px] text-text-muted">{field.hint}</p>}
            </div>
          ))}
          {def?.credentials.map((field) => (
            <div key={field.key}>
              <label className="label">{field.label} (stored AES-256 encrypted)</label>
              <input
                className="input"
                type="password"
                value={credValues[field.key] ?? ''}
                onChange={(event) =>
                  setCredValues((current) => ({
                    ...current,
                    [field.key]: event.target.value,
                  }))
                }
                placeholder={
                  editing !== 'new' ? 'leave empty to keep current' : field.placeholder
                }
                autoComplete="new-password"
              />
            </div>
          ))}
          <div className="flex justify-end gap-2">
            <button className="btn-outline" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={save} disabled={!label}>
              Save target
            </button>
          </div>
        </div>
      </Modal>
    </MainLayout>
  );
}
