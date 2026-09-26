#!/usr/bin/env python3
"""
 ============================================================================
  HOUSE OF ASPIRANTS - PROGRAMMATIC SEO LANDING PAGE BUILDER
 ----------------------------------------------------------------------------
  Reads the manifest (data/index.json), the config files and the authored
  copy (data/seo_copy.json) and generates one independent, crawlable SEO
  landing page per entity:

      data-driven entity          file                        URL
      ------------------------------------------------------------------
      Subject      subject-<id>.html              /subject-<id>
      Category     category-<subject>-<cat>.html  /category-<subject>-<cat>
      Topic        topic-<subject>-<topic>.html   /topic-<subject>-<topic>
      Quiz         quiz-<subject>-<topic>.html     /quiz-<subject>-<topic>
      Exam         exam-<id>.html                 /exam-<id>

  Every page is emitted at the repository ROOT (never in a sub-folder) so the
  shared chrome, stylesheets, images and core.js fetches keep working with the
  site's existing RELATIVE paths - no <base> tag, no path rewriting.

  It also writes:
      data/landing-manifest.json   -> single source of truth for the sitemap
                                      (read by build_index.py / build-index.mjs)
                                      and by scripts/seo_check.py
      SEO-LANDING-REPORT.md        -> pages optimized / metadata / internal
                                      links / duplicate-content analysis

  DESIGN RULES
    • Questions are READ, never generated or invented. Quiz schema mirrors the
      same normalised records the screen renders (see assets/js/core.js
      normalizeQuestions).
    • No factual claims about vacancies, dates, marks or eligibility. Copy is
      either authored in data/seo_copy.json or derived from real site data
      (counts, categories, linked exams, site settings).
    • The interactive quiz is NOT rebuilt: quiz pages are a transformed copy
      of quiz.html plus a seed object that quiz.js reads at boot.
    • Idempotent + stale-aware: re-running deletes landing pages whose entity
      no longer exists.

  USAGE:  python3 scripts/build_landing_pages.py
  Then:   python3 scripts/seo_check.py          (enforced gate)
 ============================================================================
"""
import html as html_mod
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://houseofaspirants.in"
DATA = os.path.join(ROOT, "data")

GENERATED_PREFIXES = ("subject-", "category-", "topic-", "quiz-", "exam-")

WARNINGS = []
LINKS = []          # every internal link the generator emits (for the report)
PAGES = []          # manifest records


def warn(msg):
    WARNINGS.append(msg)
    print(f"  \u26A0 {msg}")


def info(msg):
    print(f"  \u2714 {msg}")


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def esc(text):
    """HTML-escape for attribute / text nodes."""
    return html_mod.escape(str(text), quote=True)


def words(text):
    return len(re.findall(r"[A-Za-z0-9%&'-]+", text))


def para(text):
    return f"      <p>{esc(text)}</p>"


def join_paras(paras):
    return "\n".join(para(p) for p in paras)


# ---------------------------------------------------------------- metadata --
def fit_title(base, fallback):
    """Keep titles at or under 60 chars (Google truncation point)."""
    t = " ".join(str(base).split())
    if len(t) <= 60:
        return t
    t = " ".join(str(fallback).split())
    if len(t) <= 60:
        return t
    if len(t) > 60:  # last resort: hard trim at a word boundary
        t = t[:60].rsplit(" ", 1)[0]
    return t


DESC_PAD = " Start practising free on House of Aspirants - no login needed."


def fit_desc(base):
    """Pad / trim a meta description into the 140-160 character window."""
    d = " ".join(str(base).split())
    if len(d) > 160:
        d = d[:159].rsplit(" ", 1)[0].rstrip(",;:- ")
    pad = 0
    while len(d) < 140 and pad < 4:
        extra = DESC_PAD if pad == 0 else " Free MCQ practice for Punjab exams."
        if len(d) + len(extra) > 160:
            break
        d += extra
        pad += 1
    return d


def keywords(*parts):
    seen, out = set(), []
    for p in parts:
        for piece in str(p).split(","):
            k = piece.strip()
            if k and k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
    return ", ".join(out[:12])


def ld_script(obj):
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    return f'  <script type="application/ld+json">\n{body}\n  </script>'


# ------------------------------------------------------------- breadcrumbs --
def crumb_nav(crumbs):
    """Visible flat breadcrumb (matches the .breadcrumb markup on the site)."""
    parts = ['        <nav class="breadcrumb" aria-label="Breadcrumb">']
    for i, (label, href) in enumerate(crumbs):
        if href and i < len(crumbs) - 1:
            parts.append(f'          <a href="{esc(href)}">{esc(label)}</a>')
        else:
            parts.append(f"          <span>{esc(label)}</span>")
        if i < len(crumbs) - 1:
            parts.append("          <span>/</span>")
    parts.append("        </nav>")
    return "\n".join(parts)


def crumb_ld(url, crumbs):
    items = []
    for i, (label, href) in enumerate(crumbs, 1):
        item = {"@type": "ListItem", "position": i, "name": label}
        if href:  # last crumb points at the page itself
            item["item"] = href if href.endswith("/") else f"{BASE}/{href}"
        items.append(item)
    return {
        "@type": "BreadcrumbList",
        "@id": f"{url}#breadcrumb",
        "itemListElement": items,
    }


# ----------------------------------------------------------------- blocks ---
def section_head(eyebrow, title, hint="", button=""):
    out = ['        <div class="section-head">', "          <div>"]
    if eyebrow:
        out.append(f'            <span class="eyebrow">{esc(eyebrow)}</span>')
    out.append(f"            <h2>{esc(title)}</h2>")
    if hint:
        out.append(f"            <p>{esc(hint)}</p>")
    out.append("          </div>")
    if button:
        out.append(button)
    out.append("        </div>")
    return "\n".join(out)


def card_grid(items, cols=3):
    """items: [(title, blurb, href, meta)] -> card grid (h3 inside an h2 section)."""
    if not items:
        return ""
    out = [f'        <div class="grid grid-{cols}">']
    for title, blurb, href, meta in items:
        out.append('          <article class="card card-pad">')
        out.append(f'            <h3><a class="ilink" href="{esc(href)}">{esc(title)}</a></h3>')
        if blurb:
            out.append(f'            <p class="muted">{esc(blurb)}</p>')
        if meta:
            out.append(f'            <p class="text-sm muted">{esc(meta)}</p>')
        out.append("          </article>")
    out.append("        </div>")
    return "\n".join(out)


def facts_grid(pairs):
    out = ['        <div class="stats-grid mt-3" style="max-width:760px">']
    for label, value in pairs:
        out.append('          <div class="stat-card">')
        out.append(f'            <div class="stat-num">{esc(value)}</div>')
        out.append(f'            <div class="stat-label">{esc(label)}</div>')
        out.append("          </div>")
    out.append("        </div>")
    return "\n".join(out)


def faq_section(eyebrow, title, hint, faqs):
    out = ['    <section class="section" style="padding-top:0">',
           '      <div class="container" style="max-width:860px">']
    out.append(section_head(
        eyebrow, title, hint,
        '          <a class="btn btn-soft" href="faq.html">All questions \u2192</a>'))
    out.append('        <div class="faq-list">')
    for q, a in faqs:
        out.append('          <div class="faq-item">')
        out.append(f"            <h3>{esc(q)}</h3>")
        out.append(f"            <p>{esc(a)}</p>")
        out.append("          </div>")
    out.append("        </div>")
    out.append("      </div>")
    out.append("    </section>")
    return "\n".join(out)


def faq_ld(url, faqs, faq_id=None):
    return {
        "@type": "FAQPage",
        "@id": f"{url}#{faq_id or 'faq'}",
        "isPartOf": {"@id": f"{BASE}/#website"},
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faqs
        ],
    }


def webpage_ld(url, name, description, crumb_id, has_part=None):
    node = {
        "@type": "WebPage",
        "@id": f"{url}#webpage",
        "url": url,
        "name": name,
        "description": description,
        "isPartOf": {"@id": f"{BASE}/#website"},
        "publisher": {"@id": f"{BASE}/#organization"},
        "breadcrumb": {"@id": crumb_id},
        "inLanguage": "en-IN",
    }
    if has_part:
        node["hasPart"] = has_part
    return node


# ----------------------------------------------------------- page skeleton --
HEAD_TMPL = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="keywords" content="{keywords}">
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#4f46e5">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="House of Aspirants">
  <meta property="og:url" content="{url}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{base}/assets/img/og-cover.png">
  <meta property="og:locale" content="en_IN">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{base}/assets/img/og-cover.png">
  <link rel="canonical" href="{url}">
{ld}
  <link rel="preconnect" href="https://t.me">
  <link rel="dns-prefetch" href="//t.me">
  <link rel="dns-prefetch" href="//instagram.com">
  <link rel="dns-prefetch" href="//youtube.com">
  <link rel="preload" href="assets/img/logo-sm.png" as="image" type="image/png">
  <link rel="icon" href="assets/img/favicon-32.png" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" sizes="180x180" href="assets/img/icon-180.png">
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="preload" href="assets/css/style.css" as="style">
  <link rel="stylesheet" href="assets/css/style.css">
</head>

<body data-page="landing">
  <div data-site-header><noscript>
    <header class="site-header"><div class="container header-inner">
      <a class="brand" href="index.html"><span class="brand-name">House of Aspirants</span></a>
      <nav class="main-nav" aria-label="Primary"><ul class="nav-list">
        <li><a class="nav-link" href="index.html">Home</a></li>
        <li><a class="nav-link" href="index.html#subjects">Subjects</a></li>
        <li><a class="nav-link" href="punjab-exams.html">Exams</a></li>
        <li><a class="nav-link" href="faq.html">FAQ</a></li>
        <li><a class="nav-link" href="mock.html">Mock Tests</a></li>
      </ul></nav>
    </div></header>
  </noscript></div>

  <main id="main">
{hero}
{body}
{faq}
  </main>

  <div data-site-footer></div>

  <script src="assets/js/core.js" defer></script>
  <script src="assets/js/auth.js" defer></script>
</body>
</html>
"""

HERO_TMPL = """    <section class="page-hero">
      <div class="container">
{crumbs}
        <span class="eyebrow">{eyebrow}</span>
        <h1>{h1}</h1>
        <p class="muted" style="max-width:72ch">{lead}</p>
{facts}
        <div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{answer}</p>
        </div>
      </div>
    </section>"""


def render_page(*, title, description, kw, url, ld_blocks, crumbs, eyebrow, h1,
                lead, answer, facts="", body="", faq=""):
    hero = HERO_TMPL.format(
        crumbs=crumb_nav(crumbs), eyebrow=esc(eyebrow), h1=esc(h1),
        lead=esc(lead), facts=facts, answer=esc(answer))
    return HEAD_TMPL.format(
        title=esc(title), description=esc(description), keywords=esc(kw),
        url=url, ld="\n".join(ld_blocks), base=BASE,
    ).replace("{hero}", hero).replace("{body}", body).replace("{faq}", faq)


def register(filename, url, kind, entity, title, description, h1, intro_words,
             schema_types):
    PAGES.append({
        "file": filename, "url": url, "type": kind, "entity": entity,
        "title": title, "description": description, "h1": h1,
        "introWords": intro_words, "schema": sorted(schema_types),
    })


def track(src_file, src_type, dst_file, dst_type, anchor):
    LINKS.append({
        "from": src_file, "fromType": src_type,
        "to": dst_file, "toType": dst_type, "anchor": anchor,
    })


# ================================================================== LOAD =====
index = read_json(os.path.join(DATA, "index.json"))
site = index.get("site", {})
subjects = index.get("subjects", [])
stats = index.get("stats", {})
SITE_Q_SECONDS = int(site.get("questionSeconds") or 30)
SITE_DAILY = int(site.get("dailyQuizSize") or 20)
SITE_PASS = int(site.get("passPercent") or 40)

articles = read_json(os.path.join(DATA, "articles.json")).get("articles", [])
exams_cfg = read_json(os.path.join(DATA, "exams.json")).get("exams", [])
copy_cfg = read_json(os.path.join(DATA, "seo_copy.json"))
copy_subjects = copy_cfg.get("subjects", {})
copy_categories = copy_cfg.get("categories", {})
copy_topics = copy_cfg.get("topics", {})

SUBJECTS_BY_ID = {s["id"]: s for s in subjects}
EXAMS_BY_ID = {e["id"]: e for e in exams_cfg}


def subject_file(sid):
    return f"subject-{sid}.html"


def category_file(sid, cid):
    return f"category-{sid}-{cid}.html"


def topic_file(sid, tid):
    return f"topic-{sid}-{tid}.html"


def quiz_file(sid, tid):
    return f"quiz-{sid}-{tid}.html"


def exam_file(eid):
    return f"exam-{eid}.html"


def rel_url(filename):
    return filename[:-5] if filename.endswith(".html") else filename


def u(filename):
    """Canonical URL for a generated (or root) html file."""
    return f"{BASE}/{rel_url(filename)}"


def link_record(src, src_type, dst, dst_type, anchor):
    LINKS.append((src, src_type, dst, dst_type, anchor))


# ------------------------------------------------------- entity collection --
def all_topics(subject):
    """[(category_or_None, topic)] for a subject, manifest order preserved."""
    out = [(None, t) for t in subject.get("topics", [])]
    for c in subject.get("categories", []):
        out += [(c, t) for t in c.get("topics", [])]
    return out


def live_topics(subject):
    return [(c, t) for c, t in all_topics(subject) if t.get("available")]


def topic_question_file(topic):
    return os.path.join(ROOT, topic["file"])


def normalize_questions(raw_list):
    """Mirror of core.js normalizeQuestions() - same inputs, same results."""
    out = []
    for item in raw_list or []:
        q = dict(item or {})
        text = q.get("q", q.get("question", ""))
        options = q.get("options", q.get("opts", []))
        correct = q.get("correct", q.get("answer", q.get("key")))
        if isinstance(correct, str):
            s = correct.strip()
            if len(s) == 1 and s.isalpha():
                idx = ord(s.upper()) - 65
                correct = idx if 0 <= idx < len(options) else None
            else:
                correct = next(
                    (i for i, o in enumerate(options)
                     if str(o).strip().lower() == s.lower()), None)
        out.append({"q": str(text), "options": list(options or []),
                    "correct": correct, "explanation": q.get("explanation", "")})
    return out


def load_topic_questions(topic):
    try:
        data = read_json(topic_question_file(topic))
    except Exception as err:                     # unreadable / invalid JSON
        warn(f'{topic["file"]}: cannot read for Quiz schema ({err})')
        return []
    raw = data if isinstance(data, list) else (
        data.get("questions") or data.get("mcqs") or data.get("quiz") or [])
    return normalize_questions(raw)


def flashcards(questions):
    """Google Education Q&A nodes - same acceptance rules as assets/js/quiz.js."""
    cards = []
    for q in questions:
        text = str(q.get("q") or "").strip()
        opts = q.get("options") or []
        correct = q.get("correct")
        if not text or not isinstance(correct, int) or not (0 <= correct < len(opts)):
            continue                      # never guess an answer
        correct_text = str(opts[correct]).strip()
        expl = str(q.get("explanation") or "").strip()
        if expl and correct_text.lower() in expl.lower():
            answer = expl
        elif expl:
            answer = f"{correct_text}. {expl}"
        else:
            answer = correct_text
        cards.append({
            "@type": "Question",
            "name": text,
            "text": text,
            "eduQuestionType": "Flashcard",
            "acceptedAnswer": {"@type": "Answer", "text": answer},
        })
    return cards


def fmt_duration(total_seconds):
    if total_seconds < 60:
        return f"{int(total_seconds)} sec"
    mins = total_seconds / 60
    if mins == int(mins):
        return f"{int(mins)} min"
    return f"{mins:.1f} min"


def fmt_date(ms):
    if not ms:
        return ""
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).strftime("%d %b %Y")
    except (OverflowError, OSError, ValueError):
        return ""


def guides_for(subject_ids=(), category=None):
    """Study guides ranked by how well they match (same idea as related.js)."""
    best = []
    for a in articles:
        overlap = len(set(a.get("subjects", [])) & set(subject_ids))
        cat_hit = 1 if (category and category in (a.get("categories") or [])) else 0
        score = overlap * 10 + cat_hit
        if score:
            best.append((score, a))
    best.sort(key=lambda x: -x[0])
    return [a for _, a in best]


def exams_for(subject_id=None, category_id=None):
    out = []
    for e in exams_cfg:
        if subject_id and subject_id in (e.get("subjects") or []):
            out.append(e)
        elif category_id and category_id in (e.get("categories") or []):
            out.append(e)
    return out


def related_subjects(subject, limit=6):
    """Subjects sharing at least one exam, else the manifest order."""
    mine = {e["id"] for e in exams_for(subject_id=subject["id"])}
    scored = []
    for s in subjects:
        if s["id"] == subject["id"]:
            continue
        shared = len(mine & {e["id"] for e in exams_for(subject_id=s["id"])})
        scored.append((shared, -s.get("order", 99), s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, _, s in scored[:limit]]


def all_quizzes():
    """[(subject, category|None, topic)] for every live quiz, manifest order."""
    out = []
    for s in subjects:
        for c, t in live_topics(s):
            out.append((s, c, t))
    return out
