#a comic's settings edited from the web page: read, refused when wrong or stale, saved and updated from,
#brought up from an older schema, and left alone while it is being scraped.
import json
import shutil
import time

import pytest

from conftest import PNG, Site, console_errors, open_page, pages_in, read_meta, run, wait_until, write_meta

pytestmark = [pytest.mark.browser, pytest.mark.slow]
LAST = 8


class Broken(Site):
    #pages 1-3 link on, page 3's next link is broken (it goes to a page with no image), and the story
    #actually carries on at /c/5 through /c/8. a subclass with `slow` set takes its time from page 5 on,
    #so a run over them can be caught while it is going
    slow = False

    def do_GET(self):
        if self.path.startswith("/img/"):
            self.send(PNG, "image/png")
            return
        number = self.path.rsplit("/", 1)[-1]
        if not number.isdigit():
            self.send_error(404)
            return
        number = int(number)
        if self.slow and number >= 5:
            time.sleep(1.0)
        if number == 4:
            self.send("<html><body><p>broken page</p></body></html>")
            return
        link = '<a href="/c/{0}">Next</a>'.format(number + 1) if number < LAST else ""
        self.send('<html><body><div id="wrap">{1}<img id="cc-comic" src="/img/{0:04d}.png">'
                  '</div></body></html>'.format(number, link))


class SlowBroken(Broken):
    slow = True


NAME = "Uncompressed/MyComic"


@pytest.fixture
def scraped(serve, library, tmp_path):
    #scraped until the broken page, the way the comic would be found in a library
    site = serve(Broken)
    comic = library / "Uncompressed" / "MyComic"
    run("mirror_base.py", "-o", comic, site + "/c/1", cwd=tmp_path)
    return site, comic


def test_reading_a_comic_and_refusing_bad_edits(scraped, web):
    site, comic = scraped
    page = web()
    code, detail = page.call("/api/comic?name=" + NAME)
    assert code == 200, detail
    #a next link to a page with no comic on it reads as the comic going no further for now, so the run
    #ends cleanly on the last good page rather than failing on the broken one
    last = detail["runs"][0]
    assert last["exit_code"] == 0 and last["stop_reason"] == "the next link led off the comic", last
    assert detail["settings"]["url"].endswith("/c/3"), detail["settings"]["url"]
    assert detail["pages_in_folder"] == 3, detail
    assert page.call("/api/comic?name=Nope")[0] == 404

    before = (comic / "mirror_metadata.json").read_text(encoding="utf-8")
    code, answer = page.call("/api/settings", {"name": NAME, "updated": detail["updated"],
                                               "settings": {"url": "not a url", "increment": "-3"}})
    assert code == 400 and "http" in answer["error"] and "increment" in answer["error"], answer
    #an edit made against a copy older than the file would undo whatever changed it since
    code, answer = page.call("/api/settings", {"name": NAME, "updated": "2000-01-01T00:00:00Z",
                                               "settings": {"url": site + "/c/5"}})
    assert code == 409, answer
    assert (comic / "mirror_metadata.json").read_text(encoding="utf-8") == before


def test_pointing_a_comic_past_a_broken_page_and_updating(scraped, web):
    site, comic = scraped
    page = web()
    _, detail = page.call("/api/comic?name=" + NAME)
    shutil.copy(str(comic / "0003.png"), str(comic / "0004.png"))  # the page found by hand
    code, answer = page.call("/api/settings", {"name": NAME, "updated": detail["updated"], "update_after": True,
                                               "settings": dict(detail["settings"], url=site + "/c/5",
                                                                increment=5)})
    assert code == 200 and answer["saved"] and answer.get("queued"), answer
    assert set(answer["changed"]) == {"url", "increment"}, answer
    assert "output" not in answer["changed"]
    assert page.wait_idle(120), "the update never finished"
    assert pages_in(comic) == ["{0:04d}.png".format(n) for n in range(1, LAST + 1)]
    meta = read_meta(comic)
    assert len(meta["history"].get("edits", [])) == 1, "the run should keep the edit log: {0}".format(
        list(meta["history"].keys()))
    #the run's own first page is still the comic's first page, not where the edit pointed it
    assert meta["history"]["first_page_url"].endswith("/c/1"), meta["history"]


def test_a_comic_is_edited_but_not_while_running(serve, library, web):
    site = serve(SlowBroken)
    old = library / "Uncompressed" / "Old"
    old.mkdir(parents=True)
    (old / "0001.png").write_bytes(PNG)
    with open(old / "mirror_metadata.json", "w", encoding="utf-8") as f:
        json.dump({"schema": 2, "settings": {"url": site + "/c/1", "output": "Uncompressed/Old", "increment": 1},
                   "history": {"runs": [{"run_id": "x", "stop_reason": "no next button", "exit_code": 0}]}}, f)
    page = web()

    code, detail = page.call("/api/comic?name=Uncompressed/Old")
    assert code == 200 and detail["settings"]["url"].endswith("/c/1"), detail
    code, answer = page.call("/api/settings", {"name": "Uncompressed/Old", "updated": detail["updated"],
                                               "settings": dict(detail["settings"], ended=True)})
    meta = read_meta(old)
    assert code == 200 and meta["schema"] == 2 and meta["settings"]["ended"] is True, (answer, meta)
    assert not [p.name for p in old.iterdir() if p.name.endswith(".editing")]
    assert page.call("/api/settings", {"name": "Uncompressed/Old",
                                       "settings": {"ended": True}})[1].get("saved") is False, \
        "an edit that changes nothing should say so"

    #now a comic being scraped: its settings cannot be edited under the run
    write_meta(old, dict(meta, settings=dict(meta["settings"], ended=False, url=site + "/c/5")))
    page.call("/api/update", {"names": ["Uncompressed/Old"]})
    running = False
    for _ in range(80):
        _, state = page.call("/api/state")
        if state["current"] and any(c["state"] == "running" for c in state["current"].get("comics", [])):
            running = True
            break
        time.sleep(0.25)
    try:
        _, detail = page.call("/api/comic?name=Uncompressed/Old")
        assert running and detail["running"] is True, detail.get("running")
        code, answer = page.call("/api/settings", {"name": "Uncompressed/Old", "settings": {"url": site + "/c/1"}})
        assert code == 409, answer
    finally:
        page.call("/api/stop", {})
        page.wait_idle()


def test_the_editor_opens_without_console_errors(scraped, web, browser):
    page = web()
    for width, height in ((1300, 950), (420, 1100)):
        browser.set_window_size(width, height)
        open_page(browser, page.base + "/")
        #the library table is filled in by a fetch after the page loads
        wait_until(lambda: browser.execute_script(
            "return document.querySelector('[data-edit=\"{0}\"]')".format(NAME)), why="the comic never listed")
        browser.execute_script("document.querySelector('[data-edit=\"{0}\"]').click()".format(NAME))
        time.sleep(1)
        browser.execute_script("document.getElementById('edit-runs-box').open = true")
        time.sleep(0.3)
    errors = console_errors(browser)
    assert not errors, errors


def test_the_editor_shows_one_tab_at_a_time_and_its_foot_follows(scraped, web, browser):
    #settings, chapters, pages, ComicInfo and history, each its own tab rather than a dialog stacked on the
    #editor, with the foot holding what the tab shown does and nothing of the others
    page = web()
    open_page(browser, page.base + "/")
    script = browser.execute_script
    script("openEditor(arguments[0])", NAME)
    wait_until(lambda: script("return document.getElementById('editor').open"), why="the editor never opened")
    shown = lambda: script(
        "return [[...document.querySelectorAll('#editor .tab-panel')].filter((p) => !p.hidden).map((p) => p.dataset.panel),"
        " [...document.querySelectorAll('#editor .edit-foot button')].filter((b) => b.offsetParent).map((b) => b.id)]")
    assert shown() == [["settings"], ["edit-save", "edit-save-update"]], shown()
    expected = {"edit-boundaries": ["chapters", ["bd-reset", "edit-save", "edit-save-update"]],
                "edit-pages": ["pages", ["pf-walk", "pf-align", "pf-reset"]],
                "edit-comicinfo": ["comicinfo", ["ci-save"]],
                "edit-history": ["history", []]}
    for tab, (panel, buttons) in expected.items():
        script("document.getElementById(arguments[0]).click()", tab)
        assert shown() == [[panel], buttons], (tab, shown())
        assert script("return document.getElementById(arguments[0]).getAttribute('aria-selected')", tab) == "true"
    #each tab reads what it needs the first time it is shown: the ComicInfo boxes and the comic's runs
    wait_until(lambda: script("return document.querySelectorAll('#ci-boxes input').length") > 0,
               why="the ComicInfo tab never drew its boxes")
    assert "Started" in script("return document.getElementById('edit-runs').innerText")
    #and a comic opened again starts on its settings
    script("document.getElementById('editor').close(); openEditor(arguments[0])", NAME)
    wait_until(lambda: shown()[0] == ["settings"], why="the editor did not open on its settings")
    errors = console_errors(browser)
    assert not errors, errors
