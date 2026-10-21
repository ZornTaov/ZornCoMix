#the harness's web page itself: a page started for one test is that test's own, never another's that came up
#on the same port. tests run sixteen at a time, and a port found free and let go can be found free by two
#of them; a page that only asked whether something answered there talked to the first test's library from
#then on - a plugin's dialog not served, because that library had no plugin.
import pytest

import conftest
from comiclib.web.server import PageServer


def test_a_port_the_page_is_on_is_not_shared():
    #on windows, SO_REUSEADDR let a second server bind the port and take some of its connections: two
    #updaters on one port each answered for the other's library
    first = PageServer(("127.0.0.1", 0), None)
    try:
        with pytest.raises(OSError):
            PageServer(("127.0.0.1", first.server_address[1]), None).server_close()
    finally:
        first.server_close()


def test_a_page_whose_port_is_taken_is_not_taken_for_its_own(web, tmp_path, monkeypatch):
    first = web()
    other_root = tmp_path / "other"
    (other_root / "Uncompressed").mkdir(parents=True)
    other_config = tmp_path / "other-config"
    (other_config / "index").mkdir(parents=True)
    ports = iter([first.port])
    #the first port asked for is the one the other page has; any after it, a free one as usual
    real = conftest.free_port
    monkeypatch.setattr(conftest, "free_port", lambda: next(ports, None) or real())
    second = conftest.WebUI(other_root, other_config)
    try:
        assert second.port != first.port
        _, state = second.call("/api/state")
        assert conftest.same_path(state["root"], other_root), state["root"]
    finally:
        second.stop()
