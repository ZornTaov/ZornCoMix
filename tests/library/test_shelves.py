#shelves beside the CBZs one: a comic whose pages are under Uncompressed/<folder> has its archives on the
#shelf ComicScraper.json names for that folder, so a library can keep manga, say, where another reader is
#pointed at it apart from the webcomics. what the rule finds is named in the comic's settings, since the
#reader has none of the updater's and would look on the default shelf.
import json
import os
import zipfile

from comiclib import cbz, moving
from conftest import read_meta, write_meta


def shelve(config, table, default=None):
    settings = {"shelves": table}
    if default:
        settings["cbz_folder"] = default
    with open(str(config / "ComicScraper.json"), "w", encoding="utf-8") as f:
        json.dump(settings, f)


def comic(library, where, archive=None):
    folder = library / "Uncompressed" / where
    folder.mkdir(parents=True)
    (folder / "0001.png").write_bytes(b"x" * 100)
    write_meta(folder, {"schema": 2, "settings": {"output": "Uncompressed/" + where, "cbz_path": None},
                        "history": {}})
    if archive:
        full = library / archive
        full.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(full), "w") as zf:
            zf.writestr("0001.png", b"x")
    return folder


def test_a_comic_under_a_shelfs_folder_is_filed_on_that_shelf(library, config):
    shelve(config, {"Manga": "Manga"})
    folder = library / "Uncompressed" / "Manga" / "SomeSeries"
    #the shelf's folder need not be there yet: the first archive put on it makes it
    assert cbz.default_path(str(folder)) == str(library / "Manga" / "SomeSeries.cbz")
    assert cbz.on_other_shelf(str(folder))
    #and the library is still the one holding Uncompressed, not Uncompressed itself
    assert cbz.library_root(str(folder)) == str(library)
    assert cbz.resolved("Manga/SomeSeries.cbz", str(folder)) == str(library / "Manga" / "SomeSeries.cbz")
    #every other comic is on the default shelf as before, its folder named by any case
    assert cbz.default_path(str(library / "Uncompressed" / "MyComic")) == str(library / "CBZs" / "MyComic.cbz")
    assert cbz.default_path(str(library / "Uncompressed" / "manga" / "Other")) == str(library / "Manga" / "Other.cbz")


def test_a_comic_named_as_a_shelf_is_not_taken_for_one(library, config):
    #a comic's own folder called Manga, straight under Uncompressed, is a comic on the default shelf
    shelve(config, {"Manga": "Manga"})
    folder = library / "Uncompressed" / "Manga"
    assert cbz.default_path(str(folder)) == str(library / "CBZs" / "Manga.cbz")
    assert not cbz.on_other_shelf(str(folder))


def test_the_library_root_is_right_with_no_settings_at_all(library):
    #the reader has none of the updater's settings, and must still read a shelved comic's paths from the
    #library rather than from Uncompressed
    folder = library / "Uncompressed" / "Manga" / "SomeSeries"
    assert cbz.library_root(str(folder)) == str(library)
    assert cbz.default_path(str(folder)) == str(library / "CBZs" / "Manga" / "SomeSeries.cbz")


def test_the_default_shelf_is_the_one_the_settings_name(library, config):
    (library / "Webcomics").mkdir()
    shelve(config, {}, default="Webcomics")
    assert cbz.default_path(str(library / "Uncompressed" / "MyComic")) == str(library / "Webcomics" / "MyComic.cbz")


def test_with_none_named_the_default_shelf_is_the_one_the_library_has(library, tmp_path):
    #a library from before keeps CBZs, as the reader does with no settings at all
    folder = library / "Uncompressed" / "MyComic"
    assert cbz.default_shelf(str(library)) == "CBZs"
    assert cbz.default_path(str(folder)) == str(library / "CBZs" / "MyComic.cbz")
    #one with Webcomics instead files there
    (library / "CBZs").rename(library / "Webcomics")
    assert cbz.default_shelf(str(library)) == "Webcomics"
    assert cbz.default_path(str(folder)) == str(library / "Webcomics" / "MyComic.cbz")
    #CBZs first when both are there: a library from before may have a shelf called Webcomics beside it
    (library / "CBZs").mkdir()
    assert cbz.default_shelf(str(library)) == "CBZs"
    #and a new library with neither is given Webcomics
    assert cbz.default_shelf(str(tmp_path / "new")) == "Webcomics"


def test_a_shelf_reaching_outside_the_library_is_not_one(library, config):
    shelve(config, {"Out": "../Elsewhere", "A/B": "Nested", "C:": "Drive", "Ok": "Fine"})
    default, extra = cbz.shelves()
    assert default is None and extra == {"ok": ("Ok", "Fine")}, extra


def test_a_comic_moved_onto_a_shelf_names_its_archive_for_the_reader(library, config):
    shelve(config, {"Manga": "Manga"})
    folder = comic(library, "SomeSeries", archive="CBZs/SomeSeries.cbz")
    moving.carry_out(moving.plan(str(folder), str(library), "Uncompressed/Manga"))
    now = library / "Uncompressed" / "Manga" / "SomeSeries"
    assert (library / "Manga" / "SomeSeries.cbz").is_file() and not (library / "CBZs" / "SomeSeries.cbz").exists()
    #the rule found it, but only with the updater's settings: it is named outright
    assert read_meta(now)["settings"]["cbz_path"] == "Manga/SomeSeries.cbz"
    #and moved off again, the shelf and its folder under Uncompressed both stay for the next comic
    moving.carry_out(moving.plan(str(now), str(library), "Uncompressed"))
    assert (library / "CBZs" / "SomeSeries.cbz").is_file()
    assert (library / "Manga").is_dir() and (library / "Uncompressed" / "Manga").is_dir()


def test_a_chaptered_comic_moved_onto_a_shelf_names_its_chapter_folder(library, config):
    shelve(config, {"Manga": "Manga"})
    folder = comic(library, "SomeSeries")
    meta = read_meta(folder)
    meta["chapters"] = {"list": [{"number": 1, "label": "One", "start_page": 1, "end_page": 1}]}
    write_meta(folder, meta)
    held = library / "CBZs" / "SomeSeries"
    held.mkdir()
    (held / "SomeSeries - c001 - One.cbz").write_bytes(b"zip")
    moving.carry_out(moving.plan(str(folder), str(library), "Uncompressed/Manga"))
    assert (library / "Manga" / "SomeSeries" / "SomeSeries - c001 - One.cbz").is_file()
    assert read_meta(library / "Uncompressed" / "Manga" / "SomeSeries")["chapters"]["folder"] == "Manga/SomeSeries"


def test_every_shelf_is_offered_as_a_place_to_move_to(library, config):
    shelve(config, {"Manga": "Manga", "Comic": "Comic"})
    comic(library, "MyComic")
    #a shelf with authors on it already, and one named but never used
    (library / "Manga" / "SomeAuthor").mkdir(parents=True)
    (library / "Manga" / "SomeAuthor" / "Theirs.cbz").write_bytes(b"zip")
    assert moving.places(str(library), "Uncompressed", 5, "CBZs") == [
        "Uncompressed", "Uncompressed/Comic", "Uncompressed/Manga", "Uncompressed/Manga/SomeAuthor"]
    assert os.path.isdir(str(library / "Uncompressed")) and not (library / "Comic").exists()
