import { useEffect, useState } from 'react';
import type { TestStep } from '../../types/domain';
import { branchOf, uidOf } from '../../utils/flow';
import { Modal } from '../common/Modal';

interface BranchEditorProps {
  step: TestStep | null;
  steps: TestStep[];
  onSave: (step: TestStep) => void;
  onClose: () => void;
}

/**
 * Turns a node into a Yes/No decision: it checks whether the previous step's
 * output contains some text, then routes to the chosen node for each outcome.
 * Saved as `_branch` and resolved to the engine's `_if` on every change.
 */
export function BranchEditor({ step, steps, onSave, onClose }: BranchEditorProps) {
  const [contains, setContains] = useState('');
  const [yes, setYes] = useState('');
  const [no, setNo] = useState('');

  useEffect(() => {
    const branch = step ? branchOf(step) : null;
    setContains(branch?.contains ?? '');
    setYes(branch?.yes ?? '');
    setNo(branch?.no ?? '');
  }, [step]);

  if (!step) return null;
  const selfUid = uidOf(step);
  const labelOf = (s: TestStep) =>
    `${s.step_number}. ${String(s.parameters?._label ?? '') || s.action}`;
  // A node can't branch to itself, and Yes/No shouldn't point to the same
  // place — so each side hides the other side's current choice.
  const yesTargets = steps.filter((s) => uidOf(s) !== selfUid && uidOf(s) !== no);
  const noTargets = steps.filter((s) => uidOf(s) !== selfUid && uidOf(s) !== yes);

  const save = (clear = false) => {
    const params = { ...step.parameters };
    if (clear || (!yes && !no)) {
      delete params._branch;
    } else {
      params._branch = { contains, yes: yes || null, no: no || null };
    }
    onSave({ ...step, parameters: params });
    onClose();
  };

  const nameOf = (uid: string) => {
    const t = steps.find((s) => uidOf(s) === uid);
    return t ? labelOf(t) : 'the next step';
  };

  return (
    <Modal open title="Conditional branch — route by output" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="label">When the previous step's output contains…</label>
          <input
            className="input"
            value={contains}
            onChange={(e) => setContains(e.target.value)}
            placeholder="e.g. success, online, 200 OK"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label text-emerald-400">✓ Match — go to</label>
            <select className="input" value={yes} onChange={(e) => setYes(e.target.value)}>
              <option value="">the next step</option>
              {yesTargets.map((s) => (
                <option key={uidOf(s)} value={uidOf(s)}>
                  {labelOf(s)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label text-amber-400">✗ No match — go to</label>
            <select className="input" value={no} onChange={(e) => setNo(e.target.value)}>
              <option value="">the next step</option>
              {noTargets.map((s) => (
                <option key={uidOf(s)} value={uidOf(s)}>
                  {labelOf(s)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-surface-2 p-2.5 text-xs text-text-secondary">
          {contains.trim() ? (
            <>
              If the output contains <b className="text-text-primary">“{contains.trim()}”</b> →
              go to <b className="text-emerald-500">{nameOf(yes)}</b>; otherwise → go to{' '}
              <b className="text-amber-500">{nameOf(no)}</b>.
            </>
          ) : (
            <span className="text-text-muted">Enter the text to check for, above.</span>
          )}
        </div>
        <div className="flex justify-between">
          <button className="btn-ghost text-error" onClick={() => save(true)}>
            Remove branch
          </button>
          <div className="flex gap-2">
            <button className="btn-outline" onClick={onClose}>
              Cancel
            </button>
            <button className="btn-primary" onClick={() => save(false)}>
              Save branch
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
