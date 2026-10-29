#a small web page for update_comics: watch what a run is doing, start updates, add new comics, stop things.
#standard library only, so the container needs nothing new. started by update_comics.py --web PORT. #V 1.0
#
#the page is the web_page folder; what serves it is in comiclib.web, one module for each part. this is where
#update_comics finds it
from comiclib.web.server import start  # noqa: F401
