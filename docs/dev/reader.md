# The reader

`reader/` is its own program with its own image, dependencies and tests, sharing only `comiclib` -
imported, never copied, so it cannot disagree with the scraper about which page comes next.
`comicreader/` is a FastAPI server (`sources`: an archive or loose folder as a page list, kept from its
last good reading while the scraper appends to it; `library`: every comic as one stream of pages across
its chapter archives, and where the reader is up to by `page_key`, not by number; `store`: sqlite in its
data folder; `app`: the routes). `web/` is TypeScript built by Vite inside the image (the scraper's
`web_page/` stays build-free); the arithmetic - spreads, taps, keys, shelves - is in `layout.ts` and
`shelves.ts` so Vitest can test it without a browser. It mounts the library read-write, for covers chosen in it
and saved on the shelf, and for `editing`: what a comic is said to be - a scraped comic's metadata `info` and
its archives' ComicInfo, an archive from elsewhere's own ComicInfo - one comic at a time or a whole folder or
series (`describe_many`, `edit_many`: only the fields changed, every comic checked quiet before any is
written). Nothing else of the library is written.

Its suite runs apart: `cd reader && python -m pytest` (offline, a couple of seconds; `reader/pytest.ini`
makes it its own root) and `npm test` in `reader/web`. `tests/test_contract.py` there checks what it
relies on comiclib for, so **run it after any comiclib change**. Build with
`docker build -f reader/Dockerfile -t zcm-reader:local .` from the repo root.
