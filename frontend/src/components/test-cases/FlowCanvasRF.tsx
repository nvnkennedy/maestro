/**
 * React Flow (@xyflow/react) test designer.
 *
 * A drop-in alternative to {@link FlowCanvas} with the SAME props, so the
 * executor model is untouched: nodes carry the existing `_uid`/`_pos`, edges are
 * derived from run order (spine) plus `_branch` (Yes/No), and dragging a node
 * re-derives the run order via {@link orderByPosition}. Branch editing stays in
 * the existing modal (the node's branch button calls `onBranch`).
 */
import { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { GitBranch, Pencil, Plus, Trash2, Workflow } from 'lucide-react';
import type { TestStep } from '../../types/domain';
import { branchOf, orderByPosition, posOf, uidOf } from '../../utils/flow';
import { ActionChip } from '../common/ActionChip';

const NODE_W = 230;
const COL_X = 40;
const ROW_GAP = 140;
const TOP_Y = 30;

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
const NEEDS_TARGET = new Set(['ssh', 'adb']);
const missingTarget = (s: TestStep) =>
  NEEDS_TARGET.has(s.action.split('.')[0] ?? '') && s.parameters?.device_config_id == null;

const nodeId = (step: TestStep, index: number) => uidOf(step) || `idx-${index}`;
const autoPos = (index: number) => ({ x: COL_X, y: TOP_Y + index * ROW_GAP });

interface FlowCanvasProps {
  steps: TestStep[];
  onChange: (steps: TestStep[]) => void;
  onEdit: (index: number) => void;
  onBranch: (index: number) => void;
  onAdd: () => void;
}

type StepNodeData = {
  step: TestStep;
  index: number;
  onEdit: (index: number) => void;
  onBranch: (index: number) => void;
  onDelete: (index: number) => void;
};

function StepNode({ data, selected }: NodeProps<Node<StepNodeData>>) {
  const { step, index, onEdit, onBranch, onDelete } = data;
  const label = String(step.parameters?._label ?? '') || step.action;
  const hasBranch = branchOf(step) != null;
  return (
    <div
      className={`group relative rounded-xl border bg-surface shadow-sm transition-shadow ${
        selected ? 'border-primary ring-2 ring-primary/50' : 'border-border hover:border-primary/50'
      }`}
      style={{ width: NODE_W }}
    >
      <Handle type="target" position={Position.Top} className="!h-2 !w-2 !border-2 !border-primary !bg-background" />
      {hasBranch && (
        <span className="absolute -top-2 left-2 rounded-md bg-emerald-600 px-1.5 text-[9px] font-bold text-white">
          BRANCH
        </span>
      )}
      <div className="flex items-center gap-2.5 px-3 py-2" onDoubleClick={() => onEdit(index)}>
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
            {missingTarget(step) && (
              <span
                className="rounded border border-amber-500/60 bg-amber-500/15 px-1 text-[10px] font-bold text-amber-600"
                title="No device target bound — open the step to pick one"
              >
                ⚠ no target
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <button
            className="rounded p-1 hover:bg-surface-2"
            title="Edit step"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(index);
            }}
          >
            <Pencil size={12} />
          </button>
          <button
            className="rounded p-1 hover:bg-surface-2"
            title="Yes/No branch"
            onClick={(e) => {
              e.stopPropagation();
              onBranch(index);
            }}
          >
            <GitBranch size={12} className="text-emerald-400" />
          </button>
          <button
            className="rounded p-1 hover:bg-surface-2"
            title="Delete step"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(index);
            }}
          >
            <Trash2 size={12} className="text-red-400" />
          </button>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!h-2 !w-2 !border-2 !border-primary !bg-background" />
    </div>
  );
}

const nodeTypes = { maestro: StepNode };

function InnerCanvas({ steps, onChange, onEdit, onBranch, onAdd }: FlowCanvasProps) {
  // Stable callback wrappers so node `data` identity doesn't churn every render
  // (which would otherwise re-seed nodes in a loop).
  const cbRef = useRef({ onEdit, onBranch, onDelete: (i: number) => onChange(steps.filter((_, k) => k !== i)) });
  cbRef.current = { onEdit, onBranch, onDelete: (i: number) => onChange(steps.filter((_, k) => k !== i)) };
  const stable = useMemo(
    () => ({
      onEdit: (i: number) => cbRef.current.onEdit(i),
      onBranch: (i: number) => cbRef.current.onBranch(i),
      onDelete: (i: number) => cbRef.current.onDelete(i),
    }),
    [],
  );

  const buildNodes = useCallback(
    (): Node<StepNodeData>[] =>
      steps.map((step, index) => ({
        id: nodeId(step, index),
        type: 'maestro',
        position: posOf(step) ?? autoPos(index),
        data: { step, index, ...stable },
      })),
    [steps, stable],
  );

  const buildEdges = useCallback((): Edge[] => {
    const out: Edge[] = [];
    for (let i = 0; i < steps.length - 1; i += 1) {
      out.push({
        id: `spine-${i}`,
        source: nodeId(steps[i], i),
        target: nodeId(steps[i + 1], i + 1),
        type: 'smoothstep',
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#64748b' },
      });
    }
    const indexByUid = new Map<string, number>();
    steps.forEach((s, i) => {
      const u = uidOf(s);
      if (u) indexByUid.set(u, i);
    });
    steps.forEach((step, i) => {
      const branch = branchOf(step);
      if (!branch) return;
      const link = (target: string | null | undefined, kind: 'yes' | 'no') => {
        if (!target || !indexByUid.has(target)) return;
        const ti = indexByUid.get(target)!;
        const color = kind === 'yes' ? '#10B981' : '#F59E0B';
        out.push({
          id: `${kind}-${i}`,
          source: nodeId(step, i),
          target: nodeId(steps[ti], ti),
          label: kind === 'yes' ? 'match' : 'else',
          type: 'smoothstep',
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color },
          style: { stroke: color },
          labelStyle: { fill: color, fontWeight: 700 },
        });
      };
      link(branch.yes, 'yes');
      link(branch.no, 'no');
    });
    return out;
  }, [steps]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<StepNodeData>>(buildNodes());
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(buildEdges());

  // Re-seed when the underlying steps change (add/remove/edit/reorder).
  useEffect(() => setNodes(buildNodes()), [buildNodes, setNodes]);
  useEffect(() => setEdges(buildEdges()), [buildEdges, setEdges]);

  const onNodeDragStop = useCallback(
    (_: MouseEvent | TouchEvent, node: Node<StepNodeData>) => {
      const moved = steps.map((s, i) =>
        nodeId(s, i) === node.id
          ? {
              ...s,
              parameters: {
                ...s.parameters,
                _pos: { x: Math.round(node.position.x), y: Math.round(node.position.y) },
              },
            }
          : s,
      );
      onChange(orderByPosition(moved));
    },
    [steps, onChange],
  );

  const tidy = useCallback(
    () => onChange(steps.map((s, i) => ({ ...s, parameters: { ...s.parameters, _pos: autoPos(i) } }))),
    [steps, onChange],
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center gap-2">
        <button className="btn-outline px-2.5 py-1 text-xs" onClick={onAdd}>
          <Plus size={13} /> Add node
        </button>
        <button className="btn-ghost px-2.5 py-1 text-xs" onClick={tidy} title="Auto-arrange top-down">
          <Workflow size={13} /> Tidy
        </button>
        <span className="ml-auto hidden text-[11px] text-text-muted md:inline">
          Drag to reorder · double-click to edit · hover a node for edit/branch/delete ·{' '}
          <GitBranch size={11} className="inline" /> Yes/No branch
        </span>
      </div>
      <div className="min-h-[440px] flex-1 overflow-hidden rounded-2xl border border-border">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={onNodeDragStop}
          onNodeDoubleClick={(_, n) => stable.onEdit((n.data as StepNodeData).index)}
          nodeTypes={nodeTypes}
          nodesConnectable={false}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#94a3b8" />
          <MiniMap pannable zoomable className="!bg-surface-2" />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}

export function FlowCanvasRF(props: FlowCanvasProps) {
  return (
    <ReactFlowProvider>
      <InnerCanvas {...props} />
    </ReactFlowProvider>
  );
}
