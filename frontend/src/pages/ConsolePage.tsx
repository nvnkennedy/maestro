import { Pause, Play, Terminal, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { MainLayout } from '../components/layout/MainLayout';
import { getServerLogs, type LogLine } from '../services/api';

// The console background is always dark, so use explicit light-on-dark colors
// (theme tokens like text-text-primary go near-black in light mode = invisible).
const LEVEL_COLOR: Record<string, string> = {
  error: 'text-red-400',
  critical: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-sky-400',
  debug: 'text-slate-400',
};

/** In-app server console — polls the backend log buffer so you can watch
 *  activity and errors without the external cmd window. */
export function ConsolePage() {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [paused, setPaused] = useState(false);
  const [autoscroll, setAutoscroll] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    let active = true;
    const poll = async () => {
      if (pausedRef.current) return;
      try {
        const data = await getServerLogs(500);
        if (active) setLines(data);
      } catch {
        /* ignore transient polling errors */
      }
    };
    void poll();
    const id = setInterval(poll, 1500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (autoscroll) endRef.current?.scrollIntoView({ block: 'end' });
  }, [lines, autoscroll]);

  return (
    <MainLayout
      title="Console"
      subtitle="Live server log — watch activity & errors without the external window"
      icon={<Terminal size={18} />}
      iconClass="bg-slate-500/15 text-slate-300"
    >
      <div className="flex h-[calc(100vh-180px)] flex-col">
        <div className="mb-2 flex items-center gap-2">
          <button className="btn-outline px-2.5 py-1 text-xs" onClick={() => setPaused((p) => !p)}>
            {paused ? (
              <>
                <Play size={13} /> Resume
              </>
            ) : (
              <>
                <Pause size={13} /> Pause
              </>
            )}
          </button>
          <button className="btn-ghost px-2.5 py-1 text-xs" onClick={() => setLines([])}>
            <Trash2 size={13} /> Clear view
          </button>
          <label className="ml-auto flex items-center gap-1.5 text-xs text-text-secondary">
            <input
              type="checkbox"
              className="accent-primary"
              checked={autoscroll}
              onChange={(e) => setAutoscroll(e.target.checked)}
            />
            Auto-scroll
          </label>
        </div>
        <div className="flex-1 overflow-auto rounded-xl border border-border bg-zinc-950 p-3 font-mono text-xs leading-relaxed">
          {lines.length === 0 ? (
            <div className="text-slate-400">Waiting for log output…</div>
          ) : (
            lines.map((l, i) => (
              <div key={i} className="whitespace-pre-wrap break-words">
                <span className="text-slate-500">{l.ts.slice(11, 19)}</span>{' '}
                <span className={`font-bold uppercase ${LEVEL_COLOR[l.level] ?? 'text-slate-300'}`}>
                  {l.level.slice(0, 4).padEnd(4)}
                </span>{' '}
                {l.logger && <span className="text-slate-500">{l.logger} </span>}
                <span className="text-slate-100">{l.message}</span>
              </div>
            ))
          )}
          <div ref={endRef} />
        </div>
      </div>
    </MainLayout>
  );
}
