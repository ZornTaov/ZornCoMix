#ComicScraper.json: settings that describe the setup rather than any one comic, kept beside the scripts so
#a container can edit them without writing into the library. every one of them can still be given on the
#command line, and what is given there wins.
import json
import os

from comiclib.paths import config_folder

config_file = "ComicScraper.json"
config_defaults = {
    #where a library keeps its pages and its archives, as folder names inside the library. no archive folder
    #is the one the library has, CBZs or Webcomics, or Webcomics for a new one (cbz.default_shelf)
    "pages_folder": "Uncompressed",
    "cbz_folder": None,
    #shelves beside that one, by the folder under the pages folder that files a comic on each: a comic in
    #Uncompressed/Manga/<comic> has its archives in the library's Manga shelf rather than in cbz_folder. so a
    #library pointed at by a reader per shelf keeps, say, manga apart from webcomics. {"Manga": "Manga"}
    "shelves": {},
    #after a chaptered comic gains pages, line them up and write the chapter archives again
    "pack_chapters": True,
    #and read its archive page again first, in case those pages started a new chapter
    "refresh_chapters": True,
    #the same things --jobs, --timeout and the rest set, for a setup that would otherwise pass them every time
    "jobs": 1,
    "timeout": 1800,
    "progress": 60,
    "max_depth": 5,
    "schedule": None,
    #the name the pictures and the chapter pages are fetched under; None is useragent's built-in one
    "user_agent": None,
    #what the web page's add form starts with ticked
    "add_defaults": {"prime": False, "prefix": False, "increment": 1, "javascript": False,
                     "waittime": 0, "cbz": True, "direction_check": True, "multi_page": True},
}
#the settings files already complained about, so a broken one is not reported before every run
warned_about = set()


def config_path():
    return os.path.join(config_folder(), config_file)


def load_config(quiet=False):
    #read fresh rather than remembered, so a change through the web page reaches the next run without a restart
    settings = dict(config_defaults)
    settings["add_defaults"] = dict(config_defaults["add_defaults"])
    path = config_path()
    if not os.path.exists(path):
        return settings
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            saved = json.load(f)
        for key, value in (saved or {}).items():
            if key == "add_defaults" and isinstance(value, dict):
                settings["add_defaults"].update(value)
            elif key in config_defaults:
                settings[key] = value
    except (ValueError, OSError, AttributeError) as error:
        #a broken settings file must not stop the library updating, so the built-in values carry on. said
        #once for each state of the file rather than on every read, which happens before every run
        stamp = (path, os.path.getmtime(path) if os.path.exists(path) else None)
        if stamp not in warned_about:
            warned_about.add(stamp)
            print("WARNING: ignoring {0}: {1}".format(path, error), flush=True)
    return settings
