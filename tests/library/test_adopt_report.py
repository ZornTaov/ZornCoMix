#adopting a whole library a row at a time: --scan says what holds pages and has no metadata yet, --report
#writes it as a spreadsheet to fill in, and --read-report adopts every row given an address or marked ended,
#leaving the rest for later. typed answers outlive the report being written again.
import csv
import zipfile

from conftest import read_meta, run, write_meta
from test_adopt import adopt


def loose(library, name, count):
    folder = library / "Uncompressed" / name
    folder.mkdir(parents=True)
    for n in range(1, count + 1):
        (folder / "{0:04d}_page.jpg".format(n)).write_bytes(b"x")
    return folder


def shelved(library, name, count):
    path = library / "CBZs" / (name + ".cbz")
    with zipfile.ZipFile(str(path), "w") as zf:
        for n in range(1, count + 1):
            zf.writestr("{0:04d}.jpg".format(n), b"x")
    return path


def rows(path):
    with open(str(path), encoding="utf-8-sig", newline="") as f:
        return {row["path"]: row for row in csv.DictReader(f)}


def test_a_scan_lists_what_has_no_metadata_and_leaves_the_adopted_out(library):
    loose(library, "MyComic", 7)
    shelved(library, "OnlyShelved", 3)
    done = loose(library, "Adopted", 2)
    assert adopt(library, "Uncompressed/Adopted", "--root", ".", "--ended").returncode == 0
    assert (done / "mirror_metadata.json").exists()

    said = adopt(library, "--scan", "--root", ".").stdout
    assert "Uncompressed/MyComic" in said and "7 pages" in said, said
    assert "CBZs/OnlyShelved.cbz" in said, said
    assert "Uncompressed/Adopted" not in said, "an adopted comic is not a candidate: " + said
    assert "Uncompressed/Adopted" in adopt(library, "--scan", "--all", "--root", ".").stdout


def chaptered(library, name):
    #a comic packed a chapter at a time into a shelf folder of its own, as a plugin's comic is: no cbz_path
    #said, so filed where packing files one, and nothing in that folder saying whose it is
    folder = library / "Uncompressed" / name
    for n in range(1, 5):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "{0:04d}_page.jpg".format(n)).write_bytes(bytes([n]) * (40 + n))
    write_meta(folder, {"schema": 2, "settings": {"url": "https://example.com/", "output": "Uncompressed/" + name,
                                                  "cbz_path": None},
                        "chapters": {"source": "plugin", "list": [
                            {"number": 1, "label": "#1 Arrival", "start_page": 1, "end_page": 2},
                            {"number": 2, "label": "#2 Departure", "start_page": 3, "end_page": 4}]}})
    done = run("chapters.py", "pack", folder, "--root", library)
    assert done.returncode == 0, done.stdout + done.stderr
    shelf = library / "CBZs" / name
    assert len(list(shelf.glob("*.cbz"))) == 2, sorted(p.name for p in shelf.iterdir())
    return shelf


def test_a_scan_leaves_out_the_archives_an_adopted_comic_keeps(library):
    #a comic's chapter archives, and an archive its settings name under another name in a folder it shares,
    #are that comic's - but an archive beside them that neither names is still someone's to adopt
    shelf = chaptered(library, "Chaptered")
    shelved(library, "Chaptered/001", 3)
    (library / "CBZs" / "SomeAuthor").mkdir()
    loose(library, "Mine", 3)
    assert adopt(library, "Uncompressed/Mine", "--root", ".", "--ended",
                 "--cbz-path", "CBZs/SomeAuthor/Collected.cbz").returncode == 0
    assert (library / "CBZs" / "SomeAuthor" / "Collected.cbz").exists()
    shelved(library, "SomeAuthor/Theirs", 2)
    report = library / "adopt.csv"

    assert adopt(library, "--scan", "--report", str(report), "--root", ".").returncode == 0
    assert sorted(rows(report)) == ["CBZs/Chaptered/001.cbz", "CBZs/SomeAuthor/Theirs.cbz"], sorted(rows(report))
    assert not any(name.startswith("Chaptered - c") for name in rows(report)), shelf


def test_a_scan_passes_over_the_covers_on_the_shelf(library):
    #a reader's cover.jpg in a folder of the shelf, and a picture beside an archive under its name, are covers
    #- a folder of nothing else is no comic. a comic's own folder of pages counts every picture in it
    (library / "CBZs" / "Covered").mkdir()
    (library / "CBZs" / "Covered" / "cover.jpg").write_bytes(b"c")
    (library / "CBZs" / "Covered" / "Poster.PNG").write_bytes(b"c")
    shelved(library, "OnlyShelved", 3)
    (library / "CBZs" / "OnlyShelved.jpg").write_bytes(b"c")
    pages = loose(library, "Starts", 3)
    (pages / "cover.jpg").write_bytes(b"page one")
    report = library / "adopt.csv"

    assert adopt(library, "--scan", "--report", str(report), "--root", ".").returncode == 0
    written = rows(report)
    assert sorted(written) == ["CBZs/OnlyShelved.cbz", "Uncompressed/Starts"], sorted(written)
    assert written["Uncompressed/Starts"]["pages"] == "4", "a cover.jpg among pages is a page"


def test_a_library_with_nothing_to_adopt_says_so(library):
    said = adopt(library, "--scan", "--root", ".").stdout
    assert "Nothing under" in said and "needs adopting" in said, said


def test_a_report_is_filled_in_and_read_back_a_row_at_a_time(library):
    loose(library, "MyComic", 7)
    shelved(library, "MyComic", 7)
    loose(library, "Later", 4)
    report = library / "adopt.csv"

    done = adopt(library, "--scan", "--report", str(report), "--root", ".")
    assert done.returncode == 0 and "--read-report" in done.stdout, done.stdout
    written = rows(report)
    #the folder is paired with the archive of its own name on the shelf, which is then no row of its own
    assert written["Uncompressed/MyComic"]["cbz_path"] == "CBZs/MyComic.cbz", written
    assert sorted(written) == ["Uncompressed/Later", "Uncompressed/MyComic"], sorted(written)
    assert written["Uncompressed/MyComic"]["pages"] == "7"

    #filled in for one comic only, the way a spreadsheet saves it
    written["Uncompressed/MyComic"].update(last_url="https://example.com/comic/7", increment="7", prefix="yes")
    with open(str(report), "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(next(iter(written.values())).keys()))
        writer.writeheader()
        writer.writerows(written.values())

    #written again, as a library being worked through is: what was typed stays
    adopt(library, "--scan", "--report", str(report), "--root", ".")
    assert rows(report)["Uncompressed/MyComic"]["last_url"] == "https://example.com/comic/7"

    done = adopt(library, "--read-report", str(report), "--root", ".")
    assert done.returncode == 0, done.stdout
    assert "1 adopted, 1 left alone, 0 with problems" in done.stdout, done.stdout
    meta = read_meta(library / "Uncompressed" / "MyComic")
    assert meta["settings"]["url"] == "https://example.com/comic/7"
    assert meta["settings"]["increment"] == 7 and meta["settings"]["prefix"] is True, meta["settings"]
    assert meta["settings"]["cbz_path"] == "CBZs/MyComic.cbz"
    assert not (library / "Uncompressed" / "Later" / "mirror_metadata.json").exists(), "a row left blank waits"


def test_a_report_that_is_not_there_is_said_so(library):
    done = adopt(library, "--read-report", "nowhere.csv", "--root", ".")
    assert done.returncode == 2 and "does not exist" in done.stdout, done.stdout
