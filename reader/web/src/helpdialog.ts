// the keys and gestures for what is on screen, opened with ? or a ? button: the shelves', the comic open's,
// or every one of them from the reading settings
import { esc } from "./dom";
import { type Context, type Entry, helpSections, helpTitles, type HowRead } from "./help";
import { picture } from "./helppictures";
import { defaults } from "./settings";

let open: (() => void) | null = null;

// a dialog of any kind is over the page: what is under it takes no keys while it is
export function dialogOpen(): boolean {
  return document.querySelector(".dialog-back") !== null;
}

// ? asked for, and not typed into a box
export function helpKey(event: KeyboardEvent): boolean {
  return event.key === "?" && !(event.target as HTMLElement).closest?.("input, select, textarea");
}

function keys(entry: Entry): string {
  return (entry.keys ?? []).map((combo) => combo.map((key) => `<kbd>${esc(key)}</kbd>`).join("+"))
    .join('<span class="help-or">or</span>');
}

function row(entry: Entry, zone: number): string {
  const what = entry.gesture
    ? `${picture(entry.gesture, zone)}<span>${esc(entry.how ?? "")}</span>`
    : `<span class="help-keys">${keys(entry)}</span>`;
  return `<div class="help-row"><div class="help-what">${what}</div><div class="help-does">${esc(entry.does)}</div></div>`;
}

export function openHelp(context: Context, how: HowRead = defaults): void {
  if (open) return;
  const back = document.createElement("div");
  back.className = "dialog-back";
  back.innerHTML = `
    <div class="dialog help" role="dialog" aria-modal="true" aria-label="${esc(helpTitles[context])}">
      <h2>${esc(helpTitles[context])}</h2>
      ${helpSections(context, how).map((section) => `
        <section><h3>${esc(section.title)}</h3>${section.entries.map((entry) => row(entry, how.zone)).join("")}</section>`).join("")}
      <div class="dialog-row end"><button data-act="close" class="primary">Done</button></div>
    </div>`;
  document.body.append(back);

  const close = () => {
    back.remove();
    window.removeEventListener("keydown", pressed, true);
    open = null;
  };
  // caught before anything under the dialog sees it: esc would otherwise also close the reader's menu, or
  // leave the comic altogether
  const pressed = (event: KeyboardEvent) => {
    if (event.key !== "Escape" && event.key !== "?") return;
    event.preventDefault();
    event.stopImmediatePropagation();
    close();
  };
  window.addEventListener("keydown", pressed, true);
  back.addEventListener("click", (event) => { if (event.target === back) close(); });
  // a tap on the dialog is not a tap on the page under it
  back.addEventListener("pointerdown", (event) => event.stopPropagation());
  const done = back.querySelector<HTMLButtonElement>('[data-act="close"]')!;
  done.onclick = close;
  done.focus();
  open = close;
}
