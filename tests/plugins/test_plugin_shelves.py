#a plugin's own shelf, where Add comics starts its comics: kept with its settings but never handed to its
#program, and a plugin comic started on another shelf names its archive, since the reader cannot work it out
import json

import pytest

from comiclib import plugins, pluginsetup
from conftest import read_meta
from test_plugins import install


def shelve(config, table):
    with open(str(config / "ComicScraper.json"), "w", encoding="utf-8") as f:
        json.dump({"shelves": table}, f)


def test_a_plugins_shelf_is_kept_but_never_handed_over(config):
    install(config)
    shelve(config, {"Manga": "Manga"})
    plugin = plugins.load("example", with_hooks=False)
    assert pluginsetup.save_shelf(plugin, "manga") == "Manga"
    assert plugins.load("example", with_hooks=False).view()["shelf"] == "Manga"
    #saving its own settings keeps the shelf, and neither its program nor its plugin.py is told of it
    pluginsetup.save(plugin, {})
    assert pluginsetup.shelf("example") == "Manga"
    assert pluginsetup.SHELF not in pluginsetup.values(plugin)
    assert not any("Manga" in value for value in pluginsetup.environment(plugin).values())
    #and put back to the default
    assert pluginsetup.save_shelf(plugin, "") == ""


def test_a_shelf_the_settings_do_not_name_is_refused(config):
    install(config)
    with pytest.raises(pluginsetup.SetupError, match="no shelf called Manga"):
        pluginsetup.save_shelf(plugins.load("example", with_hooks=False), "Manga")


def test_a_plugin_comic_started_on_a_shelf_names_its_archive(library, config):
    install(config)
    shelve(config, {"Manga": "Manga"})
    plugin = plugins.load("example", with_hooks=False)
    folder = library / "Uncompressed" / "Manga" / "SomeSeries"
    plugins.start_comic(str(folder), plugin, {"url": "https://example.com/series"}, "Uncompressed/Manga/SomeSeries")
    assert read_meta(folder)["settings"]["cbz_path"] == "Manga/SomeSeries.cbz"
    #one on the default shelf is left to the rule, as before
    other = library / "Uncompressed" / "MyComic"
    plugins.start_comic(str(other), plugin, {"url": "https://example.com/other"}, "Uncompressed/MyComic")
    assert read_meta(other)["settings"]["cbz_path"] is None
