export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso.endsWith('Z') ? iso : `${iso}Z`).toLocaleString();
  } catch {
    return iso;
  }
}

export function truncate(text: string, limit = 120): string {
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}
