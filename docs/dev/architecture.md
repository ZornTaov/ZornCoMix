# Architecture

Six scripts, and the package they share, that mirror webcomics to a library of loose pages and `.cbz`
archives, and keep them up to date unattended. The rules every change needs are in
[CLAUDE.md](../../CLAUDE.md); this is where each part of the code lives.

| File | Lines | What it is |
| --- | ---: | --- |
| `mirror_base.py` | ~640 | Scrapes one comic: the element-path lists, the arguments, the state a run keeps in module globals, and the loop - find the page's images, save them, press next. Everything it leans on is in `comiclib`, handed that state |
| `chapters.py` | ~190 | The command for everything about chapters; the work is in `comiclib/chapters/`, below |
| `web_ui.py` | ~20 | Where `update_comics` finds the web page's server; the server is in `comiclib/web/`, below |
| `web_page/` | ~1500 | The whole front end, no build step: `index.html`, `css/`, and `js/` with one plain script per part of the page. See [web-page.md](web-page.md) |
| `update_comics.py` | ~190 | The long-running process: its arguments, the schedule loop, and starting the web page. The work is `comiclib` `config`, `library`, `batch` and `schedule` |
| `adopt_comic.py` | ~120 | Takes a folder of pages someone else scraped and makes it a comic this tool can update. The work is `comiclib/adopt/`: `scan`, `report`, `adopting` |
| `run_plugin.py` | ~130 | Runs a comic another program scrapes, through its plugin in `config/plugins/`; `--add` starts one, `--list` shows the plugins, `--install`/`--update` fetch one from its repository. The work is `comiclib` `plugins`, `intake`, `pluginrun`, `pluginenv`, `pluginfetch`. See [plugins.md](plugins.md) |
| `examples/plugins/example/` | ~200 | The example plugin: a template for writing one, and what the suite runs. Its `tool/` draws a made-up series |
| `comiclib/` | ~760 | What more than one script needs to agree on, below |
| `reader/` | ~1500 | A separate program: a PerfectViewer-style web reader for the library, in its own image. See [reader.md](reader.md) |

`comiclib` is where anything two scripts both need goes, so the answer cannot drift between them:

| Module | What it is |
| --- | --- |
| `paths` | The config folder, the element-path file, and the one rule naming a comic's index file |
| `pages` | What makes two filenames one page (`page_key`), a page's number, reading order, the name a scrape gives an image |
| `metadata` | Reading and writing `mirror_metadata.json` (always written aside and moved into place), timestamps, settings to command. Only schema 2 is read: schema 1 was never written outside the machine this began on, and its support is gone |
| `cbz` | Every archive any script writes: a new one, one added to, a chapter's, a repack. The Uncompressed/CBZs shelf rule (`layout`), with the other shelves `ComicScraper.json` names: `Uncompressed/Manga/<comic>` files on the `Manga` shelf. The reader has no updater settings, so a comic on another shelf always has its archive (or chapter folder) named in its settings (`named_path`, and moving). And which pictures on the shelf are covers (`is_cover`), which the reader shows and the adopter's scan passes over |
| `standin` | Draws a page for a page no reader can show. `cbz` asks it about every file, so every archive agrees |
| `comicinfo` | The `ComicInfo.xml` every archive carries (v2.1 draft, in the schema's element order), and a picture's size read from its first bytes. `cbz` writes it last-but-metadata and an append rewrites both on the end. Another program's ComicInfo is kept (`kept_tags`, in the metadata as `comicinfo` or a chapter's `comicinfo`) and written back: typed by hand beats it, it beats what is worked out here, and its `Pages`/`PageCount`/`Count` are never believed. `build` must give the same bytes for the same input - that is how an archive is known to be current. What is typed by hand is the metadata's `info`: the nine of `INFO` by their own names (`writer`), any other schema tag of `EXTRA` by its ComicInfo name (`Publisher`), checked by `fit`/`unsayable`. `form()` is the field list both editors - the updater's ComicInfo dialog and the reader's - are drawn from, and `retold` edits another program's ComicInfo in schema order. An edit names every one of the nine but changes an extra tag only where it is named, so a page from before extras existed cannot take one out |
| `plugins` | Finding a plugin, checking its `plugin.json` and a comic's settings against its fields, building its command, a plugin comic's first metadata |
| `intake` | Taking in what a plugin's program wrote: pages numbered on, a chapter's name in each of its pages' names (or every chapter's `001.jpg` is one `page_key`), nothing written over, the same file fetched again not taken twice, chapters added to the list |
| `pluginrun` | One plugin run: leftovers of a killed run taken in, the program run in the staging folder until its deadline, the run recorded, the single archive kept |
| `pluginenv` | A plugin's python packages (`install` in its `plugin.json`), in a `.venv` of its own in its folder, built again when its stamp says another python or another ask; and the programs it `needs`, only looked for |
| `pluginsetup` | A plugin's own settings, its `plugin.json` `setup`, the same for every comic of it: kept in `config/plugin-setup/<id>.json` (mode 600, not in the plugin's clone), edited in the Plugins dialog, handed to its program as environment variables and to its `plugin.py` as `settings["setup"]`. Beside them, under `zcm:shelf` (a key no `plugin.json` can name, never handed over), the shelf Add comics starts its comics on. A `secret` is never put on a command line, which the log and the run record keep; the page shows and edits it, since whoever can reach the page is trusted with the setup |
| `pluginfetch` | Installing a plugin from its git repository (cloned aside, checked, renamed to its `id`), updating it, removing one no comic uses, and whether the web page may (`MIRROR_WEB_PASSWORD`, or `MIRROR_ALLOW_PLUGIN_INSTALLS`) |
| `exits` | `mirror_base`'s exit codes and what each means, and `MirrorError`, which carries one |
| `browser` | Starting the browser a scrape drives, and closing it however it ended. `after_open` is what `mirror_base` does with a page opened by its address: passing an age gate |
| `cookies` | A comic's `settings.cookies` (an age gate's answer, `--cookie NAME=VALUE`): into the browser before its first page, and onto every `requests` read of the site, scoped to its domain and neighbours. `chapters.py` sets `use()` once from the comic's settings, since its readers are not handed them. Imports `requests` and selenium only where used, since `metadata` imports it and the reader has neither |
| `useragent` | The name every fetch outside the browser gives itself - `download` and `cookies.session()` read `current`. A comic's `settings.user_agent` (`--user-agent`) beats `ComicScraper.json`'s `user_agent`, which beats `default`, a current Chrome's; `use()` is called once by `mirror_base` and `chapters.py`. The scrape's browser keeps its own. A site that hangs up on every image without an answer is often refusing the name |
| `placeholders` | A comic's `settings.placeholders` (`--placeholder ADDRESS`): the pictures its site shows where a page will be once it is out, an address filled a day at a time. `page_images` cuts an address's pictures at the first one, since the slot will be a real page numbered where it stands; the scrape then stops as caught up and resumes at that address, and a walk stops there too. Matched by host and path, or by path alone. Stdlib only, since `metadata` imports it |
| `elements` | The element paths shipped as examples (comic image, next link, first-page link, age gate's button), finding the image and the links by them, and pressing a link |
| `pagecheck` | `--check`: which known paths match a page, and what to add when none do |
| `download` | Fetching an image, with retries |
| `guards` | The checks before a page is written: running backwards, writing over another page, one page under two names |
| `runrecord` | What a scrape writes into the metadata about itself: settings, where it is up to, the run record |
| `walk` | `--index`: following a comic saving nothing, with the scrape's own image-finding and next |
| `config` | `ComicScraper.json`: the setup's settings and their defaults, read fresh before every run |
| `library` | `Comic`, finding every comic in a library, and the command each resumes with |
| `batch` | One update of a library: each comic its own process, the lock, chapters packed after, the summary |
| `runlogs` | Everything a comic says during an update, a file per run in `logs/` beside the config folder (`MIRROR_LOGS` overrides), kept a week. Its pipe is read as bytes and split here, since a progress bar redrawn with `\r` is kept once, as last drawn, and shown on the page as it is drawn |
| `schedule` | The daily time, and the `update-now` file that starts a run sooner |
| `moving` | Moving a comic to another folder of the library: its pages, its archive or chapter archives to the matching place on the CBZs shelf, the settings naming them, and its index named in the comic so it is still found. Renames only, undone if one fails. Each rename goes into `history.moves`, which the reader reads (through `metadata.moves`/`before_moves`) to carry a comic's place, settings and cover to its new id - so a scrape must keep that key, as `runrecord` does |
| `web/` | The web page's server: the one job queue (`jobs`), what the page is shown (`views`), the element paths as it edits them (`elementpaths`), the add form (`adding`), a comic uploaded as a zip and put in or adopted (`uploads`), the changes it can make (`edits`), and the http handler (`server`). The page itself is `web_page/`, at the top |
| `chapters/` | Walking a comic to record which page is which, and `KeptIndex`, the index a scrape adds to as it goes (`index`), the same index read from a WordPress site's post list instead of walked (`wordpress`), lining that up against the files (`align`), which file is which page said by hand where that cannot settle it (`pagefixes`: a page pinned to its file, a line that is no page, a file the walk never saw placed after a page - kept in the metadata's `page_fixes`, which a scrape carries, and used by every alignment, so a correction is never written into the index or the alignment, where the next walk or align would lose it), reading an archive page (`archive_page`) or the addresses (`addresses`) for chapters, the chapter list and its corrections (`chapterlist`), a chapter's own number read from its label (`numbering`), packing per chapter (`packing`), renumbering, inserting and refetching pages (`pageops`), and going back to an earlier page (`rewind`: the pages from it on set aside, and the resume point, the index and alignment, the chapters and archives put back to before them - each go-back recorded in `history.rewinds`, which a scrape keeps as `runrecord` does) |

The scripts import only what they use, and nothing reaches into a script for a part of `comiclib`: a test, the web
page or another module imports it from `comiclib` itself. The web page's server is handed no script either; it
imports what it needs from `comiclib` like everything else.

## API specifications

Both servers publish an OpenAPI specification, served live and committed in `docs/`:

- **Updater** (`docs/updater-openapi.yaml`): hand-written. Served at `GET /api/openapi.yaml` by
  `comiclib/web/server.py`. When an endpoint is added, removed or changed — its path, method, parameters
  or response shape — update the spec in the same commit. The spec is the documentation a reader of the
  API trusts, so it must match what the server does.

- **Reader** (`docs/reader-openapi.json`): generated from the FastAPI app. Served at
  `GET /api/openapi.json`. After changing routes in `reader/comicreader/app.py`, regenerate it with
  `python docs/generate_reader_spec.py` and commit the result. Adding `summary`, `tags` and
  `description` to a route decorator improves the generated spec.

A change to either spec should note it in its commit message, so the history is searchable.

## Deploying and releasing, in full

- **The scripts also run in a container**, from a folder mounted over the copies baked into the image
  (see the wiki's Docker page, "Changing the scripts without rebuilding"). So **committing is not deploying**:
  the running copy is the mounted folder, and a new module has to reach it too or both scripts fail on
  import - `comiclib/` above all, which every script imports. `mirror_base.py`, `chapters.py`,
  `adopt_comic.py`, `run_plugin.py` and `web_page/` take effect immediately; `update_comics.py`, `web_ui.py` and
  anything in `comiclib/` need the container restarting, since the long-running process has them
  imported already (a scrape it starts imports `comiclib` afresh, but the web page does not).
- **A version tag publishes both images; a push to main does not.** `.github/workflows/images.yml` builds
  the updater and the reader for amd64 and arm64 and pushes them to `ghcr.io/zorntaov/` as `zcm-updater`
  and `zcm-reader`; their names from before the rename (`comics-updater`, `comic-reader`) stopped at v1.2.0
  and are left frozen there, not deleted. The two share one
  version: `git tag v1.2.0 && git push origin v1.2.0` releases both as `:1.2.0`, `:1.2`, `:1` and
  `:latest`, which both compose files pull. Main is built as `:nightly` (and `:sha-<commit>`) once a night,
  only when it has moved. A release reaches whoever next pulls - not a container running already, nor one
  running scripts from a mounted folder. Tag a release only when the user asks for one.
- **The `.gitignore` allowlist** has bitten before: `standin.py` was imported by two modules while
  committed nowhere, because a new file is untracked until it is named there.
