#a page whose navigation is drawn twice, above the comic and below it, with one copy written wrong on one page:
#its next button points back at the page it is on while the other copy goes on. both match the comic's next
#path. pressing the wrong one stayed on the page, which is how the newest page looks, so every run called the
#comic caught up there and nothing after it was ever fetched.
import json

import pytest

from conftest import PNG, Site, pages_in, run

PAGES = 5
#the page whose navigation is wrong
WRONG = 3
NEXT = '//a[img[@alt="NEXT"]]'
pytestmark = pytest.mark.browser


class DoubledNav(Site):
    #the copy that is wrong on page WRONG: "top", "bottom", or "both" for a newest page drawn the same way
    wrong = "top"

    def nav(self, n, where):
        onward = n + 1 if n < PAGES else None
        if n == WRONG and self.wrong in (where, "both"):
            onward = n
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


def scrape(serve, config, tmp_path, wrong):
    (config / "element_paths.json").write_text(json.dumps({"next": [{"xpath": NEXT, "note": "this site"}]}),
                                               encoding="utf-8")
    site = serve(type("Doubled", (DoubledNav,), {"wrong": wrong}))
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", site + "/m/1.html", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    return pages_in(out)


@pytest.mark.parametrize("wrong", ["top", "bottom"])
def test_the_copy_of_next_that_leads_on_is_pressed(serve, config, tmp_path, wrong):
    assert scrape(serve, config, tmp_path, wrong) == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, PAGES + 1)]


def test_a_page_whose_every_next_leads_back_to_it_is_still_where_the_comic_stops(serve, config, tmp_path):
    #the way a newest page often looks: nothing leads on, so nothing is passed over
    assert scrape(serve, config, tmp_path, "both") == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, WRONG + 1)]
