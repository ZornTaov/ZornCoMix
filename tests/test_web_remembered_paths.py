#the element paths a scrape remembers a comic by, put right from the editor: a wrong image path keeps saving
#a site's user icon as page after page, and a wrong next path calls the comic caught up every day, for as long
#as each matches anything - so they are edited with the comic's other settings, in its advanced section.
import pytest

from conftest import PNG_240, console_errors, open_page, read_meta, wait_until, write_meta

NAME = "Uncompressed/Remembered"
IMAGE = '//*[@id="comic"]//img'
NEXT = '//a[@rel="next"]'


@pytest.fixture
def comic(library):
    folder = library / "Uncompressed" / "Remembered"
    folder.mkdir(parents=True)
    (folder / "0001.png").write_bytes(PNG_240)
    write_meta(folder, {
        "schema": 2, "generator": "mirror_base.py", "generator_version": "3.5",
        "created": "2026-10-01T00:00:00Z", "updated": "2026-10-01T00:00:00Z",
        "settings": {"url": "https://example.com/p/1", "output": NAME, "increment": 1, "prefix": True,
                     "javascript": False, "firefox": False, "waittime": 0, "cbz": False,
                     "direction_check": True, "multi_page": True, "ended": False,
                     "cookies": {"AGE_OK": "yes"}},
        "state": {"page_count": 1, "image_xpath": '//*[@class="avatar"]/img', "next_xpath": IMAGE},
        "history": {"runs": []},
    })
    return folder


def saved(page, **settings):
    _, detail = page.call("/api/comic?name=" + NAME)
    return page.call("/api/settings", {"name": NAME, "updated": detail.get("updated"), "settings": settings})


def test_the_paths_are_put_right_in_the_state(web, comic):
    code, answer = saved(web(), image_xpath="  " + IMAGE + " ", next_xpath=NEXT)
    assert code == 200 and answer.get("saved"), answer
    meta = read_meta(comic)
    assert meta["state"]["image_xpath"] == IMAGE and meta["state"]["next_xpath"] == NEXT
    #nothing of the state crosses into the settings, which are what a scrape's command is built from
    assert "image_xpath" not in meta["settings"] and "next_xpath" not in meta["settings"]
    assert meta["state"]["page_count"] == 1, "the rest of the state is left as it was"
    #recorded like any other edit, with what it was before
    edit = meta["history"]["edits"][-1]["changed"]
    assert edit["image_xpath"] == ['//*[@class="avatar"]/img', IMAGE], edit


def test_an_emptied_box_forgets_the_path(web, comic):
    code, answer = saved(web(), image_xpath="")
    assert code == 200 and answer.get("saved"), answer
    meta = read_meta(comic)
    assert meta["state"]["image_xpath"] is None
    assert meta["state"]["next_xpath"] == IMAGE, "a path not sent is left alone"


def test_the_same_paths_again_change_nothing(web, comic):
    code, answer = saved(web(), image_xpath='//*[@class="avatar"]/img', next_xpath=IMAGE)
    assert code == 200 and not answer.get("saved"), answer


@pytest.mark.parametrize("typed", ["#comic img", "img.comic", '//img\n//a[@rel="next"]'])
def test_what_is_not_an_xpath_is_refused(web, comic, typed):
    #a css selector pasted in would match nothing, and the scrape would fall back to searching the lists
    #without a word about the box
    code, answer = saved(web(), image_xpath=typed)
    assert code == 400 and "XPath" in answer["error"], answer
    assert read_meta(comic)["state"]["image_xpath"] == '//*[@class="avatar"]/img'


@pytest.mark.browser
def test_the_editor_shows_and_saves_them(web, comic, browser):
    page = web()
    open_page(browser, page.base + "/")
    browser.execute_script("openEditor('{0}')".format(NAME))
    value = lambda id: browser.execute_script("return document.getElementById(arguments[0]).value", id)
    wait_until(lambda: value("e-image_xpath"), why="the editor never showed the comic's image path")
    assert value("e-image_xpath") == '//*[@class="avatar"]/img' and value("e-next_xpath") == IMAGE
    #the library's paths offered under each box, the shipped ones among them
    offered = wait_until(lambda: browser.execute_script(
        "return [...document.querySelectorAll('#e-next-paths option')].map(o => o.value)"),
        why="no next paths were offered")
    assert NEXT in offered, offered
    #cookies now live in the advanced section, which a comic that has some opens on
    assert browser.execute_script("return document.getElementById('e-cookies').closest('details').id") == "edit-advanced"
    assert browser.execute_script("return document.getElementById('edit-advanced').open")

    browser.execute_script("document.getElementById('e-image_xpath').value = arguments[0];", IMAGE)
    browser.execute_script("document.getElementById('edit-save').click()")
    wait_until(lambda: read_meta(comic)["state"].get("image_xpath") == IMAGE, why="the image path was never saved")
    errors = console_errors(browser)
    assert not errors, errors
