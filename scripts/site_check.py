#!/usr/bin/env python3
"""site_check.py - the link and study-shelf gate (run by scripts/ci.sh).

Fails the build when:
  1. an internal link on any built page does not resolve to a file the site
     serves (directly, through cleanUrls, as <dir>/index.html, or through a
     vercel.json redirect whose destination does) - i.e. it would 404. Literal
     href="..." values in assets/js/*.js (the header and drawer menus) are
     checked the same way.
  2. a Study subject's page in one language - the target the menu and the
     /study hub link to - shows no notes while the other edition has some,
     or a study page with no notes is written while its twin has notes.
  3. Devanagari (U+0900-U+097F, except the danda and double danda that
     Gurmukhi text uses as its full stop) appears in a line of Gurmukhi text
     in any source or built text file.

Usage: python3 scripts/site_check.py
"""
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOMAIN_HOSTS = {"houseofaspirants.in", "www.houseofaspirants.in"}
SKIP_DIRS = {".git", "node_modules", "templates", "Claude outputs", "content",
             "__pycache__", ".vercel", ".github"}
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:",
                "intent:", "blob:")

problems = []


def fail(msg):
    problems.append(msg)


# --------------------------------------------------------------- 1. links --
def redirects():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    return {r["source"]: r["destination"] for r in cfg.get("redirects", [])
            if not r.get("has") and ":" not in r["source"] and "(" not in r["source"]}


REDIRECTS = redirects()


def serves(path, hops=0):
    """Does the site answer `/path` (no query, no fragment) with a page?"""
    path = "/" + path.lstrip("/")
    if path == "/":
        return (ROOT / "index.html").is_file()
    if path in REDIRECTS and hops < 5:
        dest = REDIRECTS[path]
        if urlsplit(dest).netloc:
            return True
        return serves(urlsplit(dest).path, hops + 1)
    rel = path.strip("/")
    target = ROOT / rel
    if rel.split("/")[0] in SKIP_DIRS - {"content"}:
        return False
    return (target.is_file() or Path(str(target) + ".html").is_file()
            or (target / "index.html").is_file())


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.base = None
        self.urls = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "base" and a.get("href") is not None:
            self.base = a["href"]
        if tag in ("template",):
            self._skip += 1
        if self._skip:
            return
        for key in ("href", "src"):
            if a.get(key) and tag in ("a", "link", "script", "img", "iframe",
                                      "source", "audio", "video", "area"):
                if tag == "link" and (a.get("rel") or "") in ("preconnect", "dns-prefetch"):
                    continue
                self.urls.append(a[key])

    def handle_endtag(self, tag):
        if tag == "template" and self._skip:
            self._skip -= 1


def html_files():
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP_DIRS or any(x.startswith(".") for x in rel.parts):
            continue
        yield p


def check_url(raw, page_dir, where):
    url = raw.strip()
    if (not url or url.startswith("#") or url.lower().startswith(SKIP_SCHEMES)
            or "${" in url or "{{" in url):
        return
    parts = urlsplit(url)
    if parts.scheme in ("http", "https") or url.startswith("//"):
        if parts.netloc not in DOMAIN_HOSTS:
            return
        path = parts.path
    elif parts.scheme:
        return
    else:
        path = parts.path
        if not path:
            return
        if not path.startswith("/"):
            path = page_dir + path
    # ../ and ./ segments, then the path as the server sees it
    segs = []
    for s in unquote(path).split("/"):
        if s == "..":
            segs = segs[:-1]
        elif s not in (".", ""):
            segs.append(s)
    if not serves("/".join(segs)):
        fail(f"broken link: {where} -> {raw}")


def check_links():
    n = 0
    for p in html_files():
        parser = Links()
        parser.feed(p.read_text(encoding="utf-8", errors="replace"))
        rel_dir = p.relative_to(ROOT).parent.as_posix()
        base = parser.base
        if base is not None:
            page_dir = "/" + base.strip("/") + "/" if base.strip("/") else "/"
        else:
            page_dir = "/" + (rel_dir + "/" if rel_dir != "." else "")
        for url in parser.urls:
            n += 1
            check_url(url, page_dir, p.relative_to(ROOT).as_posix())
    # The menus are written by assets/js/core.js; its literal links are pages too.
    for js in sorted((ROOT / "assets" / "js").glob("*.js")):
        for m in re.finditer(r'href="([\w./?=&#%-]+)"', js.read_text(encoding="utf-8")):
            n += 1
            check_url(m.group(1), "/", f"assets/js/{js.name}")
    return n


# ----------------------------------------------------- 2. empty editions --
EMPTY_MARK = '<div class="empty-state">'


def check_study():
    manifest = json.loads((ROOT / "data" / "study-manifest.json").read_text(encoding="utf-8"))
    for row in manifest.get("subjects", []):
        counts = row.get("counts") or {}
        pages = row.get("pages") or {}
        if not any(counts.values()):
            continue
        for lang in ("en", "pa"):
            page = pages.get(lang, "")
            edition = "pa" if page.startswith("pa/") else "en"
            if not (ROOT / page).is_file():
                fail(f"study: {row['id']} ({lang}) links to {page}, which is not built")
            elif not counts.get(edition):
                fail(f"study: {row['id']} ({lang}) links to {page}, which has 0 notes "
                     f"while the other edition has {sum(counts.values())}")
    for p in html_files():
        rel = p.relative_to(ROOT).as_posix()
        name = rel[3:] if rel.startswith("pa/") else rel
        if not name.startswith("study-"):
            continue
        text = p.read_text(encoding="utf-8")
        if "<body data-study-page " not in text or EMPTY_MARK not in text:
            continue
        twin = ROOT / (name if rel.startswith("pa/") else f"pa/{name}")
        if twin.is_file() and EMPTY_MARK not in twin.read_text(encoding="utf-8"):
            fail(f"study: {rel} shows 0 notes while its twin "
                 f"{twin.relative_to(ROOT).as_posix()} has notes")


# ----------------------------------------------------------- 3. scripts --
DEVANAGARI = re.compile("[ऀ-ॣ०-ॿ]")
GURMUKHI = re.compile("[਀-੿]")
TEXT_EXT = {".html", ".json", ".md", ".js", ".mjs", ".ts", ".py", ".txt", ".xml",
            ".css", ".yml", ".yaml", ".webmanifest", ".sh"}


def check_scripts():
    files = subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, check=True).stdout.decode().split("\0")
    for f in files:
        p = ROOT / f
        if not f or p.suffix.lower() not in TEXT_EXT or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not DEVANAGARI.search(text):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = DEVANAGARI.search(line)
            if m and GURMUKHI.search(line):
                s = max(0, m.start() - 20)
                fail(f"Devanagari inside Gurmukhi text: {f}:{i}: …{line[s:m.end() + 20]}…")


def main():
    n = check_links()
    check_study()
    check_scripts()
    if problems:
        for msg in problems:
            print("  FAIL", msg, file=sys.stderr)
        print(f"site_check: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"  site_check OK ({n} internal links resolve, no empty study edition "
          f"behind a link, no Devanagari in Gurmukhi text)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
