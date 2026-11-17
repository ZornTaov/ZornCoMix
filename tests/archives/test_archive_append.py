#an archive built elsewhere, the way `zip -r -0 X.zip ./X` builds it: a directory entry, every path under the
#folder's name, everything stored. new pages have to go in under the same prefix, or a reader shows the comic
#as two separate groups - and appending must leave every byte already there where it is, so a sync carries
#only the new pages.
import argparse
import os
import zipfile

from conftest import write_meta

NAME = "MyComic"


def test_new_pages_are_appended_under_the_prefix_the_archive_already_uses(library, mirror, monkeypatch):
    folder = library / "Uncompressed" / NAME
    folder.mkdir()
    cbz = library / "CBZs" / (NAME + ".cbz")
    for n in range(1, 6):
        (folder / "{0:04d}_page.png".format(n)).write_bytes(b"IMAGE" + bytes([n]) * 900)
    write_meta(folder, {"schema": 2, "settings": {}})

    with zipfile.ZipFile(cbz, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr(NAME + "/", b"")
        for name in sorted(os.listdir(folder)):
            zf.write(folder / name, NAME + "/" + name)
    before_size = os.path.getsize(cbz)
    before_bytes = cbz.read_bytes()

    #a new page arrives, as a real run would leave behind
    (folder / "0006_page.png").write_bytes(b"IMAGE" + b"\x06" * 900)

    args = argparse.Namespace(output=os.path.join("Uncompressed", NAME),
                              cbz_path=os.path.join("CBZs", NAME + ".cbz"))
    monkeypatch.chdir(library)
    built, added = mirror.cbz_update(args)

    with zipfile.ZipFile(built) as zf:
        names = zf.namelist()
    after_bytes = open(built, "rb").read()
    kept = 0
    for a, b in zip(before_bytes, after_bytes):
        if a != b:
            break
        kept += 1

    assert added == 1, "expected exactly the one new page appended, got {0}".format(added)
    #the ComicInfo sits at the top whatever the pages are under, which is where a reader looks for it
    assert names.count("ComicInfo.xml") == 1, names
    names = [n for n in names if n != "ComicInfo.xml"]
    assert len(names) == 8, "the five it already had were added again: {0}".format(names)
    assert not [n for n in names if not n.startswith(NAME + "/")], names
    assert len([n for n in names if n.endswith("mirror_metadata.json")]) == 1, names
    assert NAME + "/0006_page.png" in names, names
    #only the directory at the end, and the metadata written last, should have moved
    assert kept >= before_size - 2000, "earlier bytes rewritten: {0} of {1} kept".format(kept, before_size)

    #and running again with nothing new must leave the file completely alone
    size_after = os.path.getsize(built)
    again, again_added = mirror.cbz_update(args)
    assert again_added == 0, again_added
    assert os.path.getsize(again) == size_after


def test_stand_ins_drawn_differently_now_are_swapped_in_place(library, capsys):
    #an archive packed when a video's stand-in was a tall page of words: chapters.py standins swaps in the
    #stand-in as drawn now, the video's own shape, and writes nothing else again
    from comiclib import cbz, comicinfo, standin
    from comiclib.chapters.packing import standins
    from test_standin import movie
    folder = library / "Uncompressed" / NAME
    folder.mkdir()
    for n in (1, 3):
        (folder / "{0:04d}.png".format(n)).write_bytes(b"IMAGE" + bytes([n]) * 900)
    (folder / "0002.mp4").write_bytes(movie(1280, 720))
    write_meta(folder, {"schema": 2, "settings": {"cbz_path": "CBZs/" + NAME + ".cbz"}})
    archive = str(library / "CBZs" / (NAME + ".cbz"))
    with zipfile.ZipFile(archive, "w") as zf:
        for name in ("0001.png", "0003.png"):
            zf.write(folder / name, name)
        zf.writestr("0002.png", standin.stand_in(list(standin.held_otherwise(str(folder), "0002.mp4"))))
    pages_before = open(archive, "rb").read()[:2000]
    args = argparse.Namespace(cbz=None, root=str(library), dry_run=True)
    assert standins(str(folder), args) == 0
    assert "1 stand-in(s) drawn differently now: 0002.mp4" in capsys.readouterr().out
    args.dry_run = False
    assert standins(str(folder), args) == 0
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist().count("0002.png") == 1
        assert comicinfo.dimensions(zf.read("0002.png")) == (1400, 788), "the video's 16:9"
    assert open(archive, "rb").read()[:2000] == pages_before, "the pages were not written again"
    standins(str(folder), args)
    assert "every stand-in is as it is drawn now" in capsys.readouterr().out


def test_a_page_saved_again_with_other_bytes_takes_the_old_copys_place(library):
    #the page a run resumes on, come back different: written on the end under its own name, the old entry
    #gone from the directory, and every byte before it where it was
    from comiclib import cbz
    folder = library / "Uncompressed" / NAME
    folder.mkdir()
    for n in range(1, 4):
        (folder / "{0:04d}.png".format(n)).write_bytes(b"IMAGE" + bytes([n]) * 900)
    archive = str(library / "CBZs" / (NAME + ".cbz"))
    cbz.update(str(folder), archive)
    before = open(archive, "rb").read()
    (folder / "0003.png").write_bytes(b"IMAGE" + b"\x09" * 950)
    _, added = cbz.update(str(folder), archive, changed=["0003.png"])
    assert added == 0, "a page changed is not a page added"
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert names.count("0003.png") == 1, names
        assert zf.read("0003.png") == (folder / "0003.png").read_bytes()
    after = open(archive, "rb").read()
    assert after[:len(before) - 2000] == before[:len(before) - 2000], "earlier bytes were rewritten"
