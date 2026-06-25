export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-text-muted">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
