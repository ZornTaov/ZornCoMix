#a comic that puts each episode on an address of its own - a whole scroll of images on one page, the next
#episode at the next address - is chaptered by its addresses: one chapter each, named from the page's title
#with the comic's name every title ends with left off. remembered, so each new episode becomes a chapter of
#its own; a chapter keeps the name it was saved under, and a number in an episode's name never numbers it.
import os
import time

from conftest import read_meta, run, write_index, write_meta

NAME = "Uncompressed/MyComic"


def episodes_index(chapters, library, folder, episodes):
    #episodes is [(slug, title, pages)], in reading order. every file a different size, so each lines up
    #with its own line of the index
    lines, n = [], 0
    for slug, title, count in episodes:
        for _ in range(count):
            n += 1
            name = "{0:04d}.png".format(n)
            path = folder / name
            if not path.exists():
                path.write_bytes(bytes([n % 251]) * (200 + n))
                stamp = time.time() - (1000 - n) * 10
                os.utime(str(path), (stamp, stamp))
            lines.append({"n": n, "url": "https://example.com/comic/{0}/?sid=7".format(slug),
                          "src": "https://example.com/i/" + name, "image": name, "bytes": 200 + n,
                          "title": title})
    write_index(chapters.index_path(str(folder), str(library), None), lines)
    ch(folder, library, "align")


def comic(chapters, library, episodes):
    folder = library / "Uncompressed" / "MyComic"
    folder.mkdir()
    named = os.path.basename(chapters.index_path(str(folder), str(library), None))
    write_meta(folder, {"schema": 2, "settings": {"url": "https://example.com/comic/first/", "output": NAME,
                                     "cbz_path": "CBZs/MyComic.cbz"}, "history": {"index_cache": named}})
    episodes_index(chapters, library, folder, episodes)
    return folder


def ch(folder, library, command, *more):
    done = run("chapters.py", command, folder, "--root", library, *more)
    return done.returncode, done.stdout + done.stderr


def parts(folder):
    return [(c["start_page"], c["end_page"], c["label"]) for c in read_meta(folder)["chapters"]["list"]]


THREE = [("first", "Package delivery – MyComic", 3), ("second", "Delivery status: late – MyComic", 2),
         ("third", "Tea for two – MyComic", 4)]


def test_each_address_is_a_chapter_named_from_its_title(library, chapters):
    folder = comic(chapters, library, THREE)
    code, out = ch(folder, library, "chapters", "--each-address", "--save")
    assert code == 0, out
    #the colon inside an episode's name is part of it; the comic's name after the dash is not
    assert parts(folder) == [(1, 3, "Package delivery"), (4, 5, "Delivery status: late"),
                             (6, 9, "Tea for two")], parts(folder)
    assert read_meta(folder)["chapters"]["source"] == "address"


def test_it_is_remembered_and_a_new_episode_is_a_chapter_of_its_own(library, chapters):
    folder = comic(chapters, library, THREE)
    ch(folder, library, "chapters", "--each-address", "--save")
    code, out = ch(folder, library, "chapters", "--save")
    assert code == 0 and "as it remembers" in out and "the same chapters as before" in out, out
    episodes_index(chapters, library, folder, THREE + [("fourth", "Goodbye (for now) – MyComic", 2)])
    code, out = ch(folder, library, "chapters", "--save")
    assert code == 0 and "more than before" in out and "WARNING" not in out, out
    assert parts(folder)[-1] == (10, 11, "Goodbye (for now)"), parts(folder)


def test_a_first_episode_alone_is_saved_and_keeps_its_name_as_more_arrive(library, chapters):
    #one chapter is not a comic with no headings here, just a comic one episode in; and the name it is saved
    #under is the one it keeps, or every update after the second episode would be a change needing --force
    folder = comic(chapters, library, THREE[:1])
    code, out = ch(folder, library, "chapters", "--each-address", "--save")
    assert code == 0, out
    assert parts(folder) == [(1, 3, "Package delivery")], parts(folder)
    episodes_index(chapters, library, folder, THREE[:2])
    code, out = ch(folder, library, "chapters", "--save")
    assert code == 0 and "WARNING" not in out, out
    assert parts(folder) == [(1, 3, "Package delivery"), (4, 5, "Delivery status: late")], parts(folder)


def test_a_chapter_already_saved_keeps_its_name_when_titles_read_differently(library, chapters):
    folder = comic(chapters, library, THREE)
    ch(folder, library, "chapters", "--each-address", "--save")
    meta = read_meta(folder)
    meta["chapters"]["list"][1]["label"] = "Late delivery"
    write_meta(folder, meta)
    code, out = ch(folder, library, "chapters", "--save")
    assert code == 0 and "the same chapters as before" in out, out
    assert parts(folder)[1] == (4, 5, "Late delivery"), parts(folder)


def test_titles_that_say_only_the_comic_number_the_chapters(library, chapters):
    folder = comic(chapters, library, [("a", "MyComic", 2), ("b", "MyComic", 2), ("c", "MyComic", 1)])
    code, out = ch(folder, library, "chapters", "--each-address", "--save")
    assert code == 0, out
    assert [label for _, _, label in parts(folder)] == ["Chapter 1", "Chapter 2", "Chapter 3"], parts(folder)


def test_a_number_in_an_episodes_name_does_not_number_its_archive(library, chapters):
    #"Walk with me 2" is the episode's name; filed as chapter 2 it would sort before the first
    folder = comic(chapters, library, [("one", "Hello – MyComic", 2), ("two", "Walk with me 2 – MyComic", 2),
                                       ("three", "Walk with me 5 – MyComic", 1)])
    ch(folder, library, "chapters", "--each-address", "--save")
    code, out = ch(folder, library, "pack")
    assert code == 0, out
    made = sorted(os.listdir(str(library / "CBZs" / "MyComic")))
    assert made == ["MyComic - c001 - Hello.cbz", "MyComic - c002 - Walk with me 2.cbz",
                    "MyComic - c003 - Walk with me 5.cbz"], made


def test_it_and_every_cannot_both_be_given(library, chapters):
    folder = comic(chapters, library, THREE)
    code, out = ch(folder, library, "chapters", "--each-address", "--every", "4", "--save")
    assert code == 2 and "give one of them" in out, out
    assert not read_meta(folder).get("chapters")


def test_episode_titles():
    from comiclib.chapters.chapterlist import episode_titles
    #the longest tail every title shares goes, wherever the titles first differ
    assert episode_titles(["Part 1 - Start | MyComic", "Part 2 - Middle | MyComic"]) == \
        ["Part 1 - Start", "Part 2 - Middle"]
    #a title missing is no name, and does not stop the rest being cut
    assert episode_titles(["Hello – MyComic", None, "Bye – MyComic"]) == ["Hello", None, "Bye"]
    #nothing shared: each title is the name as it stands
    assert episode_titles(["Hello", "Bye – Other"]) == ["Hello", "Bye – Other"]
