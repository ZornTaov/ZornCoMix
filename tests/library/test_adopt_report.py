#adopting a whole library a row at a time: --scan says what holds pages and has no metadata yet, --report
#writes it as a spreadsheet to fill in, and --read-report adopts every row given an address or marked ended,
#leaving the rest for later. typed answers outlive the report being written again.
import csv
import zipfile

from conftest import read_meta
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
