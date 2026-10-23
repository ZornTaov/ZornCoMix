#the Pages dialog: which file is which page, said from the web page and run through chapters.py pagefix, so
#the page and the command line mean the same by it. nothing here reaches a site: a picture is sent, not fetched.
import base64
import json
import os
import struct
import zlib

import pytest

from conftest import open_page, read_meta, run, wait_until
from test_page_fixes import build, SITE

NAME = "Uncompressed/Toy"


@pytest.fixture
def repeat(library, chapters):
    #a site showing page 3's picture in page 4's slot, lined up once so the page has something to show
    sizes = {n: 300 + 37 * n for n in range(1, 7)}
    lines = [(SITE + str(n), "p{0}.png".format(n), sizes[3] if n == 4 else sizes[n]) for n in range(1, 7)]
    folder = build(library, chapters, lines, {"p{0}.png".format(n): sizes[n] for n in range(1, 7)})
    run("chapters.py", "align", folder, "--root", library)
    return folder


def png():
    #a real one pixel picture, so the server can tell what kind it is from its bytes
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def test_the_pages_say_what_kept_the_comic_from_settling(repeat, web):
    page = web()
    code, answer = page.call("/api/pages", {"name": NAME})
    assert code == 200 and answer["settled"] is False and answer["fixes"] == [], answer
    assert [one["n"] for one in answer["report"]["conflict"]] == [4], answer["report"]
    assert answer["pages"][3]["bytes"] == 300 + 37 * 3 and answer["pages"][3]["how"], answer["pages"][3]


def test_an_alignment_from_before_reports_is_lined_up_again_from_the_page(repeat, library, chapters, web):
    #what every comic lined up before this has: no report, so nothing for the dialog to show
    path = chapters.alignment_path(chapters.index_path(str(repeat), str(library), None))
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    saved.pop("report")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(saved, f)
    page = web()
    assert page.call("/api/pages", {"name": NAME})[1]["report"] is None
    code, answer = page.call("/api/pagefix", {"name": NAME, "align": True})
    assert code == 200 and answer["settled"] is False, answer
    assert page.call("/api/pages", {"name": NAME})[1]["report"]["conflict"][0]["n"] == 4


def test_pinning_from_the_page_settles_the_comic(repeat, web):
    page = web()
    code, answer = page.call("/api/pagefix", {"name": NAME, "at": "4", "file": "p4.png", "note": "page 3 shown"})
    assert code == 200 and answer["settled"] is True, answer
    _, shown = page.call("/api/pages", {"name": NAME})
    assert shown["settled"] and shown["pages"][3]["how"] == "hand", shown["pages"][3]
    assert shown["fixes"][0]["what"] == "pin" and shown["fixes"][0]["note"] == "page 3 shown", shown["fixes"]


def test_a_new_picture_replaces_the_page_and_the_old_one_is_set_aside(repeat, web):
    page = web()
    picture = "data:image/png;base64," + base64.b64encode(png()).decode()
    code, answer = page.call("/api/pagefix", {"name": NAME, "at": "4", "picture": picture})
    assert code == 200 and answer["settled"], answer.get("output", answer)
    assert (repeat / "p4.png").read_bytes() == png()
    #never deleted: the copy that was there is in the comic's set-aside folder, to be moved back
    assert (repeat / ".set aside" / "p4.png").stat().st_size == 300 + 37 * 4
    assert read_meta(repeat)["page_fixes"][0]["file"] == "p4.png"
    #and nothing was left behind outside the comic either
    assert not [name for name in os.listdir(str(repeat)) if name.endswith(".writing")]


def test_a_picture_of_another_kind_takes_its_own_ending(repeat, web):
    page = web()
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    code, answer = page.call("/api/pagefix", {"name": NAME, "at": "4", "picture": base64.b64encode(jpeg).decode()})
    assert code == 200, answer
    assert (repeat / "p4.jpg").read_bytes() == jpeg and not (repeat / "p4.png").exists()
    assert read_meta(repeat)["page_fixes"][0]["file"] == "p4.jpg"


def test_what_is_not_a_picture_is_refused_and_nothing_changes(repeat, web):
    page = web()
    code, answer = page.call("/api/pagefix", {"name": NAME, "at": "4",
                                              "picture": base64.b64encode(b"<html>not this</html>").decode()})
    assert code == 400 and "not a picture" in answer["error"], answer
    assert (repeat / "p4.png").stat().st_size == 300 + 37 * 4
    assert "page_fixes" not in read_meta(repeat)


def test_a_file_that_is_not_there_is_refused(repeat, web):
    page = web()
    code, answer = page.call("/api/pagefix", {"name": NAME, "at": "4", "file": "nothing.png"})
    assert code == 400 and "is not in" in answer["error"], answer


def test_a_file_the_walk_never_saw_is_placed_from_the_page(repeat, library, web):
    (repeat / "zz_found.png").write_bytes(b"x" * 999)
    page = web()
    run("chapters.py", "align", repeat, "--root", library)
    _, shown = page.call("/api/pages", {"name": NAME})
    assert "zz_found.png" in shown["report"]["spare"], shown["report"]
    code, answer = page.call("/api/pagefix", {"name": NAME, "file": "zz_found.png", "after": "2"})
    assert code == 200, answer
    _, shown = page.call("/api/pages", {"name": NAME})
    assert shown["report"]["spare"] == [] and shown["fixes"][0]["what"] == "stray", shown


@pytest.mark.browser
def test_every_page_of_a_long_comic_is_drawn_a_block_at_a_time(library, chapters, web, browser):
    #a row of inputs and buttons for each of a comic's thousands of pages, drawn again after every change,
    #made the dialog crawl: only a block is ever drawn, and going to a page opens the block holding it
    lines = [(SITE + str(n), "p{0}.png".format(n), 300 + n) for n in range(1, 251)]
    folder = build(library, chapters, lines, {"p{0}.png".format(n): 300 + n for n in range(1, 251)})
    run("chapters.py", "align", folder, "--root", library)
    page = web()
    open_page(browser, page.base + "/")
    browser.execute_script("openEditor(arguments[0]).then(() => document.getElementById('edit-pages').click())", NAME)
    wait_until(lambda: browser.execute_script("return document.getElementById('pf-who').innerText").endswith("250 page(s)"),
               why="the pages never loaded")
    script = browser.execute_script
    script("const s = document.getElementById('pf-show'); s.value = 'all'; s.dispatchEvent(new Event('change'))")
    rows = lambda: script("return [...document.querySelectorAll('#pf-rows tr')].map(r => Number(r.dataset.n))")
    assert rows() == list(range(1, 101)), rows()[:3]
    assert "rows 1-100 of 250" in script("return document.getElementById('pf-count').innerText")
    script("document.getElementById('pf-later').click()")
    assert rows()[0] == 101 and len(rows()) == 100
    script("const g = document.getElementById('pf-go'); g.value = '230'; g.dispatchEvent(new Event('change'))")
    assert rows() == list(range(201, 251)), rows()[:3]
    assert script("return document.querySelector(\"#pf-rows tr[data-n='230']\").classList.contains('marked')")
    assert script("return document.getElementById('pf-later').disabled")


@pytest.mark.browser
def test_the_dialog_shows_the_page_and_pins_it(repeat, web, browser):
    page = web()
    open_page(browser, page.base + "/")
    browser.execute_script("openEditor(arguments[0]).then(() => document.getElementById('edit-pages').click())", NAME)
    row = "#pf-rows tr[data-n='4']"
    wait_until(lambda: browser.execute_script("return !!document.querySelector(arguments[0])", row),
               why="page 4 was never shown")
    said = browser.execute_script("return document.querySelector(arguments[0]).innerText", row)
    assert "the site gives it the size of" in said, said
    assert "Not settled" in browser.execute_script("return document.getElementById('pf-said').innerText")
    browser.execute_script("document.querySelector(arguments[0] + \" [data-pf-act='pin']\").click()", row)
    wait_until(lambda: "settled" in browser.execute_script("return document.getElementById('pf-msg').innerText"),
               why=browser.execute_script("return document.getElementById('pf-msg').innerText"))
    assert "Saved, and the comic is settled" in browser.execute_script("return document.getElementById('pf-msg').innerText")
    assert "pinned by hand" in browser.execute_script("return document.querySelector(arguments[0]).innerText", row)
