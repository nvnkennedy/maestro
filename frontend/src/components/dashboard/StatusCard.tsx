import { ReactNode } from 'react';

interface StatusCardProps {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  accent?: string;
  hint?: string;
}

export function StatusCard({ label, value, icon, accent, hint }: StatusCardProps) {
  return (
    <div className="card flex items-center gap-4 p-5 transition-transform duration-200 hover:scale-[1.02]">
      <div
        className="flex h-11 w-11 items-center justify-center rounded-xl"
        style={{ background: `${accent ?? '#2DD4BF'}22`, color: accent }}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <div className="truncate text-2xl font-bold">{value}</div>
        <div className="text-xs font-medium uppercase tracking-wide text-text-muted">
          {label}
        </div>
        {hint && <div className="mt-0.5 truncate text-xs text-text-secondary">{hint}</div>}
      </div>
    </div>
  );
}
