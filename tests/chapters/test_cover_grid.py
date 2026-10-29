#an archive laid out as a grid of chapters: a box for each, its cover drawn as the box's background and its
#number written under it, and a script on the box that goes to the chapter's first page when it is clicked -
#no <a>, and no heading anywhere. no browser and no network: the archives are made up here.
from comiclib.chapters.archive_page import ArchiveReader, chapters_from_events
from comiclib.chapters.links import same_page
BASE = "https://comic.example.com/archive"


def read(html, last):
    #a walk of pages /read/1 .. /read/<last>, which is what turns a link into a page number
    where = {same_page("https://comic.example.com/read/{0}".format(n)): n for n in range(1, last + 1)}
    reader = ArchiveReader()
    reader.feed(html)
    found, listed = chapters_from_events(reader.events, where, BASE)
    return found, listed, reader.events


def grid(starts, covers=None, script="location.href='{0}'", said=None):
    #a box per chapter starting at each of `starts`; covers[i] its picture, the shared stand-in when not given
    out = ['<html><body><h1>Archive</h1><div id="archive">']
    for at, start in enumerate(starts):
        cover = (covers or {}).get(at, "/uploads/Default.jpg")
        out.append('<div class="thumb-wrap" onClick="{0}">'.format(
            script.format("https://comic.example.com/read/{0}".format(start))))
        out.append('<div class="thumb" style="background-image: url({0})"></div>'.format(cover))
        out.append('<div class="spacer"></div><div class="thumb-title"><span>{0}</span></div></div>'.format(
            (said or {}).get(at, at + 1)))
    out.append('</div></body></html>')
    return "".join(out)


def test_each_box_is_a_chapter_named_by_its_number():
    html = grid([1, 33, 61, 89], covers={0: "/uploads/1.jpg", 1: "/uploads/2.jpg", 2: "/uploads/3.jpg",
                                         3: "/uploads/4.jpg"})
    found, listed, events = read(html, 120)
    assert [c["start_page"] for c in found] == [1, 33, 61, 89], found
    assert [c["label"] for c in found] == ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 4"]
    #the cover drawn in the box is the chapter's banner
    assert [c["image"] for c in found] == ["https://comic.example.com/uploads/{0}.jpg".format(n)
                                           for n in (1, 2, 3, 4)]


def test_a_cover_every_box_shares_is_no_chapter_cover():
    #the site's stand-in for a chapter whose cover is not drawn yet
    html = grid([1, 33, 61, 89], covers={0: "/uploads/1.jpg", 1: "/uploads/2.jpg"})
    found, listed, events = read(html, 120)
    assert len(found) == 4, found
    assert [c["image"] for c in found] == ["https://comic.example.com/uploads/1.jpg",
                                           "https://comic.example.com/uploads/2.jpg", None, None]


def test_a_box_with_a_name_keeps_its_name():
    html = grid([1, 20, 40], covers={0: "/a.jpg", 1: "/b.jpg", 2: "/c.jpg"},
                said={0: "The Start", 1: "Book 2", 2: "Into the Dark"})
    found, listed, events = read(html, 60)
    assert [c["label"] for c in found] == ["The Start", "Book 2", "Into the Dark"]


def test_other_ways_of_going_somewhere_are_links_too():
    #double quotes inside the attribute are written as a page has to write them
    for script in ("window.location='{0}'", "location.assign('{0}')", "window.location.href = &quot;{0}&quot;",
                   "location.replace('{0}')"):
        html = grid([1, 33, 61], covers={0: "/a.jpg", 1: "/b.jpg", 2: "/c.jpg"}, script=script)
        found, listed, events = read(html, 90)
        assert [c["start_page"] for c in found] == [1, 33, 61], (script, found)


def test_a_gallery_of_every_page_is_not_one_chapter_a_page():
    #a picture on every link, one page after another: the pages of a comic, not its chapters
    html = grid(list(range(1, 11)), covers={at: "/thumbs/{0}.jpg".format(at) for at in range(10)})
    found, listed, events = read(html, 10)
    assert len(found) == 1, [c["start_page"] for c in found]
    assert listed == 10


def test_without_a_walk_nothing_is_guessed():
    #with no page numbers, a grid of chapters and a gallery of pages cannot be told apart
    html = grid([1, 33, 61, 89], covers={0: "/a.jpg", 1: "/b.jpg", 2: "/c.jpg", 3: "/d.jpg"})
    reader = ArchiveReader()
    reader.feed(html)
    found, listed = chapters_from_events(reader.events, {}, BASE)
    assert found == []


def test_a_box_ends_at_its_own_closing_tag():
    #the box holds divs of its own, and the first of them closing must not end the link before its name
    html = grid([1, 33, 61], covers={0: "/a.jpg", 1: "/b.jpg", 2: "/c.jpg"}, said={0: "One", 1: "Two", 2: "Three"})
    reader = ArchiveReader()
    reader.feed(html)
    links = [event for event in reader.events if event[0] == "link"]
    assert [said for _, _, said in links] == ["One", "Two", "Three"], links


def test_an_option_without_its_closing_tag_still_ends_at_the_next_link():
    #a dropdown whose options leave out </option> read the same as it always has
    html = ('<html><body><select><option value="/read/1">Page 1<option value="/read/2">Page 2</select>'
            '<a href="/read/3">3</a></body></html>')
    reader = ArchiveReader()
    reader.feed(html)
    links = [first for kind, first, _ in reader.events if kind == "link"]
    assert links[-1] == "/read/3", reader.events
