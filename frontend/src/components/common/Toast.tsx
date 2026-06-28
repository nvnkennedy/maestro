import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { CheckCircle2, AlertCircle, Info } from 'lucide-react';
import { registerNotifier } from '../../services/notify';

type ToastKind = 'success' | 'error' | 'info';
interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

const ToastContext = createContext<(kind: ToastKind, message: string) => void>(() => {});

export const useToast = () => useContext(ToastContext);

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info };
const STYLES: Record<ToastKind, string> = {
  success: 'border-success/40 text-success',
  error: 'border-error/40 text-error',
  info: 'border-info/40 text-info',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const lastRef = useRef<{ message: string; at: number }>({ message: '', at: 0 });

  const push = useCallback((kind: ToastKind, message: string) => {
    // Drop a repeat of the same message within ~1.2s (e.g. a global interceptor
    // and a local catch both reporting one failure).
    const now = Date.now();
    if (message === lastRef.current.message && now - lastRef.current.at < 1200) return;
    lastRef.current = { message, at: now };
    const id = now + Math.random();
    setToasts((current) => [...current, { id, kind, message }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 4000);
  }, []);

  // Let non-React code (axios interceptor, error boundary) raise toasts too.
  useEffect(() => {
    registerNotifier(push);
    return () => registerNotifier(null);
  }, [push]);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.kind];
          return (
            <div
              key={toast.id}
              className={`card flex items-center gap-2 border px-4 py-3 text-sm shadow-lg ${STYLES[toast.kind]}`}
            >
              <Icon size={16} />
              <span className="text-text-primary">{toast.message}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
