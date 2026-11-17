// the parts of reading that are only arithmetic, kept apart from the page so they can be tested alone:
// which pages are shown together, which way a tap turns, which pages to have ready
import type { Carried, Page } from "./api";
import type { Fit, Settings } from "./settings";

// what is on screen at once: one page, or two side by side. a page drawn as a spread, a stand-in, and the
// first page of a chapter always start a view of their own, so a chapter never opens on the wrong side
export function views(pages: Page[], settings: Pick<Settings, "mode" | "coverAlone">, chapterStarts: number[] = []): number[][] {
  if (settings.mode !== "spread") return pages.map((_, at) => [at]);
  const starts = new Set(chapterStarts);
  const alone = (at: number) => {
    const page = pages[at];
    return page.standin || (page.w !== null && page.h !== null && page.w > page.h * 1.2);
  };
  const out: number[][] = [];
  let at = 0;
  if (settings.coverAlone && pages.length > 0) {
    out.push([0]);
    at = 1;
  }
  while (at < pages.length) {
    const next = at + 1;
    if (alone(at) || next >= pages.length || alone(next) || starts.has(next)) {
      out.push([at]);
      at += 1;
    } else {
      out.push([at, next]);
      at += 2;
    }
  }
  return out;
}

export function viewOf(shown: number[][], page: number): number {
  for (let at = 0; at < shown.length; at++) if (shown[at].includes(page)) return at;
  return Math.max(0, Math.min(page, shown.length - 1));
}

export type Action = "forward" | "back" | "menu";

// what a tap at x does. reading right to left, the left side goes forward, as a page turned in a printed
// manga does; swapping the zones flips that again for a reader holding the device in the other hand
export function tapAction(x: number, width: number, settings: Pick<Settings, "zone" | "swapZones" | "direction">): Action {
  const side = x < width * settings.zone ? "left" : x > width * (1 - settings.zone) ? "right" : "middle";
  if (side === "middle") return "menu";
  const leftGoesForward = (settings.direction === "rtl") !== settings.swapZones;
  return (side === "left") === leftGoesForward ? "forward" : "back";
}

// what a key does, the same way round as the taps: the arrows follow the reading direction, everything
// else - space, page down, a page-turner's buttons - always goes forward
// up and down are for moving the page a little, to put it just where it reads best: never a turn. shift
// with an arrow skips ahead or back by ten, the same way round as the arrow alone
export type KeyAction = Action | "first" | "last" | "up" | "down" | "ahead" | "behind" | "nextChapter" | "previousChapter";
export function keyAction(key: string, shift: boolean, direction: "ltr" | "rtl"): KeyAction | null {
  switch (key) {
    case "ArrowRight": return direction === "rtl" ? (shift ? "behind" : "back") : (shift ? "ahead" : "forward");
    case "ArrowLeft": return direction === "rtl" ? (shift ? "ahead" : "forward") : (shift ? "behind" : "back");
    case "]": return "nextChapter";
    case "[": return "previousChapter";
    case "ArrowDown": return "down";
    case "ArrowUp": return "up";
    case "PageDown": case "Enter": return "forward";
    case "PageUp": case "Backspace": return "back";
    case " ": return shift ? "back" : "forward";
    case "Home": return "first";
    case "End": return "last";
    case "m": case "Escape": return "menu";
    default: return null;
  }
}

// the pages to have fetched and decoded around a view, nearest first, so the next turn is instant
export function wanted(shown: number[][], view: number, ahead: number, behind: number): number[] {
  const out: number[] = [];
  for (let step = 1; step <= Math.max(ahead, behind); step++) {
    if (step <= ahead && view + step < shown.length) out.push(...shown[view + step]);
    if (step <= behind && view - step >= 0) out.push(...shown[view - step]);
  }
  return out;
}

// the page whose top is the last at or above y, among pages whose tops only ever go down the strip: found
// by halving, so it is quick however long the comic
export function pageAt(tops: { length: number; at(n: number): number }, y: number): number {
  let low = 0;
  let high = tops.length - 1;
  if (high < 0) return 0;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (tops.at(middle) <= y) low = middle;
    else high = middle - 1;
  }
  return low;
}

export interface Placed {
  tops: Float64Array;
  heights: Float64Array;
  widths: Float64Array;
  total: number;
  widest: number;
}

// where a page of a scrolled comic starts across: centred on the screen, or from its left edge when wider. a
// comic's one panorama several screens wide, centring every page in the strip as wide as it, left every
// other page off the screen to the right as the strip opens at its left edge
export function stripLeft(width: number, screen: number): number {
  return Math.max(0, (screen - width) / 2);
}

// where every page of a scrolled comic sits, worked out from the sizes the server measured rather than read
// back from the page: the four fits as the paged view has them, in `room` pixels across and `screen` tall.
// a page the server could not measure is given 40% of a screen until its picture says otherwise. `gap` is
// left empty above and below every page. `zoom` makes every page that much bigger whatever the fit, the gap
// between them left as it is
export function placeStrip(pages: { w: number | null; h: number | null }[], fit: Fit, room: number, screen: number,
                           gap = 0, zoom = 1): Placed {
  const count = pages.length;
  const placed: Placed = { tops: new Float64Array(count), heights: new Float64Array(count),
                           widths: new Float64Array(count), total: 0, widest: 0 };
  let y = 0;
  for (let n = 0; n < count; n++) {
    const { w, h } = pages[n];
    let width: number;
    let height: number;
    if (!w || !h) {
      width = room;
      height = screen * 0.4;
    } else if (fit === "width") {
      width = room;
      height = room * h / w;
    } else if (fit === "screen") {
      width = Math.min(room, screen * w / h);
      height = width * h / w;
    } else if (fit === "height") {
      height = screen;
      width = screen * w / h;
    } else {
      width = w;
      height = h;
    }
    width *= zoom;
    height *= zoom;
    y += gap;
    placed.tops[n] = y;
    placed.heights[n] = height;
    placed.widths[n] = width;
    placed.widest = Math.max(placed.widest, width);
    y += height + gap;
  }
  placed.total = y;
  return placed;
}

// a page zoomed by hand: drawn `scale` times its size, moved `x` and `y` from where it would be unzoomed
export interface Zoom { scale: number; x: number; y: number }
export const ZOOM_MIN = 1;
export const ZOOM_MAX = 6;

// whether a picture `natural` pixels wide, drawn `shown` css pixels wide on a screen of `dpr` device pixels
// to each, is drawn bigger than it is: a page shown at its own size on a screen scaled to 150% is already
// stretched half again. a hair over is not, or a page fitted to within a rounding of its size would flip
// between the two as it is drawn. a picture still arriving has no size yet, and is not
export function enlarged(shown: number, natural: number, dpr: number): boolean {
  return natural > 0 && shown * dpr > natural * 1.01;
}

// the fingers moved from `from` to `to` and spread to `scale`: whatever was under them stays under them,
// so a pinch zooms where it is made and a two-finger drag carries the page along with it. points are
// measured from the page's own corner as it would be unzoomed
export function pinched(zoom: Zoom, scale: number, from: { x: number; y: number }, to: { x: number; y: number }): Zoom {
  const k = scale / zoom.scale;
  return { scale, x: to.x - k * (from.x - zoom.x), y: to.y - k * (from.y - zoom.y) };
}

// whether a sideways swipe turns the page. one wider than the screen - a long strip at its actual size - is
// dragged across before a swipe turns it: a flick that scrolled it was reading it, and only one begun with
// the page already at its edge, nowhere left to go that way, turns. `from` is how far across it was scrolled
// as the finger came down, `furthest` how far it can be; a finger moved left pulls its right-hand side in
export function swipeTurns(direction: "left" | "right", from: number, furthest: number): boolean {
  if (furthest <= 4) return true;
  return direction === "left" ? from >= furthest - 4 : from <= 4;
}

// how far a zoomed page may be moved along one side, the least and the most: one bigger than the screen no
// further than leaves its edge at the screen's, so it is never pushed off to show nothing; one smaller kept
// on the screen. `start` is where its unzoomed corner is on the screen, `size` its unzoomed size, `screen`
// the screen's
export function panRange(scale: number, start: number, size: number, screen: number): [number, number] {
  const a = 0 - start;
  const b = screen - start - size * scale;
  return [Math.min(a, b), Math.max(a, b)];
}

// a page bigger than the screen both ways is read as text is: along a row, then down a screen and back to the
// start of the next, and only past the end of the last row turned. `at` is how far it is scrolled and
// `furthest` how far it can be, `step` how far one move goes; a row starts on the left reading left to
// right, on the right reading right to left. where to move to, or null once there is nowhere left to go
export function zigzag(at: { x: number; y: number }, furthest: { x: number; y: number }, step: { x: number; y: number },
                       forward: boolean, rtl: boolean): { x: number; y: number } | null {
  const clampX = (x: number) => Math.min(furthest.x, Math.max(0, x));
  const rowStart = rtl ? furthest.x : 0;
  const rowEnd = rtl ? 0 : furthest.x;
  const along = rtl ? -1 : 1;
  if (forward) {
    if (Math.abs(at.x - rowEnd) > 4) return { x: clampX(at.x + along * step.x), y: at.y };
    if (at.y < furthest.y - 4) return { x: rowStart, y: Math.min(furthest.y, at.y + step.y) };
    return null;
  }
  if (Math.abs(at.x - rowStart) > 4) return { x: clampX(at.x - along * step.x), y: at.y };
  if (at.y > 4) return { x: rowEnd, y: Math.max(0, at.y - step.y) };
  return null;
}

// the chapter a page is in
export function chapterOf(starts: number[], page: number): number {
  let found = -1;
  for (let at = 0; at < starts.length; at++) if (starts[at] <= page) found = at;
  return found;
}

export interface Bookmark {
  title: string;
  start: number;
  mine: boolean;
}

// what the bookmarks menu offers: what the comic's archives bookmark - a chapter's name on its first page - and
// the pages marked in the reader, in page order. a page both is one entry, under the archive's name and marked
// as yours, so taking your mark off it leaves the archive's
export function bookmarkList(carried: Carried[], marked: number[]): Bookmark[] {
  const mine = new Set(marked);
  const list: Bookmark[] = carried.map((each) => ({ title: each.title, start: each.start, mine: mine.has(each.start) }));
  const named = new Set(carried.map((each) => each.start));
  for (const start of marked) if (!named.has(start)) list.push({ title: `Page ${start + 1}`, start, mine: true });
  return list.sort((a, b) => a.start - b.start);
}

// the page a jump to the next or the previous chapter lands on, or null where that chapter is not in this
// comic at all - past its last, or before its first - and is the comic either side, as a comic packed one
// archive per chapter has it: a comic with no chapters inside it is one chapter from its first page. back
// goes to the start of the chapter being read first, as a player's back goes to the start of the track,
// and only from there to the one before
export function chapterTarget(chapterStarts: number[], page: number, forward: boolean): number | null {
  const starts = chapterStarts.length ? chapterStarts : [0];
  const at = chapterOf(starts, page);
  if (forward) return at + 1 < starts.length ? starts[at + 1] : null;
  if (at >= 0 && page > starts[at]) return starts[at];
  if (at >= 1) return starts[at - 1];
  // pages before the first chapter - a cover, a foreword - are where back goes from the first chapter's start
  return at === 0 && starts[0] > 0 ? 0 : null;
}

// a comic opened at random is only tried until it is really being read: its place is kept once this many
// pages of it have been seen, or its last one has, so one looked at and put down never joins what is being read
export const TRIAL_PAGES = 5;

export function trialKept(seen: number, at: number, pages: number): boolean {
  return seen >= TRIAL_PAGES || at >= pages - 1;
}

// the page a typed page number means: counted from one as the reader sees them, kept within the comic.
// null for anything that is not a number, which leaves the reader where it is
export function typedPage(text: string, count: number): number | null {
  const n = Number.parseInt(text.trim(), 10);
  if (!Number.isFinite(n) || count < 1) return null;
  return Math.max(0, Math.min(count - 1, n - 1));
}
