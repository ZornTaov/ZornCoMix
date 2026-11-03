// the help's gesture pictures, drawn here rather than taken from an icon set: the sides of the screen are
// drawn at the width the reader's own tap zones are set to, which no stock picture could show. lines are
// the text's colour and a finger the accent, so they read on the light dialog and the dark alike
import type { Gesture } from "./help";

const FINGER = 'fill="var(--accent)" stroke="none"';

// a screen, upright, with the part tapped shaded: `zone` is the share of its width each side takes
function screen(zone: number, part: "left" | "right" | "middle"): string {
  const x = 12, y = 4, w = 24, h = 40;
  // to a hundredth, or 0.4 of the width comes out as 9.600000000000001
  const side = Math.round(Math.max(2, Math.min(w / 2 - 2, w * zone)) * 100) / 100;
  const [from, width] = part === "left" ? [x, side] : part === "right" ? [x + w - side, side] : [x + side, w - 2 * side];
  return `<rect x="${from}" y="${y}" width="${width}" height="${h}" fill="var(--accent)" opacity=".28" stroke="none"/>`
    + `<line x1="${x + side}" y1="${y}" x2="${x + side}" y2="${y + h}" stroke-dasharray="2 2" opacity=".6"/>`
    + `<line x1="${x + w - side}" y1="${y}" x2="${x + w - side}" y2="${y + h}" stroke-dasharray="2 2" opacity=".6"/>`
    + `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3"/>`
    + `<circle cx="${from + width / 2}" cy="24" r="3.2" ${FINGER}/>`;
}

// an arrow from (x1, y1) to (x2, y2), its head at the end
function arrow(x1: number, y1: number, x2: number, y2: number): string {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = (turn: number) => `${x2 - 5 * Math.cos(angle + turn)},${y2 - 5 * Math.sin(angle + turn)}`;
  return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/><polyline points="${head(0.5)} ${x2},${y2} ${head(-0.5)}"/>`;
}

function drawing(gesture: Gesture, zone: number): string {
  switch (gesture) {
    case "zoneLeft": return screen(zone, "left");
    case "zoneRight": return screen(zone, "right");
    case "zoneMiddle": return screen(zone, "middle");
    case "doubleTap":
      return `<rect x="12" y="4" width="24" height="40" rx="3"/><circle cx="24" cy="24" r="3.2" ${FINGER}/>`
        + '<circle cx="24" cy="24" r="6.5" opacity=".7"/><circle cx="24" cy="24" r="10" opacity=".4"/>';
    case "swipeLeft": return arrow(36, 24, 10, 24) + `<circle cx="36" cy="24" r="3.6" ${FINGER}/>`;
    case "swipeRight": return arrow(12, 24, 38, 24) + `<circle cx="12" cy="24" r="3.6" ${FINGER}/>`;
    case "pinch":
      return arrow(20, 28, 9, 39) + arrow(28, 20, 39, 9)
        + `<circle cx="20" cy="28" r="3.6" ${FINGER}/><circle cx="28" cy="20" r="3.6" ${FINGER}/>`;
    case "drag":
      return arrow(24, 24, 24, 6) + arrow(24, 24, 24, 42) + arrow(24, 24, 6, 24) + arrow(24, 24, 42, 24)
        + `<circle cx="24" cy="24" r="3.6" ${FINGER}/>`;
    case "scroll":
      return '<rect x="12" y="4" width="24" height="40" rx="3" opacity=".5"/>' + arrow(24, 24, 24, 8) + arrow(24, 24, 24, 40)
        + `<circle cx="24" cy="24" r="3.6" ${FINGER}/>`;
    case "wheel":
      return '<rect x="14" y="6" width="20" height="34" rx="10"/><line x1="14" y1="20" x2="34" y2="20"/>'
        + '<line x1="24" y1="6" x2="24" y2="20"/>'
        + `<rect x="21.5" y="9" width="5" height="8" rx="2.5" ${FINGER}/>`;
    case "click":
      // a cover on the shelf, pressed
      return '<rect x="10" y="4" width="22" height="32" rx="2"/><line x1="10" y1="40" x2="26" y2="40"/>'
        + `<circle cx="27" cy="29" r="3.6" ${FINGER}/><circle cx="27" cy="29" r="7" opacity=".5"/>`;
  }
}

export function picture(gesture: Gesture, zone: number): string {
  return `<svg class="help-picture" viewBox="0 0 48 48" width="48" height="48" aria-hidden="true" fill="none" `
    + `stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawing(gesture, zone)}</svg>`;
}
