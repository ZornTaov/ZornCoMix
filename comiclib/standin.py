"""Stand-in pages, for a page no reader can show.

A comic does not always give you a picture. A page can animate, and the only capture of it is a
recording; it can be a video the comic links to, noted beside the pages; it can have been Flash before
Flash went away. Those are pages of the comic and they belong in the folder - but an archive that held
only what a reader can open would leave them out, and they would read as gaps.

So the archive gets a page of its own in their place, saying what the page is and where the real thing
is. It is drawn here rather than by an image library: requirements.txt is deliberately selenium and
requests, and a page saying where a video went is not worth rebuilding the container over.

Every archive is written through comiclib.cbz, which asks here about each file, so a page reads the same
in a comic's single archive, in its chapter archives, and in one written afresh by repack or adopt.
"""
import functools
import hashlib
import json
import os
import re
import struct
import zlib

#a page can be held as something no reader can show: a recording of a page that animated, a flash file
#from before flash went away, or a note saying where the page lives now.
video_types = re.compile(r"\.(mp4|m4v|webm|mov|mkv)$", re.I)
flash_types = re.compile(r"\.swf$", re.I)
link_types = re.compile(r"\.(txt|url|webloc)$", re.I)
#not anchored: a note can run its own words straight into the address, with no space between
a_web_address = re.compile(r"(https?://\S+)")
#a note about a page is named like a page - 0102.txt, beside 0101.png - which is what tells it from a
#comic's readme. a readme can mention all the addresses it likes; it is still not page 102.
named_for_a_page = re.compile(r"^(\d+)(?:[._])")


class NotAPicture(str):
    #a page whose comic is there but is not a picture - one you play with, drawn by the page's own script -
    #standing in a list of a page's pictures as the page's own address. kept as a note naming where it lives,
    #so the page keeps its place and its number, and a reader opens the real thing. where the comic's place
    #on the page holds a video in a frame instead, `media` is the video's address and `called` what the page
    #calls it: the page's own address alone sent a reader back to the site rather than to the video
    def __new__(cls, page, media=None, called=None):
        made = super().__new__(cls, page)
        made.media, made.called = media, called
        return made


def watch_address(address):
    #a player made to sit inside another page - youtube's /embed/ID - as the address that opens the video on
    #its own, which is what a note is for: someone opening it from the folder, or reading it off a stand-in
    found = re.match(r"https?://(?:www\.)?youtube(?:-nocookie)?\.com/embed/([\w-]{6,})", address or "")
    if found:
        return "https://www.youtube.com/watch?v=" + found.group(1)
    found = re.match(r"https?://player\.vimeo\.com/video/(\d+)", address or "")
    if found:
        return "https://vimeo.com/" + found.group(1)
    return address


def looks_like_video(address):
    #whether an address a page played in its frame is a video, rather than a game or some other site's page
    return bool(re.match(r"https?://(?:www\.)?(?:youtube\.com/watch|youtu\.be/|vimeo\.com/\d)", address or "")
                or video_types.search(re.sub(r"[?#].*$", "", address or "")))


def note_name(number, address=None):
    #what such a page is kept as: named like a page, so it is numbered as one, and read as a note - and after
    #the last part of its address, so no two notes share a name and lining them up by name can tell them apart
    path = re.sub(r'[?#].*$', '', re.sub(r'^\w+://[^/]+', '', address or ''))
    last = next((part for part in reversed(path.split('/')) if part), '')
    slug = re.sub(r'[^A-Za-z0-9._-]+', '-', re.sub(r'\.\w+$', '', last)).strip('-.')[:40] or 'link'
    return "{0:04d}_{1}.url".format(number, slug)


#the section of a note desktops pass over, saying the comic's page the note was made from and what it calls it
NOTE_SECTION = "[ZornCoMix]"


def note_body(page, media=None, called=None):
    #the shortcut format every desktop opens - at the video, where the page played one, since that is what
    #the page is - and, in a section of its own, the comic's page it was found on and what that calls it, so
    #a stand-in can say both. note_fields reads it back
    lines = ["[InternetShortcut]", "URL={0}".format(media or page), "", NOTE_SECTION, "Page={0}".format(page)]
    if called:
        lines.append("Title={0}".format(" ".join(called.split())))
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


#five columns and seven rows of dots per letter, written out rather than packed into numbers so that a
#letter that comes out wrong is a letter you can see is wrong. a nine keeps a straight stem and a g hooks
#to the left, because a video's address must not be readable two ways.
GLYPHS = {
    ' ': "...../...../...../...../...../...../.....",
    '!': "..#../..#../..#../..#../..#../...../..#..",
    '"': ".#.#./.#.#./...../...../...../...../.....",
    '#': ".#.#./.#.#./#####/.#.#./#####/.#.#./.#.#.",
    '$': "..#../.####/#.#../.###./..#.#/####./..#..",
    '%': "##.../##..#/...#./..#../.#.../#..##/...##",
    '&': ".##../#..#./#.#../.#.../#.#.#/#..#./.##.#",
    "'": "..#../..#../...../...../...../...../.....",
    '(': "...#./..#../.#.../.#.../.#.../..#../...#.",
    ')': ".#.../..#../...#./...#./...#./..#../.#...",
    '*': "...../#.#.#/.###./#####/.###./#.#.#/.....",
    '+': "...../..#../..#../#####/..#../..#../.....",
    ',': "...../...../...../...../...../..#../.#...",
    '-': "...../...../...../#####/...../...../.....",
    '.': "...../...../...../...../...../.##../.##..",
    '/': "....#/...#./..#../..#../.#.../#..../#....",
    '0': ".###./#...#/#..##/#.#.#/##..#/#...#/.###.",
    '1': "..#../.##../..#../..#../..#../..#../.###.",
    '2': ".###./#...#/....#/...#./..#../.#.../#####",
    '3': "#####/...#./..#../...#./....#/#...#/.###.",
    '4': "...#./..##./.#.#./#..#./#####/...#./...#.",
    '5': "#####/#..../####./....#/....#/#...#/.###.",
    '6': "..##./.#.../#..../####./#...#/#...#/.###.",
    '7': "#####/....#/...#./..#../.#.../.#.../.#...",
    '8': ".###./#...#/#...#/.###./#...#/#...#/.###.",
    '9': ".###./#...#/#...#/.####/....#/....#/....#",
    ':': "...../.##../.##../...../.##../.##../.....",
    ';': "...../.##../.##../...../.##../..#../.#...",
    '<': "...#./..#../.#.../#..../.#.../..#../...#.",
    '=': "...../...../#####/...../#####/...../.....",
    '>': ".#.../..#../...#./....#/...#./..#../.#...",
    '?': ".###./#...#/....#/...#./..#../...../..#..",
    '@': ".###./#...#/#.###/#.#.#/#.###/#..../.###.",
    'A': "..#../.#.#./#...#/#...#/#####/#...#/#...#",
    'B': "####./#...#/#...#/####./#...#/#...#/####.",
    'C': ".###./#...#/#..../#..../#..../#...#/.###.",
    'D': "###../#..#./#...#/#...#/#...#/#..#./###..",
    'E': "#####/#..../#..../####./#..../#..../#####",
    'F': "#####/#..../#..../####./#..../#..../#....",
    'G': ".###./#...#/#..../#.###/#...#/#...#/.####",
    'H': "#...#/#...#/#...#/#####/#...#/#...#/#...#",
    'I': ".###./..#../..#../..#../..#../..#../.###.",
    'J': "....#/....#/....#/....#/#...#/#...#/.###.",
    'K': "#...#/#..#./#.#../##.../#.#../#..#./#...#",
    'L': "#..../#..../#..../#..../#..../#..../#####",
    'M': "#...#/##.##/#.#.#/#.#.#/#...#/#...#/#...#",
    'N': "#...#/#...#/##..#/#.#.#/#..##/#...#/#...#",
    'O': ".###./#...#/#...#/#...#/#...#/#...#/.###.",
    'P': "####./#...#/#...#/####./#..../#..../#....",
    'Q': ".###./#...#/#...#/#...#/#.#.#/#..#./.##.#",
    'R': "####./#...#/#...#/####./#.#../#..#./#...#",
    'S': ".####/#..../#..../.###./....#/....#/####.",
    'T': "#####/..#../..#../..#../..#../..#../..#..",
    'U': "#...#/#...#/#...#/#...#/#...#/#...#/.###.",
    'V': "#...#/#...#/#...#/#...#/#...#/.#.#./..#..",
    'W': "#...#/#...#/#...#/#.#.#/#.#.#/##.##/#...#",
    'X': "#...#/#...#/.#.#./..#../.#.#./#...#/#...#",
    'Y': "#...#/#...#/.#.#./..#../..#../..#../..#..",
    'Z': "#####/....#/...#./..#../.#.../#..../#####",
    '[': ".###./.#.../.#.../.#.../.#.../.#.../.###.",
    '\\': "#..../#..../.#.../..#../..#../...#./....#",
    ']': ".###./...#./...#./...#./...#./...#./.###.",
    '^': "..#../.#.#./#...#/...../...../...../.....",
    '_': "...../...../...../...../...../...../#####",
    '`': ".#.../..#../...../...../...../...../.....",
    'a': "...../...../.###./....#/.####/#...#/.####",
    'b': "#..../#..../####./#...#/#...#/#...#/####.",
    'c': "...../...../.####/#..../#..../#..../.####",
    'd': "....#/....#/.####/#...#/#...#/#...#/.####",
    'e': "...../...../.###./#...#/#####/#..../.###.",
    'f': "..##./.#..#/.#.../####./.#.../.#.../.#...",
    'g': "...../...../.####/#...#/.####/....#/.###.",
    'h': "#..../#..../####./#...#/#...#/#...#/#...#",
    'i': "..#../...../.##../..#../..#../..#../.###.",
    'j': "...#./...../..##./...#./...#./#..#./.##..",
    'k': "#..../#..../#..#./#.#../##.../#.#../#..#.",
    'l': ".##../..#../..#../..#../..#../..#../.###.",
    'm': "...../...../##.#./#.#.#/#.#.#/#...#/#...#",
    'n': "...../...../####./#...#/#...#/#...#/#...#",
    'o': "...../...../.###./#...#/#...#/#...#/.###.",
    'p': "...../...../####./#...#/####./#..../#....",
    'q': "...../...../.####/#...#/.####/....#/....#",
    'r': "...../...../#.##./##..#/#..../#..../#....",
    's': "...../...../.####/#..../.###./....#/####.",
    't': ".#.../.#.../####./.#.../.#.../.#..#/..##.",
    'u': "...../...../#...#/#...#/#...#/#..##/.##.#",
    'v': "...../...../#...#/#...#/#...#/.#.#./..#..",
    'w': "...../...../#...#/#...#/#.#.#/#.#.#/.#.#.",
    'x': "...../...../#...#/.#.#./..#../.#.#./#...#",
    'y': "...../...../#...#/#...#/.####/....#/.###.",
    'z': "...../...../#####/...#./..#../.#.../#####",
    '{': "...##/..#../..#../.#.../..#../..#../...##",
    '|': "..#../..#../..#../..#../..#../..#../..#..",
    '}': "##.../..#../..#../...#./..#../..#../##...",
    '~': "...../.#..#/#.#.#/#..#./...../...../.....",
}
UNKNOWN = "#####/#...#/#...#/#...#/#...#/#...#/#####"


def grey_png(width, height, lit, background, ink):
    #a greyscale png written by hand: a header, the rows each behind a filter byte, and an end. zlib and
    #struct are standard, which is the point - the container carries selenium and requests and nothing
    #else, and a page saying where its video went is not worth rebuilding an image over.
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(ink if (x, y) in lit else background for x in range(width))

    def chunk(kind, body):
        return (struct.pack('>I', len(body)) + kind + body
                + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(rows), 9))
            + chunk(b'IEND', b''))


def stand_in(lines, width=1000, height=1400, background=28, ink=235):
    #a stand-in is drawn a dot at a time, a third of a second each, and the same lines always draw the same
    #bytes: one already drawn is not drawn again. an archive is measured and then written from the same
    #drawings, and a comic's chapters are packed one after another in one run
    return drawn(tuple(lines), width, height, background, ink)


@functools.lru_cache(maxsize=256)
def drawn(lines, width, height, background, ink):
    #the lines centred on a page of their own, as big as the longest of them allows. a long address is
    #never broken across lines, since a broken one cannot be read back, so the page widens for it rather
    #than shrinking the letters to where nobody can make out a video's id
    longest = max((len(line) for line in lines), default=1) or 1
    width = max(width, longest * 6 * 4 + 80)
    scale = max(2, min((width - 80) // (longest * 6), (height - 80) // (len(lines) * 10), 14))
    lit = set()
    wide, high = longest * 6 * scale, len(lines) * 10 * scale
    left0, top = (width - wide) // 2, (height - high) // 2
    for row, line in enumerate(lines):
        left = left0 + (wide - len(line) * 6 * scale) // 2
        for at, letter in enumerate(line):
            for y, dots in enumerate(GLYPHS.get(letter, UNKNOWN).split('/')):
                for x, dot in enumerate(dots):
                    if dot != '#':
                        continue
                    for dy in range(scale):
                        for dx in range(scale):
                            lit.add((left + (at * 6 + x) * scale + dx, top + (row * 10 + y) * scale + dy))
    return grey_png(width, height, lit, background, ink)


def archive_entry(folder, name):
    #what goes into the archive for this file: the file itself, or a stand-in page saying where the real
    #thing is. the original is never touched - the folder is the copy that keeps everything.
    lines = held_otherwise(folder, name)
    if not lines:
        return name, None
    return os.path.splitext(name)[0] + ".png", stand_in(lines)


#how stand-ins are drawn. a change to the drawing - the letters, the page's size, its shades - changes the
#bytes of every stand-in, so this goes up with it, and no size remembered from the old drawing is believed
DRAWING = 1


def fingerprint(lines):
    #what a stand-in is drawn from, and with which drawing, short enough to keep beside its size
    return hashlib.sha1(json.dumps([DRAWING, list(lines)]).encode("utf-8")).hexdigest()[:16]


class Sizes:
    #how big each stand-in of a comic comes to, remembered in its metadata. packing checks every chapter
    #archive holds its stand-ins at the size they draw to, which drew every one in the comic on every pack -
    #a third of a second each - to learn a size that only changes when what the stand-in says does
    def __init__(self, remembered=None):
        self.remembered = dict(remembered) if isinstance(remembered, dict) else {}
        #only those asked about this time, so a stand-in the comic no longer has is not kept for ever
        self.used = {}

    def of(self, lines):
        key = fingerprint(lines)
        size = self.remembered.get(key)
        if not isinstance(size, int):
            size = len(stand_in(lines))
        self.used[key] = size
        return size

    def changed(self):
        return self.used != self.remembered


def entry_name(folder, name):
    #only what archive_entry names it, with nothing drawn: asking which entries of an archive are stand-ins,
    #or whether one is there yet, drew every stand-in in the comic, for every chapter archive of it
    return os.path.splitext(name)[0] + ".png" if held_otherwise(folder, name) else name


def address_in(path):
    #the web address a note beside the pages holds, and whatever it calls it. a note can run the two
    #straight together - "My Comic's trailerhttps://example.com/video/..." - so the address is looked
    #for inside the line rather than as the whole of it.
    #
    #a comic's readme is not a page, though, and the difference is that a note about one page says almost
    #nothing else: it is short, and most of what it says is the address. a readme is longer than that,
    #whatever addresses it happens to mention.
    return note_in(path)[:2]


def note_in(path):
    #note_fields for a note in the folder: its address, what it calls it, and the comic's page it came from
    try:
        if os.path.getsize(path) > NOTE_LIMIT:
            return None, None, None
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read(NOTE_LIMIT)
    except OSError:
        return None, None, None
    return note_fields(text)


#a note about one page says almost nothing but the address
NOTE_LIMIT = 1024


def note_address(text):
    #the address a note holds, and what it calls it, from the note's text - read from the folder, or out of
    #an archive someone else made, by the same rule
    return note_fields(text)[:2]


def note_fields(text):
    #the address, the name and the comic's page a note says. a shortcut is read by its keys: read as prose,
    #everything ahead of its address - "[InternetShortcut] URL=" - was taken for what the note called its page,
    #and printed on every stand-in the scraper's own notes were drawn as
    text = (text or "").strip()
    if text.startswith("[InternetShortcut]"):
        keys = {}
        for line in text.splitlines():
            key, equals, value = line.partition("=")
            if equals:
                keys.setdefault(key.strip().lower(), value.strip())
        if a_web_address.fullmatch(keys.get("url", "")):
            return keys["url"], keys.get("title") or None, keys.get("page") or None
    found = a_web_address.search(text)
    if not found:
        return None, None, None
    address = found.group(1).rstrip('.,;)')
    called = text[:found.start()].strip().strip('-:|').strip()
    return address, called or None, None


def held_otherwise(folder, name):
    #whether this file is a page of the comic kept in some form a reader cannot show, and what a stand-in
    #for it should say. the page is not lost - it is right there in the folder - so the stand-in's job is
    #to say so, and where.
    if video_types.search(name) or flash_types.search(name):
        return lines_for(name)
    #a note about a page is named like a page - 0102.txt, beside 0101.png - which is what tells it from
    #a comic's readme. a readme can mention all the addresses it likes; it is still not page 102, and a
    #ratio of address to prose could never have told the two apart reliably: a note can be a long video
    #title and one line of address.
    if is_note_name(name):
        address, called, page = note_in(os.path.join(folder, name))
        if address:
            return lines_for(name, address, called, page=page)
    return None


def is_note_name(name):
    #a note that could be about a page: a link file, named like a page
    return bool(link_types.search(name) and named_for_a_page.match(os.path.basename(name)))


def lines_for(name, address=None, called=None, where="the comic's folder", page=None):
    #what a stand-in says for a page held as `name`: a video or flash file, or a note holding `address` -
    #and, for a note the scraper made, `page`, the comic's page it was found on
    if video_types.search(name):
        return ["This page is a video.", "", "It is in {0} as".format(where), name]
    if flash_types.search(name):
        return ["This page was Flash.", "", "It is in {0} as".format(where), name]
    #the name the note gives it is worth showing: "My Comic's trailer" says more about the page than the
    #address does
    named = wrapped(called) if called else []
    noted = ["", "noted in {0} as".format(where), name]
    if page and page == address:
        #nothing on the page the scraper could keep: the page itself is what to open
        return ["This page is not a picture."] + named + ["", "Open it on the site:", address] + noted
    if page:
        what = "This page is a video." if looks_like_video(address) else "This page plays from another site."
        return [what] + named + ["", address, "", "on the comic's page", page] + noted
    return ["This page is a video."] + named + ["", address] + noted


def wrapped(text, width=46):
    #prose broken into lines that fit. only ever used on what a note calls its page: an address is left
    #whole, because a broken one cannot be read back
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = "{0} {1}".format(line, word).strip()
    if line:
        lines.append(line)
    return [""] + lines if lines else []

