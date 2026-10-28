#mirror_metadata.json: the one file in each comic's folder that says everything about it. its settings
#block is the only thing anyone edits; the scrape command is rebuilt from it every run.
import json
import os
import time
from datetime import datetime, timezone

from comiclib import cookies, placeholders

METADATA_FILE = "mirror_metadata.json"
SCHEMA = 2


def now_stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def load(path):
    #the file itself, raising when it cannot be read, for a caller that has something to say about that
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read(folder):
    #a comic's metadata, or nothing, for a caller that carries on either way
    try:
        return load(os.path.join(folder, METADATA_FILE))
    except (OSError, ValueError):
        return {}


def write_json(path, body, indent=2):
    #written beside the real file and moved into place, so a run stopped part way never leaves half a file
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    spare = path + ".writing"
    with open(spare, 'w', encoding='utf-8') as f:
        json.dump(body, f, indent=indent)
        f.write('\n')
    replace_patiently(spare, path)


def replace_patiently(spare, path, tries=20, wait=0.1):
    #on windows a file another process has open cannot be replaced, and whatever reads a comic's metadata - the
    #reader, a virus scanner, a sync - holds it open for a moment. a save landing in that moment failed outright,
    #and the web page's request went unanswered. tried again for a couple of seconds instead; elsewhere the
    #first try always works
    for attempt in range(tries):
        try:
            os.replace(spare, path)
            return
        except PermissionError:
            if attempt == tries - 1:
                raise
            time.sleep(wait)


def write(folder, metadata):
    write_json(os.path.join(folder, METADATA_FILE), metadata)


def settings_to_argv(settings):
    #the single place a scrape command is built. the metadata records what a comic needs as plain values,
    #not as a command, so this is the only thing that has to know which value is which flag - and editing
    #one value in the file is the whole of changing how a comic is scraped.
    url = settings.get("url")
    if not url:
        return None
    argv = []
    if settings.get("increment") is not None:
        argv += ["--increment", str(settings["increment"])]
    if settings.get("output"):
        argv += ["--output", settings["output"]]
    if settings.get("prefix"):
        argv.append("--prefix")
    if settings.get("javascript"):
        argv.append("--enable_javascript")
    if settings.get("firefox"):
        argv.append("--firefox")
    if settings.get("waittime"):
        argv += ["--waittime", str(settings["waittime"])]
    #on by default, so only its absence is worth saying out loud
    if settings.get("cbz") is False:
        argv.append("--no-cbz")
    #also on by default, so only turning it off is worth saying
    if settings.get("direction_check") is False:
        argv.append("--no-direction-check")
    #likewise: saving every page an address holds is the default, and only a comic told to read one page
    #an address regardless needs the flag carried forward
    if settings.get("multi_page") is False:
        argv.append("--no-multi-page")
    if settings.get("cbz_path"):
        argv += ["--cbz-path", settings["cbz_path"]]
    #what the site wants to have been told before it shows the comic, an age gate's answer most often
    argv += cookies.as_args(settings.get("cookies"))
    #the name its pictures are fetched under, for a site that refuses the library's
    if settings.get("user_agent"):
        argv += ["--user-agent", settings["user_agent"]]
    #pictures the site shows where a page will be once it is out
    argv += placeholders.as_args(settings.get("placeholders"))
    argv.append(url)
    return argv


#how many moves a comic remembers, the same as the edits the editor keeps, since a move is shown among them
KEPT_MOVES = 50


def record_moves(metadata, moved, stamp=None):
    #one more move of the comic or of its archives, as moves() reads it back: each step {"what", "from",
    #"to"}, with paths relative to the library. the oldest are let go past KEPT_MOVES
    history = metadata.setdefault("history", {})
    stamp = stamp or now_stamp()
    history["moves"] = (history.get("moves") or [])[-(KEPT_MOVES - 1):] + [{"at": stamp, "moved": moved}]
    return stamp


def moves(metadata):
    #every move of the comic to another folder, oldest first: each a list of what was renamed, as
    #{"what", "from", "to"} with paths relative to the library the scraper was given. written by comiclib's
    #moving and read by the reader, which keys what it keeps of a comic by where the comic is
    found = (((metadata or {}).get("history") or {}).get("moves")) or []
    return [entry["moved"] for entry in found if isinstance(entry, dict) and isinstance(entry.get("moved"), list)]


def before_moves(path, records):
    #where a path in the library was before each of those moves, newest first. a path a move did not touch
    #was where it is now, so that move adds nothing; paths are relative, with / between their parts
    found = []
    for record in reversed(records):
        for step in record:
            came, went = step.get("from"), step.get("to")
            if came and went and (path == went or path.startswith(went + "/")):
                path = came + path[len(went):]
                found.append(path)
                break
    return found


def after_moves(path, records):
    #where a path from before the moves is now, the other way about
    for record in records:
        for step in record:
            came, went = step.get("from"), step.get("to")
            if came and went and (path == came or path.startswith(came + "/")):
                path = went + path[len(came):]
                break
    return path
