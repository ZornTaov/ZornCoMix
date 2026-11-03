import { describe, expect, it, vi } from "vitest";
import { screens } from "./routing";

describe("a screen opened for an address since left", () => {
  it("is kept when no route began while it opened", () => {
    const begin = screens();
    const route = begin();
    const close = vi.fn();
    expect(route.stale()).toBe(false);
    expect(route.keep(close)).toBe(close);
    expect(close).not.toHaveBeenCalled();
  });

  it("is closed at once when it finishes opening after a later route began", () => {
    // a comic still opening when back is pressed, the library then slower to open than the comic
    const begin = screens();
    const reading = begin();
    const browsing = begin();
    const closeReader = vi.fn();
    const closeLibrary = vi.fn();
    expect(reading.stale()).toBe(true);
    expect(reading.keep(closeReader)).toBeNull();
    expect(closeReader).toHaveBeenCalledOnce();
    expect(browsing.keep(closeLibrary)).toBe(closeLibrary);
    expect(closeLibrary).not.toHaveBeenCalled();
  });

  it("is closed whichever of the two finishes first", () => {
    const begin = screens();
    const reading = begin();
    const browsing = begin();
    const closeLibrary = vi.fn();
    const closeReader = vi.fn();
    expect(browsing.keep(closeLibrary)).toBe(closeLibrary);
    expect(reading.keep(closeReader)).toBeNull();
    expect(closeReader).toHaveBeenCalledOnce();
  });
});
