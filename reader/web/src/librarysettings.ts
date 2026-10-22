// how the library's shelves are drawn, kept on the server once for every device, apart from how a comic is
// read: those are kept per comic and series, and a shelf is neither
import { api } from "./api";
import { el, refusal } from "./dom";

export interface LibrarySettings {
  // how many days a comic that gained pages stays under "recently updated"; 0 leaves the shelf out
  recentDays: number;
  // a comic read to its end since it grew - its new pages read - is taken off "recently updated" at once,
  // rather than staying there with nothing left to read until its days are up
  clearRead: boolean;
}

export const libraryDefaults: LibrarySettings = { recentDays: 14, clearRead: false };

export const MAX_RECENT_DAYS = 365;

// only what this version knows, at sensible values, whatever an older or newer page stored
export function cleanLibrary(given: Partial<LibrarySettings> | null | undefined): LibrarySettings {
  const out = { ...libraryDefaults };
  if (!given) return out;
  if (typeof given.recentDays === "number" && Number.isFinite(given.recentDays)) {
    out.recentDays = Math.min(MAX_RECENT_DAYS, Math.max(0, Math.round(given.recentDays)));
  }
  if (typeof given.clearRead === "boolean") out.clearRead = given.clearRead;
  return out;
}

// the library's settings, each saved as it is changed, as the reading settings are
export function openLibrarySettings(current: LibrarySettings, changed: (settings: LibrarySettings) => void): void {
  let settings = { ...current };
  const back = el("div", "dialog-back");
  back.innerHTML = `
    <div class="dialog" role="dialog" aria-modal="true" aria-label="Library settings">
      <h2>Library settings</h2>
      <div class="dialog-row">
        <label>Keep comics under <i>Recently updated</i> for
          <input type="number" name="recentDays" min="0" max="${MAX_RECENT_DAYS}" step="1" inputmode="numeric"> days</label>
      </div>
      <p class="muted">0 leaves the shelf out.</p>
      <div class="dialog-row">
        <label><input type="checkbox" name="clearRead"> Reading a comic's new pages takes it off <i>Recently updated</i></label>
      </div>
      <p class="form-message" role="status"></p>
      <div class="dialog-row end"><button data-act="close" class="primary">Done</button></div>
    </div>`;
  document.body.append(back);
  const dialog = back.querySelector<HTMLElement>(".dialog")!;
  const days = dialog.querySelector<HTMLInputElement>('[name="recentDays"]')!;
  const clearRead = dialog.querySelector<HTMLInputElement>('[name="clearRead"]')!;
  const message = dialog.querySelector<HTMLElement>(".form-message")!;
  days.value = String(settings.recentDays);
  clearRead.checked = settings.clearRead;

  async function save(changes: Partial<LibrarySettings>) {
    settings = cleanLibrary({ ...settings, ...changes });
    changed(settings);
    try {
      await api.saveLibrarySettings(settings);
      message.textContent = "";
    } catch (error) {
      message.textContent = refusal(error);
    }
  }

  // a box half typed in is not saved; what was typed is put right once it is left
  days.addEventListener("change", () => {
    if (days.value.trim() === "" || !Number.isFinite(Number(days.value))) {
      days.value = String(settings.recentDays);
      return;
    }
    save({ recentDays: Number(days.value) }).then(() => { days.value = String(settings.recentDays); });
  });
  clearRead.addEventListener("change", () => save({ clearRead: clearRead.checked }));

  function close() {
    back.remove();
    window.removeEventListener("keydown", keys);
  }
  const keys = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
  window.addEventListener("keydown", keys);
  back.addEventListener("click", (event) => { if (event.target === back) close(); });
  dialog.querySelector<HTMLButtonElement>('[data-act="close"]')!.onclick = close;
  days.focus();
}
