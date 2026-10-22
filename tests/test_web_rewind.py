#going back from the web page: what it would do shown first, from chapters.py's own dry run, then queued like a
#move so no scrape adds pages while they are taken off; and a run undone from the editor's list of runs.
import time

import pytest

from conftest import console_errors, open_page, read_meta, wait_until
from test_rewind import BAD, GOOD, NAME, page_file, stuck  # noqa: F401 - stuck is the fixture


def finished(page, queued, limit=120):
    end = time.time() + limit
    while time.time() < end:
        _, state = page.call("/api/state")
        for job in state.get("history") or []:
            if job.get("id") == queued:
                return job
        time.sleep(0.2)
    raise AssertionError("going back never finished")


def test_a_look_first_changes_nothing(web, stuck):
    page = web()
    code, answer = page.call("/api/rewind", {"name": NAME, "from": GOOD + 1, "dry_run": True})
    assert code == 200, answer
    assert any("4 page(s) set aside" in line for line in answer["lines"]), answer["lines"]
    assert "queued" not in answer
    assert len(stuck.pages()) == GOOD + BAD


def test_going_back_is_queued_and_says_where_the_next_update_starts(web, stuck):
    page = web()
    code, answer = page.call("/api/rewind", {"name": NAME, "run": "stuck"})
    assert code == 200 and answer.get("queued"), answer
    job = finished(page, answer["queued"])
    assert not job.get("error"), job
    assert job["outcome"] == "the next update starts at https://x.test/p10, as page {0}".format(GOOD), job
    assert stuck.pages() == [page_file(n) for n in range(1, GOOD)]
    #and the editor is shown it: no longer waiting, and the run list gives each run's id to undo it by
    _, detail = page.call("/api/comic?name=" + NAME)
    assert detail["rewinding"] is False and detail["runs"][0]["run_id"] == "stuck", detail["runs"][0]


@pytest.mark.parametrize("asked, why", [
    ({}, "as a number"),
    ({"from": "eleven"}, "as a number"),
    ({"from": 0}, "as a number"),
    ({"from": GOOD + BAD + 1}, "nothing is held from page 15 on"),
    ({"from": 2, "url": "not an address"}, "full http(s) address"),
    ({"run": "nothing-like-it"}, "has no run nothing-like-it"),
])
def test_going_back_that_cannot_be_done_is_refused_at_once(web, stuck, asked, why):
    code, answer = web().call("/api/rewind", dict(asked, name=NAME))
    assert code == 400 and why in answer["error"], answer
    assert len(stuck.pages()) == GOOD + BAD


def test_a_comic_that_is_not_there_is_said_so(web, stuck):
    code, answer = web().call("/api/rewind", {"name": "Uncompressed/Elsewhere", "from": 2})
    assert code == 404, answer


@pytest.mark.browser
def test_a_run_is_undone_from_the_editor(web, stuck, browser):
    page = web()
    open_page(browser, page.base + "/")
    browser.execute_script("openEditor(arguments[0])", NAME)
    script = lambda js, *args: browser.execute_script(js, *args)
    wait_until(lambda: script("return document.querySelector('[data-undo=\"stuck\"]')"),
               why="the run that saved the user icons had no Undo")
    script("document.getElementById('edit-runs-box').open = true;"
           "document.querySelector('[data-undo=\"stuck\"]').click()")
    #what would go, shown before anything can be pressed
    plan = wait_until(lambda: (lambda shown: shown if "set aside" in shown else None)(
        script("return document.getElementById('e-rewind-plan').innerText")), why="no plan was shown")
    assert "to before the run of" in plan and "as page {0}".format(GOOD) in plan, plan
    assert script("return document.getElementById('e-rewind-from').value") == str(GOOD)
    assert script("return document.getElementById('edit-rewind-box').open")
    script("document.getElementById('e-rewind-go').click()")
    #the pages go first and the metadata after them, so it is the metadata that says going back is done
    wait_until(lambda: read_meta(stuck.comic)["settings"]["increment"] == GOOD, why="the comic never went back")
    assert stuck.pages() == [page_file(n) for n in range(1, GOOD)]
    #nothing more can be saved from what the dialog was opened with
    assert script("return document.getElementById('edit-save').disabled")
    errors = console_errors(browser)
    assert not errors, errors
