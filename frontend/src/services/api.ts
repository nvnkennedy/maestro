import axios from 'axios';
import type {
  AdapterHealth,
  DashboardStats,
  DeviceConfig,
  Execution,
  Plugin,
  Project,
  ReportSummary,
  Schedule,
  SchedulePayload,
  TemplateLibrary,
  TestCase,
  TestStep,
} from '../types/domain';

/**
 * Shared API token, when one is configured. The backend injects it into the
 * served index.html as <meta name="maestro-token">; in `vite` dev it comes from
 * VITE_MAESTRO_TOKEN. Left empty for the default zero-config local install.
 */
export const apiToken: string =
  (typeof document !== 'undefined' &&
    document.querySelector<HTMLMetaElement>('meta[name="maestro-token"]')?.content) ||
  (import.meta.env.VITE_MAESTRO_TOKEN as string | undefined) ||
  '';

export const client = axios.create({ baseURL: '/api' });

if (apiToken) {
  client.defaults.headers.common['X-Maestro-Token'] = apiToken;
}

// ---- acting user identity ---------------------------------------------------

const USER_KEY = 'maestro-user';

/** The identity used for triggered_by / audit. Persisted in localStorage. */
export function currentUser(): string {
  try {
    return window.localStorage.getItem(USER_KEY)?.trim() || 'admin';
  } catch {
    return 'admin';
  }
}

export function setCurrentUser(name: string): void {
  try {
    window.localStorage.setItem(USER_KEY, name.trim() || 'admin');
  } catch {
    /* storage may be unavailable */
  }
}

// Attach the acting user to every request so the backend records who did what.
client.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers['X-Maestro-User'] = currentUser();
  return config;
});

// ---- app meta ---------------------------------------------------------------

export const getHealth = () =>
  client.get<{ status: string; app: string; version: string }>('/health').then((r) => r.data);

// ---- projects ---------------------------------------------------------------

export const listProjects = () => client.get<Project[]>('/projects').then((r) => r.data);
export const createProject = (body: { name: string; description?: string }) =>
  client.post<Project>('/projects', body).then((r) => r.data);
export const updateProject = (id: number, body: { name: string; description?: string }) =>
  client.put<Project>(`/projects/${id}`, body).then((r) => r.data);
export const deleteProject = (id: number) => client.delete(`/projects/${id}`);

// ---- test cases -------------------------------------------------------------

export interface TestCasePayload {
  project_id: number;
  name: string;
  description?: string;
  test_type?: string;
  scenario?: string;
  default_target_id?: number | null;
  steps: TestStep[];
}

export const listTestCases = (projectId?: number) =>
  client
    .get<TestCase[]>('/test-cases', { params: { project_id: projectId } })
    .then((r) => r.data);
export const getTestCase = (id: number) =>
  client.get<TestCase>(`/test-cases/${id}`).then((r) => r.data);
export const createTestCase = (body: TestCasePayload) =>
  client.post<TestCase>('/test-cases', body).then((r) => r.data);
export const updateTestCase = (id: number, body: TestCasePayload) =>
  client.put<TestCase>(`/test-cases/${id}`, body).then((r) => r.data);
export const deleteTestCases = (ids: number[]) =>
  client.post('/test-cases/bulk-delete', { ids }).then((r) => r.data);
export const cloneTestCase = (id: number) =>
  client.post<TestCase>(`/test-cases/${id}/clone`).then((r) => r.data);
export const exportTestCase = (id: number) =>
  client.get<Record<string, unknown>>(`/test-cases/${id}/export`).then((r) => r.data);
export const importTestCase = (body: Record<string, unknown> & { project_id: number }) =>
  client.post<TestCase>('/test-cases/import', body).then((r) => r.data);
export const moveTestCases = (ids: number[], suite: string, scenario: string) =>
  client.post('/test-cases/move', { ids, suite, scenario }).then((r) => r.data);
export const renameGroup = (body: {
  project_id: number;
  suite: string;
  scenario?: string;
  new_name: string;
}) => client.post('/test-cases/rename-group', body).then((r) => r.data);
export const getTemplates = () =>
  client.get<TemplateLibrary>('/test-cases/templates').then((r) => r.data);

export interface PlannedAttachment {
  name: string;
  path: string;
  size?: number;
  /** Optional target path: when set, the file is delivered to the step's
   *  SSH/ADB device before the step runs (e.g. push a .dlt/config first). */
  deliver_to?: string;
}
export const uploadStepAttachment = (file: File) =>
  client
    .post<PlannedAttachment>('/test-cases/attachments', file, {
      params: { filename: file.name },
      headers: { 'Content-Type': 'application/octet-stream' },
    })
    .then((r) => r.data);

// ---- executions -------------------------------------------------------------

export const listExecutions = (params?: { project_id?: number; limit?: number }) =>
  client.get<Execution[]>('/executions', { params }).then((r) => r.data);
export const getExecution = (id: number) =>
  client.get<Execution>(`/executions/${id}`).then((r) => r.data);
export const startExecution = (
  testCaseId: number,
  mode: string,
  targetId?: number | null,
  cycles?: number,
  stopConditions?: Record<string, number> | null,
) =>
  client
    .post<Execution>('/executions', {
      test_case_id: testCaseId,
      mode,
      target_id: targetId ?? null,
      cycles: cycles ?? 1,
      stop_conditions: stopConditions ?? null,
    })
    .then((r) => r.data);

export interface CycleRollup {
  execution_id: number;
  cycles: {
    cycle_index: number;
    status: string;
    duration_seconds: number | null;
    summary: string;
  }[];
  rollup: {
    total: number;
    passed: number;
    failed: number;
    first_failure_cycle: number | null;
    is_endurance: boolean;
  };
}
export const getCycles = (executionId: number) =>
  client.get<CycleRollup>(`/reports/${executionId}/cycles`).then((r) => r.data);
export const controlExecution = (id: number, action: 'stop' | 'pause' | 'resume' | 'next') =>
  client.post(`/executions/${id}/${action}`).then((r) => r.data);

export interface SuiteRunPayload {
  project_id?: number;
  suite?: string;
  scenario?: string;
  test_case_ids?: number[];
  mode?: string;
  target_id?: number | null;
}

export const startSuiteRun = (body: SuiteRunPayload) =>
  client
    .post<import('../types/domain').SuiteRun>('/executions/suite', body)
    .then((r) => r.data);
export const stopSuiteRun = (suiteRunId: string) =>
  client.post(`/executions/suite/${suiteRunId}/stop`).then((r) => r.data);

// ---- reports ----------------------------------------------------------------

export const listReports = () => client.get<Execution[]>('/reports').then((r) => r.data);
export const getReportSummary = (executionId: number) =>
  client.get<ReportSummary>(`/reports/${executionId}`).then((r) => r.data);
export const deleteReports = (ids: number[]) =>
  client.post('/reports/bulk-delete', { ids }).then((r) => r.data);
export const compareReports = (a: number, b: number) =>
  client
    .post('/reports/compare', { execution_a: a, execution_b: b })
    .then((r) => r.data);
export const listPublishers = () =>
  client
    .get<{ name: string; configured: boolean }[]>('/reports/publishers')
    .then((r) => r.data);
export const publishReport = (executionId: number, channel: string) =>
  client
    .post<{ ok: boolean; skipped?: boolean; detail?: string }>(
      `/reports/${executionId}/publish`,
      { channel },
    )
    .then((r) => r.data);

// ---- device configs ----------------------------------------------------------

export interface DeviceConfigPayload {
  project_id: number;
  config_type: string;
  label: string;
  settings: Record<string, unknown>;
  credentials: Record<string, string>;
  is_active?: boolean;
}

export const listConfigs = (projectId?: number) =>
  client
    .get<DeviceConfig[]>('/configs', { params: { project_id: projectId } })
    .then((r) => r.data);
export const createConfig = (body: DeviceConfigPayload) =>
  client.post<DeviceConfig>('/configs', body).then((r) => r.data);
export const updateConfig = (id: number, body: DeviceConfigPayload) =>
  client.put<DeviceConfig>(`/configs/${id}`, body).then((r) => r.data);
export const deleteConfigs = (ids: number[]) =>
  client.post('/configs/bulk-delete', { ids }).then((r) => r.data);
export const testConfigConnection = (id: number) =>
  client.post(`/configs/${id}/test`).then((r) => r.data);

// ---- schedules ----------------------------------------------------------------

export const listSchedules = () => client.get<Schedule[]>('/schedules').then((r) => r.data);
export const createSchedule = (body: SchedulePayload) =>
  client.post<Schedule>('/schedules', body).then((r) => r.data);
export const toggleSchedule = (id: number) =>
  client.post<Schedule>(`/schedules/${id}/toggle`).then((r) => r.data);
export const deleteSchedule = (id: number) => client.delete(`/schedules/${id}`);

// ---- registered scripts & user templates --------------------------------------

export interface ScriptCommand {
  label?: string;
  args: string[];
}
export interface RegisteredScript {
  id: string;
  name: string;
  path: string;
  interpreter?: string;
  description?: string;
  commands: ScriptCommand[];
}

export const listScripts = () =>
  client.get<RegisteredScript[]>('/scripts').then((r) => r.data);
export const saveScript = (body: Partial<RegisteredScript>) =>
  body.id
    ? client.put<RegisteredScript>(`/scripts/${body.id}`, body).then((r) => r.data)
    : client.post<RegisteredScript>('/scripts', body).then((r) => r.data);
export const deleteScript = (id: string) => client.delete(`/scripts/${id}`);

export interface UserTemplate {
  id?: string;
  group: string;
  label: string;
  action: string;
  parameters: Record<string, unknown>;
  timeout_seconds: number;
}

export const listUserTemplates = () =>
  client.get<UserTemplate[]>('/templates').then((r) => r.data);
export const saveUserTemplate = (body: UserTemplate) =>
  body.id
    ? client.put<UserTemplate>(`/templates/${body.id}`, body).then((r) => r.data)
    : client.post<UserTemplate>('/templates', body).then((r) => r.data);
export const deleteUserTemplate = (id: string) => client.delete(`/templates/${id}`);

// ---- plugins / health / dashboard ---------------------------------------------

export const listPlugins = () => client.get<Plugin[]>('/plugins').then((r) => r.data);
export const togglePlugin = (name: string, enable: boolean) =>
  client.post(`/plugins/${name}/${enable ? 'enable' : 'disable'}`).then((r) => r.data);
export const adapterHealth = () =>
  client.get<Record<string, AdapterHealth>>('/connections/health').then((r) => r.data);

export interface DetectedDevice {
  name?: string;
  serial?: string;
  state?: string;
  device?: string;
  description?: string;
}

export const detectDevices = (kind: 'adb' | 'camera' | 'serial') =>
  client
    .get<{ success: boolean; error: string; devices: DetectedDevice[] }>(
      `/connections/detect/${kind}`,
    )
    .then((r) => r.data);
export const getDashboard = (projectId?: number) =>
  client
    .get<DashboardStats>('/dashboard', { params: { project_id: projectId } })
    .then((r) => r.data);
