#a comic that puts each episode on one address as a scroll of images, given a chapter at each address from
#the web page: added that way it is archived an episode a chapter, named from each page's title, with no
#single archive; the editor turns it on and off - never alongside another source of chapters - and the
#chapters job works it out again on its own.
import pytest

from conftest import PNG, Site, read_meta

pytestmark = [pytest.mark.browser, pytest.mark.slow]

EPISODES = [("first", "Package delivery", 3), ("second", "Tea for two", 2), ("third", "Goodbye", 4)]
LABELS = [title for _, title, _ in EPISODES]


class Episodes(Site):
    #every image a different size, numbered on through the comic, so each lines up as its own page
    def do_GET(self):
        if self.path.startswith("/img/"):
            n = int(self.path.rsplit("/", 1)[-1].split(".")[0])
            self.send(PNG + bytes([n]) * n, "image/png")
            return
        slug = self.path.rstrip("/").rsplit("/", 1)[-1]
        first = 1
        for at, (name, title, count) in enumerate(EPISODES):
            if name == slug:
                images = "".join('<img src="/img/{0:04d}.png">'.format(n) for n in range(first, first + count))
                link = ('<a href="/ep/{0}">Next</a>'.format(EPISODES[at + 1][0]) if at + 1 < len(EPISODES)
                        else "")
                self.send('<html><head><meta charset="utf-8"><title>{0} – MyComic</title></head>'
                          '<body><div id="wrap">{1}'
                          '<div id="comic">{2}</div></div></body></html>'.format(title, link, images))
                return
            first += count
        self.send_error(404)


def labels(comic):
    return [c["label"] for c in (read_meta(comic).get("chapters") or {}).get("list", [])]


def shelf(library):
    folder = library / "CBZs" / "Each"
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def test_a_comic_added_with_a_chapter_each_address_is_archived_an_episode_a_chapter(serve, library, web):
    site = serve(Episodes)
    page = web()
    code, answer = page.call("/api/add", {"rows": [{"folder": "Each", "url": site + "/ep/first"}],
                                          "every": "4", "each_address": True})
    assert code == 400 and "not both" in answer.get("error", ""), answer
    code, answer = page.call("/api/add", {"rows": [{"folder": "Each", "url": site + "/ep/first"}],
                                          "each_address": True})
    assert code == 200, answer
    assert page.wait_idle(600), "the add never finished"
    comic = library / "Uncompressed" / "Each"
    block = read_meta(comic).get("chapters") or {}
    assert block.get("source") == "address" and block.get("each_address") is True, block
    assert labels(comic) == LABELS, page.said()[-800:]
    assert shelf(library) == ["Each - c00{0} - {1}.cbz".format(at, label) for at, label in enumerate(LABELS, 1)], \
        "an archive an episode, and no single archive of the lot: {0}".format(shelf(library))

    #the editor: never with another source of chapters, and turned off it keeps what was worked out
    name = "Uncompressed/Each"
    _, detail = page.call("/api/comic?name=" + name)
    assert detail["chapters"]["each_address"] is True, detail["chapters"]
    code, answer = page.call("/api/settings", {"name": name, "settings": {
        "chapters_every": "4", "chapters_each_address": True}})
    assert code == 400 and "one place" in answer.get("error", ""), answer
    code, answer = page.call("/api/settings", {"name": name, "updated": detail["updated"], "settings": {
        "chapters_url": "", "chapters_every": "", "chapters_each_address": False}})
    assert code == 200 and "chapters_each_address" in answer["changed"], answer
    block = read_meta(comic)["chapters"]
    assert "each_address" not in block and labels(comic) == LABELS, block

    #and on again, worked out by the chapters job with nothing to walk
    _, detail = page.call("/api/comic?name=" + name)
    code, answer = page.call("/api/settings", {"name": name, "updated": detail["updated"], "settings": {
        "chapters_url": "", "chapters_every": "", "chapters_each_address": True}})
    assert code == 200 and read_meta(comic)["chapters"].get("each_address") is True, answer
    code, answer = page.call("/api/chapterize", {"name": name, "each_address": True})
    assert code == 200 and answer.get("from") == "each_address" and answer.get("numbers_first") is False, answer
    assert page.wait_idle(300), "the chapters were never worked out"
    assert labels(comic) == LABELS and "the same chapters as before" in page.said(), page.said()[-800:]
