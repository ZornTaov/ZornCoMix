#which part of the suite tests which part of the code. each folder of tests/ is an area, and every test in it
#carries the area's marker, so `pytest tests/web`, `pytest -m "chapters and not browser"` and
#`pytest --affected` all run a part of the suite. this map is what --affected goes by: a changed file picks
#the areas whose patterns it matches. a module added to the code needs a line here, or a change to it runs
#everything - the safe answer when nobody has said which tests cover it.
#
#patterns are fnmatch's, against paths from the repo root with forward slashes; its * crosses folders.
import fnmatch
import os
import subprocess

TESTS = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(TESTS)

AREAS = {
    "scrape": [
        "mirror_base.py",
        "comiclib/browser.py", "comiclib/cookies.py", "comiclib/useragent.py", "comiclib/placeholders.py",
        "comiclib/elements.py", "comiclib/pagecheck.py", "comiclib/download.py", "comiclib/guards.py",
        "comiclib/runrecord.py", "comiclib/exits.py",
    ],
    "chapters": [
        "chapters.py", "comiclib/chapters/*", "comiclib/walk.py",
    ],
    "archives": [
        "comiclib/cbz.py", "comiclib/standin.py", "comiclib/comicinfo.py",
    ],
    "library": [
        "update_comics.py", "adopt_comic.py",
        "comiclib/config.py", "comiclib/library.py", "comiclib/batch.py", "comiclib/runlogs.py",
        "comiclib/schedule.py", "comiclib/moving.py", "comiclib/adopt/*",
    ],
    "plugins": [
        "run_plugin.py",
        "comiclib/plugins.py", "comiclib/intake.py", "comiclib/pluginrun.py", "comiclib/pluginenv.py",
        "comiclib/pluginsetup.py", "comiclib/pluginfetch.py", "examples/*",
    ],
    "web": [
        "web_ui.py", "web_page/*", "comiclib/web/*", "docs/updater-openapi.yaml",
    ],
}

#what every area stands on: the modules whose answers every script shares, and the suite's own footing
EVERYTHING = [
    "comiclib/__init__.py", "comiclib/metadata.py", "comiclib/pages.py", "comiclib/paths.py",
    "tests/conftest.py", "tests/areas.py", "pytest.ini", "requirements.txt", "requirements-dev.txt",
]

#what no test of this suite runs. the reader has a suite of its own, and the images are built, not tested here
NOTHING = [
    "*.md", "docs/*", ".github/*", "reader/*", "Dockerfile", "docker-compose.yml", ".dockerignore",
    ".gitignore", ".gitattributes", "LICENSE", "NOTICE", "comics.example.csv",
]


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def choose(paths):
    #(areas, test files, reasons): the areas to run whole, single test files changed outside them, and a line
    #for each changed file saying what it picked. areas is None when everything has to run
    areas, files, reasons = set(), set(), []
    everything = False
    for path in sorted(paths):
        if path.startswith("tests/") and path.endswith(".py") and path.count("/") == 2:
            area = path.split("/")[1]
            if area in AREAS:
                files.add(path)
                reasons.append("{0}: itself".format(path))
                continue
        picked = [area for area, patterns in AREAS.items() if matches(path, patterns)]
        if picked:
            areas.update(picked)
            reasons.append("{0}: {1}".format(path, ", ".join(picked)))
        elif matches(path, EVERYTHING):
            everything = True
            reasons.append("{0}: everything stands on it".format(path))
        elif matches(path, NOTHING):
            reasons.append("{0}: nothing here tests it".format(path))
        else:
            #a file nobody has placed could be anything, and skipping its tests is the mistake to avoid
            everything = True
            reasons.append("{0}: not in tests/areas.py, so everything".format(path))
    return (None if everything else areas), files, reasons


def git(*args):
    done = subprocess.run(["git"] + list(args), cwd=PROJECT, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("git {0} failed: {1}".format(" ".join(args), done.stderr.strip()))
    return [line for line in done.stdout.splitlines() if line]


def changed(base):
    #what this branch has changed since it left base, committed or not, and files not yet committed at all.
    #untracked files are read through the allowlist, so a stray file in the library is not a change
    point = git("merge-base", base, "HEAD")[0]
    paths = set(git("diff", "--name-only", point))
    paths.update(git("ls-files", "--others", "--exclude-standard"))
    return paths
