/** Colored chip identifying a step's adapter/action (ssh = orange, adb = green...). */

const CHIP_STYLES: Record<string, string> = {
  ssh: 'bg-orange-500/15 text-orange-500 dark:text-orange-400 border-orange-500/30',
  adb: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
  power: 'bg-red-500/15 text-red-500 dark:text-red-400 border-red-500/30',
  camera: 'bg-purple-500/15 text-purple-500 dark:text-purple-400 border-purple-500/30',
  dlt: 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border-cyan-500/30',
  serial: 'bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/30',
  etfw: 'bg-pink-500/15 text-pink-500 dark:text-pink-400 border-pink-500/30',
  system: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30',
};

const FALLBACK = 'bg-indigo-500/15 text-indigo-500 dark:text-indigo-400 border-indigo-500/30';

export function adapterOf(action: string): string {
  return action.split('.')[0] ?? '';
}

export function ActionChip({ action, full }: { action: string; full?: boolean }) {
  const [adapter, name] = action.split('.');
  const style = CHIP_STYLES[adapter] ?? FALLBACK;
  const text = full ? action : `${adapter}_${(name ?? '').replace(/_/g, ' ').split(' ')[0]}`;
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold ${style}`}
      title={action}
    >
      {text}
    </span>
  );
}
