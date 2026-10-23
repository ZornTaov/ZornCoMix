#a page whose navigation is drawn twice, above the comic and below it, with one copy written wrong on one page:
#its next button points back at the page it is on, or at the page before, while the other copy goes on. both
#match the comic's next path. pressing the wrong one stayed on the page, which is how the newest page looks, or
#reached a page already saved, which is how a comic that wraps round looks - so every run called the comic
#caught up there and nothing after it was ever fetched.
import json

import pytest

from conftest import PNG, Site, pages_in, read_meta, run, write_index, write_meta

PAGES = 5
#the page whose navigation is wrong
WRONG = 3
NEXT = '//a[img[@alt="NEXT"]]'
pytestmark = pytest.mark.browser


class DoubledNav(Site):
    #the copy that is wrong on page WRONG: "top", "bottom", or "both" for a newest page drawn the same way; and
    #where it leads, "here" or "back" to the page before
    wrong = "top"
    to = "here"

    def nav(self, n, where):
        onward = n + 1 if n < PAGES else None
        if n == WRONG and self.wrong in (where, "both"):
            onward = n if self.to == "here" else n - 1
        if onward is None:
            return ""
        return '<a href="/m/{0}.html"><img src="/nav/fore.gif" alt="NEXT" width="40" height="20"></a>'.format(onward)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/img/") or path.startswith("/nav/"):
            self.send(PNG + path.encode(), "image/png")
            return
        number = path.rsplit("/", 1)[-1][:-len(".html")] if path.endswith(".html") else ""
        if not (path.startswith("/m/") and number.isdigit() and 1 <= int(number) <= PAGES):
            self.send_error(404)
            return
        n = int(number)
        self.send('<html><head><title>Month {0}</title></head><body><div>{1}</div><div id="wrap">'
                  '<img id="cc-comic" width="240" height="240" src="/img/{0:04d}.png"></div><div>{2}</div>'
                  '</body></html>'.format(n, self.nav(n, "top"), self.nav(n, "bottom")))


def every(first=1, last=PAGES):
    return ["{0:04d}_{0:04d}.png".format(n) for n in range(first, last + 1)]


def site_of(serve, config, wrong, to):
    (config / "element_paths.json").write_text(json.dumps({"next": [{"xpath": NEXT, "note": "this site"}]}),
                                               encoding="utf-8")
    return serve(type("Doubled", (DoubledNav,), {"wrong": wrong, "to": to}))


def scrape(serve, config, tmp_path, wrong, to="here"):
    site = site_of(serve, config, wrong, to)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", site + "/m/1.html", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    return pages_in(out)


@pytest.mark.parametrize("to", ["here", "back"])
@pytest.mark.parametrize("wrong", ["top", "bottom"])
def test_the_copy_of_next_that_leads_on_is_pressed(serve, config, tmp_path, wrong, to):
    assert scrape(serve, config, tmp_path, wrong, to) == every()


def test_a_page_whose_every_next_leads_back_to_it_is_still_where_the_comic_stops(serve, config, tmp_path):
    #the way a newest page often looks: nothing leads on, so nothing is passed over
    assert scrape(serve, config, tmp_path, "both") == every(1, WRONG)


def test_a_run_resuming_on_the_page_knows_the_way_back_by_the_comics_index(serve, config, library, chapters):
    #the next day's run starts on the page itself, so the page before was never saved by this run: only the
    #comic's record of which page is which says that the wrong copy leads backwards
    site = site_of(serve, config, "top", "back")
    out = library / "Uncompressed" / "Doubled"
    out.mkdir(parents=True)
    for n in range(1, WRONG + 1):
        (out / "{0:04d}_{0:04d}.png".format(n)).write_bytes(PNG + "/img/{0:04d}.png".format(n).encode())
    write_meta(out, {"schema": 2, "settings": {"url": "{0}/m/{1}.html".format(site, WRONG),
                                               "output": "Uncompressed/Doubled", "increment": WRONG,
                                               "prefix": True, "cbz": False},
                     "state": {"next_xpath": NEXT},
                     "history": {"first_page_url": site + "/m/1.html", "first_page_number": 1, "runs": []}})
    cache = chapters.index_path(str(out))
    meta = read_meta(out)
    meta["history"]["index_cache"] = cache.replace("\\", "/").rsplit("/", 1)[-1]
    write_meta(out, meta)
    write_index(cache, [
        {"n": n, "url": "{0}/m/{1}.html".format(site, n), "src": "{0}/img/{1:04d}.png".format(site, n),
         "file": "{0:04d}_{0:04d}.png".format(n), "title": "Month {0}".format(n), "bytes": None}
        for n in range(1, WRONG + 1)])
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", "--increment", str(WRONG),
               "{0}/m/{1}.html".format(site, WRONG), cwd=library)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == every(), done.stdout[-800:]
