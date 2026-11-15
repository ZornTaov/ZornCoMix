# The ideas the code is built on

- **`mirror_metadata.json` in each comic folder is the single source of truth.** Its `settings` block is
  the only thing anyone edits; the scrape command is rebuilt from it every run (`settings_to_argv` in
  `update_comics.py`). Schema 2. `state` and `history` are what the tools have learned and done.
- **`ended` is the reader's judgement, never the scraper's.** A scrape can only know it has caught up
  with the latest page. It comes from the report column, the web page's tick box, or a hand edit, and is
  carried through untouched. The one exception is a plugin whose site says a series is finished: its
  `plugin.py` `ended()` returning `True`, after a run whose program finished, marks the comic ended and
  sets `history.plugin_ended`. While that stands, a comic the person unticks stays unticked; `ended()`
  returning exactly `False` (the series came back) clears it, so the next `True` marks the comic again
  (`pluginrun.ended_change`). Anything else, or an `ended()` that raises, is no answer and changes nothing. `state.completed` is a different thing: that *run* reached the latest page.
- **The index (`config/index/<comic>.<tag>.jsonl`) is one line per page, in reading order**, recording
  the address and the image. Position is meaning: line 1 is page 1. It can only be appended to from a
  context that knows its own offset — a scrape resuming mid-comic must not start one.
- **A chapter has two numbers.** `chapters.list[].number` is its *place* in the comic (1..n, set by
  `settle_chapters`), which fixes, messages and the list itself go by. Its *own* number, `called`, is read
  from its label by `comiclib/chapters/numbering.py` (`Chapter 391`, `Book #12`, an intermission after 12 is
  12.5), **worked out every time and never stored**, and falls back to the place for a comic whose labels do
  not number it in order. The archive name (`c391`, `c012.5`) and ComicInfo `Number` use `called`, and the
  reader imports the same module to match an archive to its chapter. Packing renames an archive still
  named by its place - only that exact old name - and records the rename in `history.moves` with a
  `pages` step for the comic's own folder, since the reader keeps a chapter by its archive's path.
- **Alignment** matches that record against the files on disk, by name, by size, then by order. It has
  to *settle* before a comic can be chaptered. Missing pages are tolerated; unplaced files are not.
- **Element paths** are XPaths for the comic image and the next link, tried in order, with the winner
  remembered per comic, and for the first-page link a walk follows back to page 1 when a comic's start
  was never recorded - a walk that finds none stops, rather than start an index part way through. A library adds its own through `config/element_paths.json`, which is the
  sanctioned way to handle an awkward site — **do not special-case a comic in the code.**
  The shipped element paths are a short generic set, one per common kind of site (WordPress comic
  themes, ComicControl, `rel="next"`), kept in `comiclib/elements.py` as `shipped`, in the same
  `{xpath, note}` shape as `element_paths.json`. They are examples as much as defaults; the ones added
  for particular comics live in the user's own `config/element_paths.json`, which is where any new
  site-specific path belongs.
