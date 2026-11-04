// what the keys and gestures do, written down once as data, so the help for the shelves, for the comic open
// and for everything at once are three views of one list and cannot disagree. the reader's is worked out for
// the way it is being read: the arrows and the sides of the screen as they go now, and only what the mode
// open has - a scrolled comic is scrolled the browser's own way, with no swipes of its own, though it zooms
// as a page does
import type { Settings } from "./settings";

export type Context = "library" | "reader" | "all";

// what a gesture's picture shows (helppictures.ts)
export type Gesture = "zoneLeft" | "zoneRight" | "zoneMiddle" | "doubleTap" | "swipeLeft" | "swipeRight" | "pinch"
  | "drag" | "scroll" | "wheel" | "click";

export interface Entry {
  // each a way of doing it: one key, or keys held together
  keys?: string[][];
  gesture?: Gesture;
  // said beside the picture, what is done with the finger or the mouse
  how?: string;
  does: string;
}

export interface Section {
  title: string;
  entries: Entry[];
}

export type HowRead = Pick<Settings, "mode" | "direction" | "swapZones" | "zone">;

// how a key is written on its key: the name keyAction is handed, as it reads on a keyboard
const LABELS: Record<string, string> = {
  ArrowRight: "→", ArrowLeft: "←", ArrowUp: "↑", ArrowDown: "↓", " ": "Space", PageDown: "Page Down",
  PageUp: "Page Up", Escape: "Esc", m: "M", f: "F",
};
export function keyLabel(key: string): string {
  return LABELS[key] ?? key;
}

const HELP: Entry = { keys: [["?"]], does: "Show the keys and gestures for what is on screen" };

function library(): Section[] {
  return [{
    title: "The shelves",
    entries: [
      { gesture: "click", how: "Tap or click a comic", does: "Open it where you left it - one read through that has since grown opens on its first new page" },
      { gesture: "click", how: "Tap or click a folder or series", does: "Go into it" },
      { gesture: "click", how: "Tap or click ⋯ on a cover", does: "Read from the start, mark read or unread, edit its ComicInfo or cover" },
      { keys: [["Esc"]], does: "Close a ⋯ menu" },
      HELP,
    ],
  }];
}

// which side of the screen goes forward: the right reading left to right, the left reading right to left,
// and the other way round again with the zones swapped - as tapAction has it
export function leftGoesForward(how: Pick<HowRead, "direction" | "swapZones">): boolean {
  return (how.direction === "rtl") !== how.swapZones;
}

// the arrow that goes on, and the one that goes back, as keyAction has them
function arrows(direction: "ltr" | "rtl"): { on: string; back: string } {
  return direction === "rtl" ? { on: "←", back: "→" } : { on: "→", back: "←" };
}

function readerKeys(how: HowRead): Entry[] {
  const { on, back } = arrows(how.direction);
  const scrolling = how.mode === "webtoon";
  return [
    { keys: [[on], ["Space"], ["Page Down"], ["Enter"]],
      does: scrolling ? "Down a screen - at the very end, on into the next chapter" : "Next page" },
    { keys: [[back], ["Shift", "Space"], ["Page Up"], ["Backspace"]],
      does: scrolling ? "Up a screen - at the very top, back into the chapter before" : "Previous page" },
    { keys: [["Shift", on]], does: "Ten pages on" },
    { keys: [["Shift", back]], does: "Ten pages back" },
    { keys: [["]"]], does: "Next chapter" },
    { keys: [["["]], does: "Start of this chapter - from there, the chapter before" },
    { keys: [["Home"]], does: "First page" },
    { keys: [["End"]], does: "Last page" },
    { keys: [["↓"], ["↑"]],
      does: scrolling ? "Scroll a little, gliding while held" : "Move a page taller than the screen, or a zoomed one, a little" },
    { keys: [["M"]], does: "Show or hide the menu" },
    { keys: [["Esc"]], does: "Close the menu - with it closed, back to the library" },
    { keys: [["F"]], does: "Full screen" },
    HELP,
  ];
}

function sides(how: HowRead, forward: string, backward: string): Entry[] {
  const left = leftGoesForward(how);
  return [
    { gesture: left ? "zoneLeft" : "zoneRight", how: `Tap or click the ${left ? "left" : "right"} side`, does: forward },
    { gesture: left ? "zoneRight" : "zoneLeft", how: `Tap or click the ${left ? "right" : "left"} side`, does: backward },
    { gesture: "zoneMiddle", how: "Tap or click the middle", does: "Show or hide the menu" },
  ];
}

function pagedGestures(how: HowRead): Entry[] {
  // a swipe goes on the way the page would be pulled: leftward reading left to right
  const onSwipe = how.direction === "rtl" ? "swipeRight" : "swipeLeft";
  const backSwipe = how.direction === "rtl" ? "swipeLeft" : "swipeRight";
  return [
    ...sides(how, "Next page", "Previous page"),
    { gesture: "doubleTap", how: "Double-tap the middle", does: "Zoom in there, or back out" },
    { gesture: onSwipe, how: `Swipe ${onSwipe === "swipeLeft" ? "left" : "right"}`, does: "Next page" },
    { gesture: backSwipe, how: `Swipe ${backSwipe === "swipeLeft" ? "left" : "right"}`, does: "Previous page" },
    { gesture: "pinch", how: "Pinch, or drag with two fingers", does: "Zoom in or out, or move with the fingers" },
    { gesture: "drag", how: "Drag", does: "Move around a zoomed page, or down one taller than the screen" },
    { gesture: "wheel", how: "Mouse wheel", does: "Turn the page - a page taller than the screen is scrolled to its end first" },
  ];
}

function scrollGestures(how: HowRead): Entry[] {
  return [
    ...sides(how, "Down a screen", "Up a screen"),
    { gesture: "doubleTap", how: "Double-tap the middle", does: "Zoom in there, or back out" },
    { gesture: "pinch", how: "Pinch, or drag with two fingers", does: "Zoom in or out, or move with the fingers" },
    { gesture: "scroll", how: "Scroll, or drag with a finger", does: "Move through the comic, every page one under the next - and across it, zoomed" },
  ];
}

function reader(how: HowRead): Section[] {
  const mode = how.mode === "webtoon" ? "Scroll" : how.mode === "spread" ? "Two pages" : "One page";
  return [
    { title: `Keys - ${mode}, ${how.direction === "rtl" ? "right to left" : "left to right"}`, entries: readerKeys(how) },
    { title: "Touch and mouse", entries: how.mode === "webtoon" ? scrollGestures(how) : pagedGestures(how) },
  ];
}

// everything, whichever way a comic is read: the keys as they go now, with the other direction said
function all(how: HowRead): Section[] {
  const { on, back } = arrows(how.direction);
  const other = how.direction === "rtl" ? "left to right" : "right to left";
  return [
    ...library(),
    { title: "Reading - keys", entries: [
      ...readerKeys({ ...how, mode: "single" }),
      { keys: [[back], [on]], does: `Reading ${other}, the arrows swap: the comic's own direction is in the menu` },
    ] },
    { title: "Reading - One page and Two pages", entries: pagedGestures(how) },
    { title: "Reading - Scroll, where the keys that turn a page scroll a screen", entries: scrollGestures(how) },
  ];
}

export function helpSections(context: Context, how: HowRead): Section[] {
  if (context === "library") return library();
  if (context === "reader") return reader(how);
  return all(how);
}

export const helpTitles: Record<Context, string> = {
  library: "Keys and gestures - the shelves",
  reader: "Keys and gestures - reading",
  all: "Every key and gesture",
};
