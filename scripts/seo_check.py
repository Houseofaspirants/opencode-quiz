#!/usr/bin/env python3
"""
SEO self-audit for House of Aspirants (houseofaspirants.in).

Run after any head/schema change:      python3 scripts/seo_check.py

Checks static HTML metadata, JSON-LD, image attributes, internal links,
robots.txt and sitemap.xml. Exit code 0 = no hard failures.
Warnings do not fail the run (they are design-accepted items).
"""
import html as html_mod
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "https://houseofaspirants.in"
PAGES = [
    "index.html", "subject.html", "quiz.html", "mock.html", "leaderboard.html",
    "bookmarks.html", "progress.html", "result.html", "about.html",
    "contact.html", "privacy.html", "terms.html", "404.html",
]
REQUIRED_LINKS = [
    'href="index.html"', 'href="index.html#subjects"',
    'href="quiz.html?mode=daily"', 'href="mock.html"',
    'href="bookmarks.html"', 'href="progress.html"', 'href="leaderboard.html"',
    'href="contact.html"', 'href="about.html"', 'href="privacy.html"',
    'href="terms.html"',
]
errors, warnings, notes = [], [], []


def head_of(html: str) -> str:
    m = re.search(r"<head>(.*?)</head>", html, re.S)
    return m.group(1) if m else ""


def meta(html: str, name: str) -> str:
    m = re.search(r'<meta\s+(?:name|property)="%s"\s+content="([^"]*)"' % re.escape(name), head_of(html))
    return m.group(1) if m else ""


def canonical(html: str) -> str:
    m = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', head_of(html))
    return m.group(1) if m else ""


class HeadParser(HTMLParser):
    """Collects tags in <head> only."""
    def __init__(self):
        super().__init__()
        self.in_head = False
        self.tags = []
    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        if self.in_head:
            self.tags.append((tag, dict(attrs)))
    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


titles, descs, cans = {}, {}, {}

for page in PAGES:
    path = ROOT / page
    if not path.exists():
        errors.append(f"{page}: missing file")
        continue
    html = path.read_text(encoding="utf-8")

    # --- title (measured RENDERED, entities unescaped) --------------------
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    title = html_mod.unescape(m.group(1).strip()) if m else ""
    if not title:
        errors.append(f"{page}: no <title>")
    else:
        if len(title) > 60:
            warnings.append(f"{page}: title {len(title)} chars > 60")
        titles.setdefault(title.lower(), []).append(page)

    # --- description ------------------------------------------------------
    desc = html_mod.unescape(meta(html, "description"))
    if not desc:
        errors.append(f"{page}: no meta description")
    else:
        if not (140 <= len(desc) <= 160):
            warnings.append(f"{page}: description {len(desc)} chars outside 140-160")
        descs.setdefault(desc, []).append(page)

    # --- keywords / robots / theme ---------------------------------------
    if not meta(html, "keywords"):
        errors.append(f"{page}: no meta keywords")
    robots = meta(html, "robots")
    if page == "404.html":
        if "noindex" not in robots:
            errors.append(f"404.html: must be noindex (got: {robots!r})")
    else:
        if robots != "index, follow":
            errors.append(f"{page}: robots must be 'index, follow' (got: {robots!r})")

    # --- canonical --------------------------------------------------------
    can = canonical(html)
    if page == "404.html":
        if can:
            errors.append("404.html: must NOT have a canonical")
    else:
        if not can:
            errors.append(f"{page}: no canonical")
        elif not can.startswith(DOMAIN):
            errors.append(f"{page}: canonical off-domain ({can})")
        elif can.endswith(".html"):
            errors.append(f"{page}: canonical must be extensionless ({can})")
        cans.setdefault(can, []).append(page)

    # --- OG + Twitter -----------------------------------------------------
    og_needed = ["og:type", "og:url", "og:site_name", "og:title", "og:description", "og:image", "og:locale"]
    for prop in og_needed:
        if page != "404.html" and not meta(html, prop):
            errors.append(f"{page}: missing {prop}")
    if page != "404.html":
        for prop in ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]:
            if not meta(html, prop):
                errors.append(f"{page}: missing {prop}")
        if meta(html, "og:url") and meta(html, "og:url") != can:
            errors.append(f"{page}: og:url != canonical")
        if meta(html, "og:site_name") != "House of Aspirants":
            errors.append(f"{page}: og:site_name not normalized")

    # --- resource hints ---------------------------------------------------
    if 'rel="preload" href="assets/img/logo-sm.png"' not in head_of(html):
        errors.append(f"{page}: missing header-logo preload")

    # --- render-blocking JS ----------------------------------------------
    p = HeadParser(); p.feed(html)
    for tag, attrs in p.tags:
        if tag == "script" and "src" in attrs and "defer" not in attrs and "async" not in attrs:
            errors.append(f"{page}: render-blocking script {attrs['src']}")

    # --- heading structure (visible main content only) --------------------
    body = html.split("</head>", 1)[-1]
    h1s = re.findall(r"<h1[^>]*>", body)
    if len(h1s) != 1:
        errors.append(f"{page}: {len(h1s)} <h1> tags (must be exactly 1)")

    # --- JSON-LD ----------------------------------------------------------
    for i, block in enumerate(re.findall(
            r'<script type="application/ld\+json"(?: id="[^"]*")?>(.*?)</script>', html, re.S)):
        if not block.strip():
            continue  # runtime-managed placeholder (ldDynamic)
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"{page}: JSON-LD #{i + 1} invalid JSON: {e}")
            continue
        if "@context" not in data:
            errors.append(f"{page}: JSON-LD #{i + 1} missing @context")
        blob = json.dumps(data)
        if ".html" in blob and "item" in blob:
            warnings.append(f"{page}: JSON-LD #{i + 1} references .html URLs")

    # --- image attributes -------------------------------------------------
    for tag in re.findall(r"<img\b[^>]*>", html):
        for attr in ("alt", "width", "height", "decoding"):
            if f'{attr}=' not in tag:
                errors.append(f"{page}: <img> missing {attr}: {tag[:80]}")

# --- cross-page duplicate detection --------------------------------------
for t, pages in titles.items():
    if len(pages) > 1:
        errors.append(f"duplicate title {t!r} on {pages}")
for d, pages in descs.items():
    if len(pages) > 1:
        errors.append(f"duplicate description on {pages}")
for c, pages in cans.items():
    if len(pages) > 1:
        errors.append(f"duplicate canonical {c} on {pages}")

# --- shared chrome: internal link coverage --------------------------------
core = (ROOT / "assets/js/core.js").read_text(encoding="utf-8")
for link in REQUIRED_LINKS:
    if link not in core:
        errors.append(f"footer/nav missing internal link {link}")
# Subjects are emitted from one template + the SUBJECT_LINKS config.
if "subject.html?subject=${" not in core:
    errors.append("footer: subject link template missing")
if '["current-affairs"' not in core and '"current-affairs"' not in core:
    errors.append("footer: Current Affairs subject missing")
if 'href="index.html#subjects">All Subjects' not in core:
    errors.append("footer: All Subjects link must target index.html#subjects")
if 'href="subject.html">' in core:
    errors.append("footer: bare subject.html link (soft-404 target)")

# --- image attributes injected by JS --------------------------------------
for tag in re.findall(r"<img\b[^>]*>", core):
    for attr in ("alt", "width", "height", "decoding"):
        if f"{attr}=" not in tag:
            errors.append(f"core.js <img> missing {attr}: {tag[:80]}")

# --- robots.txt ------------------------------------------------------------
robots_txt = (ROOT / "robots.txt").read_text(encoding="utf-8")
if f"Sitemap: {DOMAIN}/sitemap.xml" not in robots_txt:
    errors.append("robots.txt: sitemap line missing or off-domain")
if "vercel.app" in robots_txt:
    errors.append("robots.txt: vercel.app reference")

# --- sitemap.xml -----------------------------------------------------------
sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
locs = re.findall(r"<loc>(.*?)</loc>", sm)
if not locs:
    errors.append("sitemap.xml: no <loc> entries")
seen = set()
for u in locs:
    if not u.startswith(DOMAIN):
        errors.append(f"sitemap: off-domain URL {u}")
    if u.endswith(".html"):
        errors.append(f"sitemap: extensionless rule broken by {u}")
    if u in seen:
        errors.append(f"sitemap: duplicate URL {u}")
    seen.add(u)
notes.append(f"sitemap: {len(locs)} URLs")

# --- site-wide: no vercel.app anywhere -------------------------------------
for path in ROOT.rglob("*"):
    if path.is_file() and path.suffix in {".html", ".js", ".css", ".json", ".webmanifest", ".txt", ".xml", ".md"} \
            and "node_modules" not in path.parts and ".git" not in path.parts:
        try:
            if "vercel.app" in path.read_text(encoding="utf-8"):
                errors.append(f"vercel.app reference in {path.relative_to(ROOT)}")
        except (UnicodeDecodeError, OSError):
            pass

# --- report ----------------------------------------------------------------
print(f"SEO audit — {DOMAIN}\n" + "=" * 60)
for n in notes:
    print(f"  · {n}")
if warnings:
    print(f"\nWARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  ! {w}")
if errors:
    print(f"\nFAILURES ({len(errors)}):")
    for e in errors:
        print(f"  ✗ {e}")
    print("\nRESULT: FAIL")
    sys.exit(1)
print("\nRESULT: PASS — no hard failures")
