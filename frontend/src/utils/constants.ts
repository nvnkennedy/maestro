export const STATUS_COLORS: Record<string, string> = {
  passed: 'rgb(var(--color-success))',
  failed: 'rgb(var(--color-error))',
  error: 'rgb(var(--color-error))',
  running: 'rgb(var(--color-info))',
  paused: 'rgb(var(--color-warning))',
  stopped: 'rgb(var(--color-warning))',
  queued: 'rgb(var(--color-text-muted))',
  skipped: 'rgb(var(--color-text-muted))',
  pending: 'rgb(var(--color-text-muted))',
};

export const STATUS_BADGES: Record<string, string> = {
  passed: 'bg-success/15 text-success',
  failed: 'bg-error/15 text-error',
  error: 'bg-error/15 text-error',
  running: 'bg-info/15 text-info animate-pulse',
  paused: 'bg-warning/15 text-warning',
  stopped: 'bg-warning/15 text-warning',
  queued: 'bg-surface-2 text-text-muted',
  skipped: 'bg-surface-2 text-text-muted',
  pending: 'bg-surface-2 text-text-muted',
};

/** Standard QA suite categories shown in the Test Designer. */
export const STANDARD_SUITES = [
  'Smoke Tests',
  'Sanity Tests',
  'Regression',
  'Retest',
  'Bug Verification',
] as const;

export const TEST_TYPES = [
  'ssh',
  'adb',
  'power',
  'etfw',
  'dlt',
  'camera',
  'serial',
  'system',
  'ignition',
] as const;

export const CONFIG_TYPES = [
  'ssh',
  'adb',
  'power',
  'etfw',
  'dlt',
  'camera',
  'serial',
] as const;

export const EXECUTION_MODES = [
  { value: 'serial', label: 'Serial' },
  { value: 'parallel', label: 'Parallel' },
  { value: 'step', label: 'Step-by-step' },
] as const;
