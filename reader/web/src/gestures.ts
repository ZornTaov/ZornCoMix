// touch and mouse on the page: a tap does what its side of the screen is for, a double tap in the middle
// zooms, two fingers zoom by how far they spread and carry the page along as they move. the paged view
// also has a sideways swipe to turn and one finger, or the mouse's left button, to pan a zoomed page or
// scroll one taller than the screen; the scrolled one leaves one finger to the browser's own scrolling. done by hand rather than left
// to the browser, which would zoom the whole page, menu and all, and turn nothing.
import { ZOOM_MAX, ZOOM_MIN } from "./layout";

export interface GestureHandlers {
  tap(x: number, y: number): void;
  // a second tap in the middle soon after the first: zoom in there, or back out
  doubleTap(x: number, y: number): void;
  // a first finger down: a swipe it ends in is judged against where the page was then
  start(): void;
  swipe(direction: "left" | "right"): void;
  // a one-finger drag on an unzoomed page: the stage scrolls by it
  drag(dx: number, dy: number): void;
  // a one-finger drag on a zoomed page
  pan(dx: number, dy: number): void;
  // two fingers, now spread to `scale` and between them at (x, y), having been at (fromX, fromY)
  pinch(scale: number, x: number, y: number, fromX: number, fromY: number): void;
  // the fingers lifted
  pinchEnd(): void;
  scale(): number;
  // whether a tap here is in the middle, where a double tap is waited for
  middle(x: number): boolean;
}

const TAP_SLOP = 10;
const SWIPE = 50;
const DOUBLE = 280;

// scrolls: the target is scrolled by the browser itself, with its own momentum, so one finger is left to
// it - neither captured, which would take a mouse off the scrollbar it is dragging, nor turned into swipes,
// which a zoomed strip panned sideways would be
export function attachGestures(target: HTMLElement, on: GestureHandlers, scrolls = false): () => void {
  const pointers = new Map<number, { x: number; y: number; startX: number; startY: number; at: number }>();
  let moved = false;
  // a second finger was down at some point since the first landed: a pinch or a two-finger drag, which
  // ends as neither a tap nor a swipe however its last finger lifts - a pinch let go at 1x, fingers sliding
  // sideways as they part, turned the page
  let twoFingers = false;
  let lastTap = 0;
  let pendingTap: number | undefined;

  const down = (event: PointerEvent) => {
    // a video's controls, or flash being played, take their own taps; capturing them here would turn the
    // page under a finger pressing play
    if ((event.target as Element).closest?.(".embed")) return;
    if (!scrolls) target.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY,
                                    at: performance.now() });
    // a second finger makes it a pinch, never a tap, whichever lifts first
    moved = pointers.size > 1;
    if (pointers.size > 1) twoFingers = true;
    else {
      twoFingers = false;
      on.start();
    }
  };

  const move = (event: PointerEvent) => {
    const held = pointers.get(event.pointerId);
    if (!held) return;
    const dx = event.clientX - held.x;
    const dy = event.clientY - held.y;
    held.x = event.clientX;
    held.y = event.clientY;
    if (Math.hypot(held.x - held.startX, held.y - held.startY) > TAP_SLOP) moved = true;
    if (scrolls || pointers.size !== 1 || !moved) return;
    if (on.scale() > 1.01) on.pan(dx, dy);
    // a mouse drags with its left button only: the capture above keeps a held left button from selecting
    // anything, so dragging it scrolls a page bigger than the screen as a finger does, where the middle
    // button is left to the browser's own autoscroll
    else if (event.pointerType !== "mouse" || event.buttons === 1) on.drag(dx, dy);
  };

  const up = (event: PointerEvent) => {
    const held = pointers.get(event.pointerId);
    pointers.delete(event.pointerId);
    if (!held || pointers.size > 0) return;
    const totalX = held.x - held.startX;
    const totalY = held.y - held.startY;
    if (!moved) {
      const now = performance.now();
      if (on.middle(held.x)) {
        // only the middle waits to see whether a second tap follows; a tap on either side turns at once
        if (now - lastTap < DOUBLE) {
          window.clearTimeout(pendingTap);
          lastTap = 0;
          on.doubleTap(held.x, held.y);
          return;
        }
        lastTap = now;
        const x = held.x, y = held.y;
        pendingTap = window.setTimeout(() => on.tap(x, y), DOUBLE);
        return;
      }
      lastTap = 0;
      on.tap(held.x, held.y);
      return;
    }
    // a zoomed page swipes as one bigger than the screen does: whether it turns is the handler's to say, by
    // whether the page was already at its edge
    if (!scrolls && !twoFingers && Math.abs(totalX) > SWIPE && Math.abs(totalX) > Math.abs(totalY) * 1.5
        && performance.now() - held.at < 600) {
      on.swipe(totalX < 0 ? "left" : "right");
    }
  };

  // the browser taking a finger over for its own scrolling: no tap, and nothing left held
  const cancel = (event: PointerEvent) => {
    pointers.delete(event.pointerId);
  };

  // two fingers, read from touches rather than pointers: a scrolled strip's browser takes its pointers for
  // its own scrolling, cancelling them, where touches keep coming - and a touch moved can be kept from
  // scrolling at all, which the strip needs while two fingers are zooming it
  let pinch: { distance: number; scale: number; x: number; y: number } | null = null;

  const between = (touches: TouchList) => {
    const [a, b] = [touches[0], touches[1]];
    return { distance: Math.max(1, Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)),
             x: (a.clientX + b.clientX) / 2, y: (a.clientY + b.clientY) / 2 };
  };

  const touchStart = (event: TouchEvent) => {
    if (event.touches.length !== 2) return;
    if ((event.target as Element).closest?.(".embed")) return;
    twoFingers = true;
    pinch = { ...between(event.touches), scale: on.scale() };
  };

  const touchMove = (event: TouchEvent) => {
    if (!pinch || event.touches.length !== 2) return;
    if (event.cancelable) event.preventDefault();
    const now = between(event.touches);
    // a pinch kept proportional to how far the fingers have spread since they landed, not added up a move
    // at a time, so a slow pinch and a fast one end at the same size
    const scale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, pinch.scale * now.distance / pinch.distance));
    on.pinch(scale, now.x, now.y, pinch.x, pinch.y);
    pinch.x = now.x;
    pinch.y = now.y;
  };

  // a finger lifted ends the pinch; one finger still down goes on as one finger
  const touchEnd = (event: TouchEvent) => {
    if (!pinch || event.touches.length === 2) return;
    pinch = null;
    on.pinchEnd();
  };

  target.addEventListener("pointerdown", down);
  target.addEventListener("pointermove", move);
  target.addEventListener("pointerup", up);
  target.addEventListener("pointercancel", cancel);
  target.addEventListener("touchstart", touchStart, { passive: true });
  target.addEventListener("touchmove", touchMove, { passive: false });
  target.addEventListener("touchend", touchEnd);
  target.addEventListener("touchcancel", touchEnd);
  return () => {
    window.clearTimeout(pendingTap);
    target.removeEventListener("pointerdown", down);
    target.removeEventListener("pointermove", move);
    target.removeEventListener("pointerup", up);
    target.removeEventListener("pointercancel", cancel);
    target.removeEventListener("touchstart", touchStart);
    target.removeEventListener("touchmove", touchMove);
    target.removeEventListener("touchend", touchEnd);
    target.removeEventListener("touchcancel", touchEnd);
  };
}
