#a site that shows each page small, each wrapped in a link to the same page at full size. an image path that
#picks out the link saves the full-size picture the link goes to; a path that picks out the picture still
#saves the picture; and the link a picture merely sits in - on most comic themes, the way to the next page -
#is never taken for the page.
import pytest

from comiclib import elements
from conftest import PNG_240, Site, pages_in, run

PAGES = 3


class Thumbnails(Site):
    #pages at /p/1 .. /p/N, each a small picture linked to the big one, and a next link of its own
    def do_GET(self):
        path = self.path.split("?")[0]
        for size in ("small", "big"):
            if path.startswith("/{0}/".format(size)):
                #each picture its own bytes, so which one was saved shows
                self.send(PNG_240 + "{0}{1}".format(size, path).encode("ascii"), "image/png")
                return
        number = path.rsplit("/", 1)[-1]
        if not (path.startswith("/p/") and number.isdigit() and 1 <= int(number) <= PAGES):
            self.send_error(404)
            return
        number = int(number)
        onward = '<a rel="next" href="/p/{0}">Next</a>'.format(number + 1) if number < PAGES else ""
        self.send('<html><head><title>Strip {0}</title></head><body><div id="strip">'
                  '<a href="/big/{0:04d}.png"><img width="120" height="120" src="/small/{0:04d}.png"></a>'
                  '</div>{1}</body></html>'.format(number, onward))


class WrappedInNext(Site):
    #the common theme: the comic is wrapped in a link to the next page
    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/img/"):
            self.send(PNG_240 + path.encode("ascii"), "image/png")
            return
        number = path.rsplit("/", 1)[-1]
        if not (path.startswith("/p/") and number.isdigit() and 1 <= int(number) <= PAGES):
            self.send_error(404)
            return
        number = int(number)
        picture = '<img id="cc-comic" width="240" height="240" src="/img/{0:04d}.png">'.format(number)
        if number < PAGES:
            picture = '<a rel="next" href="/p/{0}">{1}</a>'.format(number + 1, picture)
        self.send('<html><head><title>Comic {0}</title></head><body><div id="wrap">{1}</div></body>'
                  '</html>'.format(number, picture))


def saved(out, name):
    with open(out / name, "rb") as f:
        return f.read()[len(PNG_240):].decode("ascii")


@pytest.mark.browser
def test_a_path_that_picks_out_the_link_saves_the_full_size_picture(serve, tmp_path):
    site = serve(Thumbnails)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", "--image-path", '//*[@id="strip"]/a[img]',
               site + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, PAGES + 1)]
    assert [saved(out, name) for name in pages_in(out)] == \
        ["big/big/{0:04d}.png".format(n) for n in range(1, PAGES + 1)], "the picture the link goes to"


@pytest.mark.browser
def test_a_path_that_picks_out_the_picture_still_saves_the_picture(serve, tmp_path):
    site = serve(Thumbnails)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", "--image-path", '//*[@id="strip"]/a/img',
               site + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert saved(out, "0001_0001.png") == "small/small/0001.png"


@pytest.mark.browser
def test_a_picture_inside_a_next_link_is_the_page_not_the_link(serve, tmp_path):
    site = serve(WrappedInNext)
    out = tmp_path / "comic"
    done = run("mirror_base.py", "-o", out, "--prefix", "--no-cbz", site + "/p/1", cwd=tmp_path)
    assert done.returncode == 0, done.stdout[-800:]
    assert pages_in(out) == ["{0:04d}_{0:04d}.png".format(n) for n in range(1, PAGES + 1)]
    assert saved(out, "0001_0001.png") == "/img/0001.png"


class Element(object):
    #what source_of asks of an element, and whether it had to ask the tag
    def __init__(self, tag, **attributes):
        self.tag, self.attributes, self.asked_tag = tag, attributes, False

    @property
    def tag_name(self):
        self.asked_tag = True
        return self.tag

    def get_attribute(self, name):
        return self.attributes.get(name)


def test_what_an_element_stands_for():
    picture = Element("img", src="https://example.com/small/1.png")
    assert elements.source_of(picture) == "https://example.com/small/1.png"
    assert not picture.asked_tag, "a picture costs the browser no second question"
    assert elements.source_of(Element("A", href="https://example.com/big/1.png")) == "https://example.com/big/1.png"
    assert elements.source_of(Element("div", href="https://example.com/big/1.png")) is None, \
        "only a link's href is a picture's address"
    assert elements.source_of(Element("a")) is None
