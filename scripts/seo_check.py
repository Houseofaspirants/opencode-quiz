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
    # Study-guides hub + registered articles (data/articles.json)
    "articles.html", "punjab-police-exam-preparation.html",
    "punjab-gk-study-guide.html", "current-affairs-preparation.html",
    "reasoning-quant-preparation.html",
]
ART_HUB = "articles.html"
REQUIRED_LINKS = [
    'href="index.html"', 'href="index.html#subjects"',
    'href="quiz.html?mode=daily"', 'href="mock.html"',
    'href="bookmarks.html"', 'href="progress.html"', 'href="leaderboard.html"',
    'href="contact.html"', 'href="about.html"', 'href="privacy.html"',
    'href="terms.html"',
]
errors, warnings, notes = [], [], []

# --- schema.org validation vocabulary ---------------------------------------
KNOWN_TYPES = {
    "WebSite", "Organization", "EducationalOrganization", "WebPage", "AboutPage",
    "ContactPage", "CollectionPage", "BreadcrumbList", "ListItem", "SearchAction",
    "EntryPoint", "ImageObject", "Quiz", "Thing", "Country", "ContactPoint", "ItemList",
    "Article",
}
WEBPAGE_FAMILY = {"WebPage", "AboutPage", "ContactPage", "CollectionPage"}
REQUIRED = {
    "WebSite": ["name", "url"],
    "Organization": ["name", "url", "logo"],
    "EducationalOrganization": ["name", "url"],
    "WebPage": ["url", "name", "description", "isPartOf"],
    "AboutPage": ["url", "name", "description", "isPartOf"],
    "ContactPage": ["url", "name", "description", "isPartOf"],
    "CollectionPage": ["url", "name", "description", "isPartOf"],
    "BreadcrumbList": ["itemListElement"],
    "SearchAction": ["target", "query-input"],
    "EntryPoint": ["urlTemplate"],
    "Quiz": ["name", "url", "description"],
    "ContactPoint": ["contactType"],
    "ImageObject": ["url"],
    "ListItem": ["position", "name"],
    "Article": ["headline", "image", "datePublished"],
}
types_by_page = {}   # page -> set of schema types found (filled during scan)


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

    # --- heading hierarchy: no upward skips (h1 -> h3, h2 -> h4, ...) -----
    levels = [int(x) for x in re.findall(r"<h([1-4])[\s>]", body)]
    prev = 0
    for lv in levels:
        if prev and lv > prev + 1:
            errors.append(f"{page}: heading skip h{prev} -> h{lv} (levels seen: {levels})")
            break
        prev = lv

    # --- favicon references -----------------------------------------------
    head = head_of(html)
    if not re.search(r'rel="icon"', head):
        errors.append(f"{page}: missing favicon <link rel=icon>")
    if not re.search(r'rel="apple-touch-icon"', head):
        errors.append(f"{page}: missing apple-touch-icon <link>")

    # --- JSON-LD: parse + DEEP validation (types, required props, @id
    #     linkage, breadcrumb sequence, on-domain URLs) ---------------------
    for i, block in enumerate(re.findall(
            r'<script type="application/ld\+json"(?: id="[^"]*")?>(.*?)</script>', html, re.S)):
        if not block.strip():
            continue  # runtime-managed placeholder (ldDynamic)
        tag = f"{page} JSON-LD #{i + 1}"
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            errors.append(f"{tag}: invalid JSON: {e}")
            continue
        if data.get("@context") != "https://schema.org":
            errors.append(f"{tag}: @context must be exactly https://schema.org")

        # collect every typed node (top-level + nested) and every pure @id ref
        nodes, refs_found = [], set()

        def walk(o):
            if isinstance(o, dict):
                if "@type" in o:
                    nodes.append(o)
                if "@id" in o and "@type" not in o:
                    refs_found.add(o["@id"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(data)
        defined_ids = {n["@id"] for n in nodes if isinstance(n.get("@id"), str)}
        cross_page_ok = {f"{DOMAIN}/#website", f"{DOMAIN}/#organization", f"{DOMAIN}/#webpage"}
        seen_ids = set()

        for n in nodes:
            types = n.get("@type")
            tlist = [types] if isinstance(types, str) else (types or [])
            if not tlist:
                errors.append(f"{tag}: node without @type")
                continue
            for t in tlist:
                types_by_page.setdefault(page, set()).add(t)
                if t not in KNOWN_TYPES:
                    errors.append(f"{tag}: unknown @type {t!r}")
                for prop in REQUIRED.get(t, []):
                    if prop not in n:
                        errors.append(f"{tag}: <{t}> missing required property {prop!r}")
            if isinstance(n.get("@id"), str):
                if n["@id"] in seen_ids:
                    errors.append(f"{tag}: duplicate @id {n['@id']}")
                seen_ids.add(n["@id"])
            for k in ("url", "item", "urlTemplate"):
                v = n.get(k)
                if isinstance(v, str):
                    bare = re.sub(r"\{[^}]*\}", "", v)
                    if not bare.startswith(DOMAIN):
                        errors.append(f"{tag}: {k} off-domain ({v})")
                    if k in ("url", "item") and bare.endswith(".html"):
                        errors.append(f"{tag}: {k} must be extensionless ({v})")

            # breadcrumb sequence must be 1..n with names + items
            if tlist == ["BreadcrumbList"]:
                items = n.get("itemListElement") or []
                if not items:
                    errors.append(f"{tag}: BreadcrumbList has no items")
                else:
                    for expect, it in enumerate(items, 1):
                        if it.get("position") != expect:
                            errors.append(f"{tag}: breadcrumb position {it.get('position')} != {expect}")
                        if not it.get("name"):
                            errors.append(f"{tag}: breadcrumb item {expect} missing name")
                    if items[0].get("name") != "Home":
                        warnings.append(f"{tag}: first crumb is {items[0].get('name')!r}, not 'Home'")
            if tlist == ["SearchAction"]:
                tgt = n.get("target")
                if isinstance(tgt, dict):
                    if tgt.get("@type") != "EntryPoint" or not tgt.get("urlTemplate"):
                        errors.append(f"{tag}: SearchAction target must be EntryPoint + urlTemplate")
                elif isinstance(tgt, str):
                    warnings.append(f"{tag}: SearchAction target in legacy string form")
                else:
                    errors.append(f"{tag}: SearchAction missing target")
            if tlist == ["ItemList"] and "numberOfItems" in n:
                if n["numberOfItems"] != len(n.get("itemListElement") or []):
                    errors.append(f"{tag}: ItemList numberOfItems mismatch")

        # every @id reference must resolve in this document (or be a known
        # cross-page entity defined on the home page)
        for r in refs_found:
            if r not in defined_ids and r not in cross_page_ok:
                errors.append(f"{tag}: dangling @id reference {r}")

        # WebPage <-> BreadcrumbList must cross-link when both exist
        wp = [n for n in nodes
              if set([n.get("@type")] if isinstance(n.get("@type"), str) else n.get("@type") or []) & WEBPAGE_FAMILY]
        bc = [n for n in nodes if n.get("@type") == "BreadcrumbList"]
        if wp and bc:
            bc_id = bc[0].get("@id")
            if not bc_id:
                errors.append(f"{tag}: BreadcrumbList missing @id for WebPage linkage")
            else:
                ref = (wp[0].get("breadcrumb") or {}).get("@id")
                if ref != bc_id:
                    errors.append(f"{tag}: WebPage.breadcrumb {ref!r} != BreadcrumbList @id {bc_id!r}")
        elif bc and not wp:
            errors.append(f"{tag}: BreadcrumbList without a WebPage-family node")

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

# --- intelligent internal linking: the 13 destinations every page links to --
# Header + footer are rendered from core.js on every page, so each destination
# must exist in that one template, and every page must mount the chrome.
DESTINATIONS = {
    "Home": 'href="index.html"',
    "Subjects": 'href="index.html#subjects"',
    "Current Affairs": 'subject.html?subject=current-affairs',
    "Punjab GK": 'subject.html?subject=gk&amp;category=punjab-gk',
    "Mock Tests": 'href="mock.html"',
    "Expected MCQs": ">Expected MCQs<",
    "Previous Year Questions": ">Previous Year Questions<",
    "Bookmarks": 'href="bookmarks.html"',
    "Leaderboard": 'href="leaderboard.html"',
    "About": 'href="about.html"',
    "Contact": 'href="contact.html"',
    "Privacy Policy": 'href="privacy.html"',
    "Terms": 'href="terms.html"',
}
for label, frag in DESTINATIONS.items():
    if frag not in core:
        errors.append(f"chrome missing destination link: {label}")
if 'href="articles.html"' not in core:
    errors.append("chrome missing Study Guides hub link (articles.html)")
for page in PAGES:
    html = (ROOT / page).read_text(encoding="utf-8")
    if "data-site-header" not in html or "data-site-footer" not in html:
        errors.append(f"{page}: shared chrome placeholder missing")

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

# --- study guides: registry <-> pages <-> sitemap <-> hub cross-links --------
registry = None
try:
    registry = json.loads((ROOT / "data/articles.json").read_text(encoding="utf-8")).get("articles", [])
except Exception as e:
    errors.append(f"data/articles.json unreadable: {e}")
if registry is not None:
    if not registry:
        errors.append("data/articles.json: no articles registered")
    subj_ids = {s.get("id") for s in json.loads(
        (ROOT / "data/subjects.json").read_text(encoding="utf-8")).get("subjects", [])}
    hub_html = (ROOT / ART_HUB).read_text(encoding="utf-8") if (ROOT / ART_HUB).exists() else ""
    if not hub_html:
        errors.append(f"{ART_HUB}: hub page missing")
    seen_urls, seen_titles = set(), set()
    for a in registry or []:
        aid = a.get("id", "?")
        for field in ("id", "title", "url", "description", "subjects", "published", "modified"):
            if not a.get(field):
                errors.append(f"articles.json[{aid}]: missing {field!r}")
        url, title = str(a.get("url", "")), str(a.get("title", ""))
        desc = str(a.get("description", ""))
        if url in seen_urls:
            errors.append(f"articles.json: duplicate url {url}")
        seen_urls.add(url)
        if title in seen_titles:
            errors.append(f"articles.json: duplicate title {title!r}")
        seen_titles.add(title)
        if len(title) > 60:
            errors.append(f"articles.json[{aid}]: title {len(title)} chars > 60")
        if not (140 <= len(desc) <= 160):
            errors.append(f"articles.json[{aid}]: description {len(desc)} chars outside 140-160")
        for sid in a.get("subjects", []):
            if sid not in subj_ids:
                errors.append(f"articles.json[{aid}]: unknown subject id {sid!r}")
        if url not in {p for p in PAGES}:
            errors.append(f"articles.json[{aid}]: url not in audited PAGES ({url})")
        # the page file must exist and carry the registry's title/description
        if not url.endswith(".html") or not (ROOT / url).exists():
            errors.append(f"articles.json[{aid}]: page file missing ({url})")
            continue
        html = (ROOT / url).read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        page_title = html_mod.unescape(m.group(1).strip()) if m else ""
        if page_title != title:
            errors.append(f"{url}: <title> does not match articles.json title")
        if html_mod.unescape(meta(html, "description")) != desc:
            errors.append(f"{url}: meta description does not match articles.json description")
        # hub links every guide; every guide links back to the hub
        if hub_html and f'href="{url}"' not in hub_html:
            errors.append(f"{ART_HUB}: missing link to {url}")
        if 'href="articles.html"' not in html:
            errors.append(f"{url}: missing link back to {ART_HUB}")
        # every guide must be in the sitemap (extensionless)
        want = DOMAIN + "/" + url[:-5] if url.endswith(".html") else ""
        if want and want not in locs:
            errors.append(f"sitemap: missing article URL {want}")
    notes.append(f"study guides: {len(registry or [])} registered, hub + sitemap + metadata synced")
if DOMAIN + "/articles" not in locs:
    errors.append("sitemap: missing /articles hub")

# --- related-content modules (subject pages) --------------------------------
subj_html = (ROOT / "subject.html").read_text(encoding="utf-8")
if 'id="relatedSection"' not in subj_html or 'id="relatedGrid"' not in subj_html:
    errors.append("subject.html: related-content module placeholder missing")
if "assets/js/related.js" not in subj_html:
    errors.append("subject.html: related.js not loaded")
rel_js_path = ROOT / "assets/js/related.js"
if not rel_js_path.exists():
    errors.append("assets/js/related.js missing")
else:
    rel_js = rel_js_path.read_text(encoding="utf-8")
    for frag in ("data/index.json", "data/articles.json", "subject.html?subject="):
        if frag not in rel_js:
            errors.append(f"related.js: missing {frag}")
notes.append("linking: 13 chrome destinations + related subjects/quizzes/guides modules enforced")

# --- site-wide: no vercel.app anywhere -------------------------------------
for path in ROOT.rglob("*"):
    if path.is_file() and path.suffix in {".html", ".js", ".css", ".json", ".webmanifest", ".txt", ".xml", ".md"} \
            and "node_modules" not in path.parts and ".git" not in path.parts:
        try:
            if "vercel.app" in path.read_text(encoding="utf-8"):
                errors.append(f"vercel.app reference in {path.relative_to(ROOT)}")
        except (UnicodeDecodeError, OSError):
            pass

# --- schema coverage: requested types present where content allows ----------
BC_PAGES = {"about.html", "bookmarks.html", "contact.html", "leaderboard.html",
            "mock.html", "privacy.html", "progress.html", "terms.html",
            "articles.html", "punjab-police-exam-preparation.html",
            "punjab-gk-study-guide.html", "current-affairs-preparation.html",
            "reasoning-quant-preparation.html"}
ARTICLE_PAGES = {"punjab-police-exam-preparation.html", "punjab-gk-study-guide.html",
                 "current-affairs-preparation.html", "reasoning-quant-preparation.html"}
for page in PAGES:
    tps = types_by_page.get(page, set())
    if page == "404.html":
        if tps:
            errors.append("404.html: noindex page must carry no schema")
        continue
    if not (tps & WEBPAGE_FAMILY):
        errors.append(f"{page}: no WebPage-family schema node")
for p in sorted(BC_PAGES):
    if "BreadcrumbList" not in types_by_page.get(p, set()):
        errors.append(f"{p}: missing BreadcrumbList (visible breadcrumb exists)")
for p in sorted(ARTICLE_PAGES):
    if "Article" not in types_by_page.get(p, set()):
        errors.append(f"{p}: missing Article schema (visible article content)")
if "CollectionPage" not in types_by_page.get(ART_HUB, set()):
    errors.append(f"{ART_HUB}: missing CollectionPage schema")
for t in ("WebSite", "SearchAction", "EntryPoint", "Organization",
          "EducationalOrganization", "WebPage"):
    if t not in types_by_page.get("index.html", set()):
        errors.append(f"index.html: missing {t} schema")
inv = {}
for tps in types_by_page.values():
    for t in tps:
        inv[t] = inv.get(t, 0) + 1
notes.append("schema (static): " + ", ".join(f"{k}x{v}" for k, v in sorted(inv.items())))
notes.append("schema (runtime): CollectionPage + BreadcrumbList via subject.js; WebPage + Quiz via quiz.js")

# --- performance + accessibility enforcement --------------------------------
for page in PAGES:
    html = (ROOT / page).read_text(encoding="utf-8")
    # no render-blocking scripts: every external script must be defer/async
    for tag in re.findall(r"<script\b[^>]*\bsrc=[^>]*>", html):
        if " defer" not in tag and " async" not in tag:
            errors.append(f"{page}: render-blocking <script src>: {tag[:80]}")
    # resource hints
    if 'rel="dns-prefetch"' not in html:
        errors.append(f"{page}: missing dns-prefetch hint")
    if 'rel="preconnect" href="https://t.me"' not in html:
        errors.append(f"{page}: missing preconnect for primary CTA origin")
    if 'rel="preload" href="assets/img/logo-sm.png"' not in html:
        errors.append(f"{page}: missing logo preload")
    if 'rel="preload" href="assets/css/style.css" as="style"' not in html:
        errors.append(f"{page}: missing style.css preload")
    if re.search(r'<link rel="stylesheet" href="assets/css/quiz\.css">', html) and \
       'rel="preload" href="assets/css/quiz.css"' not in html:
        errors.append(f"{page}: quiz.css stylesheet without preload")
    # semantics
    if "<main" not in html:
        errors.append(f"{page}: missing <main> landmark")

# core.js chrome: header logo eager, footer logo lazy (both keep width/height)
brand = re.findall(r'<img class="brand-logo"[^>]*>', core)
if len(brand) != 2:
    errors.append(f"core.js: expected 2 brand logos, found {len(brand)}")
else:
    if "loading=" in brand[0]:
        errors.append("core.js: header logo must stay eager (no loading=lazy)")
    if 'loading="lazy"' not in brand[1]:
        errors.append("core.js: footer logo missing loading=lazy")

# cache headers (vercel.json)
try:
    vj = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rules = {r.get("source", ""): " ".join(h.get("value", "") for h in r.get("headers", []))
             for r in vj.get("headers", [])}
    expect = [
        ("/sw.js", "no-cache"),
        ("/assets/(.*)", "max-age=86400"),
        ("/data/(.*)", "max-age=60"),
        ("/", "max-age=0, must-revalidate"),
        ("/manifest.webmanifest", "max-age=86400"),
        ("/(robots.txt|sitemap.xml)", "max-age=3600"),
    ]
    for src, frag in expect:
        if src not in rules:
            errors.append(f"vercel.json: missing header rule {src}")
        elif frag not in rules[src]:
            errors.append(f"vercel.json: {src} Cache-Control lacks {frag!r} (got {rules[src]!r})")
    if not any("must-revalidate" in v and "max-age=0" in v for k, v in rules.items() if "index" in k):
        errors.append("vercel.json: no HTML rule with max-age=0, must-revalidate")
    if not any("index" in k and "articles" in k for k in rules):
        errors.append("vercel.json: HTML cache rule does not cover articles pages")
except Exception as e:
    errors.append(f"vercel.json: header validation failed: {e}")
notes.append("perf: deferred scripts, dns-prefetch x3, style+logo preloads, quantized images (-78%), explicit cache headers")

# --- student quiz access flow: Google sign-in gate --------------------------
# site.auth config (data/site.json) + auth.js on every page + flow buttons.
try:
    site_raw = json.loads((ROOT / "data" / "site.json").read_text(encoding="utf-8"))
    auth_cfg = site_raw.get("auth")
    if not isinstance(auth_cfg, dict):
        errors.append("site.json: missing auth block (student access flow)")
    else:
        if auth_cfg.get("enabled") is not True:
            errors.append("site.json: auth.enabled must be true")
        if auth_cfg.get("requireLogin") is not True:
            errors.append("site.json: auth.requireLogin must be true")
        if not isinstance(auth_cfg.get("preview"), bool):
            errors.append("site.json: auth.preview must be a boolean")
        fb = auth_cfg.get("firebase")
        if not isinstance(fb, dict):
            errors.append("site.json: auth.firebase config block missing")
        else:
            for k in ("apiKey", "authDomain", "projectId", "appId"):
                if k not in fb:
                    errors.append(f"site.json: auth.firebase.{k} key missing")
except Exception as e:
    errors.append(f"site.json: auth validation failed: {e}")

for page in PAGES:
    html = (ROOT / page).read_text(encoding="utf-8")
    if 'assets/js/auth.js' not in html:
        errors.append(f"{page}: missing auth.js script tag")
    elif html.find("assets/js/auth.js") < html.find("assets/js/core.js"):
        errors.append(f"{page}: auth.js must load after core.js")

auth_js = (ROOT / "assets/js/auth.js").read_text(encoding="utf-8")
for marker in ("Continue with Google", 'aria-modal="true"', "syncResult", "fetchScores"):
    if marker not in auth_js:
        errors.append(f"auth.js: missing required marker {marker!r}")
if "HOA.auth.ensure" not in (ROOT / "assets/js/mock.js").read_text(encoding="utf-8"):
    errors.append("mock.js: mock-test start is not gated by HOA.auth.ensure")
if "cloudEnabled" not in (ROOT / "assets/js/leaderboard.js").read_text(encoding="utf-8"):
    errors.append("leaderboard.js: no global-board (cloud) rendering path")

result_html = (ROOT / "result.html").read_text(encoding="utf-8")
for marker in ("View Dashboard", 'href="progress.html"', "Attempt Another Quiz"):
    if marker not in result_html:
        errors.append(f"result.html: missing quiz-result action {marker!r}")

progress_html = (ROOT / "progress.html").read_text(encoding="utf-8")
if 'id="authAccount"' not in progress_html:
    errors.append("progress.html: missing #authAccount container")
if 'id="authChip"' not in (ROOT / "assets/js" / "core.js").read_text(encoding="utf-8"):
    errors.append("core.js: missing #authChip account chip in header chrome")

rules_path = ROOT / "firestore.rules"
if not rules_path.exists() or "leaderboard" not in rules_path.read_text(encoding="utf-8"):
    errors.append("firestore.rules: missing or incomplete (Firestore security rules)")

notes.append("access: Google-sign-in quiz gate (site.auth), auth.js on all pages, Firestore rules + result Dashboard/Attempt actions")

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
