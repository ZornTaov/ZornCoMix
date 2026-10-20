#a comic published a week to an address, filled a day at a time: the slots not out yet all show one picture,
#the same week after week. named in the comic's settings, that picture is never saved - it was saved as a page
#numbered after the last real one, sorted before the first, and sat where the real page would be numbered when
#it came. a scrape stops at it and the next carries on from that address, numbering each page as it comes out.
import argparse

import pytest

from comiclib import placeholders
from comiclib.metadata import argv_to_settings, settings_to_argv
from comiclib.runrecord import settings_from_args
from conftest import PNG_240, Site, pages_in, read_meta, run, write_meta

SLOTS = 3
SOON = "/img/0000.png"


class Weekly(Site):
    #weeks at /w/1, /w/2 ..., each holding SLOTS pages; `out` of them are out, and a week exists once the page
    #before its first is out - the newest week can be all placeholders
    out = 5

    @classmethod
    def weeks(cls):
        return cls.out // SLOTS + 1

    def do_GET(self):
        if self.path.startswith("/img/"):
            number = int(self.path[len("/img/"):-len(".png")])
            #every page its own bytes, so none is taken for another
            self.send(PNG_240 + number.to_bytes(2, "big"), "image/png")
            return
        week = self.path.rsplit("/", 1)[-1]
        if not (self.path.startswith("/w/") and week.isdigit() and 1 <= int(week) <= self.weeks()):
            self.send_error(404)
            return
        week = int(week)
        slots = "".join('<img width="240" height="240" alt="Week {0} Strip #{1}" src="{2}">'.format(
            week, at + 1, "/img/{0:04d}.png".format(n) if n <= self.out else SOON)
            for at, n in enumerate(range((week - 1) * SLOTS + 1, week * SLOTS + 1)))
        onward = '<a rel="next" href="/w/{0}">Next</a>'.format(week + 1) if week < self.weeks() else ""
        self.send('<html><head><title>Week {0}</title></head><body><div id="comic">{1}</div>{2}</body>'
                  '</html>'.format(week, slots, onward))


@pytest.fixture
def weekly(serve):
    Weekly.out = 5
    return serve(Weekly)


def again(tmp_path, out):
    #the next update, from what the comic's settings say, as update_comics builds it
    return run("mirror_base.py", *settings_to_argv(read_meta(out)["settings"]), cwd=tmp_path)


# ---------------- the setting ----------------
def test_a_placeholder_is_given_whole_or_from_its_first_slash():
    assert placeholders.parse("https://example.com/img/soon.png  /img/later.png; /img/later.png") == \
        ["https://example.com/img/soon.png", "/img/later.png"]
    assert placeholders.parse(" ") is None
    with pytest.raises(ValueError, match="Copy image address"):
        placeholders.parse("soon.png")


@pytest.mark.parametrize("src, listed, said", [
    ("https://example.com/img/soon.png", ["https://example.com/img/soon.png"], True),
    #http or https, the host's case, and a query busting a cache are the same picture
    ("http://EXAMPLE.com/img/soon.png?v=3", ["https://example.com/img/soon.png"], True),
    ("https://cdn.example.com/img/soon.png", ["/img/soon.png"], True),
    ("https://example.com/img/soon.png", ["https://example.org/img/soon.png"], False),
    ("https://example.com/img/0001.png", ["/img/soon.png"], False),
    (None, ["/img/soon.png"], False),
])
def test_which_pictures_are_placeholders(src, listed, said):
    assert placeholders.matches(src, listed) is said


def test_the_settings_carry_placeholders_to_the_command_and_back():
    settings = {"url": "https://example.com/w/1", "placeholders": ["/img/soon.png", "/img/later.png"]}
    argv = settings_to_argv(settings)
    assert argv[-5:] == ["--placeholder", "/img/soon.png", "--placeholder", "/img/later.png",
                         "https://example.com/w/1"]
    assert argv_to_settings(argv)["placeholders"] == ["/img/soon.png", "/img/later.png"]
    assert "--placeholder" not in settings_to_argv({"url": "https://example.com/w/1"})
    args = argparse.Namespace(cbz_path=None, prefix=True, enable_javascript=False, firefox=False, waittime=0,
                              cbz=True, direction_check=True, multi_page=True)
    assert "placeholders" not in settings_from_args(args, "Uncompressed/A", "https://example.com/w/1", 1)


def test_a_bad_placeholder_is_a_usage_error(tmp_path, weekly):
    done = run("mirror_base.py", "-o", tmp_path / "comic", "--placeholder", "soon.png", weekly + "/w/1",
               cwd=tmp_path)
    assert done.returncode == 2 and "Copy image address" in done.stdout, done.stdout[-500:]


# ---------------- a scrape ----------------
@pytest.mark.browser
def test_a_placeholder_is_never_saved_and_each_page_is_numbered_as_it_comes_out(tmp_path, weekly):
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", "--placeholder", weekly + SOON,
               weekly + "/w/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert "shows a placeholder where its next page will be" in done.stdout, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, 6)]
    settings = read_meta(out)["settings"]
    assert settings["placeholders"] == [weekly + SOON]
    #the week still filling is where the next run starts, at the number its first page was saved as
    assert settings["url"].endswith("/w/2") and settings["increment"] == 4, settings

    #the week's last page comes out, and with it a week that is nothing but placeholders
    Weekly.out = 6
    done = again(tmp_path, out)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out)[-1] == "0006_0006.png" and len(pages_in(out)) == 6, pages_in(out)
    settings = read_meta(out)["settings"]
    assert settings["url"].endswith("/w/3") and settings["increment"] == 7, settings

    #and its first page, numbered on from the last
    Weekly.out = 7
    done = again(tmp_path, out)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, 8)]
    assert not [name for name in pages_in(out) if "0000" in name.split("_", 1)[1]]


@pytest.mark.browser
def test_without_the_setting_the_placeholder_is_saved_as_a_page(tmp_path, weekly):
    #what happened before there was a setting for it, so the test above is known to be about something
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--no-cbz", weekly + "/w/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert "0000.png" in pages_in(out), pages_in(out)


@pytest.mark.browser
def test_a_walk_stops_at_a_placeholder(library, chapters, weekly):
    comic = library / "Uncompressed" / "Weekly"
    comic.mkdir(parents=True)
    write_meta(comic, {"schema": 2, "settings": {"url": weekly + "/w/1", "output": "Uncompressed/Weekly",
                                                  "increment": 1, "cbz": False, "placeholders": [SOON]},
                       "history": {"runs": []}})
    done = run("chapters.py", "index", comic, "--root", library, "--start", weekly + "/w/1")
    assert done.returncode == 0, done.stdout[-800:]
    lines = chapters.read_index(chapters.index_path(str(comic), str(library), None))
    assert [line["src"].rsplit("/", 1)[-1] for line in lines] == ["{0:04d}.png".format(n) for n in range(1, 6)]


# ---------------- the web page ----------------
NAME = "Uncompressed/Weekly"


@pytest.fixture
def comic(library):
    folder = library / "Uncompressed" / "Weekly"
    folder.mkdir(parents=True)
    (folder / "0001.png").write_bytes(PNG_240)
    write_meta(folder, {
        "schema": 2, "generator": "mirror_base.py", "generator_version": "3.5",
        "created": "2026-10-01T00:00:00Z", "updated": "2026-10-01T00:00:00Z",
        "settings": {"url": "https://example.com/w/1", "output": NAME, "increment": 1, "prefix": False,
                     "javascript": False, "firefox": False, "waittime": 0, "cbz": False,
                     "direction_check": True, "multi_page": True, "ended": False},
        "history": {"runs": []},
    })
    return folder


def saved(page, given):
    _, detail = page.call("/api/comic?name=" + NAME)
    return page.call("/api/settings", {"name": NAME, "updated": detail.get("updated"),
                                       "settings": {"placeholders": given}})


def test_placeholders_are_saved_checked_and_taken_away(web, comic):
    page = web()
    code, answer = saved(page, "https://example.com/img/soon.png /img/later.png")
    assert code == 200, answer
    assert read_meta(comic)["settings"]["placeholders"] == ["https://example.com/img/soon.png", "/img/later.png"]
    code, answer = saved(page, "soon.png")
    assert code == 400 and "Copy image address" in answer["error"], answer
    code, answer = saved(page, "")
    assert code == 200 and answer.get("saved"), answer
    assert "placeholders" not in read_meta(comic)["settings"], "no empty list left behind"
