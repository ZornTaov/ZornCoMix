#the web page's side of a comic behind an age gate: its cookies edited with its other settings, the gate's
#button among the element paths, and a check that says it met a gate and pressed past it.
import json
import time

import pytest

from conftest import (PNG_240, checked, console_errors, open_page, read_meta, wait_until,
                      write_meta)
from test_age_gate import Gated, OWN_PROFILE

NAME = "Uncompressed/Gated"


@pytest.fixture
def comic(library):
    folder = library / "Uncompressed" / "Gated"
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


def saved(page, cookies):
    _, detail = page.call("/api/comic?name=" + NAME)
    return page.call("/api/settings", {"name": NAME, "updated": detail.get("updated"),
                                       "settings": {"cookies": cookies}})


def test_cookies_are_typed_as_a_browser_writes_them(web, comic):
    page = web()
    code, answer = saved(page, "AGE_OK=yes; theme=dark")
    assert code == 200, answer
    assert read_meta(comic)["settings"]["cookies"] == {"AGE_OK": "yes", "theme": "dark"}
    #recorded like any other edit
    assert any("cookies" in (edit.get("changed") or {}) for edit in read_meta(comic)["history"]["edits"])


def test_a_cookie_without_a_value_is_refused(web, comic):
    code, answer = saved(web(), "AGE_OK")
    assert code == 400
    assert "name=value" in answer["error"]
    assert "cookies" not in read_meta(comic)["settings"]


def test_emptying_the_box_takes_the_cookies_away(web, comic):
    page = web()
    saved(page, "AGE_OK=yes")
    code, answer = saved(page, "")
    assert code == 200 and answer.get("saved"), answer
    assert "cookies" not in read_meta(comic)["settings"], "no empty block left behind"


def run_check(page, body, limit=180):
    code, queued = page.call("/api/check", body)
    assert code == 200, queued
    end = time.time() + limit
    while time.time() < end:
        _, state = page.call("/api/state")
        running = [state["current"]] if state.get("current") else []
        for job in (state.get("history") or []) + running + (state.get("waiting") or []):
            if job.get("id") == queued["queued"] and job.get("check"):
                return job["check"]
        time.sleep(0.5)
    raise AssertionError("the check never finished")


def test_a_check_cookie_must_be_name_equals_value(web):
    code, answer = web().call("/api/check", {"url": "https://example.com/p/1", "cookies": "AGE_OK"})
    assert code == 400 and "name=value" in answer["error"]


@pytest.mark.browser
@pytest.mark.slow
def test_a_check_given_the_cookie_sees_past_the_gate(web, serve):
    #no gate path: without the cookie the check sees only the gate, and with it the comic
    site = serve(Gated)
    page = web(env=OWN_PROFILE)
    blocked = run_check(page, {"url": site + "/p/2"})
    assert not blocked.get("image"), blocked
    passed = run_check(page, {"url": site + "/p/2", "cookies": "AGE_OK=yes"})
    assert passed.get("image") and passed.get("title") == "Comic 2", passed


@pytest.mark.browser
@pytest.mark.slow
def test_what_the_page_shows(web, comic, serve, config, browser):
    site = serve(Gated)
    (config / "element_paths.json").write_text(
        json.dumps({"gate": [{"xpath": '//*[@id="enter"]', "note": "this site"}]}), encoding="utf-8")
    page = web(env=OWN_PROFILE)
    saved(page, "AGE_OK=yes")
    browser.set_window_size(1300, 1050)
    open_page(browser, page.base + "/")

    #the comic's cookies, written back the way they are typed
    browser.execute_script("openEditor('{0}')".format(NAME))
    wait_until(lambda: browser.execute_script("return document.getElementById('e-cookies').value"),
               why="the editor never showed the comic's cookies")
    assert browser.execute_script("return document.getElementById('e-cookies').value") == "AGE_OK=yes"
    browser.execute_script("document.getElementById('editor').close();")

    #the gate's own list among the element paths, and a check that met the gate
    browser.execute_script("document.getElementById('open-elements').click();")
    listed = wait_until(lambda: (lambda said: said if "Age gate paths" in said else None)(
        browser.execute_script("return document.getElementById('ep-lists').innerText")),
        why="the element paths dialog never listed the gate's paths")
    assert "Age gate paths" in listed
    browser.execute_script("document.getElementById('check-url').value = arguments[0];", site + "/p/2")
    browser.execute_script("document.getElementById('check-go').click()")
    result = checked(browser)
    assert "was the site's gate" in result and '//*[@id="enter"]' in result, result[:400]
    #and what was checked is the page past it
    assert "Comic 2" in result, result[:400]
    errors = console_errors(browser)
    assert not errors, errors
