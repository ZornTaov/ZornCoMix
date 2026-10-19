#cookies a comic's site wants before it shows anything: the one a "you must be 18" page sets when its button
#is pressed, saying it was. a site that checks for it on every request sends a page without the comic to
#anyone who has not got it - so the browser, every image fetched, and every page read for chapters all carry
#it, or one of them reads the gate and takes it for the comic. kept in a comic's settings as
#{"name": "value"}, given on a command line as --cookie name=value. metadata reads and writes them, and the
#reader imports metadata without a browser or requests to hand, so those are imported only where they are used
import ipaddress
from urllib.parse import urlparse

#the browser's own name for itself, which some sites want before they answer at all
USER_AGENT = "Mozilla/5.0"

#the cookies of the comic being worked on, and one of its pages to say which site they are for, for the parts
#of chapters.py that read the site without being handed the comic's settings: set once by the command, with
#use(), as download.verbose is
for_comic = {}
comic_url = None


def use(settings):
    #the comic chapters.py has been pointed at, by its settings
    global for_comic, comic_url
    for_comic = dict((settings or {}).get("cookies") or {})
    comic_url = (settings or {}).get("url")


def parse(given):
    #--cookie name=value, as many as were given, into the settings' {"name": "value"}. a value can hold an
    #"=" of its own, so only the first one divides
    cookies = {}
    for one in given or []:
        name, said, value = one.partition("=")
        name = name.strip()
        if not said or not name:
            raise ValueError("--cookie {0} has no name=value in it. Give the cookie as the site sets it, "
                             "--cookie AGE_CHECKED=yes; the browser's developer tools show it under the "
                             "site's cookies after its gate has been passed by hand.".format(one))
        cookies[name] = value.strip()
    return cookies


def as_args(cookies):
    #the settings' cookies as the command line gives them, in the order they were written down
    argv = []
    for name, value in (cookies or {}).items():
        argv += ["--cookie", "{0}={1}".format(name, value)]
    return argv


def domain_for(url):
    #the domain a comic's cookies are set for: its site and everything under it, since the pictures are often
    #served from a neighbour - static.example.com beside www.example.com - that checks the same cookie. a
    #site reached by its address alone, or by a name with no dots in it, has no neighbours, and a cookie
    #for one is set for exactly that host
    host = (urlparse(url).hostname or "").lower()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    if "." not in host:
        return host
    if host.startswith("www."):
        host = host[4:]
    return "." + host


def session(cookies=None, url=None):
    #a requests session for reading a comic's site, carrying its cookies. url is any page of the comic,
    #which says what site they are for; without one they go to every site the session reads. left out
    #altogether, both are the comic's that use() was told of
    import requests
    if cookies is None:
        cookies, url = for_comic, url or comic_url
    made = requests.Session()
    made.headers.update({"User-Agent": USER_AGENT})
    domain = domain_for(url) if url else None
    #python's cookie jar reads a host with no dots in its name as that name with .local after it, and holds
    #back a cookie set for the name alone - a browser does not
    if domain and "." not in domain:
        domain += ".local"
    for name, value in (cookies or {}).items():
        if domain:
            made.cookies.set(name, value, domain=domain, path="/")
        else:
            made.cookies.set(name, value)
    return made


def jar(cookies, url):
    #the same cookies on their own, for a single requests call rather than a session
    return session(cookies, url).cookies


def from_browser(driver):
    #the cookies the browser holds for the page it is on, as {"name": "value"}: what a gate's button set, for
    #the pictures fetched outside the browser, which the gate checks for as well
    import selenium.common.exceptions as se
    try:
        return {one["name"]: one["value"] for one in driver.get_cookies() if one.get("name")}
    except (se.WebDriverException, AttributeError, TypeError, KeyError):
        return {}


def into_browser(driver, cookies, url):
    #set before the browser loads anything, so the gate is never met at all. selenium itself will only set a
    #cookie for the site a browser already has open, which would mean loading the gate first - chrome's own
    #tools set one for any address, so chrome is told that way. firefox has no such tool: it opens the page
    #and is given them there, and whoever opens the page next gets it with them
    import selenium.common.exceptions as se
    if not cookies:
        return
    domain = domain_for(url)
    try:
        for name, value in cookies.items():
            driver.execute_cdp_cmd("Network.setCookie", {"name": name, "value": value, "domain": domain,
                                                         "path": "/"})
        return
    except (AttributeError, se.WebDriverException):
        pass
    driver.get(url)
    for name, value in cookies.items():
        try:
            driver.add_cookie({"name": name, "value": value, "path": "/"})
        except se.WebDriverException as error:
            print("WARNING: the browser would not take the cookie {0}: {1}".format(name, error), flush=True)
