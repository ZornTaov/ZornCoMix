#the name every fetch made outside the browser gives itself: the pictures a scrape saves, and every page
#chapters.py reads. a site can refuse a name that looks like a scraper's - one dropped the connection on every
#picture asked for under a chrome years out of date, and answered the same request under a current one - so
#the library can set its own (user_agent in ComicScraper.json) and a comic its own (user_agent in its
#settings, given to a scrape as --user-agent), which beats the library's. the scrape's browser keeps the name
#it was built with: chrome's real one agrees with everything else chrome says about itself, and one put over
#it might not. stdlib only, since metadata imports cookies, which imports this, and the reader imports metadata
from comiclib import config

#a current chrome's, in the reduced form chrome itself sends, which gives only its major version
default = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/155.0.0.0 Safari/537.36")
#the name the command in this process uses, set once by it with use(), as download.verbose is
current = default


def clean(given):
    #one as typed into the page or given on a command line: none at all is None, so emptying the box puts the
    #library's back rather than leaving an empty name to send. a header cannot hold a line break, and requests
    #refuses one only once the first picture is asked for, so it is caught here instead
    text = str(given or "").strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError("a User-Agent is one line of plain text, as a browser's own is; paste it again without "
                         "the line break")
    return text or None


def library():
    #the library's own, read fresh like every other setting, so one saved from the page reaches the next run
    try:
        return clean(config.load_config().get("user_agent"))
    except ValueError:
        print("WARNING: the user_agent in {0} is not one line of text, so the built-in one is used. Set it "
              "again in the web page's Settings, under Advanced settings.".format(config.config_path()), flush=True)
        return None


def pick(comic=None):
    #the comic's, the library's, or the built-in one, in that order
    return clean(comic) or library() or default


def use(comic=None):
    global current
    current = pick(comic)
    return current
