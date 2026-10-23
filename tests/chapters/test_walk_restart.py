#a record of which page is which that begins in the middle: position is meaning, so line 1 has to be the
#comic's page 1. such a record cannot be carried on from, and nothing should write one. a real browser walks
#a five page comic served from here.
import json
import os

import pytest

from conftest import PNG_240, Comic, run, write_index, write_meta

PAGES = 5
CACHE = "MyComic.stub.jsonl"
pytestmark = [pytest.mark.browser, pytest.mark.slow]


@pytest.fixture
def site(serve):
    return serve(Comic)


@pytest.fixture
def comic(library, site):
    folder = library / "Uncompressed" / "MyComic"
    folder.mkdir()
    for n in range(1, PAGES + 1):
        (folder / "{0:04d}.png".format(n)).write_bytes(PNG_240)
    return folder


def write_metadata(folder, site, index_cache=None):
    history = {"first_page_url": site + "/p/1", "first_page_number": 1, "runs": []}
    if index_cache:
        history["index_cache"] = index_cache
    write_meta(folder, {"schema": 2, "settings": {"url": site + "/p/{0}".format(PAGES), "output": str(folder),
                                                  "cbz_path": None, "increment": PAGES, "prefix": False,
                                                  "javascript": False, "cbz": False, "ended": False},
                        "state": {}, "history": history})


def read_index(path):
    with open(str(path), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_a_scrape_part_way_through_a_comic_does_not_start_a_record(config, comic, site):
    write_metadata(comic, site)
    done = run("mirror_base.py", "-o", comic, "--no-cbz", "--keep-index", "-i", "4", "--prime",
               site + "/p/4", timeout=600)
    made = [p.name for p in (config / "index").iterdir()]
    assert "has to begin at the comic's first page" in done.stdout, done.stdout[-300:]
    assert not made, made


def test_a_scrape_from_the_first_page_still_keeps_one(config, comic, site):
    write_metadata(comic, site)
    run("mirror_base.py", "-o", comic, "--no-cbz", "--keep-index", "-i", "1", "--prime", site + "/p/1",
        timeout=600)
    made = [p for p in (config / "index").iterdir() if p.name.endswith(".jsonl")]
    assert len(made) == 1, made
    lines = read_index(made[0])
    assert len(lines) == 1 and lines[0]["n"] == 1, "should hold the page it started on: {0}".format(lines)


def test_a_record_that_begins_in_the_middle_is_thrown_away_on_restart(config, library, comic, site):
    write_metadata(comic, site, CACHE)
    #exactly what a scrape of an up to date comic leaves: the newest page, called page one
    write_index(config / "index" / CACHE, [{"n": 1, "url": site + "/p/{0}".format(PAGES),
                                            "src": site + "/img/0005.png", "file": "0005.png",
                                            "title": "Comic 5", "bytes": len(PNG_240)}])
    done = run("chapters.py", "index", comic, "--root", library, "--restart", "--start", site + "/p/1",
               timeout=600)
    assert "Throwing away the record of 1 page(s)" in done.stdout, done.stdout[:500]
    #set aside rather than deleted, so a walk that goes wrong loses nothing
    kept = [name for name in os.listdir(str(config / "index")) if ".replaced-" in name and name.endswith(".jsonl")]
    assert len(kept) == 1 and read_index(config / "index" / kept[0])[0]["file"] == "0005.png", kept
    lines = read_index(config / "index" / CACHE)
    assert len(lines) == PAGES, "the whole comic should be walked: {0}".format([one.get("url") for one in lines])
    assert lines[0]["url"].endswith("/p/1"), lines[:1]
    assert lines[-1]["url"].endswith("/p/{0}".format(PAGES)), lines[-1:]
    assert [one["n"] for one in lines] == list(range(1, PAGES + 1)), [one["n"] for one in lines]


class BackLinked(Comic):
    #every page's link marked rel="next", which the shipped paths find first, leads back to the beginning; the
    #way on is a link only this comic's own path knows. a scrape goes by that path, and a walk has to as well
    def page(self, number):
        onward = '<a class="onward" href="/p/{0}">On</a>'.format(number + 1) if number < self.pages else ""
        return ('<html><head><title>Comic {0}</title></head><body><a rel="next" href="/p/1">Start</a>'
                '<img id="cc-comic" width="240" height="240" src="/img/{0:04d}.png">{1}</body></html>'.format(
                    number, onward))


def test_a_walk_follows_the_links_the_comics_scrapes_do(config, library, comic, serve):
    site = serve(BackLinked)
    write_metadata(comic, site)
    meta = json.loads((comic / "mirror_metadata.json").read_text(encoding="utf-8"))
    meta["state"] = {"image_xpath": '//*[@id="cc-comic"]', "next_xpath": '//a[@class="onward"]'}
    write_meta(comic, meta)
    done = run("chapters.py", "index", comic, "--root", library, "--start", site + "/p/1", timeout=600)
    made = [p for p in (config / "index").iterdir() if p.name.endswith(".jsonl")]
    assert len(made) == 1, (made, done.stdout[-600:])
    lines = read_index(made[0])
    assert [one["url"].rsplit("/", 1)[-1] for one in lines] == [str(n) for n in range(1, PAGES + 1)], \
        done.stdout[-600:]


def test_walking_again_from_the_web_page_makes_the_record_afresh(config, library, comic, site, web):
    #a record a scrape folded several pictures into one line of reaches the newest page, so working out chapters
    #never walks it again: the Pages dialog's Walk it again does, as a queued job
    write_metadata(comic, site, CACHE)
    write_index(config / "index" / CACHE, [{"n": 1, "url": site + "/p/1", "src": site + "/img/0001.png",
                                            "file": "0001.png", "title": "Comic 1", "bytes": len(PNG_240)}])
    page = web()
    code, answer = page.call("/api/walkagain", {"name": "Uncompressed/MyComic"})
    assert code == 200 and answer["label"] == "Walk again: Uncompressed/MyComic", answer
    assert page.wait_idle(600), "the walk never finished"
    _, state = page.call("/api/state")
    done = next(job for job in state["history"] if job["id"] == answer["queued"])
    assert not done["error"] and done["outcome"].startswith("{0} pages walked".format(PAGES)), done
    assert len(read_index(config / "index" / CACHE)) == PAGES
    assert [name for name in os.listdir(str(config / "index")) if ".replaced-" in name and name.endswith(".jsonl")]


def test_a_comic_another_program_scrapes_is_not_walked(config, library, comic, site, web):
    write_metadata(comic, site)
    meta = json.loads((comic / "mirror_metadata.json").read_text(encoding="utf-8"))
    meta["settings"]["scraper"] = "example"
    write_meta(comic, meta)
    code, answer = web().call("/api/walkagain", {"name": "Uncompressed/MyComic"})
    assert code == 400 and "plugin" in answer["error"], answer


def test_without_restart_a_record_carries_on_as_before(config, library, comic, site):
    write_metadata(comic, site, CACHE)
    write_index(config / "index" / CACHE, [
        {"n": n, "url": site + "/p/{0}".format(n), "src": site + "/img/{0:04d}.png".format(n),
         "file": "{0:04d}.png".format(n), "title": "Comic {0}".format(n)} for n in (1, 2)])
    done = run("chapters.py", "index", comic, "--root", library, timeout=600)
    lines = read_index(config / "index" / CACHE)
    assert "Throwing away" not in done.stdout, done.stdout[:300]
    assert len(lines) == PAGES, "the walk should carry on to the end: {0}".format([one.get("n") for one in lines])
