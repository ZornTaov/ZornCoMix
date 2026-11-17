#a page kept as something no reader can show: which files count as one, what the stand-in says, and that
#a comic's readme is not mistaken for a page
import os
import zipfile

import pytest

from comiclib.pages import listing as folder_pages
from comiclib.standin import address_in, archive_entry, held_otherwise


@pytest.fixture
def folder(tmp_path):
    def put(name, text):
        (tmp_path / name).write_text(text, encoding="utf-8")

    put('0007.txt', "https://example.com/video/abc123\n")
    put('0009.url', "https://example.com/video/12345678\n")
    put('README.txt', "This comic was saved by hand.\nSee https://example.com/about for the story.\n")
    put('notes.txt', "nothing here is an address\n")
    #a file of links that names no page of the comic, so it is not one
    put('links.txt', "https://example.com/only-an-address\n")
    #a note with the video's name run straight into its address, named like its page
    put('0021.txt', "The Comic's Big Story trailer"
                    "https://example.com/embed/_Abc-123?feature=oembed\n")
    put('0012.swf', "fake flash")
    put('0015.mp4', "not really a video")
    put('0003.png', "not really a png")
    return str(tmp_path)


@pytest.mark.parametrize("name, expected", [
    ('0007.txt', True), ('0009.url', True), ('0012.swf', True), ('0015.mp4', True),
    ('README.txt', False), ('notes.txt', False), ('0003.png', False),
    ('0021.txt', True), ('links.txt', False)])
def test_which_files_hold_a_page(folder, name, expected):
    assert bool(held_otherwise(folder, name)) == expected


def test_a_readme_is_not_swallowed_even_though_it_mentions_an_address(folder):
    assert not held_otherwise(folder, 'README.txt'), "because it is not named like a page"
    assert not held_otherwise(folder, 'links.txt'), "nor a file of links that names no page"
    address = address_in(os.path.join(folder, '0007.txt'))
    assert address[0] == "https://example.com/video/abc123", "while a note named for its page is read"


def test_a_note_the_scraper_writes_reads_back_whole(folder):
    #a shortcut was read as prose, so "[InternetShortcut] URL=" became what the note called its page and was
    #printed on its stand-in; and a page playing a video was noted by its own address, not the video's
    from comiclib.standin import note_body, note_fields, watch_address
    page, video = "https://example.com/comic/ghost-1/", "https://www.youtube.com/watch?v=_Abc-123xyz"
    assert watch_address("https://www.youtube.com/embed/_Abc-123xyz?feature=oembed") == video
    assert watch_address("https://player.vimeo.com/video/123456?h=ab") == "https://vimeo.com/123456"
    assert watch_address(page) == page, "anything else is left as it is"
    written = note_body(page, video, "Ghost  Story\n001").decode()
    assert written.startswith("[InternetShortcut]\r\nURL=" + video + "\r\n"), "a desktop opens the video"
    assert note_fields(written) == (video, "Ghost Story 001", page)
    assert note_fields(note_body(page).decode()) == (page, None, page), "nothing on it to keep: the page"
    assert note_fields("[InternetShortcut]\r\nURL=" + page + "\r\n") == (page, None, None), \
        "a note written before notes said their page is still read, with no name made up for it"


def test_what_a_stand_in_says_for_each_kind_of_note(tmp_path):
    from comiclib.standin import note_body
    page = "https://example.com/comic/ghost-1/"
    (tmp_path / "0004_ghost-1.url").write_bytes(note_body(page, "https://www.youtube.com/watch?v=abcdefghijk",
                                                          "Ghost Story 001"))
    (tmp_path / "0005_game.url").write_bytes(note_body("https://example.com/comic/game/"))
    (tmp_path / "0006_old.url").write_bytes(b"[InternetShortcut]\r\nURL=https://example.com/comic/old/\r\n")
    folder = str(tmp_path)
    assert held_otherwise(folder, "0004_ghost-1.url") == [
        "This page is a video.", "", "Ghost Story 001", "", "https://www.youtube.com/watch?v=abcdefghijk", "",
        "on the comic's page", page, "", "noted in the comic's folder as", "0004_ghost-1.url"]
    assert held_otherwise(folder, "0005_game.url")[:4] == [
        "This page is not a picture.", "", "Open it on the site:", "https://example.com/comic/game/"]
    assert held_otherwise(folder, "0006_old.url") == [
        "This page is a video.", "", "https://example.com/comic/old/", "", "noted in the comic's folder as",
        "0006_old.url"], "with no '[InternetShortcut] URL=' where its name would go"


def flash(kind, width, height):
    #a flash file's first bytes: its header, then its stage as four numbers of 16 bits in twentieths of a pixel
    import lzma
    import struct
    import zlib
    bits = format(16, "05b") + "".join(format(v * 20, "016b") for v in (0, width, 0, height))
    bits += "0" * (-len(bits) % 8)
    stage = bytes(int(bits[at:at + 8], 2) for at in range(0, len(bits), 8)) + b"\x00" * 40
    if kind == b"FWS":
        return kind + b"\x0a" + struct.pack("<I", 8 + len(stage)) + stage
    if kind == b"CWS":
        return kind + b"\x0a" + struct.pack("<I", 8 + len(stage)) + zlib.compress(stage)
    alone = lzma.compress(stage, format=lzma.FORMAT_ALONE)
    return kind + b"\x0a" + struct.pack("<II", 8 + len(stage), len(alone) - 13) + alone[:5] + alone[13:]


def box(kind, body):
    import struct
    return struct.pack(">I4s", 8 + len(body), kind) + body


def movie(width, height):
    #an mp4 with its moov after the pictures, as a camera writes one, and the sound's track ahead of the
    #picture's: the sound's header says no size, and is passed over
    import struct

    def track(w, h):
        return box(b"trak", box(b"tkhd", b"\x00" * 76 + struct.pack(">II", w << 16, h << 16)))
    return box(b"ftyp", b"isom" + b"\x00" * 4) + box(b"mdat", b"\x00" * 5000) + box(
        b"moov", box(b"mvhd", b"\x00" * 100) + track(0, 0) + track(width, height))


def test_the_shape_of_what_a_stand_in_stands_for_is_read_from_its_file(tmp_path):
    from comiclib import standin
    (tmp_path / "0001.swf").write_bytes(flash(b"FWS", 800, 200))
    (tmp_path / "0002.swf").write_bytes(flash(b"CWS", 750, 1550))
    (tmp_path / "0003.swf").write_bytes(flash(b"ZWS", 550, 400))
    (tmp_path / "0004.mp4").write_bytes(movie(1280, 720))
    (tmp_path / "0005.mp4").write_bytes(b"not really a video")
    folder = str(tmp_path)
    shapes = [standin.held_otherwise(folder, name).shape for name in sorted(os.listdir(folder))]
    assert shapes == [(800, 200), (750, 1550), (550, 400), (1280, 720), None]


def test_a_stand_in_is_drawn_the_shape_of_what_it_stands_for(tmp_path):
    from comiclib import comicinfo, standin
    from comiclib.standin import note_body
    (tmp_path / "0001.mp4").write_bytes(movie(1280, 720))
    (tmp_path / "0002.url").write_bytes(note_body("https://example.com/2/", "https://www.youtube.com/watch?v=abcdefghijk"))
    (tmp_path / "0003.mp4").write_bytes(b"not really a video")
    (tmp_path / "0004.swf").write_bytes(flash(b"CWS", 750, 1550))
    folder = str(tmp_path)
    for name, wide in (("0001.mp4", True), ("0002.url", True), ("0003.mp4", False), ("0004.swf", False)):
        lines = standin.held_otherwise(folder, name)
        made = standin.archive_entry(folder, name)[1]
        width, height = comicinfo.dimensions(made)
        assert (width, height) == standin.standin_size(lines), "measured as it is drawn: " + name
        assert (width > height) == wide, "{0} drawn {1}x{2}".format(name, width, height)
    assert comicinfo.dimensions(standin.archive_entry(folder, "0001.mp4")[1]) == (1400, 788), "a 16:9 page"
    #a stand-in with no shape of its own is the page it always was, so no archive holding one is rewritten
    plain = standin.held_otherwise(folder, "0003.mp4")
    assert standin.fingerprint(plain) == standin.fingerprint(list(plain))
    assert standin.stand_in(plain) == standin.drawn(tuple(plain), 1000, 1400, 28, 235)


def test_what_the_folder_counts_as_pages(folder):
    held = folder_pages(folder, others=True)
    assert held == ['0003.png', '0007.txt', '0009.url', '0012.swf', '0015.mp4', '0021.txt'], \
        "the pages and the pages held otherwise, and nothing else"
    assert folder_pages(folder) == ['0003.png'], "and without asking, only the pictures"


def test_the_stand_in_is_a_png_named_for_its_page_and_packs_into_a_cbz(folder, tmp_path):
    entry, made = archive_entry(folder, '0015.mp4')
    assert entry == '0015.png', "it is named for the page it stands in for"
    assert made[:8] == b'\x89PNG\r\n\x1a\n', "it is a png"
    assert 1000 < len(made) < 400000, "of a sensible size: {0}".format(len(made))
    entry2, made2 = archive_entry(folder, '0007.txt')
    assert entry2 == '0007.png' and made2[:4] == b'\x89PNG', "a note becomes a page too"
    assert archive_entry(folder, '0015.mp4')[1] == made, \
        "drawing it twice gives the same bytes, so packing is not rewritten every time"
    entry3, made3 = archive_entry(folder, '0003.png')
    assert entry3 == '0003.png' and made3 is None, "an ordinary page is left alone"

    #both sit in a cbz without complaint
    cbz = tmp_path / "standin_check.cbz"
    with zipfile.ZipFile(str(cbz), 'w') as zf:
        zf.writestr(entry, made)
        zf.writestr(entry2, made2)
    with zipfile.ZipFile(str(cbz)) as zf:
        assert zf.testzip() is None


def test_a_stand_in_is_drawn_once_and_never_just_to_be_named(folder, tmp_path, monkeypatch):
    #a third of a second a drawing: writing a comic's ComicInfo into each of its 94 chapter archives drew
    #every stand-in in the comic once per chapter, only to know what they are called in an archive
    from comiclib import cbz, standin
    standin.drawn.cache_clear()
    drawings = []
    draw = standin.grey_png
    monkeypatch.setattr(standin, "grey_png", lambda *args: drawings.append(1) or draw(*args))
    names = sorted(os.listdir(folder))
    assert standin.entry_name(folder, '0015.mp4') == '0015.png' and standin.entry_name(folder, '0003.png') == '0003.png'
    assert cbz.standins(folder, names) == {'0007.png', '0009.png', '0012.png', '0015.png', '0021.png'}
    assert drawings == [], "naming them draws nothing"
    archive = str(tmp_path / "standins.cbz")
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('0003.png', b"not really a png")
        zf.writestr('0015.png', standin.archive_entry(folder, '0015.mp4')[1])
    assert len(drawings) == 1
    #one already in the archive is not drawn again to find it is there, and one being added is drawn once,
    #though it is measured before it is written
    change = cbz.planned(archive, folder, ['0003.png', '0012.swf', '0015.mp4'], (), {"title": "MyComic"})
    assert change["added"] == ['0012.swf'] and len(drawings) == 2
    cbz.apply(archive, folder, change, metadata=False)
    assert len(drawings) == 2, "the drawing it was measured from is the one written"
    with zipfile.ZipFile(archive) as zf:
        assert zf.read('0012.png') == standin.archive_entry(folder, '0012.swf')[1]
