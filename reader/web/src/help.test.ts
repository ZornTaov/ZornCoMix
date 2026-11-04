import { describe, expect, it } from "vitest";
import { type Entry, helpSections, type HowRead, keyLabel, leftGoesForward } from "./help";
import { picture } from "./helppictures";
import { keyAction, tapAction } from "./layout";

const ltr: HowRead = { mode: "single", direction: "ltr", swapZones: false, zone: 0.33 };

const entries = (sections: { entries: Entry[] }[]) => sections.flatMap((section) => section.entries);
const doing = (sections: { entries: Entry[] }[], does: string) =>
  entries(sections).filter((entry) => entry.does === does);
const labels = (sections: { entries: Entry[] }[]) =>
  new Set(entries(sections).flatMap((entry) => (entry.keys ?? []).flat()));

describe("the help says what the keys do", () => {
  it("names every key the reader answers to, so a key added later cannot go unsaid", () => {
    const said = labels(helpSections("all", ltr));
    const keys = ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "]", "[", "PageDown", "PageUp", "Enter", "Backspace",
                  " ", "Home", "End", "m", "Escape", "Tab", "q", "a"];
    for (const key of keys) {
      if (keyAction(key, false, "ltr") !== null) expect(said, key).toContain(keyLabel(key));
    }
    // read before keyAction is asked
    expect(said).toContain("F");
    expect(said).toContain("?");
  });

  it("puts the arrow that goes on as the comic reads", () => {
    const next = (how: HowRead) => doing(helpSections("reader", how), "Next page")[0].keys![0];
    expect(next(ltr)).toEqual(["→"]);
    expect(next({ ...ltr, direction: "rtl" })).toEqual(["←"]);
    // and as keyAction has it
    expect(keyAction("ArrowLeft", false, "rtl")).toBe("forward");
  });

  it("says a page turned when scrolling is a screen scrolled", () => {
    const sections = helpSections("reader", { ...ltr, mode: "webtoon" });
    expect(doing(sections, "Next page")).toHaveLength(0);
    expect(entries(sections)[0].does).toMatch(/^Down a screen/);
  });
});

describe("the help shows only the gestures of what is open", () => {
  const gestures = (how: HowRead) => entries(helpSections("reader", how)).map((entry) => entry.gesture).filter(Boolean);

  it("has no swipes for a scrolled comic, which scrolls the browser's way, but zooms it as a page", () => {
    expect(gestures({ ...ltr, mode: "webtoon" })).not.toContain("swipeLeft");
    expect(gestures({ ...ltr, mode: "webtoon" })).toContain("scroll");
    expect(gestures({ ...ltr, mode: "webtoon" })).toEqual(expect.arrayContaining(["pinch", "doubleTap"]));
    expect(gestures(ltr)).toEqual(expect.arrayContaining(["pinch", "doubleTap", "swipeLeft"]));
  });

  it("has the shelves alone on the shelves, and everything in all", () => {
    expect(helpSections("library", ltr).map((section) => section.title)).toEqual(["The shelves"]);
    const all = helpSections("all", ltr).map((section) => section.title);
    expect(all[0]).toBe("The shelves");
    expect(all.some((title) => title.includes("Scroll"))).toBe(true);
    expect(all.some((title) => title.includes("One page"))).toBe(true);
  });
});

describe("the sides of the screen", () => {
  it("are the way round tapAction turns them, swapped or not", () => {
    for (const direction of ["ltr", "rtl"] as const) {
      for (const swapZones of [false, true]) {
        const how = { ...ltr, direction, swapZones };
        // a tap at the far left goes forward exactly when the help says the left side does
        expect(tapAction(1, 100, how) === "forward").toBe(leftGoesForward(how));
        const next = doing(helpSections("reader", how), "Next page").find((entry) => entry.gesture);
        expect(next!.gesture).toBe(leftGoesForward(how) ? "zoneLeft" : "zoneRight");
      }
    }
  });

  it("swipe the way a page would be pulled", () => {
    const swipe = (how: HowRead) => doing(helpSections("reader", how), "Next page").find((entry) => entry.gesture?.startsWith("swipe"));
    expect(swipe(ltr)!.gesture).toBe("swipeLeft");
    expect(swipe({ ...ltr, direction: "rtl" })!.gesture).toBe("swipeRight");
  });

  it("are drawn at the width the zones are set to", () => {
    // the left zone's shaded box is the zone's share of the 24-wide screen
    expect(picture("zoneLeft", 0.25)).toContain('width="6"');
    expect(picture("zoneLeft", 0.4)).toContain('width="9.6"');
  });
});
