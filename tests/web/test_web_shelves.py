#the shelves as the page sets and uses them: named in the Settings, refused where they would file a comic's
#next archive somewhere other than the one it has, and picked in Add comics, which puts the rows inside that
#shelf's folders instead of the default's
import json
from types import SimpleNamespace

import pytest

from comiclib import plugins, pluginsetup
from comiclib.web.adding import parse_entries
from comiclib.web.edits import save_config
from conftest import console_errors, open_page, read_meta, wait_until, write_meta
from test_plugins import URL, install
from test_web_plugins import visible


def setup(library, **settings):
    return SimpleNamespace(root=str(library), max_depth=5, pages_folder="Uncompressed", cbz_folder="CBZs",
                           **settings)


def saved(config):
    with open(str(config / "ComicScraper.json"), encoding="utf-8") as f:
        return json.load(f)


def test_shelves_are_saved_with_the_settings(library, config):
    status, answer = save_config(setup(library), {"shelves": {"Manga": "Manga", "Comic": "Shelves/Comic"}})
    assert status == 200, answer
    assert saved(config)["shelves"] == {"Manga": "Manga", "Comic": "Shelves/Comic"}
    assert answer["settings"]["shelves"] == {"Manga": "Manga", "Comic": "Shelves/Comic"}


def test_a_blank_archive_folder_is_the_one_the_library_has(library, config):
    (library / "CBZs").rename(library / "Webcomics")
    status, answer = save_config(setup(library), {"cbz_folder": "", "shelves": {"Manga": "Manga"}})
    assert status == 200, answer
    assert saved(config)["cbz_folder"] is None
    #and a shelf may not be the folder that is the default without being named
    status, answer = save_config(setup(library), {"cbz_folder": "", "shelves": {"Webcomics": "Webcomics"}})
    assert status == 400 and "the default shelf" in answer["error"], answer


def test_a_shelf_that_could_not_be_one_is_refused(library, config):
    status, answer = save_config(setup(library), {"shelves": {
        "A/B": "Nested", "Out": "../Elsewhere", "Same": "CBZs", "Inside": "Uncompressed/Inside",
        "One": "Twice", "Two": "Twice"}})
    assert status == 400
    for said in ("one folder's name", "Out's shelf", "the default shelf", "inside the pages folder",
                 "Two's shelf Twice is One's shelf already"):
        assert said in answer["error"], answer["error"]


def test_a_folder_holding_comics_filed_elsewhere_cannot_become_a_shelf(library, config):
    #a comic already in Uncompressed/Manga with its archive on CBZs: the rule would file its next one on the
    #new shelf, a second copy beside the first
    folder = library / "Uncompressed" / "Manga" / "SomeSeries"
    folder.mkdir(parents=True)
    write_meta(folder, {"schema": 2, "settings": {"cbz_path": "CBZs/Manga/SomeSeries.cbz"}})
    (library / "CBZs" / "Manga").mkdir()
    (library / "CBZs" / "Manga" / "SomeSeries.cbz").write_bytes(b"zip")
    status, answer = save_config(setup(library), {"shelves": {"Manga": "Manga"}})
    assert status == 400 and "Uncompressed/Manga/SomeSeries" in answer["error"], answer
    #one whose archive is on the shelf already is no trouble
    (library / "Manga").mkdir()
    (library / "CBZs" / "Manga" / "SomeSeries.cbz").rename(library / "Manga" / "SomeSeries.cbz")
    write_meta(folder, {"schema": 2, "settings": {"cbz_path": "Manga/SomeSeries.cbz"}})
    assert save_config(setup(library), {"shelves": {"Manga": "Manga"}})[0] == 200


def test_rows_added_to_a_shelf_go_inside_its_folders(library, config):
    save_config(setup(library), {"shelves": {"Manga": "Manga"}})
    rows = [{"folder": "SomeSeries", "url": "https://example.com/1"},
            {"folder": "SomeAuthor/Theirs", "url": "https://example.com/2", "cbz": "SomeAuthor/Collected.cbz"}]
    entries, problems = parse_entries(rows, setup(library), shelf="manga")
    assert not problems, problems
    assert [(pages, archive) for pages, archive, _, _ in entries] == [
        ("Uncompressed/Manga/SomeSeries", "Manga/SomeSeries/SomeSeries.cbz"),
        ("Uncompressed/Manga/SomeAuthor/Theirs", "Manga/SomeAuthor/Collected.cbz")]
    #and with none picked, the default as ever
    entries, _ = parse_entries(rows[:1], setup(library))
    assert entries[0][:2] == ("Uncompressed/SomeSeries", "CBZs/SomeSeries/SomeSeries.cbz")


@pytest.mark.browser
@pytest.mark.slow
def test_a_plugins_comics_start_on_its_shelf(library, config, web, browser):
    install(config)
    save_config(setup(library), {"shelves": {"Manga": "Manga"}})
    pluginsetup.save_shelf(plugins.load("example", with_hooks=False), "Manga")
    page = web()
    open_page(browser, page.base + "/")
    wait_until(lambda: visible(browser, "add-shelf-row") and visible(browser, "add-scraper-row"),
               why="the shelf picker never showed")
    text = lambda element: browser.execute_script("return document.getElementById(arguments[0]).textContent", element)
    assert text("add-roots") == "Uncompressed/ and CBZs/"
    browser.execute_script("const p = document.getElementById('add-scraper'); p.value = 'example';"
                           "p.dispatchEvent(new Event('change'))")
    wait_until(lambda: browser.execute_script("return document.getElementById('add-shelf').value") == "Manga",
               why="the plugin's shelf was not picked for it")
    assert text("add-roots") == "Uncompressed/Manga/ and Manga/"
    browser.execute_script("""
      const set = (sel, value) => { const e = document.querySelector(sel); e.value = value;
        e.dispatchEvent(new Event('input', {bubbles: true})); };
      set('[data-add-field="folder"]', 'SomeSeries');
      set('[data-add-field="url"]', arguments[0]);
      document.getElementById('add').click();""", URL)
    wait_until(lambda: "Queued" in text("add-msg"), why=text("add-msg"))
    assert page.wait_idle(120), "the add never finished"
    meta = read_meta(library / "Uncompressed" / "Manga" / "SomeSeries")
    assert meta["settings"]["cbz_path"] == "Manga/SomeSeries/SomeSeries.cbz", meta["settings"]
    assert (library / "Manga" / "SomeSeries").is_dir() and not (library / "CBZs" / "SomeSeries").exists()
    #the Plugins dialog has the shelf among its settings, picked
    browser.execute_script("document.getElementById('open-plugins').click()")
    wait_until(lambda: browser.execute_script("return document.querySelector('[data-plugin-settings=\"example\"]')"))
    browser.execute_script("document.querySelector('[data-plugin-settings=\"example\"]').click()")
    assert wait_until(lambda: browser.execute_script(
        "const s = document.querySelector('[data-plugin-shelf]'); return s && s.value")) == "Manga"
    assert not console_errors(browser)


@pytest.mark.browser
@pytest.mark.slow
def test_shelves_are_typed_a_line_each_in_the_settings(library, config, web, browser):
    page = web()
    open_page(browser, page.base + "/")
    browser.execute_script("document.getElementById('open-config').click()")
    wait_until(lambda: browser.execute_script("return document.getElementById('config').open"))
    browser.execute_script("document.getElementById('c-shelves').value = '  Manga \\n\\nComic = Shelves/Comic\\n';"
                           "document.getElementById('cfg-save').click()")
    wait_until(lambda: "Saved" in browser.execute_script("return document.getElementById('cfg-msg').textContent"))
    assert saved(config)["shelves"] == {"Manga": "Manga", "Comic": "Shelves/Comic"}
    #shown back as typed, and the add form now offers them
    assert browser.execute_script("return document.getElementById('c-shelves').value") == \
        "Manga\nComic = Shelves/Comic"
    assert browser.execute_script("return [...document.getElementById('add-shelf').options].map(o => o.value)") == \
        ["", "Manga", "Comic"]


def test_a_shelf_not_named_in_the_settings_is_refused(library, config):
    entries, problems = parse_entries([{"folder": "X", "url": "https://example.com/1"}], setup(library),
                                      shelf="Nowhere")
    assert not entries and "no shelf called Nowhere" in problems[0], problems
