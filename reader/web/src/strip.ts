// scrolling through a comic, one page under the next, however many thousands of pages it has. every page's
// place is worked out from the sizes the server measured (placeStrip), so the strip is one tall empty box
// with only the pages near the screen actually in it - a dozen or so elements, not one per page - each set
// at its worked-out place. a page coming into reach is put in; one far enough away is taken out again, its
// picture with it. nothing on screen ever moves when either happens, since no page's place depends on
// another being there.
import type { Page } from "./api";
import { pageAt, pinched, type Placed, placeStrip, stripLeft, type Zoom, ZOOM_MAX, ZOOM_MIN } from "./layout";
import type { Fit } from "./settings";

export interface StripHooks {
  // the page's picture, fetched and decoding
  picture(n: number): HTMLImageElement;
  // the page has left reach: its picture can go
  release(n: number): void;
  // a page that is a video or flash is on screen: show the real thing in its place, while wanted() holds
  play(n: number, holder: HTMLElement, wanted: () => boolean): void;
  // the page being read has changed
  reading(n: number): void;
  // the strip has moved at all, even within one page: the place kept is how far down the page too
  moved(): void;
}

// pages are put in within two screens of what is shown, and taken out beyond four: the gap between the two
// keeps a page near the edge from being dropped and fetched again as the reader scrolls back and forth
const REACH = 2;
const KEEP = 4;
// a player starts once this much of its page is on screen, and stops once less is
const SHOWING = 0.25;

export class Strip {
  private content: HTMLElement;
  private held = new Map<number, HTMLElement>();
  private playing = new Set<number>();
  private placed: Placed;
  // the page at the top of the screen and how far down it the screen starts, as a share of the page, so
  // the same place is kept when the window or the fit changes every page's size
  private anchor = { n: 0, part: 0 };
  private current = -1;
  // nothing is said about which page is being read until the strip has been put on one: laying it out
  // starts at the top, and that is not where the reader is
  private placedOnPage = false;
  private frame = 0;
  private watcher: ResizeObserver;
  private fit: Fit = "width";
  private padding = 0;
  private gap = 0;
  // zoomed by hand: every page laid out this much bigger, the strip then wider than the screen and scrolled
  // sideways as well as down, by the browser's own scrolling
  private zoom = 1;
  // a pinch under way is the strip as it is laid out, drawn bigger: laying out thousands of pages again at
  // every move of the fingers would stutter. it is laid out at the new size once they lift
  private preview: Zoom = { scale: 1, x: 0, y: 0 };
  private fingers = { x: 0, y: 0 };

  constructor(private scroller: HTMLElement, private pages: Page[], private hooks: StripHooks) {
    this.content = document.createElement("div");
    this.content.className = "strip-content";
    scroller.replaceChildren(this.content);
    this.placed = placeStrip(pages, this.fit, 1, 1);
    scroller.addEventListener("scroll", this.scrolled, { passive: true });
    this.watcher = new ResizeObserver(() => this.layout());
    this.watcher.observe(scroller);
  }

  look(fit: Fit, padding: number, gap: number) {
    this.fit = fit;
    this.padding = padding;
    this.gap = gap;
    this.layout();
  }

  // every page's place worked out again - the window resized, the fit or padding changed, a page measured
  // itself - and the reader put back on the same page, the same way down it
  layout() {
    const screen = this.scroller.clientHeight;
    const across = this.scroller.clientWidth;
    if (!screen || !across) return;
    const room = Math.max(120, across - 2 * window.innerWidth * this.padding / 100);
    this.placed = placeStrip(this.pages, this.fit, room, screen, this.gap, this.zoom);
    this.content.style.height = `${this.placed.total}px`;
    this.content.style.width = `${Math.max(across, this.placed.widest)}px`;
    const { n, part } = this.anchor;
    if (n < this.pages.length) this.scroller.scrollTop = this.placed.tops[n] + part * this.placed.heights[n];
    for (const [at, holder] of this.held) this.place(holder, at);
    this.update();
  }

  // to page n, `part` of the way down it - where the reader left it, to the pixel
  jumpTo(n: number, part = 0) {
    this.placedOnPage = true;
    this.anchor = { n, part };
    this.scroller.scrollTop = (this.placed.tops[n] ?? 0) + part * (this.placed.heights[n] ?? 0);
    this.update();
  }

  // how zoomed the strip is, a pinch under way included
  get scale(): number {
    return this.zoom * this.preview.scale;
  }

  // two fingers spread to `scale`, moved from (fromX, fromY) to (x, y) on the screen
  pinch(scale: number, x: number, y: number, fromX: number, fromY: number) {
    this.preview = pinched(this.preview, scale / this.zoom, this.inStrip(fromX, fromY), this.inStrip(x, y));
    this.fingers = { x, y };
    const { scale: s, x: tx, y: ty } = this.preview;
    this.content.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
  }

  // the fingers lifted: laid out at the size they left it
  settle() {
    this.zoomTo(this.scale, this.fingers.x, this.fingers.y);
  }

  // laid out at `scale`, whatever is at (x, y) on the screen staying there: the same page, the same way down
  // and across it
  zoomTo(scale: number, x: number, y: number) {
    const box = this.scroller.getBoundingClientRect();
    const at = this.inStrip(x, y);
    const { scale: s, x: tx, y: ty } = this.preview;
    const cx = (at.x - tx) / s;
    const cy = (at.y - ty) / s;
    const n = pageAt({ length: this.pages.length, at: (k: number) => this.placed.tops[k] }, cy);
    const down = (cy - this.placed.tops[n]) / (this.placed.heights[n] || 1);
    const across = (cx - this.leftOf(n)) / (this.placed.widths[n] || 1);
    // nearly unzoomed is unzoomed, so a pinch let go at 1.02 leaves no sideways scroll of a few pixels
    this.zoom = scale < ZOOM_MIN + 0.01 ? ZOOM_MIN : Math.min(ZOOM_MAX, scale);
    this.preview = { scale: 1, x: 0, y: 0 };
    this.content.style.transform = "";
    this.layout();
    if (n >= this.pages.length) return;
    this.scroller.scrollTop = this.placed.tops[n] + down * this.placed.heights[n] - (y - box.top);
    this.scroller.scrollLeft = this.leftOf(n) + across * this.placed.widths[n] - (x - box.left);
    this.update();
  }

  // a point on the screen, in the strip as it is laid out
  private inStrip(x: number, y: number) {
    const box = this.scroller.getBoundingClientRect();
    return { x: x - box.left + this.scroller.scrollLeft, y: y - box.top + this.scroller.scrollTop };
  }

  // how far down page n the screen is, as a share of the page: the place kept, beside the page itself
  partOf(n: number): number {
    const height = this.placed.heights[n];
    return height ? (this.scroller.scrollTop - this.placed.tops[n]) / height : 0;
  }

  destroy() {
    this.watcher.disconnect();
    this.scroller.removeEventListener("scroll", this.scrolled);
    if (this.frame) cancelAnimationFrame(this.frame);
    for (const n of this.held.keys()) this.hooks.release(n);
    this.held.clear();
    this.playing.clear();
    this.scroller.replaceChildren();
  }

  private scrolled = () => {
    // once a frame, however many scroll events the browser sends
    if (!this.frame) this.frame = requestAnimationFrame(() => { this.frame = 0; this.update(); });
  };

  // where page n's left edge is: centred on the screen, a wider one from the strip's left edge. the strip is
  // still as wide as its widest page, so that page can be scrolled across
  private leftOf(n: number): number {
    return stripLeft(this.placed.widths[n], this.scroller.clientWidth);
  }

  private place(holder: HTMLElement, n: number) {
    holder.style.top = `${this.placed.tops[n]}px`;
    holder.style.left = `${this.leftOf(n)}px`;
    holder.style.width = `${this.placed.widths[n]}px`;
    holder.style.height = `${this.placed.heights[n]}px`;
  }

  private update() {
    const count = this.pages.length;
    if (!count || !this.placedOnPage) return;
    const top = this.scroller.scrollTop;
    const screen = this.scroller.clientHeight;
    const tops = { length: count, at: (n: number) => this.placed.tops[n] };

    const atTop = pageAt(tops, top);
    this.anchor = { n: atTop, part: (top - this.placed.tops[atTop]) / (this.placed.heights[atTop] || 1) };
    // the page being read is the one at the top once a little of it is past; at the very end the last pages
    // can never reach the top of the screen - nothing below them pushes them up - so there it is the last
    // page that has come into view, or a comic could never be finished
    const atEnd = top + screen >= this.placed.total - 2;
    const reading = atEnd ? pageAt(tops, top + screen - 1) : pageAt(tops, top + 40);
    if (reading !== this.current) {
      this.current = reading;
      this.hooks.reading(reading);
    }
    this.hooks.moved();

    const from = pageAt(tops, top - REACH * screen);
    const to = pageAt(tops, top + (1 + REACH) * screen);
    for (let n = from; n <= to; n++) if (!this.held.has(n)) this.add(n);
    const keepFrom = pageAt(tops, top - KEEP * screen);
    const keepTo = pageAt(tops, top + (1 + KEEP) * screen);
    for (const [n, holder] of this.held) {
      if (n >= keepFrom && n <= keepTo) continue;
      holder.remove();
      this.held.delete(n);
      this.playing.delete(n);
      this.hooks.release(n);
    }

    // a video or flash plays only while enough of its page is on screen: a comic with a week of animated
    // strips is otherwise dozens of players at once, all making sound
    for (const [n, holder] of this.held) {
      if (!this.pages[n].standin) continue;
      const shown = this.share(n, top, screen);
      if (shown >= SHOWING && !this.playing.has(n)) {
        this.playing.add(n);
        this.hooks.play(n, holder, () => this.playing.has(n) && this.held.get(n) === holder);
      } else if (shown < SHOWING && this.playing.has(n)) {
        this.playing.delete(n);
        const player = holder.querySelector(".embed");
        if (player) player.replaceWith(this.hooks.picture(n));
      }
    }
  }

  // how much of page n is on screen, as a share of as much of it as could be
  private share(n: number, top: number, screen: number): number {
    const start = this.placed.tops[n];
    const end = start + this.placed.heights[n];
    const seen = Math.max(0, Math.min(end, top + screen) - Math.max(start, top));
    return seen / Math.max(1, Math.min(this.placed.heights[n], screen));
  }

  private add(n: number) {
    const holder = document.createElement("div");
    holder.className = "strip-page";
    holder.dataset.n = String(n);
    this.place(holder, n);
    const picture = this.hooks.picture(n);
    holder.append(picture);
    // a page the server could not measure takes its picture's size the first time it arrives, and keeps it
    if (!this.pages[n].w || !this.pages[n].h) {
      const learn = () => {
        if (!picture.naturalWidth || !picture.naturalHeight || this.pages[n].w) return;
        this.pages[n] = { ...this.pages[n], w: picture.naturalWidth, h: picture.naturalHeight };
        this.layout();
      };
      if (picture.complete) learn();
      else picture.addEventListener("load", learn, { once: true });
    }
    this.held.set(n, holder);
    this.content.append(holder);
  }
}
