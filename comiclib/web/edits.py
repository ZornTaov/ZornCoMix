#the changes the page can make: a comic's settings, the library's settings, and the chapter tools, which
#run chapters.py so that the page and the command line mean exactly the same thing by each.
import base64
import binascii
import json
import os
import re
import subprocess
import sys
import tempfile
import time

from comiclib import comicinfo, cookies, moving, placeholders, plugins, useragent
from comiclib.chapters.index import index_path, set_aside
from comiclib.metadata import write_json
from comiclib.plugins import field_value
from comiclib.web.adding import clean_folder
from comiclib.web.views import find_comic, is_moving, is_rewinding, is_running, read_metadata, walk_needed

#the settings a person may change from the page, and what each one has to be. output is left out on
#purpose: a comic's folder is what says where it lives, and update_comics ignores a stored output anyway
editable = {
    "url": "url",
    "increment": "count",
    "cbz_path": "text",
    "prefix": "flag",
    "javascript": "flag",
    "firefox": "flag",
    "waittime": "count",
    "cbz": "flag",
    "direction_check": "flag",
    "multi_page": "flag",
    "ended": "flag",
    "cookies": "cookies",
    "user_agent": "agent",
    "placeholders": "placeholders",
}
#of those, the ones a comic another program scrapes has too: everything else is mirror_base's own
plugin_kept = ("cbz", "cbz_path", "ended")
#the paths a scrape found this comic's image and next link by, which it keeps in its state rather than its
#settings and tries ahead of every list. a wrong one is kept for as long as it matches anything - a site's
#user icon saved as page after page, a next link that stays where it is and calls the comic caught up - so
#they are put right here, by hand, rather than by editing the metadata file
remembered_paths = ("image_xpath", "next_xpath")
max_edits = 50


def insert_page(args, comic, given):
    #a page the comic's own links skip past, put in where it belongs. it reads the page in a browser and
    #moves every file after it, so it takes minutes on a long comic rather than seconds.
    url = str(given.get("url") or "").strip()
    after = str(given.get("after") or "").strip()
    if not re.match(r"^https?://\S+$", url):
        return 400, {"error": "the page to put in needs its full http(s) address"}
    if not after:
        return 400, {"error": "say which page it follows"}
    script = os.path.join(os.path.dirname(os.path.abspath(args.script)), "chapters.py")
    command = [sys.executable, "-u", script, "insert", comic.folder, "--url", url, "--after", after]
    if args.root:
        command += ["--root", args.root]
    if given.get("dry_run"):
        command.append("--dry-run")
    try:
        done = subprocess.run(command, capture_output=True, text=True, errors="replace",
                              env=dict(os.environ, PYTHONUNBUFFERED="1"), timeout=3600)
    except subprocess.SubprocessError as error:
        return 500, {"error": "could not put that page in: {0}".format(error)}
    output = ((done.stdout or "") + (done.stderr or "")).strip()
    if done.returncode != 0:
        first = [line for line in output.splitlines() if line.strip().startswith("ERROR")]
        return 400, {"error": (first[0] if first else "that did not work")[:300],
                     "output": output[-4000:]}
    return 200, {"output": output[-8000:]}


def rewind_command(args, comic, given):
    #chapters.py rewind as the page asked for it: back to before a run, or to a page by its number, with its
    #address where the comic's record does not know it. (command, None), or (None, what is wrong)
    script = os.path.join(os.path.dirname(os.path.abspath(args.script)), "chapters.py")
    command = [sys.executable, "-u", script, "rewind", comic.folder]
    if args.root:
        command += ["--root", args.root]
    run_id = str(given.get("run") or "").strip()
    page = str(given.get("from") if given.get("from") is not None else "").strip()
    if run_id:
        command += ["--run", run_id]
    elif re.match(r"^\d+$", page) and int(page) >= 1:
        command += ["--from", page]
    else:
        return None, "say which page to go back to, as a number: it and every page after it are taken off"
    url = str(given.get("url") or "").strip()
    if url:
        if not re.match(r"^https?://\S+$", url):
            return None, "the page's address has to be a full http(s) address"
        command += ["--url", url]
    return command, None


def preview_rewind(args, comic, given):
    #what going back would do, said by chapters.py itself in a dry run: a moment's reading of the folder and
    #the record, nothing changed. the page shows it before anything is queued, and it is asked again then,
    #so going back that cannot be done is said at once rather than queued to fail
    command, problem = rewind_command(args, comic, given)
    if problem:
        return 400, {"error": problem}
    try:
        done = subprocess.run(command + ["--dry-run"], capture_output=True, text=True, errors="replace",
                              env=dict(os.environ, PYTHONUNBUFFERED="1"), timeout=600)
    except subprocess.SubprocessError as error:
        return 500, {"error": "could not work out going back: {0}".format(error)}
    lines = [line for line in (done.stdout or "").splitlines() if line.strip() and not line.startswith("Nothing was")]
    if done.returncode != 0:
        said = [line for line in lines if line.startswith("ERROR")]
        return 400, {"error": (said[0][len("ERROR: "):] if said else (done.stderr or "that did not work"))[:600]}
    return 200, {"lines": lines}


def fix_chapter(args, comic, given):
    #one correction to one boundary, run through chapters.py so that the page and the command line mean
    #exactly the same thing by it. it takes a moment rather than a job: nothing is fetched and nothing is
    #written but the metadata.
    script = os.path.join(os.path.dirname(os.path.abspath(args.script)), "chapters.py")
    command = [sys.executable, script, "fix", comic.folder, "--root", args.root]
    if given.get("clear"):
        command.append("--clear")
    else:
        at = str(given.get("at") or "").strip()
        if not at:
            return 400, {"error": "say which page the correction is about"}
        command += ["--at", at]
        if given.get("forget"):
            command.append("--forget")
        elif given.get("drop"):
            command.append("--drop")
        else:
            label = str(given.get("label") or "").strip()
            if not label:
                return 400, {"error": "say what the chapter starting there is called"}
            command += ["--label", label]
    try:
        #a correction on a comic whose archives are written rewrites the ones that changed, so this can
        #be a minute of zipping rather than a metadata edit
        done = subprocess.run(command, capture_output=True, text=True, errors="replace",
                              env=dict(os.environ, PYTHONUNBUFFERED="1"), timeout=1800)
    except subprocess.SubprocessError as error:
        return 500, {"error": "could not work that out: {0}".format(error)}
    output = (done.stdout or "") + (done.stderr or "")
    if done.returncode != 0:
        return 400, {"error": output.strip().splitlines()[0] if output.strip() else "that did not work",
                     "output": output[-2000:]}
    return 200, {"output": output[-4000:]}


#the biggest picture the page may send for one page, base64 and all: a long strip is a few megabytes
max_picture = 40 * 1024 * 1024


def fix_page(args, comic, given):
    #which file is which page, said from the Pages dialog, run through chapters.py pagefix so the page and
    #the command line mean the same by it. it lines the comic up again, which reads the folder but fetches
    #nothing - unless a picture is given by its address, which is one fetch
    script = os.path.join(os.path.dirname(os.path.abspath(args.script)), "chapters.py")
    command = [sys.executable, "-u", script, "pagefix", comic.folder]
    if args.root:
        command += ["--root", args.root]
    at = str(given.get("at") or "").strip()
    name = os.path.basename(str(given.get("file") or "").strip())
    picture = str(given.get("picture") or "")
    picture_url = str(given.get("picture_url") or "").strip()
    if given.get("align"):
        #lining it up again with nothing said: an alignment from before alignments kept what stood in their
        #way has nothing for the dialog to show until it is made again
        command[3] = "align"
    elif given.get("clear"):
        command.append("--clear")
    elif picture or picture_url:
        if not at:
            return 400, {"error": "say which page the picture is for"}
        command += ["--at", at]
    elif at:
        command += ["--at", at]
        if given.get("forget"):
            command.append("--forget")
        elif given.get("drop"):
            command.append("--drop")
        elif name:
            command += ["--file", name]
        else:
            return 400, {"error": "say which file page {0} is, or that it is no page".format(at)}
    elif name:
        command += ["--file", name]
        if given.get("forget"):
            command.append("--forget")
        elif str(given.get("after") or "").strip():
            command += ["--after", str(given["after"]).strip()]
    else:
        return 400, {"error": "say which page, or which file, this is about"}
    for key in ("src", "note"):
        if str(given.get(key) or "").strip():
            command += ["--" + key, str(given[key]).strip()]
    spare = None
    if picture_url:
        if not re.match(r"^https?://\S+$", picture_url):
            return 400, {"error": "the picture's address has to be a full http(s) address"}
        command += ["--picture", picture_url]
    elif picture:
        #sent as base64 in the json, since only json is taken from the page; written to a file of its own for
        #chapters.py to read, outside the library and the config folder both, and removed after
        if len(picture) > max_picture:
            return 413, {"error": "that picture is too big to send this way"}
        try:
            data = base64.b64decode(picture.split(",", 1)[-1], validate=True)
        except (ValueError, binascii.Error):
            return 400, {"error": "the picture did not arrive whole; choose it again"}
        handle, spare = tempfile.mkstemp(prefix="zcm-picture-")
        with os.fdopen(handle, "wb") as f:
            f.write(data)
        command += ["--picture", spare]
    try:
        done = subprocess.run(command, capture_output=True, text=True, errors="replace",
                              env=dict(os.environ, PYTHONUNBUFFERED="1"), timeout=1800)
    except subprocess.SubprocessError as error:
        return 500, {"error": "could not work that out: {0}".format(error)}
    finally:
        if spare and os.path.exists(spare):
            os.remove(spare)
    output = ((done.stdout or "") + (done.stderr or "")).strip()
    #1 is the comic lining up unsettled, which is an answer rather than a failure: the dialog shows what is
    #still wrong. 2 is the fix refused
    if done.returncode == 2:
        said = [line for line in output.splitlines() if line.strip().startswith("ERROR")]
        return 400, {"error": (said[0][len("ERROR: "):] if said else "that did not work")[:400],
                     "output": output[-4000:]}
    return 200, {"output": output[-8000:], "settled": done.returncode == 0}


def try_chapter_list(args, comic, given):
    #reading an archive page and saying what it would be read as. it fetches one page and writes nothing,
    #so it answers "is this page usable" before a comic is committed to it - or walked for it.
    url = str(given.get("url") or "").strip()
    if not re.match(r"^https?://\S+$", url):
        return 400, {"error": "the chapter list has to be a full http(s) address"}
    like = str(given.get("like") or "").strip()
    if not comic and not re.match(r"^https?://\S+$", like):
        return 400, {"error": "give one of the comic's own page addresses, so its pages can be told "
                              "from everything else linked on that page"}
    script = os.path.join(os.path.dirname(os.path.abspath(args.script)), "chapters.py")
    command = [sys.executable, "-u", script, "try", comic.folder if comic else ".", "--archive", url]
    if like:
        command += ["--like", like]
    if given.get("browser"):
        command.append("--browser")
    if args.root:
        command += ["--root", args.root]
    began = time.time()
    try:
        done = subprocess.run(command, capture_output=True, text=True, errors="replace",
                              env=dict(os.environ, PYTHONUNBUFFERED="1"), timeout=600)
    except subprocess.SubprocessError as error:
        return 500, {"error": "could not read that page: {0}".format(error)}
    output = ((done.stdout or "") + (done.stderr or "")).strip()
    #a page that reads as nothing still has plenty to say about why, so its output is the answer either way
    return 200, {"output": output[-20000:], "seconds": int(time.time() - began),
                 "exit_code": done.returncode}


def cookie_value(given):
    #a comic's cookies as the page sends them: written the way a browser's Cookie header has them,
    #"AGE_OK=yes; theme=dark", or one to a line - or already as {"name": "value"}. none at all is None, which
    #is how a comic that never had any reads, so emptying the box takes the setting away rather than
    #leaving an empty one behind
    if isinstance(given, dict):
        held = {str(name).strip(): str(value).strip() for name, value in given.items() if str(name).strip()}
    else:
        parts = [part.strip() for part in re.split(r"[;\n]", str(given or "")) if part.strip()]
        try:
            held = cookies.parse(parts)
        except ValueError:
            raise ValueError("each cookie is name=value, as AGE_OK=yes; several are put apart with ;")
    return held or None


def path_value(given):
    #an element path as typed, or None for a box emptied, which leaves the next scrape to search the lists
    #afresh. only its shape is checked: whether it finds the comic is for the page check to say, on the site
    path = str(given or "").strip()
    if not path:
        return None
    if "\n" in path or "\r" in path or not path.startswith(("/", "(", ".")):
        raise ValueError('an element path is one XPath, starting with / - as //*[@id="comic"]//img')
    return path


def clean_settings(given):
    #checks each value the page sent, so a typo turns into a message rather than a comic that will not run
    cleaned, problems = {}, []
    for key, kind in editable.items():
        if key not in given:
            continue
        if kind == "cookies":
            try:
                cleaned[key] = cookie_value(given[key])
            except ValueError as error:
                problems.append(str(error))
            continue
        if kind == "agent":
            try:
                cleaned[key] = useragent.clean(given[key])
            except ValueError as error:
                problems.append(str(error))
            continue
        if kind == "placeholders":
            try:
                cleaned[key] = placeholders.parse(given[key])
            except ValueError as error:
                problems.append(str(error))
            continue
        try:
            cleaned[key] = field_value(kind, given[key])
        except ValueError:
            problems.append("the start page must be a full http(s) address" if kind == "url"
                            else "{0} must be a whole number, 0 or more".format(key))
    return cleaned, problems


def plugin_settings(settings, given):
    #a plugin comic's settings as sent: its plugin's own, checked against what its plugin.json says each is,
    #and of the rest only what any comic has whoever scrapes it. (cleaned, the plugin's, problems)
    try:
        plugin = plugins.load(settings["scraper"], with_hooks=False)
    except plugins.PluginError as error:
        return {}, {}, [str(error)]
    cleaned, problems = clean_settings({key: given[key] for key in plugin_kept if key in given})
    sent = dict(given.get("plugin") or {})
    if "url" in given and plugin.field("url"):
        sent["url"] = given["url"]
    values, wrong = plugins.check_values(plugin, sent, partial=True)
    url, own = plugins.split_values(values)
    if "url" in values:
        cleaned["url"] = url
    return cleaned, own, problems + wrong


def save_settings(args, uc, runner, name, given, expected_updated):
    comic = find_comic(args, uc, name)
    if comic is None:
        return 404, {"error": "no comic named {0}".format(name)}
    #a running scrape rewrites this file after every page, and would quietly put back whatever it started with
    if is_running(runner, comic.name):
        return 409, {"error": "{0} is being scraped right now; stop it or wait for it to finish".format(name)}
    if is_moving(runner, comic.name):
        return 409, {"error": "{0} is being moved; reopen it once the move has finished".format(name)}
    if is_rewinding(runner, comic.name):
        return 409, {"error": "{0} is waiting to go back to an earlier page; reopen it once that has "
                              "finished".format(name)}
    path = os.path.join(comic.folder, uc.metadata_file)
    try:
        metadata = read_metadata(path)
    except (OSError, ValueError) as error:
        return 500, {"error": "could not read {0}: {1}".format(path, error)}
    settings = dict(metadata.get("settings") or {})
    own = None
    if settings.get("scraper"):
        cleaned, own, problems = plugin_settings(settings, given)
        #a plugin comic's chapters come from its runs, not from an archive page or a size to cut at
        given = dict(given, chapters_url=None, chapters_every=None)
    else:
        cleaned, problems = clean_settings(given)
    #a plugin's program finds its own pages, so a plugin comic has no paths to put right. a path is checked
    #only when it was changed: the editor sends both back with every save, and one a scrape or a hand edit
    #wrote in some other shape would otherwise stop every other setting of the comic being saved
    found_by = {}
    held = metadata.get("state") or {}
    for key in remembered_paths:
        if key in given and not settings.get("scraper"):
            if str(given[key] or "").strip() == (held.get(key) or ""):
                continue
            try:
                found_by[key] = path_value(given[key])
            except ValueError as error:
                problems.append(str(error))
    if problems:
        return 400, {"error": "; ".join(problems)}
    if expected_updated and metadata.get("updated") != expected_updated:
        return 409, {"error": "the metadata changed since it was opened (a run may have written it). "
                              "Reopen it and make the change again."}

    changed = {key: [settings.get(key), value] for key, value in cleaned.items() if settings.get(key) != value}
    state = dict(metadata.get("state") or {})
    changed.update((key, [state.get(key), value]) for key, value in found_by.items() if state.get(key) != value)
    if own:
        was = dict(settings.get("plugin") or {})
        changed.update(("plugin." + key, [was.get(key), value]) for key, value in own.items() if was.get(key) != value)
        was.update(own)
        cleaned["plugin"] = was

    #the chapter list is not a scraping setting, so it lives beside them rather than among them
    listing = given.get("chapters_url")
    every = given.get("chapters_every")
    if every is not None:
        every = str(every).strip()
        if every and not re.match(r"^\d+$", every):
            return 400, {"error": "pages per part has to be a whole number, or blank for none"}
        every = int(every or 0) or None
        if every and listing and str(listing).strip():
            #two sources would each save over the other's chapters on every run
            return 400, {"error": "a comic's chapters come from its archive page or from cutting it every so "
                                  "many pages, not both; clear one of them"}
        block = metadata.get("chapters") or {}
        if block.get("every") != every:
            changed["chapters_every"] = [block.get("every"), every]
            if every:
                block["source"], block["every"] = "every", every
                block.setdefault("list", [])
                metadata["chapters"] = block
            elif block.get("list"):
                #the parts already worked out stay as they are until something else is worked out
                block.pop("every", None)
                metadata["chapters"] = block
            else:
                metadata.pop("chapters", None)
    if listing is not None:
        listing = str(listing).strip()
        if listing and not re.match(r"^https?://\S+$", listing):
            return 400, {"error": "the chapter list has to be a full http(s) address"}
        block = metadata.get("chapters") or {}
        if (block.get("source_url") or "") != listing:
            changed["chapters"] = [block.get("source_url"), listing or None]
            if listing:
                block["source"], block["source_url"] = "archive", listing
                block.setdefault("list", [])
                metadata["chapters"] = block
            elif block.get("list") or block.get("every"):
                block["source_url"] = None
                metadata["chapters"] = block
            else:
                metadata.pop("chapters", None)

    if not changed:
        return 200, {"saved": False, "message": "nothing changed"}
    settings.update(cleaned)
    #neither is kept empty: a comic without its own is a comic that never had any
    for key in ("cookies", "user_agent", "placeholders"):
        if key in settings and not settings[key]:
            del settings[key]
    metadata["settings"] = settings
    if any(state.get(key) != value for key, value in found_by.items()):
        state.update(found_by)
        metadata["state"] = state
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata["updated"] = stamp
    history = metadata.setdefault("history", {})
    history["edits"] = (history.get("edits") or [])[-(max_edits - 1):] + [{"at": stamp, "changed": changed}]

    #written beside the real file and swapped in, so a crash part way never leaves half a metadata file
    write_json(path, metadata)
    print("Edited {0}: {1}".format(comic.name, ", ".join(
        "{0} {1} -> {2}".format(key, json.dumps(old), json.dumps(new)) for key, (old, new) in changed.items())),
        flush=True)
    return 200, {"saved": True, "changed": changed, "updated": stamp}


def comicinfo_view(args, uc, runner, name):
    #what a comic's archives say it is: what was said by hand, kept in its metadata's info block, and what
    #each box means left empty - worked out from the comic, and from what its plugin's program said of it
    comic = find_comic(args, uc, name)
    if comic is None:
        return 404, {"error": "no comic named {0}".format(name)}
    try:
        metadata = read_metadata(os.path.join(comic.folder, uc.metadata_file))
    except (OSError, ValueError) as error:
        return 500, {"error": "could not read {0}'s metadata: {1}".format(name, error)}
    chapters = metadata.get("chapters") or {}
    return 200, {"name": comic.name, "updated": metadata.get("updated"), "said": metadata.get("info") or {},
                 "worked": comicinfo.said_by(comicinfo.about_comic(comic.folder, dict(metadata, info=None))),
                 #a comic in chapters has each chapter's title and address said by the chapter
                 "chapters": len(chapters.get("list") or []) if chapters.get("folder") else 0,
                 "cbz": (metadata.get("settings") or {}).get("cbz") is not False,
                 "form": comicinfo.form()}


def save_comicinfo(args, uc, runner, name, said, expected_updated):
    #the nine are always on the form, so one left out is one emptied; the rest of the schema changes only
    #where it is named, "" taking it out, as on the reader's info page
    comic = find_comic(args, uc, name)
    if comic is None:
        return 404, {"error": "no comic named {0}".format(name)}, None
    if is_running(runner, comic.name):
        return 409, {"error": "{0} is being scraped right now; stop it or wait for it to finish".format(name)}, None
    if is_moving(runner, comic.name):
        return 409, {"error": "{0} is being moved; reopen it once the move has finished".format(name)}, None
    if not isinstance(said, dict):
        return 400, {"error": "say what the comic is as an object of fields"}, None
    problems = comicinfo.unsayable(said)
    if problems:
        return 400, {"error": "; ".join(problems)}, None
    path = os.path.join(comic.folder, uc.metadata_file)
    try:
        metadata = read_metadata(path)
    except (OSError, ValueError) as error:
        return 500, {"error": "could not read {0}: {1}".format(path, error)}, None
    if expected_updated and metadata.get("updated") != expected_updated:
        return 409, {"error": "the metadata changed since it was opened (a run may have written it). "
                              "Reopen it and make the change again."}, None
    named = comicinfo.INFO + tuple(tag for tag in comicinfo.EXTRA if tag in said)
    old = comicinfo.clean_info(metadata.get("info"))
    info = comicinfo.clean_info(dict({key: value for key, value in old.items() if key not in named},
                                     **comicinfo.clean_info(said)))
    changed = {"info." + key: [old.get(key), info.get(key)] for key in sorted(set(old) | set(info))
               if old.get(key) != info.get(key)}
    if not changed:
        return 200, {"saved": False, "updated": metadata.get("updated")}, comic
    if info:
        metadata["info"] = info
    else:
        metadata.pop("info", None)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata["updated"] = stamp
    history = metadata.setdefault("history", {})
    history["edits"] = (history.get("edits") or [])[-(max_edits - 1):] + [{"at": stamp, "changed": changed}]
    write_json(path, metadata)
    print("Edited {0}'s ComicInfo: {1}".format(comic.name, ", ".join(
        "{0} {1} -> {2}".format(key, json.dumps(was), json.dumps(now)) for key, (was, now) in changed.items())),
        flush=True)
    return 200, {"saved": True, "changed": changed, "updated": stamp}, comic


def save_config(args, uc, given):
    #only the settings that are known, so the file cannot fill up with things nothing reads
    saved, problems = {}, []
    for key, fallback in uc.config_defaults.items():
        if key not in given:
            continue
        value = given[key]
        if key == "add_defaults" and isinstance(value, dict):
            saved[key] = {name: value.get(name, default) for name, default in fallback.items()}
        elif key in ("pages_folder", "cbz_folder"):
            folder = clean_folder(str(value or ""))
            if folder is None:
                problems.append("{0} has to be a folder inside the library".format(key))
            else:
                saved[key] = folder
        elif key == "schedule":
            text = str(value or "").strip()
            if text:
                try:
                    uc.parse_schedule(text)
                except ValueError:
                    problems.append("the schedule wants a 24 hour time like 03:30")
            saved[key] = text or None
        elif key == "user_agent":
            try:
                saved[key] = useragent.clean(value)
            except ValueError as error:
                problems.append(str(error))
        else:
            try:
                number = int(value)
                if number < 0:
                    raise ValueError
                saved[key] = number
            except (TypeError, ValueError):
                problems.append("{0} has to be a whole number, 0 or more".format(key))
    if saved.get("jobs") == 0:
        problems.append("jobs has to be at least 1")
    if problems:
        return 400, {"error": "; ".join(problems)}
    try:
        write_json(uc.config_path(), saved)
    except OSError as error:
        return 500, {"error": "could not write {0}: {1}".format(uc.config_path(), error)}
    print("Saved {0}".format(uc.config_path()), flush=True)
    return 200, {"saved": True, "path": uc.config_path(), "settings": uc.load_config(quiet=True)}


def preview_move(args, comic, into):
    #what moving a comic would do, said before anything is queued: a few looks at the share, no listing, so
    #it answers at once. the job plans it again when its turn comes, in case the library changed meanwhile
    try:
        planned = moving.plan(comic.folder, args.root, into, args.max_depth)
    except (moving.Refused, OSError, ValueError) as error:
        return 400, {"error": str(error)}
    return 200, {"to": planned["to"],
                 "lines": [{"text": text, "stays": stays} for text, stays in moving.describe(planned)]}


def discard_walk(args, uc, comic):
    #a walk that never got past the comic's first page - begun on its newest, say, by a site whose
    #first-page link leads there - leaves a record of one page and an alignment made from it, which cutting
    #by size goes by ahead of the file numbers. renamed aside, not deleted, and only a record that says
    #nothing: one that covers the comic is an hour of walking, which no button should throw away
    if walk_needed(args, uc, comic) != "start":
        return 409, {"error": "that comic's record of which page is which is not a failed walk, so it is kept"}
    moved = set_aside(index_path(comic.folder, args.root))
    if not moved:
        return 404, {"error": "there is no record of a walk for that comic to discard"}
    for old, new in moved:
        print("{0}: moved {1} aside as {2}, as asked".format(comic.name, os.path.basename(old),
                                                             os.path.basename(new)), flush=True)
    return 200, {"moved": [os.path.basename(new) for _, new in moved]}
