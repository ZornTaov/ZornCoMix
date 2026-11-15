# Testing

The suite is `tests/`, run with pytest (`pip install -r requirements-dev.txt`, which the container never
needs). `python -m pytest` runs all of it side by side (`pytest.ini` asks xdist for up to 8 workers), at
below-normal priority that every browser and script it starts inherits (`run_politely` in `conftest.py`),
with every Chrome reusing a profile from a pool (`share_profiles`, `MIRROR_PROFILE_POOL`) rather than making
one. `-m "not browser"` runs the offline half in seconds, and `-n 0` runs one test at a time for reading its
output. A run is felt on the rest of the machine at any worker count - a video beside it hitched at 4 as at
16 - so it runs fast and is over sooner; the pool and the priority keep it as light as it can be. Tests that need Chrome skip themselves on a machine without it.

The tests sit in a folder per **area** of the code - `scrape`, `chapters`, `archives`, `library`, `plugins`,
`web` - and each carries its folder's marker, so a part of the suite is `python -m pytest tests/web`,
`-m "chapters and not browser"`, or `--affected`, which runs only the areas what the branch changed since
`origin/main` (or `--affected=BASE`) touches, saying why at the top. `tests/areas.py` maps the code to its
area: **a new module needs its line there**, or a change to it runs everything - the safe answer, not a
wrong one. `metadata`, `pages`, `paths` and the harness run everything. A new test goes in the folder of
what it tests; a new area needs its two `.gitignore` lines. Every area's folder is on the path, so a test
borrows another's fake site by its bare name (`from test_plugins import install`) - which needs test file
names unique across the folders.

**Every pull request runs all of it** (`.github/workflows/tests.yml`, also on main after a merge): the
updater's suite as an offline job and a browser job on Ubuntu, the reader's pytest, and its Vitest. The
suite was written on Windows; a test that passes there and not on the runner is a bug in one or the other.

Coverage is measured by hand, never by default: `python -m pytest --cov --cov-report=html` for the updater
(`.coveragerc` - the scripts a test starts as processes are measured too, by coverage's `patch = subprocess`),
`python -m pytest --cov=comicreader --cov=comiclib` in `reader/`, `npm run coverage` in `reader/web`, and for
the web page's own scripts `MIRROR_JS_COVERAGE=FOLDER python -m pytest tests/web` then
`python tests/jscoverage.py FOLDER`, which lists the functions no browser test ran. A process ended without being
asked loses what it measured: the web page's server is stopped with ctrl+break on Windows for that reason
(`WebUI.stop`), and code reached only by a test killing something on purpose reads as untested.

Browser tests wait for what they are waiting for - `wait_until`, `open_page`, `checked` in the harness -
never a fixed sleep: a pause long enough for the slowest machine was most of what the suite used to spend.

`tests/conftest.py` is the harness: a fake comic served on a local port, a stalling server, a library
and config folder of each test's own under `tmp_path` (named through `MIRROR_CONFIG`, so every script a
test starts reads that and not the real one), the web page started over it, and fixtures that import
`mirror_base` and `chapters` afresh - `mirror_base` keeps its run in module globals and reads its
element paths on import, so a plain import would carry one test into the next.

Nothing in the suite reaches the internet or a real library, and nothing names a real comic: a behaviour
a real site forced is reproduced with a made-up one of the same shape. Run it before and after changing
shared behaviour; it passes in full at `HEAD`, so a failure is yours.
