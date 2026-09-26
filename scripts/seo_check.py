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
from collections import Counter
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "https://houseofaspirants.in"
errors, warnings, notes = [], [], []
PAGES = [
    "index.html", "subject.html", "quiz.html", "mock.html", "leaderboard.html",
    "bookmarks.html", "progress.html", "result.html", "about.html",
    "contact.html", "privacy.html", "terms.html", "404.html",
    # Exam index (target: Punjab Government competitive exams)
    "punjab-exams.html",
    # AEO hub: site-wide Q&A for answer engines
    "faq.html",
    # Study-guides hub + registered articles (data/articles.json)
    "articles.html", "punjab-police-exam-preparation.html",
    "punjab-gk-study-guide.html", "current-affairs-preparation.html",
    "reasoning-quant-preparation.html",
]
# --- programmatic SEO landing pages (generated, committed) -------------------
# scripts/build_landing_pages.py writes data/landing-manifest.json plus the
# page files; the manifest is the single source of truth for what exists, so
# the gate scans exactly those pages and never trusts prose in the report.
LANDING_MANIFEST = ROOT / "data" / "landing-manifest.json"

# Required auto-generated routes, labelled exactly as SEO-LANDING-REPORT.md
# prints them so the gate can compare the report row against the shipped HTML.
PAIR_LABEL = {
    ("subject", "topic"): "Subject → Topic",
    ("topic", "quiz"): "Topic → Quiz",
    ("quiz", "subject"): "Quiz → Subject",
    ("exam", "subject"): "Exam → Subject",
    ("exam", "topic"): "Exam → Topic",
}
landing_pages = []          # ordered records from the manifest
landing_files = set()       # generated .html filenames
if not LANDING_MANIFEST.exists():
    errors.append("data/landing-manifest.json missing - run scripts/build_landing_pages.py")
else:
    try:
        _lm = json.loads(LANDING_MANIFEST.read_text(encoding="utf-8"))
        landing_pages = [p for p in _lm.get("pages", []) if p.get("file")]
        landing_files = {p["file"] for p in landing_pages}
        for _p in landing_pages:
            if _p.get("file") and _p["file"] not in PAGES:
                PAGES.append(_p["file"])
    except json.JSONDecodeError as e:
        errors.append(f"data/landing-manifest.json: invalid JSON: {e}")

    # every generated landing file on disk must be registered (stale files are
    # as bad as missing ones: an unregistered page is invisible to the gate)
    for _f in sorted(ROOT.glob("[a-z]*-*.html")):
        if (_f.name.startswith(("subject-", "category-", "topic-", "quiz-", "exam-"))
                and _f.name not in landing_files):
            errors.append(f"{_f.name}: landing page on disk but absent from "
                          f"landing-manifest.json")

ART_HUB = "articles.html"
REQUIRED_LINKS = [
    'href="index.html"', 'href="index.html#subjects"',
    'href="quiz.html?mode=daily"', 'href="mock.html"',
    'href="bookmarks.html"', 'href="progress.html"', 'href="leaderboard.html"',
    'href="contact.html"', 'href="about.html"', 'href="privacy.html"',
    'href="terms.html"',
]

# --- schema.org validation vocabulary ---------------------------------------
KNOWN_TYPES = {
    "WebSite", "Organization", "EducationalOrganization", "WebPage", "AboutPage",
    "ContactPage", "CollectionPage", "BreadcrumbList", "ListItem", "SearchAction",
    "EntryPoint", "ImageObject", "Quiz", "Thing", "Country", "ContactPoint", "ItemList",
    "Article", "FAQPage", "Question", "Answer", "SpeakableSpecification",
    "Person", "LearningResource",
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
    "SearchAction": ["target", "query"],
    "EntryPoint": ["urlTemplate"],
    "Quiz": ["name", "url", "description"],
    "ContactPoint": ["contactType"],
    "ImageObject": ["url"],
    "ListItem": ["position", "name"],
    "Article": ["headline", "image", "datePublished", "author", "mainEntityOfPage"],
    "LearningResource": ["learningResourceType"],
    "Person": ["name", "url"],
    # AEO layer: an FAQ must actually expose its questions and answers
    "FAQPage": ["mainEntity"],
    "Question": ["name", "acceptedAnswer"],
    "Answer": ["text"],
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
    # @id references are resolved once the WHOLE page has been parsed: Google
    # treats every JSON-LD <script> on a page as a single entity graph, so a
    # node defined in block 1 may legitimately be referenced from block 2.
    # Site-level entities (defined on the home page) stay whitelisted.
    page_defined_ids, page_seen_ids, pending_refs = set(), set(), []
    page_entities, collection_refs = {}, []   # CollectionPage -> ItemList check
    cross_page_ok = {
        f"{DOMAIN}/#website", f"{DOMAIN}/#organization",
        f"{DOMAIN}/#webpage", f"{DOMAIN}/#person",
    }
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
        for n in nodes:
            if isinstance(n.get("@id"), str):
                page_defined_ids.add(n["@id"])
                page_entities[n["@id"]] = n
        seen_ids = page_seen_ids   # duplicate @id is a page-level defect too

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
            # A CollectionPage must expose its collection as an ItemList that
            # Google can walk, referenced through @id (never inlined twice).
            if "CollectionPage" in tlist:
                me = n.get("mainEntity")
                if not (isinstance(me, dict) and "@id" in me):
                    errors.append(
                        f"{tag}: CollectionPage.mainEntity must be an @id "
                        f"reference to its ItemList"
                    )
                else:
                    collection_refs.append((tag, me["@id"]))

        # defer reference resolution until every block on this page is known
        pending_refs.extend((tag, r) for r in refs_found)

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

    # every @id reference must resolve to a node defined somewhere on this
    # page (any block) or to a known cross-page entity
    for tag, r in pending_refs:
        if r not in page_defined_ids and r not in cross_page_ok:
            errors.append(f"{tag}: dangling @id reference {r}")

    # ... and the CollectionPage's referenced node must really be an ItemList
    for tag, me_id in collection_refs:
        node = page_entities.get(me_id)
        if node is None:
            continue  # already reported as a dangling reference above
        mt = node.get("@type")
        mt = [mt] if isinstance(mt, str) else (mt or [])
        if mt != ["ItemList"]:
            errors.append(
                f"{tag}: CollectionPage.mainEntity {me_id} must be an ItemList "
                f"(found {mt})"
            )

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

# --- runtime structured data (not present in the static HTML) --------------
# quiz.js builds Google's Education Q&A graph and subject.js builds the
# CollectionPage's ItemList on the client, so seo_check can only assert that
# the required pieces stay wired into those builders.
quiz_js = (ROOT / "assets/js/quiz.js").read_text(encoding="utf-8")
for marker in (
    '"@type": "Question"',                    # Question nodes exist
    'eduQuestionType: "Flashcard"',           # Google-required fixed value
    'acceptedAnswer: { "@type": "Answer"',    # Google-required answer
    "{ hasPart: flashcards }",                # Google-required Quiz.hasPart
):
    if marker not in quiz_js:
        errors.append(f"quiz.js: Education Q&A builder missing {marker!r}")
subj_js = (ROOT / "assets/js/subject.js").read_text(encoding="utf-8")
for marker in ('"@type": "ItemList"', "`${canonical}#list`"):
    if marker not in subj_js:
        errors.append(f"subject.js: CollectionPage ItemList missing {marker!r}")

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
            "articles.html", "punjab-exams.html", "faq.html",
            "punjab-police-exam-preparation.html",
            "punjab-gk-study-guide.html", "current-affairs-preparation.html",
            "reasoning-quant-preparation.html"} | set(landing_files)
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

# --- AEO / GEO layer: direct answers, FAQ, EEAT bylines, named sources -----
# Every page that ranks for a question must answer it in the first screenful
# (40-60 words in .answer-box) and expose the same Q&A as FAQPage schema.
AEO_PAGES = {"index.html", "faq.html", "punjab-exams.html", "articles.html",
             "about.html", "subject.html", "mock.html"} | ARTICLE_PAGES | set(landing_files)
for p in sorted(AEO_PAGES):
    h = (ROOT / p).read_text(encoding="utf-8")
    if 'class="answer-box"' not in h:
        errors.append(f"{p}: AEO quick-answer block (.answer-box) missing")
    if "FAQPage" not in types_by_page.get(p, set()):
        errors.append(f"{p}: missing FAQPage schema")

# EEAT: attributed byline + a named, checkable source list on every guide
for p in sorted(ARTICLE_PAGES):
    h = (ROOT / p).read_text(encoding="utf-8")
    if 'class="byline"' not in h:
        errors.append(f"{p}: EEAT byline (author + review date) missing")
    if 'class="sources"' not in h:
        errors.append(f"{p}: named-sources block missing")
    if 'href="contact.html"' not in h:
        errors.append(f"{p}: corrections/contact link missing")

# FAQ hub: enough real questions, and schema must mirror the visible page
faq_html = (ROOT / "faq.html").read_text(encoding="utf-8")
vis_q = len(re.findall(r'<div class="faq-item">', faq_html))
sch_q = faq_html.count('"@type": "Question"')
if vis_q < 30:
    errors.append(f"faq.html: only {vis_q} visible Q&A items (want >= 30)")
if sch_q != vis_q:
    errors.append(f"faq.html: FAQPage schema has {sch_q} questions but {vis_q} are visible")
if "faq.html" not in core:
    errors.append("core.js: FAQ hub not linked from footer/drawer")
if f"{DOMAIN}/faq" not in locs:
    errors.append("sitemap: missing /faq URL")
notes.append(f"aeo: {len(AEO_PAGES)} pages answer-first, {vis_q} FAQ pairs mirrored in schema, {len(ARTICLE_PAGES)} guides carry byline + sources")

# --- programmatic SEO landing pages: per-type content contracts ------------
# data/landing-manifest.json (written by scripts/build_landing_pages.py) is the
# source of truth for WHICH pages exist; every promise below is re-derived from
# data/index.json + data/exams.json + data/articles.json and measured against
# the HTML on disk - never from SEO-LANDING-REPORT.md prose. Each landing file
# is already in PAGES, so title/description/canonical uniqueness, robots,
# chrome, resource hints and schema-family rules above apply to them too.
MIN_INTRO_WORDS = {"subject": 250, "category": 150, "topic": 60, "quiz": 60,
                   "exam": 90}


def ld_nodes(page_html):
    """Yield every JSON-LD object (flattening @graph) on a page."""
    for blk in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
                          page_html, re.S):
        if not blk.strip():          # runtime-managed placeholder (ldDynamic)
            continue
        try:
            doc = json.loads(blk)
        except json.JSONDecodeError:
            continue
        nodes = doc.get("@graph", [doc]) if isinstance(doc, dict) else []
        for node in nodes:
            if isinstance(node, dict):
                yield node


def ld_type(node):
    t = node.get("@type", "")
    return t if isinstance(t, list) else [t]


def faq_count(page_html):
    """Questions inside FAQPage only (a quiz page also has Quiz.hasPart)."""
    n = 0
    for node in ld_nodes(page_html):
        if "FAQPage" in ld_type(node):
            main = node.get("mainEntity") or []
            n += len(main) if isinstance(main, list) else 1
    return n


def intro_words(page_html):
    m = re.search(r'<div class="landing-intro" data-landing="intro">(.*?)</div>',
                  page_html, re.S)
    return len(re.sub(r"<[^>]+>", " ", m.group(1)).split()) if m else 0


if landing_pages:
    idx_land = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    subj_by_id = {s["id"]: s for s in idx_land.get("subjects", [])}
    exams_land = json.loads((ROOT / "data" / "exams.json").read_text(encoding="utf-8")).get("exams", [])
    exam_by_id = {e["id"]: e for e in exams_land}

    # (subject_id, topic_id) -> topic record, walking flat topics + categories
    topic_by_key = {}
    for s in idx_land.get("subjects", []):
        for t in s.get("topics", []) or []:
            topic_by_key[(s["id"], t["id"])] = t
        for c in s.get("categories", []) or []:
            for t in c.get("topics", []) or []:
                topic_by_key[(s["id"], t["id"])] = t

    LINK_RX = re.compile(r'href="((?:subject|category|topic|quiz|exam)-[a-z0-9-]+\.html)"')
    lpages = {r["file"]: r for r in landing_pages}
    landing_h = {f: (ROOT / f).read_text(encoding="utf-8")
                 for f in lpages if (ROOT / f).exists()}
    links_of = {f: LINK_RX.findall(h) for f, h in landing_h.items()}

    # --- manifest must describe the file that actually shipped --------------
    for f, r in lpages.items():
        h = landing_h.get(f)
        if h is None:
            continue                   # "missing file" already reported above
        want_url = f"{DOMAIN}/{f[:-5]}" if f.endswith(".html") else ""
        if r.get("url") != want_url:
            errors.append(f"{f}: manifest url {r.get('url')!r} != expected {want_url!r}")
        if canonical(h) != want_url:
            errors.append(f"{f}: canonical {canonical(h)!r} != manifest url {want_url!r}")
        if want_url not in locs:
            errors.append(f"{f}: landing URL missing from sitemap.xml ({want_url})")
        m = re.search(r"<title>(.*?)</title>", h, re.S)
        ship_title = html_mod.unescape(m.group(1).strip()) if m else ""
        if r.get("title") and r["title"] != ship_title:
            errors.append(f"{f}: manifest title drifted from rendered <title>")
        if r.get("description") and r["description"] != html_mod.unescape(meta(h, "description")):
            errors.append(f"{f}: manifest description drifted from meta description")
        w = intro_words(h)
        floor = MIN_INTRO_WORDS.get(r.get("type", ""), 0)
        if w < floor:
            errors.append(f"{f}: intro {w} words (want >= {floor} for {r.get('type')})")

    # duplicate CONTENT: no two landing pages may share an H1 or an intro
    h1_seen, intro_seen = {}, {}
    for f in landing_h:
        h = landing_h[f]
        m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
        if m:
            key = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split()).lower()
            if key in h1_seen:
                errors.append(f"duplicate H1 on {f} and {h1_seen[key]}")
            h1_seen[key] = f
        m = re.search(r'<div class="landing-intro" data-landing="intro">(.*?)</div>',
                      h, re.S)
        key = " ".join(re.sub(r"<[^>]+>", " ", m.group(1)).split()).lower() if m else ""
        if len(key) > 40:
            if key in intro_seen:
                errors.append(f"duplicate intro copy on {f} and {intro_seen[key]}")
            intro_seen[key] = f

    # --- Subject page: 250-word intro, FAQ, Related Subjects/Exams/Quizzes --
    for r in [x for x in landing_pages if x["type"] == "subject"]:
        f, h = r["file"], landing_h.get(r["file"], "")
        if not h:
            continue
        sid = r.get("entity", "")
        for frag, label in (
            ("<h2>Related subjects</h2>", "Related Subjects section"),
            ("<h2>Related quizzes</h2>", "Related Quizzes section"),
            (r"Exams that lean on ", "Related Exams section"),
            ("<h2>All about ", "intro section"),
        ):
            if not re.search(frag, h):
                errors.append(f"{f}: {label} missing")
        if faq_count(h) < 3:
            errors.append(f"{f}: needs >= 3 FAQ questions (has {faq_count(h)})")
        # Subject -> Topic / Category: every child landing file must be linked
        want = {c for c in links_of.get(r["file"], [])
                if c.startswith((f"category-{sid}-", f"topic-{sid}-"))}
        expected = {f2 for f2 in lpages
                    if f2.startswith((f"category-{sid}-", f"topic-{sid}-"))}
        missing = sorted(expected - want)
        if missing:
            errors.append(f"{f}: Subject->Topic links missing {missing}")

    # --- Category page: links back to its parent subject + at least one quiz -
    for r in [x for x in landing_pages if x["type"] == "category"]:
        h = landing_h.get(r["file"], "")
        if not h:
            continue
        sid = r.get("entity", "").split("/")[0]
        if f"subject-{sid}.html" not in links_of.get(r["file"], []):
            errors.append(f"{r['file']}: Category->Subject link missing")
        if not any(l.startswith("quiz-") for l in links_of.get(r["file"], [])):
            errors.append(f"{r['file']}: Category->Quiz link missing")

    # --- Topic page: sections, facts, and Topic -> Quiz --------------------
    for r in [x for x in landing_pages if x["type"] == "topic"]:
        f, h = r["file"], landing_h.get(r["file"], "")
        if not h:
            continue
        sid, tid = r.get("entity", "").split("/")
        for frag, label in (
            (r"<h2>What .* covers</h2>", "Topic Introduction"),
            (r"<h2>Why .* is worth the hours</h2>", "Why Important"),
            (r"<h2>Exams where .* matters</h2>", "Exam Relevance"),
            (r"<h2>Expected questions from ", "Expected Questions"),
            ("<h2>Previous Year Questions</h2>", "Previous Year Questions"),
            ("<h2>Related topics</h2>", "Related Topics"),
        ):
            if not re.search(frag, h):
                errors.append(f"{f}: topic section missing - {label}")
        for label in ("Question count", "Estimated time", "Difficulty", "Last updated"):
            if f'<div class="stat-label">{label}</div>' not in h:
                errors.append(f"{f}: topic fact '{label}' missing")
        if f"quiz-{sid}-{tid}.html" not in links_of.get(f, []):
            errors.append(f"{f}: Topic->Quiz link missing (quiz-{sid}-{tid}.html)")
        if f"subject-{sid}.html" not in links_of.get(f, []):
            errors.append(f"{f}: Topic->Subject link missing")

    # --- Quiz page: metadata facts, share, prev/next, Quiz schema, seed -----
    for r in [x for x in landing_pages if x["type"] == "quiz"]:
        f, h = r["file"], landing_h.get(r["file"], "")
        if not h:
            continue
        sid, tid = r.get("entity", "").split("/")
        for label in ("Question count", "Estimated time", "Difficulty", "Last updated"):
            if f"<b>{label}:</b>" not in h:
                errors.append(f"{f}: quiz fact '{label}' missing")
        for frag, label in (
            ("t.me/share", "Telegram share"),
            ("wa.me", "WhatsApp share"),
            ("twitter.com/intent", "X/Twitter share"),
            ("data-copy-url", "copy-link share"),
            ("<h2>Previous and next quizzes</h2>", "Previous/Next Quiz nav"),
            ("<h2>Related quizzes</h2>", "Related Quiz section"),
            ("<h2>About the ", "About this quiz section"),
        ):
            if frag not in h:
                errors.append(f"{f}: {label} missing")
        if f"subject-{sid}.html" not in links_of.get(f, []):
            errors.append(f"{f}: Quiz->Subject link missing")
        if f"topic-{sid}-{tid}.html" not in links_of.get(f, []):
            errors.append(f"{f}: Quiz->Topic link missing")
        # seed must be emitted BEFORE quiz.js so the engine boots from it
        seed_at, engine_at = h.find("__HOA_QUIZ_SEED"), h.find("assets/js/quiz.js")
        if seed_at < 0:
            errors.append(f"{f}: window.__HOA_QUIZ_SEED block missing")
        elif engine_at < 0:
            errors.append(f"{f}: assets/js/quiz.js missing")
        elif seed_at > engine_at:
            errors.append(f"{f}: __HOA_QUIZ_SEED must load before assets/js/quiz.js")
        # static JSON-LD owns the page: the runtime placeholder stays blank
        if not re.search(r'<script type="application/ld\+json" id="ldDynamic">\s*</script>', h):
            errors.append(f"{f}: ldDynamic placeholder must stay blank (static graph owns schema)")
        # Quiz schema hasPart must match the question file exactly
        quiz_nodes = [n for n in ld_nodes(h) if "Quiz" in ld_type(n)]
        if not quiz_nodes:
            errors.append(f"{f}: Quiz schema node missing")
        else:
            have = quiz_nodes[0].get("hasPart") or []
            rec = topic_by_key.get((sid, tid))
            if not rec:
                errors.append(f"{f}: {sid}/{tid} not found in data/index.json")
            else:
                qf = ROOT / rec["file"]
                try:
                    raw = json.loads(qf.read_text(encoding="utf-8"))
                    n_file = len(raw) if isinstance(raw, list) else len(raw.get("questions", []))
                except (OSError, ValueError):
                    n_file = -1
                if n_file >= 0 and len(have) != n_file:
                    errors.append(f"{f}: Quiz.hasPart has {len(have)} questions, "
                                  f"{rec['file']} holds {n_file}")
                if rec.get("count") and len(have) != rec["count"]:
                    errors.append(f"{f}: Quiz.hasPart {len(have)} != index.json count {rec['count']}")
                m = re.search(r"<b>Question count:</b>\s*(\d+)", h)
                if m and int(m.group(1)) != len(have):
                    errors.append(f"{f}: visible question count {m.group(1)} != hasPart {len(have)}")
            for node in have[:3]:
                if node.get("eduQuestionType") != "Flashcard":
                    errors.append(f"{f}: hasPart entry missing eduQuestionType: Flashcard")
                    break

    # --- Exam page: Exam -> Subject (configured) and Exam -> Topic (derived)
    for r in [x for x in landing_pages if x["type"] == "exam"]:
        f, h = r["file"], landing_h.get(r["file"], "")
        if not h:
            continue
        eid = r.get("entity", "")
        e = exam_by_id.get(eid)
        if e is None:
            errors.append(f"{f}: {eid} not found in data/exams.json")
            continue
        if not re.search(r"<h2>What to study for ", h):
            errors.append(f"{f}: exam route section (What to study for ...) missing")
        got = links_of.get(f, [])
        subj_ids = [sid for sid in (e.get("subjects") or []) if sid in subj_by_id]
        want_subjects = {f"subject-{sid}.html" for sid in subj_ids}
        if not subj_ids:
            # honest fallback: unmapped exam still links the whole subject library
            want_subjects = {f2 for f2 in lpages if f2.startswith("subject-")}
            if len({s for s in got if s.startswith("subject-")}) < len(want_subjects):
                errors.append(f"{f}: unmapped exam must link every subject page")
        miss = sorted(want_subjects - set(got))
        if miss and subj_ids:
            errors.append(f"{f}: Exam->Subject links missing {miss}")
        # Exam -> Topic: mirror the generator's derivation (subjects x live
        # topics, filtered by the exam's declared categories, first 6)
        cat_ids = [c for c in (e.get("categories") or []) if c]
        want_topics = []
        for sid in subj_ids:
            s = subj_by_id.get(sid) or {}
            flat = [(None, t) for t in s.get("topics", []) or []]
            for c in s.get("categories", []) or []:
                flat += [(c, t) for t in c.get("topics", []) or []]
            for c, t in flat:
                if cat_ids and c and c["id"] not in cat_ids:
                    continue
                tf = f"topic-{sid}-{t['id']}.html"
                if tf in lpages and tf not in want_topics:
                    want_topics.append(tf)
        miss_t = [t for t in want_topics[:6] if t not in got]
        if miss_t:
            errors.append(f"{f}: Exam->Topic links missing {miss_t}")

    # --- sitemap must never carry query-string (duplicate) URLs ------------
    for u in locs:
        if "?" in u:
            errors.append(f"sitemap: query-string URL is a duplicate-content risk: {u}")

    # --- SEO-LANDING-REPORT.md must describe THIS build -------------------
    # The report is a deliverable: a stale or hand-edited count is as bad as no
    # report. Recompute the headline numbers from the HTML and compare.
    rep_path = ROOT / "SEO-LANDING-REPORT.md"
    if not rep_path.exists():
        errors.append("SEO-LANDING-REPORT.md missing (build_landing_pages.py did not write it)")
    else:
        rep = rep_path.read_text(encoding="utf-8")
        m = re.search(r"## 1\. Pages optimized \((\d+)\)", rep)
        if not m:
            errors.append("report: 'Pages optimized (N)' heading missing")
        elif int(m.group(1)) != len(landing_pages):
            errors.append(f"report says {m.group(1)} pages, manifest has {len(landing_pages)}")
        # recompute entity<->entity links from the shipped HTML
        real_pairs = Counter()
        for f, h in landing_h.items():
            for dst in LINK_RX.findall(h):
                if dst in lpages and dst != f:
                    real_pairs[(lpages[f]["type"], lpages[dst]["type"])] += 1
        real_entity = sum(real_pairs.values())
        m = re.search(r"## 3\. Internal links created \((\d+)\)", rep)
        if not m:
            errors.append("report: 'Internal links created (N)' heading missing")
        elif int(m.group(1)) != real_entity:
            errors.append(f"report says {m.group(1)} internal links, HTML has {real_entity}")
        # every required route must be reported with the count it really has
        for pair, label in PAIR_LABEL.items():
            m = re.search(re.escape(f"| {label} | ") + r"(\d+) \| (\S+)", rep)
            if not m:
                errors.append(f"report: required route row missing ({label})")
                continue
            n, tick = int(m.group(1)), m.group(2)
            if n != real_pairs.get(pair, 0):
                errors.append(f"report: {label} shows {n}, HTML has {real_pairs.get(pair, 0)}")
            if n == 0 and tick.startswith("✅"):
                errors.append(f"report: {label} has 0 links but is still ticked ✅")
            if n > 0 and not tick.startswith("✅"):
                errors.append(f"report: {label} has {n} links but is not ticked ✅")
        if "250-word intro target" not in rep:
            errors.append("report: subject 250-word intro statement missing")

    # --- quiz.html stays a valid generator template -------------------------
    # scripts/build_landing_pages.py transforms quiz.html by regex; if someone
    # edits the template these anchors must still be findable or generation
    # silently produces broken pages.
    tpl = (ROOT / "quiz.html").read_text(encoding="utf-8")
    for frag, label in (
        ("<title>", "title"), ('name="description"', "meta description"),
        ('rel="canonical"', "canonical"), ("<h1", "h1"),
        ('id="ldDynamic"', "runtime JSON-LD slot"),
        ("<main id=\"main\">", "main landmark"),
        ("assets/js/quiz.js", "quiz engine script"),
        ("assets/js/core.js", "core.js script"),
    ):
        if frag not in tpl:
            errors.append(f"quiz.html: generator anchor missing ({label}): {frag!r}")
    # core.js must stay deferred even though attribute order may vary
    core_tags = [t for t in re.findall(r"<script\b[^>]*assets/js/core\.js[^>]*>", tpl)]
    if not core_tags or any(" defer" not in t for t in core_tags):
        errors.append("quiz.html: deferred core.js <script> anchor missing/changed")

    n_links = sum(len(v) for v in links_of.values())
    by_kind = {}
    for rec in landing_pages:
        by_kind[rec.get("type", "?")] = by_kind.get(rec.get("type", "?"), 0) + 1
    kinds = " ".join(f"{k}={by_kind[k]}" for k in sorted(by_kind))
    notes.append(
        f"landing pages: {len(landing_pages)} generated ({kinds}), {n_links} internal "
        f"links, sitemap + manifest + metadata all in sync"
    )

inv = {}
for tps in types_by_page.values():
    for t in tps:
        inv[t] = inv.get(t, 0) + 1
notes.append("schema (static): " + ", ".join(f"{k}x{v}" for k, v in sorted(inv.items())))
notes.append(
    "schema (runtime): CollectionPage + ItemList + BreadcrumbList via subject.js; "
    "WebPage + Quiz + Question/Answer (Education Q&A) via quiz.js"
)

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

# Google Analytics 4 — single source of truth in core.js (all 19 pages load it)
GA_ID = "G-WHSFW3ZYZL"
for frag, why in (
    (GA_ID, "Measurement ID"),
    ("googletagmanager.com/gtag/js", "gtag.js loader URL"),
    ("send_page_view", "page_view config"),
    ("s.async = true", "gtag.js must be async (never render-blocking)"),
    ("isLocalHost", "localhost guard (dev traffic must not pollute the property)"),
    ("startAnalytics()", "analytics must be started from init()"),
    ("try {", "analytics must be wrapped so it cannot break the portal"),
):
    if frag not in core:
        errors.append(f"core.js: GA4 missing {why} ({frag!r})")
notes.append(f"analytics: GA4 {GA_ID} from core.js (async, localhost-exempt)")

# Microsoft Clarity — same single-source policy as GA4, but production-only:
# Clarity records real sessions, so the guard is an allowlist of the live
# domain (stricter than GA4's localhost exemption) and the snippet must never
# be pasted into individual pages, where it could load twice or off-domain.
CLARITY_ID = "yodrakwmyn"
for frag, why in (
    (f'CLARITY_ID = "{CLARITY_ID}"', "project id"),
    ("clarity.ms/tag/", "official loader URL"),
    ("t.async = 1", "loader must stay async (never render-blocking)"),
    ("isProductionHost", "production allowlist guard (dev/preview must not load)"),
    ('"houseofaspirants.in"', "live domain in the allowlist"),
    ("startClarity()", "loader must be started from init()"),
    ("try {", "loader must be wrapped so it cannot break the portal"),
):
    if frag not in core:
        errors.append(f"core.js: Clarity missing {why} ({frag!r})")
for page in PAGES:
    html = (ROOT / page).read_text(encoding="utf-8")
    if "clarity" in html.lower():
        errors.append(f"{page}: Clarity must ship only from core.js, not inline")
    if "assets/js/core.js" not in html:
        errors.append(f"{page}: missing core.js — analytics/Clarity coverage broken")
notes.append(f"analytics: Clarity {CLARITY_ID} from core.js (async, production-only)")

# cache headers (vercel.json)
try:
    vj = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rules = {r.get("source", ""): " ".join(h.get("value", "") for h in r.get("headers", []))
             for r in vj.get("headers", [])}
    expect = [
        ("/sw.js", "no-cache"),
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
    # Shell assets are served cache-first by the service worker, so the HTTP
    # cache must stay SHORT: a 24h max-age let a deploy push new CSS/JS while
    # returning stale bytes from the HTTP cache for up to a day. Bounded at
    # <= 1 hour + SWR so every push reaches devices quickly.
    asset_cc = rules.get("/assets/(.*)", "")
    m = re.search(r"max-age=(\d+)", asset_cc)
    if not m:
        errors.append(f"vercel.json: /assets/(.*) has no max-age (got {asset_cc!r})")
    elif int(m.group(1)) > 3600:
        errors.append(
            f"vercel.json: /assets/(.*) max-age={m.group(1)} > 3600 — shell assets are "
            "cache-first, long HTTP caching delays deploys (got %r)" % asset_cc
        )
    elif "stale-while-revalidate" not in asset_cc:
        errors.append(f"vercel.json: /assets/(.*) missing stale-while-revalidate (got {asset_cc!r})")
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

# --- telegram growth & student conversion system ---------------------------
# Presence-only checks: the flow must never force a join, block a quiz or
# hide a result — quiz attempt pages carry no rotator and no exit popup.
idx_html = (ROOT / "index.html").read_text(encoding="utf-8")
for marker in (
    "Prepare Smarter", "Join Telegram", "Start Free Quiz",
    "Learn from Someone Who Cleared the Exam", "Gurpreet Singh",
    "tg-value-grid", "subjects-layout", 'class="tg-rail"',
):
    if marker not in idx_html:
        errors.append(f"index.html: missing Telegram growth marker {marker!r}")
# The homepage no longer carries rotator slots (mobile-first de-cluttering);
# it must instead expose enough Telegram entry points to stay discoverable.
if idx_html.count('href="https://t.me/HouseOfAspirant"') < 3:
    errors.append("index.html: expected >=3 Telegram entry points")

core_js = (ROOT / "assets/js" / "core.js").read_text(encoding="utf-8")
for marker in (
    "TG_BANNERS", "initTgRotators", "initExitIntent", "hoa_exit_intent",
    "tg-float", "data-tg-rotator", "Join thousands of aspirants",
    'page === "quiz" || page === "result"',
):
    if marker not in core_js:
        errors.append(f"core.js: missing Telegram growth marker {marker!r}")

quiz_js = (ROOT / "assets/js" / "quiz.js").read_text(encoding="utf-8")
for marker in ("Continue to Result", "Congratulations", "completion-overlay"):
    if marker not in quiz_js:
        errors.append(f"quiz.js: missing completion-screen marker {marker!r}")

for page, markers in (
    ("progress.html", ("Telegram Community Benefits", "tg-res-grid", "Today&rsquo;s resources")),
    ("leaderboard.html", ("Improve Your Rank", "tg-boost")),
    ("articles.html", ("tg-lock-grid", "Premium Resources")),
    ("result.html", ("data-tg-rotator",)),
):
    text = (ROOT / page).read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{page}: missing Telegram growth marker {marker!r}")

rot_slots = sum(
    (ROOT / page).read_text(encoding="utf-8").count("data-tg-rotator")
    for page in PAGES
)
if rot_slots < 8:
    errors.append(f"rotating Telegram banners: expected >=8 slots, found {rot_slots}")
if "data-tg-rotator" in (ROOT / "quiz.html").read_text(encoding="utf-8"):
    errors.append("quiz.html: rotating banners must not appear on the quiz attempt")

notes.append(
    "telegram growth: hero CTA + mentor credibility + 8 value props + desktop rail, "
    f"{rot_slots} rotating banners, 7-day exit intent, floating button, "
    "quiz-completion offer, dashboard cards + profile benefits + resource locks"
)

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
