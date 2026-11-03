#looking over pages someone else scraped: which folders and archives hold a comic, how its pages are
#numbered, and which archive belongs to which folder.
import os
import re
import zipfile

from comiclib import cbz
from comiclib.chapters.numbering import numbered as numbered_chapters
from comiclib.chapters.packing import chapter_file, chapter_folder, place_file
from comiclib.metadata import METADATA_FILE as metadata_file, read as read_metadata
from comiclib.pages import mac_leftover

page_types = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.avif', '.jxl')

#pages saved with --prefix start with the page number and an underscore; a folder that was renamed by hand
#is usually just the number. anything else carries no number at all.
prefixed = re.compile(r'^(\d+)_')
numbered = re.compile(r'^(\d+)\.')

#a folder's word that what is in it is not to be adopted: comics that have ended, sites that are gone,
#collections of other people's. empty, it is the whole folder; otherwise the files and folders it names, a
#name a line, so one ended comic beside one still going is left out alone
IGNORE_FILE = ".adopt-ignore"
EVERYTHING = "everything"


def ignoring(folder, files):
    #what this folder's .adopt-ignore leaves out: None, EVERYTHING, or a set of names, lower-cased. a line
    #starting # is a note to whoever reads the file
    if IGNORE_FILE not in files:
        return None
    try:
        with open(os.path.join(folder, IGNORE_FILE), encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        #a marker that cannot be read was still put there to say leave this alone
        return EVERYTHING
    names = {line.strip().lower() for line in lines if line.strip() and not line.strip().startswith('#')}
    return names or EVERYTHING


def is_page(name):
    return name.lower().endswith(page_types)


def list_pages(path):
    #the pages in a folder or an archive, ignoring anything that is not an image. folders picked up over
    #the years hold stray files - a copy of the script, a Thumbs.db - that should not count as pages.
    if os.path.isfile(path) and path.lower().endswith('.cbz'):
        with zipfile.ZipFile(path) as zf:
            return sorted(os.path.basename(n) for n in zf.namelist() if is_page(n) and not mac_leftover(n))
    pages = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        pages.extend(f for f in files if is_page(f))
    return sorted(pages)


def pages_in_archives(folder):
    #a comic kept only as .cbz volumes has no loose images. that is fine for one that has finished, and
    #the pages inside the archives are still the honest count.
    found = []
    if not os.path.isdir(folder):
        return found
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith('.cbz'):
            try:
                found.extend(list_pages(os.path.join(folder, name)))
            except (zipfile.BadZipFile, OSError):
                pass
    return found


def inspect(pages):
    #works out how the pages are numbered and what the last page number is
    highest, style = None, "unnumbered"
    for name in pages:
        match = prefixed.match(name)
        if match:
            style = "prefixed"
        else:
            match = numbered.match(name)
            if match and style != "prefixed":
                style = "numbered"
        if match:
            value = int(match.group(1))
            highest = value if highest is None else max(highest, value)
    return {"count": len(pages), "last_number": highest, "style": style}


def comic_folder(path):
    #a .cbz on its own still needs a folder to hold its metadata and receive new pages
    if os.path.isfile(path) and path.lower().endswith('.cbz'):
        return path[:-4]
    return path.rstrip('/\\')


def relative_output(folder, root):
    rel = os.path.relpath(os.path.abspath(folder), os.path.abspath(root))
    return rel.replace(os.sep, '/')


def survey(root, show_all=False):
    #lists folders and archives that hold pages but have no metadata yet, so a migration can be worked
    #through without hunting for what is left
    folders, archives, adopted, ignored = [], [], [], []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.'))
        if metadata_file in files:
            dirs[:] = [] #a comic already; nothing below it is a separate one
            adopted.append(current)
            if show_all:
                folders.append([current, "adopted", None, 0])
            continue
        #left out as an .adopt-ignore says, and listed only with --all, to show what the marker is hiding
        told = ignoring(current, files)
        if told == EVERYTHING:
            dirs[:] = []
            ignored.append([current, "ignored", None, 0])
            continue
        if told:
            ignored.extend([os.path.join(current, name), "ignored", None, 0]
                           for name in sorted(dirs + files) if name.lower() in told)
            dirs[:] = [d for d in dirs if d.lower() not in told]
            files = [f for f in files if f.lower() not in told]
        #a folder whose only pictures are the covers a reader put on the shelf - cover.jpg, MyComic.jpg beside
        #MyComic.cbz - is no comic. one with pages besides counts all of them: a scrape packs a cover.jpg among
        #its pages as a page, and a comic's first page is often called just that
        stems = cbz.archive_stems(files)
        pages = [f for f in files if is_page(f)]
        if all(cbz.is_cover(f, stems) for f in pages):
            pages = []
        if pages:
            folders.append([current, "folder", inspect(sorted(pages)), 0])
        for name in sorted(files):
            if not name.lower().endswith('.cbz') or os.path.isdir(os.path.join(current, name[:-4])):
                continue #a .cbz beside its own folder is the same comic, so only the folder is listed
            path = os.path.join(current, name)
            try:
                archives.append([path, "cbz", inspect(list_pages(path)), 0])
            except (zipfile.BadZipFile, OSError) as error:
                archives.append([path, "unreadable: {0}".format(error), None, 0])

    #a site mirror or a comic with chapter folders shows up as dozens of nested hits. only the outermost
    #is worth listing, with a note of how much sits beneath it, since that is the folder to adopt.
    tops = []
    for row in folders:
        parent = next((t for t in tops if row[0].startswith(t[0] + os.sep)), None)
        if parent is None:
            tops.append(row)
        else:
            parent[3] += 1

    #the archives an adopted comic has packed are its own, wherever its settings put them, and a comic packed
    #a chapter at a time has a shelf folder of them with no metadata in it to say so
    owned = set()
    for folder in adopted:
        owned.update(owned_archives(folder, root))
    archives = [a for a in archives if same_path(a[0]) not in owned]

    #an archive whose pages sit in a folder elsewhere in the library is that same comic, not another one.
    #it is dropped here and named in the folder's cbz_path instead, so each comic is one row.
    #comics that are already adopted still own their archive, so it must not come back as a candidate
    folder_paths = [row[0] for row in tops] + adopted
    folder_names = set()
    for folder in folder_paths:
        folder_names.update(comic_names(folder, root, folder_paths))
    archives = [a for a in archives if os.path.basename(a[0])[:-4].lower() not in folder_names]

    #archives sitting together in a sub folder are ambiguous: volumes of one comic, chapters, or a set of
    #separate comics filed under an author. that is one decision to look at rather than one row per file.
    #archives at the top of the library are listed individually, since there each one is its own comic.
    if not show_all:
        root_dir = os.path.abspath(root)
        grouped, singles = {}, []
        for row in archives:
            parent = os.path.dirname(row[0])
            siblings = [a[0] for a in archives if os.path.dirname(a[0]) == parent]
            if len(siblings) < 2 or os.path.abspath(parent) == root_dir or not one_comic_split_up(siblings):
                singles.append(row)
                continue
            if parent not in grouped:
                grouped[parent] = [parent, "cbz x", {"count": 0, "last_number": None,
                                                     "style": "look inside"}, 0]
            grouped[parent][2]["count"] += (row[2] or {}).get("count", 0)
            grouped[parent][3] += 1
        archives = sorted(singles) + [grouped[k] for k in sorted(grouped)]

    return (folders if show_all else tops) + archives + (ignored if show_all else [])


def same_path(path):
    return os.path.normcase(os.path.abspath(path))


def owned_archives(folder, root):
    #where an adopted comic keeps its archives: its one archive, where its settings name it or where packing
    #files one when they name none, and each chapter's, by the very name packing gives it - by its own number,
    #or by its place as it was named before - so anything else in a chapter folder, an archive from before
    #the comic was adopted, is still listed
    metadata = read_metadata(folder) or {}
    settings = metadata.get("settings") or {}
    if settings.get("cbz") is False:
        return set()
    found = {cbz.resolved(settings.get("cbz_path"), folder, root) or cbz.default_path(folder)}
    block = metadata.get("chapters") or {}
    if block.get("list"):
        shelf = chapter_folder(folder, metadata, root)
        for chapter in numbered_chapters(block):
            found.update(os.path.join(shelf, name) for name in (chapter_file(folder, chapter),
                                                                place_file(folder, chapter)))
    return {same_path(path) for path in found}


def every_archive(root):
    #every .cbz in the library, so a folder can be matched to the archive it belongs to even when the two
    #live in different trees
    found = {}
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for name in files:
            if name.lower().endswith('.cbz'):
                found.setdefault(name[:-4].lower(), []).append(os.path.join(current, name))
    return found


def one_comic_split_up(paths):
    #volumes or chapters of a single comic share their name - "My Comic 04", "Ch.12", "001". a folder of
    #separate comics filed under an author or a site does not. leading numbering is stripped first, so
    #"[3] MyComic - ..." still lines up with "[11] MyComic - ...".
    stems = [re.sub(r'^[\[\(]?\d+[\]\)]?[\s._-]*', '', os.path.basename(p)[:-4]).lower() for p in paths]
    if all(not stem for stem in stems):
        return True #nothing but numbers for names, so they are volumes
    return len(os.path.commonprefix(stems).strip()) >= 3


def comic_names(folder, root, folder_paths):
    #the names an archive for this comic might carry. usually just the folder's own name, but a site mirror
    #keeps its pages somewhere like MyComic/www.example.com, and the archive is named for the folder above.
    #an ancestor holding more than one comic is a grouping folder, not this comic, so the walk stops there.
    names = [os.path.basename(folder).lower()]
    root_abs = os.path.abspath(root)
    current = os.path.dirname(os.path.abspath(folder))
    while current != root_abs and current.startswith(root_abs) and os.path.dirname(current) != current:
        below = sum(1 for p in folder_paths if os.path.abspath(p).startswith(current + os.sep))
        if below > 1:
            break
        names.append(os.path.basename(current).lower())
        current = os.path.dirname(current)
    return names


def matching_archive(folder, root, archives, folder_paths):
    #a library that keeps pages under Uncompressed/ and archives at the top has to be told which is which.
    #the names almost always agree, so that is guessed here and left in the report to be corrected.
    beside = os.path.abspath(folder) + '.cbz'
    for name in comic_names(folder, root, folder_paths):
        for candidate in archives.get(name, []):
            if os.path.abspath(candidate) != beside:
                return relative_output(candidate, root)
    return ""


def loose_pages(folder):
    #only the images sitting directly in the comic's folder. this is what mirror_base packs, so an
    #archive built here holds exactly what a later scrape would have put in it and nothing else
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder)
                  if is_page(name) and os.path.isfile(os.path.join(folder, name)))


def inside(path, folder):
    return os.path.normcase(os.path.abspath(path)).startswith(os.path.normcase(os.path.abspath(folder)) + os.sep)
