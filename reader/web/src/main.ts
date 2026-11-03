// three screens, chosen by the address: #/browse/<how>/<where> is the library, #/read/<comic>[/<page>][/try] a
// comic open for reading - /try one picked at random, whose place is kept only once it is really read - and
// #/info/<comic>[/edit] what a comic is and where it came from, /edit with its form open, so the back button and
// a bookmark all do what they should
import "./style.css";
import { esc } from "./dom";
import { openInfo } from "./info";
import { browseHash, openLibrary, rememberedBrowse } from "./library";
import { openReader } from "./reader";
import { type Route, screens } from "./routing";
import type { Browse } from "./shelves";
import { watchUnderway } from "./underway";

const root = document.getElementById("app")!;
let close: () => void = () => undefined;
// where the library was when a comic was opened, so closing it goes back there rather than to the top
let lastBrowse = "";
// whether anything was shown before this screen: an info page opened from a bookmark has nowhere to go back
// to in this page's history, and goes to the library instead
let shownBefore = false;
const begin = screens();

async function route() {
  close();
  close = () => undefined;
  const now = begin();
  const box = boxFor(now);
  const reading = location.hash.match(/^#\/read\/([0-9a-f]+)(?:\/(\d+))?(\/try)?/);
  const browsing = location.hash.match(/^#\/browse\/(folder|series|author|all)(?:\/(.*))?$/);
  const about = location.hash.match(/^#\/info\/([0-9a-f]+)(\/edit)?/);
  const cameFrom = shownBefore;
  shownBefore = true;
  try {
    if (about) {
      document.body.classList.remove("reading");
      const opened = now.keep(await openInfo(box, about[1], () => {
        if (cameFrom) history.back();
        else location.hash = lastBrowse || browseHash(rememberedBrowse());
      }, about[2] !== undefined));
      if (!opened) return;
      close = opened;
      // the form is opened once: coming back to the page, or reloading it, shows the comic as it is
      if (about[2] !== undefined) history.replaceState(null, "", `#/info/${about[1]}`);
    } else if (reading) {
      document.body.classList.add("reading");
      const opened = now.keep(await openReader(box, reading[1], reading[2] !== undefined ? Number(reading[2]) - 1 : null,
                                               () => { location.hash = lastBrowse || browseHash(rememberedBrowse()); },
                                               reading[3] !== undefined));
      // nor is the address rewritten: it is a later route's now
      if (!opened) return;
      close = opened;
      // a page in the address is where to open, once: coming back to it - from the info page - opens the
      // comic where it was left, not on that page again. a trial stays one until the reader keeps its place
      if (reading[2] !== undefined) history.replaceState(null, "", `#/read/${reading[1]}${reading[3] ?? ""}`);
    } else if (browsing) {
      document.body.classList.remove("reading");
      lastBrowse = location.hash;
      const opened = now.keep(await openLibrary(box, browsing[1] as Browse, browsing[2] ? decodeURIComponent(browsing[2]) : "",
                                                (id, at, trial = false) => {
                                                  location.hash = `#/read/${id}${at === null ? "" : `/${at + 1}`}${trial ? "/try" : ""}`;
                                                }));
      if (!opened) return;
      close = opened;
    } else {
      location.replace(browseHash(rememberedBrowse()));
    }
  } catch (error) {
    // a screen that failed after the address moved on says nothing over the one that is there now
    if (now.stale()) return;
    root.innerHTML = `<p class="empty">Something went wrong: ${esc(String(error))}. <a href="#/">Back to the library</a></p>`;
  }
}

// each route's screen draws into a box of its own, which takes the page the first time it is drawn into - the
// screen before stays until then, so the library is still shown while a comic opens. a box whose route has
// been overtaken by then is dropped instead, so a screen opened for an address since left never shows
function boxFor(now: Route): HTMLElement {
  const box = document.createElement("div");
  box.className = "screen";
  root.append(box);
  const drawn = new MutationObserver(() => {
    drawn.disconnect();
    if (now.stale()) box.remove();
    // the others taken away around it, never the box itself: taken off the page and put back, a strip
    // already scrolled to where the comic was left would be back at its top
    else for (const other of [...root.childNodes]) if (other !== box) other.remove();
  });
  drawn.observe(box, { childList: true });
  return box;
}

window.addEventListener("hashchange", route);
route();
// an edit begun before this page was opened, or before it was reloaded, is still shown going
watchUnderway();
