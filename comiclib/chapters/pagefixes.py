#which file is which page, said by hand where the walk and the files cannot settle it between them. kept in
#the comic's metadata, apart from the index and the alignment, because a walk owns the one and every
#alignment works the other out afresh: a correction written into either was gone by the next run. each fix
#names its page by address, which still means the same page after the comic grows or goes back.
#
#  pin    this page is this file, whatever names and sizes say. what a site that serves the page before's
#         picture in a page's slot needs: its size is then a lie about the page, and is not checked
#  drop   this line is not a page - the site showing one twice, or a picture that was never the comic. it
#         keeps its place in the index, since position is meaning there, and holds no file
#  stray  this file is a page the walk never saw, read after the page named. a page the site has lost,
#         found elsewhere, which is what history.recovered says without saying where it goes
import os

from comiclib.chapters.links import same_page
from comiclib.metadata import now_stamp, read as read_metadata, write as write_metadata

KINDS = ("pin", "drop", "stray")


def fixes_in(metadata):
    return [dict(fix) for fix in ((metadata or {}).get("page_fixes") or []) if fix.get("what") in KINDS]


def save_fixes(folder, metadata, fixes):
    if fixes:
        metadata["page_fixes"] = fixes
    else:
        metadata.pop("page_fixes", None)
    write_metadata(folder, metadata)


def where(pages, fix, key="url", number="page"):
    #the places in the index a fix is about. an address holding several pictures has a line for each, and a
    #fix naming one of them says which by its picture; a line with no address - a page the site has lost,
    #written in by hand - can only be named by its number
    url = fix.get(key)
    if url:
        want = same_page(url)
        ats = [at for at, page in enumerate(pages) if page.get("url") and same_page(page["url"]) == want]
        if fix.get("src") and key == "url":
            picture = same_page(fix["src"])
            ats = [at for at in ats if same_page(pages[at].get("src") or "") == picture]
        return ats
    if fix.get(number) is not None:
        return [at for at, page in enumerate(pages) if page.get("n") == fix[number]]
    return []


def plan(pages, files, fixes):
    #what the fixes come to against this index and this folder: the pages dropped, the file each pinned page
    #is, and what could not be done. a fix whose page the index does not hold yet - one made before a
    #rewind, or for a page past where the walk has got to - waits rather than counting against the comic
    dropped, pins, problems, waiting = set(), {}, [], []
    held = set(files)
    for fix in fixes:
        if fix.get("what") != "drop":
            continue
        ats = where(pages, fix)
        if not ats:
            waiting.append(fix)
        dropped.update(ats)
    claimed = {}
    for fix in fixes:
        if fix.get("what") != "pin":
            continue
        ats, name = where(pages, fix), fix.get("file")
        if not ats:
            waiting.append(fix)
            continue
        n = pages[ats[0]]["n"]
        if len(ats) > 1:
            problems.append("page {0}'s address holds {1} pictures, so the pin to {2} does not say which; pin it "
                            "again from the Pages dialog, which names the picture".format(n, len(ats), name))
        elif ats[0] in dropped:
            problems.append("page {0} is both pinned to {1} and dropped as no page; forget one of them".format(
                n, name))
        elif name not in held:
            problems.append("page {0} is pinned to {1}, which is not among this comic's pages here. Put the file "
                            "back, or pin the page to the file it is now".format(n, name))
        elif name in claimed:
            problems.append("{0} is pinned to page {1} and to page {2}; one file is one page".format(
                name, claimed[name], n))
        else:
            claimed[name] = n
            pins[ats[0]] = name
    return {"dropped": dropped, "pins": pins, "problems": problems, "waiting": waiting}


def strays(fixes):
    #the stray files, in the shape history.recovered gives them, so everything that already keeps a page
    #found elsewhere out of the lining up keeps these out too
    return {str(fix["file"]): {"file": fix["file"], "note": fix.get("note") or "put here by hand",
                               "after": fix.get("after"), "after_page": fix.get("after_page")}
            for fix in fixes if fix.get("what") == "stray" and fix.get("file")}


def renamed(metadata, names):
    #a fix names its file, and renumbering or fetching a page again under the site's name renames files
    #under it. told of every rename, it follows; left behind, a pin would name a file that is gone
    count = 0
    for fix in (metadata or {}).get("page_fixes") or []:
        if fix.get("file") in names:
            fix["file"] = names[fix["file"]]
            count += 1
    return count


def moved_along(metadata, at):
    #a page put in at this number moves every page from it on one along. a fix naming its page by address
    #needs nothing; one naming a page that has no address can only name it by number, and that changed
    for fix in (metadata or {}).get("page_fixes") or []:
        for key in ("page", "after_page"):
            if isinstance(fix.get(key), int) and fix[key] >= at:
                fix[key] += 1


def describe_fix(fix, pages):
    ats = where(pages, fix) if fix.get("what") != "stray" else where(pages, fix, "after", "after_page")
    at = "page {0}".format(pages[ats[0]]["n"]) if ats else "page ?"
    if fix.get("what") == "pin":
        return "{0:<11} is {1}".format(at, fix.get("file"))
    if fix.get("what") == "drop":
        return "{0:<11} is not a page".format(at)
    return "{0:<11} is followed by {1}".format(at if (fix.get("after") or fix.get("after_page")) else "(where it sits)",
                                               fix.get("file"))


def page_named(pages, said):
    #a page as the person gave it - its number, or its address - as (index line, address), or (None, why)
    said = str(said or "").strip()
    if said.isdigit():
        page = next((page for page in pages if page.get("n") == int(said)), None)
        if page is None:
            return None, "this comic has no page {0}; its index holds {1}".format(said, len(pages))
        return page, None
    want = same_page(said)
    page = next((page for page in pages if page.get("url") and same_page(page["url"]) == want), None)
    if page is None:
        return None, "{0} is not one of this comic's pages. Give its address, or its page number".format(said)
    return page, None


def edit_page_fixes(folder, args, pages, align_again):
    #the command: say what a page is, take it back, or list what has been said. every change lines the comic
    #up again, since a fix is only worth what the alignment makes of it
    metadata = read_metadata(folder)
    if not metadata:
        print("ERROR: no metadata in {0}.".format(folder))
        return 2
    fixes = fixes_in(metadata)
    if not (args.at or args.file or args.clear):
        print("{0}: {1} page fix(es) by hand".format(folder, len(fixes)))
        for fix in fixes:
            print("  {0}{1}".format(describe_fix(fix, pages), "   " + fix["note"] if fix.get("note") else ""))
        if not fixes:
            print("  none. --at <page> --file <name> pins a page to its file, --at <page> --drop says a line is "
                  "no page, --file <name> --after <page> places a file the walk never saw.")
        return 0
    if args.clear:
        print("forgotten: all {0} page fix(es)".format(len(fixes)))
        fixes = []
    elif args.at:
        page, why = page_named(pages, args.at)
        if page is None:
            print("ERROR: {0}.".format(why))
            return 2
        named = {"url": page["url"]} if page.get("url") else {"page": page["n"]}
        if args.src:
            named["src"] = args.src
        elif page.get("url") and sum(1 for one in pages if one.get("url") == page["url"]) > 1:
            #an address with several pictures: the line asked for by number is the picture meant
            named["src"] = page.get("src")
        about = [fix for fix in fixes if fix.get("what") in ("pin", "drop") and where(pages, fix) == where(pages, named)]
        fixes = [fix for fix in fixes if fix not in about]
        if args.forget:
            print("forgotten: {0} fix(es) about page {1}".format(len(about), page["n"]))
        elif args.drop:
            fixes.append(dict(named, what="drop", made=now_stamp(), **({"note": args.note} if args.note else {})))
            print("noted: page {0} ({1}) is not a page".format(page["n"], page.get("url") or "no address"))
        elif args.file:
            name = os.path.basename(str(args.file))
            if not os.path.exists(os.path.join(folder, name)):
                print("ERROR: {0} is not in {1}. Put the page there first.".format(name, folder))
                return 2
            #a file is one page, so pinning it here takes it off wherever it was pinned before
            fixes = [fix for fix in fixes if not (fix.get("what") == "pin" and fix.get("file") == name)]
            fixes.append(dict(named, what="pin", file=name, made=now_stamp(),
                              **({"note": args.note} if args.note else {})))
            print("noted: page {0} is {1}".format(page["n"], name))
        else:
            print("ERROR: say what page {0} is: --file <name> for the file it is, --drop for no page at all, or "
                  "--forget to take back what was said.".format(page["n"]))
            return 2
    else:
        name = os.path.basename(str(args.file))
        fixes = [fix for fix in fixes if not (fix.get("what") == "stray" and fix.get("file") == name)]
        if args.forget:
            print("forgotten: {0} is no longer placed by hand".format(name))
        else:
            if not os.path.exists(os.path.join(folder, name)):
                print("ERROR: {0} is not in {1}. Put the page there first.".format(name, folder))
                return 2
            made = {"what": "stray", "file": name, "made": now_stamp()}
            if args.after:
                page, why = page_named(pages, args.after)
                if page is None:
                    print("ERROR: {0}.".format(why))
                    return 2
                made.update({"after": page["url"]} if page.get("url") else {"after_page": page["n"]})
            if args.note:
                made["note"] = args.note
            fixes.append(made)
            print("noted: {0} is a page the walk never saw, read {1}".format(
                name, "after page {0}".format(page["n"]) if args.after else "where it sits in the folder"))
    save_fixes(folder, metadata, fixes)
    print()
    return align_again(folder, args)
