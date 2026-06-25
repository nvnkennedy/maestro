/**
 * Flow-canvas serialization helpers.
 *
 * The visual canvas lets you wire Yes/No branches between nodes, but the
 * execution engine understands only the linear step model with `_if` jumps
 * (``{source_step, contains, skip_to, else_skip_to}`` keyed by step_number).
 *
 * To keep branches stable while steps are reordered/renumbered, the canvas
 * stores branch targets as stable node ids (`_uid`) under `_branch`, and we
 * resolve those to concrete step_numbers via {@link resolveBranches} on every
 * change — right before the engine ever sees them.
 */
import type { TestStep } from '../types/domain';

export interface BranchSpec {
  /** Text to look for in the checked step's output. */
  contains: string;
  /** Node uid to jump to when the text is found (Yes). */
  yes?: string | null;
  /** Node uid to jump to when it is not (No). */
  no?: string | null;
}

export interface Pos {
  x: number;
  y: number;
}

let _counter = 0;
export function newUid(): string {
  _counter += 1;
  return `n${Date.now().toString(36)}${_counter}`;
}

export function uidOf(step: TestStep): string {
  return String(step.parameters?._uid ?? '');
}

export function posOf(step: TestStep): Pos | null {
  const p = step.parameters?._pos as Pos | undefined;
  return p && typeof p.x === 'number' && typeof p.y === 'number' ? p : null;
}

export function groupOf(step: TestStep): string {
  return String(step.parameters?._parallel_group ?? '');
}

/**
 * Keep every parallel group's members contiguous, anchored at the position of
 * the group's first member (stable). The execution engine treats only
 * *consecutive* same-group steps as one parallel batch, so any reorder that
 * scatters members would silently split the group — this repairs that.
 */
export function compactGroups(steps: TestStep[]): TestStep[] {
  const firstIndex = new Map<string, number>();
  steps.forEach((step, index) => {
    const g = groupOf(step);
    if (g && !firstIndex.has(g)) firstIndex.set(g, index);
  });
  if (firstIndex.size === 0) return steps;
  // Bucket members by group; non-grouped steps keep their slot as anchors.
  const result: TestStep[] = [];
  const emitted = new Set<string>();
  steps.forEach((step, index) => {
    const g = groupOf(step);
    if (!g) {
      result.push(step);
      return;
    }
    if (firstIndex.get(g) !== index) return; // member emitted with its anchor
    if (emitted.has(g)) return;
    emitted.add(g);
    // Emit all members of this group in their current relative order.
    steps.forEach((s) => {
      if (groupOf(s) === g) result.push(s);
    });
  });
  return result;
}

/**
 * Derive execution order from on-canvas layout: top-to-bottom by a node's
 * vertical centre, ties broken left-to-right. Members of a parallel group are
 * then compacted so they stay one batch. Used by the canvas so dragging a node
 * above another actually makes it run earlier.
 */
export function orderByPosition(steps: TestStep[], fallbackRowGap = 124, topY = 70): TestStep[] {
  const withIndex = steps.map((step, index) => {
    const pos = posOf(step);
    return {
      step,
      index,
      y: pos ? pos.y : topY + index * fallbackRowGap,
      x: pos ? pos.x : 0,
    };
  });
  withIndex.sort((a, b) => a.y - b.y || a.x - b.x || a.index - b.index);
  return compactGroups(withIndex.map((w) => w.step));
}

export function branchOf(step: TestStep): BranchSpec | null {
  const b = step.parameters?._branch as BranchSpec | undefined;
  return b && typeof b === 'object' ? b : null;
}

/** Give every step a stable uid (idempotent). */
export function assignUids(steps: TestStep[]): TestStep[] {
  return steps.map((step) =>
    uidOf(step)
      ? step
      : { ...step, parameters: { ...step.parameters, _uid: newUid() } },
  );
}

/**
 * Translate each node's `_branch` (uid-based) into the engine's `_if`
 * (step_number-based), using the order the steps currently sit in. A branch
 * checks the output of the step immediately before it. Targets that no longer
 * exist are dropped. Steps without a branch get any stale `_if` cleared.
 */
export function resolveBranches(steps: TestStep[]): TestStep[] {
  const numberByUid = new Map<string, number>();
  steps.forEach((step, index) => {
    const uid = uidOf(step);
    if (uid) numberByUid.set(uid, index + 1);
  });

  return steps.map((step, index) => {
    const branch = branchOf(step);
    // Only branch-bearing nodes own their `_if`; leave manually-authored
    // `_if` (advanced editor) on other steps untouched.
    if (!branch) return step;
    const params = { ...step.parameters };
    if (!branch.yes && !branch.no) {
      delete params._if;
      return { ...step, parameters: params };
    }
    const ifSpec: Record<string, unknown> = {
      source_step: index, // previous step's number == current index (1-based prev)
      contains: branch.contains ?? '',
    };
    if (branch.yes && numberByUid.has(branch.yes)) {
      ifSpec.skip_to = numberByUid.get(branch.yes);
    }
    if (branch.no && numberByUid.has(branch.no)) {
      ifSpec.else_skip_to = numberByUid.get(branch.no);
    }
    params._if = ifSpec;
    return { ...step, parameters: params };
  });
}
