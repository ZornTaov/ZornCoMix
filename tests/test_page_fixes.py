#which file is which page, said by hand where the walk and the files cannot settle it between them: a page
#pinned to its file, a line of the index that is no page, a file the walk never saw placed after a page. kept
#in the metadata, so every alignment after - and a fresh one from nothing - keeps them.
import json
import os
import zipfile

import pytest

from conftest import read_meta, run, write_index, write_meta

SITE = "https://example.com/comic/"


def ch(command, folder, *more):
    done = run("chapters.py", command, folder, *more)
    return done.returncode, done.stdout + done.stderr


def build(library, chapters, lines, files):
    #files: name -> size, written in that order; lines: (address, the site's picture, its size)
    folder = library / "Uncompressed" / "Toy"
    folder.mkdir()
    for at, (name, size) in enumerate(files.items()):
        (folder / name).write_bytes(bytes([at % 251]) * size)
    write_meta(folder, {"settings": {"url": lines[-1][0], "cbz_path": "CBZs/Toy/Toy.cbz"}, "history": {}})
    write_index(chapters.index_path(str(folder), str(library), None),
                [{"n": n, "url": url, "src": SITE + "img/" + src, "file": src, "title": "Toy", "bytes": size}
                 for n, (url, src, size) in enumerate(lines, 1)])
    return folder


@pytest.fixture
def repeat(library, chapters):
    #the shape of a site that serves the page before's picture in a page's slot: page 4's line names its own
    #picture, but the size the site gives is page 3's. the folder holds the real page 4, from elsewhere
    sizes = {n: 300 + 37 * n for n in range(1, 7)}
    lines = [(SITE + str(n), "p{0}.png".format(n), sizes[3] if n == 4 else sizes[n]) for n in range(1, 7)]
    return build(library, chapters, lines, {"p{0}.png".format(n): sizes[n] for n in range(1, 7)})


def alignment(chapters, library, folder):
    with open(chapters.alignment_path(chapters.index_path(str(folder), str(library), None)), encoding="utf-8") as f:
        return json.load(f)


def test_a_site_serving_another_pages_picture_keeps_the_comic_from_settling(repeat, library):
    code, out = ch("align", repeat, "--root", library)
    assert code == 1 and "page 4" in out and "its size belongs to" in out, out.strip().splitlines()[-4:]
    #and it says how to put that right
    assert "chapters.py pagefix" in out, out.strip().splitlines()[-1:]


def test_pinning_the_page_to_its_file_settles_it(repeat, library, chapters):
    code, out = ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library,
                   "--note", "the site shows page 3 here")
    assert code == 0 and "noted: page 4 is p4.png" in out, out.strip().splitlines()[:2]
    assert "NOT settled" not in out and "settled" in out, out.strip().splitlines()[-3:]
    fix = read_meta(repeat)["page_fixes"][0]
    assert (fix["what"], fix["url"], fix["file"]) == ("pin", SITE + "4", "p4.png"), fix
    saved = alignment(chapters, library, repeat)
    assert saved["pages"][3]["how"] == "hand" and saved["pages"][3]["file"] == "p4.png", saved["pages"][3]
    assert saved["settled"] and saved["report"]["conflict"] == [], saved["report"]


def test_a_pin_outlives_lining_the_comic_up_again(repeat, library, chapters):
    #what a correction written into the alignment itself never did
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library)
    code, out = ch("align", repeat, "--root", library)
    assert code == 0 and "1 by hand" in out, [line for line in out.splitlines() if "lined up" in line]


def test_a_pinned_page_is_not_fetched_again_for_being_another_size(repeat, library):
    #fetched again it would become the very picture it was pinned against
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library)
    code, out = ch("refetch", repeat, "--root", library, "--dry-run")
    assert "Nothing to fetch again" in out, out.strip().splitlines()[:3]


def test_renumbering_takes_the_pin_along_with_its_file(repeat, library, chapters):
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library)
    code, out = ch("renumber", repeat, "--root", library)
    assert code == 0, out.strip().splitlines()[-3:]
    pinned = read_meta(repeat)["page_fixes"][0]["file"]
    assert pinned != "p4.png" and os.path.exists(str(repeat / pinned)), (pinned, sorted(os.listdir(str(repeat))))
    code, out = ch("align", repeat, "--root", library)
    assert code == 0 and "FIX NOT USED" not in out, out.strip().splitlines()[-3:]


def test_a_pin_to_a_file_that_is_not_there_is_said_and_does_not_settle(repeat, library):
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library)
    os.rename(str(repeat / "p4.png"), str(repeat / "p4-elsewhere.png"))
    code, out = ch("align", repeat, "--root", library)
    assert code == 1 and "FIX NOT USED: page 4 is pinned to p4.png" in out, \
        [line for line in out.splitlines() if "FIX" in line or "settled" in line]


def test_pins_that_read_out_of_order_are_refused(repeat, library):
    #page 2 pinned to page 5's file and page 5 to page 2's: both cannot read in the comic's order
    ch("pagefix", repeat, "--at", "2", "--file", "p5.png", "--root", library)
    code, out = ch("pagefix", repeat, "--at", "5", "--file", "p2.png", "--root", library)
    assert code == 1 and "out of the order the other pins read in" in out, \
        [line for line in out.splitlines() if "FIX" in line]


def test_a_line_that_is_no_page_is_dropped_and_keeps_its_place(library, chapters):
    #the site shows page 3 twice, at two addresses, and the folder holds it once
    sizes = {n: 300 + 37 * n for n in range(1, 6)}
    lines = [(SITE + "1", "p1.png", sizes[1]), (SITE + "2", "p2.png", sizes[2]), (SITE + "3", "p3.png", sizes[3]),
             (SITE + "3b", "p3.png", sizes[3]), (SITE + "4", "p4.png", sizes[4]), (SITE + "5", "p5.png", sizes[5])]
    folder = build(library, chapters, lines, {"p{0}.png".format(n): sizes[n] for n in range(1, 6)})
    code, out = ch("pagefix", folder, "--at", SITE + "3b", "--drop", "--root", library)
    assert code == 0 and "noted: page 4" in out and "is not a page" in out, out.strip().splitlines()[:2]
    assert "1 line(s) of the index are no page" in out and "NOT settled" not in out, out.strip().splitlines()[-4:]
    saved = alignment(chapters, library, folder)
    #position is meaning in the index: the dropped line keeps its number, and the page after it keeps its own
    assert [(page["n"], page["file"], page["how"]) for page in saved["pages"][2:5]] == [
        (3, "p3.png", "size"), (4, None, "dropped"), (5, "p4.png", "size")], saved["pages"][2:5]
    #and it is not a page gone missing, to be fetched
    code, out = ch("refetch", folder, "--root", library, "--missing", "--dry-run")
    assert "Nothing missing" in out, out.strip().splitlines()[:2]
    assert not [gap for gap in read_meta(folder)["history"].get("gaps") or [] if gap["page"] == 4]


def test_a_file_the_walk_never_saw_reads_after_the_page_it_is_placed_after(library, chapters):
    #found elsewhere and named so it sorts last in the folder, but it reads after page 2
    sizes = {n: 300 + 37 * n for n in range(1, 5)}
    lines = [(SITE + str(n), "p{0}.png".format(n), sizes[n]) for n in range(1, 5)]
    files = dict({"p{0}.png".format(n): sizes[n] for n in range(1, 5)}, **{"zz_found.png": 999})
    folder = build(library, chapters, lines, files)
    code, out = ch("align", folder, "--root", library)
    assert "1 file(s) no page claims" in out, [line for line in out.splitlines() if "claims" in line]
    code, out = ch("pagefix", folder, "--file", "zz_found.png", "--after", "2", "--root", library)
    assert code == 0 and "read after page 2" in out and "NOT settled" not in out, out.strip().splitlines()[-3:]
    code, out = ch("chapters", folder, "--root", library, "--every", "10", "--save")
    assert code == 0, out.strip().splitlines()[-3:]
    code, out = ch("pack", folder, "--root", library)
    assert code == 0, out.strip().splitlines()[-3:]
    shelf = library / "CBZs" / "Toy"
    archive = sorted(name for name in os.listdir(str(shelf)) if name.endswith(".cbz"))[0]
    with zipfile.ZipFile(str(shelf / archive)) as z:
        inside = [name for name in z.namelist() if not name.endswith(".xml")]
    assert inside == ["p1.png", "p2.png", "zz_found.png", "p3.png", "p4.png"], inside


def test_fixes_are_listed_forgotten_and_cleared(repeat, library):
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library, "--note", "page 3 shown here")
    code, out = ch("pagefix", repeat, "--root", library)
    assert code == 0 and "page 4" in out and "p4.png" in out and "page 3 shown here" in out, out.strip().splitlines()
    code, out = ch("pagefix", repeat, "--at", SITE + "4/", "--forget", "--root", library)
    assert code == 1 and "forgotten: 1 fix(es) about page 4" in out, out.strip().splitlines()[:2]
    assert "page_fixes" not in read_meta(repeat)
    ch("pagefix", repeat, "--at", "4", "--file", "p4.png", "--root", library)
    code, out = ch("pagefix", repeat, "--clear", "--root", library)
    assert "forgotten: all 1" in out and "page_fixes" not in read_meta(repeat), out.strip().splitlines()[:2]


def test_a_page_or_file_that_is_not_there_is_refused(repeat, library):
    code, out = ch("pagefix", repeat, "--at", "40", "--file", "p4.png", "--root", library)
    assert code == 2 and "has no page 40" in out, out.strip().splitlines()[:1]
    code, out = ch("pagefix", repeat, "--at", "4", "--file", "nothing.png", "--root", library)
    assert code == 2 and "is not in" in out, out.strip().splitlines()[:1]
    assert "page_fixes" not in read_meta(repeat)


def test_a_dry_run_lines_up_and_writes_nothing(repeat, library, chapters):
    code, out = ch("align", repeat, "--root", library, "--dry-run")
    assert "a dry run: nothing was written" in out, out.strip().splitlines()[-2:]
    assert not os.path.exists(chapters.alignment_path(chapters.index_path(str(repeat), str(library), None)))


def test_show_json_says_how_each_page_was_matched_and_what_is_wrong(repeat, library):
    ch("align", repeat, "--root", library)
    code, out = ch("show", repeat, "--root", library, "--json")
    shown = json.loads(out)
    assert shown["settled"] is False and shown["fixes"] == [], shown
    assert shown["report"]["conflict"][0]["n"] == 4, shown["report"]
    page = shown["pages"][3]
    assert page["how"] and page["src"].endswith("p4.png") and page["bytes"] == 300 + 37 * 3, page
