#pictures a site shows where a page will be once it is out. a comic published a week to an address fills it a
#day at a time, and shows one picture - the same one in every slot not out yet, week after week - in the rest.
#saved, it was a page of the comic: numbered after the last real one, sorted before the first (a 000.jpg says
#page 0), and in the place the real page would be numbered when it came. a comic's settings name them, as
#{"placeholders": [address, ...]}, a command line as --placeholder ADDRESS; a scrape stops at the first one,
#since nothing after a slot not out yet can be numbered, and the next run starts again at that address.
#metadata reads and writes them, and the reader imports metadata, so this is stdlib only
import re
from urllib.parse import urlsplit


def parse(given):
    #as typed into the page or given on command lines: whole addresses, or the path alone for a picture the
    #site serves from more than one host, put apart by spaces, line breaks or ;. none at all is None, so
    #emptying the box takes the setting away rather than leaving an empty list behind
    if isinstance(given, (list, tuple)):
        given = " ".join(str(one) for one in given)
    found = []
    for one in re.split(r"[\s;]+", str(given or "")):
        if not one:
            continue
        if not (re.match(r"^https?://[^/\s]+/\S*$", one) or one.startswith("/")):
            raise ValueError("{0} is not a picture's address. Give it whole, as https://example.com/img/"
                             "coming-soon.png, or from its first /, as /img/coming-soon.png; the browser's "
                             "Copy image address gives it whole.".format(one))
        if one not in found:
            found.append(one)
    return found or None


def as_args(listed):
    argv = []
    for one in listed or []:
        argv += ["--placeholder", one]
    return argv


def plain(address):
    #the part that says which picture it is: http or https, a query a site adds to bust caches, and the case
    #of the host name all say the same picture
    parts = urlsplit(address)
    return (parts.netloc.lower(), parts.path)


def matches(src, listed):
    #whether a picture found as the comic is one the comic's settings name as not out yet
    if not src or not listed:
        return False
    host, path = plain(str(src))
    for one in listed:
        if one.startswith("/"):
            if path == urlsplit(one).path:
                return True
        elif (host, path) == plain(one):
            return True
    return False
