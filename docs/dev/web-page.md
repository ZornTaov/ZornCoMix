# The web page

`web_page/` is the page, served file by file by `comiclib/web/server.py`, which hands out only the
`.html`, `.css` and `.js` inside that folder. `index.html` is the markup, every section and dialog;
`css/` is `base` (colours and controls), `page` (the sections), `dialogs`, and `elements` (the element
paths dialog and the check result). `js/` holds one file per part of the page: `common` (`$`, `api`,
`post`, `esc`, the time formats), `library`, `running` (the `/api/state` poll: Running now, queue, Recent,
log), `editor`, `elements`, `listcheck`, `bounds`, `pagefix`, `comicinfo`, `adding`, `uploads`, `settings`,
`plugins` (a plugin's settings as a form), and `main`, which starts it all.

A comic's editor is **one dialog in tabs**: Settings and History are `editor.js`'s own, Chapters is `bounds.js`
(with `edit-chapterize` and the chapter list, which are `editor.js`'s), Pages is `pagefix.js` (which file is
which page, said by hand through `chapters.py pagefix`, and Walk it again), ComicInfo is `comicinfo.js`. A tab's
file puts what it does the first time the tab is shown for a comic into `tabOpeners` as it loads, as a plugin's
`dialog.js` does into `pluginForms`; `showTab` runs it. The editor's foot holds every tab's buttons and message,
each marked with the `data-tabs` it shows on. A new thing done to a comic goes in the tab it is about, not in a
dialog stacked on the editor; only the chapter-list check stays a dialog of its own, since Add comics uses it too.

The scripts are **plain scripts sharing one global scope, not modules**, on purpose: the dialogs hand each other
state (`editing`, `checkJob`, `paths`), and an imported `let` cannot be assigned to. So a top-level name
must be declared in exactly one file, and **only `main.js` may call anything as it loads**, since a
script can then use what a later one declares. The one exception is a plugin's own `dialog.js`, served from
`/plugins/<name>/` and loaded on demand long after `main.js` has run, which registers itself in `pluginForms`
as it loads. A part of the page only the built-in scraper has is marked `builtin-only`, and one only a
plugin comic has `plugin-only`; a `with-plugin` class on the add section or the editor picks which shows. `index.html` loads them in order, `main.js` last. A new
file needs a `<script>` tag there, and a new folder needs its two lines in `.gitignore`.
`tests/web/test_web_status.py` runs the Result column's expression out of `js/library.js` by text, so moving
that expression means moving the test's markers with it.
