import {
  ClipboardPaste,
  Copy,
  GitBranch,
  Maximize2,
  Minus,
  Pencil,
  Plus,
  Scissors,
  Trash2,
  Workflow,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { TestStep } from '../../types/domain';
import { branchOf, orderByPosition, posOf, type Pos, uidOf } from '../../utils/flow';
import { ActionChip } from '../common/ActionChip';

const NODE_W = 200;
const NODE_H = 78;
const COL_X = 60;
const ROW_GAP = 124;
const TOP_Y = 70;

const ADAPTER_HUE: Record<string, string> = {
  ssh: 'bg-orange-500',
  adb: 'bg-emerald-500',
  power: 'bg-red-500',
  camera: 'bg-purple-500',
  dlt: 'bg-cyan-500',
  serial: 'bg-yellow-500',
  etfw: 'bg-pink-500',
  system: 'bg-sky-500',
};
const hueOf = (action: string) => ADAPTER_HUE[action.split('.')[0] ?? ''] ?? 'bg-indigo-500';

// Adapters that need a bound device target to connect (and send credentials).
const NEEDS_TARGET = new Set(['ssh', 'adb']);
const missingTarget = (step: TestStep) =>
  NEEDS_TARGET.has(step.action.split('.')[0] ?? '') &&
  step.parameters?.device_config_id == null;

interface FlowCanvasProps {
  steps: TestStep[];
  onChange: (steps: TestStep[]) => void;
  onEdit: (index: number) => void;
  onBranch: (index: number) => void;
  onAdd: () => void;
}

/** Lay every node out in a tidy top-down column (used as a fallback + Tidy). */
function autoPos(index: number): Pos {
  return { x: COL_X, y: TOP_Y + index * ROW_GAP };
}

export function FlowCanvas({ steps, onChange, onEdit, onBranch, onAdd }: FlowCanvasProps) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const zoomRef = useRef(1);
  zoomRef.current = zoom;
  // Live positions while dragging (committed to the model on pointer-up).
  const [drag, setDrag] = useState<{ index: number; pos: Pos } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [clip, setClip] = useState<TestStep | null>(null);

  const duplicateStep = (s: TestStep): TestStep => {
    const params = { ...s.parameters };
    delete params._uid; // renumber/assignUids assigns a fresh id
    delete params._branch; // a copy shouldn't inherit Yes/No routing
    const p = posOf(s);
    if (p) params._pos = { x: p.x + 36, y: p.y + 36 };
    return { ...s, id: undefined, parameters: params };
  };

  const selectedIndex = () => steps.findIndex((s) => uidOf(s) === selected);

  const copySelected = () => {
    const idx = selectedIndex();
    if (idx >= 0) setClip(steps[idx]);
  };
  const cutSelected = () => {
    const idx = selectedIndex();
    if (idx < 0) return;
    setClip(steps[idx]);
    onChange(steps.filter((_, i) => i !== idx));
    setSelected(null);
  };
  const pasteClip = () => {
    if (!clip) return;
    const idx = selectedIndex();
    const copy = duplicateStep(clip);
    const next = [...steps];
    // Paste right after the selected node, else append.
    next.splice(idx >= 0 ? idx + 1 : next.length, 0, copy);
    onChange(next);
    setSelected(uidOf(copy));
  };
  const duplicateAt = (idx: number) => {
    const next = [...steps];
    next.splice(idx + 1, 0, duplicateStep(steps[idx]));
    onChange(next);
  };

  // Keyboard shortcuts: Delete, Ctrl/Cmd + C / X / V / D on the selected node.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const idx = selectedIndex();
      const mod = e.ctrlKey || e.metaKey;
      if ((e.key === 'Delete' || e.key === 'Backspace') && idx >= 0) {
        e.preventDefault();
        onChange(steps.filter((_, i) => i !== idx));
        setSelected(null);
      } else if (mod && e.key.toLowerCase() === 'c' && idx >= 0) {
        e.preventDefault();
        copySelected();
      } else if (mod && e.key.toLowerCase() === 'x' && idx >= 0) {
        e.preventDefault();
        cutSelected();
      } else if (mod && e.key.toLowerCase() === 'v' && clip) {
        e.preventDefault();
        pasteClip();
      } else if (mod && e.key.toLowerCase() === 'd' && idx >= 0) {
        e.preventDefault();
        duplicateAt(idx);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps, selected, clip, onChange]);

  const positions = useMemo(
    () => steps.map((step, index) => posOf(step) ?? autoPos(index)),
    [steps],
  );

  const posFor = (index: number): Pos =>
    drag && drag.index === index ? drag.pos : positions[index];

  const uidToIndex = useMemo(() => {
    const map = new Map<string, number>();
    steps.forEach((step, index) => map.set(uidOf(step), index));
    return map;
  }, [steps]);

  // Bounding boxes for parallel groups, so members read as one lane.
  // Recomputed each render because it tracks live drag positions.
  const groupBoundsMap = new Map<string, number[]>();
  steps.forEach((step, index) => {
    const group = step.parameters?._parallel_group as string | undefined;
    if (group) {
      if (!groupBoundsMap.has(group)) groupBoundsMap.set(group, []);
      groupBoundsMap.get(group)!.push(index);
    }
  });
  const groupBounds = [...groupBoundsMap.entries()].map(([group, indices]) => {
    const xs = indices.map((i) => posFor(i).x);
    const ys = indices.map((i) => posFor(i).y);
    return {
      group,
      x: Math.min(...xs) - 10,
      y: Math.min(...ys) - 10,
      w: Math.max(...xs) + NODE_W - Math.min(...xs) + 20,
      h: Math.max(...ys) + NODE_H - Math.min(...ys) + 20,
    };
  });

  const startDrag = useCallback(
    (index: number, event: React.PointerEvent) => {
      event.preventDefault();
      const surface = surfaceRef.current;
      if (!surface) return;
      const rect = surface.getBoundingClientRect();
      const z = zoomRef.current || 1;
      const start = positions[index];
      // Screen → canvas coordinates (account for scroll + zoom).
      const toCanvas = (cx: number, cy: number) => ({
        x: (cx - rect.left + surface.scrollLeft) / z,
        y: (cy - rect.top + surface.scrollTop) / z,
      });
      const origin = toCanvas(event.clientX, event.clientY);
      const grabX = origin.x - start.x;
      const grabY = origin.y - start.y;
      const calc = (e: PointerEvent) => {
        const c = toCanvas(e.clientX, e.clientY);
        return { x: Math.round(Math.max(0, c.x - grabX)), y: Math.round(Math.max(0, c.y - grabY)) };
      };

      const move = (e: PointerEvent) => setDrag({ index, pos: calc(e) });
      const up = (e: PointerEvent) => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        const pos = calc(e);
        setDrag(null);
        // Commit the new position, then re-derive the run order from the
        // layout (top→bottom) so dragging a node above another makes it run
        // earlier. Parallel-group members stay contiguous (compactGroups).
        const moved = steps.map((step, i) =>
          i === index ? { ...step, parameters: { ...step.parameters, _pos: pos } } : step,
        );
        onChange(orderByPosition(moved));
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    },
    [positions, steps, onChange],
  );

  const tidy = () =>
    onChange(
      steps.map((step, index) => ({
        ...step,
        parameters: { ...step.parameters, _pos: autoPos(index) },
      })),
    );

  const deleteAt = (index: number) =>
    onChange(steps.filter((_, i) => i !== index));

  const TIMEOUTS = [10, 15, 30, 60, 120, 300, 600];
  const fmtTimeout = (s: number) => (s >= 60 ? `${Math.round(s / 60)}m` : `${s}s`);
  const cycleTimeout = (index: number) =>
    onChange(
      steps.map((step, i) => {
        if (i !== index) return step;
        const pos = TIMEOUTS.indexOf(step.timeout_seconds);
        const next = TIMEOUTS[(pos + 1) % TIMEOUTS.length];
        return { ...step, timeout_seconds: next };
      }),
    );

  // ---- edges ---------------------------------------------------------------

  type Anchor = { x: number; y: number; dir: 'up' | 'down' | 'left' | 'right' };
  const bottom = (p: Pos): Anchor => ({ x: p.x + NODE_W / 2, y: p.y + NODE_H, dir: 'down' });
  const top = (p: Pos): Anchor => ({ x: p.x + NODE_W / 2, y: p.y, dir: 'up' });
  const left = (p: Pos): Anchor => ({ x: p.x, y: p.y + NODE_H / 2, dir: 'left' });
  const right = (p: Pos): Anchor => ({ x: p.x + NODE_W, y: p.y + NODE_H / 2, dir: 'right' });

  // Pick the side of each node to leave/enter from, based on their relative
  // positions — so arrows never cut across a node or wander off randomly.
  const anchorsFor = (a: Pos, b: Pos): [Anchor, Anchor] => {
    const acx = a.x + NODE_W / 2;
    const bcx = b.x + NODE_W / 2;
    const dx = bcx - acx;
    const dy = b.y - a.y;
    if (Math.abs(dy) >= Math.abs(dx)) {
      return dy >= 0 ? [bottom(a), top(b)] : [top(a), bottom(b)];
    }
    return dx >= 0 ? [right(a), left(b)] : [left(a), right(b)];
  };

  // Cubic bezier that leaves/enters each anchor along its facing direction.
  const edgePath = (a: Anchor, b: Anchor) => {
    const off = (anchor: Anchor, span: number) => {
      const k = Math.max(30, span / 2);
      if (anchor.dir === 'down') return { x: anchor.x, y: anchor.y + k };
      if (anchor.dir === 'up') return { x: anchor.x, y: anchor.y - k };
      if (anchor.dir === 'right') return { x: anchor.x + k, y: anchor.y };
      return { x: anchor.x - k, y: anchor.y };
    };
    const span = Math.hypot(b.x - a.x, b.y - a.y);
    const c1 = off(a, span);
    const c2 = off(b, span);
    return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`;
  };

  type Edge = { id: string; d: string; kind: 'spine' | 'yes' | 'no'; label?: { x: number; y: number; text: string } };
  const edges: Edge[] = [];
  // Start anchor → first node
  if (steps.length) {
    const first = top(posFor(0));
    edges.push({
      id: 'start',
      d: edgePath({ x: first.x, y: TOP_Y - 36, dir: 'down' }, first),
      kind: 'spine',
    });
  }
  steps.forEach((step, index) => {
    const branch = branchOf(step);
    // Default sequential flow to the next node (engine falls through when no jump).
    if (index < steps.length - 1) {
      const [a, b] = anchorsFor(posFor(index), posFor(index + 1));
      edges.push({ id: `spine-${index}`, d: edgePath(a, b), kind: 'spine' });
    }
    if (branch) {
      const draw = (uid: string | null | undefined, kind: 'yes' | 'no', text: string) => {
        if (!uid) return;
        const target = uidToIndex.get(uid);
        if (target == null) return;
        const [a, b] = anchorsFor(posFor(index), posFor(target));
        edges.push({
          id: `${kind}-${index}`,
          d: edgePath(a, b),
          kind,
          label: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, text },
        });
      };
      draw(branch.yes, 'yes', 'match');
      draw(branch.no, 'no', 'else');
    }
  });

  // Size the canvas tightly around the actual nodes (no giant empty scroll).
  const canvasW = Math.max(640, ...positions.map((_p, i) => posFor(i).x + NODE_W + 60));
  const canvasH = Math.max(360, ...positions.map((_p, i) => posFor(i).y + NODE_H + 60));

  const zoomBy = (delta: number) =>
    setZoom((z) => Math.min(1.5, Math.max(0.3, Math.round((z + delta) * 100) / 100)));
  const fitToView = () => {
    const s = surfaceRef.current;
    if (!s) return;
    const z = Math.min((s.clientWidth - 24) / canvasW, (s.clientHeight - 24) / canvasH, 1);
    setZoom(Math.max(0.3, Math.round(z * 100) / 100));
    s.scrollTo({ top: 0, left: 0 });
  };

  const strokeFor = (kind: Edge['kind']) =>
    kind === 'yes' ? '#10B981' : kind === 'no' ? '#F59E0B' : '#64748b';

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center gap-2">
        <button className="btn-outline px-2.5 py-1 text-xs" onClick={onAdd}>
          <Plus size={13} /> Add node
        </button>
        <button className="btn-ghost px-2.5 py-1 text-xs" onClick={tidy} title="Auto-arrange top-down">
          <Workflow size={13} /> Tidy layout
        </button>
        <div className="flex items-center overflow-hidden rounded-lg border border-border">
          <button
            className="px-2 py-1 hover:bg-surface-2 disabled:opacity-40"
            onClick={copySelected}
            disabled={selected === null}
            title="Copy selected step (Ctrl+C)"
            aria-label="Copy step"
          >
            <Copy size={13} />
          </button>
          <button
            className="border-l border-border px-2 py-1 hover:bg-surface-2 disabled:opacity-40"
            onClick={cutSelected}
            disabled={selected === null}
            title="Cut selected step (Ctrl+X)"
            aria-label="Cut step"
          >
            <Scissors size={13} />
          </button>
          <button
            className="border-l border-border px-2 py-1 hover:bg-surface-2 disabled:opacity-40"
            onClick={pasteClip}
            disabled={!clip}
            title="Paste step (Ctrl+V)"
            aria-label="Paste step"
          >
            <ClipboardPaste size={13} />
          </button>
        </div>
        <div className="flex items-center overflow-hidden rounded-lg border border-border">
          <button className="px-2 py-1 hover:bg-surface-2" onClick={() => zoomBy(-0.1)} title="Zoom out" aria-label="Zoom out">
            <Minus size={13} />
          </button>
          <span className="w-12 text-center text-[11px] tabular-nums text-text-muted">
            {Math.round(zoom * 100)}%
          </span>
          <button className="px-2 py-1 hover:bg-surface-2" onClick={() => zoomBy(0.1)} title="Zoom in" aria-label="Zoom in">
            <Plus size={13} />
          </button>
          <button className="border-l border-border px-2 py-1 hover:bg-surface-2" onClick={fitToView} title="Fit to screen" aria-label="Fit to screen">
            <Maximize2 size={13} />
          </button>
        </div>
        <span className="ml-auto hidden text-[11px] text-text-muted md:inline">
          Drag up/down to reorder run order · click to select (Del / Ctrl+C·V·D) · double-click to edit ·{' '}
          <GitBranch size={11} className="inline" /> Yes/No branch
        </span>
      </div>
      <div
        ref={surfaceRef}
        className="relative flex-1 overflow-auto rounded-2xl border border-border bg-[radial-gradient(circle,_rgba(148,163,184,0.18)_1px,_transparent_1px)] [background-size:22px_22px]"
      >
        <div style={{ width: canvasW * zoom, height: canvasH * zoom }}>
          <div
            className="relative origin-top-left"
            style={{ width: canvasW, height: canvasH, transform: `scale(${zoom})` }}
          >
          <svg
            className="pointer-events-none absolute inset-0"
            width={canvasW}
            height={canvasH}
          >
            <defs>
              {(['spine', 'yes', 'no'] as const).map((kind) => (
                <marker
                  key={kind}
                  id={`arrow-${kind}`}
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill={strokeFor(kind)} />
                </marker>
              ))}
            </defs>
            {groupBounds.map((b) => (
              <rect
                key={`g-${b.group}`}
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                rx={16}
                fill="rgba(139,92,246,0.06)"
                stroke="rgba(139,92,246,0.4)"
                strokeDasharray="6 4"
              />
            ))}
            {edges.map((edge) => (
              <path
                key={edge.id}
                d={edge.d}
                fill="none"
                stroke={strokeFor(edge.kind)}
                strokeWidth={edge.kind === 'spine' ? 1.6 : 2}
                strokeDasharray={edge.kind === 'spine' ? undefined : '5 4'}
                markerEnd={`url(#arrow-${edge.kind})`}
              />
            ))}
            {edges
              .filter((e) => e.label)
              .map((edge) => (
                <g key={`lbl-${edge.id}`}>
                  <rect
                    x={edge.label!.x - 19}
                    y={edge.label!.y - 9}
                    width={38}
                    height={18}
                    rx={9}
                    fill={edge.kind === 'yes' ? '#064e3b' : '#451a03'}
                  />
                  <text
                    x={edge.label!.x}
                    y={edge.label!.y + 4}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="700"
                    fill={strokeFor(edge.kind)}
                  >
                    {edge.label!.text}
                  </text>
                </g>
              ))}
          </svg>

          {/* Start anchor */}
          {steps.length > 0 && (
            <div
              className="absolute -translate-x-1/2 rounded-full border border-emerald-500/50 bg-emerald-500/15 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-emerald-400"
              style={{ left: posFor(0).x + NODE_W / 2, top: TOP_Y - 54 }}
            >
              Start
            </div>
          )}

          {steps.map((step, index) => {
            const pos = posFor(index);
            const branch = branchOf(step);
            const label = String(step.parameters?._label ?? '') || step.action;
            const isDragging = drag?.index === index;
            const isSelected = selected === uidOf(step);
            return (
              <div
                key={uidOf(step) || index}
                className={`group absolute select-none rounded-xl border bg-surface shadow-sm transition-shadow ${
                  isDragging
                    ? 'z-20 border-primary shadow-xl ring-2 ring-primary/30'
                    : isSelected
                      ? 'z-20 border-primary ring-2 ring-primary/50'
                      : 'z-10 border-border hover:border-primary/50 hover:shadow-md'
                }`}
                style={{ left: pos.x, top: pos.y, width: NODE_W, height: NODE_H }}
              >
                <div
                  className="flex h-full cursor-grab items-center gap-2.5 px-3 active:cursor-grabbing"
                  onPointerDown={(e) => startDrag(index, e)}
                  onClick={() => setSelected(uidOf(step))}
                  onDoubleClick={() => onEdit(index)}
                >
                  <span
                    className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[11px] font-bold text-white ${hueOf(
                      step.action,
                    )}`}
                  >
                    {step.step_number}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="line-clamp-2 break-words text-sm font-semibold leading-tight" title={label}>
                      {label}
                    </div>
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <ActionChip action={step.action} />
                      <button
                        className="rounded-md border border-border bg-background px-1.5 py-px text-[10px] font-semibold text-amber-400 hover:border-amber-500/50"
                        onClick={() => cycleTimeout(index)}
                        onPointerDown={(e) => e.stopPropagation()}
                        title="Click to change this step's timeout"
                      >
                        ⏱ {fmtTimeout(step.timeout_seconds)}
                      </button>
                      {missingTarget(step) && (
                        <button
                          className="rounded-md border border-amber-500/60 bg-amber-500/15 px-1 py-px text-[10px] font-bold text-amber-600"
                          onClick={() => onEdit(index)}
                          onPointerDown={(e) => e.stopPropagation()}
                          title="No device target bound — click to pick one (needed to connect & send credentials)"
                        >
                          ⚠ no target
                        </button>
                      )}
                      {Array.isArray(step.parameters?._attachments) &&
                        (step.parameters._attachments as unknown[]).length > 0 && (
                          <span
                            className="rounded-md border border-cyan-500/40 bg-cyan-500/10 px-1 py-px text-[10px] font-semibold text-cyan-500"
                            title="Planned attachments"
                          >
                            📎 {(step.parameters._attachments as unknown[]).length}
                          </span>
                        )}
                    </div>
                  </div>
                </div>
                {branch && (
                  <span className="absolute -top-2 left-2 rounded-md bg-emerald-600 px-1.5 text-[9px] font-bold text-white">
                    BRANCH
                  </span>
                )}
                <div className="absolute -right-1 -top-2 flex gap-0.5 opacity-70 transition-opacity group-hover:opacity-100">
                  <button
                    className="rounded-md border border-border bg-surface p-1 text-sky-400 shadow-sm hover:bg-surface-2"
                    onClick={() => onEdit(index)}
                    onPointerDown={(e) => e.stopPropagation()}
                    title="Edit step"
                  >
                    <Pencil size={12} />
                  </button>
                  <button
                    className="rounded-md border border-border bg-surface p-1 text-indigo-400 shadow-sm hover:bg-surface-2"
                    onClick={() => duplicateAt(index)}
                    onPointerDown={(e) => e.stopPropagation()}
                    title="Duplicate step (or Ctrl+C / Ctrl+V)"
                  >
                    <Copy size={12} />
                  </button>
                  <button
                    className="rounded-md border border-border bg-surface p-1 text-emerald-400 shadow-sm hover:bg-surface-2"
                    onClick={() => onBranch(index)}
                    onPointerDown={(e) => e.stopPropagation()}
                    title="Add / edit Yes-No branch"
                  >
                    <GitBranch size={12} />
                  </button>
                  <button
                    className="rounded-md border border-border bg-surface p-1 text-error shadow-sm hover:bg-surface-2"
                    onClick={() => deleteAt(index)}
                    onPointerDown={(e) => e.stopPropagation()}
                    title="Delete step"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            );
          })}

          {steps.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center text-sm text-text-muted">
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-3xl text-primary">
                ⤓
              </span>
              <div>
                Click <b className="text-primary">＋ on a palette action</b> or{' '}
                <b className="text-primary">Add node</b> to start your flow
              </div>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
