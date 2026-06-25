import {
  closestCenter,
  CollisionDetection,
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  MeasuringStrategy,
  pointerWithin,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  FolderCog,
  GripVertical,
  Link2,
  Lock,
  Pause,
  Pencil,
  Play,
  Plus,
  Save,
  Search,
  Split,
  Trash2,
  Unlink,
  Upload,
} from 'lucide-react';
import { Fragment, ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../../context/ProjectContext';
import { useApi } from '../../hooks/useApi';
import {
  cloneTestCase,
  createTestCase,
  deleteTestCases,
  exportTestCase,
  getTemplates,
  getTestCase,
  importTestCase,
  listConfigs,
  listTestCases,
  moveTestCases,
  renameGroup,
  startExecution,
  startSuiteRun,
  updateTestCase,
} from '../../services/api';
import type { StepTemplate, TestStep } from '../../types/domain';
import { STANDARD_SUITES } from '../../utils/constants';
import { ActionChip } from '../common/ActionChip';
import { Modal } from '../common/Modal';
import { Spinner } from '../common/Spinner';
import { useToast } from '../common/Toast';
import { StepEditModal } from './StepEditModal';
import { BranchEditor } from './BranchEditor';
import { FlowCanvas } from './FlowCanvas';
import { FlowCanvasRF } from './FlowCanvasRF';
import { assignUids, compactGroups, resolveBranches } from '../../utils/flow';
import { setNavGuard } from '../../utils/navGuard';

interface Draft {
  name: string;
  suite: string;
  scenario: string;
  description: string;
  steps: TestStep[];
  createdBy?: string;
  modifiedBy?: string;
  origin?: string;
  defaultTargetId?: number | null;
}

interface Row {
  kind: 'single' | 'lane';
  indices: number[];
  group?: string;
}

type SortableHook = ReturnType<typeof useSortable>;
type HandleProps = {
  attributes: SortableHook['attributes'];
  listeners: SortableHook['listeners'];
};

const GROUP_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];

/** Per-adapter accent colour for the step's number badge. */
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

/**
 * Collision detection in two clean modes:
 *  - Reordering (active = 'row'): snap to the nearest step card only.
 *  - Adding from the palette: prefer the card under the pointer, otherwise the
 *    whole-canvas drop target. The canvas covers all empty space, so a drop
 *    anywhere below the last step reliably appends — no dead zones.
 */
const collisionStrategy: CollisionDetection = (args) => {
  const kind = args.active.data.current?.type;
  if (kind === 'row') {
    const rows = args.droppableContainers.filter((c) => String(c.id).startsWith('row|'));
    return closestCenter({ ...args, droppableContainers: rows });
  }
  const within = pointerWithin(args);
  const overRow = within.filter((c) => String(c.id).startsWith('row|'));
  if (overRow.length) return overRow;
  const overCanvas = within.filter((c) => c.id === 'canvas');
  if (overCanvas.length) return overCanvas;
  return closestCenter(args);
};

function buildRows(steps: TestStep[]): Row[] {
  const rows: Row[] = [];
  let i = 0;
  while (i < steps.length) {
    const group = steps[i].parameters?._parallel_group;
    if (group) {
      let j = i;
      while (j < steps.length && steps[j].parameters?._parallel_group === group) j++;
      rows.push({
        kind: 'lane',
        indices: Array.from({ length: j - i }, (_, k) => i + k),
        group: String(group),
      });
      i = j;
    } else {
      rows.push({ kind: 'single', indices: [i] });
      i++;
    }
  }
  return rows;
}

/** Drop a lane down to a single step when only one member remains. */
function normalize(steps: TestStep[]): TestStep[] {
  const rows = buildRows(steps);
  const result = [...steps];
  rows.forEach((row) => {
    if (row.kind === 'lane' && row.indices.length === 1) {
      result[row.indices[0]] = stripGroup(result[row.indices[0]]);
    }
  });
  return result;
}

function stripGroup(step: TestStep): TestStep {
  const params = { ...step.parameters };
  delete params._parallel_group;
  return { ...step, parameters: params };
}

function nextGroup(steps: TestStep[]): string {
  const used = new Set(
    steps
      .map((s) => s.parameters?._parallel_group)
      .filter(Boolean)
      .map(String),
  );
  return GROUP_LETTERS.find((letter) => !used.has(letter)) ?? 'A';
}

// ---- palette item (draggable source) ------------------------------------------

function PaletteItem({
  id,
  template,
  onAppend,
}: {
  id: string;
  template: StepTemplate;
  onAppend: () => void;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: { type: 'palette', template },
  });
  return (
    <div
      ref={setNodeRef}
      className={`group/p flex cursor-grab touch-none items-center gap-2 rounded-lg border bg-background px-2.5 py-2 text-left transition-all active:cursor-grabbing ${
        isDragging
          ? 'opacity-30'
          : 'border-border hover:-translate-y-px hover:border-primary/50 hover:shadow-sm'
      }`}
      {...attributes}
      {...listeners}
      title={template.description || 'Drag onto the canvas, or click + to append'}
    >
      <ActionChip action={template.action} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-xs font-medium">{template.label}</span>
        {template.description && (
          <span className="block truncate text-[11px] leading-tight text-text-muted">
            {template.description}
          </span>
        )}
      </span>
      <button
        className="btn-ghost shrink-0 rounded-md p-1 text-primary opacity-0 transition-opacity group-hover/p:opacity-100"
        onClick={(e) => {
          e.stopPropagation();
          onAppend();
        }}
        onPointerDown={(e) => e.stopPropagation()}
        aria-label={`Append ${template.label}`}
      >
        <Plus size={13} />
      </button>
    </div>
  );
}

// ---- the step "box" ------------------------------------------------------------

function StepBox({
  step,
  number,
  inLane,
  canMergeUp,
  canMoveLeft,
  canMoveRight,
  handle,
  dragging,
  onEdit,
  onDelete,
  onDuplicate,
  onTogglePause,
  onMergeUp,
  onUnlink,
  onMoveInLane,
}: {
  step: TestStep;
  number: number;
  inLane: boolean;
  canMergeUp?: boolean;
  canMoveLeft?: boolean;
  canMoveRight?: boolean;
  handle?: HandleProps;
  dragging?: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onTogglePause: () => void;
  onMergeUp: () => void;
  onUnlink: () => void;
  onMoveInLane?: (dir: -1 | 1) => void;
}) {
  const label = String(step.parameters?._label ?? '') || step.action;
  const pause = Boolean(step.parameters?._pause_before);
  const alwaysRun = Boolean(step.parameters?._always_run);
  return (
    <div
      className={`group relative flex min-w-0 items-center gap-3 rounded-xl border bg-surface px-3.5 py-3 shadow-sm transition-all ${
        inLane ? 'flex-1' : 'w-full'
      } ${
        dragging
          ? 'border-primary shadow-lg ring-2 ring-primary/30'
          : pause
            ? 'border-amber-500/50 hover:border-amber-500/70'
            : 'border-border hover:border-primary/50 hover:shadow-md'
      }`}
    >
      {handle ? (
        <button
          className="-ml-1 cursor-grab touch-none rounded-md p-1 text-text-muted hover:bg-surface-2 hover:text-text-primary active:cursor-grabbing"
          {...handle.attributes}
          {...handle.listeners}
          aria-label="Drag to reorder"
        >
          <GripVertical size={16} />
        </button>
      ) : null}
      <span
        className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg text-[11px] font-bold text-white ${hueOf(
          step.action,
        )}`}
      >
        {number}
      </span>
      <ActionChip action={step.action} />
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{label}</span>
      {pause && (
        <span className="shrink-0 rounded-md border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-bold text-amber-400">
          ⏸ pause
        </span>
      )}
      {alwaysRun && (
        <span
          className="shrink-0 rounded-md border border-cyan-500/40 bg-cyan-500/15 px-1.5 py-0.5 text-[10px] font-bold text-cyan-400"
          title="Collector: always runs at the end, even if earlier steps fail"
        >
          📎 always
        </span>
      )}
      <div className="flex shrink-0 items-center gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
        <button className="btn-ghost rounded-md p-1 text-sky-400" onClick={onEdit} title="Edit fields">
          <Pencil size={13} />
        </button>
        <button
          className="btn-ghost rounded-md p-1 text-indigo-400"
          onClick={onDuplicate}
          title="Duplicate this step"
        >
          <Copy size={13} />
        </button>
        {inLane ? (
          <>
            <button
              className="btn-ghost rounded-md p-1 text-violet-400 disabled:opacity-30"
              onClick={() => onMoveInLane?.(-1)}
              disabled={!canMoveLeft}
              title="Move earlier within the parallel group"
            >
              <ChevronLeft size={13} />
            </button>
            <button
              className="btn-ghost rounded-md p-1 text-violet-400 disabled:opacity-30"
              onClick={() => onMoveInLane?.(1)}
              disabled={!canMoveRight}
              title="Move later within the parallel group"
            >
              <ChevronRight size={13} />
            </button>
            <button
              className="btn-ghost rounded-md p-1 text-violet-400"
              onClick={onUnlink}
              title="Remove from parallel group"
            >
              <Unlink size={13} />
            </button>
          </>
        ) : (
          <>
            {canMergeUp && (
              <button
                className="btn-ghost rounded-md p-1 text-violet-400"
                onClick={onMergeUp}
                title="Run in parallel with the step above"
              >
                <Link2 size={13} />
              </button>
            )}
            <button
              className={`btn-ghost rounded-md p-1 ${pause ? 'text-amber-400' : 'text-text-muted'}`}
              onClick={onTogglePause}
              title={pause ? 'Remove pause checkpoint' : 'Pause before this step (wait for Next)'}
            >
              <Pause size={13} />
            </button>
          </>
        )}
        <button className="btn-ghost rounded-md p-1 text-error" onClick={onDelete} title="Delete step">
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}

// ---- sortable wrapper (one per row: a step or a parallel lane) -----------------

function SortableRow({
  rowIndex,
  children,
}: {
  rowIndex: number;
  children: (handle: HandleProps, dragging: boolean) => ReactNode;
}) {
  const sortable = useSortable({ id: `row|${rowIndex}`, data: { type: 'row', rowIndex } });
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
  };
  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className={sortable.isDragging ? 'relative z-10 opacity-50' : 'relative'}
    >
      {children(
        { attributes: sortable.attributes, listeners: sortable.listeners },
        sortable.isDragging,
      )}
    </div>
  );
}

/** A bright bar showing exactly where a dragged palette action will land. */
function InsertionBar() {
  return (
    <div className="my-1 flex items-center gap-2">
      <span className="h-2 w-2 rounded-full bg-primary" />
      <span className="h-1 flex-1 rounded-full bg-primary shadow-[0_0_8px_1px] shadow-primary/50" />
    </div>
  );
}

// ---- the designer ---------------------------------------------------------------

export function TestCaseDesigner() {
  const { activeProjectId } = useProject();
  const toast = useToast();
  const navigate = useNavigate();

  const { data: templates } = useApi(getTemplates, []);
  const { data: allConfigs } = useApi(
    () => (activeProjectId ? listConfigs(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );
  const targets = useMemo(
    () => (allConfigs ?? []).filter((c) => c.config_type === 'target'),
    [allConfigs],
  );
  const {
    data: testCases,
    loading: loadingCases,
    refetch: refetchCases,
  } = useApi(
    () => (activeProjectId ? listTestCases(activeProjectId) : Promise.resolve([])),
    [activeProjectId],
  );

  // ---- breadcrumb selectors ------------------------------------------------------

  const [suite, setSuite] = useState('');
  const [scenario, setScenario] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  // Existing cases load read-only; the user must explicitly unlock (take
  // ownership) before editing, so a saved design isn't changed by accident.
  const [locked, setLocked] = useState(false);

  const suites = useMemo(() => {
    const set = new Set<string>(STANDARD_SUITES);
    (testCases ?? []).forEach((tc) => set.add(tc.test_type || 'Ungrouped'));
    return [...set];
  }, [testCases]);
  const activeSuite = suite || suites[0] || '';

  const scenarios = useMemo(
    () => [
      ...new Set(
        (testCases ?? [])
          .filter((tc) => (tc.test_type || 'Ungrouped') === activeSuite)
          .map((tc) => tc.scenario || 'General'),
      ),
    ],
    [testCases, activeSuite],
  );
  const activeScenario = scenario || scenarios[0] || '';

  const visibleCases = useMemo(
    () =>
      (testCases ?? []).filter(
        (tc) =>
          (tc.test_type || 'Ungrouped') === activeSuite &&
          (tc.scenario || 'General') === activeScenario,
      ),
    [testCases, activeSuite, activeScenario],
  );

  /** Confirm before discarding unsaved changes when switching away. */
  const confirmDiscard = () =>
    !dirty ||
    window.confirm('You have unsaved changes in the designer. Leave and lose them?');

  // Warn before a full reload/close, and gate sidebar navigation, while dirty.
  useEffect(() => {
    setNavGuard(() => confirmDiscard());
    if (!dirty) return () => setNavGuard(null);
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => {
      window.removeEventListener('beforeunload', handler);
      setNavGuard(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty]);

  const loadCase = async (id: number) => {
    if (!confirmDiscard()) return;
    const testCase = await getTestCase(id);
    setSelectedCaseId(id);
    setSuite(testCase.test_type);
    setScenario(testCase.scenario);
    setDraft({
      name: testCase.name,
      suite: testCase.test_type,
      scenario: testCase.scenario,
      description: testCase.description,
      steps: testCase.steps ?? [],
      createdBy: testCase.created_by,
      modifiedBy: testCase.modified_by,
      origin: testCase.origin,
      defaultTargetId: testCase.default_target_id ?? null,
    });
    setDirty(false);
    setLocked(true);
  };

  // ---- export / import (port a design to another machine) ------------------------

  const importInputRef = useRef<HTMLInputElement>(null);

  const exportCase = async () => {
    if (!selectedCaseId) return;
    try {
      const bundle = await exportTestCase(selectedCaseId);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safe = String(bundle.name ?? 'testcase').replace(/[^\w.-]+/g, '_');
      a.href = url;
      a.download = `${safe}.maestro.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast('error', 'Export failed');
    }
  };

  const importCase = async (files: FileList | null) => {
    if (!files || files.length === 0 || !activeProjectId) return;
    try {
      const bundle = JSON.parse(await files[0].text()) as Record<string, unknown>;
      const created = await importTestCase({ ...bundle, project_id: activeProjectId });
      toast('success', `Imported "${created.name}"`);
      await refetchCases();
      void loadCase(created.id);
    } catch (err) {
      toast('error', `Import failed: ${err instanceof Error ? err.message : 'invalid file'}`);
    } finally {
      if (importInputRef.current) importInputRef.current.value = '';
    }
  };

  // ---- palette ----------------------------------------------------------------------

  const [search, setSearch] = useState('');
  // Palette groups start collapsed — expand on demand or via search.
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  const paletteGroups = useMemo(() => {
    const text = search.toLowerCase();
    return Object.entries(templates ?? {})
      .map(([group, items]) => ({
        group,
        items: items.filter(
          (t) =>
            !text ||
            t.label.toLowerCase().includes(text) ||
            t.action.toLowerCase().includes(text) ||
            (t.description ?? '').toLowerCase().includes(text) ||
            (t.tags ?? []).some((tag) => tag.toLowerCase().includes(text)),
        ),
      }))
      .filter((g) => g.items.length > 0);
  }, [templates, search]);

  // ---- step mutations ------------------------------------------------------------------

  const renumber = (steps: TestStep[]): TestStep[] => {
    // Keep parallel-group members contiguous (the engine batches only
    // consecutive same-group steps), drop single-member lanes, then renumber.
    const ordered = compactGroups(normalize(steps)).map((step, index) => ({
      ...step,
      step_number: index + 1,
    }));
    // Give nodes stable ids and turn canvas Yes/No branches into engine `_if`.
    return resolveBranches(assignUids(ordered));
  };

  const mutateSteps = (steps: TestStep[]) => {
    if (locked) return; // read-only until the user unlocks (takes ownership)
    setDraft((current) => (current ? { ...current, steps: renumber(steps) } : current));
    setDirty(true);
  };

  const stepFromTemplate = (template: StepTemplate): TestStep => ({
    step_number: 0,
    action: template.action,
    parameters: { _label: template.label, ...template.parameters },
    timeout_seconds: template.timeout_seconds,
    retry_count: 0,
  });

  const appendTemplate = (template: StepTemplate) => {
    if (!draft) {
      toast('info', 'Select or create a test case first');
      return;
    }
    mutateSteps([...draft.steps, stepFromTemplate(template)]);
  };

  const rows = draft ? buildRows(draft.steps) : [];

  // ---- parallel grouping (via buttons, not fragile drag-onto) --------------------------

  const mergeUp = (rowIndex: number) => {
    if (!draft || rowIndex <= 0) return;
    const prev = rows[rowIndex - 1];
    const cur = rows[rowIndex];
    const group = prev.kind === 'lane' ? prev.group! : nextGroup(draft.steps);
    const merge = new Set([...prev.indices, ...cur.indices]);
    mutateSteps(
      draft.steps.map((step, i) =>
        merge.has(i) ? { ...step, parameters: { ...step.parameters, _parallel_group: group } } : step,
      ),
    );
  };

  const unlinkMember = (stepIndex: number) => {
    if (!draft) return;
    const steps = [...draft.steps];
    const [member] = steps.splice(stepIndex, 1);
    const group = member.parameters?._parallel_group;
    let lastOfGroup = -1;
    steps.forEach((s, i) => {
      if (s.parameters?._parallel_group === group) lastOfGroup = i;
    });
    steps.splice(lastOfGroup + 1, 0, stripGroup(member));
    mutateSteps(steps);
  };

  /** Reorder a parallel-group member among its siblings (members are contiguous). */
  const moveMember = (stepIndex: number, dir: -1 | 1) => {
    if (!draft) return;
    const target = stepIndex + dir;
    if (target < 0 || target >= draft.steps.length) return;
    // Only swap with a sibling in the same group.
    if (
      draft.steps[target].parameters?._parallel_group !==
      draft.steps[stepIndex].parameters?._parallel_group
    )
      return;
    mutateSteps(arrayMove(draft.steps, stepIndex, target));
  };

  const ungroupLane = (rowIndex: number) => {
    if (!draft) return;
    const targets = new Set(rows[rowIndex].indices);
    mutateSteps(draft.steps.map((step, i) => (targets.has(i) ? stripGroup(step) : step)));
  };

  const updateStep = (index: number, updater: (step: TestStep) => TestStep) => {
    if (!draft) return;
    const steps = [...draft.steps];
    steps[index] = updater(steps[index]);
    mutateSteps(steps);
  };

  const deleteStep = (index: number) => {
    if (!draft) return;
    mutateSteps(draft.steps.filter((_, i) => i !== index));
  };

  /** Copy a step in place (inserted right after the original). */
  const duplicateStepInList = (index: number) => {
    if (!draft) return;
    const original = draft.steps[index];
    const params = { ...original.parameters };
    delete params._uid; // renumber assigns a fresh id
    delete params._branch; // a copy shouldn't inherit Yes/No routing
    delete params._pos;
    const steps = [...draft.steps];
    steps.splice(index + 1, 0, { ...original, id: undefined, parameters: params });
    mutateSteps(steps);
  };

  const togglePause = (index: number) =>
    updateStep(index, (step) => {
      const params = { ...step.parameters };
      if (params._pause_before) delete params._pause_before;
      else params._pause_before = true;
      return { ...step, parameters: params };
    });

  // ---- drag & drop --------------------------------------------------------------------

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));
  const { setNodeRef: setCanvasRef, isOver: canvasOver } = useDroppable({ id: 'canvas' });
  const [activeKind, setActiveKind] = useState<'palette' | 'row' | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const [dragGhost, setDragGhost] = useState<{ action: string; label: string; number?: number } | null>(
    null,
  );

  /** Where (row position) a palette drop currently targets — used for insert + indicator. */
  const targetRowFor = (event: DragOverEvent | DragEndEvent): number => {
    const over = event.over;
    if (!over) return rows.length;
    const overId = String(over.id);
    if (overId === 'canvas') return rows.length;
    if (overId.startsWith('row|')) {
      const j = Number(overId.split('|')[1]);
      const a = event.active.rect.current.translated;
      const overCenter = over.rect.top + over.rect.height / 2;
      const activeCenter = a ? a.top + a.height / 2 : overCenter;
      return activeCenter < overCenter ? j : j + 1;
    }
    return rows.length;
  };

  const handleDragStart = (event: DragStartEvent) => {
    const data = event.active.data.current as
      | { type: 'palette'; template: StepTemplate }
      | { type: 'row'; rowIndex: number }
      | undefined;
    if (data?.type === 'palette') {
      setActiveKind('palette');
      setDropIndex(rows.length);
      setDragGhost({ action: data.template.action, label: data.template.label });
    } else if (data?.type === 'row' && draft) {
      setActiveKind('row');
      const step = draft.steps[rows[data.rowIndex].indices[0]];
      setDragGhost({
        action: step.action,
        label: String(step.parameters?._label ?? '') || step.action,
        number: step.step_number,
      });
    }
  };

  const handleDragOver = (event: DragOverEvent) => {
    if (event.active.data.current?.type !== 'palette' || !draft) return;
    setDropIndex(targetRowFor(event));
  };

  const resetDrag = () => {
    setActiveKind(null);
    setDropIndex(null);
    setDragGhost(null);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    const data = active.data.current as
      | { type: 'palette'; template: StepTemplate }
      | { type: 'row'; rowIndex: number }
      | undefined;
    resetDrag();
    if (!draft || !data) return;

    if (data.type === 'row') {
      if (!over) return;
      const overId = String(over.id);
      if (!overId.startsWith('row|')) return;
      const to = Number(overId.split('|')[1]);
      if (data.rowIndex === to) return;
      const chunks = rows.map((row) => row.indices.map((i) => draft.steps[i]));
      mutateSteps(arrayMove(chunks, data.rowIndex, to).flat());
      return;
    }

    // palette → insert a new step at the targeted position
    const p = targetRowFor(event);
    const flat = p >= rows.length ? draft.steps.length : rows[p].indices[0];
    const steps = [...draft.steps];
    steps.splice(flat, 0, stepFromTemplate(data.template));
    mutateSteps(steps);
  };

  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [branchIndex, setBranchIndex] = useState<number | null>(null);
  const [view, setView] = useState<'flow' | 'canvas' | 'list'>('flow');

  // Resizable action-palette column.
  const [paletteWidth, setPaletteWidth] = useState(280);
  const startPaletteResize = (event: React.PointerEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startW = paletteWidth;
    const move = (e: PointerEvent) =>
      setPaletteWidth(Math.min(560, Math.max(200, startW + (e.clientX - startX))));
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  // ---- save / run -------------------------------------------------------------------------

  const saveCase = async (): Promise<number | null> => {
    if (!draft || !activeProjectId) return null;
    const payload = {
      project_id: activeProjectId,
      name: draft.name,
      description: draft.description,
      test_type: draft.suite || 'Ungrouped',
      scenario: draft.scenario || 'General',
      default_target_id: draft.defaultTargetId ?? null,
      steps: renumber(draft.steps),
    };
    try {
      let id = selectedCaseId;
      if (selectedCaseId) {
        await updateTestCase(selectedCaseId, payload);
      } else {
        const created = await createTestCase(payload);
        setSelectedCaseId(created.id);
        id = created.id;
      }
      setDirty(false);
      setSuite(payload.test_type);
      setScenario(payload.scenario);
      toast('success', 'Test case saved');
      void refetchCases();
      return id;
    } catch (err) {
      toast('error', `Save failed: ${err instanceof Error ? err.message : err}`);
      return null;
    }
  };

  const [runMenuOpen, setRunMenuOpen] = useState(false);
  const [cycles, setCycles] = useState(1);
  const suiteCaseCount = useMemo(
    () => (testCases ?? []).filter((tc) => (tc.test_type || 'Ungrouped') === activeSuite).length,
    [testCases, activeSuite],
  );

  const runCase = async (cycleCount = 1) => {
    setRunMenuOpen(false);
    if (!draft) {
      toast('info', 'Create or select a test case first');
      return;
    }
    // Persist unsaved edits (e.g. a target binding) so the run uses them.
    const id = dirty || !selectedCaseId ? await saveCase() : selectedCaseId;
    if (!id) return;
    await startExecution(id, 'serial', null, cycleCount > 1 ? cycleCount : undefined);
    toast(
      'success',
      cycleCount > 1
        ? `Endurance run started — ${cycleCount} cycles`
        : 'Run started — opening Execution Console',
    );
    navigate('/execution');
  };

  const runGroup = async (withScenario: boolean) => {
    setRunMenuOpen(false);
    if (dirty) await saveCase(); // don't run a stale version of the open case
    try {
      const result = await startSuiteRun({
        project_id: activeProjectId ?? undefined,
        suite: activeSuite,
        scenario: withScenario ? activeScenario : undefined,
      });
      toast('success', `Run started — ${result.total} test case(s)`);
      navigate('/execution');
    } catch {
      toast('error', 'No test cases to run in this group');
    }
  };

  // ---- manage cases modal --------------------------------------------------------------------

  const [managing, setManaging] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const allCases = testCases ?? [];
  const toggleSelected = (ids: number[], on: boolean) =>
    setSelectedIds((current) => {
      const next = new Set(current);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  const deleteSelected = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`Delete ${selectedIds.size} test case(s) and their history?`)) return;
    await deleteTestCases([...selectedIds]);
    if (selectedCaseId !== null && selectedIds.has(selectedCaseId)) {
      setSelectedCaseId(null);
      setDraft(null);
    }
    setSelectedIds(new Set());
    toast('success', 'Deleted');
    void refetchCases();
  };

  const [moveSuite, setMoveSuite] = useState('');
  const [moveScenario, setMoveScenario] = useState('');
  const applyMove = async () => {
    if (selectedIds.size === 0 || !moveSuite.trim()) return;
    await moveTestCases([...selectedIds], moveSuite.trim(), moveScenario.trim() || 'General');
    toast('success', `Moved ${selectedIds.size} test case(s) to ${moveSuite}`);
    setSelectedIds(new Set());
    void refetchCases();
  };

  const usedSuites = useMemo(
    () => [...new Set(allCases.map((tc) => tc.test_type || 'Ungrouped'))],
    [allCases],
  );
  const groupTree = useMemo(() => {
    const map = new Map<string, Map<string, typeof allCases>>();
    allCases.forEach((tc) => {
      const suiteName = tc.test_type || 'Ungrouped';
      const scenarioName = tc.scenario || 'General';
      if (!map.has(suiteName)) map.set(suiteName, new Map());
      const scenarios = map.get(suiteName)!;
      if (!scenarios.has(scenarioName)) scenarios.set(scenarioName, []);
      scenarios.get(scenarioName)!.push(tc);
    });
    return map;
  }, [allCases]);

  const [editingGroup, setEditingGroup] = useState<{
    suite: string;
    scenario?: string;
    caseId?: number;
    value: string;
  } | null>(null);

  const saveGroupRename = async () => {
    if (!editingGroup || !editingGroup.value.trim() || !activeProjectId) return;
    const newName = editingGroup.value.trim();
    try {
      if (editingGroup.caseId != null) {
        const full = await getTestCase(editingGroup.caseId);
        await updateTestCase(editingGroup.caseId, {
          project_id: full.project_id,
          name: newName,
          description: full.description,
          test_type: full.test_type,
          scenario: full.scenario,
          steps: full.steps ?? [],
        });
        if (selectedCaseId === editingGroup.caseId && draft) {
          setDraft({ ...draft, name: newName });
        }
      } else {
        await renameGroup({
          project_id: activeProjectId,
          suite: editingGroup.suite,
          scenario: editingGroup.scenario,
          new_name: newName,
        });
      }
      toast('success', `Renamed to "${newName}"`);
      setEditingGroup(null);
      void refetchCases();
    } catch {
      toast('error', 'Rename failed');
    }
  };

  const deleteGroup = async (suiteName: string, scenarioName?: string) => {
    const scenarios = groupTree.get(suiteName);
    if (!scenarios) return;
    const ids = (
      scenarioName ? scenarios.get(scenarioName) ?? [] : [...scenarios.values()].flat()
    ).map((tc) => tc.id);
    if (ids.length === 0) return;
    const target = scenarioName ? `scenario "${scenarioName}"` : `suite "${suiteName}"`;
    if (!window.confirm(`Delete ${target} with its ${ids.length} test case(s) and their run history?`))
      return;
    await deleteTestCases(ids);
    if (selectedCaseId !== null && ids.includes(selectedCaseId)) {
      setSelectedCaseId(null);
      setDraft(null);
    }
    toast('success', `Deleted ${target}`);
    void refetchCases();
  };

  // ---- new case modal ----------------------------------------------------------------------------

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSuite, setNewSuite] = useState<string>(STANDARD_SUITES[0]);
  const [customSuite, setCustomSuite] = useState('');
  const [newScenario, setNewScenario] = useState('');

  const confirmCreate = () => {
    if (!newName.trim()) return;
    const suiteName = newSuite === '__custom__' ? customSuite.trim() || 'Ungrouped' : newSuite;
    setSelectedCaseId(null);
    setDraft({
      name: newName.trim(),
      suite: suiteName,
      scenario: newScenario.trim() || 'General',
      description: '',
      steps: [],
    });
    setSuite(suiteName);
    setScenario(newScenario.trim() || 'General');
    setDirty(true);
    setLocked(false);
    setCreating(false);
  };

  // ---- keyboard shortcuts: F2 rename, Ctrl+S save ------------------------------------------------

  const nameInputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'F2') {
        event.preventDefault();
        nameInputRef.current?.focus();
        nameInputRef.current?.select();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (dirty) void saveCase();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, draft, selectedCaseId, activeProjectId]);

  // ---- render ---------------------------------------------------------------------------------------

  const paletteDragging = activeKind === 'palette';
  const rowIds = rows.map((_, i) => `row|${i}`);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={collisionStrategy}
      measuring={{ droppable: { strategy: MeasuringStrategy.Always } }}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={resetDrag}
    >
      <DragOverlay>
        {dragGhost && (
          <div className="flex cursor-grabbing items-center gap-3 rounded-xl border border-primary/60 bg-surface px-3.5 py-3 shadow-2xl ring-2 ring-primary/40">
            {dragGhost.number != null && (
              <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary text-[11px] font-bold text-white">
                {dragGhost.number}
              </span>
            )}
            <ActionChip action={dragGhost.action} />
            <span className="text-sm font-medium">{dragGhost.label}</span>
          </div>
        )}
      </DragOverlay>

      <div className="flex h-full flex-col gap-4">
        {/* Breadcrumb / actions bar */}
        <div className="card flex flex-wrap items-center gap-2 p-2.5">
          <p className="w-full text-[11px] text-text-muted">
            Pick a <b>Suite → Scenario → Test case</b> to open it, or create a new one.
            The <b>Run on</b> selector (below the name) sets where it runs: Local or a saved RDP machine.
          </p>
          <select
            className="input w-36"
            value={activeSuite}
            onChange={(e) => {
              setSuite(e.target.value);
              setScenario('');
            }}
            aria-label="Suite"
          >
            {suites.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <ChevronRight size={14} className="text-text-muted" />
          <select
            className="input w-40"
            value={activeScenario}
            onChange={(e) => setScenario(e.target.value)}
            aria-label="Scenario"
          >
            {scenarios.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
            {scenarios.length === 0 && <option value="">—</option>}
          </select>
          <ChevronRight size={14} className="text-text-muted" />
          <select
            className="input w-44"
            value={selectedCaseId ?? ''}
            onChange={(e) => {
              if (e.target.value) void loadCase(Number(e.target.value));
            }}
            aria-label="Test case"
          >
            <option value="">
              {draft && !selectedCaseId ? `✱ ${draft.name} (unsaved)` : 'Select test case…'}
            </option>
            {visibleCases.map((tc) => (
              <option key={tc.id} value={tc.id}>
                {tc.name} ({tc.step_count})
              </option>
            ))}
          </select>
          <button
            className="btn-primary px-3 py-1.5 text-xs"
            onClick={() => {
              setNewName('');
              setNewSuite(activeSuite || STANDARD_SUITES[0]);
              setCustomSuite('');
              setNewScenario(activeScenario);
              setCreating(true);
            }}
          >
            <Plus size={13} /> New
          </button>
          <button
            className="btn-outline px-3 py-1.5 text-xs"
            onClick={() => setManaging(true)}
            title="Bulk manage test cases"
          >
            <FolderCog size={13} className="text-orange-400" /> Manage
          </button>
          <div className="ml-auto flex items-center gap-2">
            <input
              ref={importInputRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => void importCase(e.target.files)}
            />
            <button
              className="btn-ghost px-2 py-1.5 text-xs text-emerald-400"
              onClick={() => importInputRef.current?.click()}
              title="Import a test case exported from another machine"
            >
              <Upload size={13} /> Import
            </button>
            {selectedCaseId && (
              <button
                className="btn-ghost px-2 py-1.5 text-xs text-amber-400"
                onClick={exportCase}
                title="Export this test case to a portable JSON file"
              >
                <Download size={13} /> Export
              </button>
            )}
            {selectedCaseId && (
              <button
                className="btn-ghost px-2 py-1.5 text-xs text-cyan-400"
                onClick={async () => {
                  const clone = await cloneTestCase(selectedCaseId);
                  await refetchCases();
                  void loadCase(clone.id);
                }}
                title="Clone this test case"
              >
                <Copy size={13} /> Clone
              </button>
            )}
            <div className="relative">
              <button
                className="btn bg-emerald-600 px-3 py-1.5 text-xs text-white hover:opacity-90"
                onClick={() => setRunMenuOpen((open) => !open)}
              >
                <Play size={13} /> Run <ChevronDown size={12} />
              </button>
              {runMenuOpen && (
                <div className="card absolute right-0 top-full z-30 mt-1 w-72 p-1.5">
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2 disabled:opacity-40"
                    onClick={() => void runCase(1)}
                    disabled={!selectedCaseId || dirty}
                    title={dirty ? 'Save the test case first' : ''}
                  >
                    <Play size={13} className="text-emerald-400" />
                    <span className="min-w-0 flex-1 truncate">Test case: {draft?.name ?? '—'}</span>
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2 disabled:opacity-40"
                    onClick={() => void runGroup(true)}
                    disabled={visibleCases.length === 0}
                  >
                    <Play size={13} className="text-purple-400" />
                    <span className="min-w-0 flex-1 truncate">Scenario: {activeScenario || '—'}</span>
                    <span className="shrink-0 text-xs text-text-muted">
                      {visibleCases.length} case{visibleCases.length === 1 ? '' : 's'}
                    </span>
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2 disabled:opacity-40"
                    onClick={() => void runGroup(false)}
                    disabled={suiteCaseCount === 0}
                  >
                    <Play size={13} className="text-indigo-400" />
                    <span className="min-w-0 flex-1 truncate">Whole suite: {activeSuite || '—'}</span>
                    <span className="shrink-0 text-xs text-text-muted">
                      {suiteCaseCount} case{suiteCaseCount === 1 ? '' : 's'}
                    </span>
                  </button>
                  <div className="mt-1 border-t border-border px-3 py-2">
                    <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">
                      Endurance / stability
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min={1}
                        max={100000}
                        value={cycles}
                        onChange={(e) => setCycles(Math.max(1, parseInt(e.target.value, 10) || 1))}
                        className="input w-20 py-1 text-xs"
                        aria-label="Cycles"
                        title="Repeat the test case this many cycles"
                      />
                      <button
                        className="btn flex-1 bg-amber-600 px-2.5 py-1 text-xs text-white hover:opacity-90 disabled:opacity-40"
                        onClick={() => void runCase(cycles)}
                        disabled={!selectedCaseId || dirty}
                        title={
                          dirty
                            ? 'Save the test case first'
                            : 'Repeat the case N cycles, recording per-cycle results + a roll-up'
                        }
                      >
                        <Play size={13} /> Run {cycles} cycle{cycles === 1 ? '' : 's'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <button className="btn-primary px-3 py-1.5 text-xs" onClick={saveCase} disabled={!draft || !dirty}>
              <Save size={13} /> Save{dirty ? ' •' : ''}
            </button>
          </div>
        </div>

        <div
          className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-rows-[minmax(0,1fr)]"
          style={draft ? { gridTemplateColumns: `${paletteWidth}px 1fr` } : undefined}
        >
          {/* Action palette — only while building a test case */}
          {draft && (
          <div className="card relative flex min-h-0 flex-col p-3.5">
            {/* Drag the right edge to resize this column */}
            <div
              onPointerDown={startPaletteResize}
              className="absolute -right-2.5 top-0 z-10 hidden h-full w-2.5 cursor-col-resize lg:block"
              title="Drag to resize the palette"
            >
              <div className="mx-auto h-full w-px bg-border transition-colors hover:bg-primary/60" />
            </div>
            <div className="relative mb-2.5">
              <Search size={14} className="absolute left-2.5 top-2.5 text-text-muted" />
              <input
                className="input pl-8 text-xs"
                placeholder="Search actions…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="min-h-0 flex-1 space-y-2 overflow-auto">
              {paletteGroups.map(({ group, items }) => {
                const open = openGroups.has(group) || search.length > 0;
                return (
                  <div key={group}>
                    <button
                      className="flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-xs font-semibold uppercase tracking-wide text-text-secondary hover:bg-surface-2"
                      onClick={() =>
                        setOpenGroups((current) => {
                          const next = new Set(current);
                          if (next.has(group)) next.delete(group);
                          else next.add(group);
                          return next;
                        })
                      }
                    >
                      {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                      {group}
                      <span className="ml-auto font-normal text-text-muted">{items.length}</span>
                    </button>
                    {open && (
                      <div className="mt-1 space-y-1">
                        {items.map((template, index) => (
                          <PaletteItem
                            key={`${group}-${index}`}
                            id={`pal|${group}|${index}`}
                            template={template}
                            onAppend={() => appendTemplate(template)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          )}

          {/* Step canvas */}
          <div className="card flex min-h-0 flex-col p-4">
            {loadingCases ? (
              <Spinner />
            ) : draft ? (
              <>
                <input
                  ref={nameInputRef}
                  className="input mb-1 max-w-md"
                  value={draft.name}
                  readOnly={locked}
                  onChange={(e) => {
                    if (locked) return;
                    setDraft({ ...draft, name: e.target.value });
                    setDirty(true);
                  }}
                  placeholder="Test case name (F2 to rename, Ctrl+S to save)"
                  title="F2 focuses this field; Ctrl+S saves"
                />
                <div className="mb-3 flex items-center gap-3">
                  <p className="text-[11px] text-text-muted">
                    {draft.suite} / {draft.scenario}
                    {draft.createdBy && (
                      <>
                        {' · '}created by <span className="font-medium text-text-secondary">{draft.createdBy}</span>
                      </>
                    )}
                    {draft.modifiedBy && (
                      <>
                        {' · '}last edited by{' '}
                        <span className="font-medium text-text-secondary">{draft.modifiedBy}</span>
                      </>
                    )}
                    {draft.origin === 'imported' && (
                      <span className="ml-1.5 rounded border border-amber-500/40 bg-amber-500/10 px-1 py-px text-[10px] font-semibold text-amber-400">
                        imported
                      </span>
                    )}
                  </p>
                  {locked && (
                    <button
                      className="btn-outline px-2.5 py-1 text-xs text-amber-400"
                      onClick={() => {
                        setLocked(false);
                        toast('info', 'Editing unlocked — saving will record you as the editor');
                      }}
                      title="Take ownership to edit this saved test case"
                    >
                      <Lock size={12} /> Unlock to edit
                    </button>
                  )}
                  <label className="ml-auto flex items-center gap-1.5 text-[11px] text-text-muted">
                    Run on
                    <select
                      className="input h-7 py-0 text-xs"
                      value={draft.defaultTargetId ?? ''}
                      disabled={locked}
                      onChange={(e) => {
                        if (locked) return;
                        const value = e.target.value ? Number(e.target.value) : null;
                        setDraft({ ...draft, defaultTargetId: value });
                        setDirty(true);
                      }}
                      title="Where this test runs: Local, or a saved remote/RDP target"
                    >
                      <option value="">Local (this machine)</option>
                      {targets.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.label}
                          {t.settings?.kind === 'remote'
                            ? ` (${t.settings?.hostname ?? 'remote'})`
                            : ' (local)'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="inline-flex overflow-hidden rounded-lg border border-border text-xs">
                    <button
                      className={`px-3 py-1 font-medium transition-colors ${
                        view === 'flow'
                          ? 'bg-primary text-white'
                          : 'bg-surface text-text-secondary hover:bg-surface-2'
                      }`}
                      onClick={() => setView('flow')}
                      title="React Flow designer"
                    >
                      ✦ Flow
                    </button>
                    <button
                      className={`border-l border-border px-3 py-1 font-medium transition-colors ${
                        view === 'canvas'
                          ? 'bg-primary text-white'
                          : 'bg-surface text-text-secondary hover:bg-surface-2'
                      }`}
                      onClick={() => setView('canvas')}
                      title="Classic canvas"
                    >
                      ⊞ Classic
                    </button>
                    <button
                      className={`px-3 py-1 font-medium transition-colors ${
                        view === 'list'
                          ? 'bg-primary text-white'
                          : 'bg-surface text-text-secondary hover:bg-surface-2'
                      }`}
                      onClick={() => setView('list')}
                    >
                      ☰ List
                    </button>
                  </div>
                </div>

                {view === 'flow' ? (
                  <FlowCanvasRF
                    steps={draft.steps}
                    onChange={mutateSteps}
                    onEdit={(index) => setEditingIndex(index)}
                    onBranch={(index) => setBranchIndex(index)}
                    onAdd={() =>
                      mutateSteps([
                        ...draft.steps,
                        {
                          step_number: 0,
                          action: 'system.echo',
                          parameters: { _label: 'New step' },
                          timeout_seconds: 30,
                          retry_count: 0,
                        },
                      ])
                    }
                  />
                ) : view === 'canvas' ? (
                  <FlowCanvas
                    steps={draft.steps}
                    onChange={mutateSteps}
                    onEdit={(index) => setEditingIndex(index)}
                    onBranch={(index) => setBranchIndex(index)}
                    onAdd={() =>
                      mutateSteps([
                        ...draft.steps,
                        {
                          step_number: 0,
                          action: 'system.echo',
                          parameters: { _label: 'New step' },
                          timeout_seconds: 30,
                          retry_count: 0,
                        },
                      ])
                    }
                  />
                ) : (
                <div
                  ref={setCanvasRef}
                  className={`mx-auto w-full max-w-2xl flex-1 overflow-auto rounded-2xl p-1.5 transition-colors ${
                    paletteDragging ? 'bg-primary/5 ring-1 ring-inset ring-primary/20' : ''
                  }`}
                >
                  {draft.steps.length === 0 ? (
                    <div
                      className={`flex min-h-[260px] flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed text-center text-sm transition-colors ${
                        canvasOver || paletteDragging
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-text-muted'
                      }`}
                    >
                      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-3xl text-primary">
                        ⤓
                      </span>
                      <div>
                        Drag an action anywhere in here to add the first step
                        <br />
                        <span className="text-xs">…or click the + on any palette item</span>
                      </div>
                    </div>
                  ) : (
                    <SortableContext items={rowIds} strategy={verticalListSortingStrategy}>
                      <div className="space-y-2.5">
                        {rows.map((row, rowIndex) => (
                          <Fragment key={rowIndex}>
                            {paletteDragging && dropIndex === rowIndex && <InsertionBar />}
                            <SortableRow rowIndex={rowIndex}>
                              {(handle, dragging) =>
                                row.kind === 'single' ? (
                                  <StepBox
                                    step={draft.steps[row.indices[0]]}
                                    number={draft.steps[row.indices[0]].step_number}
                                    inLane={false}
                                    canMergeUp={rowIndex > 0}
                                    handle={handle}
                                    dragging={dragging}
                                    onEdit={() => setEditingIndex(row.indices[0])}
                                    onDelete={() => deleteStep(row.indices[0])}
                                    onDuplicate={() => duplicateStepInList(row.indices[0])}
                                    onTogglePause={() => togglePause(row.indices[0])}
                                    onMergeUp={() => mergeUp(rowIndex)}
                                    onUnlink={() => {}}
                                  />
                                ) : (
                                  <div className="rounded-2xl border-2 border-dashed border-violet-500/40 bg-violet-500/5 p-2.5">
                                    <div className="mb-2 flex items-center gap-1.5">
                                      <button
                                        className="-ml-0.5 cursor-grab touch-none rounded p-1 text-violet-400/80 hover:bg-violet-500/10 active:cursor-grabbing"
                                        {...handle.attributes}
                                        {...handle.listeners}
                                        aria-label="Drag parallel group"
                                      >
                                        <GripVertical size={14} />
                                      </button>
                                      <span className="text-[10px] font-bold uppercase tracking-wider text-violet-400">
                                        ⇉ Parallel group {row.group} · run together
                                      </span>
                                      <button
                                        className="btn-ghost ml-auto rounded-md p-1 text-[10px] text-violet-300"
                                        onClick={() => ungroupLane(rowIndex)}
                                        title="Break into sequential steps"
                                      >
                                        <Split size={12} /> ungroup
                                      </button>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                      {row.indices.map((stepIndex, memberPos) => (
                                        <StepBox
                                          key={stepIndex}
                                          step={draft.steps[stepIndex]}
                                          number={draft.steps[stepIndex].step_number}
                                          inLane
                                          canMoveLeft={memberPos > 0}
                                          canMoveRight={memberPos < row.indices.length - 1}
                                          onEdit={() => setEditingIndex(stepIndex)}
                                          onDelete={() => deleteStep(stepIndex)}
                                          onDuplicate={() => duplicateStepInList(stepIndex)}
                                          onTogglePause={() => {}}
                                          onMergeUp={() => {}}
                                          onUnlink={() => unlinkMember(stepIndex)}
                                          onMoveInLane={(dir) => moveMember(stepIndex, dir)}
                                        />
                                      ))}
                                    </div>
                                  </div>
                                )
                              }
                            </SortableRow>
                          </Fragment>
                        ))}
                        {paletteDragging && dropIndex !== null && dropIndex >= rows.length && (
                          <InsertionBar />
                        )}
                        <div
                          className={`mt-1 flex items-center justify-center gap-2 rounded-xl border border-dashed py-3 text-xs transition-colors ${
                            paletteDragging
                              ? 'border-primary/60 text-primary'
                              : 'border-border/60 text-text-muted'
                          }`}
                        >
                          <Plus size={14} /> Drag actions here, or click + on a palette item
                        </div>
                      </div>
                    </SortableContext>
                  )}
                </div>
                )}
              </>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
                <p className="text-sm text-text-muted">
                  Pick a test case from the bar above, or create a new one.
                </p>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setNewName('');
                    setNewSuite(activeSuite || STANDARD_SUITES[0]);
                    setNewScenario(activeScenario);
                    setCreating(true);
                  }}
                >
                  <Plus size={15} /> New test case
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      <StepEditModal
        step={editingIndex !== null && draft ? draft.steps[editingIndex] : null}
        onClose={() => setEditingIndex(null)}
        onSave={(updated) => {
          if (editingIndex === null || !draft) return;
          const steps = [...draft.steps];
          steps[editingIndex] = updated;
          mutateSteps(steps);
        }}
      />

      <BranchEditor
        step={branchIndex !== null && draft ? draft.steps[branchIndex] : null}
        steps={draft?.steps ?? []}
        onClose={() => setBranchIndex(null)}
        onSave={(updated) => {
          if (branchIndex === null || !draft) return;
          const steps = [...draft.steps];
          steps[branchIndex] = updated;
          mutateSteps(steps);
        }}
      />

      <Modal open={creating} title="New test case" onClose={() => setCreating(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Test case name</label>
            <input
              className="input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Verify QNX SSH"
              autoFocus
            />
          </div>
          <div>
            <label className="label">Suite</label>
            <select className="input" value={newSuite} onChange={(e) => setNewSuite(e.target.value)}>
              {suites.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
              <option value="__custom__">Custom suite…</option>
            </select>
            {newSuite === '__custom__' && (
              <input
                className="input mt-2"
                value={customSuite}
                onChange={(e) => setCustomSuite(e.target.value)}
                placeholder="Custom suite name"
              />
            )}
          </div>
          <div>
            <label className="label">Scenario</label>
            <input
              className="input"
              value={newScenario}
              onChange={(e) => setNewScenario(e.target.value)}
              placeholder="e.g. System Health Check"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button className="btn-outline" onClick={() => setCreating(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={confirmCreate} disabled={!newName.trim()}>
              Create
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={managing} title="Manage suites & test cases" onClose={() => setManaging(false)} wide>
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-background p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
              Suites → scenarios → test cases — hover any row to rename or delete
            </div>
            <div className="max-h-[48vh] space-y-0.5 overflow-auto">
              {[...groupTree.entries()].map(([suiteName, scenarioMap]) => {
                const suiteCount = [...scenarioMap.values()].flat().length;
                const editingSuite = editingGroup?.suite === suiteName && !editingGroup.scenario;
                return (
                  <div key={suiteName}>
                    <div className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2">
                      {editingSuite ? (
                        <>
                          <input
                            className="input w-52 py-1 text-xs"
                            value={editingGroup.value}
                            onChange={(e) => setEditingGroup({ ...editingGroup, value: e.target.value })}
                            onKeyDown={(e) => e.key === 'Enter' && void saveGroupRename()}
                            autoFocus
                          />
                          <button className="btn-primary px-2 py-0.5 text-xs" onClick={saveGroupRename}>
                            Save
                          </button>
                          <button
                            className="btn-ghost px-2 py-0.5 text-xs"
                            onClick={() => setEditingGroup(null)}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="text-sm font-semibold text-indigo-400">{suiteName}</span>
                          <span className="rounded-full bg-surface-2 px-2 text-[11px] text-text-muted">
                            {suiteCount}
                          </span>
                          <div className="ml-auto flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                            <button
                              className="btn-ghost p-1 text-amber-400"
                              title="Rename suite"
                              onClick={() => setEditingGroup({ suite: suiteName, value: suiteName })}
                            >
                              <Pencil size={12} />
                            </button>
                            <button
                              className="btn-ghost p-1 text-error"
                              title="Delete suite and all its test cases"
                              onClick={() => void deleteGroup(suiteName)}
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                    {[...scenarioMap.entries()].map(([scenarioName, cases]) => {
                      const editingScenario =
                        editingGroup?.suite === suiteName &&
                        editingGroup.scenario === scenarioName &&
                        editingGroup.caseId == null;
                      return (
                        <div key={scenarioName} className="ml-6">
                          <div className="group flex items-center gap-2 rounded-md px-2 py-1 hover:bg-surface-2">
                            {editingScenario ? (
                              <>
                                <input
                                  className="input w-52 py-1 text-xs"
                                  value={editingGroup.value}
                                  onChange={(e) =>
                                    setEditingGroup({ ...editingGroup, value: e.target.value })
                                  }
                                  onKeyDown={(e) => e.key === 'Enter' && void saveGroupRename()}
                                  autoFocus
                                />
                                <button className="btn-primary px-2 py-0.5 text-xs" onClick={saveGroupRename}>
                                  Save
                                </button>
                                <button
                                  className="btn-ghost px-2 py-0.5 text-xs"
                                  onClick={() => setEditingGroup(null)}
                                >
                                  Cancel
                                </button>
                              </>
                            ) : (
                              <>
                                <input
                                  type="checkbox"
                                  className="accent-primary"
                                  checked={cases.every((tc) => selectedIds.has(tc.id))}
                                  onChange={(e) =>
                                    toggleSelected(cases.map((tc) => tc.id), e.target.checked)
                                  }
                                  aria-label={`Select all in ${scenarioName}`}
                                />
                                <span className="text-xs font-medium text-purple-400">{scenarioName}</span>
                                <span className="rounded-full bg-surface-2 px-2 text-[10px] text-text-muted">
                                  {cases.length}
                                </span>
                                <div className="ml-auto flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                                  <button
                                    className="btn-ghost p-1 text-amber-400"
                                    title="Rename scenario"
                                    onClick={() =>
                                      setEditingGroup({
                                        suite: suiteName,
                                        scenario: scenarioName,
                                        value: scenarioName,
                                      })
                                    }
                                  >
                                    <Pencil size={12} />
                                  </button>
                                  <button
                                    className="btn-ghost p-1 text-error"
                                    title="Delete scenario and its test cases"
                                    onClick={() => void deleteGroup(suiteName, scenarioName)}
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                          {cases.map((tc) => {
                            const editingCase = editingGroup?.caseId === tc.id;
                            return (
                              <div
                                key={tc.id}
                                className="group ml-7 flex items-center gap-2 rounded-md px-2 py-1 hover:bg-surface-2"
                              >
                                {editingCase ? (
                                  <>
                                    <input
                                      className="input w-56 py-1 text-xs"
                                      value={editingGroup!.value}
                                      onChange={(e) =>
                                        setEditingGroup({ ...editingGroup!, value: e.target.value })
                                      }
                                      onKeyDown={(e) => e.key === 'Enter' && void saveGroupRename()}
                                      autoFocus
                                    />
                                    <button className="btn-primary px-2 py-0.5 text-xs" onClick={saveGroupRename}>
                                      Save
                                    </button>
                                    <button
                                      className="btn-ghost px-2 py-0.5 text-xs"
                                      onClick={() => setEditingGroup(null)}
                                    >
                                      Cancel
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <input
                                      type="checkbox"
                                      className="accent-primary"
                                      checked={selectedIds.has(tc.id)}
                                      onChange={(e) => toggleSelected([tc.id], e.target.checked)}
                                      aria-label={`Select ${tc.name}`}
                                    />
                                    <button
                                      className="min-w-0 flex-1 truncate text-left text-xs hover:text-primary"
                                      onClick={() => {
                                        setManaging(false);
                                        void loadCase(tc.id);
                                      }}
                                      title="Open in the editor"
                                    >
                                      {tc.name}
                                    </button>
                                    <span className="text-[10px] text-text-muted">{tc.step_count} steps</span>
                                    <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                                      <button
                                        className="btn-ghost p-1 text-amber-400"
                                        title="Rename test case"
                                        onClick={() =>
                                          setEditingGroup({
                                            suite: suiteName,
                                            scenario: scenarioName,
                                            caseId: tc.id,
                                            value: tc.name,
                                          })
                                        }
                                      >
                                        <Pencil size={12} />
                                      </button>
                                      <button
                                        className="btn-ghost p-1 text-error"
                                        title="Delete test case"
                                        onClick={async () => {
                                          if (!window.confirm(`Delete "${tc.name}"?`)) return;
                                          await deleteTestCases([tc.id]);
                                          if (selectedCaseId === tc.id) {
                                            setSelectedCaseId(null);
                                            setDraft(null);
                                          }
                                          void refetchCases();
                                        }}
                                      >
                                        <Trash2 size={12} />
                                      </button>
                                    </div>
                                  </>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-background p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
              Move selected test cases to
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="input w-44"
                value={moveSuite}
                onChange={(e) => setMoveSuite(e.target.value)}
                aria-label="Target suite"
              >
                <option value="">Pick suite…</option>
                {[...new Set([...STANDARD_SUITES, ...usedSuites])].map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <input
                className="input w-44"
                value={moveScenario}
                onChange={(e) => setMoveScenario(e.target.value)}
                placeholder="Scenario (e.g. Connectivity)"
              />
              <button
                className="btn-outline px-3 py-1.5 text-xs"
                onClick={applyMove}
                disabled={selectedIds.size === 0 || !moveSuite}
                title={selectedIds.size === 0 ? 'Select test cases below first' : ''}
              >
                Move ({selectedIds.size})
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-text-secondary">
              <input
                type="checkbox"
                className="accent-primary"
                checked={allCases.length > 0 && selectedIds.size === allCases.length}
                onChange={(e) =>
                  setSelectedIds(e.target.checked ? new Set(allCases.map((tc) => tc.id)) : new Set())
                }
              />
              Select all ({allCases.length})
            </label>
            <button
              className="btn-danger px-3 py-1.5 text-xs"
              onClick={deleteSelected}
              disabled={selectedIds.size === 0}
            >
              <Trash2 size={13} /> Delete selected ({selectedIds.size})
            </button>
          </div>
        </div>
      </Modal>
    </DndContext>
  );
}
