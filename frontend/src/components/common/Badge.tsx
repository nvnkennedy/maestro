import { STATUS_BADGES } from '../../utils/constants';

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_BADGES[status] ?? 'bg-surface-2 text-text-muted';
  return <span className={`badge ${cls}`}>{status}</span>;
}
