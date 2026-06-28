/**
 * Tiny bridge so non-React code (e.g. the axios error interceptor) can raise a
 * toast. The ToastProvider registers its push function on mount.
 */
export type NotifyKind = 'success' | 'error' | 'info';
type Notifier = (kind: NotifyKind, message: string) => void;

let handler: Notifier | null = null;

export function registerNotifier(fn: Notifier | null): void {
  handler = fn;
}

export function notify(kind: NotifyKind, message: string): void {
  handler?.(kind, message);
}
