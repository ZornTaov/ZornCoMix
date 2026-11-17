# Working on this project

The project is **ZornCoMix**: ZornCoMix Updater and ZornCoMix Reader, `zcm-` in image and container
names. It was ZC-ComicUpdater before, and archives already made still say so in their ComicInfo notes;
leave those alone, since a changed note rewrites every archive's ComicInfo. The user-facing docs are the
GitHub wiki (<https://github.com/ZornTaov/ZornCoMix/wiki>, its own repo `ZornCoMix.wiki.git`), and a change
users would notice needs its wiki page updated too. Paths on a particular machine belong in local notes,
not in this tracked file.

Six scripts and the `comiclib` package they share mirror webcomics to a library of loose pages and
`.cbz` archives; `reader/` is a separate web reader. Before changing an area, read its notes:

| Notes | Read before touching |
| --- | --- |
| [docs/dev/architecture.md](docs/dev/architecture.md) | What each script and `comiclib` module does: deciding where a change belongs. Also the API specs and releases in full |
| [docs/dev/concepts.md](docs/dev/concepts.md) | Metadata, `ended`, the index, chapter numbers, alignment, element paths |
| [docs/dev/web-page.md](docs/dev/web-page.md) | `web_page/` or `comiclib/web/` |
| [docs/dev/reader.md](docs/dev/reader.md) | `reader/` |
| [docs/dev/plugins.md](docs/dev/plugins.md) | `run_plugin.py`, the plugin modules, `examples/plugins/` |
| [docs/dev/testing.md](docs/dev/testing.md) | Test areas, the harness, coverage |

## Rules every change needs

- **`.gitignore` is an allowlist** (the repo sits inside a working library): `*` first, then `!name`
  for each tracked file. A new file is untracked until named there, in the same commit. A folder
  needs two lines, `!folder/` then `!folder/*.py`, because `*` matches at every depth.
- **Anything two scripts need goes in `comiclib`**, and everything imports it from there, never from a
  script. A new module needs its line in `tests/areas.py`.
- **`config/` is the user's data** (`ComicScraper.json`, `element_paths.json`, `index/`, `plugins/`;
  `MIRROR_CONFIG` overrides the folder, `MIRROR_ELEMENTS` the element-path file): never edit or delete
  anything in it.
- **No real webcomic is named anywhere in the repo**: code, comments, help text, the web page, tests,
  docs. Describe the site's shape; use `example.com`, `MyComic`, `SomeAuthor/TheirComic`. Naming comic
  *software* is fine. AChillVamp's credit (`NOTICE`, the README, the `mirror_base.py` header) is
  attribution and stays.
- **Do not special-case a comic in the code.** A site-specific element path belongs in the user's
  `config/element_paths.json`; the shipped ones in `comiclib/elements.py` are generic examples.
- **`mirror_metadata.json` is the single source of truth**, and its `settings` block is the only part
  anyone edits. `ended` is the reader's judgement, never the scraper's (see concepts.md).
- **Files are written aside** (`.writing`, `.packing`) and moved into place, so an interrupted run
  leaves nothing half-written.
- **An endpoint change updates its spec in the same commit**, noted in the message: the updater's
  `docs/updater-openapi.yaml` is hand-written; the reader's is regenerated with
  `python docs/generate_reader_spec.py`.
- **After any `comiclib` change, run `reader/tests/test_contract.py`** (`cd reader && python -m pytest`).
- **Dependencies are selenium and requests** (`requirements.txt`). Adding one is allowed when it is
  genuinely needed, but it means rebuilding the container, so **say plainly whether a change needs a
  rebuild, a restart, or neither**. Prefer the stdlib where cheap; `comiclib`'s archive and page modules
  stay stdlib-only, since other programs import them.
- **The license is PolyForm Noncommercial 1.0.0**: never edit `LICENSE` (the copyright line is in
  `NOTICE`), and no dependency or copied code may carry conflicting terms.

## The library

- **The library** holds `Uncompressed/<Comic>` for loose pages and `Webcomics/` for archives - `CBZs/` in a
  library made before then, which is still found: with no `cbz_folder` set, the default shelf is whichever
  of the two the library has, `CBZs` first (`cbz.default_shelf`), so the reader agrees without settings. A comic's
  `output` and `cbz_path` are stored relative to the library root, so the library can move. Other shelves
  sit beside `CBZs` (`shelves` in `ComicScraper.json`), one library root still, so a reader pointed at each
  shelf as a library of its own needs no more mounts. The library root is the folder holding
  `Uncompressed`, never the folder above a comic's pages tree, which for a shelved comic is `Uncompressed`.
- **The library is usually on a network share.** Listing a comic folder of a few thousand files takes
  minutes. Prefer one listing the user can provide over repeated directory reads, and expect file-heavy
  commands to need long timeouts.

## Deploying and releasing

- **Committing is not deploying.** The container runs scripts from a mounted folder, so a new module has
  to reach it too. `mirror_base.py`, `chapters.py`, `adopt_comic.py`, `run_plugin.py` and `web_page/`
  take effect immediately; `update_comics.py`, `web_ui.py` and `comiclib/` need a container restart.
- **A version tag publishes both images; a push to main does not** (`.github/workflows/images.yml`,
  `ghcr.io/zorntaov/zcm-updater` and `zcm-reader`; main builds `:nightly`). Tag only when the user asks.

## Conventions worth matching

- Comments explain **why**, in lower-case prose, describing the kind of site that forced the
  behaviour ("a comic can re-serve an old page's image under a later page"). Match the surrounding
  density; it is high.
- Errors say what to do next, not just what failed ("Run this comic with `--prefix` so each page is
  numbered as it is saved").
- Flags that default on use `argparse.BooleanOptionalAction`; only the *off* case goes into settings.
- `mirror_base.py` exit codes are checked by callers: `0` ok, `1` interrupted, `2` usage, `3` no image
  found, `4` download failed, `5` driver, `6` timeout, `7` unexpected, `8` next link runs backwards,
  `9` the site reuses filenames, `10` next link skips pages the index lists, `11` the same picture found
  as the comic page after page; `run_plugin.py` adds `12` the plugin's program failed, `13` it ran out of
  time (what it got is kept).

## Testing

`python -m pytest` runs everything (xdist, low priority, pooled Chrome profiles); `-m "not browser"` is
the offline half in seconds; `--affected` runs only the areas changed since `origin/main`; `-n 0` runs
one test at a time for reading output. A new test goes in the folder of the area it tests. Browser
tests wait with `wait_until`/`open_page`/`checked`, never a fixed sleep. Nothing reaches the internet or
a real library. It passes in full at `HEAD`, so a failure is yours. Details are in testing.md.

## Things that have bitten, more than once

- **A feature landing in the wrong layer.** A comic with one archive and a comic with one per chapter
  need the same answer to "what does a reader see here". Twice now something went into `chapters.py`
  or the aligner and had to be pulled out for `mirror_base` to use it.
- **Presence standing in for completeness.** The web page asked whether an index file *existed* and
  took a one-line stub to mean a walked comic. Ask what something holds, not whether it is there.
- **A rule that is 99.9% right.** A comic can re-serve an old page's image under a new page, so "name
  the file after the site's image" would have overwritten a page 1,500 earlier. On a library of
  thousands of files, check the exception before a rename or a delete.
- **Heredocs.** Do not edit files by piping a script into `python - <<'EOF'`; backslashes are mangled
  before the shell sees them and the failure is silent. Use the editor tools.
