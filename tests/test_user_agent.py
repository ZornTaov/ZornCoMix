#the name the pictures and the chapter pages are fetched under. a site can refuse a name that looks like a
#scraper's - one dropped the connection on every picture asked for as a chrome years out of date, without a
#word of answer - so the library sets its own in ComicScraper.json and a comic its own in its settings, which
#beats it, and both are edited on the web page under Advanced settings.
import argparse
import json

import pytest

from comiclib import cookies, download, useragent
from comiclib.metadata import argv_to_settings, settings_to_argv
from comiclib.runrecord import settings_from_args
from conftest import (PNG_240, Comic, console_errors, open_page, pages_in, read_meta, run, wait_until,
                      write_meta)

PAGES = 3
OURS = "MyReader/1.0 (+https://example.com/about)"
#the name the scraper gave itself until this was a setting
STALE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/91.0.4472.124 Safari/537.36")


def hang_up(handler):
    #what the site did: no status, no headers, the connection closed under the request
    handler.close_connection = True


class Stale(Comic):
    #the site that started this: every picture refused to the old chrome, answered to anything else
    pages = PAGES

    def do_GET(self):
        if self.path.startswith("/img/") and "Chrome/91." in (self.headers.get("User-Agent") or ""):
            return hang_up(self)
        Comic.do_GET(self)


class Choosy(Comic):
    #a site that answers its pictures to one name only. the scrape's browser is refused them too and shows a
    #box of the image's size, which is all the scrape asks of it
    pages = PAGES
    heard = []

    def do_GET(self):
        if self.path.startswith("/img/"):
            Choosy.heard.append(self.headers.get("User-Agent"))
            if self.headers.get("User-Agent") != OURS:
                return hang_up(self)
        Comic.do_GET(self)


@pytest.fixture
def choosy(serve):
    Choosy.heard = []
    return serve(Choosy)


@pytest.fixture
def library_agent(config):
    #a ComicScraper.json naming the library's own
    def write(agent):
        with open(config / "ComicScraper.json", "w", encoding="utf-8") as f:
            json.dump({"user_agent": agent}, f)
    return write


@pytest.fixture(autouse=True)
def put_back():
    yield
    useragent.current = useragent.default


# ---------------- which name ----------------
def test_the_built_in_name_is_a_current_chromes_not_the_old_one():
    assert "Chrome/91." not in useragent.default
    assert useragent.pick() == useragent.default


def test_the_comic_beats_the_library_which_beats_the_built_in(library_agent):
    library_agent("Library/2.0")
    assert useragent.pick() == "Library/2.0"
    assert useragent.pick(OURS) == OURS
    #a blank one is no name at all, and the next one down is used
    assert useragent.pick("  ") == "Library/2.0"
    library_agent("")
    assert useragent.pick() == useragent.default


def test_a_name_is_one_line(library_agent):
    assert useragent.clean("  " + OURS + "  ") == OURS
    assert useragent.clean("") is None
    with pytest.raises(ValueError, match="one line"):
        useragent.clean("Mozilla/5.0\nX-Evil: yes")
    #one broken in the library's file falls back rather than stopping every comic's run
    library_agent("Broken\r\nname")
    assert useragent.pick() == useragent.default


def test_a_comic_name_goes_to_the_command_and_back():
    settings = {"url": "https://example.com/1", "user_agent": OURS}
    argv = settings_to_argv(settings)
    assert argv[-3:] == ["--user-agent", OURS, "https://example.com/1"]
    assert argv_to_settings(argv)["user_agent"] == OURS
    assert "--user-agent" not in settings_to_argv({"url": "https://example.com/1"})


def test_only_a_comic_with_its_own_name_has_one_in_its_settings():
    args = argparse.Namespace(cbz_path=None, prefix=True, enable_javascript=False, firefox=False, waittime=0,
                              cbz=True, direction_check=True, multi_page=True)
    assert "user_agent" not in settings_from_args(args, "Uncompressed/A", "https://example.com/1", 1)
    args.user_agent = OURS
    assert settings_from_args(args, "Uncompressed/A", "https://example.com/1", 1)["user_agent"] == OURS


def test_every_fetch_outside_the_browser_gives_the_name_in_use(choosy):
    useragent.use(OURS)
    assert download.fetch(choosy + "/img/0001.png").content == PNG_240
    assert cookies.session().get(choosy + "/img/0002.png").content == PNG_240
    assert Choosy.heard == [OURS, OURS]


# ---------------- a scrape ----------------
@pytest.mark.browser
def test_a_site_refusing_the_old_name_is_scraped_under_the_new_one(tmp_path, serve):
    site = serve(Stale)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", site + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}.png".format(n) for n in range(1, PAGES + 1)]
    #and the comic is not given a name of its own for it
    assert "user_agent" not in read_meta(out)["settings"]
    #where the old name still gets the old answer
    done = run("mirror_base.py", "-o", tmp_path / "again", "--no-cbz", "--user-agent", STALE, site + "/p/1",
               cwd=tmp_path)
    assert done.returncode == 4, done.stdout[-800:]


@pytest.mark.browser
def test_a_comic_name_is_used_and_kept(tmp_path, choosy):
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", "--user-agent", OURS, choosy + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert len(pages_in(out)) == PAGES
    #written into the settings, so every later run - rebuilt from them - is given it again
    assert read_meta(out)["settings"]["user_agent"] == OURS


@pytest.mark.browser
def test_the_library_name_is_used_without_one_of_the_comics(tmp_path, choosy, library_agent):
    library_agent(OURS)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", choosy + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert len(pages_in(out)) == PAGES
    #the library's stays the library's: a comic would otherwise keep it after the library changed it
    assert "user_agent" not in read_meta(out)["settings"]


@pytest.mark.browser
def test_a_refused_name_fails_as_a_download(tmp_path, choosy):
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", choosy + "/p/1", cwd=tmp_path)
    assert done.returncode == 4, done.stdout[-800:]
    assert "Remote end closed connection" in done.stdout or "Connection aborted" in done.stdout, done.stdout[-800:]


def test_a_name_of_two_lines_is_a_usage_error(tmp_path, choosy):
    done = run("mirror_base.py", "-o", tmp_path / "comic", "--user-agent", "A\nB", choosy + "/p/1", cwd=tmp_path)
    assert done.returncode == 2
    assert "one line" in done.stdout


def test_chapters_reads_the_site_under_the_comic_name(library, choosy):
    #an archive page read for its chapters, which chapters.py is pointed at the comic's folder for
    comic = library / "Uncompressed" / "Choosy"
    comic.mkdir()
    write_meta(comic, {"schema": 2, "settings": {"url": choosy + "/p/1", "output": "Uncompressed/Choosy",
                                                  "increment": 1, "cbz": False, "user_agent": OURS},
                       "history": {"runs": []}})
    done = run("chapters.py", "try", comic, "--archive", choosy + "/img/0001.png", "--like", choosy + "/p/1")
    assert OURS in Choosy.heard, done.stdout[-800:]


# ---------------- the web page ----------------
NAME = "Uncompressed/Choosy"


@pytest.fixture
def comic(library):
    folder = library / "Uncompressed" / "Choosy"
    folder.mkdir(parents=True)
    (folder / "0001.png").write_bytes(PNG_240)
    write_meta(folder, {
        "schema": 2, "generator": "mirror_base.py", "generator_version": "3.5",
        "created": "2026-10-01T00:00:00Z", "updated": "2026-10-01T00:00:00Z",
        "settings": {"url": "https://example.com/p/1", "output": NAME, "increment": 1, "prefix": True,
                     "javascript": False, "firefox": False, "waittime": 0, "cbz": False,
                     "direction_check": True, "multi_page": True, "ended": False},
        "history": {"runs": []},
    })
    return folder


def saved(page, agent):
    _, detail = page.call("/api/comic?name=" + NAME)
    return page.call("/api/settings", {"name": NAME, "updated": detail.get("updated"),
                                       "settings": {"user_agent": agent}})


def test_a_comic_name_is_saved_checked_and_taken_away(web, comic):
    page = web()
    code, answer = saved(page, OURS)
    assert code == 200, answer
    assert read_meta(comic)["settings"]["user_agent"] == OURS
    code, answer = saved(page, "A\nB")
    assert code == 400 and "one line" in answer["error"], answer
    code, answer = saved(page, "")
    assert code == 200 and answer.get("saved"), answer
    assert "user_agent" not in read_meta(comic)["settings"], "no empty name left behind"


def test_the_library_name_is_saved_and_the_built_in_one_said(web, config):
    page = web()
    code, cfg = page.call("/api/config")
    assert cfg["settings"]["user_agent"] is None and cfg["user_agent_default"] == useragent.default
    code, answer = page.call("/api/config", {"settings": dict(cfg["settings"], user_agent=OURS)})
    assert code == 200 and answer["settings"]["user_agent"] == OURS, answer
    code, answer = page.call("/api/config", {"settings": dict(cfg["settings"], user_agent="A\rB")})
    assert code == 400 and "one line" in answer["error"], answer
    with open(config / "ComicScraper.json", encoding="utf-8") as f:
        assert json.load(f)["user_agent"] == OURS


@pytest.mark.browser
def test_the_advanced_settings_take_this_browsers_name(web, comic, browser):
    page = web()
    open_page(browser, page.base + "/")
    mine = browser.execute_script("return navigator.userAgent")
    value = lambda box: browser.execute_script("return document.getElementById(arguments[0]).value", box)

    #the library's: shut while it holds nothing, the built-in name shown as what blank means
    browser.execute_script("document.getElementById('open-config').click()")
    wait_until(lambda: browser.execute_script("return document.getElementById('config').open"),
               why="the settings never opened")
    assert not browser.execute_script("return document.getElementById('cfg-advanced').open")
    assert browser.execute_script("return document.getElementById('c-user_agent').placeholder") == useragent.default
    browser.execute_script("document.getElementById('cfg-advanced').open = true;"
                           "document.getElementById('c-user_agent-mine').click();"
                           "document.getElementById('cfg-save').click()")
    assert value("c-user_agent") == mine
    wait_until(lambda: "Saved" in browser.execute_script("return document.getElementById('cfg-msg').textContent"),
               why="the settings were never saved")
    browser.execute_script("document.getElementById('config').close()")

    #the comic's: blank says it uses the library's, and the button fills it the same
    browser.execute_script("openEditor('{0}')".format(NAME))
    wait_until(lambda: browser.execute_script("return document.getElementById('editor').open"),
               why="the editor never opened")
    wait_until(lambda: browser.execute_script("return document.getElementById('e-user_agent').placeholder") == mine,
               why="the editor never said the library's name")
    browser.execute_script("document.getElementById('edit-advanced').open = true;"
                           "document.getElementById('e-user_agent-mine').click();"
                           "document.getElementById('edit-save').click()")
    wait_until(lambda: (read_meta(comic)["settings"].get("user_agent") == mine) or None,
               why="the comic's name was never saved")
    errors = console_errors(browser)
    assert not errors, errors
