#the editor's chapter tools, through the page's own api: reading a chapter list before anything is committed to
#it, correcting a boundary by hand, and putting in a page the comic's links skip - each refused with a reason
#the page can show when it is asked wrongly, and run through chapters.py when it is asked right.
import pytest

from conftest import console_errors, open_page, read_meta, wait_until
from test_fix_boundary import toy  # noqa: F401 - the comic of three issues, as a fixture
from test_web_edit_chapters import Archived

NAME = "Uncompressed/Toy"


def test_a_chapter_list_is_read_before_anything_is_committed_to_it(serve, library, web):
    site = serve(Archived)
    page = web()
    code, answer = page.call("/api/trylist", {"url": site + "/archive", "like": site + "/comic/page001/"})
    assert code == 200 and answer["exit_code"] == 0, answer
    for label in ("Chapter One", "Chapter Two", "Chapter Three"):
        assert label in answer["output"], answer["output"][-600:]


def test_a_chapter_list_asked_for_wrongly_is_refused_with_why(library, web):
    page = web()
    code, answer = page.call("/api/trylist", {"url": "not an address"})
    assert code == 400 and "full http(s) address" in answer["error"], answer
    #with no comic to go by, one of its pages is needed to tell its pages from the rest of the list's links
    code, answer = page.call("/api/trylist", {"url": "https://example.com/archive"})
    assert code == 400 and "one of the comic's own page addresses" in answer["error"], answer


def test_chapters_set_by_hand_from_the_editor(toy, library, web):  # noqa: F811
    page = web()
    code, answer = page.call("/api/chapterfix", {"name": NAME, "at": "1", "label": "Part One"})
    assert code == 200, answer
    code, answer = page.call("/api/chapterfix", {"name": NAME, "at": "8", "label": "Part Two"})
    assert code == 200 and "2 chapter(s) over" in answer["output"], answer
    kept = read_meta(toy)["chapters"]
    assert [c["label"] for c in kept["list"]] == ["Part One", "Part Two"], kept
    assert kept.get("source") == "hand", kept


def test_a_correction_asked_for_wrongly_is_refused_with_why(toy, library, web):  # noqa: F811
    page = web()
    code, answer = page.call("/api/chapterfix", {"name": NAME, "label": "Part One"})
    assert code == 400 and "which page" in answer["error"], answer
    code, answer = page.call("/api/chapterfix", {"name": NAME, "at": "1"})
    assert code == 400 and "what the chapter starting there is called" in answer["error"], answer
    code, answer = page.call("/api/chapterfix", {"name": "Uncompressed/Nobody", "at": "1", "label": "A"})
    assert code == 404, answer
    assert "chapters" not in read_meta(toy), "a refused correction wrote something"


def test_a_page_to_put_in_asked_for_wrongly_is_refused_with_why(toy, library, web):  # noqa: F811
    page = web()
    code, answer = page.call("/api/insert", {"name": NAME, "url": "page 3", "after": "2"})
    assert code == 400 and "full http(s) address" in answer["error"], answer
    code, answer = page.call("/api/insert", {"name": NAME, "url": "https://x.test/c/extra/"})
    assert code == 400 and "which page it follows" in answer["error"], answer
    code, answer = page.call("/api/insert", {"name": "Uncompressed/Nobody", "url": "https://x.test/c/extra/",
                                             "after": "2"})
    assert code == 404, answer


@pytest.mark.browser
def test_a_boundary_is_added_from_the_chapters_tab(toy, library, web, browser):  # noqa: F811
    page = web()
    open_page(browser, page.base + "/")
    script = browser.execute_script
    wait_until(lambda: script("return document.querySelector('[data-edit=\"{0}\"]')".format(NAME)),
               why="the comic never listed")
    script("document.querySelector('[data-edit=\"{0}\"]').click()".format(NAME))
    script("document.getElementById('edit-boundaries').click()")
    #its pages are offered once they are read, so a boundary is chosen rather than guessed at
    wait_until(lambda: "Pick from this comic's 15 pages" in browser.find_element("id", "bd-picked").text,
               why="the comic's pages were never offered")

    #a page typed by its number is said back as the page it is
    browser.find_element("id", "bd-new-at").send_keys("8")
    wait_until(lambda: browser.find_element("id", "bd-picked").text.startswith("page 8:"),
               why="the page typed was never said back")
    label = browser.find_element("id", "bd-new-label")
    label.clear()
    label.send_keys("Part Two")
    browser.find_element("id", "bd-add").click()
    wait_until(lambda: browser.find_element("id", "edit-msg").text == "Saved.", limit=120,
               why="the boundary was never saved")
    assert "Part Two" in script("return [...document.querySelectorAll('#bd-rows input')].map(i => i.value).join()")
    assert [c["label"] for c in read_meta(toy)["chapters"]["list"]] == ["Part Two"]

    #a page to put in, given no address, is refused on the page before anything is asked of the server
    script("document.getElementById('bd-insert-box').open = true")
    browser.find_element("id", "bd-in-url").send_keys("the skipped one")
    browser.find_element("id", "bd-in-try").click()
    assert "full address" in browser.find_element("id", "edit-msg").text
    assert not console_errors(browser)
