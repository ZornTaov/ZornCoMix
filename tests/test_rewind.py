#going back: a comic's pages from one page on taken off and everything that says where its scrape is up to put
#back to before them, so the next update fetches them again. the comic here is one whose last run saved a
#site's user icon for its four newest pages - one of them starting a chapter of its own - which is what going
#back is for: the path put right, the comic taken back, updated again.
import json
import os
import zipfile

import pytest

from conftest import read_meta, run, write_index, write_meta

GOOD = 10
BAD = 4
NAME = "Uncompressed/Stuck"
CHAPTERS = [{"number": 1, "label": "Chapter 1", "start_page": 1, "end_page": 4, "pages": 4},
            {"number": 2, "label": "Chapter 2", "start_page": 5, "end_page": 9, "pages": 5},
            {"number": 3, "label": "Chapter 3", "start_page": 10, "end_page": 12, "pages": 3},
            {"number": 4, "label": "Chapter 4", "start_page": 13, "end_page": 14, "pages": 2}]
AVATAR = "https://x.test/img/avatar.png"


def page_file(n):
    return "{0:04d}_{1}.png".format(n, n) if n <= GOOD else "{0:04d}_avatar.png".format(n)


class Stuck:
    def __init__(self, library, comic, cache):
        self.library = library
        self.comic = comic
        self.cache = cache
        self.alignment = cache.replace(".jsonl", ".align.json")
        self.shelf = library / "CBZs" / "Stuck"
        self.aside = comic / ".set aside"

    def rewind(self, *extra):
        return run("chapters.py", "rewind", self.comic, "--root", self.library, *extra)

    def index(self):
        with open(self.cache, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def pages(self):
        return sorted(name for name in os.listdir(str(self.comic)) if name.endswith(".png"))

    def held(self, archive):
        with zipfile.ZipFile(str(self.shelf / archive)) as zf:
            return [name for name in zf.namelist() if name.endswith(".png")]


def write_pages(comic, count, chapters, cache, *, listed=None, settings=None):
    for n in range(1, count + 1):
        #every user icon is the same picture, and each good page its own
        (comic / page_file(n)).write_bytes(b"avatar" * 50 if n > GOOD else bytes([n]) * (100 * n))
    meta = {"schema": 2, "settings": dict({"url": "https://x.test/p{0}".format(count), "output": NAME,
                                           "cbz_path": "CBZs/Stuck.cbz", "cbz": True, "increment": count,
                                           "prefix": True}, **(settings or {})),
            "state": {"page_count": count, "completed": True, "image_xpath": '//*[@class="avatar"]/img',
                      "last_image_file": page_file(count), "last_image_url": AVATAR},
            "history": {"first_page_url": "https://x.test/p1", "first_page_number": 1,
                        "runs": [{"run_id": "first", "start_url": "https://x.test/p1", "start_page_number": 1,
                                  "last_page_number": GOOD, "pages_saved": GOOD},
                                 {"run_id": "stuck", "started": "2026-10-19T10:31:00Z",
                                  "start_url": "https://x.test/p{0}".format(GOOD), "start_page_number": GOOD,
                                  "last_url": "https://x.test/p{0}".format(GOOD), "last_page_number": count,
                                  "pages_saved": count - GOOD + 1}],
                        "gaps": [{"page": 3, "note": "no file here for this page"},
                                 {"page": 12, "note": "no file here for this page"}]}}
    if chapters:
        meta["chapters"] = {"source": "archive", "list": chapters}
    write_meta(comic, meta)
    if cache is None:
        return
    lines = [{"n": n, "url": "https://x.test/p{0}".format(n),
              "src": AVATAR if n > GOOD else "https://x.test/img/{0}.png".format(n),
              "file": page_file(n)} for n in range(1, (listed or count) + 1)]
    write_index(cache, lines)
    with open(cache.replace(".jsonl", ".align.json"), "w", encoding="utf-8") as f:
        json.dump({"comic": str(comic), "settled": True,
                   "pages": [{"n": line["n"], "url": line["url"], "src": line["src"],
                              "file": line["file"] if line["n"] <= count else None, "how": "name"}
                             for line in lines]}, f)


@pytest.fixture
def stuck(library, chapters):
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    cache = chapters.index_path(str(comic))
    write_pages(comic, GOOD + BAD, CHAPTERS, cache)
    held = Stuck(library, comic, cache)
    packed = run("chapters.py", "pack", comic, "--root", library)
    assert packed.returncode == 0, packed.stdout[-600:]
    return held


def test_a_dry_run_says_what_it_would_do_and_changes_nothing(stuck):
    before = (stuck.pages(), read_meta(stuck.comic), stuck.index(), sorted(os.listdir(str(stuck.shelf))))
    done = stuck.rewind("--from", GOOD + 1, "--dry-run")
    assert done.returncode == 0, done.stdout
    said = done.stdout
    assert "4 page(s) set aside, 0011_avatar.png to 0014_avatar.png" in said, said
    assert "cut back to page 10 (4 line(s) taken off)" in said, said
    assert "starts at https://x.test/p11, as page 11" in said, said
    assert "chapter 3 (Chapter 3) ends at page 10 now" in said, said
    assert "chapter 4 (Chapter 4) starts at page 13 or after, so it is taken out" in said, said
    assert "Stuck - c004 - Chapter 4.cbz set aside" in said, said
    assert "Nothing was changed" in said
    assert before == (stuck.pages(), read_meta(stuck.comic), stuck.index(), sorted(os.listdir(str(stuck.shelf))))


def test_going_back_puts_everything_back_to_before_the_page(stuck):
    done = stuck.rewind("--from", GOOD + 1)
    assert done.returncode == 0, done.stdout[-1500:]
    #the user icons are set aside, not deleted, and nothing else went with them
    assert stuck.pages() == [page_file(n) for n in range(1, GOOD + 1)]
    assert sorted(os.listdir(str(stuck.aside))) == sorted(
        [page_file(n) for n in range(GOOD + 1, GOOD + BAD + 1)] + ["Stuck - c004 - Chapter 4.cbz"])
    #the record of which page is which ends at the last page kept, with a copy of it as it was beside it
    assert [line["n"] for line in stuck.index()] == list(range(1, GOOD + 1))
    copies = [name for name in os.listdir(os.path.dirname(stuck.cache)) if ".rewound-" in name]
    assert len(copies) == 2 and any(name.endswith(".align.json") for name in copies), copies
    with open(stuck.alignment, encoding="utf-8") as f:
        assert [page["n"] for page in json.load(f)["pages"]] == list(range(1, GOOD + 1))
    meta = read_meta(stuck.comic)
    #the next update starts at the first page taken off, as that page
    assert (meta["settings"]["url"], meta["settings"]["increment"]) == ("https://x.test/p11", GOOD + 1)
    state = meta["state"]
    assert (state["page_count"], state["last_image_file"], state["last_image_url"], state["completed"]) == \
        (GOOD, page_file(GOOD), "https://x.test/img/10.png", False), state
    #the path is not going back's to change: it is put right in the editor, beside this
    assert state["image_xpath"] == '//*[@class="avatar"]/img'
    #the chapter that began among the user icons is gone, and the one they joined ends where they began
    listed = meta["chapters"]["list"]
    assert [chapter["number"] for chapter in listed] == [1, 2, 3]
    assert (listed[-1]["end_page"], listed[-1]["pages"]) == (GOOD, 1)
    assert [gap["page"] for gap in meta["history"]["gaps"]] == [3]
    #said in the edits, as every change to where a comic is up to is, and in a record of its own
    assert meta["history"]["edits"][-1]["changed"]["pages"] == [GOOD + BAD, GOOD]
    went = meta["history"]["rewinds"][-1]
    assert (went["from_page"], went["newest_was"], len(went["set_aside"])) == (GOOD + 1, GOOD + BAD, BAD), went
    #and the archives agree: chapter 3's written again with its one good page, chapter 4's set aside
    assert sorted(os.listdir(str(stuck.shelf))) == ["Stuck - c001 - Chapter 1.cbz", "Stuck - c002 - Chapter 2.cbz",
                                                    "Stuck - c003 - Chapter 3.cbz"]
    assert stuck.held("Stuck - c003 - Chapter 3.cbz") == [page_file(GOOD)]
    assert "exactly one chapter archive" in done.stdout


def test_undoing_a_run_goes_back_to_where_it_started(stuck):
    #the run started on the page it resumed from, which it saved again: that page comes off too and is
    #fetched first next time, so a run whose very first save was the wrong picture is undone whole
    done = stuck.rewind("--run", "stuck")
    assert done.returncode == 0, done.stdout[-1500:]
    assert stuck.pages() == [page_file(n) for n in range(1, GOOD)]
    meta = read_meta(stuck.comic)
    assert (meta["settings"]["url"], meta["settings"]["increment"]) == ("https://x.test/p10", GOOD)
    assert meta["history"]["rewinds"][-1]["run"] == "stuck"
    assert [chapter["number"] for chapter in meta["chapters"]["list"]] == [1, 2]
    assert meta["state"]["last_image_file"] == page_file(GOOD - 1)


def test_a_run_not_in_the_history_is_refused(stuck):
    done = stuck.rewind("--run", "nothing-like-it")
    assert done.returncode == 2 and "has no run nothing-like-it" in done.stdout, done.stdout
    assert len(stuck.pages()) == GOOD + BAD


def test_going_back_past_the_newest_page_is_refused(stuck):
    done = stuck.rewind("--from", GOOD + BAD + 1)
    assert done.returncode == 2 and "nothing is held from page 15 on" in done.stdout, done.stdout


def test_a_comic_never_walked_goes_back_by_its_numbered_files(library):
    #no index and no alignment: the numbers in the names say which file is which page, and where to start
    #comes from the run that started at that page
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    write_pages(comic, GOOD + BAD, None, None)
    done = run("chapters.py", "rewind", comic, "--root", library, "--from", GOOD)
    assert done.returncode == 0, done.stdout[-1500:]
    meta = read_meta(comic)
    assert (meta["settings"]["url"], meta["settings"]["increment"]) == ("https://x.test/p10", GOOD)
    #its single archive, of which there is none yet here, is not made up out of nothing
    assert not (library / "CBZs" / "Stuck.cbz").exists()


def test_an_address_nothing_knows_has_to_be_given(library):
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    write_pages(comic, GOOD + BAD, None, None)
    #page 12, and page 11 before it: neither in an index, nor where a run started
    done = run("chapters.py", "rewind", comic, "--root", library, "--from", 12)
    assert done.returncode == 2 and "--url" in done.stdout, done.stdout
    given = run("chapters.py", "rewind", comic, "--root", library, "--from", 12, "--url", "https://x.test/p12")
    assert given.returncode == 0, given.stdout[-1500:]
    meta = read_meta(comic)
    assert (meta["settings"]["url"], meta["settings"]["increment"]) == ("https://x.test/p12", 12)


def test_an_index_read_from_the_site_is_kept_whole(library, chapters):
    #read from a site's own list of its posts, it holds the pages to come as well as those held: the site's,
    #not the run's. only which file is which goes from the alignment
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    cache = chapters.index_path(str(comic))
    write_pages(comic, GOOD + BAD, None, cache, listed=20)
    done = run("chapters.py", "rewind", comic, "--root", library, "--from", GOOD + 1)
    assert done.returncode == 0, done.stdout[-1500:]
    assert "kept whole" in done.stdout
    with open(cache, encoding="utf-8") as f:
        assert sum(1 for line in f if line.strip()) == 20
    with open(cache.replace(".jsonl", ".align.json"), encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    assert len(pages) == 20 and [page["n"] for page in pages if page["file"]] == list(range(1, GOOD + 1))


def test_a_single_archive_is_written_afresh_from_the_pages_left(library):
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    write_pages(comic, GOOD + BAD, None, None)
    archive = library / "CBZs" / "Stuck.cbz"
    with zipfile.ZipFile(str(archive), "w") as zf:
        for name in sorted(os.listdir(str(comic))):
            zf.write(str(comic / name), name)
    done = run("chapters.py", "rewind", comic, "--root", library, "--from", GOOD + 1)
    assert done.returncode == 0, done.stdout[-1500:]
    with zipfile.ZipFile(str(archive)) as zf:
        held = sorted(name for name in zf.namelist() if name.endswith(".png"))
    assert held == [page_file(n) for n in range(1, GOOD + 1)], held


def test_a_plugin_comic_is_refused(library):
    comic = library / "Uncompressed" / "Stuck"
    comic.mkdir(parents=True)
    write_pages(comic, GOOD + BAD, None, None, settings={"scraper": "example"})
    done = run("chapters.py", "rewind", comic, "--root", library, "--from", GOOD)
    assert done.returncode == 2 and "plugin" in done.stdout, done.stdout
    assert len([name for name in os.listdir(str(comic)) if name.endswith(".png")]) == GOOD + BAD
