#settings_to_argv is the one place a comic's command is built from its settings, and a run writes its settings
#back from what that command told it. a daily run goes round that loop every time, so nothing may be lost on the way.
import pytest

from comiclib import cookies, placeholders
from comiclib.metadata import settings_to_argv
from comiclib.runrecord import settings_from_args

BASE = {"cbz_path": None, "prefix": False, "javascript": False, "firefox": False, "waittime": 0, "cbz": True,
        "direction_check": True, "multi_page": True, "ended": False}
CASES = [
    #a prefix, an archive path, and an address ending in a slash
    dict(BASE, url="https://example.com/comic/some-page/", output="Uncompressed/My_Comic", increment=734,
         prefix=True, cbz_path="CBZs/My_Comic.cbz"),
    #an address carrying its page in the query string
    dict(BASE, url="https://example.com/view.php?comic=5885", output="Uncompressed/OtherComic", increment=5885,
         cbz_path="CBZs/OtherComic.cbz"),
    #every flag that defaults on turned off, and the machine-ish ones on
    dict(BASE, url="https://x.test/1", output="Weird", increment=1, javascript=True, firefox=True, waittime=3,
         cbz=False, direction_check=False, multi_page=False),
    #what only a site behind a gate, refusing the library's name, or showing pages still to come has
    dict(BASE, url="https://example.com/w/1", output="Uncompressed/Gated", increment=9, cookies={"AGE_OK": "yes"},
         user_agent="SomeBrowser/1.0", placeholders=["/img/soon.png"]),
]


@pytest.mark.parametrize("settings", CASES, ids=["prefixed", "query-string", "all-flags", "gated"])
def test_settings_survive_a_run(mirror, settings):
    args = mirror.make_parser().parse_args(settings_to_argv(settings))
    #what setup() makes of the repeated flags before a run reads them
    args.cookies = cookies.parse(args.cookie)
    args.placeholders = placeholders.parse(args.placeholder)
    back = settings_from_args(args, args.output, args.URL, args.increment, settings["ended"])
    assert back == settings, back
