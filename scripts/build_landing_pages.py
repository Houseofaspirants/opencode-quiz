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
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

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


DESC_TAILS = [
    " Start practising free on House of Aspirants - no login needed.",
    " Free MCQ practice for Punjab exams.",
    " Free MCQ practice with answers.",
    " Free MCQ practice.",
    " Free practice.",
]


def fit_desc(base):
    """Pad / trim a meta description into the 140-160 character window."""
    d = " ".join(str(base).split())
    if len(d) > 160:
        d = d[:159].rsplit(" ", 1)[0].rstrip(",;:- ")
    # Top up with the LONGEST natural tail that still fits the 160 ceiling,
    # repeating with shorter tails until the 140 floor is cleared. (A single
    # `break` here is what once left 132-char descriptions below the window.)
    seen = set()
    while len(d) < 140:
        if not d.endswith((".", "!", "?", ":")):
            d += "."
        room = 160 - len(d)
        cands = [t for t in DESC_TAILS if len(t) <= room and d + t not in seen]
        if not cands:
            break
        tail = max(cands, key=len)
        seen.add(d + tail)
        d += tail
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
    """crumbs: [(label, item_url_or_None)] - None means 'this page'."""
    items = []
    for i, (label, href) in enumerate(crumbs, 1):
        item = {"@type": "ListItem", "position": i, "name": label}
        if href:
            item["item"] = href if href.startswith("http") else f"{BASE}/{href}"
        else:
            item["item"] = url
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
        hero=hero, body=body, faq=faq)


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
    """Record an emitted internal link (normalised to a root-level filename)."""
    dst = str(dst).split("#")[0].split("?")[0]
    if dst and not dst.endswith(".html"):
        dst += ".html"
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


# =========================================================== SECTION BLOCKS ==
def section_wrap(inner, pad_top=True):
    style = "" if pad_top else ' style="padding-top:0"'
    return (f'    <section class="section"{style}>\n'
            f'      <div class="container">\n{inner}\n      </div>\n    </section>')


def note_box(title, text, links=()):
    out = ['        <div class="card card-pad">', f"          <h3>{esc(title)}</h3>",
           f'          <p class="muted">{esc(text)}</p>']
    if links:
        out.append('          <div class="btn-row mt-2">')
        for label, href in links:
            out.append(f'            <a class="btn btn-sm btn-soft" href="{esc(href)}">{esc(label)}</a>')
        out.append("          </div>")
    out.append("        </div>")
    return "\n".join(out)


def cta_card(eyebrow, title, text, links):
    out = ['        <div class="card card-pad">',
           f'          <span class="eyebrow">{esc(eyebrow)}</span>',
           f"          <h2>{esc(title)}</h2>",
           f'          <p class="muted">{esc(text)}</p>',
           '          <div class="btn-row mt-3">']
    for label, href in links:
        out.append(f'            <a class="btn btn-sm btn-soft" href="{esc(href)}">{esc(label)}</a>')
    out.append("          </div>\n        </div>")
    return "\n".join(out)


def card_section(eyebrow, title, hint, items, empty_note=None, cols=3, button=None):
    """A linked card grid section, or an honest empty-state note."""
    if items:
        inner = section_head(eyebrow, title, hint, button or "") + "\n" + card_grid(items, cols)
    elif empty_note:
        inner = section_head(eyebrow, title, hint, button or "") + "\n" + empty_note
    else:
        return ""
    return section_wrap(inner)


def guide_cards(guides):
    """Guide cards keep the site-wide `.html` href convention (relative paths +
    shared chrome). Only the CANONICAL/og:url is extensionless."""
    return [(a["title"], a["description"], a["url"], "Study guide") for a in guides]


# ============================================================ SUBJECT PAGE ===
def build_subject(s):
    sid, name = s["id"], s["name"]
    filename = subject_file(sid)
    url = u(filename)
    cats = s.get("categories", [])
    topics = all_topics(s)
    live = live_topics(s)
    n_topics, n_live = len(topics), len(live)
    q_total = sum(t.get("count", 0) for _, t in topics)
    ex_list = exams_for(subject_id=sid)
    guides = guides_for([sid])
    authored = copy_subjects.get(sid, {})
    cfg_desc = s.get("description", "").strip()

    title = fit_title(f"{name} Quiz: Free MCQs for Punjab Exams",
                      f"{name} MCQs for Punjab Exams")
    if n_topics:
        description = fit_desc(
            f"Free {name} MCQs for Punjab Police, PSSSB and PPSC practice - "
            f"{n_topics} topic sets ({q_total} questions) with instant answers, "
            f"explanations and accuracy tracking.")
    else:
        description = fit_desc(
            f"Free {name} MCQs for Punjab Police, PSSSB and PPSC practice - "
            f"daily quizzes, instant answers, full explanations and accuracy tracking.")
    kw = keywords(f"{name} MCQs", f"{name} quiz", f"{name} questions",
                  "Punjab Police MCQ", "Free online MCQ test", cfg_desc)
    h1 = f"{name} MCQs for Punjab Exams"
    lead = (f"{cfg_desc.rstrip('.')} - organised into short, timed sets you can "
            f"finish between two study sessions.")
    answer = authored.get("answer") or (
        f"{name} is one of the subjects every Punjab recruitment tests. Practise it here "
        f"as short timed MCQ sets with instant answers and a full explanation after every "
        f"question, then track which lane is costing you marks.")

    # ---- intro: authored paragraphs first, generated facts after ------------
    intro = list(authored.get("intro", []))
    lane = (f" across {len(cats)} category lanes - "
            + ", ".join(c["name"] for c in cats) + " -" if cats else "")
    intro.append(
        f"{name} on House of Aspirants publishes as separate, self-contained sets{lane} "
        f"rather than one endless paper. Each set runs {SITE_Q_SECONDS} seconds per question "
        f"with four options and a written explanation, so a wrong answer teaches the next "
        f"attempt instead of only scoring it.")
    intro.append(
        f"Work it in three moves: open the daily quiz ({SITE_DAILY} questions) to find the "
        f"lane that is costing you marks, run a topic set when you want depth, and keep a "
        f"full mock test for the weekend. A set is cleared at {SITE_PASS}% accuracy, and "
        f"your subject-wise accuracy is tracked on the progress page.")
    intro.append(
        "A wrong answer lands in your bookmarks together with its explanation, so revision "
        "becomes a second pass over the same set instead of a separate chapter of notes.")
    if ex_list:
        intro.append(
            f"These are the papers {name} shows up in most: "
            + ", ".join(e["name"] for e in ex_list[:5]) + ". "
            + (f"Written guides on the portal cover the same ground: "
               + "; ".join(a["title"] for a in guides[:2]) + "." if guides else ""))
    intro_html = f'        <div class="landing-intro" data-landing="intro">\n{join_paras(intro)}\n        </div>'

    # ---- facts ---------------------------------------------------------------
    if cats:
        facts = facts_grid([("Categories", str(len(cats))), ("Topic sets", str(n_topics)),
                            ("Questions", str(q_total)), ("Live quizzes", str(n_live))])
    else:
        facts = facts_grid([("Topic sets", str(n_topics)), ("Questions", str(q_total)),
                            ("Live quizzes", str(n_live)), ("Study guides", str(len(guides)))])

    # ---- sections ------------------------------------------------------------
    body = []
    # Answer-first intro (the 250+ word block the gate measures on .landing-intro)
    body.append(section_wrap(
        section_head("About this subject", f"All about {name}",
                     "What this page holds and how to work through it.")
        + "\n" + intro_html))
    body.append(section_wrap(
        section_head("Structure", f"Inside {name}", 
                     "Every lane below is its own page - open one and practise.")
        + "\n" + (card_grid([
            (c["name"],
             (f"{len(c.get('topics', []))} topic sets, "
              f"{sum(t.get('count', 0) for t in c.get('topics', []))} questions"
              if c.get("topics") else "Category lane - topic sets publish as they are added"),
             category_file(sid, c["id"]), "") for c in cats], 3) if cats else
           card_grid([
               (t["name"], "", topic_file(sid, t["id"]),
                f"{t.get('count', 0)} MCQs" + ("" if t.get("available") else " - being written"))
               for _, t in topics], 3) if topics else
           note_box(f"{name} topic sets are being published",
                    "The first topic quizzes for this subject are still being written. "
                    "Meanwhile the daily quiz and the mock test keep the subject covered.",
                    [("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html"),
                     ("Open the subject view", f"subject.html?subject={sid}")]))))

    # Subject -> Quiz
    own_quizzes = [(t["name"], "", quiz_file(sid, t["id"]), f"{t.get('count', 0)} MCQs")
                   for _, t in live]
    other_quizzes = [(t["name"], f"From {sub['name']}", quiz_file(sub["id"], t["id"]),
                      f"{t.get('count', 0)} MCQs")
                     for sub, _c, t in all_quizzes() if sub["id"] != sid][:3]
    quiz_items = own_quizzes or other_quizzes
    quiz_section = card_section(
        "Practice", f"Related quizzes",
        ("Every published quiz in this subject, ready to start." if own_quizzes
         else "No topic quiz in this subject yet - these are the sets live on the portal right now."),
        quiz_items,
        empty_note=note_box("Try the daily quiz instead",
                            f"{SITE_DAILY} fresh questions every day, mixed from every subject.",
                            [("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html")]))
    if quiz_section:
        body.append(quiz_section)
    for _t, _b, href, _m in quiz_items:
        link_record(filename, "subject", href, "quiz", _t)

    # Subject -> Exam
    exam_section = card_section(
        "Exam relevance", f"Exams that lean on {name}",
        "Preparation papers where this subject carries real weight.",
        [(e["name"], e["summary"], exam_file(e["id"]), "") for e in ex_list],
        empty_note=note_box("How is this subject tested?",
                            "Every Punjab recruitment paper draws on general awareness. "
                            "Check the exam hub for the full list of papers this portal covers.",
                            [("All Punjab exams", "punjab-exams.html")]))
    if exam_section:
        body.append(exam_section)
    for e in ex_list:
        link_record(filename, "subject", exam_file(e["id"]), "exam", e["name"])

    # Subject -> Subject
    body.append(card_section(
        "Keep going", "Related subjects",
        "Subjects that share exams, study guides or a lane of the same paper.",
        [(r["name"], r["description"], subject_file(r["id"]), "") for r in related_subjects(s)],
        cols=3))
    for r in related_subjects(s):
        link_record(filename, "subject", subject_file(r["id"]), "subject", r["name"])

    # Study guides
    if guides:
        body.append(card_section(
            "Read next", "Study guides for this subject",
            "Long-form strategy pages that pair with the quizzes above.",
            guide_cards(guides), cols=3))

    body.append(section_wrap(cta_card(
        "Start practising", f"Practise {name} now",
        f"Open the live subject view for the full topic grid, or jump straight into "
        f"today's mixed set.",
        [(f"Open {name} view", f"subject.html?subject={sid}"),
         ("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html"),
         ("Track progress", "progress.html")]), pad_top=False))

    # ---- FAQ -----------------------------------------------------------------
    if n_topics:
        q1a = (f"{n_topics} topic sets are published for {name} right now, carrying "
               f"{q_total} questions in total. Every set shows its own count and estimated "
               f"time before you start, and new sets are added as they are verified.")
    else:
        q1a = (f"Topic sets for {name} are still being written. Until the first one lands, "
               f"the daily quiz and the full mock test keep the subject covered - both pull "
               f"from every subject on the portal.")
    if ex_list:
        names = ", ".join(e["name"] for e in ex_list[:4])
        q2a = (f"{name} is the subject these papers lean on: {names}."
               + (f" and {len(ex_list) - 4} more" if len(ex_list) > 4 else "")
               + " Each exam page on this portal lists the subjects to study and the sets to run.")
    else:
        q2a = ("Every Punjab recruitment paper draws on general awareness, so this subject "
               "sits under all of them. The exam hub lists every paper this portal covers.")
    q3a = (f"Each question is timed at {SITE_Q_SECONDS} seconds, so a {q_total}-question set "
           f"runs to about {fmt_duration(q_total * SITE_Q_SECONDS)}. Sets are cleared at "
           f"{SITE_PASS}% accuracy, and you can retake them as often as you like.") \
        if n_topics else (f"Question sets are timed at {SITE_Q_SECONDS} seconds each. Once a "
                           f"set publishes for {name} its length and estimated time appear "
                           f"here before you start.")
    q4a = ("No. You can open any quiz and answer questions immediately. A Google sign-in is "
           "optional and is only needed to save scores, bookmarks, streaks and progress "
           "across devices.")
    faqs = [
        (f"How many {name} questions are in this library?", q1a),
        (f"Which exams test {name}?", q2a),
        (f"How long does a {name} quiz take?", q3a),
        ("Do I need an account to practise?", q4a),
    ]

    crumbs = [("Home", "index.html", f"{BASE}/"),
              ("Subjects", "subject.html", f"{BASE}/subject"),
              (name, None, None)]
    ld = [
        ld_script({"@context": "https://schema.org", "@graph": [
            webpage_ld(url, h1, description, f"{url}#breadcrumb",
                       has_part=[{"@id": f"{url}#faq"}]),
            crumb_ld(url, [(l, i) for l, _, i in crumbs]),
            faq_ld(url, faqs),
        ]})
    ]

    html = render_page(
        title=title, description=description, kw=kw, url=url, ld_blocks=ld,
        crumbs=[(l, h) for l, h, _ in crumbs], eyebrow="Subject", h1=h1, lead=lead,
        answer=answer, facts=facts,
        body="\n".join(b for b in body if b),
        faq=faq_section("Questions", f"{name} - common questions",
                        "Answered the way the portal actually behaves.", faqs))

    write_page(filename, html)
    register(filename, url, "subject", sid, title, description, h1, words(intro_html),
             {"WebPage", "BreadcrumbList", "FAQPage"})
    info(f"subject  {filename}  intro={words(intro_html)}w  faq={len(faqs)}")
    return filename


# =========================================================== CATEGORY PAGE ===
def build_category(s, c):
    sid, cid, name = s["id"], c["id"], c["name"]
    filename = category_file(sid, cid)
    url = u(filename)
    topics = c.get("topics", [])
    live = [t for t in topics if t.get("available")]
    q_total = sum(t.get("count", 0) for t in topics)
    ex_list = exams_for(category_id=cid)
    guides = guides_for([sid], category=cid)
    authored = copy_categories.get(cid, {})

    title = fit_title(f"{name} Quiz: {s['name']} MCQs for Punjab Exams",
                      f"{name} MCQs for Punjab Exams")
    description = fit_desc(
        f"Free {name} MCQs inside {s['name']} - {len(topics)} topic sets ({q_total} questions) "
        f"with instant answers, explanations and exam-relevant practice.") if topics else \
        fit_desc(f"Free {name} MCQs inside {s['name']} - topic sets publish as they are "
                 f"verified, with instant answers, explanations and exam-relevant practice.")
    kw = keywords(f"{name} MCQs", f"{name} questions", f"{s['name']} quiz",
                  "Punjab Police MCQ", "Free online MCQ test")
    h1 = f"{name} MCQs for Punjab Exams"
    lead = (f"A focused lane inside {s['name']} - one folder, one set of facts, "
            f"and a short quiz to prove you know them.")
    answer = authored.get("answer") or (
        f"{name} is a lane inside {s['name']}. Practise it here as short timed MCQ sets with "
        f"four options, an instant result and a full explanation after every question.")

    intro = list(authored.get("intro", []))
    intro.append(
        f"This lane sits inside {s['name']} ({len(s.get('categories', []))} lanes in total), "
        f"so it stays narrow on purpose: {len(topics)} topic sets and {q_total} questions "
        f"currently publish under {name}. Every question is timed at {SITE_Q_SECONDS} "
        f"seconds, carries four options and explains why the right answer is right.")
    intro.append(
        f"Run a set untimed first to find the gaps, then repeat it against the clock. The "
        f"questions you miss twice are your revision list - keep them to one line each and "
        f"revise the file the night before the paper.")
    if ex_list:
        intro.append(
            f"Papers that ask for it: {', '.join(e['name'] for e in ex_list[:4])}.")
    intro_html = f'        <div class="landing-intro" data-landing="intro">\n{join_paras(intro)}\n        </div>'

    facts = facts_grid([("Topic sets", str(len(topics))), ("Questions", str(q_total)),
                        ("Parent subject", s["name"]),
                        ("Exams asking", str(len(ex_list)))])

    body = []
    # Answer-first intro (measured on .landing-intro by the gate)
    body.append(section_wrap(
        section_head("About this category", f"All about {name}",
                     f"Where this lane sits inside {s['name']}.")
        + "\n" + intro_html))
    body.append(section_wrap(
        section_head("Structure", f"Topics in {name}",
                     "Each topic opens its own landing page, then the quiz itself.")
        + "\n" + (card_grid([(t["name"], "", topic_file(sid, t["id"]),
                              f"{t.get('count', 0)} MCQs" + ("" if t.get("available")
                                                             else " - being written"))
                             for t in topics], 3) if topics else
                   note_box(f"{name} topic sets are being published",
                            "No topic file lives in this folder yet. Add one and the build "
                            "detects it automatically - nothing else to touch.",
                            [("Back to " + s["name"], subject_file(sid)),
                             ("Daily Quiz", "quiz.html?mode=daily")]))))
    for t in topics:
        link_record(filename, "category", topic_file(sid, t["id"]), "topic", t["name"])

    own_quizzes = [(t["name"], "", quiz_file(sid, t["id"]), f"{t.get('count',0)} MCQs")
                   for t in live]
    other = [(t["name"], f"From {sub['name']}", quiz_file(sub["id"], t["id"]),
              f"{t.get('count',0)} MCQs") for sub, _c, t in all_quizzes()][:3]
    qs = own_quizzes or other
    body.append(card_section("Practice", f"Related quizzes - {name}",
                             "Start with the sets inside this lane, then the rest of the portal.",
                             qs,
                             empty_note=note_box("Nothing live in this lane yet",
                                                 "The daily quiz still mixes in this subject.",
                                                 [("Daily Quiz", "quiz.html?mode=daily"),
                                                  ("Open " + s["name"], subject_file(sid))])))
    for _t, _b, href, _m in qs:
        link_record(filename, "category", href, "quiz", _t)

    if ex_list:
        body.append(card_section(
            "Exam relevance", f"Exams that ask {name}",
            "Where this lane actually shows up on paper.",
            [(e["name"], e["summary"], exam_file(e["id"]), "") for e in ex_list]))
        for e in ex_list:
            link_record(filename, "category", exam_file(e["id"]), "exam", e["name"])

    body.append(card_section(
        "Keep going", "Related subjects",
        "Other lanes of the same papers.",
        [(r["name"], r["description"], subject_file(r["id"]), "") for r in related_subjects(s)]))
    for r in related_subjects(s):
        link_record(filename, "category", subject_file(r["id"]), "subject", r["name"])

    if guides:
        body.append(card_section("Read next", "Study guides",
                                 "Guides that rank this lane highest.", guide_cards(guides)))

    body.append(section_wrap(cta_card(
        "Start practising", f"Practise {name} now",
        "Open the live subject view with this lane pre-selected, or take today's mixed set.",
        [(f"Open {s['name']} view", f"subject.html?subject={sid}&category={cid}"),
         ("Parent subject", subject_file(sid)), ("Daily Quiz", "quiz.html?mode=daily")]),
        pad_top=False))

    if topics:
        q1a = (f"{len(topics)} topic sets publish under {name}, carrying {q_total} questions "
               f"in total. Each set lists its count and estimated time before you start.")
    else:
        q1a = (f"No topic set has been added to the {name} folder yet. The build scans that "
               f"folder on every deploy, so the first file dropped in appears here "
               f"automatically.")
    q2a = (f"{', '.join(e['name'] for e in ex_list[:4])} draw on {name}. Each exam page on "
           f"this portal links straight back to the lanes it needs." if ex_list else
           f"Every Punjab recruitment paper touches this lane, so it is worth a weekly set "
           f"regardless of which exam you are sitting.")
    q3a = (f"{name} is one of {len(s.get('categories', []))} lanes inside {s['name']}. Open "
           f"the subject page to see every lane, its exam links and the guides that cover it.")
    faqs = [
        (f"What is covered in {name}?", q1a),
        (f"Which exams ask {name} questions?", q2a),
        (f"Where do I find the rest of {s['name']}?", q3a),
    ]

    crumbs = [("Home", "index.html", f"{BASE}/"),
              ("Subjects", "subject.html", f"{BASE}/subject"),
              (s["name"], subject_file(sid), u(subject_file(sid))),
              (name, None, None)]
    ld = [ld_script({"@context": "https://schema.org", "@graph": [
        webpage_ld(url, h1, description, f"{url}#breadcrumb",
                   has_part=[{"@id": f"{url}#faq"}]),
        crumb_ld(url, [(l, i) for l, _, i in crumbs]),
        faq_ld(url, faqs),
    ]})]

    html = render_page(
        title=title, description=description, kw=kw, url=url, ld_blocks=ld,
        crumbs=[(l, h) for l, h, _ in crumbs], eyebrow="Category", h1=h1, lead=lead,
        answer=answer, facts=facts, body="\n".join(b for b in body if b),
        faq=faq_section("Questions", f"{name} - common questions", "", faqs))

    write_page(filename, html)
    register(filename, url, "category", f"{sid}/{cid}", title, description, h1,
             words(intro_html), {"WebPage", "BreadcrumbList", "FAQPage"})
    info(f"category {filename}  intro={words(intro_html)}w  faq={len(faqs)}")
    return filename


# ============================================================= TOPIC PAGE ====
def difficulty_label(questions):
    """Per-question tags when the file has them, otherwise an honest 'Mixed'."""
    levels = [str(q.get("difficulty") or "").strip() for q in questions]
    levels = [l for l in levels if l]
    if not levels:
        return "Mixed"
    uniq = sorted({l.lower() for l in levels})
    if len(uniq) == 1:
        return levels[0].capitalize()
    return "Mixed"


def build_topic(s, c, t):
    sid, tid = s["id"], t["id"]
    filename = topic_file(sid, tid)
    url = u(filename)
    name = t["name"]
    count = int(t.get("count") or 0)
    available = bool(t.get("available"))
    qs = load_topic_questions(t) if available else []
    cards_nodes = flashcards(qs)
    est = fmt_duration(count * SITE_Q_SECONDS)
    updated = fmt_date(t.get("updatedAt"))
    diff = difficulty_label(qs)
    cat_name = c["name"] if c else ""
    key = f"{sid}/{tid}"
    authored = copy_topics.get(key, {})

    ex_list = exams_for(category_id=c["id"]) if c else []
    if not ex_list:
        ex_list = exams_for(subject_id=sid)

    title = fit_title(f"{name}: Topic Guide and MCQ Practice",
                      f"{name} MCQ Practice")
    description = fit_desc(
        f"{name} ({s['name']}) - why it is asked, what to expect, expected questions and "
        f"{count} free MCQs with instant answers and full explanations.")
    kw = keywords(name, f"{name} MCQs", f"{s['name']} quiz",
                  f"{cat_name} MCQs" if cat_name else "", "Punjab exam MCQs")
    h1 = f"{name} - Topic Guide and MCQs"
    lead = (f"Part of {s['name']}" + (f" > {cat_name}" if cat_name else "")
            + f" - {count} questions, about {est}, with an explanation after every answer.")
    answer = authored.get("answer") or (
        f"{name} is a topic inside {s['name']}"
        + (f" ({cat_name})" if cat_name else "")
        + f". It runs {count} MCQs at {SITE_Q_SECONDS} seconds each - roughly {est} - and "
          f"every question explains its answer the moment you submit it.")

    intro = list(authored.get("intro", []))
    if not intro:
        intro.append(
            f"{name} sits inside {s['name']}"
            + (f", under the {cat_name} lane" if cat_name else "")
            + f", and the portal keeps it as one self-contained set: {count} questions, four "
              f"options each, {SITE_Q_SECONDS} seconds on the clock and a written explanation "
              f"behind every answer.")
        intro.append(
            "Attempt it untimed first to find the gaps, read why each distractor is wrong, "
            "then repeat the same set against the clock. The questions you miss twice are "
            "the ones worth writing down.")
    intro_html = f'        <div class="landing-intro" data-landing="intro">\n{join_paras(intro)}\n        </div>'

    facts = facts_grid([("Question count", str(count)), ("Estimated time", f"about {est}"),
                        ("Difficulty", diff),
                        ("Last updated", updated or "on next build")])

    topic_rel = [(c2, t2) for c2, t2 in all_topics(s) if t2["id"] != tid]
    other_quizzes = [(t2["name"], f"From {sub['name']}", quiz_file(sub["id"], t2["id"]),
                      f"{t2.get('count',0)} MCQs")
                     for sub, _c, t2 in all_quizzes() if not (sub["id"] == sid and t2["id"] == tid)]

    body = []
    body.append(section_wrap(
        section_head("Topic introduction", f"What {name} covers",
                     "The shape of the set before you start it.")
        + "\n" + intro_html))

    body.append(section_wrap(section_head(
        "Why it matters", f"Why {name} is worth the hours",
        "Where the marks actually come from.")
        + "\n" + join_paras([authored.get("why") or (
            f"{name} is factual rather than analytical: you either recall it in seconds or "
            f"you lose the mark to somebody who did. That makes it one of the cheapest "
            f"sections to convert - a handful of short sittings usually settles the whole "
            f"cluster.")])))

    if ex_list:
        body.append(card_section(
            "Exam relevance", f"Exams where {name} matters",
            "Derived from the subject and lane this topic belongs to.",
            [(e["name"], e["summary"], exam_file(e["id"]), "") for e in ex_list]))
        for e in ex_list:
            link_record(filename, "topic", exam_file(e["id"]), "exam", e["name"])

    body.append(section_wrap(section_head(
        "Expected questions", f"Expected questions from {name}",
        "What an examiner usually reaches for in this cluster.")
        + "\n" + join_paras([authored.get("expected") or (
            f"Expect one-line recall questions - definitions, stand-for expansions, "
            f"identifiers and the ordering of things. Practise the wording as well as the "
            f"concept: these papers test terminology, and the set above uses the same "
            f"four-option shape they do.")])
        + "\n" + cta_card("Daily habit", "Keep the Expected MCQs habit running",
                          f"{SITE_DAILY} fresh mixed questions a day, plus the current-affairs "
                          f"sets examiners keep reusing.",
                          [("Daily Quiz", "quiz.html?mode=daily"),
                           ("Expected MCQs", "subject.html?subject=current-affairs")]),
        pad_top=False))

    body.append(section_wrap(section_head(
        "Previous year questions", "Previous Year Questions",
        "How this topic behaves in real papers.")
        + "\n" + join_paras([authored.get("pyq") or (
            "Past papers reuse clusters like this almost verbatim across years and posts. "
            "Run the same set until every distractor is familiar - previous-year style "
            "questions stop being recall and start being free marks.")])
        + "\n" + note_box("Where the previous-year sets live",
                          "The portal's previous-year practice runs through the General "
                          "Knowledge lane and the daily mixed quiz.",
                          [("Previous Year Questions", "subject.html?subject=gk"),
                           ("Daily Quiz", "quiz.html?mode=daily")]),
        pad_top=False))

    if topic_rel:
        rel_items = [(t2["name"], "", topic_file(sid, t2["id"]),
                      f"{t2.get('count',0)} MCQs") for _c2, t2 in topic_rel]
        rel_items += other_quizzes[:2]
    else:
        rel_items = other_quizzes[:3]
    body.append(card_section(
        "Keep going", "Related topics",
        "Neighbouring sets in this subject, then the rest of the portal.",
        rel_items,
        empty_note=note_box("More topics are on the way",
                            "This is the first topic set published on the portal. The daily "
                            "quiz keeps the rest of the syllabus covered meanwhile.",
                            [("Daily Quiz", "quiz.html?mode=daily"),
                             ("Open " + s["name"], subject_file(sid))])))
    for _n, _b, href, _m in rel_items:
        link_record(filename, "topic", href, "topic", _n)

    body.append(section_wrap(cta_card(
        "Start practising", f"Take the {name} quiz",
        f"{count} questions, about {est}, instant scoring and a full review at the end.",
        [(f"Start {name} quiz", quiz_file(sid, tid)),
         (f"{s['name']} page", subject_file(sid)),
         ("Daily Quiz", "quiz.html?mode=daily"),
         ("Mock Tests", "mock.html")]), pad_top=False))
    link_record(filename, "topic", quiz_file(sid, tid), "quiz", f"Start {name} quiz")
    link_record(filename, "topic", subject_file(sid), "subject", s["name"])

    if count:
        q1a = (f"{name} runs {count} questions - about {est} at {SITE_Q_SECONDS} seconds each. "
               f"The set clears at {SITE_PASS}% and you can retake it as often as you like.")
    else:
        q1a = (f"The first file for this topic has not been added yet. The build scans the "
               f"questions folder on every deploy, so the set appears here - and in the quiz "
               f"below - as soon as it is published.")
    q2a = (f"The set answers that: each question carries four options and a full explanation, "
           f"so you learn the wording an examiner uses, not just the fact behind it.")
    q3a = (f"Open the quiz page above, or start from the {s['name']} subject page if you want "
           f"to drill neighbouring lanes in the same sitting.")
    q4a = (f"Scores, bookmarks and streaks need the optional Google sign-in. Opening the set "
           f"and answering questions does not.")
    faqs = [
        (f"How long is the {name} quiz?", q1a),
        (f"What kind of questions does {name} ask?", q2a),
        (f"Where else can I practise {s['name']}?", q3a),
        ("Do my scores save?", q4a),
    ]

    crumbs = [("Home", "index.html", f"{BASE}/"),
              ("Subjects", "subject.html", f"{BASE}/subject"),
              (s["name"], subject_file(sid), u(subject_file(sid)))]
    if c:
        crumbs.append((cat_name, category_file(sid, c["id"]), u(category_file(sid, c["id"]))))
    crumbs.append((name, None, None))

    ld = [ld_script({"@context": "https://schema.org", "@graph": [
        webpage_ld(url, h1, description, f"{url}#breadcrumb",
                   has_part=[{"@id": f"{url}#faq"}]),
        crumb_ld(url, [(l, i) for l, _, i in crumbs]),
        faq_ld(url, faqs),
    ]})]

    html = render_page(
        title=title, description=description, kw=kw, url=url, ld_blocks=ld,
        crumbs=[(l, h) for l, h, _ in crumbs], eyebrow="Topic", h1=h1, lead=lead,
        answer=answer, facts=facts, body="\n".join(b for b in body if b),
        faq=faq_section("Questions", f"{name} - common questions",
                        "Answered against the set as it is published today.", faqs))

    write_page(filename, html)
    register(filename, url, "topic", key, title, description, h1, words(intro_html),
             {"WebPage", "BreadcrumbList", "FAQPage"})
    info(f"topic    {filename}  {count}q  intro={words(intro_html)}w  faq={len(faqs)}")
    return filename


# =============================================================== QUIZ PAGE ===
def build_quiz(s, c, t):
    """quiz-<subject>-<topic>.html = quiz.html + unique head + static schema
    + landing sections + a seed object. The engine itself is untouched."""
    sid, tid = s["id"], t["id"]
    filename = quiz_file(sid, tid)
    key = f"{sid}/{tid}"
    url = u(filename)
    name = t["name"]
    count = int(t.get("count") or 0)
    available = bool(t.get("available"))
    qs = load_topic_questions(t) if available else []
    cards_nodes = flashcards(qs)
    est = fmt_duration(count * SITE_Q_SECONDS)
    updated = fmt_date(t.get("updatedAt"))
    diff = difficulty_label(qs)

    title = fit_title(f"{name} Quiz ({count} MCQs) - Free Online Test",
                      f"{name} Quiz - Free MCQs")
    description = fit_desc(
        f"Practise {name} online: {count} MCQs in about {est}, instant scoring, question "
        f"palette and a full answer review. Free topic quiz for Punjab exam preparation.")
    kw = keywords(f"{name} quiz", f"{name} MCQs", f"{s['name']} MCQs",
                  "MCQ quiz with timer", "Free online MCQ test")
    h1 = name
    lead = (f"{count} questions from {s['name']}"
            + (f" > {c['name']}" if c else "")
            + f" - {SITE_Q_SECONDS} seconds a question, about {est} in total.")
    answer = (f"{name} is a timed topic quiz: {count} questions at {SITE_Q_SECONDS} seconds "
              f"each, about {est} in all. You get a question palette, instant scoring, a "
              f"{SITE_PASS}% pass mark and a full answer review - free, and no sign-in is "
              f"needed to start.")

    faqs = [
        (f"How many questions are in the {name} quiz?",
         f"{count} questions, about {est} at {SITE_Q_SECONDS} seconds each. Every question "
         f"has four options, and the review screen shows the explanation behind each answer."),
        ("What counts as a pass?",
         f"A set is cleared at {SITE_PASS}% - that is {max(1, round(count * SITE_PASS / 100))} "
         f"of {count} questions. You can retake it immediately, as many times as you like."),
        ("Can I pause, bookmark or retake the quiz?",
         "Yes. Answers autosave, any question can be bookmarked or marked for review, and "
         "Restart quiz clears the session so you can run the set again from zero."),
        ("Do I need an account to start a quiz?",
         "No. You can open any quiz and answer questions immediately. A Google sign-in is "
         "optional and is only needed to save scores, bookmarks, streaks and progress across "
         "devices."),
    ]

    crumbs = [("Home", "index.html", f"{BASE}/"),
              ("Subjects", "subject.html", f"{BASE}/subject"),
              (s["name"], subject_file(sid), u(subject_file(sid)))]
    if c:
        crumbs.append((c["name"], category_file(sid, c["id"]), u(category_file(sid, c["id"]))))
    crumbs.append((name, None, None))

    # ---- sections inserted AFTER the engine, before the ad slot -------------
    share_enc_url = quote(url, safe="")
    share_enc_title = quote(f"{name} Quiz - House of Aspirants", safe="")
    share_enc_both = quote(f"{name} Quiz {url}", safe="")

    quiz_list = all_quizzes()
    pos = next((i for i, (qsub, _qc, qt) in enumerate(quiz_list)
                if qsub["id"] == sid and qt["id"] == tid), -1)
    neighbours = []
    if pos > 0:
        qsub, _qc, qt = quiz_list[pos - 1]
        neighbours.append((f"\\u2190 Previous: {qt['name']}",
                           f"From {qsub['name']}", quiz_file(qsub["id"], qt["id"]),
                           f"{qt.get('count',0)} MCQs"))
    if 0 <= pos < len(quiz_list) - 1:
        qsub, _qc, qt = quiz_list[pos + 1]
        neighbours.append((f"Next: {qt['name']} \\u2192",
                           f"From {qsub['name']}", quiz_file(qsub["id"], qt["id"]),
                           f"{qt.get('count',0)} MCQs"))
    related = [(qt["name"], f"From {qsub['name']}", quiz_file(qsub["id"], qt["id"]),
                f"{qt.get('count',0)} MCQs")
               for qsub, _qc, qt in quiz_list
               if not (qsub["id"] == sid and qt["id"] == tid)][:3]

    bottom = []
    bottom.append(section_wrap(
        section_head("About this quiz", f"About the {name} quiz",
                     "What you are about to attempt, in one screen.")
        + "\n" + '        <div class="answer-box">\n'
        + '          <span class="ab-label">Quick answer</span>\n'
        + f"          <p>{esc(answer)}</p>\n        </div>\n"
        + '        <div class="landing-intro" data-landing="intro">\n'
        + join_paras([
            f"The set pulls {count} questions from {s['name']}"
            + (f", under the {c['name']} lane" if c else "")
            + f", each timed at {SITE_Q_SECONDS} seconds. A question palette in the sidebar "
              f"tracks answered, skipped and marked questions, progress autosaves if you "
              f"leave mid-quiz, and the final screen replays every answer with its "
              f"explanation.",
            (f"Difficulty is reported as {diff} because "
             + ("the file already tags its questions by level."
                if diff != "Mixed" else
                "this set does not carry per-question difficulty tags yet - treat your first "
                "timed attempt as the baseline and let the score decide.")
             + f" The last build refreshed this page on {updated or 'the next deploy'}."),
        ]) + "\n        </div>",
        pad_top=False))

    bottom.append(section_wrap(
        section_head("Share", f"Share the {name} quiz",
                     "Send it to somebody preparing for the same paper.")
        + "\n" + '        <div class="btn-row mt-3">'
        + f'\n          <a class="btn btn-sm btn-soft" href="https://t.me/share/url?url={share_enc_url}&amp;text={share_enc_title}" target="_blank" rel="noopener">✈ Telegram</a>'
        + f'\n          <a class="btn btn-sm btn-soft" href="https://wa.me/?text={share_enc_both}" target="_blank" rel="noopener">📱 WhatsApp</a>'
        + f'\n          <a class="btn btn-sm btn-soft" href="https://twitter.com/intent/tweet?url={share_enc_url}&amp;text={share_enc_title}" target="_blank" rel="noopener">𝕏 Twitter</a>'
        + f'\n          <a class="btn btn-sm btn-soft" href="mailto:?subject={share_enc_title}&amp;body={share_enc_both}">✉ Email</a>'
        + f'\n          <button class="btn btn-sm btn-soft" type="button" data-copy-url="{esc(url)}">🔗 Copy link</button>'
        + "\n        </div>", pad_top=False))

    nav_section = card_section(
        "Quiz navigation", "Previous and next quizzes",
        "Ordered by subject across every published set.",
        neighbours,
        empty_note=note_box("This is the first published quiz",
                            "New sets are added as their question files are verified - the "
                            "quiz above stays at the front of the queue.",
                            [("All quizzes start here", subject_file(sid)),
                             ("Daily Quiz", "quiz.html?mode=daily")]))
    if nav_section:
        bottom.append(nav_section)
    for _n, _b, href, _m in neighbours:
        link_record(filename, "quiz", href, "quiz", _n)

    related_section = card_section(
        "Keep going", "Related quizzes",
        "Other sets on the portal, then the subject they belong to.",
        related,
        empty_note=note_box("More quizzes are on the way",
                            "The daily quiz and the full mock test cover the rest of the "
                            "syllabus in the meantime.",
                            [("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html")]))
    if related_section:
        bottom.append(related_section)
    for _n, _b, href, _m in related:
        link_record(filename, "quiz", href, "quiz", _n)

    bottom.append(section_wrap(cta_card(
        "Study path", f"Study {s['name']} next",
        f"The quiz above sits inside {s['name']}"
        + (f" > {c['name']}" if c else "")
        + ". The subject page lists every lane, exam link and guide that goes with it.",
        [(f"{s['name']} page", subject_file(sid)),
         ("Topic guide", topic_file(sid, tid)),
         ("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html")]),
        pad_top=False))
    link_record(filename, "quiz", subject_file(sid), "subject", s["name"])
    link_record(filename, "quiz", topic_file(sid, tid), "topic", f"{name} guide")

    bottom.append(faq_section("Questions", f"{name} quiz - common questions",
                              "How the portal runs this set.", faqs))

    # ---- static JSON-LD (Education Q&A) -------------------------------------
    minutes = max(1, round(count * SITE_Q_SECONDS / 60)) if count else 0
    quiz_node = {
        "@type": "Quiz",
        "@id": f"{url}#quiz",
        "name": f"{name} Quiz",
        "url": url,
        "description": description,
        "about": {"@type": "Thing", "name": s["name"]},
        "inLanguage": "en-IN",
        "isAccessibleForFree": True,
        "provider": {"@id": f"{BASE}/#organization"},
        "hasPart": cards_nodes,
    }
    if minutes:
        quiz_node["timeRequired"] = f"PT{minutes}M"
    graph = [
        webpage_ld(url, h1, description, f"{url}#breadcrumb",
                   has_part=[{"@id": f"{url}#quiz"}, {"@id": f"{url}#faq"}]),
        crumb_ld(url, [(l, i) for l, _, i in crumbs]),
        quiz_node,
        faq_ld(url, faqs),
    ]

    # ---- surgery on the quiz.html template ---------------------------------
    src_path = os.path.join(ROOT, "quiz.html")
    with open(src_path, "r", encoding="utf-8") as fh:
        page = fh.read()

    def rep(pattern, replacement, label):
        nonlocal page
        page, n = re.subn(pattern, (lambda _m: replacement), page, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"quiz.html template marker missing: {label}")

    rep(r"<title>.*?</title>", f"<title>{esc(title)}</title>", "title")
    rep(r'<meta name="description" content="[^"]*">',
        f'<meta name="description" content="{esc(description)}">', "description")
    rep(r'<meta name="keywords" content="[^"]*">',
        f'<meta name="keywords" content="{esc(kw)}">', "keywords")
    rep(r'<meta property="og:url" content="[^"]*">',
        f'<meta property="og:url" content="{url}">', "og:url")
    rep(r'<meta property="og:title" content="[^"]*">',
        f'<meta property="og:title" content="{esc(title)}">', "og:title")
    rep(r'<meta property="og:description" content="[^"]*">',
        f'<meta property="og:description" content="{esc(description)}">', "og:description")
    rep(r'<meta name="twitter:title" content="[^"]*">',
        f'<meta name="twitter:title" content="{esc(title)}">', "twitter:title")
    rep(r'<meta name="twitter:description" content="[^"]*">',
        f'<meta name="twitter:description" content="{esc(description)}">',
        "twitter:description")
    rep(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">',
        "canonical")
    rep(r'<h1 class="quiz-title" id="quizTitle">.*?</h1>',
        f'<h1 class="quiz-title" id="quizTitle">{esc(name)}</h1>', "h1")

    # runtime placeholder stays empty: the static graph above owns the schema
    ld_static = ld_script({"@context": "https://schema.org", "@graph": graph})
    rep(r'<script type="application/ld\+json" id="ldDynamic">.*?</script>',
        ld_static + '\n  <script type="application/ld+json" id="ldDynamic">\n  </script>',
        "ldDynamic")

    top_block = (
        '    <div class="container" style="padding-top:18px">\n'
        + crumb_nav([(l, h) for l, h, _ in crumbs])
        + f'\n      <p class="text-sm muted mt-2"><b>Question count:</b> {count}'
        + f' · <b>Estimated time:</b> about {est} · <b>Difficulty:</b> {diff}'
        + f' · <b>Last updated:</b> {esc(updated or "next build")}</p>\n    </div>\n\n')
    rep(r'<main id="main">\n', '<main id="main">\n' + top_block, "main")

    ad_anchor = ('\n    <section class="section" style="padding-top:0">\n'
                 '      <div class="container">\n        <div class="ad-slot">')
    if ad_anchor not in page:
        raise RuntimeError("quiz.html template marker missing: ad slot")
    page = page.replace(ad_anchor, "\n" + "\n".join(bottom) + ad_anchor, 1)

    # Only the four fields quiz.js actually reads (see "0. BOOT" in quiz.js);
    # title/description live in this page's static <head> instead.
    seed = json.dumps({
        "subject": sid, "topic": tid,
        "category": (c["id"] if c else None),
        "canonical": url,
    }, ensure_ascii=False)
    seed_block = (
        '  <script>\n'
        '    /* Programmatic SEO landing-page seed, written by '
        'scripts/build_landing_pages.py. quiz.js reads it at boot (see "0. BOOT") so this\n'
        '       page runs as a topic quiz with no query string, keeps this page\'s static\n'
        '       metadata, and never re-emits schema over the static graph in the head. */\n'
        f'    window.__HOA_QUIZ_SEED = {seed};\n  </script>\n')
    anchor = '  <script src="assets/js/quiz.js" defer></script>'
    if anchor not in page:
        raise RuntimeError("quiz.html template marker missing: quiz.js script tag")
    page = page.replace(anchor, seed_block + anchor, 1)

    copy_block = (
        '  <script>\n'
        '    document.querySelectorAll("[data-copy-url]").forEach(function (btn) {\n'
        '      btn.addEventListener("click", function () {\n'
        '        var link = btn.getAttribute("data-copy-url");\n'
        '        if (navigator.clipboard && navigator.clipboard.writeText) {\n'
        '          navigator.clipboard.writeText(link).then(function () {\n'
        '            btn.textContent = "Copied \\u2713";\n'
        '          });\n'
        '        }\n'
        '      });\n'
        '    });\n'
        '  </script>\n')
    page = page.replace("</body>", copy_block + "</body>", 1)

    write_page(filename, page)
    register(filename, url, "quiz", key, title, description, h1, 0,
             {"WebPage", "BreadcrumbList", "FAQPage", "Quiz"})
    info(f"quiz     {filename}  {count}q  flashcards={len(cards_nodes)}  faq={len(faqs)}")
    return filename


# =============================================================== EXAM PAGE ===
def build_exam(e):
    eid, name = e["id"], e["name"]
    filename = exam_file(eid)
    url = u(filename)
    summary = e.get("summary", "").strip()
    subj_ids = [sid for sid in (e.get("subjects") or []) if sid in SUBJECTS_BY_ID]
    cat_ids = [cid for cid in (e.get("categories") or []) if cid]
    exam_subjects = [SUBJECTS_BY_ID[sid] for sid in subj_ids]
    ex_guides = guides_for(subj_ids)

    derived = []
    for s in exam_subjects:
        for c, t in live_topics(s):
            if cat_ids and c and c["id"] not in cat_ids and subj_ids:
                continue
            derived.append((s, c, t))
    derived = derived[:6]
    related = [x for x in exams_cfg
               if x["id"] != eid
               and (set(x.get("subjects") or []) & set(subj_ids)
                    or set(x.get("categories") or []) & set(cat_ids))][:4]

    title = fit_title(f"{name}: Preparation, Subjects and Free MCQs",
                      f"{name}: Preparation and Free MCQs")
    description = fit_desc(
        f"Prepare for {name} - which subjects to study, which topic quizzes to run and the "
        f"free MCQ sets that cover them on House of Aspirants.")
    kw = keywords(f"{name} preparation", f"{name} syllabus", f"{name} MCQs",
                  "Punjab government exam", "Free online MCQ test")
    h1 = f"{name} - Preparation and Free MCQs"
    lead = (f"What to study for {name}, in the order that scores: subjects first, topic "
            f"quizzes second, mock tests last.")
    answer = (f"To prepare for {name}, study the subjects it leans on"
              + (f" - {', '.join(s['name'] for s in exam_subjects[:3])}" if exam_subjects else "")
              + f", run their topic quizzes as timed sets, then finish with a full mock test. "
                f"Every part of that route links out from this page.")

    intro = [summary] if summary else []
    if exam_subjects:
        intro.append(
            f"{name} preparation on this portal starts from the subjects it actually tests: "
            + ", ".join(f"{s['name']}" for s in exam_subjects)
            + (f" (with {len(cat_ids)} lanes called out specifically)"
               if cat_ids else "")
            + ". Each subject page below lays out its categories, the quiz sets inside them "
              "and the other exams that lean on the same material, so the route from exam to "
              "question set takes two clicks.")
        intro.append(
            "Practise in the order the marks come: untimed topic sets until the pattern is "
            f"familiar, then the same sets against the {SITE_Q_SECONDS}-second clock, then a "
            f"full mock test at {SITE_PASS}% to clear. Wrong answers save themselves to "
            "bookmarks, so revision stays inside the tool you practise in.")
    else:
        intro.append(
            f"{name} papers are syllabus-heavy, so this portal does not guess at a subject "
            "list for them. The route below still works: pick the study guide that matches "
            "your timeline, run the subject library as short timed sets, and finish with a "
            "full mock test to find the lane costing you marks.")
        intro.append(
            f"Every set is timed at {SITE_Q_SECONDS} seconds a question, clears at "
            f"{SITE_PASS}% and explains each answer the moment you submit it.")
    intro_html = f'        <div class="landing-intro" data-landing="intro">\n{join_paras(intro)}\n        </div>'

    facts = facts_grid([("Subjects mapped", str(len(exam_subjects))),
                        ("Topic quizzes", str(len(derived))),
                        ("Study guides", str(len(ex_guides))),
                        ("Related exams", str(len(related)))])

    body = []
    # Answer-first intro (measured on .landing-intro by the gate)
    body.append(section_wrap(
        section_head("About this exam", f"Preparing for {name}",
                     "Why this paper is on the portal and what to run for it.")
        + "\n" + intro_html))
    body.append(section_wrap(
        section_head("Start here", f"What to study for {name}",
                     ("Subjects first - every one opens its own landing page."
                      if exam_subjects else
                      "This paper has no subject list in the exam config yet, so every "
                      "subject the portal covers is offered below - nothing is guessed."))
        + "\n" + card_grid([(s["name"], s["description"], subject_file(s["id"]),
                             "" if exam_subjects else "all subjects")
                            for s in (exam_subjects or subjects)], 3)))
    for s in (exam_subjects or subjects):
        link_record(filename, "exam", subject_file(s["id"]), "subject", s["name"])

    if derived:
        body.append(card_section(
            "Question sets", f"Topic quizzes for {name}",
            "Derived from the subjects and lanes this paper leans on.",
            [(f"{t['name']}", f"{sub['name']}" + (f" > {c['name']}" if c else ""),
              topic_file(sub["id"], t["id"]), f"{t.get('count',0)} MCQs")
             for sub, c, t in derived]))
        for sub, c, t in derived:
            link_record(filename, "exam", topic_file(sub["id"], t["id"]), "topic", t["name"])
    else:
        body.append(section_wrap(note_box(
            "No topic file matches this paper yet",
            "Topic sets are added as question files are verified. Until then the daily quiz "
            "and the mock test still cover the general sections.",
            [("Daily Quiz", "quiz.html?mode=daily"), ("Mock Tests", "mock.html")])))

    if ex_guides:
        body.append(card_section("Read next", f"Study guides for {name}",
                                 "Written strategy that pairs with the sets above.",
                                 guide_cards(ex_guides)))

    if related:
        body.append(card_section(
            "Related exams", "Papers that share the same syllabus",
            "Same subjects, different interview board.",
            [(x["name"], x["summary"], exam_file(x["id"]), "") for x in related]))
        for x in related:
            link_record(filename, "exam", exam_file(x["id"]), "exam", x["name"])

    body.append(section_wrap(cta_card(
        "Keep practising", f"Start preparing for {name}",
        "Open the exam hub for the full list, or take today's mixed set right now.",
        [("All Punjab exams", "punjab-exams.html"), ("Daily Quiz", "quiz.html?mode=daily"),
         ("Mock Tests", "mock.html"), ("Track progress", "progress.html")]),
        pad_top=False))

    if exam_subjects:
        q1a = ("Start with "
               + ", ".join(s["name"] for s in exam_subjects[:3])
               + (" and the rest of the subject library" if len(exam_subjects) > 3 else "")
               + ". Each subject page above lists its categories, its quizzes and the exams "
                 "that rely on it, so you never have to guess what to open next.")
    else:
        q1a = ("This portal does not publish a subject list for this paper. The study guide "
               "above covers the planning side, and the subject library covers the questions.")
    q2a = ("Yes. Every quiz, mock test and study guide on House of Aspirants is free, and no "
           "sign-in is needed to open a set - Google sign-in is optional and only saves "
           "scores, bookmarks and progress.")
    q3a = ("No, and that is deliberate. Vacancies, dates, marks and admit cards change and "
           "this portal does not track them - always read the official notification on the "
           "recruiting body's own website before acting on a date.")
    faqs = [
        (f"Where should I start for {name}?", q1a),
        ("Is the material on this portal free?", q2a),
        ("Do you publish dates, marks or admit cards?", q3a),
    ]

    crumbs = [("Home", "index.html", f"{BASE}/"),
              ("Punjab Exams", "punjab-exams.html", f"{BASE}/punjab-exams"),
              (name, None, None)]
    ld = [ld_script({"@context": "https://schema.org", "@graph": [
        webpage_ld(url, h1, description, f"{url}#breadcrumb",
                   has_part=[{"@id": f"{url}#faq"}]),
        crumb_ld(url, [(l, i) for l, _, i in crumbs]),
        faq_ld(url, faqs),
    ]})]

    html = render_page(
        title=title, description=description, kw=kw, url=url, ld_blocks=ld,
        crumbs=[(l, h) for l, h, _ in crumbs], eyebrow="Exam", h1=h1, lead=lead,
        answer=answer, facts=facts, body="\n".join(b for b in body if b),
        faq=faq_section("Questions", f"{name} - common questions",
                        "Answered the way this portal actually behaves.", faqs))

    write_page(filename, html)
    register(filename, url, "exam", eid, title, description, h1, words(intro_html),
             {"WebPage", "BreadcrumbList", "FAQPage"})
    info(f"exam     {filename}  subjects={len(exam_subjects)} topics={len(derived)}")
    return filename


# ================================================================ WRITING ====
def write_page(filename, html):
    with open(os.path.join(ROOT, filename), "w", encoding="utf-8") as fh:
        fh.write(html)


def root_html_pages():
    """{filename: (title, description)} for every non-generated root page."""
    out = {}
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".html") or fn.startswith(GENERATED_PREFIXES):
            continue
        try:
            with open(os.path.join(ROOT, fn), "r", encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        t = re.search(r"<title>(.*?)</title>", src, re.S)
        d = re.search(r'<meta\s+(?:name|property)="description"\s+content="([^"]*)"', src)
        out[fn] = (html_mod.unescape(t.group(1).strip()) if t else "",
                   html_mod.unescape(d.group(1)) if d else "")
    return out


def check_unique(records):
    """Requirement 6: no two landing pages may share title/description/canonical."""
    dupes = []
    for field in ("title", "description", "url"):
        seen = {}
        for r in records:
            k = r[field].lower()
            if k in seen:
                dupes.append(f"landing pages share {field}: "
                             f"{seen[k]} / {r['file']} ({r[field]!r})")
            seen[k] = r["file"]
    existing = root_html_pages()
    for r in records:
        for fn, (t, d) in existing.items():
            if r["title"].lower() == t.lower():
                dupes.append(f"{r['file']}: title identical to {fn}")
            if r["description"] and r["description"].lower() == d.lower():
                dupes.append(f"{r['file']}: description identical to {fn}")
    return dupes


def write_manifest(records):
    path = os.path.join(DATA, "landing-manifest.json")
    payload = {
        "$note": "GENERATED by scripts/build_landing_pages.py. Single source of truth for "
                 "the landing-page URLs: build_index.py / build-index.mjs append these to "
                 "sitemap.xml, and scripts/seo_check.py enforces that every entry exists, "
                 "is unique and is correctly linked. Do not edit by hand.",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(records),
        "pages": records,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


PAIR_LABEL = {
    ("subject", "topic"): "Subject → Topic",
    ("topic", "quiz"): "Topic → Quiz",
    ("quiz", "subject"): "Quiz → Subject",
    ("exam", "subject"): "Exam → Subject",
    ("exam", "topic"): "Exam → Topic",
}
REQUIRED_PAIRS = [("subject", "topic"), ("topic", "quiz"), ("quiz", "subject"),
                  ("exam", "subject"), ("exam", "topic")]


def scan_links(records):
    """Re-read every internal anchor back out of the SHIPPED html.

    The report must never disagree with the pages it describes. Counting the
    generator's own link_log drifts (a card grid that emits an href without
    recording it under-counts, and a required route then reads "0" while still
    being ticked), so the numbers below are measured from the generated files -
    the same source seo_check.py audits.
    """
    from collections import Counter, defaultdict
    ftype = {r["file"]: r["type"] for r in records}
    a_rx = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.S)
    href_rx = re.compile(r'href="([^"]+)"')
    tag_rx = re.compile(r"<[^>]+>")
    pairs, examples = Counter(), defaultdict(list)
    anchors = entity_links = 0
    for rec in records:
        path = os.path.join(ROOT, rec["file"])
        if not os.path.exists(path):
            continue
        html = open(path, encoding="utf-8").read()
        for m in a_rx.finditer(html):
            hm = href_rx.search(m.group(1) or "")
            if not hm:
                continue
            href = hm.group(1).strip()
            # off-site, in-page and non-document targets are not internal links
            if href.startswith(("http://", "https://", "//", "#",
                                "mailto:", "tel:", "javascript:")):
                continue
            anchors += 1
            dst = href.split("#", 1)[0].split("?", 1)[0].strip()
            if not dst:
                continue
            if not dst.endswith(".html"):
                dst += ".html"
            if dst == rec["file"] or dst not in ftype:
                continue
            entity_links += 1
            key = (rec["type"], ftype[dst])
            pairs[key] += 1
            if len(examples[key]) < 3:
                text = " ".join(tag_rx.sub(" ", m.group(2)).split())
                examples[key].append(f"`{text or href}`: {rec['file']} → {dst}")
    return pairs, examples, anchors, entity_links


def write_report(records):
    from collections import Counter, defaultdict
    pairs, examples, anchors, entity_links = scan_links(records)
    total_links = entity_links
    by_type = Counter(r["type"] for r in records)
    titles = [r["title"] for r in records]
    descs = [r["description"] for r in records]
    urls = [r["url"] for r in records]
    dupes = check_unique(records)

    lines = []
    add = lines.append
    add("# Programmatic SEO - Landing Page Report")
    add("")
    add(f"Generated by `scripts/build_landing_pages.py` on "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC.")
    add("")
    add("```bash")
    add("python3 scripts/build_index.py          # manifest + sitemap")
    add("python3 scripts/build_landing_pages.py  # these pages + this report")
    add("python3 scripts/seo_check.py            # gate (must exit 0)")
    add("```")
    add("")
    add("---")
    add("")

    # ---- 1. pages optimized -------------------------------------------------
    add(f"## 1. Pages optimized ({len(records)})")
    add("")
    add("| Type | Pages | URL pattern |")
    add("| --- | ---: | --- |")
    patterns = {
        "subject": ("/subject-\<id\>", "`subject-<id>.html`"),
        "category": ("/category-\<subject\>-\<category\>", "`category-<subject>-<category>.html`"),
        "topic": ("/topic-\<subject\>-\<topic\>", "`topic-<subject>-<topic>.html`"),
        "quiz": ("/quiz-\<subject\>-\<topic\>", "`quiz-<subject>-<topic>.html`"),
        "exam": ("/exam-\<id\>", "`exam-<id>.html`"),
    }
    for kind in ("subject", "category", "topic", "quiz", "exam"):
        if by_type.get(kind):
            add(f"| {kind.capitalize()} | {by_type[kind]} | {patterns[kind][1]} |")
    add(f"| **Total** | **{len(records)}** | emitted at repo root (relative assets, "
        f"shared chrome) |")
    add("")
    add("| # | URL | Type | Title (chars) | Meta description (chars) | H1 | Intro words | Schema |")
    add("| ---: | --- | --- | --- | --- | --- | ---: | --- |")
    for i, r in enumerate(records, 1):
        add(f"| {i} | `{r['url'].replace(BASE, '')}` | {r['type']} | "
            f"{r['title']} ({len(r['title'])}) | {len(r['description'])} | "
            f"{r['h1']} | {r.get('introWords') or '-'} | {', '.join(r['schema'])} |")
    add("")
    intro_rows = [r for r in records if r.get("introWords")]
    if intro_rows:
        short = [r for r in intro_rows if r["introWords"] < 250 and r["type"] == "subject"]
        add(f"Intro word counts: min {min(r['introWords'] for r in intro_rows)}, "
            f"max {max(r['introWords'] for r in intro_rows)}. "
            + (f"Subject pages below the 250-word target: "
               f"{', '.join(r['file'] for r in short)}." if short
               else "Every subject page clears the 250-word intro target."))
        add("")

    # ---- 2. metadata --------------------------------------------------------
    add("## 2. Metadata generated")
    add("")
    add(f"- **Unique titles:** {len(set(t.lower() for t in titles))}/{len(titles)}"
        + (" ✅" if len(set(t.lower() for t in titles)) == len(titles) else " ❌"))
    add(f"- **Unique meta descriptions:** "
        f"{len(set(d.lower() for d in descs))}/{len(descs)}"
        + (" ✅" if len(set(d.lower() for d in descs)) == len(descs) else " ❌"))
    add(f"- **Unique canonical URLs:** {len(set(urls))}/{len(urls)}"
        + (" ✅" if len(set(urls)) == len(urls) else " ❌"))
    add(f"- **Title length:** {min(len(t) for t in titles)}-"
        f"{max(len(t) for t in titles)} chars (Google truncates at ~60)")
    add(f"- **Description length:** {min(len(d) for d in descs)}-"
        f"{max(len(d) for d in descs)} chars (target window 140-160)")
    add(f"- **Robots:** `index, follow` on every landing page; canonical is the page's own "
        f"extensionless URL (`{BASE}/<slug>`).")
    add("")
    add("Title templates (entity name + real site data only, no invented facts):")
    add("")
    add("| Type | Title template |")
    add("| --- | --- |")
    add("| Subject | `<Subject> Quiz: Free MCQs for Punjab Exams` |")
    add("| Category | `<Category> Quiz: <Subject> MCQs for Punjab Exams` |")
    add("| Topic | `<Topic>: Topic Guide and MCQ Practice` |")
    add("| Quiz | `<Topic> Quiz (<n> MCQs) - Free Online Test` |")
    add("| Exam | `<Exam>: Preparation, Subjects and Free MCQs` |")
    add("")
    add("All landing metadata is **static HTML** - it is present before JavaScript runs, so "
        "crawlers never have to render the page to see the title, description, canonical or "
        "JSON-LD.")
    add("")

    # ---- 3. internal links --------------------------------------------------
    add(f"## 3. Internal links created ({total_links})")
    add("")
    add(f"- Links between generated entities: **{total_links}**")
    add(f"- Every internal anchor on the {len(records)} generated pages: "
        f"**{anchors}** (includes links to site guides, `/faq`, `/mock` and the app views)")
    add("- Counts are re-read from the shipped HTML, not from the generator's log, "
        "so this table cannot drift from the pages themselves.")
    add("- Every link is a plain `<a href>` in static HTML (no JS-dependent navigation).")
    add("")
    add("| Route | Count | Required by spec | Examples |")
    add("| --- | ---: | --- | --- |")
    for pair in REQUIRED_PAIRS:
        n = pairs.get(pair, 0)
        exs = examples.get(pair, [])
        add(f"| {PAIR_LABEL[pair]} | {n} | {'✅' if n else '❌ MISSING'} | "
            + ("; ".join(exs) if exs else "—") + " |")
    add("")
    other = [(k, v) for k, v in sorted(pairs.items(), key=lambda kv: -kv[1])
             if k not in REQUIRED_PAIRS]
    if other:
        add("Additional routes generated automatically:")
        add("")
        add("| Route | Count |")
        add("| --- | ---: |")
        for (a, b), v in other:
            add(f"| {a.capitalize()} → {b.capitalize()} | {v} |")
        add("")

    # ---- 4. duplicate content ------------------------------------------------
    add("## 4. Potential duplicate content")
    add("")
    if dupes:
        add("⚠️ **Collisions found (fix before publishing):**")
        add("")
        for d in dupes:
            add(f"- {d}")
    else:
        add("- **Metadata collisions: none.** Every landing title, description and canonical "
            "is unique, and none matches an existing root page.")
    add("")
    add("Parameter URLs are canonicalised onto their landing page at runtime "
        "(`assets/js/subject.js`, `assets/js/quiz.js`), so the app views never compete with "
        "the landing pages:")
    add("")
    add("| Parameter URL | Canonical target | Set by |")
    add("| --- | --- | --- |")
    add("| `/subject?subject=<id>` | `/subject-<id>` | `subject.js` |")
    add("| `/subject?subject=<id>&category=<c>` | `/category-<id>-<c>` | `subject.js` |")
    add("| `/quiz?subject=<s>&topic=<t>` | `/quiz-<s>-<t>` | `quiz.js` (seeded page) |")
    add("| `/quiz?mode=daily` / `?mode=mock` | *(self, `noindex`)* | `quiz.js` (unchanged) |")
    add("| `/quiz?subject=<s>&topic=<t>` (no landing page yet) | `/quiz?...` self | `quiz.js` |")
    add("")
    add("Residual risk notes:")
    add("")
    add("- The generated quiz page and `/quiz?subject=...&topic=...` run the **same engine on "
        "the same questions**. They are intentionally canonicalised to the generated page, "
        "which carries the static Quiz/FAQ schema; the parameter URL keeps only its runtime "
        "UI.")
    add("- Landing pages share site chrome (header, footer, related cards) by design; body "
        "copy, H1, FAQ answers and link sets are entity-specific, so pages stay "
        "distinguishable even where sections rhyme.")
    add("- Lanes with no question file yet publish an explicit 'being published' state rather "
        "than padded content - no doorway pages, no invented counts.")
    add("- `sitemap.xml` is built from `data/landing-manifest.json`, so a landing URL can "
        "never enter the sitemap without its file existing on disk.")
    if WARNINGS:
        add("")
        add("### Generator warnings")
        add("")
        for w in WARNINGS:
            add(f"- {w}")
    add("")

    path = os.path.join(ROOT, "SEO-LANDING-REPORT.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    # hand main() the same numbers the report printed, so console and report
    # can never disagree about how many links were emitted
    return path, dupes, {"entity": entity_links, "anchors": anchors, "pairs": pairs}


def main():
    print("PROGRAMMATIC SEO - building landing pages")
    print("=" * 60)
    # 1) fresh entity list (scans questions/), 2) build the pages, 3) fold the
    # landing paths back into data/index.json + sitemap.xml. One command is
    # therefore enough:  python3 scripts/build_landing_pages.py
    builder = os.path.join(ROOT, "scripts", "build_index.py")
    run_builder = lambda: subprocess.run(  # noqa: E731 - tiny local helper
        [sys.executable, builder], cwd=ROOT, check=True)
    run_builder()

    built = []
    for s in subjects:
        built.append(build_subject(s))
    for s in subjects:
        for c in s.get("categories", []):
            built.append(build_category(s, c))
    for s in subjects:
        for c, t in all_topics(s):
            built.append(build_topic(s, c, t))
    for s in subjects:
        for c, t in live_topics(s):
            built.append(build_quiz(s, c, t))
    for e in exams_cfg:
        built.append(build_exam(e))

    expected = set(built)
    removed = []
    for fn in sorted(os.listdir(ROOT)):
        if (fn.endswith(".html") and fn.startswith(GENERATED_PREFIXES)
                and fn not in expected):
            os.remove(os.path.join(ROOT, fn))
            removed.append(fn)
    if removed:
        warn("stale landing pages removed: " + ", ".join(removed))

    dupes = check_unique(PAGES)
    for d in dupes:
        warn(d)

    manifest_path = write_manifest(PAGES)
    run_builder()          # fold landing paths into index.json + sitemap.xml
    report_path, _dupes, link_stats = write_report(PAGES)

    print("=" * 60)
    print(f"  pages written : {len(PAGES)}  "
          f"({', '.join(f'{k}={v}' for k, v in sorted(Counter(r['type'] for r in PAGES).items()))})")
    print(f"  internal links: {link_stats['entity']} between generated entities "
          f"({link_stats['anchors']} internal anchors in total)")
    print(f"  manifest      : data/landing-manifest.json")
    print(f"  report        : SEO-LANDING-REPORT.md")
    if dupes:
        print(f"  !! {len(dupes)} metadata collision(s) - seo_check.py will fail")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())




