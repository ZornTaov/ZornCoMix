#a comic behind an age gate. the site checks a cookie on every request: without it each page is the gate - no
#comic, a link to say you are old enough - and every picture is refused. the comic's settings carry the cookie,
#and everything that reads the site carries it from there: the scrape's browser, the pictures it fetches, a walk
#for chapters, a refetch.
import argparse
import json

import pytest
import requests

from comiclib import cookies
from comiclib.metadata import settings_to_argv
from comiclib.runrecord import settings_from_args
from conftest import PNG_240, Comic, pages_in, read_meta, run, write_index, write_meta
from comiclib.chapters.archive_page import read_archive

PAGES = 4
PASS = "AGE_OK=yes"
#a fresh profile for every browser: the test pool's profiles keep cookies, and a cookie is a host's whatever
#its port, so one left by another test would let a browser through a gate it was never given the cookie for
OWN_PROFILE = {"MIRROR_PROFILE_POOL": ""}


def passed(handler):
    return PASS in (handler.headers.get("Cookie") or "")


class Gated(Comic):
    pages = PAGES
    #what the gate's button says, and where it sends a reader: back to the page asked for, or - as plenty of
    #gates do - to the front page
    says = "Let me in"
    sends_back = True
    #anything else the gate shows: a warning drawn as a picture, say
    shows = ""

    def gate(self, back):
        return ('<html><head><title>Are you old enough?</title></head><body><p>This comic is for adults.</p>'
                '{0}<a id="enter" href="/enter?next={1}">{2}</a></body></html>'.format(
                    self.shows, back if self.sends_back else "/p/1", self.says))

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/enter":
            #the gate's button: the cookie, and back to the page that was asked for
            self.send_response(302)
            self.send_header("Set-Cookie", PASS + "; Path=/")
            self.send_header("Location", query.partition("next=")[2] or "/p/1")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not passed(self):
            if path.startswith("/img/"):
                self.send_error(403)
            else:
                self.send(self.gate(path))
            return
        Comic.do_GET(self)


# ---------------- the settings ----------------
def test_a_cookie_is_given_as_name_equals_value():
    assert cookies.parse(["AGE_OK=yes", "theme=dark=mode"]) == {"AGE_OK": "yes", "theme": "dark=mode"}
    with pytest.raises(ValueError, match="name=value"):
        cookies.parse(["AGE_OK"])


def test_the_settings_carry_cookies_to_the_command():
    #and back from it, with every other setting, in test_roundtrip
    settings = {"url": "https://example.com/1", "cookies": {"AGE_OK": "yes"}}
    argv = settings_to_argv(settings)
    assert argv[-3:] == ["--cookie", "AGE_OK=yes", "https://example.com/1"]
    assert "--cookie" not in settings_to_argv({"url": "https://example.com/1"})


def test_only_a_comic_with_cookies_has_them_in_its_settings():
    #every other comic's sidecar stays as it was, rather than gaining an empty block the day it next runs
    args = argparse.Namespace(cbz_path=None, prefix=True, enable_javascript=False, firefox=False, waittime=0,
                              cbz=True, direction_check=True, multi_page=True)
    assert "cookies" not in settings_from_args(args, "Uncompressed/A", "https://example.com/1", 1)
    args.cookies = {"AGE_OK": "yes"}
    assert settings_from_args(args, "Uncompressed/A", "https://example.com/1", 1)["cookies"] == {"AGE_OK": "yes"}


@pytest.mark.parametrize("comic, asked, sent", [
    ("https://www.example.com/c/1", "https://example.com/x", True),
    ("https://www.example.com/c/1", "https://static.example.com/1.png", True),
    ("https://www.example.com/c/1", "https://notexample.com/x", False),
    ("https://www.example.com/c/1", "https://example.org/x", False),
    ("http://127.0.0.1:8000/c/1", "http://127.0.0.1:9000/x", True),
    ("http://127.0.0.1:8000/c/1", "http://127.0.0.2/x", False),
    ("http://localhost:8000/c/1", "http://localhost:8000/x", True),
])
def test_a_cookie_goes_to_the_comic_site_and_its_neighbours_only(comic, asked, sent):
    #a picture served from static.example.com beside www.example.com is checked against the same cookie; a site
    #that is no part of the comic is never sent it
    made = cookies.session({"AGE_OK": "yes"}, comic)
    header = made.prepare_request(requests.Request("GET", asked)).headers.get("Cookie")
    assert (header == PASS) is sent


# ---------------- reading the site ----------------
def missing_a_page(library, chapters, base, name, settings):
    #a walked comic whose folder has lost its second page, on a site that refuses its pictures without the
    #cookie
    comic = library / "Uncompressed" / name
    comic.mkdir()
    write_meta(comic, {"schema": 2, "settings": dict({"url": base + "/p/2", "output": "Uncompressed/" + name,
                                                      "increment": 2, "cbz": False}, **settings),
                       "history": {"runs": []}})
    (comic / "0001.png").write_bytes(PNG_240)
    cache = chapters.index_path(str(comic))
    lines = [{"n": n, "url": "{0}/p/{1}".format(base, n), "src": "{0}/img/{1:04d}.png".format(base, n),
              "file": "{0:04d}.png".format(n), "title": "t", "bytes": len(PNG_240)} for n in (1, 2)]
    write_index(cache, lines)
    with open(cache.replace(".jsonl", ".align.json"), "w") as f:
        json.dump({"comic": str(comic), "settled": True,
                   "pages": [dict(lines[0], how="name"), dict(lines[1], file=None, how=None)]}, f)
    return comic


@pytest.mark.parametrize("settings, fetched", [({}, False), ({"cookies": {"AGE_OK": "yes"}}, True)])
def test_a_refetch_carries_the_comic_cookie(library, chapters, serve, settings, fetched):
    comic = missing_a_page(library, chapters, serve(Gated), "Gated", settings)
    done = run("chapters.py", "refetch", comic, "--root", library, "--missing")
    assert "1 page(s) missing here" in done.stdout, done.stdout[-800:]
    assert any(name.startswith("0002") for name in pages_in(comic)) is fetched, done.stdout[-800:]
    if not fetched:
        assert "403" in done.stdout, done.stdout[-800:]


def test_an_archive_page_is_read_with_the_comic_cookie(serve):
    #a gate has no chapters, so an archive read without the cookie would find none
    base = serve(Gated)
    try:
        cookies.use({"url": base + "/p/1"})
        assert "Are you old enough" in read_archive(base + "/p/2")
        cookies.use({"url": base + "/p/1", "cookies": {"AGE_OK": "yes"}})
        assert "cc-comic" in read_archive(base + "/p/2")
    finally:
        cookies.use({})


@pytest.mark.browser
def test_without_the_cookie_a_scrape_sees_only_the_gate(tmp_path, serve):
    site = serve(Gated)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", site + "/p/1", cwd=tmp_path, env=OWN_PROFILE)
    assert done.returncode != 0
    assert not out.exists() or pages_in(out) == []


@pytest.mark.browser
def test_with_the_cookie_a_scrape_saves_every_page_and_keeps_it(tmp_path, serve):
    site = serve(Gated)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", "--cookie", PASS, site + "/p/1", cwd=tmp_path,
               env=OWN_PROFILE)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}.png".format(n) for n in range(1, PAGES + 1)]
    #written into the settings, so every later run - rebuilt from them - is given it again
    assert read_meta(out)["settings"]["cookies"] == {"AGE_OK": "yes"}


@pytest.mark.browser
def test_a_bad_cookie_is_a_usage_error(tmp_path, serve):
    site = serve(Gated)
    done = run("mirror_base.py", "-o", tmp_path / "comic", "--cookie", "AGE_OK", site + "/p/1", cwd=tmp_path)
    assert done.returncode == 2
    assert "name=value" in done.stdout


# ---------------- the gate's button ----------------
class OverEighteen(Gated):
    #the commonest wording, which the shipped gate paths know without being told
    says = "I am over 18"


class ToTheFront(Gated):
    #a gate that sends whoever passes it to the front page, not back to the page they asked for
    sends_back = False


class Warning(Gated):
    #a gate whose warning is a picture an image path matches: taken for the comic, that picture's path was
    #remembered as the comic's, and on the real pages it found the site's masthead, page after page
    shows = '<div id="wrap"><img id="cc-comic" src="/img/warning.png"></div>'


class ScriptButton(Gated):
    #a gate whose button sets its cookie with a script, which a browser without javascript never runs
    def gate(self, back):
        return ('<html><body><p>This comic is for adults.</p><button id="enter" onclick="document.cookie='
                "'{0}; path=/'; location.href='{1}'\">Let me in</button></body></html>".format(PASS, back))


def gate_path(config, xpath='//*[@id="enter"]'):
    (config / "element_paths.json").write_text(json.dumps({"gate": [{"xpath": xpath, "note": "this site"}]}),
                                               encoding="utf-8")


def scraped(tmp_path, site, *extra):
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", *extra, site + "/p/2", cwd=tmp_path, env=OWN_PROFILE)
    return out, done


@pytest.mark.browser
@pytest.mark.parametrize("handler", [Gated, ToTheFront])
def test_a_gate_path_presses_past_the_gate(tmp_path, config, serve, handler):
    gate_path(config)
    out, done = scraped(tmp_path, serve(handler))
    assert done.returncode == 0, done.stdout[-800:]
    assert "is the site's age gate; pressing" in done.stdout
    #from the page asked for, wherever the gate sent the browser - and the pictures fetched with the cookie
    #the gate set in the browser
    assert pages_in(out) == ["{0:04d}.png".format(n) for n in range(2, PAGES + 1)], done.stdout[-800:]
    #the gate's answer is the gate's to give each run: only a cookie given to the comic is its setting
    assert "cookies" not in read_meta(out)["settings"]


@pytest.mark.browser
def test_the_shipped_gate_paths_know_the_commonest_wording(tmp_path, config, serve):
    out, done = scraped(tmp_path, serve(OverEighteen))
    assert done.returncode == 0, done.stdout[-800:]
    assert len(pages_in(out)) == PAGES - 1


@pytest.mark.browser
def test_a_gate_picture_never_becomes_the_comic_image_path(tmp_path, config, serve):
    gate_path(config)
    out, done = scraped(tmp_path, serve(Warning))
    assert done.returncode == 0, done.stdout[-800:]
    assert "warning" not in " ".join(pages_in(out))
    assert len(pages_in(out)) == PAGES - 1


@pytest.mark.browser
def test_a_gate_that_stays_says_how_to_get_past_it(tmp_path, config, serve):
    #without javascript the button's script never runs, and the gate is still there after it is pressed
    gate_path(config)
    out, done = scraped(tmp_path, serve(ScriptButton))
    assert done.returncode != 0
    assert "still shows the gate" in done.stdout and "--cookie" in done.stdout, done.stdout[-800:]


@pytest.mark.browser
def test_a_gate_that_needs_javascript_is_passed_with_it(tmp_path, config, serve):
    gate_path(config)
    out, done = scraped(tmp_path, serve(ScriptButton), "--enable_javascript")
    assert done.returncode == 0, done.stdout[-800:]
    assert len(pages_in(out)) == PAGES - 1


@pytest.mark.browser
def test_a_walk_for_chapters_carries_the_comic_cookie(library, chapters, serve):
    site = serve(Gated)
    comic = library / "Uncompressed" / "Gated"
    done = run("mirror_base.py", "-o", comic, "--no-cbz", "--no-keep-index", "--cookie", PASS, site + "/p/1",
               cwd=library, env=OWN_PROFILE)
    assert done.returncode == 0, done.stdout[-800:]
    done = run("chapters.py", "index", comic, "--root", library, env=OWN_PROFILE)
    with open(chapters.index_path(str(comic)), encoding="utf-8") as f:
        walked = [json.loads(line)["url"].rsplit("/", 1)[-1] for line in f if line.strip()]
    assert walked == [str(n) for n in range(1, PAGES + 1)], done.stdout[-800:]
