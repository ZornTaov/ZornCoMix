// a screen takes a moment to open - the comic or the shelf is asked for first - and the address can move on
// in that moment: back pressed while a comic is still opening. the screen opened for an address left behind
// is closed the moment it is ready, or it would be left running with nothing to close it: a reader left so
// still had its keys, and an arrow pressed on the library turned its pages, saved its place, and at the
// end of a chapter opened the next - and with its strip off the page it saved its place as fifty pages up.
// what it draws never shows either: each route draws into a box of its own, which main.ts lets take the
// page only while its route is the newest
export interface Route {
  // whether a later route has begun since this one
  stale(): boolean;
  // the screen's close once it has opened, given back if this route is still the newest - otherwise the
  // screen is closed there and then, and null given back
  keep(close: () => void): (() => void) | null;
}

export function screens(): () => Route {
  let newest = 0;
  return () => {
    const mine = ++newest;
    const stale = () => mine !== newest;
    return {
      stale,
      keep(close) {
        if (!stale()) return close;
        close();
        return null;
      },
    };
  };
}
