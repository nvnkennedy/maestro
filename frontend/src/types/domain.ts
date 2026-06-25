export interface Project {
  id: number;
  name: string;
  description: string;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
  test_case_count: number;
}

export interface TestStep {
  id?: number;
  step_number: number;
  action: string;
  parameters: Record<string, unknown>;
  timeout_seconds: number;
  retry_count: number;
}

export interface TestCase {
  id: number;
  project_id: number;
  name: string;
  description: string;
  test_type: string;
  scenario: string;
  created_by: string;
  modified_by?: string;
  origin?: string;
  default_target_id?: number | null;
  created_at: string | null;
  updated_at: string | null;
  step_count: number;
  steps?: TestStep[];
}

export type ExecutionStatus =
  | 'queued'
  | 'running'
  | 'paused'
  | 'passed'
  | 'failed'
  | 'error'
  | 'stopped';

export interface ExecutionStep {
  id: number;
  execution_id: number;
  step_number: number;
  action: string;
  label: string;
  status: string;
  actual_output: string;
  error_message: string;
  attempts: number;
  duration_seconds: number | null;
}

export interface Execution {
  id: number;
  test_case_id: number;
  test_case_name?: string;
  status: ExecutionStatus;
  execution_mode: string;
  triggered_by: string;
  suite_run_id?: string;
  target_id?: number | null;
  target_label?: string;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  steps?: ExecutionStep[];
  report_available?: boolean;
  suite?: string;
  scenario?: string;
}

export interface ReportSummary {
  execution: Execution;
  test_case_name: string;
  steps: ExecutionStep[];
  artifacts: {
    id: number;
    artifact_type: string;
    file_path: string;
    step_number: number | null;
  }[];
  totals: { passed: number; failed: number; skipped: number };
}

export interface DeviceConfig {
  id: number;
  project_id: number;
  config_type: string;
  label: string;
  settings: Record<string, unknown>;
  is_active: boolean;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  credential_keys: string[];
}

export interface Schedule {
  id: number;
  test_case_id: number;
  test_case_name?: string;
  suite: string;
  scenario: string;
  project_id: number | null;
  target_label: string;
  schedule_type: 'once' | 'daily' | 'weekly' | 'cron';
  run_at: string | null;
  time_of_day: string;
  weekday: number | null;
  cron_expression: string;
  description: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface SchedulePayload {
  test_case_id?: number;
  suite?: string;
  scenario?: string;
  project_id?: number;
  schedule_type: 'once' | 'daily' | 'weekly';
  run_at?: string;
  time_of_day?: string;
  weekday?: number;
  start_at?: string;
  end_at?: string;
}

export interface Plugin {
  name: string;
  display_name?: string;
  version?: string;
  type?: string;
  description?: string;
  actions: string[];
  enabled: boolean;
  powered_by?: { tool: string; module?: string } | null;
  tool_version?: string | null;
  capability_groups?: Record<string, string[]> | null;
  dependencies?: string[];
}

export interface StepTemplate {
  label: string;
  action: string;
  parameters: Record<string, unknown>;
  timeout_seconds: number;
  description?: string;
  category?: string;
  tags?: string[];
}

export type TemplateLibrary = Record<string, StepTemplate[]>;

export interface DashboardStats {
  total_executions: number;
  passed: number;
  failed: number;
  running: number;
  pass_rate: number;
  status_counts: Record<string, number>;
  executions_by_type: Record<string, number>;
  trend: {
    execution_id: number;
    status: string;
    duration_seconds: number | null;
    started_at: string | null;
  }[];
  last_execution: Execution | null;
  next_scheduled: Schedule | null;
  test_case_count: number;
  project_count: number;
}

export interface WsEvent {
  type: string;
  execution_id?: number;
  execution?: Execution;
  step_number?: number;
  action?: string;
  label?: string;
  status?: string;
  output?: string;
  error?: string;
  message?: string;
  level?: string;
  timestamp?: string;
  duration_seconds?: number;
  // suite run events
  suite_run_id?: string;
  current_index?: number;
  total?: number;
  test_case_id?: number;
  test_case_name?: string;
  completed?: number;
  cancelled?: boolean;
  passed?: number;
  failed?: number;
  test_cases?: { id: number; name: string }[];
}

export interface SuiteRun {
  suite_run_id: string;
  label: string;
  total: number;
  mode: string;
}

export interface AdapterHealth {
  success: boolean;
  output: string;
  error: string;
}
