# Scraper plugins

A comic another program scrapes has `settings.scraper` (the plugin's folder name in `config/plugins/`) and
`settings.plugin` (its settings; its address is `settings.url`, as every comic's is). `library.resume_argv`
gives `run_plugin.py` just the comic, `batch.program` picks that over `mirror_base` and gives it a
`--deadline` a little inside the batch's timeout - killed by the timeout instead, a long catch-up would be
thrown away every day. The program runs in `<comic>/.plugin-staging/` and what it wrote is taken in after;
a run killed part way leaves it there, and the next run takes in whatever of it is whole first. On Linux
the program shares `run_plugin`'s process group, so the batch's `killpg` takes it too.

Each plugin is the user's own, in its own repository, the program itself usually a submodule in its
`tool/`. Its `plugin.json`'s `id` names its folder - and so every comic's `settings.scraper` - and a folder
of another name is refused rather than guessed at. The web page's Plugins dialog (and `run_plugin.py
--install`/`--update`) clones it with git, which the image carries for this. Its python packages go in
`<plugin>/.venv`, made `--system-site-packages` so the image's selenium is still seen: the config mount
keeps it through a new image, and a stamp written last rebuilds it when the image's python changes. The
plugin's command runs with that venv's python - `{python}`, or a `plugin.py` command starting with
`sys.executable`, which is swapped for it. Nothing apt would install is handled yet, only named in `needs`
and reported missing; that waits for a plugin that needs one. Nothing of a real plugin - nor the site it is for - is named in this repo; `examples/` holds the
generic one. A plugin's `plugin.py` runs only in the process running its comic; the web page reads only its
`plugin.json`. A plugin comic's chapters have `source: "plugin"`: never walked or aligned, packed by its
pages' numbers (`numbered_pages`), the way a comic cut `every` so many pages is.
