/**
 * Tiny cross-component navigation guard.
 *
 * A page (e.g. the Test Designer) registers a predicate that returns `true`
 * when it's safe to navigate away — typically after a confirm() when there are
 * unsaved edits. The Sidebar consults it before following a link. This avoids a
 * full data-router migration just to get a leave prompt.
 */
let guard: (() => boolean) | null = null;

export function setNavGuard(predicate: (() => boolean) | null): void {
  guard = predicate;
}

/** True when navigation may proceed. Calling it may show a confirm dialog. */
export function canLeave(): boolean {
  return guard ? guard() : true;
}
