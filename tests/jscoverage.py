#which of the web page's functions the browser tests ever ran, from what MIRROR_JS_COVERAGE=FOLDER had each
#browser test write there:
#
#    MIRROR_JS_COVERAGE=FOLDER python -m pytest tests/web
#    python tests/jscoverage.py FOLDER
#
#chrome measures the page itself, since its scripts are plain files nothing instruments. a function no test ran
#is not always one nothing calls: the page is driven only as far as the tests drive it, so one listed here is a
#question to ask, not something to delete.
import collections
import json
import os
import re
import sys

PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web_page")
#a function as these scripts write one: declared, or a name given an arrow or a function
DECLARED = re.compile(r"^[ \t]*(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(|"
                      r"^[ \t]*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)",
                      re.M)


def page_file(url):
    #the file a script was served from: /js/library.js is web_page/js/library.js
    path = url.split("://", 1)[-1].split("/", 1)[-1].split("?", 1)[0]
    if not path.startswith("js/"):
        return None
    full = os.path.join(PAGE, *path.split("/"))
    return full if os.path.isfile(full) else None


def innermost(ranges, at):
    #what ran at an offset is said by the smallest range holding it: a function's first range is the whole of
    #it, and the blocks inside it - a function nested in it among them - are ranges of their own
    best = None
    for start, end, count in ranges:
        if start <= at < end and (best is None or end - start < best[1] - best[0]):
            best = (start, end, count)
    return best[2] if best else 0


def gather(folder):
    #every run of every script, as the ranges it reported, by file
    runs = collections.defaultdict(list)
    tests = 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            taken = json.load(f)
        tests += 1
        for script in taken["scripts"]:
            full = page_file(script.get("url", ""))
            if full:
                runs[full].append([(r["startOffset"], r["endOffset"], r["count"])
                                   for function in script["functions"] for r in function["ranges"]])
    return runs, tests


def report(folder):
    runs, tests = gather(folder)
    print("{0} browser test(s) measured\n".format(tests))
    every = sorted(os.path.join(PAGE, "js", name) for name in os.listdir(os.path.join(PAGE, "js"))
                   if name.endswith(".js"))
    total_ran = total = 0
    for full in every:
        with open(full, encoding="utf-8", newline="") as f:
            source = f.read()
        found = [(match.start(), match.group(1) or match.group(2)) for match in DECLARED.finditer(source)]
        never = []
        for at, name in found:
            #its body: the first brace or arrow after the name
            body = min([i for i in (source.find("{", at), source.find("=>", at)) if i >= 0] or [at])
            if not any(innermost(ranges, body + 1) > 0 for ranges in runs.get(full, [])):
                never.append((source.count("\n", 0, at) + 1, name))
        ran = len(found) - len(never)
        total_ran, total = total_ran + ran, total + len(found)
        print("{0:<16} {1:>3}/{2:<3} functions ran{3}".format(
            os.path.basename(full), ran, len(found), "" if full in runs else "   (never loaded)"))
        for line, name in never:
            print("    line {0:<5} {1}".format(line, name))
    print("\n{0}/{1} functions ran".format(total_ran, total))


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit("usage: python tests/jscoverage.py FOLDER, the folder MIRROR_JS_COVERAGE named")
    report(sys.argv[1])
