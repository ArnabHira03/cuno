import type { Action } from 'svelte/action';

/**
 * Touch handling for the player's hand (touch pointers only; mouse and pen keep the
 * desktop hover + click behaviour).
 *
 * - Touching a card lifts it; sliding a finger across the hand moves the lift to
 *   whichever card is under the finger.
 * - Tapping the card that is already lifted calls `ontap` (which plays it).
 * - The browser's synthetic click after a touch is swallowed so a single tap never
 *   plays a card through `Card`'s own onclick.
 *
 * Cards are found from the finger's x position (slot `step` widths from the left of
 * the row), not by hit-testing, so the lifted card moving up does not cause jitter.
 */
export type TouchHandParams = {
  count: number;
  step: number;
  lifted: number | null; // index of the lifted card, if any
  onlift: (index: number) => void;
  ontap: (index: number) => void;
  onclear: () => void;
};

const TAP_SLOP = 10; // px a finger may move and still count as a tap
const GHOST_CLICK_MS = 600;

export const touchHand: Action<HTMLElement, TouchHandParams> = (node, initial) => {
  let p = initial;
  let pointerId: number | null = null;
  let startX = 0;
  let startY = 0;
  let lastX = 0;
  let moved = false;
  let downIndex = -1;
  let wasLifted = false;
  let current = -1;
  let frame = 0;
  let suppressClicksUntil = 0;

  const indexAt = (x: number) => {
    if (p.count <= 0) return -1;
    const left = node.getBoundingClientRect().left;
    const i = Math.floor((x - left) / Math.max(p.step, 1));
    return Math.max(0, Math.min(p.count - 1, i));
  };

  const lift = (i: number) => {
    if (i < 0 || i === current) return;
    current = i;
    p.onlift(i);
  };

  const onDown = (e: PointerEvent) => {
    if (e.pointerType !== 'touch' || !e.isPrimary) return;
    pointerId = e.pointerId;
    startX = lastX = e.clientX;
    startY = e.clientY;
    moved = false;
    downIndex = indexAt(e.clientX);
    wasLifted = downIndex >= 0 && downIndex === p.lifted;
    current = p.lifted ?? -1;
    lift(downIndex);
    // Keep receiving moves even if the finger drifts above or below the row.
    try {
      node.setPointerCapture(e.pointerId);
    } catch {
      /* not capturable; moves still arrive while over the row */
    }
  };

  const onMove = (e: PointerEvent) => {
    if (e.pointerId !== pointerId) return;
    lastX = e.clientX;
    if (!moved && Math.hypot(e.clientX - startX, e.clientY - startY) > TAP_SLOP) moved = true;
    if (!frame) {
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (pointerId !== null) lift(indexAt(lastX));
      });
    }
  };

  const end = (e: PointerEvent, cancelled: boolean) => {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
    suppressClicksUntil = performance.now() + GHOST_CLICK_MS;
    if (frame) {
      cancelAnimationFrame(frame);
      frame = 0;
    }
    if (!cancelled && !moved && wasLifted && indexAt(e.clientX) === downIndex) p.ontap(downIndex);
  };
  const onUp = (e: PointerEvent) => end(e, false);
  const onCancel = (e: PointerEvent) => end(e, true);

  // Swallow the click the browser synthesises after a touch; keyboard clicks still pass.
  const onClick = (e: MouseEvent) => {
    if (performance.now() < suppressClicksUntil) {
      e.preventDefault();
      e.stopPropagation();
    }
  };

  // A touch anywhere outside the hand drops the lift.
  const onDocDown = (e: PointerEvent) => {
    if (e.pointerType !== 'touch') return;
    if (e.target instanceof Node && node.contains(e.target)) return;
    current = -1;
    p.onclear();
  };

  node.addEventListener('pointerdown', onDown);
  node.addEventListener('pointermove', onMove);
  node.addEventListener('pointerup', onUp);
  node.addEventListener('pointercancel', onCancel);
  node.addEventListener('click', onClick, true);
  document.addEventListener('pointerdown', onDocDown, true);

  return {
    update(next) {
      p = next;
      current = p.lifted ?? -1;
    },
    destroy() {
      if (frame) cancelAnimationFrame(frame);
      node.removeEventListener('pointerdown', onDown);
      node.removeEventListener('pointermove', onMove);
      node.removeEventListener('pointerup', onUp);
      node.removeEventListener('pointercancel', onCancel);
      node.removeEventListener('click', onClick, true);
      document.removeEventListener('pointerdown', onDocDown, true);
    },
  };
};
