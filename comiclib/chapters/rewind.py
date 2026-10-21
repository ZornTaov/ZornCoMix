#going back: a comic's pages from one page on taken off, and everything that says where its scrape is up to
#put back to before them - the resume point, the record of which page is which and its alignment, the
#chapters and their archives - so the next update fetches them again. for a run that saved the wrong picture
#page after page, a site's user icon say, or followed the wrong next link: the path is put right, the comic
#taken back to before the run, and updated again. nothing is deleted. the pages and any archive no chapter
#is left for go into the comic's set-aside folder, and the record and alignment are copied aside first
import json
import os
import shutil
from datetime import datetime

from comiclib.chapters.index import (aside_target, alignment_path, counted_from_nought, index_path,
                                     numbered_files, read_index, write_lines)
from comiclib.chapters.links import same_page
from comiclib.chapters.numbering import numbered
from comiclib.chapters.packing import COVER_ENDINGS, chapter_file, chapter_folder, pack, repack
from comiclib.metadata import METADATA_FILE, now_stamp, read as read_metadata, write as write_metadata, write_json
from comiclib.pages import page_number

#as many as the web page keeps of a comic's edits, and of the go-backs themselves
kept_edits = 50
kept_rewinds = 20


class Refused(Exception):
    #going back cannot be done as asked, and why, in words that say what to do instead
    pass


def address_of(n, lines, runs, history):
    #where page n is, from what is sure of it: the record of which page is which, the address a run was told
    #to start from - its own command - or the comic's first page. not where a run ended: a run stuck on one
    #address, saving its pictures under number after number, ended "at" a page it never reached
    for line in lines:
        if line.get("n") == n and line.get("url"):
            return line["url"]
    for run in reversed(runs):
        if run.get("start_page_number") == n and run.get("start_url"):
            return run["start_url"]
    if n == (history.get("first_page_number") or 1) and history.get("first_page_url"):
        return history["first_page_url"]
    return None


def plan(folder, args):
    #everything going back would do, worked out and nothing changed: what a dry run says, and the page shows
    #before anything is done. raises Refused when it cannot be done as asked
    metadata = read_metadata(folder)
    if not metadata:
        raise Refused("{0} has no metadata, so there is nothing to go back in.".format(folder))
    settings = metadata.get("settings") or {}
    if settings.get("scraper"):
        raise Refused("{0} is scraped by the {1} plugin, whose program keeps where it is up to itself; going "
                      "back is for a comic mirror_base scrapes.".format(folder, settings["scraper"]))
    history = metadata.get("history") or {}
    runs = history.get("runs") or []
    run = None
    if getattr(args, "run", None):
        run = next((held for held in runs if held.get("run_id") == args.run), None)
        if run is None:
            raise Refused("{0} has no run {1} in its history.".format(folder, args.run))
        start, url = run.get("start_page_number"), run.get("start_url")
        if not start or not url:
            raise Refused("that run did not record where it started; go back to a page by its number instead.")
    else:
        start, url = getattr(args, "from_page", None), getattr(args, "url", None)
        if not start or start < 1:
            raise Refused("say which page to go back to, with --from: that page and every one after it are "
                          "taken off, and the next update starts there.")

    cache = index_path(folder, args.root, args)
    lines = read_index(cache) if os.path.exists(cache) else []
    alignment = alignment_path(cache)
    aligned = None
    if os.path.exists(alignment):
        with open(alignment, encoding="utf-8") as f:
            aligned = json.load(f)

    #which page each file is: the alignment where it places a file, which can differ from the number in its
    #name - a page put in by hand, an alignment made by hand - and otherwise the number its name carries
    names, by_number, _ = numbered_files(folder)
    shift = counted_from_nought(by_number)
    placed = {page["file"]: page["n"] for page in (aligned or {}).get("pages") or [] if page.get("file")}
    page_of = {}
    for name in names:
        if name in placed:
            page_of[name] = placed[name]
        elif page_number(name) is not None:
            page_of[name] = page_number(name) + shift
    unplaced = [name for name in names if name not in page_of]
    if unplaced:
        raise Refused("{0} file(s) carry no page number and the alignment does not place them, such as {1}, so "
                      "which of them come after page {2} cannot be told. Line the comic up first (chapters.py "
                      "align), then go back.".format(len(unplaced), unplaced[0], start))
    newest = max(page_of.values(), default=0)
    going = sorted((name for name in names if page_of[name] >= start), key=lambda name: (page_of[name], name))
    if not going:
        raise Refused("nothing is held from page {0} on: the newest page {1} has is page {2}.".format(
            start, os.path.basename(folder), newest))

    #where the next update starts: the address given, or page `start` itself, or failing that the page
    #before it, which the update saves again over itself and presses next from - as it does every day. an
    #address holding several pages starts from the first of them, which are saved again under the same names
    if url:
        resume_url, resume_n = url, start
    else:
        resume_url, resume_n = address_of(start, lines, runs, history), start
        if not resume_url and start > 1:
            resume_url, resume_n = address_of(start - 1, lines, runs, history), start - 1
        if not resume_url:
            raise Refused("where page {0} is on the site is not known: the record of which page is which does "
                          "not reach it and no run started there. Give its address with --url.".format(start))
    first_there = min((line["n"] for line in lines
                       if line.get("url") and same_page(line["url"]) == same_page(resume_url)), default=resume_n)
    resume_n = min(resume_n, first_there)

    #a record read from the site's list of posts holds pages no scrape has fetched yet, and its lines past the
    #newest page are the site's, not the run's: it is kept whole, and the next scrape puts each line right as
    #it saves the page. one a scrape wrote as it went is cut back to the page before `start`
    listed_ahead = bool(lines) and lines[-1].get("n", 0) > newest
    cut_lines = [] if listed_ahead else [line for line in lines if line.get("n", 0) >= start]
    cut_aligned = [page for page in (aligned or {}).get("pages") or [] if page["n"] >= start]

    block = metadata.get("chapters") or {}
    chapters = numbered(block) if block.get("list") else []
    dropped = [chapter for chapter in chapters if chapter["start_page"] >= start]
    trimmed = next((chapter for chapter in chapters if chapter["start_page"] < start <= chapter["end_page"]), None)
    archives = []
    if dropped:
        shelf = chapter_folder(folder, metadata, args.root)
        try:
            on_shelf = os.listdir(shelf)
        except OSError:
            on_shelf = []
        for chapter in dropped:
            stem = os.path.splitext(chapter_file(folder, chapter))[0]
            #its archive, and the banner saved beside it as its cover
            archives += [os.path.join(shelf, name) for name in on_shelf
                         if os.path.splitext(name)[0] == stem
                         and (name.endswith(".cbz") or os.path.splitext(name)[1].lower() in COVER_ENDINGS)]
    single = None
    if not chapters and settings.get("cbz") is not False and settings.get("cbz_path"):
        single = settings["cbz_path"]
        if args.root and not os.path.isabs(single):
            single = os.path.join(args.root, single.replace("/", os.sep))
        if not os.path.exists(single):
            single = None

    kept_last = start - 1
    last_file = max((name for name in names if page_of[name] == kept_last), default=None)
    last_src = next((line.get("src") for line in lines if line.get("n") == kept_last), None)
    return {"folder": folder, "metadata": metadata, "start": start, "newest": newest, "run": run,
            "going": going, "resume_url": resume_url, "resume_n": resume_n,
            "cache": cache if os.path.exists(cache) else None, "lines": lines, "cut_lines": cut_lines,
            "listed_ahead": listed_ahead, "alignment": alignment if aligned else None, "aligned": aligned,
            "cut_aligned": cut_aligned, "chapters": chapters, "dropped": dropped, "trimmed": trimmed,
            "archives": archives, "single": single, "last_file": last_file, "last_src": last_src}


def describe(planned):
    #what going back does, a line for each part, in the words the page shows
    going, start = planned["going"], planned["start"]
    said = ["Going back to page {0} of {1}, whose newest page is {2}{3}:".format(
        start, os.path.basename(planned["folder"]), planned["newest"],
        ", to before the run of {0}".format(planned["run"].get("started")) if planned["run"] else "")]
    said.append("  {0} page(s) set aside, {1}{2}".format(
        len(going), going[0], " to {0}".format(going[-1]) if len(going) > 1 else ""))
    if planned["cut_lines"]:
        said.append("  the record of which page is which cut back to page {0} ({1} line(s) taken off)".format(
            start - 1, len(planned["cut_lines"])))
    elif planned["listed_ahead"]:
        said.append("  the record of which page is which is kept whole: it was read from the site's own list, "
                    "and reaches past the pages held")
    if planned["cut_aligned"]:
        said.append("  the alignment cut back to page {0}".format(start - 1))
    said.append("  the next update starts at {0}, as page {1}".format(planned["resume_url"], planned["resume_n"]))
    trimmed = planned["trimmed"]
    if trimmed:
        said.append("  chapter {0} ({1}) ends at page {2} now, and its archive is written again".format(
            trimmed.get("called") or trimmed["number"], trimmed["label"], start - 1))
    for chapter in planned["dropped"]:
        said.append("  chapter {0} ({1}) starts at page {2} or after, so it is taken out".format(
            chapter.get("called") or chapter["number"], chapter["label"], chapter["start_page"]))
    for path in planned["archives"]:
        said.append("  {0} set aside".format(os.path.basename(path)))
    if planned["single"]:
        said.append("  {0} written afresh from the pages left".format(os.path.basename(planned["single"])))
    return said


def carry_out(planned, args):
    #going back as planned: the pages moved aside, the record and alignment cut back with a copy of each kept
    #beside it, the metadata put back to before them, then the archives. lines saying what was done
    folder, start = planned["folder"], planned["start"]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    done = []
    set_aside = []
    for name in planned["going"]:
        target = aside_target(folder, name)
        os.replace(os.path.join(folder, name), target)
        set_aside.append(os.path.relpath(target, folder).replace(os.sep, "/"))
    done.append("set aside {0} page(s) in {1}".format(len(set_aside), os.path.dirname(set_aside[0])))

    copied = None
    if planned["cache"] and planned["cut_lines"]:
        copied = planned["cache"][:-len(".jsonl")] + ".rewound-{0}.jsonl".format(stamp)
        shutil.copyfile(planned["cache"], copied)
        write_lines(planned["cache"], [line for line in planned["lines"] if line.get("n", 0) < start])
        done.append("cut the record of which page is which back to page {0}; it was {1}".format(
            start - 1, os.path.basename(copied)))
    if planned["alignment"] and planned["cut_aligned"]:
        aligned = planned["aligned"]
        shutil.copyfile(planned["alignment"], alignment_path(copied) if copied
                        else planned["alignment"][:-len(".align.json")] + ".rewound-{0}.align.json".format(stamp))
        if planned["listed_ahead"]:
            #the site's pages past the newest are still the site's; only which file is which goes
            for page in aligned["pages"]:
                if page["n"] >= start:
                    page["file"], page["how"] = None, None
        else:
            aligned["pages"] = [page for page in aligned["pages"] if page["n"] < start]
        write_json(planned["alignment"], aligned, indent=1)
        done.append("cut the alignment back to page {0}".format(start - 1))

    #read again rather than the copy the plan was made from: nothing should have written it since, but a
    #moment-old copy written back would put back anything that had
    metadata = read_metadata(folder)
    settings = metadata.setdefault("settings", {})
    state = metadata.setdefault("state", {})
    history = metadata.setdefault("history", {})
    changed = {"url": [settings.get("url"), planned["resume_url"]],
               "increment": [settings.get("increment"), planned["resume_n"]],
               "pages": [planned["newest"], start - 1]}
    settings["url"], settings["increment"] = planned["resume_url"], planned["resume_n"]
    with os.scandir(folder) as entries:
        state["page_count"] = sum(1 for entry in entries if entry.name != METADATA_FILE and entry.is_file())
    state["last_image_file"] = planned["last_file"]
    state["last_image_url"] = planned["last_src"]
    #a run reaching the newest page is what this says, and the newest page is no longer held
    state["completed"] = False
    block = metadata.get("chapters") or {}
    if planned["dropped"] or planned["trimmed"]:
        kept = []
        for chapter in block.get("list") or []:
            if chapter["start_page"] >= start:
                continue
            if chapter["end_page"] >= start:
                chapter = dict(chapter, end_page=start - 1, pages=start - chapter["start_page"])
            kept.append(chapter)
        block["list"] = kept
    for kind in ("gaps", "hand_made"):
        if isinstance(history.get(kind), list):
            history[kind] = [note for note in history[kind] if (note.get("page") or 0) < start]
    stamp_now = now_stamp()
    metadata["updated"] = stamp_now
    history["edits"] = (history.get("edits") or [])[-(kept_edits - 1):] + [{"at": stamp_now, "changed": changed}]
    history["rewinds"] = (history.get("rewinds") or [])[-(kept_rewinds - 1):] + [{
        "at": stamp_now, "from_page": start, "newest_was": planned["newest"],
        "run": (planned["run"] or {}).get("run_id"), "set_aside": set_aside,
        "archives_set_aside": [os.path.basename(path) for path in planned["archives"]],
        "index_was": os.path.basename(copied) if copied else None}]
    write_metadata(folder, metadata)
    done.append("the next update starts at {0}, as page {1}".format(planned["resume_url"], planned["resume_n"]))

    #archives last: going back is done once the pages and the record agree, and an archive that will not
    #write is said and left for the next pack, which writes whatever differs
    code = 0
    for path in planned["archives"]:
        target = aside_target(folder, os.path.basename(path))
        shutil.move(path, target)
        done.append("set aside {0}".format(os.path.basename(path)))
    #packed whenever it has chapters, not only when one was cut short: pages saved since the chapters were
    #worked out are in the last chapter's archive without being in the list. a pack writes only what differs
    if planned["chapters"] and settings.get("cbz") is not False:
        code = pack(folder, args)
        if code:
            done.append("the chapter archives did not all write; pack the comic again (chapters.py pack)")
    elif planned["single"]:
        args.cbz = planned["single"]
        code = repack(folder, args)
        if code:
            done.append("the archive did not write; repack the comic again (chapters.py repack)")
    return code, done


def rewind(folder, args):
    #chapters.py rewind: going back, said first, and done unless this is a dry run
    try:
        planned = plan(folder, args)
    except (Refused, OSError, ValueError) as error:
        print("ERROR: {0}".format(error))
        return 2
    for line in describe(planned):
        print(line)
    if args.dry_run:
        print("Nothing was changed. Run it again without --dry-run.")
        return 0
    code, done = carry_out(planned, args)
    for line in done:
        print("Done: {0}".format(line))
    return code
