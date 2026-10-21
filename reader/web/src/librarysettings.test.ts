import { describe, expect, it } from "vitest";
import { cleanLibrary, libraryDefaults } from "./librarysettings";

describe("library settings", () => {
  it("starts from the defaults, and keeps only what it knows at sensible values", () => {
    expect(cleanLibrary(undefined)).toEqual(libraryDefaults);
    expect(cleanLibrary({ recentDays: 30.4, clearRead: true, other: 1 } as never)).toEqual({ recentDays: 30, clearRead: true });
    expect(cleanLibrary({ recentDays: -5 }).recentDays).toBe(0);
    expect(cleanLibrary({ recentDays: 10_000 }).recentDays).toBe(365);
    expect(cleanLibrary({ recentDays: "7", clearRead: "yes" } as never)).toEqual(libraryDefaults);
  });
});
