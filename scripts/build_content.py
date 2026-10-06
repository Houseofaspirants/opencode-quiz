#!/usr/bin/env python3
"""
build_content.py | House of Aspirants
===============================================================================
Markdown content system for the learning platform. No CMS, no third-party
packages: the site stays vanilla, and this builder runs on a bare Python 3.9.

WHAT IT DOES
    content/<collection>/<slug>.md   --source of truth (Git-reviewed Markdown)
                |
                v
    scripts/build_content.py
                |
                +--> <prefix>-<slug>.html     one static page per document
                +--> <hub>.html               one hub per collection
                +--> data/content-manifest.json
                |      - feeds sitemap.xml (via BOTH index builders)
                |      - feeds seo_check's content gate
                |      - feeds the homepage feed blocks (index.html)
                +--> homepage feed blocks patched between markers

COLLECTIONS (folder  ->  page prefix  ->  hub)
    content/notes/                    note-       study-notes.html
    content/current-affairs/          ca-         current-affairs.html
    content/monthly-magazine/         magazine-   magazine.html
    content/strategy/                 strategy-   strategy.html
    content/live-sessions/            session-    live-sessions.html
    content/recruitment/              recruit-    recruitment.html
    content/blogs/                    blog-       blogs.html
    content/news/                     news-       news.html
    content/announcements/            announce-   announcements.html
    content/expected-mcqs/            expected-   expected-mcqs.html
    content/previous-year-questions/  pyq-        previous-year-questions.html
    content/pdfs/         (registry only - the PDF is the artifact)  pdfs.html

PHASE 3 - AI CONTENT ENGINE
    scripts/content_engine.py holds the eleven reusable content templates, the
    facet-scoring recommendation engine (subject / exam / category /
    difficulty / tags / language) and the internal content graph. Every page
    the builder writes gets its recommendation slots from its template, its
    metadata from the front matter, and its >=5 contextual internal links from
    the graph - or the build fails.

PUNJABI VARIANTS
    A sibling `<slug>.pa.md` publishes `pa/<prefix>-<slug>.html` (lang="pa"),
    cross-linked from the English page and vice versa. Punjabi-first means the
    note itself can ship in Punjabi; English stays one tap away.

PDF DROPS (a PDF alone is enough to publish)
    content/<collection>/<file>.pdf is a document like any other. The builder
    discovers it, derives every field it can from the file name (title, slug,
    description, date, download URL), gives it a page in its own collection
    hub and registers it in the manifest, the search corpus, the feed, the
    archives and the sitemap - no Markdown required. A sibling `<slug>.md`
    with the same name is still read first; in that case the PDF becomes that
    document's download instead of a second page. `data/pdf-meta.json` keeps
    the dates of already-published PDFs stable, so a rebuild on another machine
    (or in CI) emits byte-identical files.

DETERMINISM
    The output never contains a run timestamp: rebuilding without editing
    content emits byte-identical files, so `scripts/ci.sh` step 5 can prove the
    committed tree is exactly what this builder produces.

USAGE
    python3 scripts/build_content.py            # build everything
    python3 scripts/build_content.py --strict   # warnings become errors
    python3 scripts/new_content.py --list       # the content templates
===============================================================================
"""
import hashlib
import html as html_mod
import datetime
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import study_material            # data/study-manifest.json (Study's subject list)
import proof_documents           # data/proof-manifest.json (the Blueprint's scans)
import pyq_collection            # data/pyq-manifest.json (the PYQ exam folders)
import current_affairs           # current-affairs/<language>/<Month YYYY>/ -> nested pages

from content_engine import (TEMPLATES, GENERIC_PLAN, WEIGHTS, plan_for,
                            template_for, rank, build_graph, build_silos,
                            make_node, make_edge, node_id, link_floor)

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "https://houseofaspirants.in"
CONTENT = ROOT / "content"
MANIFEST = ROOT / "data" / "content-manifest.json"
GRAPH = ROOT / "data" / "content-graph.json"
OG_IMAGE = "assets/img/og-cover.png"
OG_ABS = f"{DOMAIN}/{OG_IMAGE}"
BYLINE = "House of Aspirants Editorial Team"
BRAND_SUFFIX = " | House of Aspirants"

# Generated page prefixes - used for idempotent cleanup of stale output.
GEN_PREFIXES = ("material-", "note-", "ca-", "magazine-", "strategy-", "session-", "recruit-",
                "blog-", "news-", "announce-", "expected-", "pyq-",
                # Phase 4 collections. The prefixes are deliberately NOT the
                # collection names: build_landing_pages.py already owns
                # subject-*.html, topic-*.html and category-*.html, so the
                # document prefixes here stay out of its namespace.
                "pnote-", "sguide-", "tguide-", "practice-", "story-", "book-",
                # Phase 4 generated index pages (authors, tag/category
                # archives). "archives.html" itself is never matched.
                "archive-", "author-")
GENERATED_MARKER = "generated by scripts/build_content.py - do not edit by hand"

# Official-source policy (decision: recruitment pages may only point at the
# recruiting body's own website). Anything else fails the build, so a stray
# affiliate or third-party jobs portal can never ship.
OFFICIAL_HOST_SUFFIXES = (".gov.in", ".nic.in", ".gov.uk")
OFFICIAL_HOSTS = {"pspcl.co.in", "pspcl.gov.in"}

errors, warnings, notes = [], [], []
RECRUITMENT = []            # recruitment records, filled during the load pass
CHAIN_TARGETS = {}          # newest record per chain collection (learning path)


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def info(msg):
    notes.append(msg)


def esc(s):
    return html_mod.escape(str(s), quote=True)


# =============================================================================
# 1. FRONT MATTER  (minimal YAML subset - scalars, inline lists, block lists,
#                   one level of nested mappings, "|"" literal blocks)
# =============================================================================
LIST_FIELDS = {
    "subjects", "exams", "tags", "highlights", "dates", "syllabus", "selection",
    "expected_questions", "previous_papers", "questions", "doubts", "categories",
}


def _split_inline_list(inner):
    """Split `a, b, "c, d"` on commas that are not inside quotes."""
    items, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf.strip())
    return [x for x in (_scalar(i) for i in items) if x not in ("", None)]


def _scalar(raw):
    v = raw.strip()
    # inline list:  key: [a, b, c]
    if len(v) >= 2 and v[0] == "[" and v[-1] == "]":
        return _split_inline_list(v[1:-1])
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    low = v.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def parse_front_matter(text, where):
    """-> (meta dict, body str). Raises ValueError with a line-accurate message."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{where}: file must start with a '---' front matter fence")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError(f"{where}: front matter fence is never closed")

    meta, i, n = {}, 1, end
    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            raise ValueError(f"{where}:{i + 1}: expected 'key: value', got {line!r}")
        key, rest = m.group(1), m.group(2)
        i += 1

        # literal block:  key: |   (indented lines follow)
        if rest in ("|", ">"):
            block = []
            while i < n and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            meta[key] = " ".join(x for x in block if x).strip()
            continue

        # block list / nested mapping
        if rest == "":
            items, first_indent = [], None
            while i < n and lines[i].strip() and not lines[i].lstrip().startswith("#") \
                    and re.match(r"^\s+-\s", lines[i]):
                if first_indent is None:
                    first_indent = len(lines[i]) - len(lines[i].lstrip())
                item_line = lines[i]
                i += 1
                im = re.match(r"^\s+-\s+(.*)$", item_line)
                payload = im.group(1)
                # nested mapping inside a list item: "- k: v" then deeper "k: v"
                # (YAML needs the space after the colon - that is what keeps a
                # bare URL like https://… from being read as a key)
                if re.match(r"^[A-Za-z0-9_]+:\s+\S", payload):
                    entry = {}
                    km = re.match(r"^([A-Za-z0-9_]+):\s+(.*)$", payload)
                    entry[km.group(1)] = _scalar(km.group(2))
                    while i < n:
                        nxt = lines[i]
                        ind = len(nxt) - len(nxt.lstrip())
                        if not nxt.strip() or ind <= first_indent:
                            break
                        if not re.match(r"^[A-Za-z0-9_]+:\s+\S", nxt.strip()):
                            break
                        km2 = re.match(r"^\s*([A-Za-z0-9_]+):\s+(.*)$", nxt)
                        entry[km2.group(1)] = _scalar(km2.group(2))
                        i += 1
                    items.append(entry)
                else:
                    items.append(_scalar(payload))
            meta[key] = items
            continue

        meta[key] = _scalar(rest)

    body = "\n".join(lines[end + 1:]).strip("\n")
    return meta, body


# =============================================================================
# 2. MARKDOWN  (headings, paragraphs, lists, tables, quotes, code, links)
#    Raw HTML in the source is escaped, never passed through: the Markdown
#    author cannot break the page or inject markup.
# =============================================================================
_INLINE_CODE = re.compile(r"`([^`]+)`")
_INLINE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_INLINE_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def md_inline(text):
    s = esc(text)
    s = _INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", s)
    s = _LINK.sub(
        lambda m: f'<a href="{esc(m.group(2))}">{m.group(1)}</a>', s)
    s = _INLINE_BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = _INLINE_ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", s)
    return s


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def md_to_html(src):
    """-> (html, toc) where toc = [(anchor, text), ...] for every ## heading.

    Heading levels are remapped so the page keeps one <h1> (the title) and a
    skip-free outline: Markdown '#' and '##' become h2, deeper levels follow,
    and no level ever jumps more than one.
    """
    lines = src.replace("\r\n", "\n").split("\n")
    out, toc, i, n = [], [], 0, len(lines)
    seen, last_level = {}, 0

    def anchor_for(text):
        base = slugify(text)
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f"{base}-{seen[base]}"

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # fenced code
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{esc(chr(10).join(buf))}</code></pre>")
            continue

        # horizontal rule
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            raw_level = len(m.group(1))
            level = max(2, min(6, raw_level + (1 if raw_level == 1 else 0)))
            if last_level and level > last_level + 1:
                level = last_level + 1
            text = m.group(2).strip().rstrip("#").strip()
            anchor = anchor_for(text)
            if level == 2:
                toc.append((anchor, text))
            out.append(f'<h{level} id="{anchor}">{md_inline(text)}</h{level}>')
            last_level = level
            i += 1
            continue

        # table
        if stripped.startswith("|") and i + 1 < n and \
                re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{md_inline(c)}</th>" for c in head)
            body_rows = "".join(
                "<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>"
                for r in rows)
            out.append(f"<div class=\"md-table\"><table><thead><tr>{th}</tr></thead>"
                       f"<tbody>{body_rows}</tbody></table></div>")
            continue

        # blockquote
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote><p>{md_inline(' '.join(buf))}</p></blockquote>")
            continue

        # lists (unordered + ordered, two levels deep)
        if re.match(r"^([-*+]|\d+\.)\s+", stripped):
            ordered = bool(re.match(r"^\d+\.", stripped))
            items, i = _read_list(lines, i, n)
            out.append(_render_list(items, ordered, 0))
            continue

        # paragraph
        buf = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{md_inline(' '.join(buf))}</p>")
        else:                       # defensive: never spin
            i += 1

    return "\n".join(out), toc


def _is_block_start(line):
    s = line.strip()
    return (s.startswith(("```", ">", "|", "#")) or
            re.match(r"^([-*+]|\d+\.)\s+", s) is not None or
            re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s) is not None)


def _read_list(lines, i, n):
    """Read a list block -> [{text, children: [...]}] (children = nested list)."""
    base = len(lines[i]) - len(lines[i].lstrip())
    items = []
    while i < n:
        raw = lines[i]
        if not raw.strip():
            # blank line ends the list only when the NEXT line is not a list line
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j >= n or not re.match(r"^\s*([-*+]|\d+\.)\s", lines[j]) \
                    or (len(lines[j]) - len(lines[j].lstrip())) < base:
                break
            i += 1
            continue
        ind = len(raw) - len(raw.lstrip())
        if ind < base:
            break
        m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", raw)
        if not m:
            break
        if ind > base and items:
            child_lines = []
            start = i
            while i < n and (not lines[i].strip() or
                             (len(lines[i]) - len(lines[i].lstrip())) > base):
                child_lines.append(lines[i])
                i += 1
            sub, _ = _read_list(child_lines, 0, len(child_lines))
            items[-1]["children"] = sub
            if i == start:          # safety
                i += 1
            continue
        items.append({"text": m.group(2).strip(), "children": []})
        i += 1
    return items, i


def _render_list(items, ordered, depth):
    tag = "ol" if ordered else "ul"
    parts = [f"<{tag}>"]
    for it in items:
        inner = md_inline(it["text"])
        if it["children"]:
            inner += _render_list(it["children"], not ordered, depth + 1)
        parts.append(f"<li>{inner}</li>")
    parts.append(f"</{tag}>")
    return "".join(parts)


# =============================================================================
# 3. COLLECTION CONFIGURATION
# =============================================================================
# intro/lead copy for hubs: honest, evergreen, and specific about what lives
# in the section TODAY (empty collections say so rather than pretending).
HUBS = {
    # --- STEP 2/3: the STUDY MATERIAL shelf -------------------------------
    # content/study-material/<subject>/<file> is the only authoring surface:
    # the folder is the registration, the file name is the metadata, and the
    # scanner above walks it exactly as it walks every other collection. It
    # sits first because it is the Study system's unified listing - one
    # section, one heading, no per-file-type shelves beside it.
    "study-material": {
        "file": "study-material.html",
        "dir": "study-material",
        "prefix": "material",
        "eyebrow": "Free to read & download",
        "h1": "Study Material",
        "title": "Free Study Material for Punjab Competitive Exams",
        "description": (
            "Free study material for Punjab Police, PSSSB and PPSC exams - "
            "PDFs, notes and downloads for every subject, discovered from the "
            "files themselves with no sign-up."
        ),
        "keywords": ("Free Study Material Punjab, Punjab Police study material "
                     "PDF, PSSSB notes download, study material in Punjabi"),
        "lead": (
            "Every file dropped into the Study Material folders lands here: "
            "the subject it belongs to, the language it is written in, when it "
            "was last updated and how long it takes to read - all derived from "
            "the file itself, none of it typed in by hand."
        ),
        "answer": (
            "Study material here is free and needs no account: PDFs, notes and "
            "downloads are listed together under one heading whatever their "
            "format, filtered by subject and language, and searchable by title, "
            "file name and keyword."
        ),
        "empty_h3": "No study material published yet",
        "empty_p": (
            "Files dropped into content/study-material/ appear on this page "
            "with their subject, language and file size already filled in. "
            "Until the first set lands, the study notes and the practice "
            "system are ready to use."
        ),
        "empty_cta": ("study.html", "Open the Study system"),
        "schema_hub": "Study Material",
    },
    "notes": {
        "file": "study-notes.html",
        "dir": "notes",
        "prefix": "note",
        "eyebrow": "Learn & Revise",
        "h1": "Study Notes for Punjab Competitive Exams",
        "title": "Punjab Exam Study Notes | House of Aspirants",
        "description": (
            "Free subject-wise study notes for Punjab Police, PSSSB and PPSC "
            "aspirants - reading time, difficulty, exam tags, table of contents "
            "and related quizzes."
        ),
        "keywords": ("Study Notes Punjab, Punjab Police notes, PSSSB study notes, "
                     "PPSC notes, free exam notes Punjabi English"),
        "lead": (
            "Every note is written by the House of Aspirants editorial team and "
            "organised the way you actually revise: one subject, one idea, one "
            "read. Notes link straight into the quiz set that tests them."
        ),
        "answer": (
            "Study notes here are free, subject-wise pages that carry reading "
            "time, difficulty and exam tags, so you know what you are opening "
            "before you start. Every note ends with related quizzes, so revising "
            "a concept and proving you remember it happens in one click."
        ),
        "empty_h3": "No notes published yet",
        "empty_p": ("The first set of notes is being written and reviewed now. "
                    "Until it lands, the study guides and daily quizzes below are "
                    "ready to use."),
        "empty_cta": ("articles.html", "Browse study guides"),
        "schema_hub": "Study Notes",
    },
    "current-affairs": {
        "file": "current-affairs.html",
        "dir": "current-affairs",
        "prefix": "ca",
        "eyebrow": "Monthly magazine & practice",
        "h1": "Current Affairs for Punjab Exams",
        "title": "Punjab Current Affairs | House of Aspirants",
        "description": (
            "Current affairs for Punjab exam aspirants - explained in Punjabi "
            "and English, linked to the quiz set that tests them and to the "
            "monthly magazine issue."
        ),
        "keywords": ("Punjab current affairs, current affairs Punjab Police, "
                     "daily current affairs MCQ, current affairs magazine"),
        "lead": (
            "Two things, in Punjabi and English: the monthly current affairs "
            "magazine to read, and timed MCQ sets to practise the same months."
        ),
        "answer": (
            "Current affairs pages explain one development at a time in Punjabi "
            "and English, then link the quiz set and the monthly magazine issue "
            "that cover the same period, so reading, testing and revising the "
            "same event never means hunting for three different pages."
        ),
        "empty_h3": "No current affairs article published yet",
        "empty_p": ("The daily current affairs sets are already live on the "
                    "subject page. Explained articles will be published here as "
                    "they are written and reviewed."),
        "empty_cta": ("subject.html?subject=current-affairs",
                      "Practise current affairs sets"),
        "schema_hub": "Current Affairs",
    },
    "magazine": {
        "file": "magazine.html",
        "dir": "monthly-magazine",
        "prefix": "magazine",
        "eyebrow": "Current Affairs",
        "h1": "Current Affairs Monthly Magazine",
        "title": "Current Affairs Monthly Magazine | House of Aspirants",
        "description": (
            "Monthly current affairs magazine for Punjab exam aspirants - cover, "
            "PDF download, online reading, highlights, expected MCQs and a quiz "
            "for every issue."
        ),
        "keywords": ("current affairs magazine PDF, monthly current affairs Punjab, "
                     "Punjab current affairs magazine, current affairs MCQ"),
        "lead": (
            "One issue per month, built from the events that matter to Punjab "
            "exams: a cover, a downloadable PDF, the highlights worth revising "
            "and the quiz that turns reading into marks."
        ),
        "answer": (
            "Each monthly issue ships a cover, a PDF download, an online reading "
            "version, the month's important highlights and its own quiz, so one "
            "issue covers reading, revision and recall. The archive below lists "
            "every issue that has actually been published - nothing is previewed "
            "before it exists."
        ),
        "empty_h3": "No issue published yet",
        "empty_p": ("The first monthly issue is being assembled from this month's "
                    "current affairs sets. The current affairs quizzes are already "
                    "live if you want to start there."),
        "empty_cta": ("subject.html?subject=current-affairs", "Practise current affairs"),
        "schema_hub": "Monthly Magazine",
    },
    "strategy": {
        "file": "strategy.html",
        "dir": "strategy",
        "prefix": "strategy",
        "eyebrow": "Plan & Execute",
        "h1": "Preparation Strategy for Punjab Exams",
        "title": "Exam Preparation Strategy & Study Plans | House of Aspirants",
        "description": (
            "Preparation strategy for Punjab aspirants - study plans, daily and "
            "weekly timetables, book guidance, revision, mock test and mistake "
            "analysis method."
        ),
        "keywords": ("preparation strategy Punjab, study plan Punjab Police, daily "
                     "timetable exam, revision strategy, mock test strategy"),
        "lead": (
            "Method beats motivation. This section collects the practical side of "
            "preparation: how to plan a day, how to plan a week, what to revise "
            "and how to turn a mock test score into a to-do list."
        ),
        "answer": (
            "Strategy pages cover study plans, daily and weekly timetables, book "
            "recommendations, revision cycles, mock test method, mistake analysis "
            "and time management. Each one is written to be used this week rather "
            "than someday, and every method ends in a link to free practice on "
            "this portal."
        ),
        "empty_h3": "No strategy article published yet",
        "empty_p": ("Study plans and timetable templates are being written as "
                    "reviewed articles. The four evergreen study guides already "
                    "cover the same ground today."),
        "empty_cta": ("articles.html", "Read the study guides"),
        "schema_hub": "Preparation Strategy",
    },
    "sessions": {
        "file": "live-sessions.html",
        "dir": "live-sessions",
        "prefix": "session",
        "eyebrow": "Weekly Live Guidance",
        "h1": "Weekly Live Guidance Sessions",
        "title": "Weekly Live Guidance Sessions | House of Aspirants",
        "description": (
            "Upcoming and past House of Aspirants live sessions - topic, date, "
            "time, platform, join link, session summary, important questions and "
            "student doubts."
        ),
        "keywords": ("live session Punjab exam, weekly live guidance, exam strategy "
                     "live class, student doubts session Punjab"),
        "lead": (
            "A live session every week: one topic, one time slot, one join link. "
            "Past sessions stay here with their summary, the questions that were "
            "discussed and the doubts students raised."
        ),
        "answer": (
            "Every session lists its topic, date, time and platform with a direct "
            "join link, then keeps a summary, the important questions discussed "
            "and the student doubts raised. Upcoming sessions appear first and "
            "past sessions stay below them, so nothing you attended disappears."
        ),
        "empty_h3": "No session scheduled yet",
        "empty_p": ("The next live session will be posted here with its date, time "
                    "and join link. Until then, the Telegram channel carries every "
                    "announcement."),
        "empty_cta": ("https://t.me/HouseOfAspirant", "Join on Telegram"),
        "schema_hub": "Live Sessions",
    },
    "recruitment": {
        "file": "recruitment.html",
        "dir": "recruitment",
        "prefix": "recruit",
        "eyebrow": "Official Sources Only",
        "h1": "Punjab Recruitment Updates & Official Notifications",
        "title": "Punjab Recruitment Updates | House of Aspirants",
        "description": (
            "Recruitment records for Punjab posts - official notification link, "
            "eligibility, syllabus, selection process, important dates and "
            "preparation links."
        ),
        "keywords": ("Punjab recruitment, Punjab Police notification, PSSSB "
                     "notification, PPSC jobs, PSPCL jobs, Patwari recruitment"),
        "lead": (
            "This section points at the recruiting body's own website and nothing "
            "else. Every record links the official notification, restates only "
            "what that notification says and links back to the preparation guide "
            "for the post."
        ),
        "answer": (
            "Recruitment pages here never invent dates, vacancies or admit cards. "
            "Each one carries the official notification link on a government "
            "domain, restates eligibility, syllabus, selection process and "
            "important dates from that notification only, and links the matching "
            "preparation guide for the post."
        ),
        "empty_h3": "No official notification published here yet",
        "empty_p": ("Notifications are added only when the recruiting body "
                    "publishes one, and only as a link to that body's own website. "
                    "The preparation guides for every post are ready below."),
        "empty_cta": ("punjab-exams.html", "See all Punjab exam guides"),
        "schema_hub": "Recruitment Updates",
    },
    "blogs": {
        "file": "blogs.html",
        "dir": "blogs",
        "prefix": "blog",
        "eyebrow": "From the Desk",
        "h1": "Preparation Blog for Punjab Aspirants",
        "title": "Preparation Blog | House of Aspirants",
        "description": (
            "Preparation blog for Punjab aspirants - study habits, book notes, "
            "mock test debriefs and honest attempts, written by the House of "
            "Aspirants editorial team."
        ),
        "keywords": ("exam preparation blog, Punjab exam blog, study tips "
                     "Punjab Police, mock test debrief"),
        "lead": (
            "Longer reads than a note and less formal than a strategy guide: "
            "what a week of preparation actually looked like, what failed, what "
            "stayed and what is worth copying."
        ),
        "answer": (
            "Blog posts carry the reflective side of preparation - study habit "
            "experiments, book notes, mock test debriefs and the mistakes behind "
            "them - written by the same editorial team that publishes the notes "
            "and strategy guides."
        ),
        "empty_h3": "No blog post published yet",
        "empty_p": ("First posts are being drafted from real preparation weeks. "
                    "Until they are reviewed and published, the study guides "
                    "carry the same material in guide form."),
        "empty_cta": ("articles.html", "Read the study guides"),
        "schema_hub": "Blog",
    },
    "news": {
        "file": "news.html",
        "dir": "news",
        "prefix": "news",
        "eyebrow": "Exam News & Updates",
        "h1": "Exam News and Updates",
        "title": "Exam News & Updates | House of Aspirants",
        "description": (
            "Exam news for Punjab aspirants - application dates, exam pattern "
            "changes and policy announcements, each restated only from the "
            "recruiting body's notification."
        ),
        "keywords": ("Punjab exam news, Punjab Police exam update, PSSSB news, "
                     "PPSC exam date update"),
        "lead": (
            "News here is short and sourced: what changed, when it changes and "
            "which official page says so. Nothing is reported before the "
            "concerning body publishes it."
        ),
        "answer": (
            "Exam news pages restate only what a recruiting body has already "
            "published, link straight to that official page and date the change, "
            "so an application deadline or pattern update is never second-hand "
            "or guessed."
        ),
        "empty_h3": "No news item published yet",
        "empty_p": ("News is published only when an official notification or "
                    "update exists to link. Recruitment records already carry "
                    "every official link that is live today."),
        "empty_cta": ("recruitment.html", "See recruitment updates"),
        "schema_hub": "News",
    },
    "announcements": {
        "file": "announcements.html",
        "dir": "announcements",
        "prefix": "announce",
        "eyebrow": "From House of Aspirants",
        "h1": "Announcements from House of Aspirants",
        "title": "Site Announcements | House of Aspirants",
        "description": (
            "Announcements from House of Aspirants - new sections, schedule "
            "changes, editorial updates and platform news, published by the "
            "team that runs this site."
        ),
        "keywords": ("House of Aspirants announcement, site update, new section "
                     "launch, live session schedule"),
        "lead": (
            "Anything that changes how the site works lands here first: new "
            "sections, schedule changes, editorial policy updates and platform "
            "news."
        ),
        "answer": (
            "Announcements record what changed on this platform and when - new "
            "sections, live session schedules, editorial updates and app "
            "changes - so a returning aspirant can see what is new without "
            "scrolling the whole site."
        ),
        "empty_h3": "No announcement posted yet",
        "empty_p": ("Announcements appear here the moment something changes on "
                    "the site. Until then, the Telegram channel carries every "
                    "schedule and feature update."),
        "empty_cta": ("https://t.me/HouseOfAspirant", "Follow on Telegram"),
        "schema_hub": "Announcements",
    },
    "expected-mcqs": {
        "file": "expected-mcqs.html",
        "dir": "expected-mcqs",
        "prefix": "expected",
        "eyebrow": "Forecast, then review",
        "h1": "Expected MCQs for Punjab Competitive Exams",
        "title": "Expected MCQs Punjab Exams | House of Aspirants",
        "description": (
            "Expected MCQs for Punjab aspirants - forecast questions drawn "
            "from the syllabus and the pattern of the exam, published here "
            "only after they are reviewed."
        ),
        "keywords": ("expected MCQs Punjab Police, PSSSB expected questions, "
                     "Punjab exam forecast MCQ, expected questions Punjabi"),
        "lead": (
            "Forecast questions are only worth reading when someone is willing "
            "to stand behind them. Every set here is written from the syllabus "
            "and the pattern of a real exam, then reviewed before it is "
            "published."
        ),
        "answer": (
            "Expected MCQs on this site are forecast practice questions built "
            "from the syllabus and the recent pattern of a specific exam, "
            "reviewed by the editorial team before they are published - they "
            "are never presented as leaked, predicted or guaranteed questions, "
            "and nothing appears here before it has been checked."
        ),
        "empty_h3": "No expected MCQ set published yet",
        "empty_p": ("Sets are drafted from the syllabus and the pattern of "
                    "each exam, then reviewed before publication. Until a set "
                    "clears review, the daily quiz and the subject quizzes "
                    "below are live and tested."),
        "empty_cta": ("quiz.html?mode=daily", "Open the daily quiz"),
        "schema_hub": "Expected MCQs",
    },
    "previous-year-questions": {
        "file": "previous-year-questions.html",
        "dir": "previous-year-questions",
        "prefix": "pyq",
        "eyebrow": "Official papers only",
        "h1": "Previous Year Questions for Punjab Exams",
        "title": "Previous Year Questions Punjab Exams | House of Aspirants",
        "description": (
            "Previous year questions for Punjab exams - questions taken from "
            "the official paper itself, with the exam and year named, listed "
            "only when that paper exists."
        ),
        "keywords": ("Punjab Police previous year questions, PSSSB previous "
                     "papers, PPSC PYQ, Punjab exam solved papers"),
        "lead": (
            "A previous year question is evidence, not a prediction. Everything "
            "in this section names the exam and the year it came from and points "
            "at the official paper it was taken from."
        ),
        "answer": (
            "Previous year questions here are taken only from official exam "
            "papers, each one labelled with the exam and the year it belongs to "
            "- nothing is reconstructed from memory or copied from an "
            "aggregator, and this section stays empty until a paper exists to "
            "cite."
        ),
        "empty_h3": "No previous year paper published yet",
        "empty_p": ("Papers are added only when the official PDF exists to "
                    "link, with the exam and year named. Until then the topic "
                    "quizzes below already practise the same syllabus."),
        "empty_cta": ("punjab-exams.html", "See all Punjab exam guides"),
        "schema_hub": "Previous Year Questions",
    },
    "pdfs": {
        "file": "pdfs.html",
        "dir": "pdfs",
        "prefix": "",            # registry only - no per-PDF page
        "eyebrow": "Download & Study Offline",
        "h1": "Free PDFs for Punjab Exams",
        "title": "Free PDFs for Punjab Exams | House of Aspirants",
        "description": (
            "Free downloadable PDFs for Punjab exam preparation - notes, "
            "question sets and revision sheets, each with a subject, exam tags "
            "and a direct download button."
        ),
        "keywords": ("free PDF Punjab Police notes, current affairs PDF, exam "
                     "revision PDF, Punjab GK PDF"),
        "lead": (
            "Download, print, revise. Every PDF listed here is a real file hosted "
            "on this site with a direct download button - no sign-up, no email "
            "wall, no third-party redirect."
        ),
        "answer": (
            "PDFs are hosted on this site and download with one click, straight "
            "from our own storage - no sign-up, no email wall and no redirect "
            "through a third party. Each entry shows its subject and exam tags so "
            "you can grab the exact sheet you need before a commute."
        ),
        "empty_h3": "No PDF published yet",
        "empty_p": ("PDF sheets are being typeset from the notes and question "
                    "sets. Until they land, every quiz works offline once you "
                    "have visited the site."),
        "empty_cta": ("quiz.html?mode=daily", "Open the daily quiz"),
        "schema_hub": "Free PDFs",
    },
    # ---- Phase 4 collections -----------------------------------------------
    # The remaining content collections of the platform brief. Same builder,
    # same contract, same gates: adding a collection is a table entry, never a
    # new page template.
    "personal-notes": {
        "file": "personal-notes.html",
        "dir": "personal-notes",
        "prefix": "pnote",
        "eyebrow": "What Actually Worked",
        "h1": "Personal Notes from Real Preparation",
        "title": "Personal Study Notes | House of Aspirants",
        "description": (
            "Personal study notes from House of Aspirants - what changed in "
            "the method, what worked, what failed and the habits worth "
            "repeating before your next attempt."
        ),
        "keywords": ("personal notes exam preparation, study journal Punjab "
                     "Police, preparation log PSSSB, what worked in exam prep"),
        "lead": (
            "A note is written after the method has actually been used: what "
            "changed, what it produced and whether it is worth repeating. No "
            "general advice, only the part that survived a real attempt."
        ),
        "answer": (
            "Personal notes here are short write-ups of a method that was "
            "really tried - a timetable, a revision loop, an error that cost "
            "marks - with the result described plainly. Each one links into "
            "the subject and the quiz it came from, so you can copy the habit "
            "and test it the same day."
        ),
        "empty_h3": "No personal note published yet",
        "empty_p": ("Notes are written only after a method has been tested "
                    "over a full week, so nothing is posted for the sake of "
                    "posting. The strategy archive below carries the method "
                    "pieces that are already reviewed."),
        "empty_cta": ("strategy.html", "Read the strategy archive"),
        "schema_hub": "Personal Notes",
    },
    "subject-guides": {
        "file": "subject-guides.html",
        "dir": "subject-guides",
        "prefix": "sguide",
        "eyebrow": "Syllabus, End to End",
        "h1": "Subject Guides for Punjab Competitive Exams",
        "title": "Subject Guides | House of Aspirants",
        "description": (
            "Free subject guides for Punjab Police, PSSSB and PPSC - what the "
            "syllabus asks, the order that works, what to practise first and "
            "where each topic is tested."
        ),
        "keywords": ("subject guide Punjab exams, Punjab Police syllabus guide, "
                     "PSSSB subject preparation, PPSC subject guide free"),
        "lead": (
            "One guide per subject: what the syllabus asks for, the order that "
            "actually works, the books and notes that cover it, and the quizzes "
            "on this portal that prove you have learned it."
        ),
        "answer": (
            "A subject guide is a single page that maps one subject from the "
            "syllabus through to practice - scope, study order, common traps "
            "and the exact sets to attempt afterwards. It links into the "
            "subject hub, the study notes and the quizzes, so one page becomes "
            "the starting point for a whole subject."
        ),
        "empty_h3": "No subject guide published yet",
        "empty_p": ("Subject guides are being written one subject at a time so "
                    "each one covers the full syllabus rather than a slice of "
                    "it. The subject hub and the daily quiz are ready now."),
        "empty_cta": ("subject.html?subject=gk", "Open a subject hub"),
        "schema_hub": "Subject Guides",
    },
    "topic-guides": {
        "file": "topic-guides.html",
        "dir": "topic-guides",
        "prefix": "tguide",
        "eyebrow": "One Topic at a Time",
        "h1": "Topic Guides inside the Punjab Exam Syllabus",
        "title": "Topic Guides | House of Aspirants",
        "description": (
            "Topic-wise guides for Punjab competitive exams - what each topic "
            "covers, how the exam asks it, the points to remember and the set "
            "that proves you know it."
        ),
        "keywords": ("topic guide Punjab exam, syllabus topic wise notes, "
                     "important topics Punjab Police, PSSSB topic preparation"),
        "lead": (
            "Where a subject guide covers the whole subject, a topic guide "
            "zooms into one chapter: its scope, how it has been asked, the "
            "facts that get repeated and the set to attempt after reading."
        ),
        "answer": (
            "Topic guides sit between a study note and a subject guide - one "
            "chapter, fully explained, with the exam pattern for that chapter "
            "and the practice set attached to it. Each guide links to its "
            "subject hub, the related notes and the quiz that tests it."
        ),
        "empty_h3": "No topic guide published yet",
        "empty_p": ("Topic guides are being built out from the notes that are "
                    "already reviewed. Until each chapter is complete, the "
                    "study notes and daily practice below cover the same "
                    "ground one idea at a time."),
        "empty_cta": ("study-notes.html", "Read the study notes"),
        "schema_hub": "Topic Guides",
    },
    "daily-practice": {
        "file": "daily-practice.html",
        "dir": "daily-practice",
        "prefix": "practice",
        "eyebrow": "Today's Work, Written Down",
        "h1": "Daily Practice Sets for Punjab Exams",
        "title": "Daily Practice for Punjab Exams | House of Aspirants",
        "description": (
            "Daily practice sets for Punjab exams - the questions attempted "
            "today, why each answer is what it is and the revision notes that "
            "come out of the mistakes."
        ),
        "keywords": ("daily practice Punjab Police, daily MCQ set PSSSB, "
                     "everyday practice questions, daily revision Punjab exam"),
        "lead": (
            "A practice set is not finished when the answers are checked: the "
            "written part explains each answer and lists what to revise from "
            "the ones that went wrong."
        ),
        "answer": (
            "Every daily practice page records the set attempted that day with "
            "the reasoning behind each answer and a short revision list at the "
            "end. It links straight to the quiz it came from, the notes behind "
            "it and yesterday's set, so the streak stays intact."
        ),
        "empty_h3": "No daily practice set published yet",
        "empty_p": ("Practice pages are published alongside the quiz, one set "
                    "at a time. The daily quiz itself runs every day and keeps "
                    "your streak, so start there."),
        "empty_cta": ("quiz.html?mode=daily", "Open the daily quiz"),
        "schema_hub": "Daily Practice",
    },
    "success-stories": {
        "file": "success-stories.html",
        "dir": "success-stories",
        "prefix": "story",
        "eyebrow": "Attempts, Told Honestly",
        "h1": "Competitive Exam Success Stories",
        "title": "Success Stories | House of Aspirants",
        "description": (
            "Exam success stories told by the aspirant who lived them - the "
            "attempt, the mistakes, what changed in the preparation and the "
            "part of the method worth copying."
        ),
        "keywords": ("success story Punjab Police, PSSSB selection story, "
                     "exam preparation experience, how I cleared Punjab exam"),
        "lead": (
            "A story is published only when the aspirant tells their own "
            "attempt: the paper, the timeline, the parts that failed and the "
            "change that made the difference. Nothing here is written on "
            "someone else's behalf."
        ),
        "answer": (
            "Each success story names the exam and the attempt, describes the "
            "preparation as it actually happened and ends with the specific "
            "habits that are worth copying. It links into the strategy archive "
            "and the study material mentioned, so reading a story turns into "
            "doing the work."
        ),
        "empty_h3": "No success story published yet",
        "empty_p": ("Stories are published only when an aspirant shares their "
                    "own attempt, so this page stays empty rather than "
                    "carrying a claimed result. The strategy archive holds the "
                    "methods that are already documented."),
        "empty_cta": ("strategy.html", "Read the strategy archive"),
        "schema_hub": "Success Stories",
    },
    "book-recommendations": {
        "file": "book-recommendations.html",
        "dir": "book-recommendations",
        "prefix": "book",
        "eyebrow": "What to Buy, What to Skip",
        "h1": "Book Recommendations for Punjab Exams",
        "title": "Book Recommendations | House of Aspirants",
        "description": (
            "Book recommendations for Punjab exam preparation - what each book "
            "covers, who it is actually for, which chapters matter and how to "
            "use it alongside free notes."
        ),
        "keywords": ("best books Punjab Police exam, PSSSB book list, Punjab "
                     "GK book recommendation, which book for PPSC preparation"),
        "lead": (
            "One book, one subject, one honest answer: what it covers, who it "
            "is for, which chapters are worth the hours and what to skip "
            "entirely."
        ),
        "answer": (
            "A recommendation names the book and the subject it serves, says "
            "who will get value from it and who should pass, and maps its "
            "chapters onto the free notes and quizzes on this portal so you "
            "never buy twice."
        ),
        "empty_h3": "No book recommended yet",
        "empty_p": ("Books are listed only after they have been used for a "
                    "full preparation cycle, so nothing is recommended from a "
                    "blurb. The free notes below already cover the first "
                    "version of every subject."),
        "empty_cta": ("study-notes.html", "Start with the free notes"),
        "schema_hub": "Book Recommendations",
    },
}

# =============================================================================
# NAVIGATION - generated, never hand-edited.
# scripts/build_content.py writes the Study menu, the drawer Study group and
# the footer Study column between markers in assets/js/core.js from this one
# table, so a collection added here reaches the header, the drawer, the footer,
# the sitemap and the search index in the same run. No HTML or JS is edited by
# hand - seo_check fails the build if any hub drops out of the chrome.
# =============================================================================
HUB_NAV = {                          # hub file stem -> data-nav highlight key
    # Study Material is a Study page like every other hub in the Study menu,
    # so it lights up the same `notes` key the drawer and header already use.
    "study-material": "notes",
    "study-notes": "notes", "current-affairs": "ca", "magazine": "magazine",
    "strategy": "strategy", "live-sessions": "sessions",
    "recruitment": "recruitment", "blogs": "blogs", "news": "news",
    "announcements": "announcements", "pdfs": "pdfs", "archives": "archives",
    "expected-mcqs": "expected-mcqs",
    "previous-year-questions": "previous-year-questions",
    "personal-notes": "personal-notes", "subject-guides": "subject-guides",
    "topic-guides": "topic-guides", "daily-practice": "daily-practice",
    "success-stories": "success-stories",
    "book-recommendations": "book-recommendations",
}

NAV_ENTRY = {                        # collection -> (English label, emoji)
    "study-material": ("Study Material", "\U0001f4da"),
    "notes": ("Study Notes", "\U0001f4dd"),
    "current-affairs": ("Current Affairs", "\U0001f5de️"),
    "magazine": ("Monthly Magazine", "\U0001f4d6"),
    "strategy": ("Preparation Strategy", "\U0001f3af"),
    "sessions": ("Live Sessions", "\U0001f3a5"),
    "recruitment": ("Recruitment", "\U0001f4cb"),
    "expected-mcqs": ("Expected MCQs", "\U0001f9e0"),
    "previous-year-questions": ("Previous Year Questions", "\U0001f4dc"),
    "blogs": ("Blog", "✍️"),
    "news": ("News", "\U0001f4f0"),
    "announcements": ("Announcements", "\U0001f4e3"),
    "pdfs": ("Free PDFs", "\U0001f4c4"),
    "personal-notes": ("Personal Notes", "\U0001f4d3"),
    "subject-guides": ("Subject Guides", "\U0001f4da"),
    "topic-guides": ("Topic Guides", "\U0001f4d1"),
    "daily-practice": ("Daily Practice", "✅"),
    "success-stories": ("Success Stories", "\U0001f3c6"),
    "book-recommendations": ("Books", "\U0001f4d5"),
}
# Publication order of the Study menu (drives the header menu, the drawer
# group and the footer column - one table, three surfaces). Phase 4 inserts the
# new collections where an aspirant would look for them, not at the end.
NAV_ORDER = ["study-material",
             "notes", "subject-guides", "topic-guides", "personal-notes",
             "current-affairs", "magazine", "strategy", "sessions",
             "daily-practice", "recruitment", "expected-mcqs",
             "previous-year-questions", "success-stories",
             "book-recommendations", "pdfs", "blogs", "news", "announcements"]
NAV_EXTRA = [("archives.html", "Archives", "\U0001f5c2️")]
# Footer-only entries: every page in the content manifest has to be reachable
# from the chrome (header, drawer or footer). The generated profile pages and
# the search page belong at the bottom of every page rather than in the Study
# menu, so they are appended to the footer column only.
FOOT_EXTRA = [("search.html", "Search", "\U0001f50d")]

# Front matter contract per collection: required + optional keys (used for
# validation and for the authoring guide in content/README.md).
REQUIRED_FIELDS = {
    # Study material is discovered, never authored: title and description are
    # DERIVED from the file name when the file does not carry them, so the two
    # keys are guaranteed present by the time validation runs and are listed
    # here only as the contract a metadata.json override has to satisfy.
    "study-material": ["title", "description"],
    "notes": ["title", "description", "published", "subject"],
    "current-affairs": ["title", "description", "published"],
    "magazine": ["title", "description", "published", "month"],
    "strategy": ["title", "description", "published", "category"],
    "sessions": ["title", "description", "published", "date"],
    "recruitment": ["title", "description", "published", "post", "official_url"],
    "blogs": ["title", "description", "published"],
    "news": ["title", "description", "published"],
    "announcements": ["title", "description", "published"],
    "expected-mcqs": ["title", "description", "published", "subject"],
    "previous-year-questions": ["title", "description", "published", "exams"],
    "pdfs": ["title", "description", "file"],
    # Phase 4 collections (see the content model in content/README.md).
    "personal-notes": ["title", "description", "published", "subject"],
    "subject-guides": ["title", "description", "published", "subject"],
    "topic-guides": ["title", "description", "published", "subject"],
    "daily-practice": ["title", "description", "published", "subject"],
    "success-stories": ["title", "description", "published", "exam"],
    "book-recommendations": ["title", "description", "published", "subject"],
}

# Phase 2 - publishing fields every ARTICLE collection understands. The content
# automation engine reads these before it renders anything: identity (slug),
# ownership (author / reviewedBy), classification (category / subject / exam /
# tags), presentation (language, difficulty, readingTime, coverImage), linking
# (quiz, pdf) and publication control (featured, draft).
ARTICLE_COMMON = [
    "slug", "language", "author", "reviewedBy", "updated", "difficulty",
    "readingTime", "category", "tags", "subjects", "subject", "exams", "exam",
    "quiz", "pdf", "coverImage", "featured", "draft",
    # Phase 4 - the full platform content model, allowed on every document:
    # identity (id), presentation (subtitle / thumbnail), search & SEO
    # (seoTitle / seoDescription / keywords / summary), structure (toc),
    # linking (relatedContent / telegramLink / youtubeLink), evidence
    # (references / faq), publishing (status) and schema (schemaType).
    "id", "subtitle", "thumbnail", "seoTitle", "seoDescription", "keywords",
    "summary", "toc", "relatedContent", "telegramLink", "youtubeLink",
    "references", "faq", "schemaType", "status",
]

# Front-matter spellings the platform brief uses, mapped onto the keys this
# builder has always read. An alias is applied before validation, so a
# document written with `publishDate:` passes the required-field check exactly
# as if it had written `published:` - one canonical key per value, no drift.
ALIASES = {
    "publishDate": "published",
    "updatedDate": "updated",
    "examTags": "exams",
    "relatedQuiz": "quiz",
    "downloadPDF": "pdf",
    "tableOfContents": "toc",
}

# Publication states shared by every collection. `sessions` additionally
# accepts its own scheduling values (upcoming / past) in the same field.
PUB_STATUS = ("published", "draft", "archived")
SESSION_STATUS = ("upcoming", "past", "held")

# schemaType: the JSON-LD type a document publishes under. Kept to the types
# seo_check knows and rich_results_check can score, so a document can never
# invent a schema the gates cannot verify.
SCHEMA_TYPES = ("Article", "BlogPosting", "NewsArticle", "WebPage")

# The blog formats of the platform brief (compared case-insensitively after
# spaces are turned into hyphens).
BLOG_CATEGORIES = ("preparation-experience", "study-plans", "time-management",
                   "motivation", "book-reviews", "mistakes", "strategy-articles",
                   "exam-analysis")

OPTIONAL_FIELDS = {
    # Study material: everything the optional metadata.json sidecar may carry.
    # Dates are optional on purpose - a file with no date in its name and no
    # override simply has none, and the card shows no "last updated" rather
    # than inventing one (a fabricated date would drift on every rebuild).
    "study-material": ["published", "updated", "language", "keywords",
                       "featured", "new", "popular", "readingTime",
                       "difficulty", "subject", "subjects", "exams", "tags",
                       "category", "slug", "file", "pdf", "author"],
    "notes": ["updated", "author", "difficulty", "exams", "subjects", "tags",
              "pdf", "slug"],
    "magazine": ["updated", "month", "pdf", "quiz", "highlights", "tags",
                 "subjects", "cover", "cover_width", "cover_height",
                 "expected_mcqs", "important_questions", "revision_notes",
                 "cover_alt"],
    "strategy": ["updated", "category", "difficulty", "exams", "subjects",
                 "tags", "pdf"],
    "sessions": ["updated", "date", "time", "start_time", "platform", "join",
                 "status", "questions", "doubts", "summary", "tags", "subjects",
                 "poster", "recording", "resources"],
    "recruitment": ["updated", "post", "exam", "official_url", "official_source",
                    "eligibility", "syllabus", "selection", "dates", "pdf",
                    "expected_questions", "previous_papers", "tags", "subjects"],
    "current-affairs": ["updated", "category", "difficulty", "exam", "pdf"],
    "blogs": ["updated", "category", "difficulty", "pdf"],
    "news": ["updated", "category", "official_url", "official_source", "pdf"],
    "announcements": ["updated", "category", "join", "pdf"],
    "expected-mcqs": ["updated", "difficulty", "exams", "subjects", "tags",
                      "quiz", "pdf"],
    "previous-year-questions": ["updated", "difficulty", "tags", "quiz", "pdf",
                                "subjects"],
    "pdfs": ["file", "subject", "exams", "tags", "note"],
    # Phase 4 collections.
    "personal-notes": ["updated", "difficulty", "exams", "subjects", "tags"],
    "subject-guides": ["updated", "difficulty", "exams", "subjects", "tags"],
    "topic-guides": ["updated", "topic", "difficulty", "exams", "subjects",
                     "tags"],
    "daily-practice": ["updated", "difficulty", "exams", "subjects", "tags",
                       "quiz"],
    "success-stories": ["updated", "post", "difficulty", "tags", "subjects"],
    "book-recommendations": ["updated", "book", "book_author", "publisher",
                             "exams", "subjects", "tags", "difficulty"],
}
for _coll in list(OPTIONAL_FIELDS):
    if _coll != "pdfs":
        OPTIONAL_FIELDS[_coll] = sorted(
            set(OPTIONAL_FIELDS[_coll]) | set(ARTICLE_COMMON))
# `type` names the content template a document follows (see
# scripts/content_engine.py). It is optional - every collection has a default -
# but when present it must be one of the registered templates.
KNOWN_EXTRA = {"slug", "title_pa", "description_pa", "type"}


def apply_aliases(meta, where):
    """Rewrite platform spellings onto the canonical keys, in place."""
    for src, dst in ALIASES.items():
        if src not in meta:
            continue
        if dst in meta and meta[dst] not in (None, "", []):
            warn(f"{where}: {src!r} ignored, {dst!r} is already set")
        else:
            meta[dst] = meta[src]
        del meta[src]


# =============================================================================
# AUTHOR REGISTRY - data/authors.json
# One registry behind three surfaces: the byline on every document, the Person
# node in its JSON-LD and the generated author profile page. A document may
# only name an author who exists here, which is why a byline can never be an
# invented name.
# =============================================================================
AUTHORS_PATH = ROOT / "data" / "authors.json"
_AUTHORS = {"loaded": False, "list": []}


def load_authors():
    if _AUTHORS["loaded"]:
        return _AUTHORS["list"]
    _AUTHORS["loaded"] = True
    if not AUTHORS_PATH.exists():
        err("data/authors.json missing: the author system needs a registry")
        return _AUTHORS["list"]
    try:
        data = json.loads(AUTHORS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"data/authors.json unreadable: {e}")
        return _AUTHORS["list"]
    people = data.get("authors")
    if not isinstance(people, list) or not people:
        err("data/authors.json: 'authors' must be a non-empty list")
        return _AUTHORS["list"]
    seen = set()
    for a in people:
        if not isinstance(a, dict):
            err("data/authors.json: every entry must be an object")
            continue
        aid = str(a.get("id") or "")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,62}", aid):
            err(f"data/authors.json: id {aid!r} must be lowercase letters, "
                f"digits and hyphens")
            continue
        if aid in seen:
            err(f"data/authors.json: duplicate id {aid!r}")
        seen.add(aid)
        if not str(a.get("name") or "").strip():
            err(f"data/authors.json: author {aid!r} needs a name")
        a.setdefault("type", "Person")
        if a["type"] not in ("Person", "Organization"):
            err(f"data/authors.json: {aid!r} type must be Person or "
                f"Organization (got {a['type']!r})")
        if a["type"] == "Person":
            a.setdefault("profile", True)
        if not str(a.get("bio") or "").strip():
            err(f"data/authors.json: {aid!r} needs a bio")
        if a.get("credentials") and not isinstance(a["credentials"], list):
            err(f"data/authors.json: {aid!r} credentials must be a list")
    _AUTHORS["list"] = people
    return people


def author_names():
    return [str(a.get("name", "")) for a in load_authors()]


def _author_by_name(value):
    v = str(value or "").strip().lower()
    if not v:
        return None
    for a in load_authors():
        if v in (str(a.get("name", "")).strip().lower(),
                 str(a.get("id", "")).strip().lower()):
            return a
    return None


def author_profile_file(author):
    """Generated profile page for a registered Person, '' for the team."""
    if not author or author.get("type") != "Person" or not author.get("profile"):
        return ""
    return f"author-{author['id']}.html"


def author_href(author, lang="en"):
    """Linkable profile path for a byline ('' when the byline is the team)."""
    f = author_profile_file(author)
    if not f:
        return ""
    return f"/{f}" if lang == "pa" else f


def validate_meta(coll, slug, meta, where, required=None):
    """Check one document's front matter against its collection contract.

    `required` overrides the collection's required keys - only the PDF-drop
    path uses it, because a PDF that was dropped into a folder cannot invent
    the fields a hand-written document would carry (subject, post, official
    URL...). Everything else - title, description, dates, schema, authors - is
    still held to exactly the same rules.
    """
    apply_aliases(meta, where)
    known = set(REQUIRED_FIELDS[coll]) | set(OPTIONAL_FIELDS[coll]) | KNOWN_EXTRA
    # Normalise list fields first: `exams: Punjab Police` (no brackets) is a
    # single item, not a string to be iterated character by character.
    for key in LIST_FIELDS & set(meta):
        if isinstance(meta[key], str):
            meta[key] = [meta[key]] if meta[key].strip() else []
        elif not isinstance(meta[key], list):
            err(f"{where}: {key} must be a list")
            meta[key] = []
    for key in (REQUIRED_FIELDS[coll] if required is None else required):
        if key not in meta or meta[key] in ("", None, []):
            err(f"{where}: required front matter field {key!r} missing or empty")
    if meta.get("type") is not None:
        tkey = str(meta["type"]).strip()
        tpl = TEMPLATES.get(tkey)
        if not tpl:
            err(f"{where}: unknown content template {tkey!r} - run "
                f"python3 scripts/new_content.py --list")
        elif tpl["collection"] != coll:
            err(f"{where}: template {tkey!r} publishes in "
                f"content/{tpl['collection']}/, not content/{coll}/")
    for key in meta:
        if key not in known:
            warn(f"{where}: unknown front matter field {key!r} (ignored)")

    title = str(meta.get("title", ""))
    if title and len(title) > 60:
        err(f"{where}: title is {len(title)} chars, the site limit is 60")
    desc = str(meta.get("description", ""))
    if desc and not (140 <= len(desc) <= 160):
        err(f"{where}: description is {len(desc)} chars, the site range is 140-160 "
            f"characters (got: {desc[:70]!r}...)")
    for dkey in ("published", "updated", "date"):
        if meta.get(dkey) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta[dkey])):
            err(f"{where}: {dkey} must be YYYY-MM-DD (got {meta[dkey]!r})")
    # --- Phase 2 publishing fields ------------------------------------------
    for bkey in ("featured", "draft", "new", "popular"):
        if bkey in meta and not isinstance(meta[bkey], bool):
            if str(meta[bkey]).strip().lower() in ("yes", "1", "no", "0"):
                meta[bkey] = str(meta[bkey]).strip().lower() in ("yes", "1", "true")
            else:
                err(f"{where}: {bkey} must be true or false (got {meta[bkey]!r})")
                meta[bkey] = False
    if meta.get("language") is not None:
        got = str(meta["language"]).strip().lower()
        if coll == STUDY_DIR and re.fullmatch(r"[a-z]{2,8}", got or " "):
            # Study material's language is the language the FILE is written
            # in, read from the language folder it sits in (or its name or its
            # sidecar). It says nothing about which URL the page lives at, and
            # a subject may be published in any language, so a folder this
            # site has never seen is a language rather than a build error.
            meta["language"] = got
        elif got not in ("en", "pa"):
            err(f"{where}: language must be 'en' or 'pa' (got {meta['language']!r})")
        elif coll == STUDY_DIR:
            # never held to the .pa.md variant rule that governs authored
            # documents: a study file's language is a display field.
            meta["language"] = got
        else:
            want = "pa" if where.endswith(".pa.md") else "en"
            if got != want:
                err(f"{where}: language {got!r} contradicts the file variant "
                    f"(a .pa.md file publishes as 'pa', a .md file as 'en')")
    if meta.get("readingTime") is not None and (
            not str(meta["readingTime"]).isdigit() or int(meta["readingTime"]) < 1):
        err(f"{where}: readingTime must be a whole number of minutes "
            f"(got {meta['readingTime']!r})")
    if meta.get("slug") and not re.fullmatch(
            r"[a-z0-9][a-z0-9-]*", str(meta["slug"])):
        err(f"{where}: slug must be lowercase letters, digits and hyphens only "
            f"(got {meta['slug']!r})")
    for nkey in ("author", "reviewedBy", "category"):
        if meta.get(nkey) is not None and len(str(meta[nkey])) > 60:
            err(f"{where}: {nkey} must be 60 characters or less "
                f"(got {len(str(meta[nkey]))})")
    if coll == "recruitment" and meta.get("official_url") and \
            not official_url_ok(str(meta["official_url"])):
        err(f"{where}: official_url must be a government domain "
            f"(.gov.in / .nic.in / pspcl) - got {meta['official_url']!r}")
    if meta.get("pdf") and not (ROOT / str(meta["pdf"])).exists():
        err(f"{where}: pdf file not found at {meta['pdf']!r}")
    if meta.get("quiz") and not (ROOT / str(meta["quiz"])).exists():
        err(f"{where}: quiz file not found at {meta['quiz']!r}")
    if meta.get("coverImage") and not meta.get("cover"):
        meta["cover"] = meta["coverImage"]     # coverImage is the friendly alias
    if meta.get("cover") and not (ROOT / str(meta["cover"])).exists():
        err(f"{where}: cover image not found at {meta['cover']!r}")
    for dkey in ("cover_width", "cover_height"):
        if meta.get(dkey) and not str(meta[dkey]).isdigit():
            err(f"{where}: {dkey} must be a positive integer (got {meta[dkey]!r})")
    if meta.get("join") and not re.fullmatch(
            r"https://[^\s]+", str(meta["join"])):
        err(f"{where}: join must be an https:// URL (got {meta['join']!r})")
    if meta.get("file") and not (ROOT / str(meta["file"])).exists():
        err(f"{where}: file not found at {meta['file']!r} (add it or remove the record)")
    subj = str(meta.get("subject", ""))
    if subj and subj not in SUBJECT_IDS:
        err(f"{where}: unknown subject id {subj!r} (known: {', '.join(sorted(SUBJECT_IDS))})")
    for s in as_list(meta.get("subjects")):
        if str(s) not in SUBJECT_IDS:
            err(f"{where}: unknown subject id {s!r} (known: "
                f"{', '.join(sorted(SUBJECT_IDS))})")

    # --- Phase 4 content model ----------------------------------------------
    # SEO pair: an explicit seoTitle / seoDescription replaces the generated
    # pair for this document only, so it is held to the same limits the
    # generated pair is held to.
    if meta.get("seoTitle") is not None and len(str(meta["seoTitle"])) > 60:
        err(f"{where}: seoTitle is {len(str(meta['seoTitle']))} chars, the site "
            f"limit is 60")
    if meta.get("seoDescription") is not None and meta["seoDescription"] and not (
            140 <= len(str(meta["seoDescription"])) <= 160):
        err(f"{where}: seoDescription is {len(str(meta['seoDescription']))} "
            f"chars, the site range is 140-160 characters")
    if meta.get("subtitle") is not None and len(str(meta["subtitle"])) > 120:
        err(f"{where}: subtitle is {len(str(meta['subtitle']))} chars (max 120)")
    if meta.get("summary") is not None and len(str(meta["summary"])) > 320:
        err(f"{where}: summary is {len(str(meta['summary']))} chars (max 320)")
    if meta.get("id") is not None and not re.fullmatch(
            r"[a-z][a-z0-9-]{1,62}", str(meta["id"])):
        err(f"{where}: id must be lowercase letters, digits and hyphens only "
            f"(got {meta['id']!r})")
    if meta.get("keywords") is not None:
        kws = as_list(meta["keywords"])
        if not kws:
            err(f"{where}: keywords must not be empty (got {meta['keywords']!r})")
        for kw in kws:
            if not str(kw).strip() or len(str(kw)) > 48:
                err(f"{where}: keyword {str(kw)!r} must be 1-48 characters")
        if len(kws) > 12:
            err(f"{where}: {len(kws)} keywords (max 12)")
    if meta.get("thumbnail") and not (
            str(meta["thumbnail"]).startswith("https://")
            or (ROOT / str(meta["thumbnail"])).exists()):
        err(f"{where}: thumbnail must be an https:// URL or an existing file "
            f"(got {meta['thumbnail']!r})")
    for skey in ("telegramLink", "youtubeLink"):
        if meta.get(skey):
            url = str(meta[skey])
            ok = (url.startswith("https://t.me/") if skey == "telegramLink"
                  else bool(re.match(r"https://(www\.)?(youtube\.com|youtu\.be)/",
                                     url)))
            if not ok:
                err(f"{where}: {skey} must be a {skey} link on its own platform "
                    f"(got {url!r})")
    if meta.get("schemaType") is not None and str(meta["schemaType"]) not in SCHEMA_TYPES:
        err(f"{where}: schemaType must be one of {', '.join(SCHEMA_TYPES)} "
            f"(got {meta['schemaType']!r})")
    if meta.get("toc") is not None and not isinstance(meta["toc"], bool):
        val = str(meta["toc"]).strip().lower()
        if val in ("yes", "1", "true", "no", "0", "false"):
            meta["toc"] = val in ("yes", "1", "true")
        else:
            err(f"{where}: toc must be true or false (got {meta['toc']!r})")
    status = str(meta.get("status") or "").strip().lower()
    if status:
        allowed = PUB_STATUS + (SESSION_STATUS if coll == "sessions" else ())
        if status not in allowed:
            err(f"{where}: status must be one of {', '.join(allowed)} "
                f"(got {meta['status']!r})")
        if status in ("draft", "archived"):
            meta["draft"] = True          # never published, whatever `draft:` says
    if meta.get("relatedContent"):
        for target in as_list(meta["relatedContent"]):
            t = str(target)
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*(/[a-z0-9][a-z0-9-]*)*"
                                r"(\.html)?(#([a-z0-9][a-z0-9-]*))?", t):
                err(f"{where}: relatedContent entry {t!r} must be a site path "
                    f"like 'study-notes' or 'note-some-page.html'")
    if meta.get("references"):
        for ref in as_list(meta["references"]):
            if isinstance(ref, dict):
                if not str(ref.get("title", "")).strip():
                    err(f"{where}: each reference needs a title")
                url = str(ref.get("url", ""))
                if url and not url.startswith(("https://", "http://")):
                    err(f"{where}: reference url must be http(s):// "
                        f"(got {url!r})")
            elif not str(ref).strip():
                err(f"{where}: empty reference")
    if meta.get("faq"):
        for i, pair in enumerate(as_list(meta["faq"]), 1):
            if isinstance(pair, dict):
                q = pair.get("q") or pair.get("question")
                a = pair.get("a") or pair.get("answer")
            elif isinstance(pair, (list, tuple)) and len(pair) == 2:
                q, a = pair[0], pair[1]
            else:
                q, a = (None, None)
            if not str(q or "").strip() or not str(a or "").strip():
                err(f"{where}: faq entry {i} must be a question/answer pair "
                    f"(write `q:` / `a:` keys)")
    if meta.get("status"):
        meta["status"] = str(meta["status"]).strip().lower()
    if coll == "blogs" and meta.get("category"):
        cat = re.sub(r"[\s_]+", "-", str(meta["category"]).strip().lower())
        if cat not in BLOG_CATEGORIES:
            err(f"{where}: category {meta['category']!r} is not one of the "
                f"blog formats {', '.join(BLOG_CATEGORIES)}")
    if meta.get("author"):
        author = str(meta["author"])
        if _author_by_name(author) is None:
            err(f"{where}: unknown author {author!r} - register them in "
                f"data/authors.json (known: {', '.join(author_names())})")
    if coll == "sessions" and meta.get("resources"):
        for res in as_list(meta["resources"]):
            if isinstance(res, dict):
                url = str(res.get("url", ""))
            else:
                text = str(res)
                url = (text.split("::", 1)[1] if "::" in text else text).strip()
            if not url or ("://" in url and not url.startswith("https://")) \
                    or url.lower().startswith(("javascript:", "data:", "//")):
                err(f"{where}: session resource must be an https:// URL or a "
                    f"site path (got {url!r})")
    if meta.get("poster") and not (
            str(meta["poster"]).startswith("https://")
            or (ROOT / str(meta["poster"])).exists()):
        err(f"{where}: poster must be an https:// URL or an existing file "
            f"(got {meta['poster']!r})")


def official_url_ok(url):
    m = re.match(r"^https?://([^/]+)", url.strip())
    if not m:
        return False
    host = m.group(1).lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host in OFFICIAL_HOSTS or host.endswith(OFFICIAL_HOST_SUFFIXES)


# =============================================================================
# 4. PAGE SCAFFOLD  (head + chrome hooks - mirrors the hand-written pages so
#                    seo_check treats generated pages exactly like the rest)
# =============================================================================
def _noindex_urls():
    """Canonical URLs listed in data/noindex.json (crawlable, never indexed)."""
    try:
        cfg = json.loads((ROOT / "data" / "noindex.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {f"{DOMAIN}/{str(f)[:-5]}" for f in cfg.get("pages", [])
            if str(f).endswith(".html")}


NOINDEX_URLS = _noindex_urls()
ARCHIVE_MIN_DOCS = 3   # tag/category archives below this stay noindex


def robots_for(url):
    return "noindex, follow" if url in NOINDEX_URLS else "index, follow"


def head(title, desc, keywords, url, og_type, jsonld, lang="en", alternates=(),
         image="", nested=False):
    """Page scaffold. `lang` drives <html lang>, the /pa/ base URL and hreflang.

    Punjabi pages publish under /pa/, so they carry <base href="/">: the shared
    chrome (header, drawer, footer) links the whole site with relative URLs and
    the base element keeps every one of them resolving from the site root.
    `nested` says the same for a page that lives in a sub-directory of its own
    (a Previous Year Questions exam page at pyq/<slug>/index.html): one base,
    no depth-aware asset prefixes threaded through every chrome block.
    """
    base = '  <base href="/">\n' if (lang == "pa" or nested) else ""
    og_image = image or OG_ABS
    if og_image.startswith("/"):
        og_image = f"{DOMAIN}{og_image}"
    elif not og_image.startswith(("http://", "https://")):
        og_image = f"{DOMAIN}/{og_image.lstrip('/')}"
    hreflang = "".join(
        f'\n  <link rel="alternate" hreflang="{h}" href="{esc(u)}">'
        for h, u in alternates)
    return f"""<!DOCTYPE html>
<!-- {GENERATED_MARKER} -->
<html lang="{lang}" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{base}  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="keywords" content="{esc(keywords)}">
  <meta name="robots" content="{robots_for(url)}">
  <meta name="theme-color" content="#4f46e5">
  <link rel="canonical" href="{esc(url)}">{hreflang}
  <link rel="alternate" type="application/rss+xml" title="House of Aspirants"
        href="feed.xml">
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="House of Aspirants">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:locale" content="en_IN">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(desc)}">
  <meta name="twitter:image" content="{esc(og_image)}">
  <link rel="icon" href="assets/img/favicon-32.png" type="image/png" sizes="32x32">
  <link rel="apple-touch-icon" sizes="180x180" href="assets/img/icon-180.png">
  <link rel="manifest" href="manifest.webmanifest">
  <link rel="preconnect" href="https://t.me">
  <link rel="dns-prefetch" href="//t.me">
  <link rel="dns-prefetch" href="//instagram.com">
  <link rel="dns-prefetch" href="//youtube.com">
  <link rel="preload" href="assets/css/style.css" as="style">
  <link rel="stylesheet" href="assets/css/style.css">
  <link rel="preload" href="assets/img/logo-sm.png" as="image" type="image/png">
  <script type="application/ld+json">
{jsonld}
  </script>
</head>
<body data-page="{og_page_key(url)}">
  <div data-site-header></div>
"""


def og_page_key(url):
    """body data-page key used for nav highlighting (matches data-nav keys)."""
    path = url.replace(DOMAIN, "")
    if path.startswith("/pa/"):
        path = path[3:]                       # the Punjabi edition mirrors the
    stem = path.strip("/").split(".", 1)[0]   # English page's nav key
    if stem in HUB_NAV:
        return HUB_NAV[stem]
    if path.startswith("/pyq/"):
        # A Previous Year Questions exam page (pyq/<slug>/index.html) lights up
        # the same nav key pyq.html and the collection hub already use.
        return "previous-year-questions"
    if path.startswith("/current-affairs/"):
        # A Current Affairs language or month page lights up the same nav key
        # current-affairs.html uses: they are the one Current Affairs door,
        # not a second section.
        return HUB_NAV.get("current-affairs", "ca")
    for key, prefix in (("ca", "/ca-"), ("blogs", "/blog-"),
                        ("news", "/news-"), ("announcements", "/announce-"),
                        ("notes", "/note"), ("magazine", "/magazine"),
                        ("strategy", "/strategy"), ("sessions", "/session"),
                        ("recruitment", "/recruit"), ("expected-mcqs", "/expected-"),
                        ("previous-year-questions", "/pyq-"),
                        ("personal-notes", "/pnote-"), ("subject-guides", "/sguide-"),
                        ("topic-guides", "/tguide-"), ("daily-practice", "/practice-"),
                        ("success-stories", "/story-"),
                        ("book-recommendations", "/book-")):
        if path.startswith(prefix):
            return key
    if path.startswith("/archives"):
        return "archives"
    return path.strip("/") or "home"


TAIL = """
  <div data-site-footer></div>

  <script src="assets/js/core.js" defer></script>
  <script src="assets/js/auth.js" defer></script>
  <script src="assets/js/content.js" defer></script>
</body>
</html>
"""


def breadcrumb_jsonld(crumbs):
    items = []
    for pos, (name, u) in enumerate(crumbs, 1):
        node = {"@type": "ListItem", "position": pos, "name": name}
        if u:
            node["item"] = u
        items.append(node)
    return json.dumps(items, ensure_ascii=False, indent=2)


def graph(nodes):
    body = ",\n".join("    " + json.dumps(n, ensure_ascii=False, indent=2).replace("\n", "\n    ")
                      for n in nodes)
    return ('  {\n    "@context": "https://schema.org",\n    "@graph": [\n'
            + body + "\n    ]\n  }")


def webpage_node(url, name, description, breadcrumb_id, kind="WebPage"):
    node = {
        "@type": kind,
        "@id": f"{url}#webpage",
        "name": name,
        "url": url,
        "description": description,
        "inLanguage": "en-IN",
        "isPartOf": {"@id": f"{DOMAIN}/#website"},
        "breadcrumb": {"@id": breadcrumb_id},
    }
    return node


def author_jsonld(rec):
    """The author node for a document's JSON-LD.

    A registered Person with a generated profile page publishes as a Person
    with its own URL, so the E-E-A-T claim is checkable; the editorial desk
    stays the Organization it has always been.
    """
    a = rec.get("author_ref")
    if a and author_profile_file(a):
        node = {"@type": "Person",
                "name": str(a["name"]),
                "url": f"{DOMAIN}/{author_profile_file(a)[:-5]}"}
        if a.get("role"):
            node["jobTitle"] = str(a["role"])
        if a.get("award"):
            node["award"] = str(a["award"])
        if a.get("sameAs"):
            node["sameAs"] = [str(x) for x in a["sameAs"]]
        return node
    return {
        "@type": "Organization",
        "name": rec.get("author") or BYLINE,
        "url": f"{DOMAIN}/about",
        "logo": {
            "@type": "ImageObject",
            "url": f"{DOMAIN}/assets/img/logo-sm.png",
            "width": 120,
            "height": 120,
        },
    }


def article_node(rec, url):
    st = str(rec.get("schemaType") or "Article")
    node = {
        "@type": [st] if st == "WebPage" else [st, "WebPage"],
        "@id": f"{url}#webpage",
        "name": rec["title"],
        "url": url,
        "headline": rec["title"],
        "description": rec["description"],
        "image": {
            "@type": "ImageObject",
            "@id": f"{OG_ABS}#image",
            "url": OG_ABS,
            "width": 1200,
            "height": 630,
        },
        "datePublished": rec["published"],
        "dateModified": rec.get("updated") or rec["published"],
        "inLanguage": "en-IN",
        # E-E-A-T: a registered author with a profile page publishes as a
        # Person pointing at that page; everything else keeps the team
        # Organization behind /about. The byline text is never free-running.
        "author": author_jsonld(rec),
        "publisher": {"@id": f"{DOMAIN}/#organization"},
        "isPartOf": {"@id": f"{DOMAIN}/#website"},
        "breadcrumb": {"@id": f"{url}#breadcrumb"},
        "mainEntityOfPage": {"@id": f"{url}#webpage"},
    }
    # Editorial keywords (front matter) travel into the schema as well as the
    # meta tag, so the document and its JSON-LD never disagree about topic.
    kw = [k.strip() for k in str(keywords_for(rec)).split(",") if k.strip()]
    if kw:
        node["keywords"] = ", ".join(kw)
    return node


def learning_resource_node(rec, url):
    """What a generated PDF page IS, in schema: a downloadable learning
    resource whose encoding is the file itself and whose abstract is the
    first page of that file, read by the scanner.

    No `numberOfPages` here: schema.org scopes that property to Book, and a
    page count the gates cannot verify would be worse than none."""
    node = {
        "@type": "LearningResource",
        "@id": f"{url}#learning-resource",
        "name": rec["title"],
        "url": url,
        "description": rec["description"],
        "learningResourceType": "PDF",
        "inLanguage": "en-IN",
        "publisher": {"@id": f"{DOMAIN}/#organization"},
    }
    summary = str(rec.get("summary") or "").strip()
    if summary:
        node["abstract"] = summary
    pdf = str((rec.get("meta") or {}).get("pdf") or "")
    if pdf:
        # DataDownload is the file's own type; MediaObject is the type that
        # owns contentUrl, so the node carries both and every property it
        # states is one schema.org really declares.
        node["encoding"] = {
            "@type": ["DataDownload", "MediaObject"],
            "contentUrl": f"{DOMAIN}/{pdf_href(pdf)}",
            "encodingFormat": "application/pdf",
        }
    src = str(rec.get("pdfPreview") or "")
    if src:
        w = int(rec.get("pdfPreviewW") or 0)
        h = int(rec.get("pdfPreviewH") or 0)
        node["image"] = {"@type": "ImageObject", "url": f"{DOMAIN}/{src}"}
        if w > 0 and h > 0:
            node["image"]["width"] = w
            node["image"]["height"] = h
    return node


def breadcrumb_node(crumbs):
    return {
        "@type": "BreadcrumbList",
        "@id": crumbs["id"],
        "itemListElement": json.loads(breadcrumb_jsonld(crumbs["items"])),
    }


# =============================================================================
# 4b. STUDY MATERIAL - folder discovery, file-name defaults, sidecar overrides
# -----------------------------------------------------------------------------
# content/study-material/<subject>/<file> is the Study system's only authoring
# surface, and nothing in this block is a list of anything. The folders on disk
# ARE the subjects, the file names ARE the titles, and the two metadata.json
# sidecars only decorate what was already derived. Drop a file, run the build,
# and it is discovered: no page to write, no registry to append to, no JSON to
# edit by hand.
#
# The PDFs are described twice - once here, once by build_content_manifest.ts
# (ci.sh diffs both answers) - so the file-name derivation is deliberately the
# SAME helpers the PDF drops use: title, slug, date, description. One naming
# rule across the whole platform.
# =============================================================================
STUDY_DIR = "study-material"           # content/study-material/
STUDY_EXTS = (".md", ".json")          # .pdf arrives through the scanner
STUDY_JSON_META = {                    # keys a .json file may carry itself
    "title", "description", "keywords", "language", "published", "updated",
    "featured", "new", "popular", "difficulty", "readingTime", "subject",
    "subjects", "exams", "tags", "category", "slug", "author",
}


def _study_json(path, what):
    """Read a JSON sidecar/file, failing the build loudly and precisely."""
    where = str(path.relative_to(ROOT))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        err(f"{where}: {what} is not valid JSON: {e}")
        return None
    if data is None:
        return None
    if not isinstance(data, dict):
        err(f"{where}: {what} must be a JSON object")
        return None
    return data


def study_registry():
    """The optional subject registry: content/study-material/metadata.json.

    Read once per subject-name lookup by design - a sidecar can change between
    runs and every reader (the shelf, the nav, the Study renderer) must see the
    same answer within one build."""
    return _study_json(CONTENT / STUDY_DIR / "metadata.json", "subject registry")


def study_subject_names():
    """folder id -> display name, from the optional subject registry.

    A folder is a subject whether or not it is listed here: anything missing is
    derived from the folder name, and a subject listed with no folder is
    ignored - so content/study-material/metadata.json can decorate a page but
    can never invent one."""
    reg = study_registry()
    out = {}
    for fid, cfg in (reg or {}).get("subjects", {}).items():
        if isinstance(cfg, str):
            cfg = {"name": cfg}
        if isinstance(cfg, dict):
            out[str(fid)] = str(cfg.get("name") or fid)
    return out


def study_subject_name(folder):
    return study_subject_names().get(folder) or folder.replace("-", " ").title()


# ---------------------------------------------------------------------------
# content/study-material/<subject>/<language>/<chapter>/<part file>
# ---------------------------------------------------------------------------
# The hierarchy below is READ, never configured. The first folder under the
# collection is a subject; the folder under it is the language the material is
# written in; the folder under that is the chapter; the files under them are
# the parts. Adding any of the four means creating a folder - there is no list
# of subjects, languages or chapters anywhere in this file to append to, and a
# subject with no language yet is still a subject (that is where the next
# folder goes).
STUDY_LANG = {
    "pa": {"code": "pa", "name": "Punjabi", "native": "\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40",
           "flag": "\U0001f1f5\U0001f1fa"},
    "en": {"code": "en", "name": "English", "native": "English",
           "flag": "\U0001f1ec\U0001f1e7"},
}
# Folder spellings that mean one of the languages above. Anything not in this
# table is still a language - its folder name simply becomes its name - so a
# `hindi/` folder is Hindi without a line of code changing.
STUDY_LANG_ALIAS = {"punjabi": "pa", "panjabi": "pa", "gurmukhi": "pa",
                    "gurumukhi": "pa", "pbi": "pa", "pa": "pa",
                    "english": "en", "en": "en"}


def _is_material(path):
    """A publishable material file: never a README, never a metadata.json."""
    return (path.is_file()
            and not path.name.lower().startswith("readme")
            and path.name != "metadata.json"
            and path.suffix.lower() in (".pdf",) + STUDY_EXTS)


def study_locator(path):
    """(subject folder, language folder, chapter folder) for one file.

    Shorter layouts still resolve, so nothing already on disk has to move
    before this rule takes effect: a file straight under a subject has no
    language or chapter folder yet, and one folder deep is the language it
    was dropped in."""
    parts = Path(path).parts
    if STUDY_DIR not in parts:
        return "", "", ""
    tail = list(parts[parts.index(STUDY_DIR) + 1:])
    if len(tail) < 2:
        return "", "", ""           # configuration at the collection root
    dirs = tail[1:-1]               # the folders between subject and file
    return tail[0], (dirs[0] if len(dirs) >= 1 else ""), \
        (dirs[1] if len(dirs) >= 2 else "")


def study_lang_id(folder):
    """Folder name -> language id.

    The two languages this site is written in map onto their codes; any other
    folder becomes a language of its own, so languages are discovered rather
    than listed."""
    raw = str(folder or "").strip()
    if not raw:
        return ""
    if any("\u0a00" <= c <= "\u0a7f" for c in raw):
        return "pa"
    key = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return STUDY_LANG_ALIAS.get(key) or re.sub(r"[^a-z0-9]+", "", key) or ""


def study_lang(folder):
    """The display facts of one language folder: id, code, name, native name
    and flag. A language the site has never seen keeps its folder name as its
    name and carries no flag rather than a wrong one."""
    lid = study_lang_id(folder)
    if not lid:
        return {"id": "", "code": "", "name": "", "native": "", "flag": ""}
    known = STUDY_LANG.get(lid) or {}
    return {"id": lid, "code": lid,
            "name": known.get("name") or study_nice_name(folder),
            "native": known.get("native") or "",
            "flag": known.get("flag") or ""}


def study_language_from_name(stem):
    """The language a file claims, used only when it has no language folder.

    A folder always wins: where a file sits is something the publisher
    decided, and a name is only a guess."""
    text = str(stem).lower()
    if re.search(r"(^|[^a-z])(punjabi|panjabi|gurmukhi)([^a-z]|$)", text) \
            or any("\u0a00" <= c <= "\u0a7f" for c in str(stem)):
        return "pa"
    return "en"


def study_nice_name(folder):
    """`arrival-of-europeans` -> `Arrival of Europeans`.

    A numbered folder keeps its number and gains a colon, so
    `chapter-1-arrival-of-europeans` reads `Chapter 1: Arrival of Europeans`
    instead of four title-cased words in a row."""
    text = re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", str(folder or ""))).strip()
    if not text:
        return str(folder or "")
    # The language is already on the page: `sikhism-pa` reads `Sikhism`.
    bare = re.sub(r"(?i)\s+(pa|en|punjabi|english)$", "", text).strip()
    if bare:
        text = bare
    # `01 - Naav (Noun)` / `3 Naav`: the number orders the shelf and reads as
    # the chapter number - `Chapter 1: Naav (Noun)`.
    m = re.match(r"^0*(\d+)\s*[.)]?\s+(.+)$", text)
    if m:
        rest = m.group(2)
        # Keep an English gloss in brackets: `ਨਾਂਵ (Noun)`.
        pm = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", rest)
        label = (f"{pdf_title_from_name(pm.group(1))} ({pdf_title_from_name(pm.group(2))})"
                 if pm and pm.group(1).strip() else pdf_title_from_name(rest))
        return clip(f"Chapter {int(m.group(1))}: {label}")
    m = re.match(r"(?i)\b(chapter|lesson|unit|part|book|topic)\s+(\d+)\s+(.+)$",
                 text)
    if m:
        return clip(f"{pdf_title_from_name(m.group(1))} {m.group(2)}: "
                    f"{pdf_title_from_name(m.group(3))}")
    return pdf_title_from_name(text)


def study_part_number(stem):
    """`part-3-english` / `part 3 (english)` / `part_4` -> the number."""
    m = re.search(r"(?i)\bpart[\s._-]*(\d+)\b", ascii_fold(stem))
    return int(m.group(1)) if m else 0


def study_part_key(path):
    """Reading order: the number written into the name, then the name.

    `part 2` sorts before `part 10`, and a file carrying no number - a single
    `notes.pdf`, a chapter's one and only part - sorts last and still gets a
    position of its own."""
    n = study_part_number(path.stem)
    return (0 if n else 1, n, path.name.lower())


def study_siblings(path):
    """Every file in this one folder, in reading order (cached per folder)."""
    full = Path(path)
    if not full.is_absolute():
        full = ROOT / full
    folder = full.parent
    if folder not in _STUDY_SIBLINGS:
        try:
            kids = [p for p in folder.iterdir() if _is_material(p)]
        except OSError:
            kids = []
        _STUDY_SIBLINGS[folder] = sorted(kids, key=study_part_key)
    return _STUDY_SIBLINGS[folder]


_STUDY_SIBLINGS = {}


def study_part_of(path):
    """(1-based position of this part, how many parts its chapter holds)."""
    sibs = study_siblings(path)
    full = Path(path)
    if not full.is_absolute():
        full = ROOT / full
    try:
        return sibs.index(full) + 1, len(sibs)
    except ValueError:
        return 1, max(1, len(sibs))


def study_title_for(path):
    """`Arrival of Europeans - Part 3 (English)`.

    The title is assembled from the folders the file sits in and the part's
    position among its siblings - not from the file name - so `part 3
    (english).pdf` and `part-3-english-en.pdf` read as the same part of the
    same chapter, and the language is on the face of the page because an
    English part and a Punjabi part of one chapter share a name."""
    subject, lang_folder, chapter = study_locator(path)
    language = study_lang_id(lang_folder) or study_language_from_name(path.stem)
    if lang_folder:
        lang_name = study_lang(lang_folder).get("name") or "English"
    else:
        lang_name = (STUDY_LANG.get(language) or {}).get("name") or "English"
    position, total = study_part_of(path)
    chapter_name = study_nice_name(chapter or path.stem)
    # A chapter with one file has no parts to tell apart: "Part 1" would be
    # noise on the page, the card and the download.
    if total <= 1:
        return clip(f"{chapter_name} ({lang_name})")
    return clip(f"{chapter_name} - Part {position} ({lang_name})")


def study_files(subject):
    """Every material file of one subject, at any depth, sorted by path.

    A new chapter folder under a language folder needs no registration
    anywhere: it publishes on the next build because it is a folder."""
    d = CONTENT / STUDY_DIR / subject
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*")
                  if _is_material(p) and not any(
                      part.startswith((".", "_"))
                      for part in p.relative_to(d).parts[:-1]))


def study_paths():
    """Every non-PDF material file in the collection, at any depth.

    The collection root is configuration (this README, the subject registry)
    and publishes nothing: a file has to sit under a subject folder."""
    cdir = CONTENT / STUDY_DIR
    if not cdir.is_dir():
        return []
    out = []
    for subject_dir in sorted(p for p in cdir.iterdir()
                              if p.is_dir() and not p.name.startswith((".", "_"))):
        out.extend(p for p in study_files(subject_dir.name)
                   if p.suffix.lower() in STUDY_EXTS)
    return sorted(out)


def study_overrides(path):
    """The metadata.json layers sitting beside a file, nearest one winning.

    A sidecar may live in the file's own folder, in a language folder or in
    the subject folder; each layer is merged over the one before it, so the
    word closest to the file is the word that counts. Two shapes are accepted
    and nothing else, so a sidecar can never be misread: the documented map
    keyed by file name, and - for a folder holding exactly one material file -
    a plain object applied to that file."""
    path = Path(path)
    subject, _, _ = study_locator(path)
    if not subject:
        return {}
    subject_dir = CONTENT / STUDY_DIR / subject
    layers, here = [], path.parent
    while True:
        side = here / "metadata.json"
        if side.is_file():
            layers.append((side, here))
        if here == subject_dir or here == here.parent:
            break
        here = here.parent

    def _clean(node):
        # `$note`, `_comment` and friends are for the person reading the file;
        # they are never a field of the document it describes.
        return {k: v for k, v in node.items() if not str(k).startswith(("$", "_"))}

    out = {}
    for side, folder in reversed(layers):        # furthest first, nearest last
        data = _study_json(side, "study material overrides")
        if not data:
            continue
        node = data.get(path.name)
        if isinstance(node, dict):
            out.update(_clean(node))
            continue
        if any(str(k).lower().endswith((".pdf", ".md", ".json")) for k in data):
            continue                             # a map without this file's key
        files = [p for p in folder.iterdir() if _is_material(p)]
        if len(files) == 1 and files[0].name == path.name:
            out.update(_clean(data))
    return out


def study_auto_meta(path, subject):
    """What the build knows about a file before anything is written down.

    The folders carry the subject, the language and the chapter; the name
    carries the part number and any date; the description is generated in the
    site's 140-160 character window. The generator is study-specific rather
    than the PDF one on purpose: an .md or .json file is not something you
    "download as a PDF", and a description that lies about the format is worse
    than no description."""
    stem = path.stem
    _, lang_folder, _ = study_locator(path)
    title = study_title_for(path)
    name = study_subject_name(subject)
    meta = {
        "title": title,
        "description": study_description(title, name),
        "category": name,
        "keywords": [clip(title, 48), name, "Study Material", stem],
        "language": study_lang_id(lang_folder) or study_language_from_name(stem),
    }
    when = pdf_date_from_name(stem)
    if when:
        meta["published"] = when
    return meta


def study_description(title, subject):
    """140-160 characters, assembled from the title and the subject.

    Same window as every other page on the site, but the clauses are true of
    any file format - PDF, Markdown or JSON - because this generator has to
    describe a file it has never been told the type of."""
    text = f"{title} - free study material from House of Aspirants."
    clauses = [
        f" {subject} material, filed under its subject, language and chapter.",
        " Read it online or keep it for offline revision.",
        " No sign-up, no email wall, no paid tier.",
        " Listed under Study Material with its language and reading time.",
        " Free for every aspirant.",
    ]
    for _ in range(4):
        for clause in clauses:
            if len(text) >= 140:
                break
            if len(text) + len(clause) <= 160:
                text += clause
        if len(text) >= 140:
            break
    if len(text) < 140:
        text += " Free to read and download, generated from the file name."
    while len(text) > 160:
        text = text.rsplit(" ", 1)[0]
    if not (140 <= len(text) <= 160):          # pragma: no cover - guarded gate
        err(f"generated study description for {title!r} is {len(text)} chars "
            f"(the site range is 140-160)")
    return text


def study_merge(base, *layers):
    """Later layers win; blanks never erase a value that was already derived."""
    out = dict(base)
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        for k, v in layer.items():
            if v not in (None, "", []):
                out[k] = v
    return out


def study_json_document(raw):
    """-> (meta, markdown) for a .json study file.

    A JSON file is its own metadata file: title, description, language and
    dates are read from its keys when present. Whatever it does not describe
    about itself is rendered - string content as Markdown, sections as
    headings, and anything else as a fenced block, because a study file that
    renders as unreadable braces is a study file nobody opens."""
    data = _study_json_flex(raw)
    if not isinstance(data, dict):
        data = {"content": raw.strip()}
    meta = {k: v for k, v in data.items() if k in STUDY_JSON_META}
    rest = {k: v for k, v in data.items() if k not in STUDY_JSON_META}
    body = data.get("content") or data.get("body") or data.get("text") or ""
    if not body and isinstance(data.get("sections"), list):
        parts = []
        for i, sec in enumerate(data["sections"], 1):
            if isinstance(sec, str):
                parts.append(sec)
            elif isinstance(sec, dict):
                head = sec.get("heading") or sec.get("title") or f"Section {i}"
                text = sec.get("text") or sec.get("content") or ""
                items = sec.get("items")
                parts.append(f"## {head}\n\n{text}".rstrip())
                if isinstance(items, list) and items:
                    parts.append("\n".join(f"- {x}" for x in items))
        body = "\n\n".join(p for p in parts if p)
    if not body and rest:
        body = ("```json\n"
                + json.dumps(rest, indent=2, ensure_ascii=False)
                + "\n```")
    return meta, str(body)


def _study_json_flex(raw):
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def study_document(path, subject):
    """-> (meta, body): file name, then the file's own words, then sidecar.

    Nothing here requires the author to know what a front matter block is: an
    empty Markdown file still earns a title, a description, a subject, a
    language and a keyword list."""
    auto = study_auto_meta(path, subject)
    if path.suffix.lower() == ".json":
        raw = path.read_text(encoding="utf-8")
        file_meta, body = study_json_document(raw)
        where = str(path.relative_to(ROOT))
        apply_aliases(file_meta, where)
        merged = study_merge(auto, file_meta)
    else:
        raw = path.read_text(encoding="utf-8")
        where = str(path.relative_to(ROOT))
        try:
            file_meta, body = parse_front_matter(raw, where)
        except ValueError as e:
            err(f"{where}: {e}")
            raise SystemExit(1)
        apply_aliases(file_meta, where)
        merged = study_merge(auto, file_meta)
    merged = study_merge(merged, study_overrides(path))
    merged["category"] = str(merged.get("category") or study_subject_name(subject))
    return merged, body


def stamp_study_fields(records):
    """The shelf's own fields: subject, language, chapter, part, size, badges.

    Derived once, from the path and the sidecar, so the shelf, the hub page,
    the part page, the search index and the JSON-LD can never disagree about
    what a file is. Nothing here reads the clock: a "new" badge has to come
    from metadata, or a rebuild on a different day would produce a different
    tree."""
    names = study_subject_names()
    for rec in records:
        rel = Path(rec["path"])                 # content/study-material/...
        full = ROOT / rel
        meta = rec.get("meta") or {}
        folder, lang_folder, chapter = study_locator(rel)
        if not chapter:
            # A file dropped straight into a subject has no chapter folder
            # yet: its own name is the chapter it forms, so the tree stays
            # complete instead of silently missing a level.
            chapter = pdf_slug_from_name(rel.stem) or "part"
        position, total = study_part_of(full)
        lang = study_lang(lang_folder) if lang_folder else {}
        rec["studySubject"] = folder
        rec["subjectName"] = names.get(folder) or study_subject_name(folder)
        rec["category"] = str(meta.get("category") or rec["subjectName"])
        rec["language"] = str(meta.get("language") or lang.get("code")
                              or study_language_from_name(rel.stem))
        rec["studyLanguage"] = str(meta.get("language") or lang.get("code") or "")
        rec["studyLanguageName"] = lang.get("name") or \
            study_language_label(rec["studyLanguage"])
        rec["studyChapter"] = chapter
        rec["studyChapterName"] = study_nice_name(chapter)
        rec["studyPart"] = position
        rec["studyParts"] = total
        rec["type"] = rel.suffix.lower().lstrip(".")
        rec["size"] = full.stat().st_size if full.exists() else 0
        rec["sizeLabel"] = file_size_label(full)
        said = int((rec.get("meta") or {}).get("readingTime") or 0)
        if said > 0:
            rec["readingMinutes"] = said          # the author said it out loud
        elif rec.get("type") == "pdf" and int(rec.get("pdfPages") or 0) > 0:
            # The body text the build writes for a PDF is a summary of it, not
            # the file, so word-count would read "1 min" for a 40-page chapter.
            # The page count is the only honest estimate available: one page a
            # minute at the 200-words-a-minute pace the site assumes elsewhere.
            rec["readingMinutes"] = max(1, int(rec["pdfPages"]))
        rec["source"] = f"{DOMAIN}/{quote(str(rel))}" if rec.get("path") else ""
        rec["badges"] = [b for b in ("featured", "new", "popular")
                         if rec.get(b)]
        hay = " ".join([str(rec.get("title") or ""),
                        str(rec.get("description") or ""),
                        rel.name, folder, rec["subjectName"],
                        rec["studyLanguageName"], rec["studyChapterName"],
                        str(rec.get("studyPart") and f"part {rec['studyPart']}"),
                        " ".join(str(k) for k in (rec.get("keywords") or [])),
                        " ".join(str(s) for s in (rec.get("subjects") or [])),
                        " ".join(str(e) for e in (rec.get("exams") or []))])
        rec["search"] = re.sub(r"\s+", " ", hay).strip().lower()


def study_language_label(code):
    """How one language code is written on screen.

    English and Punjabi are named in full (Punjabi in the script it is read
    in); a language this site has not named before still gets a readable
    label built from its code rather than a blank."""
    text = str(code or "").strip().lower()
    if not text:
        return ""
    known = (STUDY_LANG.get(text) or {}).get("name")
    if known:
        return known
    return study_nice_name(text) if len(text) >= 3 else text


def study_nav(records):
    """Where every part sits: what comes before it, what comes after it, and
    which chapters of the same subject a reader could go to next.

    Everything is grouped from the records the build just stamped, so a
    chapter folder added tonight is walked tomorrow with no configuration,
    and a chapter published in two languages is reachable from either one."""
    def row(r):
        return {"file": r["file"], "title": r["title"]}

    def href(key):
        subject, lang, chapter = key
        return "study.html?subject={0}&language={1}&chapter={2}".format(
            quote(str(subject), safe=""), quote(str(lang), safe=""),
            quote(str(chapter), safe=""))

    by_chapter = {}
    for r in records:
        key = (str(r.get("studySubject") or ""),
               str(r.get("studyLanguage") or ""),
               str(r.get("studyChapter") or ""))
        by_chapter.setdefault(key, []).append(r)

    chapters = {}
    for key, rows in by_chapter.items():
        rows.sort(key=lambda r: (int(r.get("studyPart") or 0), r["file"]))
        chapters[key] = {"name": str(rows[0].get("studyChapterName") or ""),
                         "count": len(rows)}
        for i, r in enumerate(rows):
            r["partNav"] = {
                "prev": row(rows[i - 1]) if i > 0 else None,
                "next": row(rows[i + 1]) if i + 1 < len(rows) else None,
            }

    def card(key, info):
        return {"href": href(key), "eyebrow": "Chapter",
                "title": info["name"] or "Study Material", "sub": "",
                "meta": f'{info["count"]} part'
                        f'{"s" if info["count"] != 1 else ""}'
                        f' · {study_language_label(key[1])}'}

    for key, info in chapters.items():
        subject, lang, _ = key
        mine = sorted(((k, m) for k, m in chapters.items()
                       if k[0] == subject and k[1] == lang and k != key),
                      key=lambda kv: (kv[1]["name"].lower(), kv[0][2]))
        elsewhere = sorted(((k, m) for k, m in chapters.items()
                            if k[0] == subject and k[1] != lang),
                           key=lambda kv: (kv[1]["name"].lower(),
                                           kv[0][1], kv[0][2]))
        related = [card(k, m) for k, m in mine[:3]]
        related += [card(k, m) for k, m in elsewhere[:max(0, 3 - len(related))]]
        for r in by_chapter[key]:
            r["relatedChapters"] = related
    return records


def study_date_label(iso):
    """`2026-09-30` -> `30 Sep 2026`; anything unparseable stays unstated
    rather than being shown as a date the file never had."""
    s = str(iso or "")[:10]
    try:
        d = datetime.date.fromisoformat(s)
    except ValueError:
        return ""
    return f"{d.day} {d.strftime('%b %Y')}"


def study_sort_key(rec):
    """STEP 7: Featured -> Newest -> Alphabetical, computed not maintained.

    One sort key, applied once at build time, so the hub page, the sitemap
    order, the search results and the Study renderer can never disagree about
    what a student sees first."""
    when = str(rec.get("updated") or rec.get("published") or "")[:10]
    try:
        newest = -int(when.replace("-", ""))
    except ValueError:
        newest = 0
    return (0 if rec.get("featured") else 1, newest,
            str(rec.get("title") or "").lower())


def study_card(r, facets=None):
    """One Study Material card - STEP 6 in one markup block.

    Title, short description, language, last updated, reading time, file size,
    optional Featured/New/Popular badges and a Download/Open button. It is a
    <div> rather than an <a> because the card holds two destinations - the
    generated page and the file itself - and a browser will not forgive an
    anchor inside an anchor: the title is the link, the button is the action."""
    badge_kind = {"featured": ("success", "Featured"),
                  "new": ("warn", "New"),
                  "popular": ("muted", "Popular")}
    badges = "".join(
        f'<span class="badge badge-{badge_kind[b][0]}">{badge_kind[b][1]}</span>'
        for b in (r.get("badges") or []) if b in badge_kind)
    meta = []
    lang = str(r.get("language") or ("pa" if r.get("lang") == "pa" else "en"))
    meta.append(study_language_label(lang) or "English")
    when = study_date_label(r.get("updated") or r.get("published"))
    if when:
        meta.append(f"Updated {when}")
    if r.get("readingMinutes"):
        meta.append(f'{r["readingMinutes"]} min read')
    if r.get("sizeLabel"):
        meta.append(str(r["sizeLabel"]))
    source = pdf_href(str(r.get("path") or ""))
    is_pdf = str(r.get("type") or "") == "pdf"
    button = (f'<a class="btn btn-primary" href="{esc(r["file"])}">📖 Read online</a>'
              f'<a class="btn btn-ghost btn-sm" href="{esc(source)}" download>'
              f'⬇ Download</a>' if is_pdf and source else
              f'<a class="btn btn-soft" href="{esc(source)}">Open file</a>'
              if source else "")
    attrs = filter_attrs(r, facets) if facets else ""
    return (f'<div class="card card-pad reveal study-card"{attrs}>'
            f'{f"""<div class="card-badges">{badges}</div>""" if badges else ""}'
            f'<span class="eyebrow">{esc(str(r.get("category") or "Study Material"))}</span>'
            f'<h3><a href="{esc(r["file"])}">{esc(r["title"])}</a></h3>'
            f'<p class="muted">{esc(r["description"])}</p>'
            f'<p class="study-meta">{esc(" · ".join(m for m in meta if m))}</p>'
            + (f'<p class="btn-row" style="margin-top:14px">{button}</p>'
               if button else "")
            + '</div>')


# =============================================================================
# 5. CONTENT LOADING
# =============================================================================
def load_subject_ids():
    try:
        data = json.loads((ROOT / "data" / "subjects.json").read_text(encoding="utf-8"))
        return {s["id"] for s in data.get("subjects", [])}
    except Exception as e:                     # pragma: no cover
        err(f"data/subjects.json unreadable: {e}")
        return set()


SUBJECT_IDS = load_subject_ids()


def load_index():
    try:
        return json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
    except Exception as e:                     # pragma: no cover
        err(f"data/index.json unreadable: {e}")
        return {"subjects": []}


def load_quiz_landing():
    """(subject_id, topic_id) -> extensionless landing path, when built."""
    out = {}
    try:
        man = json.loads((ROOT / "data" / "landing-manifest.json")
                         .read_text(encoding="utf-8"))
    except Exception:
        return out
    for p in man.get("pages", []):
        if p.get("type") == "quiz" and "/" in str(p.get("entity", "")):
            s, t = p["entity"].split("/", 1)
            out[(s, t)] = p.get("url", "").replace(DOMAIN, "")
    return out


def read_variant(coll_dir, slug, pa):
    """Read `<slug>.md` (English) and, when present, `<slug>.pa.md` (Punjabi)."""
    suffix = ".pa.md" if pa else ".md"
    path = coll_dir / f"{slug}{suffix}"
    return path if path.exists() else None


def build_record(coll, cfg, slug, path, index, lang, meta=None, body=None,
                 required=None):
    """One document -> one record. Markdown is read unless the caller (the
    PDF-drop path below) hands over front matter and a body it already built."""
    where = str(path.relative_to(ROOT))
    if meta is None or body is None:
        try:
            raw = path.read_text(encoding="utf-8")
            meta, body = parse_front_matter(raw, where)
        except ValueError as e:
            err(str(e))
            return None
        except UnicodeDecodeError:
            err(f"{where}: not valid UTF-8")
            return None

    validate_meta(coll, slug, meta, where, required=required)
    if errors:
        return None

    prefix = cfg["prefix"]
    # A Punjabi variant file carries its OWN front matter (Gurmukhi title and
    # description), so it is validated and rendered exactly like the English
    # original - Punjabi-first, with English one tap away on both pages.
    # Language URLs (Phase 2): English lives at the site root, the Punjabi
    # edition publishes under /pa/, so every article can be addressed as
    # /<slug> and /pa/<slug> and neither language is a hidden fallback.
    page_slug = str(meta.get("slug") or slug)
    filename, url = "", ""
    if prefix:
        stem = f"{prefix}-{page_slug}"
        filename = (f"pa/{stem}.html" if lang == "pa" else f"{stem}.html")
        url = f"{DOMAIN}/{filename[:-5]}"

    title = str(meta.get("title", ""))
    desc = str(meta.get("description", ""))

    html_body, toc = md_to_html(body)
    words = len(re.sub(r"<[^>]+>", " ", html_body).split())
    reading = max(1, -(-words // 200))          # ceil at 200 wpm, never "0 min"
    if meta.get("readingTime"):                 # editorial override wins
        reading = int(meta["readingTime"])
    subjects = [str(s) for s in (meta.get("subjects") or
                                 ([meta["subject"]] if meta.get("subject") else []))]
    subjects = [s for s in subjects if s in SUBJECT_IDS]
    # `exam` is the singular spelling of the same badge list, except in a
    # recruitment record where it names the exam guide page to link.
    exams = [str(t) for t in (meta.get("exams") or [])]
    if not exams and coll != "recruitment" and meta.get("exam"):
        exams = [str(meta["exam"])]

    record = {
        "collection": coll,
        "file": filename,
        "url": url,
        "path": str(path.relative_to(ROOT)),
        "title": title,
        "description": desc,
        "published": str(meta.get("published") or meta.get("date") or ""),
        "updated": str(meta.get("updated") or meta.get("published") or meta.get("date") or ""),
        "subjects": subjects,
        "tags": [str(t) for t in (meta.get("tags") or [])],
        "exams": exams,
        "readingMinutes": reading,
        "wordCount": words,
        "lang": lang,
        "meta": meta,
        "bodyHtml": html_body,
        "toc": toc,
        "slug": page_slug,
        "featured": bool(meta.get("featured")),
        "draft": bool(meta.get("draft")),
    }
    for extra in ("difficulty", "category", "month", "date", "time", "platform",
                  "status", "post", "official_url", "official_source", "exam",
                  "file", "pdf", "quiz", "join", "start_time", "author",
                  "reviewedBy", "subtitle", "thumbnail", "seoTitle",
                  "seoDescription", "keywords", "summary",
                  "relatedContent", "telegramLink", "youtubeLink",
                  "references", "faq", "schemaType", "topic", "book",
                  "book_author", "publisher", "poster", "recording",
                  "resources", "important_questions", "revision_notes",
                  "cover_alt", "new", "popular"):
        if meta.get(extra) not in (None, "", []):
            record[extra] = meta[extra]
    # `toc:` (alias `tableOfContents:`) is a SHOW/HIDE flag; `record["toc"]`
    # above is the heading list md_to_html produced. They never share a key.
    if meta.get("toc") is not None:
        record["toc_on"] = bool(meta["toc"])
    # Stable document id: explicit `id:` when given, otherwise the canonical
    # collection/slug form the content graph already uses.
    record["id"] = str(meta.get("id") or f"{coll}/{page_slug}")
    # The byline as the registry knows it - the Person node in JSON-LD and the
    # link on the visible byline both come from this, never from free text.
    record["author_ref"] = _author_by_name(record.get("author", "")) \
        if record.get("author") else None
    # Which of the eleven content templates governs this page: the explicit
    # `type:` when given, otherwise the collection's default (strategy and blog
    # split further by category). It decides the recommendation plan below.
    record["template"] = (str(meta.get("type") or "").strip()
                          or template_for(coll, str(meta.get("category") or "")))
    return record


# =============================================================================
# 5b. PDF DROPS - a PDF alone is enough to publish
# =============================================================================
# Dropping a file into content/<collection>/ publishes it: the file name IS the
# metadata. Nothing here invents a fact the file cannot carry - where the name
# has no date, the day the PDF first appeared is remembered in
# data/pdf-meta.json instead of being stamped afresh on every run, so the
# output stays byte-identical (the determinism promise in the header).
PDF_META = ROOT / "data" / "pdf-meta.json"
PDF_PAGE_FIELDS = ("title", "description", "published")
PDF_REGISTRY_FIELDS = ("title", "description", "file")   # content/pdfs/ has no page

_MONTH_NAMES = ("january february march april may june july august september "
                "october november december").split()
MONTHS = {name: i for i, name in enumerate(_MONTH_NAMES, 1)}
MONTHS.update({name[:3]: i for name, i in list(MONTHS.items())})
PDF_SMALL_WORDS = {"a", "an", "the", "of", "for", "and", "or", "in", "on",
                   "to", "at", "by", "from", "vs"}
# The exam vocabulary that must keep its capitals; every other word in a file
# name is title-cased, so `CURRENT AFFAIRS JULY 2026.pdf` reads as a title
# while `PPSC 2024 PYQ.pdf` still reads as an acronym.
PDF_ACRONYMS = {"ppsc", "psssb", "ssb", "pcs", "upsc", "ias", "ips", "ssc",
                "ibps", "rbi", "nta", "clat", "neet", "jee", "aiims", "nda",
                "cds", "afcat", "si", "asi", "po", "gk", "gs", "mcq", "mcqs",
                "pyq", "pyqs", "pdf", "ca", "pstet", "ptet", "ctet", "reet",
                "htet", "gb", "ukpsc", "hppsc", "jpse"}
# Gurmukhi -> Latin, so a Punjabi file name still earns a readable URL.
# ASCII passes through untouched: every name this site has ever had derives
# exactly as it did before this table existed. scripts/build_content_manifest.ts
# carries the same table and scripts/ci.sh diffs both answers over a fixture
# list, so the two can never drift apart.
GURMUKHI_COMBOS = {"\u0A38\u0A3C": "sh"}     # ਸ + nukta, the sequence spelling ਸ਼
GURMUKHI = {
    # independent vowels
    "\u0A05": "a", "\u0A06": "a", "\u0A07": "i", "\u0A08": "i",
    "\u0A09": "u", "\u0A0A": "u", "\u0A0F": "e", "\u0A10": "ai",
    "\u0A13": "o", "\u0A14": "au",
    # dependent vowel signs (long and short map to one Latin vowel each)
    "\u0A3E": "a", "\u0A3F": "i", "\u0A40": "i", "\u0A41": "u",
    "\u0A42": "u", "\u0A47": "e", "\u0A48": "ai", "\u0A4B": "o",
    "\u0A4C": "au",
    # signs: virama implies the half form, tippi and bindi nasalise
    "\u0A4D": "", "\u0A02": "n", "\u0A03": "", "\u0A3C": "", "\u0A70": "n",
    "\u0A71": "", "\u0A74": "",
    # consonants
    "\u0A15": "k", "\u0A16": "kh", "\u0A17": "g", "\u0A18": "gh",
    "\u0A19": "ng", "\u0A1A": "ch", "\u0A1B": "chh", "\u0A1C": "j",
    "\u0A1D": "jh", "\u0A1E": "nj", "\u0A1F": "t", "\u0A20": "th",
    "\u0A21": "d", "\u0A22": "dh", "\u0A23": "n", "\u0A24": "t",
    "\u0A25": "th", "\u0A26": "d", "\u0A27": "dh", "\u0A28": "n",
    "\u0A2A": "p", "\u0A2B": "ph", "\u0A2C": "b", "\u0A2D": "bh",
    "\u0A2E": "m", "\u0A2F": "y", "\u0A30": "r", "\u0A32": "l",
    "\u0A33": "l", "\u0A35": "v", "\u0A36": "sh", "\u0A38": "s",
    "\u0A39": "h",
    # letters written with a nukta
    "\u0A59": "kh", "\u0A5A": "gh", "\u0A5B": "z", "\u0A5C": "r",
    "\u0A5E": "f",
    # digits
    "\u0A66": "0", "\u0A67": "1", "\u0A68": "2", "\u0A69": "3",
    "\u0A6A": "4", "\u0A6B": "5", "\u0A6C": "6", "\u0A6D": "7",
    "\u0A6E": "8", "\u0A6F": "9",
}


GURMUKHI_CONSONANT = re.compile(r"[\u0A15-\u0A39\u0A59-\u0A5E]")   # letters only
GURMUKHI_NASAL = {"\u0A02", "\u0A70"}          # bindi, tippi


def translit_gurmukhi(text):
    """Gurmukhi letters to Latin, one code point at a time.

    ASCII is returned unchanged, which is what keeps this a pure addition:
    `mobile phone.pdf` still derives `mobile phone` -> `mobile-phone`.

    A nasal carries its syllable's inherent vowel, so `ਪੰਜਾਬੀ ਟੈਸਟ` becomes
    `panjabi-taist` and never `pnjabi-taist` - the same rule
    scripts/build_content_manifest.ts applies, which scripts/ci.sh diffs."""
    chars = list(str(text))
    out, i, pending = [], 0, False
    while i < len(chars):
        c = chars[i]
        two = c + (chars[i + 1] if i + 1 < len(chars) else "")
        if two in GURMUKHI_COMBOS:
            out.append(GURMUKHI_COMBOS[two])
            pending = True
            i += 2
            continue
        mapped = GURMUKHI.get(c, c)
        if c in GURMUKHI_NASAL:
            if pending:
                out.append("a")          # the syllable's inherent vowel
            out.append("n")
            pending = False
        elif GURMUKHI_CONSONANT.match(c):
            out.append(mapped)
            pending = True
        else:
            out.append(mapped)
            pending = False
        i += 1
    return "".join(out)


def ascii_fold(text):
    """Non-ASCII runs become one space.

    Python's `\\b` is Unicode-aware and JavaScript's is not, so every boundary
    regex below runs over this folded copy in BOTH builders and means the same
    thing. For the ASCII file names the site has always had, it is a no-op."""
    return re.sub(r"[^\x00-\x7F]+", " ", str(text))


def clip(text, limit=60):
    """Cut at a word boundary so a generated title stays readable."""
    s = str(text).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return cut or s[:limit]


def pdf_href(path):
    """href for a file we host ourselves: percent-encoded once, never twice."""
    v = str(path or "")
    if v.startswith(("http://", "https://")):
        return v
    return quote(v, safe="/%")


def pdf_date_from_name(stem):
    """`2026-07-15`, `July 2026`, `july-2026`, `2026-07` -> ISO date, else ''.

    A date the file cannot prove (one still in the future) is ignored rather
    than published."""
    today = datetime.date.today().isoformat()
    text = ascii_fold(stem).lower()
    found = ""
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if m:
        try:
            found = datetime.date(int(m.group(1)), int(m.group(2)),
                                  int(m.group(3))).isoformat()
        except ValueError:
            found = ""
    if not found:
        for pat in (r"\b([a-z]{3,9})[\s._-]+(20\d{2})\b",
                    r"\b(20\d{2})[\s._-]+([a-z]{3,9})\b"):
            m = re.search(pat, text)
            if not m:
                continue
            a, b = m.group(1), m.group(2)
            month = MONTHS.get(a) or MONTHS.get(b)
            if not month:
                continue
            year = int(b) if a in MONTHS else int(a)
            found = f"{year:04d}-{month:02d}-01"
            break
    if not found:
        m = re.search(r"\b(20\d{2})-(\d{1,2})\b", text)
        if m and 1 <= int(m.group(2)) <= 12:
            found = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-01"
    return "" if (found and found > today) else found


def pdf_title_from_name(stem):
    """`Current Affairs July 2026` <- `Current Affairs July 2026.pdf`.

    Acronyms (PPSC, SI) and years keep their shape; everything else is title
    cased, and the result is cut to the site's 60-character title limit."""
    stem = str(stem)
    # A date written into the name ("Sheet 2026-08-12") is part of the
    # document, not a word to be re-spaced: it is parked while the rest of the
    # name is title cased.
    iso = re.search(r"\b20\d{2}-\d{1,2}(?:-\d{1,2})?\b", ascii_fold(stem))
    guard = iso.group(0) if iso else ""
    if guard:
        stem = stem.replace(guard, "Dateday", 1)
    words = [w for w in re.split(r"[^A-Za-z0-9\u0A00-\u0A7F]+", stem) if w]
    out = []
    for w in words:
        if not w.isascii():
            out.append(w)          # Gurmukhi keeps its own shape
        elif w.isdigit() or any(c.isdigit() for c in w):
            out.append(w)          # 2026, SI-2, v3 keep their shape
        elif w.lower() in PDF_ACRONYMS:
            out.append(w.upper())  # ppsc -> PPSC, ca -> CA, pyq -> PYQ
        else:
            out.append(w[0].upper() + w[1:].lower())
    for i, w in enumerate(out):
        if i and w.lower() in PDF_SMALL_WORDS:
            out[i] = w.lower()
    title = " ".join(out)
    if guard:
        # Clip the words around the date - never through it.
        head, _, tail = title.partition("Dateday")
        head = clip(head, max(10, 60 - len(guard) - 1))
        title = f"{head.strip()} {guard} {tail.strip()}".strip()
        if len(title) > 60:
            title = clip(f"{head.strip()} {guard}", 60)
    else:
        title = clip(title, 60)
    return " ".join(title.split())


def pdf_slug_from_name(stem):
    """Filename -> the slug rule every other document follows, or ''.

    Punjabi and mixed names are transliterated first, so `ਪੰਜਾਬੀ ਨੋਟ.pdf`
    earns `panjabi-not` instead of falling back to a numbered placeholder."""
    s = re.sub(r"-{2,}", "-",
               re.sub(r"[^a-z0-9]+", "-", translit_gurmukhi(stem).lower())) \
        .strip("-")[:64].rstrip("-")
    return s if re.fullmatch(r"[a-z0-9][a-z0-9-]*", s) else ""


def pdf_description(title, label):
    """A 140-160 character meta description assembled from the title and the
    collection label - truthful clauses only, never padded with claims."""
    text = f"Download {title} as a PDF from House of Aspirants."
    clauses = [
        " One click, no sign-up and no email wall.",
        f" {label} material, filed straight from the file name.",
        " Free to download, print and keep for offline revision.",
        " The page was generated from the file name.",
        " Filed in the House of Aspirants library.",
        " Hosted on this site.",
        " No account needed.",
        " Free.",
    ]
    for _ in range(4):
        for clause in clauses:
            if len(text) >= 140:
                break
            if len(text) + len(clause) <= 160:
                text += clause
        if len(text) >= 140:
            break
    if len(text) < 140:
        # Nothing else fits whole: one longer sentence, then a word-boundary
        # trim keeps the result inside the site's 140-160 window.
        text += " Hosted on this site, indexed in the archives and free for " \
                "every aspirant."
    while len(text) > 160:
        text = text.rsplit(" ", 1)[0]
    if not (140 <= len(text) <= 160):          # pragma: no cover - guarded gate
        err(f"generated PDF description for {title!r} is {len(text)} chars "
            f"(the site range is 140-160)")
    return text


def file_size_label(path):
    try:
        size = Path(path).stat().st_size
    except OSError:
        return ""
    return f"{size // 1024} KB" if size < 1024 * 1024 \
        else f"{size / (1024 * 1024):.1f} MB"


def pdf_summary_md(summary):
    """The scanner's first-page text, shown as the file wrote it: every
    character that Markdown would otherwise take for its own is quoted."""
    return re.sub(r"([\\`*_\[\]#>])", r"\\\1", str(summary or "").strip())


def pdf_body_text(title, rel, published, label, record=None):
    """The honest body of a generated page: what the file is, what is inside
    it (read out of the PDF by the scanner) and where it is."""
    rec = record or {}
    href = pdf_href(rel)
    size = file_size_label(ROOT / rel)
    pages = int(rec.get("pdfPages") or 0)
    summary = pdf_summary_md(rec.get("summary"))
    facts = ", ".join(x for x in (size, f"{pages} pages" if pages else "")
                      if x)
    date_line = (f"- **Published:** {fmt_date(published)}\n"
                 if published else "")
    return (
        (f"## Summary\n{summary}\n\n" if summary else "")
        + f"## Download\n"
        + f"[Download {title} (PDF)]({href})"
        + (f" - {facts}, hosted on this site." if facts else ".")
        + " No sign-up, no email wall and no redirect through a third party.\n\n"
        f"## About this file\n"
        f"- **File name:** `{Path(rel).name}`\n"
        + (f"- **Pages:** {pages}\n" if pages else "")
        + (f"- **Size:** {size}\n" if size else "")
        + f"- **Filed under:** {label}\n"
        f"{date_line}\n"
        f"This page was generated automatically when the PDF was placed in "
        f"`{Path(rel).parent.as_posix()}/`. Its title, slug, description and "
        f"date come from the file name, and its page count and summary were "
        f"read out of the PDF itself - the file is the document."
    )


def study_pdf_body(title, rel, published, label, record=None):
    """The honest body of a study part page.

    Where the file sits - subject, language, chapter and its place among the
    parts beside it - is the fact a reader needs before downloading and the
    whole of the authoring surface for the person who published it, so it is
    written down here instead of living in a README nobody opens. Everything
    else is what the scanner read out of the file itself."""
    rec = record or {}
    href = pdf_href(rel)
    subject, lang_folder, chapter = study_locator(rel)
    position, total = study_part_of(rel)
    lang = study_lang(lang_folder) if lang_folder else {}
    pages = int(rec.get("pdfPages") or 0)
    size = file_size_label(ROOT / rel)
    summary = pdf_summary_md(rec.get("summary"))
    facts = ", ".join(x for x in (size, f"{pages} pages" if pages else "") if x)
    lang_name = lang.get("name") or study_language_label(
        study_lang_id(lang_folder) or "en")
    where = Path(rel).parent.as_posix()
    return (
        (f"## Summary\n{summary}\n\n" if summary else "")
        + f"## Download\n"
        + f"[Download {title} (PDF)]({href})"
        + (f" - {facts}, hosted on this site." if facts else ".")
        + " No sign-up, no email wall and no redirect through a third party.\n\n"
        f"## About this file\n"
        f"- **File name:** `{Path(rel).name}`\n"
        + (f"- **Pages:** {pages}\n" if pages else "")
        + (f"- **Size:** {size}\n" if size else "")
        + (f"- **Published:** {fmt_date(published)}\n" if published else "")
        + f"- **Filed under:** {label}\n"
        f"\n## Where this file sits\n"
        f"- **Subject:** {study_subject_name(subject)}\n"
        f"- **Language:** {lang_name}"
        + (f" ({lang['native']})" if lang.get("native") and
           lang.get("native") != lang_name else "")
        + "\n"
        + (f"- **Chapter:** {study_nice_name(chapter)}\n" if chapter else "")
        + (f"- **Part:** Part {position} of {total}\n" if total > 1 else "")
        + f"\nThis page was generated automatically from `{where}/`. Its "
        f"subject, language and chapter come from the folders the file sits "
        f"in, its part number from its place among the files beside it, and "
        f"its title, slug and description from those. The page count and the "
        f"summary were read out of the PDF itself - the file is the document."
    )


def pdf_preview_html(record):
    """The scanner's first-page preview, if it drew one: the same box the
    issue covers use, sized by the pixels that were actually written so the
    page never shifts while the image decodes."""
    src = str(record.get("pdfPreview") or "")
    w, h = int(record.get("pdfPreviewW") or 0), int(record.get("pdfPreviewH") or 0)
    if not src or w <= 0 or h <= 0 or not (ROOT / src).is_file():
        return ""
    return (f'<img class="doc-cover" src="{esc(src)}" alt="First page of '
            f'{esc(record["title"])}" width="{w}" height="{h}" '
            f'decoding="async" style="aspect-ratio:{w} / {h}">')


def apply_pdf_body(record, label):
    """Re-render the generated body (a title disambiguation changes it)."""
    record["bodyHtml"], record["toc"] = md_to_html(
        pdf_body_text(record["title"], record["path"],
                      str(record.get("published") or ""), label, record))
    record["bodyHtml"] = pdf_preview_html(record) + record["bodyHtml"]


def load_pdf_sidecar():
    """> {"version": 1, "files": {<path>: {hash, published, updated}}}."""
    if not PDF_META.exists():
        return {"version": 1, "files": {}}
    try:
        data = json.loads(PDF_META.read_text(encoding="utf-8"))
        if not isinstance(data.get("files"), dict):
            raise ValueError("'files' must be an object")
        return {"version": 1, "files": data["files"]}
    except Exception as e:
        warn(f"data/pdf-meta.json unreadable ({e}) - regenerating it")
        return {"version": 1, "files": {}}


def load_drops():
    """The PDF inventory scripts/build_content_manifest.ts wrote.

    This builder reads that list and never walks content/ itself: the manifest
    is the single list, exactly as data/index.json is for quizzes. A missing or
    stale inventory stops the build with instructions rather than publishing a
    folder nobody scanned."""
    if not MANIFEST.exists():
        err("data/content-manifest.json is missing - run node "
            "scripts/build_content_manifest.ts (the PDF scanner)")
        return []
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception as e:
        err(f"data/content-manifest.json unreadable ({e}) - run node "
            f"scripts/build_content_manifest.ts")
        return []
    drops = data.get("drops")
    if not isinstance(drops, list):
        err("data/content-manifest.json carries no `drops` inventory - run "
            "node scripts/build_content_manifest.ts (the PDF scanner)")
        return []
    return drops


def check_drop(drop, path, cfg):
    """The scanner and this builder must describe the same document.

    scripts/build_content_manifest.ts derives the title, slug, folder and
    category from the file name; this script derives them again for the page it
    renders. A disagreement means the manifest is out of date - and a stale
    manifest is a silently wrong page - so it fails the build with the exact
    command that fixes it."""
    where = str(path.relative_to(ROOT))
    rel = path.relative_to(CONTENT / cfg["dir"])
    parent = rel.parts[-2] if len(rel.parts) > 1 else ""
    stem = path.stem
    for key, want in (("path", where), ("filename", path.name),
                      ("folder", cfg["dir"]), ("category", parent),
                      ("title", pdf_title_from_name(stem)),
                      ("slug", pdf_slug_from_name(stem))):
        have = drop.get(key)
        have = "" if have is None else have
        if str(have) != want:
            err(f"{where}: content manifest says {key}={have!r}, this build "
                f"derives {want!r} - run node scripts/build_content_manifest.ts")
            return False
    return True


def remember_pdf_dates(path, old_files, new_files, fname_date):
    """-> (published, updated), stable across rebuilds.

    The file name wins when it carries a date. Otherwise the date the PDF was
    first published is read back from data/pdf-meta.json - today's date is
    stamped once, never on every run (which would look like content drift to
    `scripts/ci.sh` step 6)."""
    rel = str(path.relative_to(ROOT))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stored = old_files.get(rel) or {}
    today = datetime.date.today().isoformat()
    published = fname_date or str(stored.get("published") or "") or today
    if str(stored.get("hash") or "") == digest:
        updated = str(stored.get("updated") or "") or published
    else:
        updated = today if stored else published   # file replaced since first seen
    entry = {"hash": digest, "published": published, "updated": updated}
    new_files[rel] = entry
    return published, updated


def pdf_eyebrow(record, index=None):
    """The one fact a generated PDF page can honestly lead with."""
    if record.get("subjects") and index is not None:
        return subject_name(index, record["subjects"][0])
    if record.get("month"):
        return f'Issue {record["month"]}'
    if record.get("category"):
        return str(record["category"])
    if record.get("official_source"):
        return str(record["official_source"])
    if record.get("date"):
        return fmt_date(str(record["date"]))
    return "PDF download"


def build_pdf_record(coll, cfg, path, slug, published, updated, fname_date,
                     index, folder="", drop=None, extra=None):
    """meta + body derived from the file name -> a normal document record.

    `folder` is the subfolder the file was dropped in ("english"), kept on the
    record so a second file of the same name can say which one it is.
    `drop` is the scanner's row for this file - the facts it read out of the
    PDF itself (page count, first-page summary, first-page preview), which no
    file name could ever have told us.
    `extra` is the study material sidecar: whatever the author wrote down for
    this one file, merged last so it beats every derivation - except the
    download itself, which is this file and not a link somebody typed."""
    label = NAV_ENTRY.get(coll, (HUBS[coll]["schema_hub"], ""))[0]
    title = pdf_title_from_name(path.stem) or label
    if coll == STUDY_DIR:
        # A study file's title is the folders it sits in plus its place among
        # its siblings, never the raw file name: `part 3 (english).pdf` is the
        # third part of its chapter, and which chapter is on the page too.
        title = study_title_for(path)
    rel = str(path.relative_to(ROOT))
    drop = drop or {}
    pages = int(drop.get("pages") or 0)
    summary = clip(str(drop.get("summary") or "").strip(), 300)
    body_facts = {"pdfPages": pages, "summary": summary}
    meta = {"title": title, "description": pdf_description(title, label)}
    if coll == "pdfs":
        # The PDF hub is a registry: the file is the artifact, so the record
        # carries the download and never a date or a page of its own.
        meta["file"] = rel
        required = PDF_REGISTRY_FIELDS
    else:
        required = PDF_PAGE_FIELDS
        meta["published"] = published
        if updated and updated != published:
            meta["updated"] = updated
        meta["pdf"] = rel                     # the Download button
        meta["keywords"] = [clip(title, 48), label, "PDF download"]
        if summary:
            # The first page of the file, in the file's own words: it feeds
            # the on-page Summary, the search row and the JSON-LD abstract.
            meta["summary"] = summary
        if coll == "magazine" and fname_date:
            meta["month"] = fname_date[:7]    # "Issue 2026-07", from the name
        if coll == STUDY_DIR:
            # The folders say which subject this file belongs to, which
            # language it is written in and which chapter it is part of; the
            # file name only breaks a tie where no language folder exists.
            # A sidecar may still say otherwise - it is merged in below and
            # beats every derivation.
            subject, lang_folder, _ = study_locator(path)
            name = study_subject_name(subject)
            meta["language"] = (study_lang_id(lang_folder)
                                or str(drop.get("language") or "en"))
            meta["category"] = name
            meta["description"] = study_description(title, name)
            meta["keywords"] = [clip(title, 48), name, "Study Material",
                                path.stem]
    if extra:
        meta.update({k: v for k, v in extra.items() if v not in (None, "", [])})
    if coll != "pdfs":
        meta["pdf"] = rel                     # not overridable - it is the file
        meta.setdefault("published", published)
    record = build_record(coll, cfg, slug, path, index, "en",
                          meta=meta,
                          body=(study_pdf_body(str(meta.get("title") or title),
                                               rel,
                                               str(meta.get("published") or published),
                                               label, body_facts)
                                if coll == STUDY_DIR else
                                pdf_body_text(str(meta.get("title") or title),
                                              rel,
                                              str(meta.get("published") or published),
                                              label, body_facts)),
                          required=required)
    if record is not None:
        record["pdfDrop"] = True
        record["pdfFolder"] = folder
        record["pdfPages"] = pages
        record["pdfPreview"] = str(drop.get("thumbnail") or "")
        record["pdfPreviewW"] = int(drop.get("thumbW") or 0)
        record["pdfPreviewH"] = int(drop.get("thumbH") or 0)
        record["bodyHtml"] = pdf_preview_html(record) + record["bodyHtml"]
    return record


def dedupe_pdf_titles(all_records):
    """Every <title> on the site is unique (gated in scripts/seo_check.py), so
    a generated title is disambiguated with its collection label - and the
    description and body that quote it are regenerated with it."""
    used = {str(h.get("title", "")).lower() for h in HUBS.values()}
    used.add(ARCHIVES_TITLE.lower())
    for rows in all_records.values():
        used.update(str(r["title"]).lower() for r in rows if not r.get("pdfDrop"))
    for coll, rows in all_records.items():
        label = NAV_ENTRY.get(coll, (coll, ""))[0]
        for r in rows:
            if not r.get("pdfDrop"):
                continue
            base = str(r["title"])
            # A file in a subfolder says which one it is with that folder's
            # name ("english") before it falls back to the collection label.
            # A study file already has its chapter on the face of the title,
            # so it disambiguates with the subject instead.
            folder = pdf_title_from_name(r.get("studySubject")
                                          or r.get("pdfFolder") or "")
            first = folder or label
            cand, n = base, 1
            while cand.lower() in used:
                n += 1
                if n > 50:
                    err(f"{r['path']}: no unique title can be derived from this "
                        f"file name - rename the PDF")
                    break
                cand = clip(f"{base} ({first if n == 2 else n})", 60)
            if cand != base:
                r["title"] = cand
                r["meta"]["title"] = cand
                r["meta"]["description"] = (
                    study_description(cand, str(r.get("subjectName") or first))
                    if r.get("studySubject") else pdf_description(cand, label))
                r["description"] = r["meta"]["description"]
                if r["meta"].get("keywords"):
                    r["meta"]["keywords"][0] = clip(cand, 48)
                    r["keywords"] = r["meta"]["keywords"]
                apply_pdf_body(r, label)
                info(f"{r['path']}: title disambiguated to {cand!r}")
            used.add(str(r["title"]).lower())


def link_related_pdfs(all_records, punjabi):
    """A generated PDF page shows the PDFs it sits beside: its own folder
    first, then its collection, then the rest of the library - three at most.

    The choice comes from the inventory alone (folder, collection, title), so
    it never claims two files are about the same subject when only their
    names say so. Runs after dedupe_pdf_titles, because the titles on the
    cards have to be the ones the site ends up publishing."""
    def live(r):
        return bool(HUBS.get(r["collection"], {}).get("prefix")) and \
            bool(r.get("file"))

    pages = [r for rows in all_records.values() for r in rows if live(r)]
    for coll in punjabi:
        pages += [r for r in punjabi[coll] if live(r)]
    for rec in pages:
        mine = str(rec.get("pdfFolder") or "")
        others = [o for o in pages
                  if o is not rec and o["file"] != rec["file"]]
        others.sort(key=lambda o: (
            0 if mine and str(o.get("pdfFolder") or "") == mine else 1,
            0 if o["collection"] == rec["collection"] else 1,
            str(o["title"]).lower(), o["file"]))
        rec["relatedPdfs"] = [
            {"href": o["file"],
             "eyebrow": NAV_ENTRY.get(o["collection"],
                                      (o["collection"], ""))[0],
             "title": o["title"], "sub": "", "meta": "Open the page"}
            for o in others[:3]]


def subject_name(index, sid):
    s = next((x for x in index.get("subjects", []) if x.get("id") == sid), None)
    return (s or {}).get("name") or sid.replace("-", " ").title()


def related_quizzes(record, index, landing, limit=3):
    out = []
    for sid in record["subjects"]:
        subj = next((s for s in index.get("subjects", []) if s["id"] == sid), None)
        if not subj:
            continue
        for t in subj.get("topics", []):
            if not t.get("available"):
                continue
            path = landing.get((sid, t["id"])) or \
                f"quiz.html?subject={sid}&topic={t['id']}"
            href = path.lstrip("/") + ".html" if path.startswith("/quiz-") else path
            out.append({
                "title": t.get("name", ""),
                "href": href,
                "subject": subj.get("name", ""),
            })
            if len(out) >= limit:
                return out
    return out


_QZ_STOP = {"part", "chapter", "english", "punjabi", "the", "and", "for", "with",
            "mcq", "mcqs", "current", "affairs", "notes", "pdf", "free", "study",
            "material", "paper", "question", "questions", "from", "into"}


def _qz_tokens(text):
    """Comparable words of a title: lower-case, no stop words, plural 's' off."""
    out = set()
    for w in re.findall(r"[a-z]+", str(text).lower()):
        if len(w) < 3 or w in _QZ_STOP:
            continue
        out.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)
    return out


def practice_link(record, index, landing):
    """Where "Practice MCQs" on a reading page goes: the quiz whose name shares
    the most words with this document (its own subject wins a tie), else the
    subject's practice page, else the Practice hub. Always a real page."""
    want = _qz_tokens(" ".join(str(record.get(k) or "") for k in
                               ("title", "studyChapterName", "subtitle")))
    subs = set(record.get("subjects") or [])
    if record.get("studySubject"):
        subs.add(str(record["studySubject"]))
    if "current-affairs" in str(record.get("collection") or ""):
        subs.add("current-affairs")
    # A document whose subject has a quiz shelf only ever points into that
    # shelf, so "One Word Substitution" (Punjabi) can never land on MS Word.
    quiz_subjects = {s_["id"] for s_ in index.get("subjects", [])}
    only = subs & quiz_subjects
    part_rx = re.compile(r"part\s*-?\s*(\d+)", re.I)
    pm = part_rx.search(str(record.get("title") or ""))
    my_part = pm.group(1) if pm else "1"
    best, best_score = None, 0.0
    for subj in index.get("subjects", []):
        if only and subj["id"] not in only:
            continue
        for t in subj.get("topics", []):
            if not t.get("available"):
                continue
            score = float(len(want & _qz_tokens(t.get("name", ""))))
            if not score:
                continue
            if subj["id"] in subs:
                score += 0.5
            tm = part_rx.search(str(t.get("name") or "") + " " + str(t.get("id") or ""))
            if tm and tm.group(1) == my_part:
                score += 0.25
            if score > best_score:
                best, best_score = (subj, t), score
    if best:
        subj, t = best
        path = landing.get((subj["id"], t["id"])) or \
            f"quiz.html?subject={subj['id']}&topic={t['id']}"
        return path.lstrip("/") + ".html" if path.startswith("/quiz-") else path
    for sid in sorted(subs):
        if (ROOT / f"subject-{sid}.html").exists():
            return f"subject-{sid}.html"
    return "practice.html"


# =============================================================================
# 6. ITEM PAGE RENDERING
# =============================================================================
# =============================================================================
# TAXONOMY - the tag / category pages that really exist (Phase 4)
# Computed once from the English documents before anything renders, so a badge
# on a document and the archive page it points at can never disagree: if the
# slug is not in here, the badge stays plain text and no dead link ships.
# =============================================================================
TAXONOMY = {"tag": {}, "category": {}}


def build_taxonomy(all_records):
    TAXONOMY["tag"], TAXONOMY["category"] = {}, {}
    for rows in all_records.values():
        for r in rows:
            if r.get("lang") != "en":
                continue                # archives are English-language pages
            for t in r.get("tags") or []:
                TAXONOMY["tag"].setdefault(_slug_facet(t), str(t))
            if r.get("category"):
                TAXONOMY["category"].setdefault(_slug_facet(r["category"]),
                                                str(r["category"]))
    return TAXONOMY


def badge_row(record):
    bits = []
    meta = record.get("meta", {})
    coll = record.get("collection", "")
    # Collection-specific facts go first: an issue leads with its month, a live
    # session with its slot, a recruitment record with the body that issued it.
    if coll == "magazine" and record.get("month"):
        bits.append(f'<span class="badge">Issue {esc(str(record["month"]))}</span>')
    if coll == "sessions":
        if record.get("date"):
            bits.append(f'<span class="badge">{esc(fmt_date(str(record["date"])))}</span>')
        for key, label in (("time", "Time"), ("platform", "Platform")):
            if record.get(key):
                bits.append(f'<span class="badge">{esc(str(record[key]))}</span>')
        if record.get("status"):
            bits.append('<span class="badge badge-muted">'
                        f'{"Upcoming" if str(record["status"]) == "upcoming" else "Past session"}'
                        '</span>')
    if coll == "recruitment" and record.get("official_source"):
        bits.append(f'<span class="badge">Official · {esc(str(record["official_source"]))}</span>')
    if coll == "strategy" and meta.get("category"):
        cat_slug = _slug_facet(str(meta["category"]))
        if cat_slug in TAXONOMY["category"]:
            bits.append(f'<a class="badge badge-muted" '
                        f'href="archive-category-{esc(cat_slug)}.html">'
                        f'{esc(str(meta["category"]))}</a>')
        else:
            bits.append(f'<span class="badge badge-muted">'
                        f'{esc(str(meta["category"]))}</span>')
    if record.get("readingMinutes"):
        bits.append(f'<span class="badge badge-muted">{record["readingMinutes"]} min read</span>')
    if record.get("difficulty"):
        bits.append(f'<span class="badge badge-muted">{esc(str(record["difficulty"]))}</span>')
    for exam in record.get("exams", [])[:4]:
        bits.append(f'<span class="badge badge-muted">{esc(exam)}</span>')
    # Tags link to their archive page when that page exists - the document and
    # its tag page link to each other, which is the whole point of a taxonomy.
    for tag in record.get("tags", [])[:4]:
        tag_slug = _slug_facet(tag)
        if tag_slug in TAXONOMY["tag"]:
            bits.append(f'<a class="badge badge-muted" '
                        f'href="archive-tag-{esc(tag_slug)}.html">{esc(tag)}</a>')
        else:
            bits.append(f'<span class="badge badge-muted">{esc(tag)}</span>')
    return f'<div class="doc-badges">{"".join(bits)}</div>' if bits else ""


def share_row(url, title):
    q = f"?url={url}&text={title}"
    return f"""<div class="share-row" data-share-url="{esc(url)}">
          <span class="share-label">Share</span>
          <a class="share-btn" data-share="copy" href="{esc(url)}" role="button">🔗 Copy link</a>
          <a class="share-btn" href="https://wa.me/{q}" target="_blank" rel="noopener">WhatsApp</a>
          <a class="share-btn" href="https://t.me/share/url{q}" target="_blank" rel="noopener">Telegram</a>
          <a class="share-btn" href="https://twitter.com/intent/tweet{q}" target="_blank" rel="noopener">X</a>
        </div>"""


def prev_next(record, pool):
    """pool is already sorted newest-first -> prev = older, next = newer."""
    idx = next((i for i, r in enumerate(pool) if r["file"] == record["file"]), None)
    if idx is None:
        return "", ""
    older = pool[idx + 1] if idx + 1 < len(pool) else None
    newer = pool[idx - 1] if idx > 0 else None

    # A study note is a chapter in its subject's sequence, so it says so; a
    # dated record (current affairs, a session) is honest about what the order
    # actually is - publication date.
    tpl = TEMPLATES.get(str(record.get("template") or ""), {})
    chaptered = bool(tpl.get("chaptered"))

    def card(r, kind):
        if not r:
            return '<span class="pn-card pn-empty"></span>'
        if chaptered:
            arrow = "Next chapter →" if kind == "next" else "← Previous chapter"
        else:
            arrow = "← Newer" if kind == "next" else "Older →"
        return (f'<a class="pn-card" href="{r["file"]}">'
                f'<span class="pn-label">{arrow}</span>'
                f'<span class="pn-title">{esc(r["title"])}</span></a>')

    return card(older, "prev"), card(newer, "next")


def part_prev_next(record):
    """The parts either side of this one, in chapter order.

    Derived in study_nav() from the chapter folder itself, so part 3 knows
    part 2 and part 4 exist whether the file names say `part-3` or `Part 3`."""
    nav = record.get("partNav") or {}

    def card(row, kind):
        if not row:
            return '<span class="pn-card pn-empty"></span>'
        arrow = "Next part →" if kind == "next" else "← Previous part"
        return (f'<a class="pn-card" href="{esc(row["file"])}">'
                f'<span class="pn-label">{arrow}</span>'
                f'<span class="pn-title">{esc(row["title"])}</span></a>')

    return card(nav.get("prev"), "prev"), card(nav.get("next"), "next")


def content_chain(record, quizzes):
    """The platform's learning path, as automatic internal links.

    Study note -> related quiz -> previous year questions -> expected MCQs ->
    current affairs -> magazine -> strategy. Every step points at something that
    really exists; the two reserved steps are named but never linked, because
    no verified question bank ships before its data does.
    """
    steps = [(record["title"], record["file"], "current")]
    if record.get("quiz"):
        steps.append(("The quiz that tests this", str(record["quiz"]), "link"))
    elif quizzes:
        steps.append((quizzes[0]["title"], quizzes[0]["href"], "link"))
    # Previous year papers and expected MCQs: linked the moment verified data
    # exists, reserved (named, never linked) until then. The hub carries the
    # honest empty state either way.
    for coll in ("previous-year-questions", "expected-mcqs"):
        hit = CHAIN_TARGETS.get(coll)
        if hit and hit["file"] == record["file"]:
            continue                      # this page IS that step - no self-link
        if hit:
            steps.append((hit["title"], hit["file"], "link"))
        else:
            steps.append((HUBS[coll]["schema_hub"], "", "reserved"))
    for coll, label in (("current-affairs", "Current affairs"),
                        ("magazine", "Monthly magazine"),
                        ("strategy", "Preparation strategy")):
        if coll == record["collection"]:
            continue
        hit = CHAIN_TARGETS.get(coll)
        if hit and hit["file"] == record["file"]:
            continue
        steps.append((hit["title"] if hit else label,
                      hit["file"] if hit else HUBS[coll]["file"], "link"))
    return steps


def chain_html(record, quizzes):
    items = []
    for label, href, kind in content_chain(record, quizzes):
        if kind == "current":
            items.append(f'<li class="chain-step is-current" aria-current="page">'
                         f'<span>{esc(label)}</span></li>')
        elif kind == "link":
            items.append(f'<li><a class="chain-step" href="{esc(href)}">'
                         f'<span>{esc(label)}</span></a></li>')
        else:
            items.append(f'<li class="chain-step is-reserved">'
                         f'<span>{esc(label)}</span><em>reserved</em></li>')
    return f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Learning path</span>
          <h2>Where this page fits</h2>
          <p>One step, one real link. Reserved steps appear so the path is
             honest about what this platform does not publish yet.</p>
        </div></div>
        <ol class="doc-chain">{''.join(items)}</ol>
      </div>
    </section>"""


# =============================================================================
# 6b. RECOMMENDATION ENGINE -> HTML  (Phase 3)
# =============================================================================
# The plan a page renders comes from its content template
# (scripts/content_engine.py): every slot resolves either to real links the
# site serves today, or - when the data behind it does not exist yet - to a
# single honest "reserved" line. Nothing is ever linked to a page that is not
# there, and the reasons a candidate was chosen are recorded in
# data/content-graph.json.
def explore_links(coll):
    """Contextual links used to guarantee the >=5 internal-link floor.

    A collection's own links and the three common ones can point at the same
    page (the daily quiz is both "practice for this collection" and "practice"
    in general), so the pool is deduplicated by page - a reader must never see
    the same card twice in one Explore module."""
    out, seen = [], set()
    for href, eyebrow, title in list(EXPLORE_BY_COLL.get(coll, [])) + list(EXPLORE_COMMON):
        key = str(href).split("#", 1)[0].split("?", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        out.append((href, eyebrow, title))
    return out


EXPLORE_COMMON = [
    ("punjab-exams.html", "Exam hub", "Every Punjab exam guide in one place"),
    ("quiz.html?mode=daily", "Practice", "Today's daily challenge"),
    ("archives.html", "Archive", "Everything published, by subject and month"),
]

EXPLORE_BY_COLL = {
    "notes": [
        ("articles.html", "Pillar guides", "Four long-form study guides"),
        ("subject.html?subject=gk", "Subject hub", "Punjab GK notes and quizzes"),
        ("current-affairs.html", "Current affairs", "This month, explained"),
    ],
    "current-affairs": [
        ("subject.html?subject=current-affairs", "Practice", "Current affairs MCQ sets"),
        ("magazine.html", "Monthly magazine", "The issue covering this month"),
        ("news.html", "Exam news", "Official notices behind the events"),
    ],
    "magazine": [
        ("current-affairs.html", "Current affairs", "The articles each issue draws from"),
        ("subject.html?subject=current-affairs", "Practice", "Current affairs MCQ sets"),
        ("quiz.html?mode=daily", "Daily", "Today's daily challenge"),
    ],
    "strategy": [
        ("articles.html", "Study guides", "Long-form preparation guides"),
        ("pdfs.html", "Free PDFs", "Notes and sheets to study from"),
        ("live-sessions.html", "Live sessions", "Bring the doubts live"),
    ],
    "sessions": [
        ("strategy.html", "Preparation strategy", "Turn a session into a week"),
        ("announcements.html", "Announcements", "Schedule changes land first"),
        ("blogs.html", "Blog", "Write-ups from the week"),
    ],
    "recruitment": [
        ("punjab-exams.html", "Exam guides", "Preparation guide for every post"),
        ("strategy.html", "Preparation strategy", "How to prepare for the post"),
        ("news.html", "Exam news", "Pattern and date updates"),
    ],
    "expected-mcqs": [
        ("previous-year-questions.html", "Past papers", "The official papers these follow"),
        ("study-notes.html", "Study notes", "Revise the concept before you attempt"),
        ("quiz.html?mode=daily", "Practice", "Today's daily challenge"),
    ],
    "previous-year-questions": [
        ("expected-mcqs.html", "Forecast", "Expected MCQs for the next attempt"),
        ("study-notes.html", "Study notes", "Revise before you attempt"),
        ("punjab-exams.html", "Exam guides", "Syllabus and pattern for every exam"),
    ],
    "blogs": [
        ("articles.html", "Study guides", "The long-form guides"),
        ("strategy.html", "Preparation strategy", "Plans and timetables"),
        ("study-notes.html", "Study notes", "One idea per read"),
    ],
    "news": [
        ("recruitment.html", "Recruitment", "The notifications behind this"),
        ("announcements.html", "Announcements", "Site changes first"),
        ("current-affairs.html", "Current affairs", "Explained, not just reported"),
    ],
    "announcements": [
        ("live-sessions.html", "Live sessions", "The weekly schedule"),
        ("blogs.html", "Blog", "What the team is writing"),
        ("news.html", "Exam news", "Official updates"),
    ],
    "pdfs": [
        ("study-notes.html", "Study notes", "The pages these sheets come from"),
        ("quiz.html?mode=daily", "Practice", "Test what you revised"),
        ("punjab-exams.html", "Exam guides", "Syllabus for every exam"),
    ],
    "archives": [
        ("study-notes.html", "Study notes", "Newest first"),
        ("current-affairs.html", "Current affairs", "This month"),
        ("punjab-exams.html", "Exam guides", "Every Punjab exam"),
    ],
    # Generated index pages (Phase 4): a profile and the search page both need
    # a floor of their own - they list no documents on their own.
    "author": [
        ("magazine.html", "Monthly magazine", "The issues this byline writes"),
        ("live-sessions.html", "Live sessions", "Where the mentor appears"),
        ("strategy.html", "Preparation strategy", "The method, documented"),
    ],
    "search": [
        ("archives.html", "Archive", "Everything published, by subject"),
        ("punjab-exams.html", "Exam guides", "Syllabus for every exam"),
        ("quiz.html?mode=daily", "Practice", "Today's daily challenge"),
        ("study-notes.html", "Study notes", "Browse by subject and tag"),
    ],
    # Phase 4 collections - the links that make each new hub contextual
    # rather than generic, on top of the common trio below.
    "personal-notes": [
        ("strategy.html", "Preparation strategy", "The method behind a note"),
        ("study-notes.html", "Study notes", "The concept it recorded"),
        ("quiz.html?mode=daily", "Practice", "Today's daily challenge"),
    ],
    "subject-guides": [
        ("study-notes.html", "Study notes", "One idea per read"),
        ("quiz.html?mode=daily", "Practice", "Test the syllabus"),
        ("pdfs.html", "Free PDFs", "Sheets to study from"),
    ],
    "topic-guides": [
        ("study-notes.html", "Study notes", "The concepts around it"),
        ("subject.html?subject=gk", "Subject hub", "Where this topic sits"),
        ("current-affairs.html", "Current affairs", "The topic in the news"),
    ],
    "daily-practice": [
        ("quiz.html?mode=daily", "Daily quiz", "The same set, timed"),
        ("study-notes.html", "Study notes", "Read what you got wrong"),
        ("progress.html", "Progress", "Your streak and accuracy"),
    ],
    "success-stories": [
        ("strategy.html", "Preparation strategy", "The method, written down"),
        ("live-sessions.html", "Live sessions", "Ask the mentor directly"),
        ("announcements.html", "Announcements", "What the site added next"),
    ],
    "book-recommendations": [
        ("pdfs.html", "Free PDFs", "Start free first"),
        ("study-notes.html", "Study notes", "The same syllabus, no cost"),
        ("strategy.html", "Preparation strategy", "How to actually use a book"),
    ],
}


def _dedupe_by_slug(pool, prefer_lang):
    """One document per slug, keeping the reader's language where it exists."""
    best = {}
    for r in pool:
        if not r.get("file"):
            continue
        key = (r.get("collection"), r.get("slug"), r.get("published"))
        cur = best.get(key)
        if cur is None or (cur.get("lang") != prefer_lang
                           and r.get("lang") == prefer_lang):
            best[key] = r
    return list(best.values())


def _doc_card(r, eyebrow):
    return {"href": r["file"], "eyebrow": eyebrow, "title": r["title"],
            "sub": r["description"],
            "meta": f'{r["readingMinutes"]} min read'}


def resolve_slot(record, spec, ctx, quizzes, anchors):
    """Resolve one plan slot into (cards, reserved, edges).

    cards    - ready-to-render links to pages that exist
    reserved - slots whose data does not exist yet, described honestly
    edges    - (target, rel) pairs recorded in the content graph
    """
    src = str(spec.get("src", ""))
    limit = int(spec.get("limit", 3))
    cards, reserved, edges = [], [], []

    def keep(href, rel):
        if href and not href.startswith(("#", "http", "mailto:", "tel:")):
            edges.append((href, rel))

    if src == "quiz":
        own = str(record.get("quiz") or "").strip()
        if own:
            # The document names the set that tests it: that is the practice
            # link, not an unrelated set that happens to share a subject.
            cards.append({"href": own, "eyebrow": "Practice quiz",
                          "title": "The set that tests this", "sub": "",
                          "meta": "Start the quiz →"})
            keep(own, "practice-quiz")
        for q in quizzes[:max(0, limit - len(cards))]:
            cards.append({"href": q["href"], "eyebrow": q["subject"] or "Practice",
                          "title": q["title"], "sub": "",
                          "meta": "Start the quiz →"})
            keep(q["href"], "practice-quiz")
        if not cards:
            # No set matches this subject yet: the three practice routes that
            # are always live, instead of dressing up unrelated quizzes.
            for href, eyebrow, title in (
                ("quiz.html?mode=daily", "Daily", "Today's Daily Challenge"),
                ("index.html#subjects", "All subjects", "Pick a subject to drill"),
                ("mock.html", "Full paper", "Take a mock test"),
            ):
                cards.append({"href": href, "eyebrow": eyebrow, "title": title,
                              "sub": "", "meta": "Start the quiz →"})
                keep(href, "practice-quiz")

    elif src == "subject" or src.startswith("subject:"):
        sids = (record.get("subjects") if src == "subject"
                else [src.split(":", 1)[1]])
        for sid in (sids or [])[:limit]:
            name = subject_name(ctx["index"], sid)
            href = (f"subject-{sid}.html" if (ROOT / f"subject-{sid}.html").exists()
                    else f"subject.html?subject={sid}")
            cards.append({"href": href, "eyebrow": "Subject hub", "title": name,
                          "sub": "Notes, quizzes and topics for this subject",
                          "meta": "Open the subject →"})
            keep(href, "subject-hub")

    elif src.startswith("coll:"):
        rest = src[5:]
        coll, _, query = rest.partition("?")
        hub = HUBS.get(coll)
        pool = list(ctx["pools"].get(coll, []))
        if "tag=" in query:
            needle = query.split("tag=", 1)[1].lower()
            pool = [r for r in pool
                    if any(needle in str(t).lower() for t in (r.get("tags") or []))
                    or needle in str(r.get("category") or "").lower()]
        pool = _dedupe_by_slug(pool, record.get("lang"))
        if "latest=1" in query:
            picks = [(pool[0], "")] if pool else []
        else:
            picks = [(r, why) for r, _, why in
                     rank(record, pool, limit, prefer_lang=record.get("lang"),
                          require_score=not spec.get("any"))]
        for r, _why in picks:
            cards.append(_doc_card(r, hub["schema_hub"] if hub else r["collection"]))
            keep(r["file"], "related-" + coll)
        if not cards:
            if spec.get("fallback"):
                cards.append({"href": spec["fallback"], "eyebrow": "Section",
                              "title": spec.get("fallback_title")
                              or (hub or {}).get("schema_hub", "Section"),
                              "sub": "", "meta": "Open the section →"})
                keep(spec["fallback"], "related-" + coll)
            elif spec.get("reserved"):
                reserved.append({"title": spec["title"],
                                 "note": spec["reserved"]})

    elif src.startswith("hub:"):
        coll = src.split(":", 1)[1]
        hub = HUBS.get(coll)
        if hub:
            cards.append({"href": hub["file"], "eyebrow": "Section",
                          "title": spec.get("title") or hub["schema_hub"],
                          "sub": "", "meta": "Open the section →"})
            keep(hub["file"], "section-" + coll)

    elif src.startswith("page:"):
        anchor = src.split(":", 1)[1]
        if anchor in anchors:
            cards.append({"href": _anchor_on(record, anchor),
                          "eyebrow": "On this page", "title": spec["title"],
                          "sub": "", "meta": "Jump to it →"})

    return cards, reserved, edges


def _anchor_on(record, anchor):
    # /pa/ pages carry <base href="/">, so a self-anchor names its page.
    return f'/{record["file"]}#{anchor}' if record.get("lang") == "pa" \
        else f"#{anchor}"


def effective_plan(record):
    """Template plan + the cross-section slots every page earns."""
    plan = [dict(s) for s in plan_for(record.get("template", ""))]
    seen = {str(s.get("src", "")) for s in plan}
    own = record.get("collection", "")
    label = NAV_ENTRY.get(own, (record.get("template") or "section", ""))[0]
    # Same section first: a reader who opened a note wants more notes, even
    # when this one's facets do not overlap with theirs.
    own_src = f"coll:{own}"
    tail = [
        {"src": own_src, "eyebrow": "More to read",
         "title": f"More {label.lower()}", "limit": 3, "any": True},
        {"src": "coll:current-affairs", "eyebrow": "Related current affairs",
         "title": "Current affairs in this area", "limit": 3},
        {"src": "coll:strategy", "eyebrow": "Related articles",
         "title": "Guides worth reading next", "limit": 3},
    ]
    for spec in tail:
        src = str(spec["src"])
        coll = src.split(":", 1)[1]
        if src in seen:
            continue
        if src != own_src and coll == own:
            continue
        plan.append(spec)
        seen.add(src)
    return plan[:7]


def card_html(c):
    sub = f'<p class="muted">{esc(c["sub"])}</p>' if c.get("sub") else ""
    # the arrow is the card's affordance - add it once, whatever the slot says
    action = str(c.get("meta") or "").strip().rstrip("→ ").strip()
    meta = f'<p class="ilink">{esc(action)} →</p>' if action else ""
    return (f'<a class="card card-pad reveal" href="{esc(c["href"])}">'
            f'<span class="eyebrow">{esc(c["eyebrow"])}</span>'
            f'<h3>{esc(c["title"])}</h3>{sub}{meta}</a>')


def recommend_sections(record, ctx, quizzes, anchors):
    """Render the page's template plan. Returns (html, edges)."""
    plan = effective_plan(record)
    groups, reserved, edges = [], [], []
    for spec in plan:
        cards, res, ed = resolve_slot(record, spec, ctx, quizzes, anchors)
        if cards:
            groups.append((spec, cards))
        reserved.extend(res)
        edges.extend((e, rel) for e, rel in ed)

    # A generated PDF page leads with the PDFs it sits beside - one group the
    # plan never has to know about, on the same cards every other slot uses.
    # A study part leads with the chapters around it instead: its own chapter
    # already covers the file, so the useful next step is a different chapter.
    related = record.get("relatedChapters") or record.get("relatedPdfs") or []
    if related:
        title = ("Related Chapters" if record.get("relatedChapters")
                 else "Related PDFs")
        groups.insert(0, ({"title": title}, related))
        edges.extend((c["href"], "related-pdf") for c in related)

    if not groups and not reserved:
        return "", edges

    blocks = []
    for spec, cards in groups:
        blocks.append(
            f'<div class="rec-group"><h3 class="rec-title">'
            f'{esc(spec["title"])}</h3>'
            f'<div class="grid grid-3">{"".join(card_html(c) for c in cards)}'
            f'</div></div>')

    reserved_html = ""
    if reserved:
        names = ", ".join(r["title"] for r in reserved)
        notes = " ".join(sorted({r["note"] for r in reserved}))
        reserved_html = (f'<p class="rec-reserved">'
                         f'<span class="badge badge-muted">Reserved</span> '
                         f'{esc(names)} - {esc(notes)}</p>')

    why = ("Matched on subject, exam, category, difficulty, tags and language - "
           "the same facets you search with.")
    html = f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Recommended</span>
          <h2>What to do with this page</h2>
          <p>{why}</p>
        </div></div>
        {''.join(blocks)}
        {reserved_html}
      </div>
    </section>"""
    return html, edges


def enforce_link_floor(html, coll, page):
    """Guarantee >=5 contextual internal links inside <main>.

    Appends the collection's explore module when a page (an empty hub, the
    archive) has fewer real links than the content graph promises, and fails
    the build if it still cannot reach the floor.
    """
    m = re.search(r"(<main[^>]*>)(.*?)(</main>)", html, re.S)
    if not m:
        err(f"{page}: generated page without <main>")
        return html
    have = link_floor(m.group(2))
    if len(have) >= 5:
        return html

    def _card(href, eyebrow, title):
        return (f'<a class="card card-pad reveal" href="{esc(href)}">'
                f'<span class="eyebrow">{esc(eyebrow)}</span>'
                f'<h3>{esc(title)}</h3>'
                f'<p class="ilink">Open →</p></a>')

    def _section(body_cards):
        return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Keep going</span>
          <h2>Explore the library</h2>
          <p>The parts of House of Aspirants that connect to this page.</p>
        </div></div>
        <div class="grid grid-3">{body_cards}</div>
      </div>
    </section>
"""
    cards = "".join(_card(href, eyebrow, title)
                    for href, eyebrow, title in explore_links(coll)
                    if href not in have)
    # appended as its own indented section, leaving </main> where it was
    body = m.group(2).rstrip() + "\n" + _section(cards) + "  "
    have = link_floor(body)
    # A page whose own collection offers little (an empty hub, a new profile
    # page) tops up with the hubs themselves until the floor is really met.
    if len(have) < 5:
        picked = set(have)
        top = ""
        for href, eyebrow, title in [(HUBS[c]["file"],) + NAV_ENTRY[c]
                                     for c in NAV_ORDER]:
            key = str(href).split("#", 1)[0].split("?", 1)[0]
            if not key or key in picked:
                continue
            picked.add(key)
            top += _card(href, eyebrow, title)
            if len(picked) >= 5:
                break
        if top:
            body = m.group(2).rstrip() + "\n" + _section(cards + top) + "  "
            have = link_floor(body)
    if len(have) < 5:
        err(f"{page}: {len(have)} contextual internal links after the explore "
            f"module (the content graph requires 5)")
    return html[:m.start()] + m.group(1) + body + m.group(3) + html[m.end():]


def render_item(record, cfg, pool, index, landing, ctx=None):
    url = record["url"]
    hub = HUBS[record["collection"]]
    hub_url = f"{DOMAIN}/{hub['file'][:-5]}"

    # Article also carries the WebPage type, so one node covers both rules and
    # there is never a duplicate @id on the page.
    # A study part is reached through subject -> language -> chapter, so the
    # trail (in JSON-LD and on screen) walks that chain rather than jumping
    # from the shelf straight to the file.
    crumbs = {"id": f"{url}#breadcrumb",
              "items": [("Home", f"{DOMAIN}/"),
                        (hub["schema_hub"], hub_url),
                        (record["title"], url)]}
    crumb_tail = ""
    if record.get("studySubject"):
        def _q(value):
            return quote(str(value), safe="")
        trail, tail = [(hub["schema_hub"], hub_url)], ""
        sid = _q(record["studySubject"])
        sname = str(record["subjectName"])
        subject_url = f"{DOMAIN}/study?subject={sid}"
        trail.append((sname, subject_url))
        tail += f'<a href="study.html?subject={sid}">{esc(sname)}</a><span>/</span>'
        level = subject_url
        if record.get("studyLanguage"):
            lang_id = _q(record["studyLanguage"])
            lang_name = str(record.get("studyLanguageName")
                             or record["studyLanguage"])
            level = f"{subject_url}&language={lang_id}"
            trail.append((lang_name, level))
            tail += (f'<a href="study.html?subject={sid}&amp;language={lang_id}">'
                     f'{esc(lang_name)}</a><span>/</span>')
        if record.get("studyChapter"):
            chap_id = _q(record["studyChapter"])
            chap_name = str(record["studyChapterName"])
            trail.append((chap_name, f"{level}&chapter={chap_id}"))
            tail += (f'<a href="study.html?subject={sid}'
                     f'&amp;language={_q(record.get("studyLanguage") or "")}'
                     f'&amp;chapter={chap_id}">{esc(chap_name)}</a>'
                     f'<span>/</span>')
        trail.append((record["title"], url))
        crumbs["items"] = trail
        crumb_tail = tail
    nodes = [article_node(record, url), breadcrumb_node(crumbs)]

    if record.get("pdfDrop"):
        # The document node says what was published; this one says what the
        # thing is - a PDF, encoded as the file the reader can download.
        nodes.insert(1, learning_resource_node(record, url))

    if record["collection"] == "sessions" and record.get("start_time") and \
            record.get("date"):
        nodes.insert(1, {
            "@type": "Event",
            "@id": f"{url}#event",
            "name": record["title"],
            "description": record["description"],
            "startDate": f'{record["date"]}T{record["start_time"]}:00+05:30',
            "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "isAccessibleForFree": True,
            # The join link (Telegram) lives on the page itself; schema URLs
            # stay on-domain, so the virtual location is the session page.
            "location": {"@type": "VirtualLocation", "url": url},
            "organizer": {"@type": "Organization", "name": "House of Aspirants",
                          "url": DOMAIN + "/"},
            "url": url,
        })

    # An FAQ in the front matter is published twice, deliberately: as visible
    # questions on the page and as FAQPage schema holding the same pairs.
    faq_pairs = doc_faq(record)
    if faq_pairs:
        nodes.append({
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq_pairs
            ],
        })

    jsonld = graph(nodes)

    # ---- hero -------------------------------------------------------------
    eyebrow_bits = []
    if record.get("studySubject"):
        # Subject · Language · Chapter: the three folders the file sits in,
        # so the page says where it belongs before it says anything else.
        eyebrow_bits.append(" · ".join(
            b for b in (str(record.get("subjectName") or ""),
                        str(record.get("studyLanguageName") or ""),
                        str(record.get("studyChapterName") or "")) if b))
    elif record.get("pdfDrop"):
        # Generated from a file name: lead with the one fact it really carries
        eyebrow_bits.append(pdf_eyebrow(record, index))
    elif record["collection"] == "notes":
        names = [subject_name(index, s) for s in record["subjects"]]
        eyebrow_bits.append(" · ".join(names) if names else "Study Note")
    elif record["collection"] == "magazine":
        eyebrow_bits.append(f"Monthly issue · {record.get('month', '')}".strip(" ·"))
    elif record["collection"] == "strategy":
        eyebrow_bits.append(str(record.get("category", "Strategy")))
    elif record["collection"] == "sessions":
        state = "Upcoming session" if str(record.get("status", "")) == "upcoming" \
            else "Past session"
        eyebrow_bits.append(f'{state} · {record.get("date", "")}')
    elif record["collection"] == "recruitment":
        eyebrow_bits.append(str(record.get("official_source", "Official notification")))

    meta_line = []
    if record.get("published"):
        meta_line.append(f'Published {fmt_date(record["published"])}')
    if record.get("updated") and record["updated"] != record.get("published"):
        meta_line.append(f'Updated {fmt_date(record["updated"])}')

    pdf_html = ""
    reader_html = ""
    if record.get("pdf"):
        # Read it here first, then practise; the file itself comes last.
        src = esc(pdf_href(record["pdf"]))
        read_href = f'/{record["file"]}#read' if record["lang"] == "pa" else "#read"
        quiz_href = esc(practice_link(record, index, landing))
        pages = int(record.get("pdfPages") or 0)
        pdf_html = (f'<a class="btn btn-primary" href="{read_href}" data-pdf-open>📖 Read Online</a>'
                    f'<a class="btn btn-soft" href="{quiz_href}" data-practice-link>📝 Practice MCQs</a>'
                    f'<a class="btn btn-ghost btn-sm" href="{src}" download>⬇ Download PDF</a>')
        reader_html = (
            f'<div class="pdf-reader" data-pdf-src="{src}">'
            f'<div class="pr-head"><span class="pr-label">📖 Read online'
            f'{f" · {pages} pages" if pages else ""}</span>'
            f'<a class="pr-dl" href="{src}" download>⬇ Download</a></div>'
            f'<div class="pr-pages"><button type="button" class="btn btn-primary" '
            f'data-pdf-open>📖 Start reading</button></div>'
            f'<div class="pr-end"><p><b>Finished reading?</b> Check what you remember '
            f'with a quick MCQ test.</p><p class="btn-row"><a class="btn btn-primary" '
            f'href="{quiz_href}" data-practice-link>📝 Practice MCQs</a></p></div>'
            f'</div>\n')

    # Community links the document itself points at - rendered only when the
    # front matter carries them.
    link_btns = ""
    if record.get("telegramLink"):
        link_btns += (f'<a class="btn btn-soft" href="{esc(str(record["telegramLink"]))}" '
                      f'target="_blank" rel="noopener">Telegram channel ↗</a>')
    if record.get("youtubeLink"):
        link_btns += (f'<a class="btn btn-soft" href="{esc(str(record["youtubeLink"]))}" '
                      f'target="_blank" rel="noopener">Session on YouTube ↗</a>')

    switch_html = ""
    alternates = ()
    sibling = ROOT / "content" / cfg["dir"] / (
        record["slug"] + (".md" if record["lang"] == "pa" else ".pa.md"))
    if sibling.exists():
        stem = f'{cfg["prefix"]}-{record["slug"]}'
        alternates = (("en", f"{DOMAIN}/{stem}"),
                      ("pa", f"{DOMAIN}/pa/{stem}"))
        if record["lang"] == "pa":
            switch_html = (f'<a class="badge badge-lang" href="/{stem}.html" '
                           f'hreflang="en">English version</a>')
        else:
            switch_html = (f'<a class="badge badge-lang" lang="pa" hreflang="pa" '
                           f'href="/pa/{stem}.html">'
                           f'ਪੰਜਾਬੀ ਵਿੱਚ ਪੜ੍ਹੋ</a>')

    toc_html = ""
    if record.get("toc_on", True) and len(record["toc"]) >= 2:
        # /pa/ pages set <base href="/">, so an in-page anchor has to name the
        # page it belongs to; the English page stays at the site root.
        def _anchor(a):
            # /pa/ pages set <base href="/">, so a self-anchor has to name the
            # page it belongs to (the file path, matching every other link here).
            return f'/{record["file"]}#{a}' if record["lang"] == "pa" else f"#{a}"
        items = "".join(f'<li><a href="{_anchor(a)}">{esc(t)}</a></li>'
                        for a, t in record["toc"])
        toc_head = {"notes": "In this note", "magazine": "In this issue",
                    "strategy": "In this guide", "sessions": "On this page",
                    "recruitment": "On this page"}.get(record["collection"],
                                                       "In this page")
        toc_html = (f'<aside class="doc-toc" aria-label="Table of contents">'
                    f'<h2>{toc_head}</h2><ol>{items}</ol>'
                    f'<p class="toc-meta">≈ {record["readingMinutes"]} min to finish'
                    + (f' · {esc(str(record["difficulty"]))}'
                       if record.get("difficulty") else "")
                    + '</p></aside>')

    byline_meta = " · ".join(meta_line)
    author_label = str(record.get("author") or BYLINE)
    author_ref = record.get("author_ref")
    author_file = author_profile_file(author_ref) if author_ref else ""
    author_html = (f'<a href="{esc(author_file)}" class="bl-link">'
                   f'{esc(author_label)}</a>' if author_file
                   else esc(author_label))
    byline = f"""<div class="byline">
          <span class="bl-avatar" aria-hidden="true">HA</span>
          <div class="bl-body">
            <span class="bl-label">Written &amp; reviewed by</span>
            <span class="bl-name">{author_html}</span>
            <span class="bl-meta">{esc(byline_meta or "Reviewed by the editorial team")}</span>
          </div>
        </div>"""

    # ---- body sections ----------------------------------------------------
    sections = []
    front = ""
    coll = record["collection"]

    if coll == "magazine":
        front = issue_front(record)          # cover + issue actions, above the text
        sections.append(magazine_sections(record))
    elif coll == "sessions":
        front = session_front(record)        # date / time / platform / join link
        sections.append(session_sections(record))
    elif coll == "recruitment":
        sections.append(recruitment_sections(record))

    # ---- Phase 4 front-matter blocks: every one renders only when the
    # document actually provides it - never a placeholder, never a stub.
    for block in (references_section(record), faq_block(record),
                  related_section(record)):
        if block:
            sections.append(block)

    quizzes = related_quizzes(record, index, landing)
    # ---- template-driven recommendations (Phase 3) -------------------------
    # Every page renders the plan that belongs to its content template:
    # real links where the data exists, one honest "reserved" line where it
    # does not, and every choice recorded in data/content-graph.json.
    anchors = recruitment_anchors(record)
    rec_html, rec_edges = recommend_sections(record, ctx or {}, quizzes, anchors)
    if rec_html:
        sections.append(rec_html)
    if ctx is not None:
        for target, rel in rec_edges:
            ctx["edges"].append((record["file"], target, rel))

    chain = chain_html(record, quizzes)
    if chain:
        sections.append(chain)

    if record.get("partNav"):
        # A study part belongs to a chapter's own sequence, so it walks that
        # sequence rather than the publication order of the whole shelf.
        prev_card, next_card = part_prev_next(record)
        pn_label = "Previous and next part"
    else:
        prev_card, next_card = prev_next(record, pool)
        pn_label = "Previous and next note"
    sections.append(f"""<section class="section" style="padding-top:0">
      <div class="container">
        <nav class="prev-next" aria-label="{pn_label}">{prev_card}{next_card}</nav>
      </div>
    </section>""")

    # ---- assemble ---------------------------------------------------------
    toc_slot = toc_html or ""
    # seoTitle / seoDescription replace the generated pair for this document
    # only, and only within the same length contract the generated pair meets.
    html = head(str(record.get("seoTitle") or record["title"]),
                str(record.get("seoDescription") or record["description"]),
                keywords_for(record), url, "article", jsonld,
                lang="pa" if record["lang"] == "pa" else "en",
                alternates=alternates,
                image=str(record.get("thumbnail") or record.get("cover") or ""))
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <a href="index.html">Home</a><span>/</span>
          <a href="{hub['file']}">{esc(hub["schema_hub"])}</a><span>/</span>{crumb_tail}
          <span>{esc(record["title"])}</span>
        </nav>
        <span class="eyebrow">{esc(" · ".join(eyebrow_bits) or hub["eyebrow"])}</span>
        <h1>{esc(record["title"])}</h1>
        {f'<p class="doc-subtitle">{esc(str(record["subtitle"]))}</p>' if record.get("subtitle") else ""}
        {badge_row(record)}
        <div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{esc(record["description"])}</p>
        </div>
        {byline}
        <div class="doc-actions">{pdf_html}{link_btns}{switch_html}</div>
        {share_row(url, record["title"])}
      </div>
    </section>
{front}
    <section class="section" style="padding-top:0" id="read">
      <div class="container doc-layout">
        {toc_slot}
        <article class="doc-body prose">
{reader_html}{record["bodyHtml"]}
        </article>
      </div>
    </section>
{"".join(sections)}
  </main>
"""
    # Content-graph contract: every published page carries at least five
    # contextual internal links, or the build fails here.
    html = enforce_link_floor(html, coll, record["file"])
    html += TAIL
    return html, jsonld


def recruitment_sections(record):
    """Notification / eligibility / syllabus / selection / dates / strategy /
    expected questions / previous papers - each block renders only when the
    Markdown actually provides it (no invented content, ever)."""
    blocks = []

    def block(title, inner, eyebrow="Recruitment details", anchor=""):
        # Every block carries an id so the recommendation plan can point at
        # `page:eligibility` / `page:syllabus` - and only when it exists.
        aid = f' id="{esc(anchor)}"' if anchor else ""
        return f"""<section class="section"{aid} style="padding-top:0">
        <div class="container">
          <div class="section-head reveal"><div>
            <span class="eyebrow">{eyebrow}</span>
            <h2>{esc(title)}</h2>
          </div></div>
          {inner}
        </div>
      </section>"""

    off = str(record.get("official_url", ""))
    src = str(record.get("official_source", "the recruiting body's website"))
    notif = f"""<div class="card card-pad">
          <p class="muted">Official notification - read it on {esc(src)}'s own
             website. Dates, vacancies and admit cards below are copied from that
             notification only and are never published from any other source.</p>
          <p class="btn-row" style="margin-top:14px">
            <a class="btn btn-primary" href="{esc(off)}" target="_blank" rel="noopener">Open official notification ↗</a>
            <a class="btn btn-soft" href="punjab-exams.html">Preparation guide</a>
          </p>
        </div>"""
    # A notification can only be pointed at when the record actually names the
    # official URL (a PDF dropped into this folder never does), so the block -
    # and the anchor the recommendation plan links - appear only when real.
    if off:
        blocks.append(block("Notification", notif, "Official source", "notification"))

    if record["meta"].get("eligibility"):
        blocks.append(block("Eligibility",
                            f'<div class="prose">{md_to_html(str(record["meta"]["eligibility"]))[0]}</div>',
                            anchor="eligibility"))
    if record["meta"].get("syllabus"):
        blocks.append(block("Syllabus", list_html(record["meta"]["syllabus"]),
                            anchor="syllabus"))
    if record["meta"].get("selection"):
        blocks.append(block("Selection Process", list_html(record["meta"]["selection"]),
                            anchor="selection"))
    if record["meta"].get("dates"):
        rows = "".join(f"<li>{md_inline(str(d))}</li>" for d in as_list(record["meta"]["dates"]))
        blocks.append(block("Important Dates",
                            f'<div class="prose"><ul>{rows}</ul></div>',
                            "From the official notification", "dates"))
    if record["meta"].get("expected_questions"):
        blocks.append(block("Expected Questions",
                            list_html(record["meta"]["expected_questions"]),
                            "Practice focus", "expected-questions"))
    if record["meta"].get("previous_papers"):
        blocks.append(block("Previous Papers",
                            list_html(record["meta"]["previous_papers"]),
                            anchor="previous-papers"))
    return "".join(blocks)


def recruitment_anchors(record):
    """Which recruitment sections this page really rendered.

    The recommendation plan links `page:eligibility` and `page:syllabus`; a
    record that does not carry them must not be promised an anchor it has.
    """
    if record.get("collection") != "recruitment":
        return set()
    out = set()
    if str(record["meta"].get("official_url") or "").strip():
        out.add("notification")           # only when the block really rendered
    for key in ("eligibility", "syllabus", "selection", "dates",
                "expected_questions", "previous_papers"):
        if record["meta"].get(key):
            out.add(key)
    return out


def section_block(title, inner, eyebrow="Details"):
    """Shared section shell for the collection-specific blocks below."""
    return f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">{esc(eyebrow)}</span>
          <h2>{esc(title)}</h2>
        </div></div>
        {inner}
      </div>
    </section>"""


# =============================================================================
# Phase 4 front-matter blocks. Each helper returns "" when the document does
# not carry the field, so a page without references has no references section
# (never an empty heading).
# =============================================================================
def doc_faq(record):
    """Normalised question/answer pairs from `faq:` in the front matter."""
    pairs = []
    for item in as_list(record.get("faq")):
        if isinstance(item, dict):
            q = item.get("q") or item.get("question")
            a = item.get("a") or item.get("answer")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            q, a = item[0], item[1]
        else:
            continue
        if str(q or "").strip() and str(a or "").strip():
            pairs.append((str(q).strip(), str(a).strip()))
    return pairs


def faq_block(record):
    """The visible half of `faq:` - the same pairs the JSON-LD publishes."""
    pairs = doc_faq(record)
    if not pairs:
        return ""
    items = "".join(
        f'<div class="faq-item"><h3>{esc(q)}</h3>'
        f'<p>{md_inline(str(a))}</p></div>'
        for q, a in pairs)
    return section_block("Frequently asked questions", f'<div class="faq-list">'
                         f'{items}</div>', "Straight answers")


def references_section(record):
    """`references:` - a named, checkable source list on the page itself."""
    refs = as_list(record.get("references"))
    if not refs:
        return ""
    rows = []
    for ref in refs:
        if isinstance(ref, dict):
            title = str(ref.get("title") or ref.get("url") or "Source")
            url = str(ref.get("url") or "").strip()
        else:
            title, url = str(ref).strip(), ""
        if url:
            host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
            rows.append(f'<li><a href="{esc(url)}" target="_blank" '
                        f'rel="noopener noreferrer">{esc(title)}'
                        f'<span class="src-host">{esc(host)}</span></a></li>')
        else:
            rows.append(f"<li>{md_inline(title)}</li>")
    return section_block(
        "Sources and references",
        f'<div class="prose"><ol class="source-list">{"".join(rows)}</ol></div>',
        "Checked against")


def related_section(record):
    """`relatedContent:` - links the editor chose, resolved to real pages."""
    targets = as_list(record.get("relatedContent"))
    if not targets:
        return ""
    cards = []
    for t in targets:
        path = str(t).split("#", 1)[0].lstrip("/")
        if not path:
            continue
        page = path if path.endswith(".html") else f"{path}.html"
        p = ROOT / page
        if not p.exists():
            info(f"{record['file']}: relatedContent target {t!r} does not "
                 f"exist yet - link skipped")
            continue
        head_html = p.read_text(encoding="utf-8", errors="replace")[:4000]
        m = re.search(r"<title>(.*?)</title>", head_html, re.S)
        label = (m.group(1).strip().replace(" | House of Aspirants", "")
                 if m else str(t))
        cards.append(f'<a class="card card-pad" href="{esc(page)}">'
                     f'<span class="eyebrow">Related reading</span>'
                     f'<h3>{esc(label)}</h3></a>')
    if not cards:
        return ""
    return section_block("Related reading",
                         f'<div class="grid grid-3">{"".join(cards)}</div>',
                         "Chosen by the editor")


def issue_front(record):
    """Cover + issue actions, placed between the hero and the online reading.
    Nothing is rendered unless the Markdown ships it: no cover file, no cover;
    no linked quiz, no quiz button."""
    meta = record["meta"]
    cover = str(meta.get("cover", ""))
    quiz = str(meta.get("quiz", ""))
    if not cover and not quiz:
        return ""

    img = ""
    if cover:
        # seo_check requires width+height on every <img>; unknown covers keep a
        # stable 3:4 box (object-fit crops) so the layout never jumps.
        w = int(str(meta.get("cover_width") or 320))
        h = int(str(meta.get("cover_height") or 448))
        img = (f'<img class="doc-cover" src="{esc(cover)}" alt="Cover of '
               f'{esc(record["title"])}" width="{w}" height="{h}" decoding="async" '
               f'style="aspect-ratio:{w} / {h}">')

    buttons = ['<a class="btn btn-primary" href="#read">Read online</a>']
    if quiz:
        buttons.append(f'<a class="btn btn-soft" href="{esc(quiz)}">'
                       f'Attempt the issue MCQs</a>')
    buttons.append(f'<a class="btn btn-soft" href="{HUBS["magazine"]["file"]}">'
                   f'All issues</a>')

    facts = []
    if record.get("month"):
        facts.append(("Issue", str(record["month"])))
    if record.get("published"):
        facts.append(("Published", fmt_date(str(record["published"]))))
    if record.get("updated") and record.get("updated") != record.get("published"):
        facts.append(("Updated", fmt_date(str(record["updated"]))))
    rows = "".join(f'<div class="doc-fact"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>'
                   for k, v in facts)

    return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="card card-pad doc-issue">
          {img}
          <div class="doc-issue-body">
            <span class="eyebrow">This issue</span>
            <dl class="doc-facts">{rows}</dl>
            <div class="btn-row">{"".join(buttons)}</div>
          </div>
        </div>
      </div>
    </section>
"""


def magazine_sections(record):
    """After the reading: the issue's highlights, expected MCQs, important
    questions and revision notes - each rendered only when the Markdown lists
    them, so an issue never shows an empty promise."""
    meta = record["meta"]
    out = []
    if meta.get("highlights"):
        out.append(section_block("Important highlights",
                                 list_html(meta["highlights"]),
                                 "The month at a glance"))
    if meta.get("expected_mcqs"):
        out.append(section_block("Most expected MCQs",
                                 list_html(meta["expected_mcqs"]),
                                 "From this issue"))
    if meta.get("important_questions"):
        out.append(section_block("Important questions",
                                 list_html(meta["important_questions"]),
                                 "Revise these first"))
    if meta.get("revision_notes"):
        out.append(section_block("Revision notes",
                                 list_html(meta["revision_notes"]),
                                 "Two-minute recap"))
    return "".join(out)


def session_front(record):
    """Date, time, platform and the join link - what a student needs before the
    reading starts. Built only from front matter that exists."""
    facts = []
    if record.get("date"):
        facts.append(("Date", fmt_date(str(record["date"]))))
    for key, label in (("time", "Time"), ("platform", "Platform")):
        if record.get(key):
            facts.append((label, str(record[key])))
    # `status` carries the publication state (draft/archived never reach here)
    # or the session's own scheduling state - only the latter is shown.
    st = str(record.get("status") or "")
    if st in ("upcoming", "past", "held"):
        facts.append(("Status", "Upcoming" if st == "upcoming" else "Held"))
    join = str(record.get("join", ""))
    rec = str(record.get("recording", ""))
    poster = str(record.get("poster", ""))
    if not facts and not join and not rec and not poster:
        return ""

    img = ""
    if poster:
        # seo_check requires width+height on every <img>; the poster keeps a
        # stable 16:9 box so the layout never jumps.
        img = (f'<img class="doc-cover" src="{esc(poster)}" alt="Poster for '
               f'{esc(record["title"])}" width="640" height="360" '
               f'decoding="async" style="aspect-ratio:640 / 360">')

    rows = "".join(f'<div class="doc-fact"><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>'
                   for k, v in facts)
    buttons = ""
    if join:
        buttons = (f'<a class="btn btn-primary" href="{esc(join)}" '
                   f'target="_blank" rel="noopener">Join the session ↗</a>')
    if rec:
        buttons += (f'<a class="btn btn-soft" href="{esc(rec)}" '
                    f'target="_blank" rel="noopener">Watch the recording ↗</a>')
    buttons += f'<a class="btn btn-soft" href="{HUBS["sessions"]["file"]}">All sessions</a>'

    return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="card card-pad doc-issue">
          {img}
          <div class="doc-issue-body">
            <span class="eyebrow">Session details</span>
            <dl class="doc-facts">{rows}</dl>
            <div class="btn-row">{buttons}</div>
          </div>
        </div>
      </div>
    </section>
"""


def session_sections(record):
    """Summary, the questions that mattered, the doubts raised, the recording
    and the resources - written by the editorial team after the session,
    never before."""
    meta = record["meta"]
    out = []
    if meta.get("summary"):
        body = md_to_html(str(meta["summary"]))[0]
        out.append(section_block("Session summary", f'<div class="prose">{body}</div>',
                                 "What we covered"))
    if meta.get("questions"):
        out.append(section_block("Important questions discussed",
                                 list_html(meta["questions"]), "Discuss these again"))
    if meta.get("doubts"):
        out.append(section_block("Student doubts", list_html(meta["doubts"]),
                                 "Answered live"))
    if meta.get("recording"):
        rec = str(meta["recording"])
        out.append(section_block(
            "Watch the recording",
            f'<p class="btn-row"><a class="btn btn-primary" href="{esc(rec)}" '
            f'target="_blank" rel="noopener">Open the recording ↗</a></p>',
            "If you missed it"))
    if meta.get("resources"):
        rows = []
        for res in as_list(meta["resources"]):
            if isinstance(res, dict):
                label = str(res.get("title") or res.get("url") or "Resource")
                url = str(res.get("url") or "")
            else:
                text = str(res)
                label, url = (text.split("::", 1) if "::" in text
                              else ("", text))
                label, url = label.strip(), url.strip()
            if not url:
                continue
            label = label or url
            rows.append(f'<li><a href="{esc(url)}"'
                        + (' target="_blank" rel="noopener noreferrer"'
                           if url.startswith("http") else "")
                        + f'>{esc(label)}</a></li>')
        if rows:
            out.append(section_block("Session resources",
                                     f'<div class="prose"><ul>{"".join(rows)}</ul></div>',
                                     "Slides, PDFs and links"))
    return "".join(out)


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def list_html(v):
    items = "".join(f"<li>{md_inline(str(x))}</li>" for x in as_list(v))
    return f'<div class="prose"><ul>{items}</ul></div>'


def fmt_date(iso):
    try:
        y, m, d = iso.split("-")
        months = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"]
        return f"{int(d)} {months[int(m) - 1]} {y}"
    except Exception:
        return str(iso)


def keywords_for(record):
    if record.get("keywords"):
        bits = [str(k).strip() for k in as_list(record["keywords"]) if str(k).strip()]
        bits.append("House of Aspirants")
        return ", ".join(dict.fromkeys(bits))[:300]
    bits = []
    bits += record.get("exams", [])[:3]
    bits += [t.title() for t in record.get("tags", [])[:4]]
    bits += [s.replace("-", " ").title() for s in record.get("subjects", [])[:2]]
    bits.append("Punjab exam notes")
    bits.append("House of Aspirants")
    return ", ".join(dict.fromkeys(bits))[:300]


# =============================================================================
# 7. HUB RENDERING
# =============================================================================
# =============================================================================
# 6b. LIST FILTERS (Phase 4)
# Exam / subject / language / difficulty / date / category facets, computed
# from the records that really exist. The bar only renders when a facet has
# something to choose between, so an empty or single-value list never shows a
# control that cannot do anything.
# =============================================================================
FILTER_FACETS = ("exam", "subject", "language", "difficulty", "date",
                 "category", "chapter")
FILTER_LABEL = {"exam": "Exam", "subject": "Subject", "language": "Language",
                "difficulty": "Difficulty", "date": "Date",
                "category": "Category", "chapter": "Chapter"}


def _slug_facet(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def filter_facets(records, index):
    """{facet: [(value, label), ...]} for values that really occur.

    Two conditions before a facet is worth showing: the list has to hold more
    than one document (a single card has nothing to filter), and the facet
    itself has to offer at least two distinct values to pick between."""
    if len(records) < 2:
        return {}
    found = {f: {} for f in FILTER_FACETS}
    for r in records:
        for e in r.get("exams") or []:
            found["exam"][_slug_facet(e)] = str(e)
        for s in r.get("subjects") or []:
            found["subject"][s] = subject_name(index, s)
        lang_v = str(r.get("language") or r.get("lang") or "")
        if lang_v:
            # Study material states its OWN language (the language folder the
            # file sits in, or its name or sidecar); everything else falls
            # back to the page language.
            found["language"][lang_v] = study_language_label(lang_v)
        if r.get("difficulty"):
            found["difficulty"][_slug_facet(r["difficulty"])] = \
                str(r["difficulty"])
        if r.get("published"):
            ym = str(r["published"])[:7]
            found["date"][ym] = month_label(ym)
        if r.get("category"):
            found["category"][_slug_facet(r["category"])] = \
                str(r["category"])
        if r.get("studyChapter"):
            found["chapter"][_slug_facet(r["studyChapter"])] = str(
                r.get("studyChapterName") or r["studyChapter"])
    return {f: sorted(vals.items(), key=lambda kv: kv[1].lower())
            for f, vals in found.items() if len(vals) >= 2}


def filter_attrs(r, facets):
    """data-f-* attributes on one listing card, limited to the facets shown."""
    lang_v = str(r.get("language") or r.get("lang") or "")
    vals = {
        "exam": [_slug_facet(e) for e in (r.get("exams") or [])],
        "subject": list(r.get("subjects") or []),
        "language": [lang_v] if lang_v else [],
        "difficulty": [_slug_facet(r["difficulty"])] if r.get("difficulty") else [],
        "date": [str(r["published"])[:7]] if r.get("published") else [],
        "category": [_slug_facet(r["category"])] if r.get("category") else [],
        "chapter": [_slug_facet(r["studyChapter"])]
                   if r.get("studyChapter") else [],
    }
    out = ""
    for f in facets:
        if vals.get(f):
            out += f' data-f-{f}="{" ".join(vals[f])}"'
    return out


def filter_bar(facets, labels=None):
    """The chip row above a listing. Rendered only from real facet values.

    `labels` lets one collection name a facet the way its readers would: on a
    Study Material shelf the `category` facet IS the subject, and calling it
    "Category" would be a word the brief explicitly does not want on screen."""
    if not facets:
        return ""
    labels = {**FILTER_LABEL, **(labels or {})}
    groups = []
    for f in FILTER_FACETS:
        values = facets.get(f)
        if not values:
            continue
        chips = "".join(
            f'<button type="button" class="filter-chip" aria-pressed="false" '
            f'data-filter-facet="{f}" data-filter-value="{esc(v)}">'
            f'{esc(label)}</button>'
            for v, label in values)
        groups.append(f'<div class="filter-group" role="group" '
                      f'aria-label="{labels[f]}">'
                      f'<span class="fg-label">{labels[f]}</span>'
                      f'{chips}</div>')
    return (f'<div class="filter-bar" data-filter-bar>'
            f'{"".join(groups)}'
            f'<button type="button" class="filter-reset" data-filter-reset '
            f'hidden>Clear filters</button>'
            f'<p class="filter-count" data-filter-count aria-live="polite">'
            f'</p></div>')


def hub_cards(coll, items, index, lang="en", facets=None):
    cards = []
    for r in items:
        if coll == STUDY_DIR:
            cards.append(study_card(r, facets))
            continue
        if coll == "pdfs":
            path = pdf_href(r["meta"].get("file", ""))
            cards.append(f'<div class="card card-pad">'
                         f'<span class="eyebrow">PDF download</span>'
                         f'<h3>{esc(r["title"])}</h3>'
                         f'<p class="muted">{esc(r["description"])}</p>'
                         f'<p class="btn-row" style="margin-top:14px">'
                         f'<a class="btn btn-primary" href="{esc(path)}" download>'
                         f'⬇ Download PDF</a></p></div>')
            continue
        eyebrow = (pdf_eyebrow(r, index) if r.get("pdfDrop")
                   else {
                       "notes": (subject_name(index, r["subjects"][0])
                                 if r["subjects"] else "Study note"),
                       "magazine": f'Issue {r.get("month", "")}',
                       "strategy": str(r.get("category", "Strategy")),
                       "sessions": (f'{r.get("date", "")} · {r.get("platform", "")}'
                                    .strip(" ·")),
                       "recruitment": str(r.get("official_source",
                                                "Official notification")),
                   }.get(coll, str(r.get("category") or r.get("post")
                                   or NAV_ENTRY.get(coll, ("", ""))[0] or "Article")))
        if coll == "notes":
            meta = f'{r["readingMinutes"]} min read'
        elif coll == "sessions":
            meta = "Upcoming" if str(r.get("status", "")) == "upcoming" else "Past"
        else:
            meta = "Read more"
        cards.append(
            f'<a class="card card-pad reveal" href="{r["file"]}"'
            + f' data-lang="{esc(r["lang"] or "en")}"'
            + (' lang="pa"' if r["lang"] == "pa" else "")
            + (filter_attrs(r, facets) if facets else "") + '>'
            f'<span class="eyebrow">{esc(eyebrow)}</span>'
            f'<h3>{esc(r["title"])}</h3>'
            f'<p class="muted">{esc(r["description"])}</p>'
            f'<p class="ilink">{esc(meta)} →</p>'
            f'</a>')
    return "".join(cards)


def _pyq_one_download(cell, label=None):
    """A single download link plus the facts measured off the file itself."""
    href = esc(pdf_href(cell["path"]))
    bits = [f'<button type="button" class="btn btn-primary btn-sm pyq-dl" '
            f'data-pdf-preview="{href}" data-pdf-title="{esc(cell.get("title") or cell.get("filename") or "")}">'
            f'📖 Read</button>'
            f'<a class="btn btn-ghost btn-sm pyq-dl" href="{href}"'
            f' download>Download &darr;</a>']
    if label:
        bits.append(f'<span class="pyq-file">{esc(label)}</span>')
    meta = [f'{cell["pages"]} pages' if cell.get("pages") else "",
            str(cell.get("sizeLabel") or "")]
    meta = [m for m in meta if m]
    if meta:
        bits.append(f'<span class="pyq-filemeta">{" · ".join(meta)}</span>')
    return "".join(bits)


def _pyq_download(cells):
    """One table cell: every file the year is on record for, or the honest
    words for a document the conducting body has not published. Never a
    placeholder, never a guess. A year that ran in more than one shift keeps
    every shift, named, so the reader can tell them apart."""
    if not cells:
        return '<span class="pyq-none">Not published</span>'
    many = len(cells) > 1
    return "".join(
        f'<span class="pyq-dl-row">'
        f'{_pyq_one_download(c, c.get("label") or (c["filename"] if many else None))}'
        f'</span>'
        for c in cells)


def _pyq_row(paper):
    return (f'<tr><th scope="row" data-label="Year">{esc(paper["year"])}</th>'
            f'<td data-label="Question Paper">{_pyq_download(paper["papers"])}</td>'
            f'<td data-label="Official Answer Key">'
            f'{_pyq_download(paper.get("keys") or ([paper["key"]] if paper["key"] else []))}</td>'
            f'</tr>')


def pyq_exam_page(exam):
    """content/previous-year-questions/<exam>/ -> pyq/<slug>/index.html.

    The page IS the table: one row per year, the question paper and the
    official answer key side by side, every cell either a download or the
    words "Not published". Above it sit metadata.json and the overview files;
    below it, only links to pages this site really serves. A folder with no
    paper yet still publishes - with the table saying so - so the first PDF
    that lands is a file plus `npm run publish`, never an HTML edit.
    """
    url, file = exam["url"], exam["file"]
    hub_file = exam["hub"]
    title, desc = exam["title"], exam["description"]
    hub_url = f"{DOMAIN}/{hub_file[:-5]}"
    crumbs = {"id": f"{url}#breadcrumb",
              "items": [("Home", f"{DOMAIN}/"),
                        ("Previous Year Questions", f"{DOMAIN}/pyq"),
                        (title, url)]}
    jsonld = graph([webpage_node(url, title, desc, f"{url}#breadcrumb"),
                    breadcrumb_node(crumbs)])
    keywords = ", ".join(dict.fromkeys([
        title, f'{exam["organization"]} previous year questions',
        str(exam["category"]), "Punjab exam question papers",
        "official answer key", "House of Aspirants"]))[:300]

    # ---- overview: one block per language the sidecar declares -------------
    blocks = []
    for lang in exam["languages"]:
        src = exam["overview"].get(lang)
        if not src:
            continue                       # warned about while the manifest
        body, _toc = md_to_html(src)       # was built; never filled in here
        if lang == "pa":
            blocks.append(f"""        <div class="pyq-alt" lang="pa">
          <h3 lang="pa">ਪੰਜਾਬੀ ਵਿੱਚ</h3>
          <div class="prose">{body}</div>
        </div>""")
        else:
            blocks.append(f'        <div class="prose">{body}</div>')
    if blocks:
        overview_body = "\n".join(blocks)
    else:
        # A folder whose sidecar has not been written up still publishes: the
        # table below is complete, and this says so in as many words rather
        # than inventing a paragraph about an exam nobody has described yet.
        overview_body = (
            '        <div class="empty-state"><span class="es-icon" '
            'aria-hidden="true">\U0001F4C4</span>'
            '<h3>No overview written yet</h3>'
            "<p>The table below is complete either way. An overview is added "
            "as <code>overview.en.md</code> beside this exam's folder.</p>"
            "</div>")
    editions = ", ".join(esc({"en": "English", "pa": "Punjabi"}.get(l, l))
                         for l in exam["languages"])
    n_ed = len(exam["languages"])
    overview = f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Overview</span>
          <h2>About this exam</h2>
          <p>{esc(exam["organization"])} &middot; {esc(exam["category"])} &middot;
             {editions} edition{"s" if n_ed > 1 else ""} published</p>
        </div></div>
{overview_body}
      </div>
    </section>"""

    # ---- the table ---------------------------------------------------------
    if exam["papers"]:
        rows = "".join(_pyq_row(p) for p in exam["papers"])
        listing = f"""<div class="pyq-table-wrap">
        <table class="pyq-papers">
          <caption class="sr-only">{esc(title)} - question papers and official
            answer keys, newest year first</caption>
          <thead>
            <tr><th scope="col">Year</th><th scope="col">Question Paper</th>
                <th scope="col">Official Answer Key</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>"""
    else:
        listing = """<div class="empty-state">
          <span class="es-icon" aria-hidden="true">📄</span>
          <h3>No paper published yet</h3>
          <p>Nothing has been dropped into this exam's folder, so this page
             lists nothing rather than describing a paper that does not exist
             here. The day a question paper is added it appears in the table
             above on the very next publish.</p>
          <p class="btn-row" style="justify-content:center">
            <a class="btn btn-soft" href="pyq.html">Every published paper</a>
            <a class="btn btn-soft" href="mock.html">Attempt a timed mock</a>
          </p>
        </div>"""
    table_section = f"""    <section class="section" id="papers" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">By year</span>
          <h2>Papers and answer keys</h2>
          <p>One row per year. The question paper is published the moment it
             exists; its official answer key joins the same row when the
             conducting body releases one.</p>
        </div></div>
        {listing}
      </div>
    </section>"""

    # ---- other documents in the same folder -------------------------------
    others = ""
    if exam["others"]:
        items = "".join(
            f'<li><a href="pyq-{pdf_slug_from_name(Path(o["filename"]).stem)}.html">'
            f'{esc(o["title"])}</a><span class="part-meta">'
            f'{esc(o["sizeLabel"])}</span></li>'
            for o in exam["others"])
        others = f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Same folder</span>
          <h2>Other documents for this exam</h2>
        </div></div>
        <ul class="part-list">{items}</ul>
      </div>
    </section>"""

    exam_page = f"exam-{exam.get('exam') or exam['id']}.html"
    cross = [a for a in (
        (exam_page, "Exam guide", "Syllabus, pattern and subjects"),
        ("previous-year-questions.html", "Collection",
         "Every published paper, by exam"),
    ) if (ROOT / a[0]).exists()]
    cross_cards = "".join(
        f'<a class="card card-pad reveal" href="{esc(href)}">'
        f'<span class="eyebrow">{esc(kind)}</span><h3>{esc(what)}</h3>'
        f'<p class="ilink">Open &rarr;</p></a>' for href, kind, what in cross)

    html = head(title, desc, keywords, url, "website", jsonld, nested=True)
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <a href="index.html">Home</a><span>/</span><a href="pyq.html">Previous Year Questions</a><span>/</span><span>{esc(title)}</span>
        </nav>
        <span class="eyebrow">{esc(exam["organization"])} &middot; {esc(exam["category"])}</span>
        <h1>{esc(title)}</h1>
        <p class="muted">Official papers only - named with the exam and the year
           they came from, with the conducting body's answer key beside each one.</p>
        <div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{esc(desc)}</p>
        </div>
        <div class="doc-actions">
          <a class="btn btn-soft" href="#papers">Jump to the table &darr;</a>
          <a class="btn btn-soft" href="pyq.html">All previous year papers</a>
        </div>
      </div>
    </section>
{overview}
{table_section}
{others}
    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Keep going</span>
          <h2>Where to go next</h2>
          <p>The parts of House of Aspirants that connect to this page.</p>
        </div></div>
        <div class="grid grid-3">{cross_cards}
          <a class="card card-pad reveal" href="punjab-exams.html"><span class="eyebrow">Exam hub</span><h3>Every Punjab exam guide</h3><p class="ilink">Open &rarr;</p></a>
          <a class="card card-pad reveal" href="expected-mcqs.html"><span class="eyebrow">Practice</span><h3>Chapter-wise Expected MCQs</h3><p class="ilink">Open &rarr;</p></a>
          <a class="card card-pad reveal" href="mock.html"><span class="eyebrow">Practice</span><h3>Timed full-length mocks</h3><p class="ilink">Open &rarr;</p></a>
          <a class="card card-pad reveal" href="study.html?subject=gk"><span class="eyebrow">Study material</span><h3>Build the base a paper tests</h3><p class="ilink">Open &rarr;</p></a>
          <a class="card card-pad reveal" href="archives.html"><span class="eyebrow">Archive</span><h3>Everything published, by subject and month</h3><p class="ilink">Open &rarr;</p></a>
        </div>
      </div>
    </section>
  </main>
"""
    # `#papers` is an in-page anchor on a page that sets <base href="/">, so
    # the target has to name the page it belongs to - the same rule the
    # Punjabi edition and the study parts follow.
    html = html.replace('href="#papers"', f'href="/{file}#papers"')
    html += TAIL
    return html


def ca_section_page(page):
    """current-affairs/<language>/[<month>/]index.html -> /current-affairs/...

    Two page kinds, one shape. A language page carries the four doors the
    section is built from - Daily Current Affairs, Monthly Magazine, PDF
    Downloads, Archives - then the months it has published and every file it
    holds. A month page carries that month's files and the months beside it.

    Both set <base href="/">, exactly like the PYQ exam pages three directories
    above the root do, so the shared header and footer keep resolving from a
    nested URL; and because a page under a <base> resolves `#anchor` against
    the base rather than itself, the two in-page anchors are written as full
    paths - the same rule pyq/<exam>/index.html follows for `#papers`.

    Every number on the page comes from the records this run published. A
    language with nothing filed under it publishes an empty month list that
    says so, rather than describing months that are not on disk.
    """
    file, url = page["file"], page["url"]
    lang, is_month = page["language"], page["kind"] == "month"
    name, folder = lang["name"], lang["folder"]
    label = str(page.get("label") or "")
    crumb_items = [("Home", f"{DOMAIN}/"),
                   ("Current Affairs", f"{DOMAIN}/current-affairs"),
                   (name, f"{DOMAIN}/current-affairs/{folder}")]
    if is_month:
        crumb_items.append((label, url))
    crumbs = {"id": f"{url}#breadcrumb", "items": crumb_items}

    nodes = [webpage_node(url, page["title"], page["description"],
                          f"{url}#breadcrumb"),
             breadcrumb_node(crumbs)]

    trail = '<a href="index.html">Home</a><span>/</span>'
    trail += f'<a href="current-affairs.html">Current Affairs</a><span>/</span>'
    trail += (f'<a href="current-affairs/{folder}/index.html">{esc(name)}</a>'
              if is_month else f"<span>{esc(name)}</span>")
    if is_month:
        trail += f'<span>/</span><span>{esc(label)}</span>'

    if is_month:
        items = page["items"]
        rows = "".join(
            f'<li><a href="{esc(i["file"])}">{esc(i["title"])}</a>'
            f'<span class="part-meta">{esc(fmt_date(i["published"]))}'
            + (f' &middot; {i["pages"]} pages' if i["pages"] else "")
            + (f' &middot; {esc(i["size"])}' if i["size"] else "")
            + "</span></li>"
            for i in items)
        listing = f'<ul class="part-list">{rows}</ul>' if rows else """
          <div class="empty-state">
            <span class="es-icon" aria-hidden="true">🗞️</span>
            <h3>Nothing published for this month yet</h3>
            <p>This page exists because the folder is on disk. The day a file
               is dropped into it, the document appears here on the very next
               publish - nothing has to be edited.</p>
          </div>"""
        eyebrow = f"{esc(name)} &middot; {esc(label)}"
        h1 = f"{esc(label)} {esc(name)} Current Affairs"
        lead = (f"Everything published in {esc(name)} for {esc(label)}, newest "
                f"first. One list, one tap to read or download.")
        answer = (f"{len(items)} document{'s' if len(items) != 1 else ''} of "
                  f"{name} current affairs for {label}, free to read online or "
                  f"download as a PDF.")
    else:
        listing = ""
        n_doc = int(page["count"])
        eyebrow = (f"{esc(name)} &middot; {n_doc} document"
                   f"{'s' if n_doc != 1 else ''}")
        h1 = f"{esc(name)} Current Affairs"
        lead = (f"The monthly current affairs magazine in {esc(name)}, and "
                f"timed MCQ sets to practise the same months.")
        answer = (f"{name} current affairs for Punjab exams: {n_doc} document"
                  f"{'s' if n_doc != 1 else ''} published, newest "
                  f"{fmt_date(page['newest']) or 'not yet'}.")

    # --- language page: the same two doors as the hub ----------------------
    # A page under <base href="/"> resolves `#anchor` against the base, so the
    # in-page targets are written as root-relative paths to this page.
    here = "/" + file.rsplit("/", 1)[0]
    if is_month:
        sections = [f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">This month</span>
          <h2>In {esc(label)}</h2>
          <p>The issues published for this month. Open one to read it or
             download the PDF.</p>
        </div></div>
        {listing}
        <p class="btn-row" style="margin-top:22px">
          <a class="btn btn-soft" href="current-affairs/{esc(folder)}/index.html">All {esc(name)} issues</a>
          <a class="btn btn-soft" href="current-affairs.html#practice">Practice current affairs</a>
        </p>
      </div>
    </section>"""]
    else:
        langs_all = page.get("all_languages") or [page]
        idx = page.get("index") or {}
        n_issues = int(page.get("count") or 0)
        _, n_sets = _ca_counts([], idx)
        sections = [ca_doors(f"{here}#magazine", f"{here}#practice",
                             n_issues, n_sets, name),
                    ca_magazine_section(langs_all, only=folder),
                    ca_practice_section(idx)]

    html = head(page["title"], page["description"], page["keywords"], url,
                "website", graph(nodes), nested=True)
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">{trail}</nav>
        <span class="eyebrow">{eyebrow}</span>
        <h1>{h1}</h1>
        <p class="muted" style="max-width:70ch">{lead}</p>
      </div>
    </section>
{chr(10).join(sections)}
  </main>
"""
    html += TAIL
    return html


def hub_page(coll, cfg, items, index, exams, pyq_exams=(), ca_section=None):
    hub = HUBS[coll]
    url = f"{DOMAIN}/{hub['file'][:-5]}"
    prefix = cfg["prefix"]
    # Punjabi pages live under /pa/, so the collection prefix is matched on the
    # file name, never on the whole path.
    live = ([r for r in items
             if r["file"].split("/")[-1].startswith(prefix + "-")]
            if prefix else items)
    # The PDF hub is a registry (the PDF itself is the artifact - there is no
    # per-document page to list), so it ships as a plain WebPage, never as an
    # ItemList of URLs that do not exist.
    is_registry = (coll == "pdfs")

    crumbs = {"id": f"{url}#breadcrumb",
              "items": [("Home", f"{DOMAIN}/"), (hub["schema_hub"], url)]}
    page_node = webpage_node(url, hub["title"], hub["description"],
                             f"{url}#breadcrumb",
                             "CollectionPage" if (live and not is_registry)
                             else "WebPage")
    nodes = [page_node, breadcrumb_node(crumbs)]
    if live and not is_registry:
        nodes.insert(1, {
            "@type": "ItemList",
            "@id": f"{url}#list",
            "name": f'House of Aspirants {hub["schema_hub"]}',
            "numberOfItems": len(live),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": r["title"],
                 "item": r["url"]}
                for i, r in enumerate(live)
            ],
        })
        page_node["mainEntity"] = {"@id": f"{url}#list"}

    sections = []

    # --- primary listing ---------------------------------------------------
    if live:
        facets = filter_facets(live, index)
        # STEP 5: one section, one heading. Study material is never split into
        # a PDFs list, a notes list and a guides list - every file, whatever it
        # is, appears under the same heading.
        heading = "Study Material" if coll == STUDY_DIR else (
            "Latest notes" if coll == "notes" else "All published")
        # Two language folders: a guide published in English and in Punjabi
        # is one article in two languages, so the list opens on ONE language
        # (the reader's) instead of showing every guide twice. The folder is
        # chosen in content.js; without JavaScript both languages show.
        n_lang = {"en": 0, "pa": 0}
        for r in live:
            n_lang["pa" if r.get("lang") == "pa" else "en"] += 1
        folders = (coll not in (STUDY_DIR, "pdfs")
                   and n_lang["en"] > 0 and n_lang["pa"] > 0)
        bar_facets = ({k: v for k, v in facets.items() if k != "language"}
                      if folders else facets)
        folder_html = (f"""<div class="lang-folders" role="group" aria-label="Language" data-lang-folders>
            <button type="button" class="lang-folder" aria-pressed="false" data-lang-folder="pa">
              <span class="lf-ico" aria-hidden="true">📁</span>
              <span class="lf-name" lang="pa">ਪੰਜਾਬੀ</span>
              <span class="lf-count" lang="pa">{n_lang["pa"]} ਲੇਖ</span>
            </button>
            <button type="button" class="lang-folder" aria-pressed="false" data-lang-folder="en">
              <span class="lf-ico" aria-hidden="true">📁</span>
              <span class="lf-name">English</span>
              <span class="lf-count">{n_lang["en"]} article{"s" if n_lang["en"] != 1 else ""}</span>
            </button>
          </div>""" if folders else "")
        head_html = f"""<div class="section-head reveal"><div>
            <span class="eyebrow">{"Published" if coll != STUDY_DIR else "Every format, one list"}</span>
            <h2>{heading}</h2>
            <p>{esc(hub["lead"])}</p>
          </div></div>
          {folder_html}
          {filter_bar(bar_facets, {"category": "Subject"} if coll == STUDY_DIR else None)}
          <div class="grid grid-3" data-filter-list>{hub_cards(coll, live, index, facets=facets)}</div>"""
    else:
        cta_href, cta_text = hub["empty_cta"]
        head_html = f"""<div class="section-head reveal"><div>
            <span class="eyebrow">Publishing pipeline</span>
            <h2>{esc(hub["empty_h3"])}</h2>
          </div></div>
          <div class="empty-state">
            <span class="es-icon" aria-hidden="true">✍️</span>
            <h3>{esc(hub["empty_h3"])}</h3>
            <p>{esc(hub["empty_p"])}</p>
            <p class="btn-row" style="justify-content:center">
              <a class="btn btn-soft" href="{esc(cta_href)}">{esc(cta_text)}</a>
            </p>
          </div>"""
    sections.append(f"""<section class="section">
      <div class="container">{head_html}</div>
    </section>""")

    # --- Current Affairs opens with a choice, not a list --------------------
    # /current-affairs is a door, not a feed: the first thing a reader sees is
    # Punjabi and English as the two big language cards, because every month,
    # magazine issue and download lives behind one of them. The published list
    # below stays exactly where it was - it is what the hub's schema and its
    # sitemap entry describe - so nothing that worked stops working.
    if coll == "current-affairs":
        langs = (ca_section or {}).get("languages") or []
        covered = {i["file"] for l in langs for m in l.get("months", [])
                   for i in m.get("items", [])}
        extra = [{"file": r["file"], "title": r["title"],
                  "published": r.get("published", ""), "pages": 0, "size": ""}
                 for r in live if r["file"] not in covered]
        n_issues, n_sets = _ca_counts(langs, index)
        sections = [ca_doors("#magazine", "#practice",
                             n_issues, n_sets),
                    ca_magazine_section(langs, extra),
                    ca_practice_section(index)]

    # --- collection-specific extras (always real links, never invented) ----
    if coll == "notes":
        guides = []
        guides_path = ROOT / "data" / "articles.json"
        if guides_path.exists():
            try:
                guides = json.loads(guides_path.read_text(encoding="utf-8")).get("articles", [])
            except Exception as e:
                warn(f"data/articles.json unreadable: {e}")
        cards = "".join(
            f'<a class="card card-pad reveal" href="{esc(a["url"])}">'
            f'<span class="eyebrow">Study guide</span><h3>{esc(a["title"])}</h3>'
            f'<p class="muted">{esc(a["description"])}</p>'
            f'<p class="ilink">Read guide →</p></a>' for a in guides[:4])
        if cards:
            sections.append(f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Evergreen</span>
          <h2>Study guides to start with</h2>
          <p>Long-form guides that pair with the notes as they publish.</p>
        </div><a class="btn btn-soft" href="articles.html">All study guides</a></div>
        <div class="grid grid-3">{cards}</div>
      </div>
    </section>""")

    elif coll == "magazine":
        ca = next((s for s in index.get("subjects", []) if s["id"] == "current-affairs"), None)
        if ca:
            cards = "".join(
                f'<a class="card card-pad reveal" href="{quiz_href(t)}">'
                f'<span class="eyebrow">Current affairs set</span>'
                f'<h3>{esc(t.get("name", ""))}</h3>'
                f'<p class="ilink">{t.get("count", 0)} MCQs →</p></a>'
                for t in ca.get("topics", []) if t.get("available")) 
            sections.append(f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Related current affairs</span>
          <h2>Current affairs sets</h2>
          <p>The published quiz sets each issue draws from.</p>
        </div><a class="btn btn-soft" href="subject.html?subject=current-affairs">All current affairs</a></div>
        <div class="grid grid-3">{cards}</div>
      </div>
    </section>""")

    elif coll == "previous-year-questions":
        # Every exam folder publishes a page of its own at pyq/<slug>/index.html.
        # The collection hub links them, so a paper is never a dead end and the
        # SEO gate has one static place to check the link from: a new exam
        # appears here the day its folder does, with no page edited by hand.
        def _pyq_card(e):
            years = ", ".join(p["year"] for p in e["papers"][:4])
            return (f'<a class="card card-pad reveal" href="{esc(e["file"])}">'
                    f'<span class="eyebrow">📁 {esc(e["organization"])}</span>'
                    f'<h3>{esc(e["title"])}</h3>'
                    f'<p class="text-sm muted">{esc(years) or "Papers coming soon"}</p>'
                    f'<p class="text-sm">{e["count"]} paper'
                    f'{"s" if e["count"] != 1 else ""} · {e.get("keyFiles", e["keys"])} answer key'
                    f'{"s" if e.get("keyFiles", e["keys"]) != 1 else ""}</p>'
                    f'<p class="ilink">Open &rarr;</p></a>')
        org_order = ["Punjab Police", "PSSSB", "PPSC"]
        orgs = {}
        for e in pyq_exams:
            orgs.setdefault(e["organization"], []).append(e)
        ordered = sorted(orgs, key=lambda o: (org_order.index(o) if o in org_order
                                              else len(org_order), o))
        org_names = {
            "Punjab Police": "Punjab Police",
            "PSSSB": "PSSSB - Subordinate Services Selection Board, Punjab",
            "PPSC": "PPSC - Punjab Public Service Commission",
        }
        for n, org in enumerate(ordered):
            group = orgs[org]
            cards = "".join(_pyq_card(e) for e in group)
            papers_n = sum(e["count"] for e in group)
            intro = ("""
          <p>Each exam is a folder: its question papers and the official answer
             keys beside them, one row per year, with a download for each file.</p>"""
                     if n == 0 else "")
            browse = ('<a class="btn btn-soft" href="pyq.html">Browse every paper</a>'
                      if n == 0 else "")
            sections.append(f"""<section class="section" style="padding-top:0" id="org-{esc(slugify(org))}">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">{len(group)} exam{"s" if len(group) != 1 else ""} · {papers_n} paper{"s" if papers_n != 1 else ""}</span>
          <h2>{esc(org_names.get(org, org))}</h2>{intro}
        </div>{browse}</div>
        <div class="grid grid-3">{cards}</div>
      </div>
    </section>""")

    elif coll == "strategy":
        sections.append(subject_strip(index))

    elif coll == "sessions":
        sections.append("""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">How a session runs</span>
          <h2>What every session includes</h2>
          <p>One topic, one slot, one join link - and a written record afterwards.</p>
        </div></div>
        <div class="grid grid-3">
          <div class="card card-pad"><h3>Before</h3><p class="muted">Topic, date,
            time, platform and the join link, published as soon as the slot is
            confirmed.</p></div>
          <div class="card card-pad"><h3>During</h3><p class="muted">One focused
            topic with live questions - bring your doubts and ask them in the
            session.</p></div>
          <div class="card card-pad"><h3>After</h3><p class="muted">A session
            summary, the important questions discussed and the student doubts
            that came up.</p></div>
        </div>
      </div>
    </section>""")

    elif coll == "recruitment":
        sections.append(exam_coverage(exams))
        sections.append("""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Policy</span>
          <h2>How recruitment information is published</h2>
        </div></div>
        <div class="grid grid-2">
          <div class="card card-pad"><h3>Official sources only</h3>
            <p class="muted">Every record links the recruiting body's own website -
            a government domain - and restates only what that notification says.
            Nothing is copied from jobs aggregators or Telegram forwards.</p></div>
          <div class="card card-pad"><h3>Dates are never guessed</h3>
            <p class="muted">Vacancies, cut-offs and admit cards change between
            notifications, so this portal does not track them. Always read the
            official notification before acting on a date.</p></div>
        </div>
      </div>
    </section>""")

    elif coll == "pdfs":
        sections.append("""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Offline first</span>
          <h2>Downloads behave like the rest of the site</h2>
          <p>No sign-up, no email wall, no redirect through a third party.</p>
        </div></div>
        <div class="grid grid-3">
          <div class="card card-pad"><h3>One click</h3><p class="muted">Each PDF
            downloads straight from this site's own storage.</p></div>
          <div class="card card-pad"><h3>Tagged</h3><p class="muted">Subject and
            exam tags tell you which paper the sheet belongs to.</p></div>
          <div class="card card-pad"><h3>Free</h3><p class="muted">Everything on
            this portal stays free - study material included.</p></div>
        </div>
      </div>
    </section>""")

    html = head(hub["title"], hub["description"], hub["keywords"], url,
                "website", graph(nodes))
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <a href="index.html">Home</a><span>/</span><span>{esc(hub["schema_hub"])}</span>
        </nav>
        <span class="eyebrow">{esc(hub["eyebrow"])}</span>
        <h1>{esc(hub["h1"])}</h1>
        <p class="muted" style="max-width:70ch">{esc(hub["lead"])}</p>
        {"" if coll == "current-affairs" else f'''<div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{esc(hub["answer"])}</p>
        </div>'''}
      </div>
    </section>
{"".join(sections)}
  </main>
"""
    html = enforce_link_floor(html, coll, hub["file"])
    html += TAIL
    return html, live


def quiz_href(t):
    return (t["landing"].lstrip("/") + ".html") if t.get("landing") else \
        f'quiz.html?subject=current-affairs&topic={t["id"]}'


def ca_language_section(languages, index):
    """The "Choose your language" cards at the top of /current-affairs.

    The same .lang-card the Study shelf renders its language step from, with
    the same two badges - months and PDFs - counted off the records this run
    published. Nothing here is typed: a language with no folder under it
    would publish saying so, and a new language folder becomes a card on the
    next build with no line of this file touched."""
    color = next((str(s.get("color") or "")
                  for s in index.get("subjects", [])
                  if s.get("id") == "current-affairs"), "")
    style = f' style="--sc:{esc(color)}"' if color else ""
    cards = []
    for lang in languages:
        labels = [m["label"] for m in lang.get("months", [])]
        shown = ", ".join(labels[:3])
        if len(labels) > 3:
            shown += f" and {len(labels) - 3} more"
        n_month, n_pdf = len(labels), int(lang.get("count") or 0)
        native = (f'<p class="lang-native">{esc(lang["native"])}</p>'
                  if lang.get("native") and lang["native"] != lang["name"]
                  else "")
        cards.append(
            f'<a class="card lang-card reveal"{style} href="{esc(lang["file"])}">'
            f'<span class="lang-flag" aria-hidden="true">'
            f'{esc(lang.get("flag") or chr(0x1F310))}</span>'
            f'<h3>{esc(lang["name"])}</h3>{native}'
            f'<p class="muted">{esc(shown) or "Nothing published yet."}</p>'
            f'<div class="subject-meta">'
            f'<span class="badge {"badge-success" if n_month else "badge-muted"}">'
            f'{n_month} month{"s" if n_month != 1 else ""}</span>'
            f'<span class="badge {"badge-success" if n_pdf else "badge-muted"}">'
            f'{n_pdf} PDF{"s" if n_pdf != 1 else ""}</span>'
            f'</div></a>')
    return f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Language</span>
          <h2>Choose your language</h2>
          <p>Every month, magazine issue and download lives behind one of
             these two. Pick a language and the rest is one tap away.</p>
        </div></div>
        <div class="grid grid-2">{''.join(cards)}</div>
      </div>
    </section>"""


# --- Current Affairs: two doors, nothing else -------------------------------
# The section offers exactly two things - the monthly magazine (the PDFs, by
# month) and practice (the current affairs quiz sets). The hub and every
# language page open with the same two cards and then list those two things.
def ca_doors(mag_href, practice_href, n_issues, n_sets, lang_name=""):
    tiles = (
        ("Monthly", "Monthly Current Affairs Magazine",
         f"{n_issues} issue{'s' if n_issues != 1 else ''} in "
         f"{lang_name or 'Punjabi and English'} - read online or download the PDF.",
         mag_href, "Open the magazine"),
        ("Practice", "Practice Current Affairs",
         f"{n_sets} timed MCQ set{'s' if n_sets != 1 else ''} on the same months, "
         "with answers explained.", practice_href, "Start practising"),
    )
    cards = "".join(
        f'<a class="card card-pad ca-door reveal" href="{esc(href)}">'
        f'<span class="eyebrow">{esc(eb)}</span><h2>{esc(title)}</h2>'
        f'<p class="muted">{esc(sub)}</p>'
        f'<p class="ilink">{esc(action)} &rarr;</p></a>'
        for eb, title, sub, href, action in tiles)
    return f"""<section class="section" style="padding-top:28px">
      <div class="container">
        <div class="grid grid-2">{cards}</div>
      </div>
    </section>"""


def _ca_doc_row(i, lang_name=""):
    meta = esc(fmt_date(i["published"]))
    if i.get("pages"):
        meta += f' &middot; {i["pages"]} pages'
    if i.get("size"):
        meta += f' &middot; {esc(i["size"])}'
    badge = (f'<span class="badge badge-muted">{esc(lang_name)}</span> '
             if lang_name else "")
    return (f'<li>{badge}<a href="{esc(i["file"])}">{esc(i["title"])}</a>'
            f'<span class="part-meta">{meta}</span></li>')


def ca_magazine_section(languages, extra=(), only=None):
    """Every issue, newest month first. On the hub each month lists both
    languages; on a language page (`only`) just that language. The month
    heading links the month page, so every month page stays reachable."""
    months = {}
    for lang in languages:
        if only and lang.get("folder") != only:
            continue
        for m in lang.get("months", []):
            row = months.setdefault(m["slug"], {"label": m["label"],
                                                "key": (m.get("year") or 0, m.get("num") or 0),
                                                "rows": []})
            for i in m.get("items", []):
                row["rows"].append((lang, m, i))
    blocks = []
    for slug, mo in sorted(months.items(), key=lambda kv: kv[1]["key"], reverse=True):
        links = []
        seen = set()
        for lang, m, _ in mo["rows"]:
            if lang["folder"] in seen:
                continue
            seen.add(lang["folder"])
            links.append(f'<a class="ilink" href="{esc(m["file"])}">'
                         f'{esc(lang["name"])} &rarr;</a>')
        rows = "".join(_ca_doc_row(i, "" if only else lang["name"])
                       for lang, m, i in mo["rows"])
        blocks.append(
            f'<div class="card card-pad ca-month reveal">'
            f'<div class="ca-month-head"><h3>{esc(mo["label"])}</h3>'
            f'<span class="ca-month-links">{" ".join(links)}</span></div>'
            f'<ul class="part-list">{rows}</ul></div>')
    if extra:
        rows = "".join(_ca_doc_row(i) for i in extra)
        blocks.append(f'<div class="card card-pad ca-month reveal">'
                      f'<div class="ca-month-head"><h3>Other issues</h3></div>'
                      f'<ul class="part-list">{rows}</ul></div>')
    if only:
        langs_here = [l for l in languages if l.get("folder") != only]
        other = "".join(f'<a class="btn btn-soft" href="{esc(l["file"])}">'
                        f'{esc(l["name"])} issues</a>' for l in langs_here)
    else:
        other = "".join(f'<a class="btn btn-soft" href="{esc(l["file"])}">'
                        f'Only {esc(l["name"])}</a>' for l in languages)
    body = "".join(blocks) or """<div class="empty-state">
            <span class="es-icon" aria-hidden="true">🗞️</span>
            <h3>No issue published yet</h3>
            <p>The first monthly issue appears here the day its PDF is published.</p>
          </div>"""
    return f"""<section class="section" id="magazine" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Monthly</span>
          <h2>Monthly Current Affairs Magazine</h2>
          <p>Newest month first. Open an issue to read it or download the PDF -
             no sign-up.</p>
        </div><div class="btn-row">{other}</div></div>
        <div class="ca-months">{body}</div>
      </div>
    </section>"""


def ca_practice_section(index):
    ca = next((s for s in index.get("subjects", [])
               if s.get("id") == "current-affairs"), None) or {}
    topics = [t for t in ca.get("topics", []) if t.get("available")]
    # Newest month first; inside a month, Part 1 before Part 2.
    months = {m: i for i, m in enumerate(
        ("january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"), 1)}
    def month_key(t):
        m = re.search(r"(january|february|march|april|may|june|july|august|"
                      r"september|october|november|december)\D{0,3}(20\d\d)",
                      str(t.get("name") or t.get("id") or "").lower())
        return (int(m.group(2)), months[m.group(1)]) if m else (0, 0)
    def part_no(t):
        m = re.search(r"part\D{0,2}(\d+)", str(t.get("name") or "").lower())
        return int(m.group(1)) if m else 0
    topics.sort(key=lambda t: (part_no(t), t.get("name") or ""))
    topics.sort(key=month_key, reverse=True)
    def langs(t):
        v = sorted((t.get("variants") or {}).keys())
        names = {"pa": "ਪੰਜਾਬੀ", "en": "English"}
        return " · ".join(names.get(x, x) for x in v)
    cards = "".join(
        f'<a class="card card-pad reveal" href="{quiz_href(t)}">'
        f'<span class="eyebrow">{t.get("count", 0)} MCQs'
        + (f' &middot; {esc(langs(t))}' if langs(t) else "") + '</span>'
        f'<h3>{esc(t.get("name", ""))}</h3>'
        f'<p class="ilink">Start the set &rarr;</p></a>'
        for t in topics)
    body = (f'<div class="grid grid-3">{cards}</div>' if cards else
            """<div class="empty-state"><span class="es-icon" aria-hidden="true">📝</span>
            <h3>No practice set published yet</h3>
            <p>Current affairs sets appear here as soon as they are published.</p></div>""")
    return f"""<section class="section" id="practice" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Practice</span>
          <h2>Practice Current Affairs</h2>
          <p>Timed MCQ sets, newest first. Switch between Punjabi and English
             inside any set.</p>
        </div></div>
        {body}
      </div>
    </section>"""


def _ca_counts(languages, index):
    n_issues = sum(int(l.get("count") or 0) for l in languages)
    ca = next((s for s in index.get("subjects", [])
               if s.get("id") == "current-affairs"), None) or {}
    n_sets = sum(1 for t in ca.get("topics", []) if t.get("available"))
    return n_issues, n_sets


def subject_strip(index):
    cards = []
    for s in index.get("subjects", []):
        # One pass over the subject's flat topic list: it already contains the
        # categorized quizzes, so also summing categories[].topics would count
        # every one of them twice (e.g. "8 sets" where 4 sets exist).
        n = sum(1 for t in s.get("topics", []) if t.get("available"))
        if not n:
            continue
        cards.append(f'<a class="card card-pad reveal" href="subject.html?subject={s["id"]}">'
                     f'<span class="eyebrow">{esc(s.get("icon", ""))} {n} sets</span>'
                     f'<h3>{esc(s.get("name", ""))}</h3>'
                     f'<p class="ilink">Practise now →</p></a>')
    return f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Practice</span>
          <h2>Pair the plan with practice</h2>
          <p>Every subject already has live sets to run the plan against.</p>
        </div><a class="btn btn-soft" href="index.html#subjects">All subjects</a></div>
        <div class="grid grid-3">{"".join(cards)}</div>
      </div>
    </section>"""


def exam_coverage(exams):
    cards = []
    for e in exams:
        slug = e.get("id", "")
        href = f"exam-{slug}.html"
        if not (ROOT / href).exists():
            continue
        rec = next((r for r in RECRUITMENT if r.get("exam") == slug), None)
        badge = ('<span class="badge badge-success">Official link</span>'
                 if rec else '<span class="badge badge-muted">Guide only</span>')
        cards.append(f'<a class="card card-pad reveal" href="{href}">'
                     f'<span class="eyebrow">{badge} Preparation guide</span>'
                     f'<h3>{esc(e.get("name", ""))}</h3>'
                     f'<p class="muted">{esc(e.get("summary", ""))}</p>'
                     f'<p class="ilink">Open guide →</p></a>')
    return f"""<section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Posts we cover</span>
          <h2>Every post, with its preparation guide</h2>
          <p>Eligibility, syllabus and selection process for each post live on its
             guide page, written from the official syllabus.</p>
        </div><a class="btn btn-soft" href="punjab-exams.html">All Punjab exams</a></div>
        <div class="grid grid-3">{"".join(cards)}</div>
      </div>
    </section>"""


# =============================================================================
# 8. HOMEPAGE FEED BLOCKS (patched between markers in index.html)
# =============================================================================
FEED_BLOCKS = {
    "notes": "notes",
    "current-affairs": "current-affairs",
    "magazine": "magazine",
    "sessions": "sessions",
    "recruitment": "recruitment",
}


def feed_html(kind, items, index):
    """Static homepage cards for the newest content. Returns '' when a section
    has nothing real to show, so the homepage never advertises empty shelves."""
    if kind == "notes":
        if not items:
            return ""
        cards = "".join(
            f'<a class="card card-pad reveal" href="{r["file"]}">'
            f'<span class="eyebrow">{esc(subject_name(index, r["subjects"][0]) if r["subjects"] else "Study note")}</span>'
            f'<h3>{esc(r["title"])}</h3>'
            f'<p class="muted">{esc(r["description"])}</p>'
            f'<p class="ilink">{r["readingMinutes"]} min read →</p></a>'
            for r in items[:3])
        return cards

    if kind == "current-affairs":
        ca = next((s for s in index.get("subjects", []) if s["id"] == "current-affairs"), None)
        topics = [t for t in (ca.get("topics", []) if ca else []) if t.get("available")]
        topics.sort(key=lambda t: t.get("updatedAt") or 0, reverse=True)
        ca_articles = [r for r in items if r.get("collection") == "current-affairs"]
        ca_notes = [r for r in items
                    if r.get("collection") == "notes"
                    and "current-affairs" in r["subjects"]]
        cards = "".join(
            f'<a class="card card-pad reveal" href="{quiz_href(t)}">'
            f'<span class="eyebrow">Latest set · {t.get("count", 0)} MCQs</span>'
            f'<h3>{esc(t.get("name", ""))}</h3>'
            f'<p class="ilink">Attempt the set →</p></a>'
            for t in topics[:2])
        cards += "".join(
            f'<a class="card card-pad reveal" href="{r["file"]}">'
            f'<span class="eyebrow">{esc("Current affairs" if r.get("collection") == "current-affairs" else "Study note")}</span>'
            f'<h3>{esc(r["title"])}</h3>'
            f'<p class="ilink">{r["readingMinutes"]} min read →</p></a>'
            for r in (ca_articles + ca_notes)[:1])
        if not cards:
            return ""
        return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <span class="eyebrow">Latest Current Affairs</span>
            <h2>This month's current affairs</h2>
            <p>Fresh sets and notes - newest first, in Punjabi and English.</p>
          </div>
          <a class="btn btn-soft" href="subject.html?subject=current-affairs">All current affairs</a>
        </div>
        <div class="grid grid-3">{cards}</div>
      </div>
    </section>"""

    if kind == "magazine":
        if not items:
            return ""
        r = items[0]
        return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <span class="eyebrow">Latest Magazine</span>
            <h2>{esc(r["title"])}</h2>
            <p>{esc(r["description"])}</p>
          </div>
          <a class="btn btn-soft" href="magazine.html">Magazine archive</a>
        </div>
        <div class="grid grid-3">
          <a class="card card-pad reveal" href="{r["file"]}">
            <span class="eyebrow">Issue {esc(str(r.get("month", "")))}</span>
            <h3>{esc(r["title"])}</h3>
            <p class="ilink">Read the issue →</p>
          </a>
        </div>
      </div>
    </section>"""

    if kind == "sessions":
        up = [r for r in items if str(r.get("status", "")) == "upcoming"]
        if not up:
            return ""
        r = up[0]
        join = f'<a class="btn btn-primary" href="{esc(str(r.get("join", "")))}" target="_blank" rel="noopener">Join session</a>' \
            if r.get("join") else ""
        return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <span class="eyebrow">Weekly Live Session</span>
            <h2>{esc(r["title"])}</h2>
            <p>{esc(r.get("date", ""))} · {esc(str(r.get("time", "")))} · {esc(str(r.get("platform", "")))}</p>
          </div>
          <a class="btn btn-soft" href="live-sessions.html">All sessions</a>
        </div>
        <div class="btn-row reveal">{join}<a class="btn btn-soft" href="{r["file"]}">Session details →</a></div>
      </div>
    </section>"""

    if kind == "recruitment":
        if not items:
            return ""
        cards = "".join(
            f'<a class="card card-pad reveal" href="{r["file"]}">'
            f'<span class="eyebrow">Official notification</span>'
            f'<h3>{esc(r["title"])}</h3>'
            f'<p class="ilink">Open record →</p></a>' for r in items[:3])
        return f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <span class="eyebrow">Recruitment Updates</span>
            <h2>Official notifications only</h2>
            <p>Links to the recruiting body's own website - never a repost.</p>
          </div>
          <a class="btn btn-soft" href="recruitment.html">All recruitment records</a>
        </div>
        <div class="grid grid-3">{cards}</div>
      </div>
    </section>"""
    return ""


# The phone drawer is a shortlist, not a sitemap: these are the sections an
# aspirant opens between classes. Everything else still ships in the footer,
# the header dropdown and the thumb bar, so trimming the drawer removes no
# destination — only the scroll it used to cost.
DRAWER_HUBS = ("study-notes.html", "current-affairs.html", "strategy.html",
               "live-sessions.html", "expected-mcqs.html")


def nav_lines(kind):
    """(href, label, emoji, data-nav) for every hub, in publication order."""
    entries = [(HUBS[c]["file"],) + NAV_ENTRY[c] + (HUB_NAV[HUBS[c]["file"][:-5]],)
               for c in NAV_ORDER]
    entries += [(f, label, emoji, HUB_NAV.get(f[:-5], ""))
                for f, label, emoji in NAV_EXTRA]
    if kind == "drawer":
        entries = [e for e in entries if e[0] in DRAWER_HUBS]
    if kind == "footer":
        entries += [(f, label, emoji, "")
                     for f, label, emoji in FOOT_EXTRA]
        entries += [(author_profile_file(a), str(a["name"]), "\U0001f4dd", "")
                    for a in load_authors() if author_profile_file(a)]
    out = []
    for file, label, emoji, key in entries:
        if kind == "menu":
            out.append(f'<a data-nav="{key}" href="{file}">'
                       f'<span data-i18n="{label}">{label}</span></a>')
        elif kind == "drawer":
            out.append(f'<a class="mm-link" data-nav="{key}" href="{file}">'
                       f'<span class="mm-emoji">{emoji}</span> '
                       f'<span data-i18n="{label}">{label}</span></a>')
        else:
            out.append(f'<a href="{file}" data-i18n="{label}">{label}</a>')
    return out


def patch_core_nav():
    """Regenerate the header menu, drawer and footer Study links from HUBS.

    Navigation is data, not markup: the three blocks between HOA-NAV markers in
    assets/js/core.js are rewritten on every build, so adding a collection
    publishes it into the navigation without anyone hand-editing JS.
    """
    path = ROOT / "assets" / "js" / "core.js"
    src = path.read_text(encoding="utf-8")
    out = src
    for kind in ("menu", "drawer", "footer"):
        start, end = f"<!-- HOA-NAV:{kind} -->", f"<!-- /HOA-NAV:{kind} -->"
        if start not in out or end not in out:
            err(f"assets/js/core.js: navigation marker {start!r} missing - "
                f"restore it before running the content build")
            return
        pre, rest = out.split(start, 1)
        head, post = rest.split(end, 1)
        ws = re.search(r"[ \t]*$", head).group(0)   # marker indentation
        lines = nav_lines(kind)
        out = pre + start + "\n" + "\n".join(ws + ln for ln in lines) + \
            "\n" + ws + end + post
    if out != src:
        path.write_text(out, encoding="utf-8")
        info("assets/js/core.js: navigation blocks regenerated from HUBS")


# =============================================================================
# 8b. PHASE 2 ARTEFACTS - search corpus, RSS feed, archive index
# =============================================================================
SEARCH_INDEX = ROOT / "data" / "search-index.json"
FEED_PATH = ROOT / "feed.xml"
POPULARITY_PATH = ROOT / "data" / "popularity.json"
ARCHIVES_FILE = "archives.html"
ARCHIVES_TITLE = "Punjab Exam Study Archive | House of Aspirants"
ARCHIVES_DESC = (
    "Every study note, current affairs article, magazine issue, strategy "
    "guide, live session and recruitment record here - newest first, by "
    "subject, exam and month."
)
ARCHIVES_KEYWORDS = ("study notes archive, current affairs archive, Punjab exam "
                     "articles, monthly archive, subject wise notes")
BODY_LIMIT = 1200        # per document; the corpus is fetched when search opens
FEED_LIMIT = 20
WDAY = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MON_FULL = ("January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December")


def plain_text(src):
    """Visible words only: markup, scripts and styles are dropped, so the
    search corpus never matches invisible page furniture or schema markup."""
    src = re.sub(r"<(script|style)\b.*?</\1>", " ", src or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", src)).strip()


def rfc822(iso):
    """Deterministic RFC 822 date: the document's own published day, never the
    build clock, so a rebuild emits byte-identical XML."""
    when = datetime.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10]))
    return (f"{WDAY[when.weekday()]}, {when.day:02d} {MON[when.month - 1]} "
            f"{when.year} 00:00:00 +0000")


def month_label(ym):
    return f"{MON_FULL[int(ym[5:7]) - 1]} {ym[:4]}"


def load_popularity():
    """Real readership numbers, if any exist.

    Popularity is measured, never guessed: the file ships empty and the
    "Popular posts" section stays off the archive page until analytics fill it
    in with counts that can be checked.
    """
    if not POPULARITY_PATH.exists():
        return {}
    try:
        rows = json.loads(POPULARITY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        err(f"data/popularity.json unreadable: {e}")
        return {}
    rows = rows.get("views", {}) if isinstance(rows, dict) else rows
    if not isinstance(rows, dict):
        err("data/popularity.json: 'views' must be an object of url -> views")
        return {}
    out = {}
    for k, v in rows.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            err(f"data/popularity.json: {k!r} must be a positive view count")
            continue
        out[str(k)] = int(v)
    return out


def write_search_index(items, index, pyq_exams=()):
    """data/search-index.json - the full-site corpus behind Ctrl+K.

    Title, description, body, tags, subjects, exams and category for every
    published document plus the study guides. Fetched lazily the first time the
    search overlay opens, so it costs nothing on page load.
    """
    corpus = [{
        "u": "/" + r["file"],
        "t": r["title"],
        "d": r["description"],
        "b": plain_text(r.get("bodyHtml", ""))[:BODY_LIMIT],
        "k": r["collection"],
        "l": r["lang"],
        "c": str(r.get("category") or ""),
        "g": r["tags"],
        "s": [subject_name(index, s) for s in r["subjects"]],
        "e": r["exams"],
        # Phase 4 search contract: summary, keywords and author are first-class
        # search fields, next to title, body, subject, category and exam tags.
        # The description is the last fallback so a row is never blank - the
        # gate in scripts/seo_check.py checks exactly this.
        "m": str(r.get("summary") or r.get("subtitle") or r.get("description") or "")[:220],
        # keywords_for() falls back to the document's own exams, tags and
        # subjects, so a row is never blank here either (seo_check gates this).
        "w": [w.strip() for w in keywords_for(r).split(",") if w.strip()][:12],
        "a": str(r.get("author") or BYLINE),
        "f": str(r.get("difficulty") or ""),
    } for r in items]
    try:
        guides = json.loads(
            (ROOT / "data" / "articles.json").read_text(encoding="utf-8")
        ).get("articles", [])
    except Exception as e:
        err(f"data/articles.json unreadable: {e}")
        guides = []
    for g in guides:
        path = ROOT / str(g.get("url", ""))
        corpus.append({
            "u": "/" + str(g.get("url", "")),
            "t": str(g.get("title", "")),
            "d": str(g.get("description", "")),
            "b": (plain_text(path.read_text(encoding="utf-8"))[:BODY_LIMIT]
                  if path.exists() else ""),
            "k": "guide",
            "l": "en",
            "c": "",
            "g": [],
            "s": [subject_name(index, s) for s in g.get("subjects", [])],
            "e": [],
            "m": "",
            "w": [str(k) for k in g.get("keywords", [])][:12]
                 if isinstance(g.get("keywords"), list) else [],
            "a": BYLINE,
            "f": "",
        })
    # Exam landing pages: the "Exams" facet of the search contract. The summary
    # is the site's own copy for that page, so nothing here is invented.
    try:
        exam_rows = json.loads(
            (ROOT / "data" / "exams.json").read_text(encoding="utf-8")
        ).get("exams", [])
    except Exception as e:
        err(f"data/exams.json unreadable: {e}")
        exam_rows = []
    for ex in exam_rows:
        f = f"exam-{str(ex.get('id', ''))}.html"
        if not (ROOT / f).exists() or not str(ex.get("summary", "")).strip():
            continue
        corpus.append({
            "u": "/" + f,
            "t": str(ex.get("name", "")),
            "d": str(ex.get("summary", "")),
            "b": "",
            "k": "exam",
            "l": "en",
            "c": "",
            "g": [],
            "s": [subject_name(index, s) for s in ex.get("subjects", [])],
            "e": [str(ex.get("name", ""))],
            "m": "",
            "w": [str(k) for k in ex.get("keywords", [])][:12]
                 if isinstance(ex.get("keywords"), list) else [],
            "a": BYLINE,
            "f": "",
        })
    # Previous Year Questions: one row per exam folder, so a search for an
    # exam's papers lands on the table that lists them rather than on nothing.
    # The body is the exam's own overview - real words from overview.en.md /
    # overview.pa.md, never a summary invented here.
    exam_names = {str(ex.get("id", "")): str(ex.get("name", ""))
                  for ex in exam_rows}
    for ex in (pyq_exams or []):
        overview = re.sub(r"^#+\s*", "", " ".join(
            ex.get("overview", {}).values() or []), flags=re.M)
        corpus.append({
            "u": "/" + ex["file"],
            "t": ex["title"],
            "d": ex["description"],
            "b": plain_text(overview)[:BODY_LIMIT],
            "k": "previous-year-questions",
            "l": "en",
            "c": str(ex.get("category") or ""),
            "g": [],
            "s": [],
            "e": [n for n in (exam_names.get(str(ex.get("id", ""))),) if n],
            "m": str(ex.get("description") or "")[:220],
            "w": [str(w) for w in (ex.get("title"), ex.get("organization"),
                                   ex.get("category"), "Previous Year Questions",
                                   "official answer key") if w][:12],
            "a": BYLINE,
            "f": "",
        })
    corpus = [row for row in corpus if row["u"] not in ("", "/")]
    corpus.sort(key=lambda row: row["u"])
    payload = json.dumps({"version": 1, "count": len(corpus), "items": corpus},
                         ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(payload.encode("utf-8")) > 512 * 1024:
        warn(f"search index is {len(payload) // 1024}KB - trim BODY_LIMIT "
             f"or split the corpus")
    SEARCH_INDEX.write_text(payload, encoding="utf-8")
    info(f"search index: {len(corpus)} document(s) -> data/search-index.json")


def write_feed(items):
    """feed.xml - RSS 2.0 of the newest documents (item dates only)."""
    newest = sorted(items, key=lambda r: (r["published"], r["title"]),
                    reverse=True)[:FEED_LIMIT]
    body = []
    for r in newest:
        cats = (r.get("exams", []) + r.get("tags", []))[:5]
        body.append(
            "  <item>\n"
            f"    <title>{esc(r['title'])}</title>\n"
            f"    <link>{r['url']}</link>\n"
            f'    <guid isPermaLink="true">{r["url"]}</guid>\n'
            f"    <pubDate>{rfc822(r['published'])}</pubDate>\n"
            f"    <description>{esc(r['description'])}</description>\n"
            f"    <language>{'pa-in' if r['lang'] == 'pa' else 'en-in'}</language>"
            + "".join(f"\n    <category>{esc(c)}</category>" for c in cats)
            + "\n  </item>")
    build = (f"    <lastBuildDate>{rfc822(newest[0]['published'])}</lastBuildDate>\n"
             if newest else "")
    xml = (('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
            "<channel>\n"
            "  <title>House of Aspirants</title>\n"
            f"  <link>{DOMAIN}/</link>\n"
            "  <description>Study notes, current affairs, magazine issues, live "
            "sessions and recruitment updates for Punjab competitive exams - free "
            "in Punjabi and English.</description>\n"
            "  <language>en-in</language>\n"
            f'  <atom:link href="{DOMAIN}/feed.xml" rel="self" '
            'type="application/rss+xml"/>\n')
           + build + "\n".join(body) + "\n</channel>\n</rss>\n")
    FEED_PATH.write_text(xml, encoding="utf-8")
    info(f"rss feed: {len(newest)} item(s) -> feed.xml")


def archives_page(items, index, popularity):
    """archives.html - latest, popular, and every subject / exam / month index.

    This is the content index readers and crawlers both use: one page that
    lists every published document exactly once per axis, generated from the
    manifest so it can never drift from what exists.
    """
    url = f"{DOMAIN}/archives"
    crumbs = {"id": f"{url}#breadcrumb",
              "items": [("Home", f"{DOMAIN}/"), ("Archives", url)]}
    # An empty archive is a plain WebPage; a populated one is a CollectionPage
    # whose mainEntity is the real, walkable ItemList of what it indexes.
    latest = items[:10]
    page_node = webpage_node(url, ARCHIVES_TITLE, ARCHIVES_DESC,
                             f"{url}#breadcrumb",
                             "CollectionPage" if items else "WebPage")
    nodes = [page_node, breadcrumb_node(crumbs)]
    if items:
        nodes.insert(1, {
            "@type": "ItemList",
            "@id": f"{url}#list",
            "name": "Latest documents in the House of Aspirants archive",
            "numberOfItems": len(latest),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": r["title"],
                 "item": r["url"]}
                for i, r in enumerate(latest)
            ],
        })
        page_node["mainEntity"] = {"@id": f"{url}#list"}
    jsonld = graph(nodes)

    def label(r):
        return NAV_ENTRY.get(r["collection"], ("Article", ""))[0]

    def card(r):
        return (f'<a class="card card-pad reveal" href="{esc(r["file"])}"'
                + (' lang="pa"' if r["lang"] == "pa" else "") + ">"
                f'<span class="eyebrow">{esc(label(r))}</span>'
                f"<h3>{esc(r['title'])}</h3>"
                f'<p class="muted">{esc(r["description"])}</p>'
                f'<p class="ilink">Published {esc(fmt_date(r["published"]))} '
                f"→</p></a>")

    def row(r):
        return (f'<li><a href="{esc(r["file"])}">'
                f'<time datetime="{esc(r["published"])}">'
                f"{esc(fmt_date(r['published']))}</time>"
                f'<span class="arch-title">{esc(r["title"])}</span>'
                f'<span class="arch-tag">{esc(label(r))}</span></a></li>')

    def group(heading, sub, rows, grid=False, link=""):
        if not rows:
            return ""
        inner = (f'<div class="grid grid-3">{"".join(card(r) for r in rows)}</div>'
                 if grid else
                 f'<ul class="arch-list">{"".join(row(r) for r in rows)}</ul>')
        return (f'<section class="section" style="padding-top:0">'
                f'<div class="container"><div class="section-head reveal"><div>'
                f'<span class="eyebrow">{esc(sub)}</span>'
                f"<h2>{esc(heading)}{link}</h2></div></div>{inner}</div></section>")

    # popularity keys are written by analysts, so accept absolute, root-relative
    # and extensionless spellings of the same page.
    pop_keys = {}
    for k, v in popularity.items():
        key = str(k).replace(DOMAIN, "").strip("/")
        pop_keys[key[:-5] if key.endswith(".html") else key] = v

    def views(r):
        return pop_keys.get(r["url"].replace(DOMAIN, "").strip("/"))

    sections = []
    if not items:
        sections.append("""<section class="section" style="padding-top:0">
        <div class="container">
          <div class="section-head reveal"><div>
            <span class="eyebrow">Archive</span>
            <h2>Nothing archived yet</h2>
          </div></div>
          <div class="empty-state">
            <span class="es-icon" aria-hidden="true">🗂️</span>
            <h3>Ready to read right now</h3>
            <p>Documents appear here the moment they are published. The study
               guides, daily quiz and mock tests are ready right now.</p>
            <p class="btn-row" style="justify-content:center">
              <a class="btn btn-soft" href="articles.html">Browse study guides</a>
            </p>
          </div>
        </div></section>""")
    else:
        sections.append(group("Latest posts", "Newest first",
                              items[:10], grid=True))
        popular = sorted(
            ((views(r), r) for r in items if views(r)),
            key=lambda p: (-p[0], p[1]["published"]))
        popular = [r for _, r in popular[:6]]
        if popular:
            sections.append(group("Popular posts", "Most read", popular,
                                  grid=True))
        by_subject = []
        for s in index.get("subjects", []):
            rows = [r for r in items if s["id"] in r["subjects"]]
            if rows:
                by_subject.append((s["name"], f"{len(rows)} item(s)", rows,
                                   f'<a class="arch-more" '
                                   f'href="subject.html?subject={s["id"]}">'
                                   f'Practise →</a>'))
        for heading, sub, rows, link in by_subject:
            sections.append(group(heading, "By subject", rows, link=link))
        exams = {}
        for r in items:
            for e in r["exams"]:
                exams.setdefault(str(e), []).append(r)
        for e in sorted(exams):
            sections.append(group(e, "By exam", exams[e]))
        months = {}
        for r in items:
            months.setdefault(r["published"][:7], []).append(r)
        for ym in sorted(months, reverse=True):
            sections.append(group(month_label(ym), "By month", months[ym]))

    # Taxonomy: one link per tag / category that has a page of its own. These
    # are the outbound half of the relationship - the tag page links back to
    # here - so nothing that exists is ever only reachable from the footer.
    for heading, key, plural in (("Browse by tag", "tag", "tags"),
                                 ("Browse by category", "category", "categories")):
        facets = sorted(TAXONOMY[key].items(), key=lambda kv: kv[1].lower())
        if not facets:
            continue
        chips = "".join(
            f'<a class="badge badge-muted" '
            f'href="archive-{key}-{esc(slug)}.html">{esc(lab)} →</a>'
            for slug, lab in facets)
        sections.append(
            f'<section class="section" style="padding-top:0">'
            f'<div class="container"><div class="section-head reveal"><div>'
            f'<span class="eyebrow">Taxonomy</span>'
            f"<h2>{esc(heading)}</h2>"
            f"<p>Every {plural} with a published document opens its own page, "
            f"kept in step with this archive by the build.</p>"
            f'</div></div><div class="doc-badges">{chips}</div>'
            f'</div></section>')

    html = head(ARCHIVES_TITLE, ARCHIVES_DESC, ARCHIVES_KEYWORDS, url,
                "website", jsonld)
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">
          <a href="index.html">Home</a><span>/</span><span>Archives</span>
        </nav>
        <span class="eyebrow">Browse by subject, exam and month</span>
        <h1>{esc(ARCHIVES_TITLE.split(" | ")[0])}</h1>
        <div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{esc(ARCHIVES_DESC)}</p>
        </div>
        <p class="muted">{len(items)} published document(s) - newest first, in
          Punjabi and English.</p>
      </div>
    </section>
{"".join(sections)}
  </main>
"""
    html = enforce_link_floor(html, "archives", ARCHIVES_FILE)
    html += TAIL
    return html


def _quiz_titles(index, landing):
    """Landing path -> topic name, for the homepage's 'Trending quiz' card."""
    titles = {}
    for subj in index.get("subjects", []):
        for topic in subj.get("topics", []):
            path = landing.get((subj["id"], topic.get("id")))
            if path and topic.get("name"):
                key = str(path).lstrip("/")
                titles[key[:-5] if key.endswith(".html") else key] = topic["name"]
    return titles


def home_engine_html(records, popularity, quiz_titles):
    """Homepage 'Popular notes' + 'Trending quiz', measured only.

    Both cards read data/popularity.json, which ships empty - so this returns
    '' until real analytics numbers exist. Nothing popular is ever claimed
    without a count someone can check.
    """
    pop = {}
    for k, v in (popularity or {}).items():
        key = str(k).replace(DOMAIN, "").strip("/")
        pop[key[:-5] if key.endswith(".html") else key] = v

    def views_for(r):
        return pop.get(r["url"].replace(DOMAIN, "").strip("/"))

    cards = []
    for views, r in sorted(((v, r) for r in records if views_for(r)),
                           key=lambda p: (-p[0], p[1]["file"]))[:3]:
        cards.append(
            f'<a class="card card-pad reveal" href="{esc(r["file"])}">'
            f'<span class="eyebrow">Popular note · {views} reads</span>'
            f'<h3>{esc(r["title"])}</h3>'
            f'<p class="ilink">{r["readingMinutes"]} min read →</p></a>')

    for views, path in sorted(((v, k) for k, v in pop.items()
                               if (quiz_titles or {}).get(k)),
                              key=lambda p: (-p[0], p[1]))[:2]:
        href = path if path.endswith((".html", "/")) or "?" in path \
            else path + ".html"
        cards.append(
            f'<a class="card card-pad reveal" href="{esc(href)}">'
            f'<span class="eyebrow">Trending quiz · {views} attempts</span>'
            f'<h3>{esc(quiz_titles[path])}</h3>'
            f'<p class="ilink">Attempt the set →</p></a>')

    return "".join(cards)


def home_engine_data(records):
    """Candidates for the personalised blocks, embedded so the homepage never
    pays for a second request. home.js scores them with the same facets the
    builder uses and only renders them for a reader who actually has a signal
    (a practised subject or a bookmarked one)."""
    rows = []
    for r in records:
        if r.get("lang") != "en" or not r.get("file"):
            continue
        rows.append({"u": r["file"], "t": r["title"],
                     "c": r.get("collection", ""),
                     "s": r.get("subjects") or [], "e": r.get("exams") or [],
                     "m": r.get("readingMinutes", 1),
                     "d": r.get("difficulty") or ""})
        if len(rows) >= 80:
            break
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def page_main(html):
    """The <main> of a rendered page - what the content graph measures."""
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.S)
    return m.group(1) if m else ""


def guess_node_type(path, hub_files, guide_urls):
    if path in hub_files:
        return "hub"
    if path in guide_urls:
        return "guide"
    if path.startswith("exam-"):
        return "exam-hub"
    if path.startswith("subject-"):
        return "subject-hub"
    if path.startswith(("topic-", "cluster-", "category-", "punjab-",
                        "articles", "index")):
        return "landing"
    if path.startswith("quiz"):
        return "quiz"
    if path.startswith(GEN_PREFIXES):
        return "document"
    return "page"


def write_content_graph(ctx, index, exams, articles, landing_pages, records):
    """data/content-graph.json - nodes, contextual edges, silos.

    Edges are read back out of the HTML that actually shipped, so the graph
    can never describe a link the site does not serve.
    """
    hub_files = {h["file"] for h in HUBS.values()}
    guide_urls = {str(a.get("url", "")).lstrip("/") for a in (articles or [])}
    known_rel = {}
    for src, target, rel in ctx.get("edges", []):
        t = target.split("#", 1)[0].split("?", 1)[0]
        if t:
            known_rel[(node_id(src), node_id(t))] = rel

    # Pass 1: every page we published, with its real metadata. Pass 2: only
    # then the targets those pages link to, so a hub keeps its own title even
    # when something else linked to it first.
    nodes = {}
    for file, _main, node in ctx["pages"]:
        nodes[node_id(file)] = node

    edge_rel = {}
    for file, main, _node in ctx["pages"]:
        src = node_id(file)
        for href in sorted(link_floor(main)):
            target = href.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            tid = node_id(target)
            if tid not in nodes:
                nodes[tid] = {
                    "id": tid, "url": "/" + tid,
                    "type": guess_node_type(tid, hub_files, guide_urls),
                    "template": "", "title": "", "lang": "en",
                    "subjects": [], "exams": [], "tags": [], "hub": "",
                }
            edge_rel.setdefault((src, tid), known_rel.get((src, tid),
                                                          "contextual"))

    edges = [make_edge(s, t, rel) for (s, t), rel in edge_rel.items()]
    silos = build_silos(index, articles, exams, landing_pages, records)
    doc = build_graph(list(nodes.values()), edges, silos)
    GRAPH.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    c = doc["counts"]
    info(f"content graph: {c['nodes']} nodes, {c['edges']} contextual links, "
         f"{c['silos']} silos ({c['pillars']} pillars, {c['clusters']} clusters)"
         f" -> data/content-graph.json")


def patch_index(items_by_kind, index, popularity=None, records=None,
                quiz_titles=None):
    path = ROOT / "index.html"
    src = path.read_text(encoding="utf-8")
    out = src
    for kind in FEED_BLOCKS:
        start = f"<!-- HOA-FEED:{kind} -->"
        end = f"<!-- /HOA-FEED:{kind} -->"
        if start not in out or end not in out:
            err(f"index.html: feed marker {start!r} missing - restore it before "
                f"running the content build")
            return
        pre, rest = out.split(start, 1)
        _, post = rest.split(end, 1)
        body = feed_html(kind, items_by_kind.get(kind, []), index)
        out = pre + start + ("\n" + body + "\n" if body else "") + end + post

    # ---- Phase 3: the homepage engine ------------------------------------
    # `popular` is measured (data/popularity.json) and rendered here; the
    # personalised half is filled by home.js from the reader's own progress,
    # so the section only shows what is really there.
    popular_body = home_engine_html(records or [], popularity or {},
                                    quiz_titles or {})
    for marker, body in (("popular", popular_body),
                         ("data", home_engine_data(records or []))):
        start, end = f"<!-- HOA-HOME:{marker} -->", f"<!-- /HOA-HOME:{marker} -->"
        if start not in out or end not in out:
            err(f"index.html: engine marker {start!r} missing - restore it "
                f"before running the content build")
            return
        pre, rest = out.split(start, 1)
        _, post = rest.split(end, 1)
        out = pre + start + body + end + post
    if popular_body:
        out = out.replace('<section class="section section-alt" id="foryou" hidden>',
                          '<section class="section section-alt" id="foryou">')

    if out != src:
        path.write_text(out, encoding="utf-8")
        info("index.html: homepage feed + engine blocks refreshed")


# =============================================================================
# 9. MAIN
# =============================================================================
def fit_description(text):
    """Keep a generated description inside the site's 140-160 character
    window: trim whole words at the end, then pad with whole words."""
    words, out = str(text).split(), []
    for w in words:
        cand = " ".join(out + [w])
        if len(cand) > 160:
            break
        out.append(w)
    desc = " ".join(out)
    for w in ("Free", "to", "read", "in", "Punjabi", "and", "English,", "with",
              "reading", "time", "and", "exam", "tags."):
        cand = f"{desc} {w}"
        if len(cand) > 160:
            break
        desc = cand
        if len(desc) >= 140:
            break
    return desc


def _abs_url(href):
    h = str(href)
    if h.startswith(("http://", "https://")):
        return h
    h = h.lstrip("/")
    if h.endswith(".html"):
        h = h[:-5]
    return f"{DOMAIN}/{h}"


def index_shell(coll, file, title, desc, keywords, url, crumb_label, parents,
                eyebrow, h1, answer, body_html, kind="WebPage",
                main_entity=None, extra_nodes=(), lang="en"):
    """Shared shell for every generated index page (author profiles, tag and
    category archives, search): the same breadcrumb, hero, schema contract,
    link floor and chrome every other page in this builder ships with."""
    crumbs = [("Home", f"{DOMAIN}/")]
    ld_crumb = crumbs + [(lbl, _abs_url(href))
                         for lbl, href in parents] + [(crumb_label, url)]
    nodes = [webpage_node(url, title, desc, f"{url}#breadcrumb", kind),
             breadcrumb_node({"id": f"{url}#breadcrumb", "items": ld_crumb})]
    if main_entity:
        nodes[0]["mainEntity"] = main_entity
    nodes.extend(extra_nodes)

    vis = ['<a href="index.html">Home</a><span>/</span>']
    for lbl, href in parents:
        vis.append(f'<a href="{esc(href)}">{esc(lbl)}</a><span>/</span>')
    vis.append(f"<span>{esc(crumb_label)}</span>")

    html = head(title, desc, keywords, url, "website", graph(nodes), lang=lang)
    html += f"""  <main id="main">
    <section class="page-hero">
      <div class="container">
        <nav class="breadcrumb" aria-label="Breadcrumb">{"".join(vis)}</nav>
        <span class="eyebrow">{esc(eyebrow)}</span>
        <h1>{esc(h1)}</h1>
        <div class="answer-box">
          <span class="ab-label">Quick answer</span>
          <p>{esc(answer)}</p>
        </div>
      </div>
    </section>
{body_html}
  </main>
"""
    html = enforce_link_floor(html, coll, file)
    return html + TAIL


def doc_card(r, eyebrow):
    """One listing card shared by the generated index pages."""
    return (f'<a class="card card-pad reveal" href="{esc(r["file"])}"'
            + (' lang="pa"' if r["lang"] == "pa" else "") + ">"
            f'<span class="eyebrow">{esc(eyebrow)}</span>'
            f"<h3>{esc(r['title'])}</h3>"
            f'<p class="muted">{esc(r["description"])}</p>'
            f'<p class="ilink">{r["readingMinutes"]} min read →</p></a>')


def author_page_html(a, records):
    """author-<id>.html - the profile behind a byline (data/authors.json)."""
    f = author_profile_file(a)
    url = f"{DOMAIN}/{f[:-5]}"
    name = str(a["name"])
    role = str(a.get("role") or "Editor, House of Aspirants")
    bio = str(a.get("bio") or "")
    creds = [str(c) for c in (a.get("credentials") or [])]
    topics = [str(t) for t in (a.get("topics") or [])]
    mine = [r for r in records
            if (r.get("author_ref") or {}).get("id") == a["id"]]

    badges = "".join(f'<li>{esc(c)}</li>' for c in creds)
    topics_html = "".join(f'<li>{esc(t)}</li>' for t in topics)
    about = f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">About the author</span>
          <h2>{esc(name)}</h2>
          <p>{esc(bio)}</p>
        </div></div>
        <div class="grid grid-3">
          <div class="card card-pad"><span class="eyebrow">Credentials</span>
            <div class="prose"><ul>{badges}</ul></div></div>
          <div class="card card-pad"><span class="eyebrow">Writes about</span>
            <div class="prose"><ul>{topics_html}</ul></div></div>
          <div class="card card-pad"><span class="eyebrow">Published here</span>
            <div class="prose"><p>{len(mine)} document(s) carry this byline.
              Every one of them is reviewed against the official syllabus and
              the notification it cites.</p></div></div>
        </div>
      </div>
    </section>"""

    if mine:
        grid = "".join(doc_card(r, NAV_ENTRY.get(r["collection"],
                                                 ("Article", ""))[0])
                       for r in mine[:24])
        listing = f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Bylines</span>
          <h2>Written and reviewed by {esc(name)}</h2>
        </div></div>
        <div class="grid grid-3">{grid}</div>
      </div>
    </section>"""
    else:
        listing = """    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Bylines</span>
          <h2>Nothing published under this byline yet</h2>
        </div></div>
        <div class="empty-state">
          <span class="es-icon" aria-hidden="true">✍️</span>
          <h3>Documents appear here the moment they publish</h3>
          <p>Nothing carries this byline today, and no byline is ever added to
             a page that does not exist. The study guides, daily quiz and the
             archive are ready right now.</p>
          <p class="btn-row" style="justify-content:center">
            <a class="btn btn-soft" href="archives.html">Open the archive</a>
          </p>
        </div>
      </div>
    </section>"""

    person = {"@type": "Person", "@id": f"{url}#person", "name": name,
              "url": url, "jobTitle": role, "description": bio}
    if a.get("award"):
        person["award"] = str(a["award"])
    if a.get("sameAs"):
        person["sameAs"] = [str(x) for x in a["sameAs"]]
    if topics:
        person["knowsAbout"] = topics
    title = f"{name} | House of Aspirants"
    desc = fit_description(
        f"{name} - {role}. Credentials, topics covered and every document "
        f"written and reviewed under this byline on House of Aspirants.")
    return index_shell(
        "author", f, title, desc, f"{name} Punjab exam preparation", url,
        name, [], "Author profile", name, bio.split(". ")[0] + ".",
        about + listing, kind="ProfilePage", main_entity={"@id": f"{url}#person"},
        extra_nodes=[person])


def archive_index_html(kind, slug, label, records, index):
    """archive-tag-<slug>.html / archive-category-<slug>.html - one walkable
    page per tag and per content category that really has documents."""
    f = f"archive-{kind}-{slug}.html"
    url = f"{DOMAIN}/{f[:-5]}"
    noun = "tagged" if kind == "tag" else "categorised as"
    title = f"{label} | House of Aspirants"
    if len(title) > 60:
        title = f"{label[:52].rstrip()} | HOA"
    desc = fit_description(
        f"Every document {noun} {label} on House of Aspirants - study notes, "
        f"current affairs, magazine issues, quiz sets and preparation guides "
        f"for Punjab competitive exams, newest first.")
    facets = filter_facets(records, index)
    cards = "".join(doc_card(r, NAV_ENTRY.get(r["collection"],
                                              ("Article", ""))[0])
                    for r in records)
    body = (f"""    <section class="section" style="padding-top:0">
      <div class="container">
        <div class="section-head reveal"><div>
          <span class="eyebrow">Archive</span>
          <h2>{len(records)} document(s) - {esc(label)}</h2>
        </div></div>
        {filter_bar(facets)}
        <div class="grid grid-3" data-filter-list>{cards}</div>
      </div>
    </section>""")
    items_node = {
        "@type": "ItemList", "@id": f"{url}#list",
        "name": f"House of Aspirants {label}",
        "numberOfItems": len(records),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": r["title"],
             "item": r["url"]} for i, r in enumerate(records)],
    }
    return index_shell(
        "archives", f, title, desc, f"{label} Punjab exam notes, {label} study "
        f"material", url, label, [("Archives", ARCHIVES_FILE)],
        f"By {'tag' if kind == 'tag' else 'category'}", label,
        f"{len(records)} published document(s) {noun} {label}, newest first, "
        f"with reading time, difficulty and exam tags on each card.",
        body, kind="CollectionPage", main_entity={"@id": f"{url}#list"},
        extra_nodes=[items_node])


def search_page_html():
    """search.html - a crawlable search page over the same corpus the Ctrl+K
    overlay uses. The form works without JavaScript; content.js fills the
    results once it has the index (never on first paint)."""
    url = f"{DOMAIN}/search"
    title = "Search | House of Aspirants"
    desc = fit_description(
        "Search every study note, current affairs article, magazine issue, "
        "strategy, quiz set and guide on House of Aspirants - by title, "
        "subject, exam tag, keyword, category or author.")
    body = """    <section class="section" style="padding-top:0">
      <div class="container">
        <form class="search-page-form" role="search" action="search.html" method="get">
          <label class="sr-only" for="search-q">Search this site</label>
          <input type="search" id="search-q" name="q" autocomplete="off"
                 placeholder="Search notes, quizzes, subjects, authors…">
          <button class="btn btn-primary" type="submit">Search</button>
        </form>
        <div class="section-head reveal"><div>
          <span class="eyebrow">Results</span>
          <h2>Documents matching your search</h2>
        </div></div>
        <div id="search-results" data-search-results>
          <div class="empty-state">
            <span class="es-icon" aria-hidden="true">🔎</span>
            <h3>Type a word to search</h3>
            <p>Results come from every published document on this site - its
               title, summary, keywords, exam tags, subject, category, author
               and body.</p>
          </div>
        </div>
      </div>
    </section>"""
    return index_shell(
        "search", "search.html", title, desc,
        "search House of Aspirants, search Punjab exam notes", url,
        "Search", [], "Find anything on this site", "Search House of Aspirants",
        "Search every published document on this site by title, summary, "
        "keywords, exam tags, subject, category, author or body text.",
        body)


def phase4_pages(records, index):
    """Generate the Phase 4 index pages and return them for the caller to
    write: [(file, html, node), ...]. Archives and search always exist; tag
    and category archives appear only when a document really carries the tag.
    """
    out = []
    people = [a for a in load_authors() if author_profile_file(a)]
    for a in people:
        f = author_profile_file(a)
        html = author_page_html(a, records)
        out.append((f, html, {
            "id": f, "url": f"/{f}", "type": "author", "template": "",
            "title": str(a["name"]), "lang": "en", "subjects": [],
            "exams": [], "tags": [], "hub": "archives.html"}))

    groups = {}
    for r in records:
        if r.get("lang") != "en":
            continue                       # the Punjabi edition mirrors /pa/
        for t in r.get("tags") or []:
            groups.setdefault(("tag", _slug_facet(t)), str(t))
        if r.get("category"):
            groups.setdefault(("category", _slug_facet(r["category"])),
                              str(r["category"]))
    for (kind, slug), label in sorted(groups.items()):
        rows = [r for r in records if r.get("lang") == "en" and (
            any(_slug_facet(t) == slug for t in (r.get("tags") or []))
            if kind == "tag"
            else _slug_facet(r.get("category") or "") == slug)]
        if not rows:
            continue
        f = f"archive-{kind}-{slug}.html"
        if len(rows) < ARCHIVE_MIN_DOCS:
            # one or two documents = a thin list that only repeats links the
            # documents' own hubs already carry: crawlable, kept out of the
            # index (and the sitemap) until the tag grows
            NOINDEX_URLS.add(f"{DOMAIN}/{f[:-5]}")
        html = archive_index_html(kind, slug, label, rows, index)
        out.append((f, html, {
            "id": f, "url": f"/{f}", "type": "archive", "template": "",
            "title": label, "lang": "en", "subjects": [], "exams": [],
            "tags": [slug] if kind == "tag" else [],
            "hub": ARCHIVES_FILE}))

    f = "search.html"
    out.append((f, search_page_html(), {
        "id": f, "url": f"/{f}", "type": "page", "template": "",
        "title": "Search", "lang": "en", "subjects": [], "exams": [],
        "tags": [], "hub": "archives.html"}))
    return out

def main():
    strict = "--strict" in sys.argv
    index = load_index()
    landing = load_quiz_landing()
    exams = []
    try:
        exams = json.loads((ROOT / "data" / "exams.json").read_text(encoding="utf-8")) \
            .get("exams", [])
    except Exception as e:
        err(f"data/exams.json unreadable: {e}")

    # Hub metadata is permanent copy, so it is held to the same contract as
    # every document: a unique title of at most 60 characters and a meta
    # description inside the site's 140-160 character window.
    for _coll, _hub in HUBS.items():
        if len(_hub["title"]) > 60:
            err(f"hub {_coll}: title is {len(_hub['title'])} chars (max 60)")
        if not (140 <= len(_hub["description"]) <= 160):
            err(f"hub {_coll}: description is {len(_hub['description'])} chars "
                f"(want 140-160)")
    if len(ARCHIVES_TITLE) > 60:
        err(f"archives: title is {len(ARCHIVES_TITLE)} chars (max 60)")
    if not (140 <= len(ARCHIVES_DESC) <= 160):
        err(f"archives: description is {len(ARCHIVES_DESC)} chars (want 140-160)")

    # Engine <-> builder parity: every template publishes into a collection
    # that exists, and every field a template calls required is enforced by
    # that collection's own contract (not merely suggested by the scaffold).
    for _key, _tpl in TEMPLATES.items():
        if _tpl["collection"] not in HUBS:
            err(f"template {_key}: unknown collection {_tpl['collection']!r}")
            continue
        for _field in _tpl["required"]:
            if _field not in REQUIRED_FIELDS.get(_tpl["collection"], []):
                err(f"template {_key}: requires {_field!r} but content/"
                    f"{_tpl['collection']}/ does not enforce it")
    for _coll in NAV_ORDER:
        if _coll not in HUBS or _coll not in NAV_ENTRY:
            err(f"navigation: {_coll!r} has no hub or no label")

    global RECRUITMENT, CHAIN_TARGETS
    RECRUITMENT = []
    CHAIN_TARGETS = {}

    all_records = {c: [] for c in HUBS}
    punjabi = {c: [] for c in HUBS}
    drafts = 0
    pdf_old = load_pdf_sidecar()["files"]
    pdf_files = {}                 # rebuilt from the PDFs that publish this run
    pdf_drops = 0

    for coll, cfg in HUBS.items():
        cdir = CONTENT / cfg["dir"]
        if not cdir.exists():
            continue
        # Study material lives one level deeper - content/study-material/
        # <subject>/<file> - and takes Markdown and JSON as well as the PDFs
        # the scanner owns. Every other collection keeps its flat *.md layout.
        study = (coll == STUDY_DIR)
        taken = {r["slug"] for r in all_records[coll]}
        for path in (study_paths() if study else sorted(cdir.glob("*.md"))):
            if path.name in ("README.md",):
                continue
            name = path.name
            if study:
                subject = study_locator(path)[0] or path.parent.name
                is_pa = False   # language is a display field, not a URL, here
                # Any name is a valid name here. "Chapter 1 Notes.md" gets the
                # same transliteration and hyphenation a PDF gets, so a file
                # nobody styled still publishes instead of failing a naming
                # rule they were never told about.
                slug = pdf_slug_from_name(path.stem) or ""
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug or " "):
                    err(f"content/{cfg['dir']}/{subject}/{name}: no slug could "
                        f"be derived from this file name")
                    continue
                base, n = slug, 1
                while slug in taken:
                    n += 1
                    slug = f"{base}-{n}"      # deterministic, never a build error
                taken.add(slug)
                meta, body = study_document(path, subject)
                rec = build_record(coll, cfg, slug, path, index, "en",
                                   meta=meta, body=body)
            else:
                is_pa = name.endswith(".pa.md")
                slug = name[:-6] if is_pa else name[:-3]
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
                    err(f"content/{cfg['dir']}/{name}: filename must be lowercase "
                        f"letters, digits and hyphens only")
                    continue
                if is_pa:
                    if not (cdir / f"{slug}.md").exists():
                        err(f"content/{cfg['dir']}/{name}: Punjabi variant without an "
                            f"English original ({slug}.md)")
                        continue
                rec = build_record(coll, cfg, slug, path, index,
                                   "pa" if is_pa else "en")
            if rec is None:
                continue
            if rec.get("draft"):
                drafts += 1                 # validated, never published
                continue
            (punjabi if (not study and is_pa) else all_records)[coll].append(rec)

    # --- PDF drops: data/content-manifest.json is the scanner's view ---------
    # scripts/build_content_manifest.ts walks content/**, derives every file's
    # metadata from its name and writes `drops`; this builder publishes from
    # that list. Drop -> manifest -> page, and nothing in between is manual.
    drops = load_drops()
    dir_coll = {cfg["dir"]: coll for coll, cfg in HUBS.items()}
    drops_by_coll = {c: [] for c in HUBS}
    for drop in drops:
        folder_name = str(drop.get("folder") or "")
        coll = dir_coll.get(folder_name)
        if coll is None:
            err(f"{drop.get('path')}: content/{folder_name}/ is not a "
                f"registered collection - add it to HUBS in "
                f"scripts/build_content.py before dropping files there")
            continue
        drops_by_coll[coll].append(drop)

    # ---- Previous Year Questions: one folder per exam ----------------------
    # content/previous-year-questions/<exam>/ is the collection's authoring
    # surface: metadata.json describes the exam, overview.en.md / overview.pa.md
    # write it up, and YYYY-question-paper.pdf + YYYY-official-answer-key.pdf
    # are paired by year into the table the exam page renders. Built before the
    # validation gate below so a broken sidecar fails with nothing half-written
    # on disk; the pages are rendered from this object later in main().
    pyq_manifest = pyq_collection.build(drops, err, warn, info)
    pyq_exams = pyq_manifest.get("exams", [])
    claimed = {d.get("path") for d in drops if pyq_collection.claims(d)}

    for coll, cfg in HUBS.items():
        # A PDF alone is enough: the file name gives the document its title,
        # slug, description, date and download URL, and the record below lands
        # in exactly the same pipeline a Markdown document does.
        taken = {r["slug"] for r in all_records[coll]}
        # Subfolders publish too: `content/history/chapter 1/part 1.pdf` is a
        # drop like any other - only hidden folders and `_drafts` are skipped.
        for drop in drops_by_coll[coll]:
            path = ROOT / str(drop.get("path") or "")
            if not path.is_file():
                err(f"{drop.get('path')}: listed in data/content-manifest.json "
                    f"but missing from disk - run node "
                    f"scripts/build_content_manifest.ts")
                continue
            if not check_drop(drop, path, cfg):
                continue
            where = str(path.relative_to(ROOT))
            # Previous Year Questions: a file named YYYY-question-paper.pdf or
            # YYYY-official-answer-key.pdf inside an exam folder is published
            # as a download inside that exam page's table, so it never earns a
            # page of its own. `drops` still carries it (pyq.html's paper grid
            # and the inventory gate read that list unchanged); only the
            # per-document page is skipped, because the table is its page.
            if str(drop.get("path") or "") in claimed:
                info(f"{where}: published as a download on its exam page")
                continue
            folder = str(drop.get("category") or "")
            slug = pdf_slug_from_name(path.stem)
            # `Quant Shortcuts.pdf` next to `quant-shortcuts.md` is that
            # document's download, not a second page: one file, one URL.
            host = next((r for r in all_records[coll]
                         if not r.get("pdfDrop") and r.get("slug") == slug), None)
            if host is not None:
                if not host.get("pdf"):
                    host["pdf"] = host["meta"]["pdf"] = where
                    info(f"{where}: attached to {host['file']} as its download")
                else:
                    info(f"{where}: not published - {host['file']} already "
                         f"links a download of its own")
                continue
            slug = slug or "pdf"
            base, n = slug, 1
            while slug in taken:
                n += 1
                slug = f"{base}-{n}"        # deterministic, never a build error
            taken.add(slug)
            fname_date = pdf_date_from_name(path.stem)
            published, updated = remember_pdf_dates(path, pdf_old, pdf_files,
                                                    fname_date)
            if (str(drop.get("published") or "") != published
                    or str(drop.get("modified") or "") != updated):
                err(f"{where}: content manifest dates "
                    f"{drop.get('published')!r}/{drop.get('modified')!r} but "
                    f"the sidecar stamped {published!r}/{updated!r} - run node "
                    f"scripts/build_content_manifest.ts")
                continue
            rec = build_pdf_record(
                coll, cfg, path, slug, published, updated, fname_date, index,
                folder, drop,
                study_overrides(path) if coll == STUDY_DIR
                else None)
            if rec is None:
                continue
            all_records[coll].append(rec)
            pdf_drops += 1

    # Validate EVERYTHING before a single byte is written: a broken file fails
    # the build with nothing half-written on disk.
    if errors:
        for e in errors:
            print(f"  \u274c {e}")
        print(f"\n\u274c content build FAILED with {len(errors)} error(s) - "
              f"no files were written.")
        return 1

    # A generated title is made unique before anything renders from it.
    # The shelf's own fields - subject, language, size, badges, the one string
    # the shelf searches - are stamped once, from the path and the sidecar, so
    # the hub page, the Study renderer and the search index can never disagree
    # about what a file is.
    stamp_study_fields(all_records[STUDY_DIR])
    dedupe_pdf_titles(all_records)
    link_related_pdfs(all_records, punjabi)
    # Part order and the chapters beside them: derived from the records above,
    # so a part page always knows what comes next and which chapter to read
    # after this one.
    study_nav(all_records[STUDY_DIR])
    if pdf_drops:
        info(f"pdf drops: {pdf_drops} PDF(s) published from their file names")
    # One stamp per PDF that still exists. A file this run did not publish - a
    # download attached to a host page, or a folder that is not a registered
    # collection - keeps its date instead of being dropped, because the scanner
    # stamps every file on disk and the two views must not fight each other.
    for rel, entry in pdf_old.items():
        if rel not in pdf_files and (ROOT / rel).is_file():
            pdf_files[rel] = entry
    if pdf_files != pdf_old:
        PDF_META.write_text(
            json.dumps({"version": 1,
                        "files": {k: pdf_files[k] for k in sorted(pdf_files)}},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        info(f"pdf dates: {len(pdf_files)} file(s) recorded in "
             f"data/pdf-meta.json")

    # deterministic order: newest first, then title
    for coll in all_records:
        if coll == STUDY_DIR:
            # STEP 7 has its own answer - Featured -> Newest -> Alphabetical -
            # computed once here so the hub page, the sitemap, the search rows
            # and the Study renderer all read the same first card. The general
            # rule below would flatten it straight back out.
            all_records[coll].sort(key=study_sort_key)
        else:
            all_records[coll].sort(key=lambda r: (r["published"], r["title"]),
                                   reverse=True)
        punjabi[coll].sort(key=lambda r: (r["published"], r["title"]), reverse=True)
    if drafts:
        info(f"{drafts} draft document(s) validated but not published")

    RECRUITMENT = all_records["recruitment"]
    # Which tag / category archive pages will exist - decided before the first
    # document renders so badges and archives can never disagree.
    build_taxonomy(all_records)
    # Learning-path targets are the newest real page in each chain collection.
    CHAIN_TARGETS = {c: all_records[c][0] for c in
                     ("current-affairs", "magazine", "strategy",
                      "expected-mcqs", "previous-year-questions")
                     if all_records.get(c)}

    # ---- Current Affairs: one section, one home --------------------------
    # content/current-affairs/<language>/<Month YYYY>/ decides which language
    # and which month page exists, so the whole /current-affairs/... tree is
    # decided here, before the first byte is written, and can never disagree
    # with what the hub links to below.
    ca_section = current_affairs.build(
        all_records["current-affairs"], drops, study_lang, warn, info)

    expected = set()
    manifest_items = []
    rendered = []
    # Recommendation context shared by every page: the pools the engine ranks
    # over, the edges it emitted, and each rendered <main> for the graph.
    ctx = {
        "index": index,
        "pools": {c: all_records[c] + punjabi[c] for c in HUBS},
        "edges": [],
        "pages": [],
    }

    # ---- item pages -------------------------------------------------------
    for coll, cfg in HUBS.items():
        if not cfg["prefix"]:
            continue
        pool = all_records[coll]
        for rec in pool + punjabi[coll]:
            html_out, _ = render_item(rec, cfg, pool if rec["lang"] == "en"
                                      else punjabi[coll], index, landing, ctx)
            out_path = ROOT / rec["file"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html_out, encoding="utf-8")
            expected.add(rec["file"])
            rendered.append(rec)
            ctx["pages"].append((rec["file"], page_main(html_out),
                                 make_node(rec, HUBS[coll]["file"])))
            manifest_items.append({k: rec[k] for k in
                                   ("collection", "file", "url", "title",
                                    "description", "published", "updated",
                                    "subjects", "tags", "exams",
                                    "readingMinutes", "lang", "featured")
                                   if k in rec} | {
                "path": rec["path"],
                "category": str(rec.get("category") or ""),
                # Study material carries the shelf's own fields (STEP 6/7/9):
                # subject, language, file size, badges and the haystack the
                # Study renderer searches. Scalars only - the page itself is
                # the long form, the manifest stays a listing.
                **({k: rec[k] for k in ("language", "subjectName",
                                        "studySubject", "studyLanguage",
                                        "studyLanguageName", "studyChapter",
                                        "studyChapterName", "studyPart",
                                        "studyParts", "size", "sizeLabel",
                                        "type", "source", "badges", "search")
                    if k in rec}),
                **({"author": str(rec["author"])} if rec.get("author") else {}),
                **({"reviewedBy": str(rec["reviewedBy"])} if rec.get("reviewedBy") else {}),
                **({"difficulty": str(rec["difficulty"])} if rec.get("difficulty") else {}),
                **({"month": str(rec["month"])} if rec.get("month") else {}),
                **({"date": str(rec["date"])} if rec.get("date") else {}),
                **({"status": str(rec["status"])} if rec.get("status") else {}),
                **({"post": str(rec["post"])} if rec.get("post") else {}),
                **({"official_url": str(rec["official_url"])} if rec.get("official_url") else {}),
                **({"pdf": str(rec["pdf"])} if rec.get("pdf") else {}),
            })
        info(f"{coll}: {len(pool)} english + {len(punjabi[coll])} punjabi page(s)")

    # Language pairs: /slug and /pa/slug point at each other in hreflang, the
    # language switch badge and the search corpus.
    pairs = {}
    for m in manifest_items:
        pairs.setdefault((m["collection"], m["file"].split("/")[-1][:-5]),
                         {})[m["lang"]] = m
    for m in manifest_items:
        other = pairs[(m["collection"], m["file"].split("/")[-1][:-5])]
        if len(other) == 2:
            alt = other["pa" if m["lang"] == "en" else "en"]
            m["alt"] = {"lang": alt["lang"], "file": alt["file"],
                        "url": alt["url"]}

    # ---- hubs -------------------------------------------------------------
    hubs_out = []
    for coll, cfg in HUBS.items():
        pool = all_records[coll] + punjabi[coll]
        html_out, live = hub_page(coll, cfg, pool, index, exams, pyq_exams,
                                  ca_section)
        (ROOT / cfg["file"]).write_text(html_out, encoding="utf-8")
        expected.add(cfg["file"])
        ctx["pages"].append((cfg["file"], page_main(html_out), {
            "id": cfg["file"], "url": f'/{cfg["file"]}', "type": "hub",
            "template": "", "title": cfg["title"], "lang": "en",
            "subjects": [], "exams": [], "tags": [], "hub": cfg["file"],
        }))
        hubs_out.append({
            "collection": coll,
            "file": cfg["file"],
            "url": f'{DOMAIN}/{cfg["file"][:-5]}',
            "title": HUBS[coll]["title"],
            "description": HUBS[coll]["description"],
            "count": len(live),
        })
        info(f"hub {cfg['file']}: {len(live)} item(s)")

    # ---- pdf registry -----------------------------------------------------
    pdf_url = f'{DOMAIN}/{HUBS["pdfs"]["file"][:-5]}'
    pdfs = [{
        "title": r["title"],
        "description": r["description"],
        "path": str(r["meta"].get("file", "")),
        "subjects": r["subjects"],
        "exams": r["exams"],
        "lang": r["lang"],
        "url": pdf_url,
    } for r in all_records["pdfs"] + punjabi["pdfs"]]

    # ---- stale output removal (runs LAST, after every writer above has
    # registered what it generated - see the end of this function) ----------

    # ---- homepage feed + engine ------------------------------------------
    popularity = load_popularity()
    feed_items = {
        "notes": all_records["notes"] + punjabi["notes"],
        "current-affairs": (all_records["current-affairs"] +
                            punjabi["current-affairs"] +
                            all_records["notes"] + punjabi["notes"]),
        "magazine": all_records["magazine"] + punjabi["magazine"],
        "sessions": all_records["sessions"] + punjabi["sessions"],
        "recruitment": all_records["recruitment"] + punjabi["recruitment"],
    }
    patch_index(feed_items, index, popularity=popularity, records=rendered,
                quiz_titles=_quiz_titles(index, landing))

    # ---- navigation -------------------------------------------------------
    patch_core_nav()

    # ---- Phase 2 artefacts ------------------------------------------------
    write_search_index(rendered, index, pyq_exams)
    write_feed(rendered)
    arch_html = archives_page(rendered, index, popularity)
    (ROOT / ARCHIVES_FILE).write_text(arch_html, encoding="utf-8")
    expected.add(ARCHIVES_FILE)
    ctx["pages"].append((ARCHIVES_FILE, page_main(arch_html), {
        "id": ARCHIVES_FILE, "url": f"/{ARCHIVES_FILE}", "type": "page",
        "template": "", "title": ARCHIVES_TITLE, "lang": "en",
        "subjects": [], "exams": [], "tags": [], "hub": ARCHIVES_FILE,
    }))
    info(f"archives: {len(rendered)} document(s) indexed on {ARCHIVES_FILE}")

    # ---- Phase 4: generated index pages -----------------------------------
    # Author profiles (data/authors.json), one archive page per tag and per
    # content category that exists, and the crawlable search page. Every one
    # of them is registered in the manifest, so the sitemap, the SEO gate and
    # the link floor all pick them up in the same run.
    phase4_manifest = []
    for _f, _html, _node in phase4_pages(rendered, index):
        (ROOT / _f).write_text(_html, encoding="utf-8")
        expected.add(_f)
        ctx["pages"].append((_f, page_main(_html), _node))
        _t = re.search(r"<title>(.*?)</title>", _html, re.S)
        _d = re.search(r'<meta name="description" content="(.*?)">', _html, re.S)
        phase4_manifest.append({
            "file": _f,
            "url": f"{DOMAIN}/{_f[:-5]}",
            "title": (_t.group(1) if _t else ""),
            "description": (_d.group(1) if _d else ""),
            **({"noindex": True} if f"{DOMAIN}/{_f[:-5]}" in NOINDEX_URLS else {}),
        })
    info(f"index pages: {len(phase4_manifest)} generated "
         f"(authors, tags, categories, search)")

    # ---- Previous Year Questions exam pages -------------------------------
    # One page per exam folder, written into its own directory so the URL is
    # /pyq/<slug> in production (cleanUrls in vercel.json). Each one is
    # registered in the manifest like every other generated index page, so the
    # sitemap, the SEO gate and the search corpus all pick it up in this run -
    # and each carries the same "generated, do not edit" marker as the rest.
    pyq_page_entries = []
    for _exam in pyq_exams:
        _html = pyq_exam_page(_exam)
        _path = ROOT / _exam["file"]
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(_html, encoding="utf-8")
        expected.add(_exam["file"])
        pyq_page_entries.append({
            "file": _exam["file"],
            "url": _exam["url"],
            "title": _exam["title"],
            "description": _exam["description"],
        })
        ctx["pages"].append((_exam["file"], page_main(_html), {
            "id": _exam["file"], "url": f'/{_exam["file"]}', "type": "page",
            "template": "", "title": _exam["title"], "lang": "en",
            "subjects": [], "exams": [_exam["title"]], "tags": [],
            "hub": _exam["hub"],
        }))
    if pyq_page_entries:
        info(f"pyq pages: {len(pyq_page_entries)} exam page(s) written under "
             f"pyq/")

    # ---- Current Affairs section pages ------------------------------------
    # One page per language and one per month, written into their own
    # directories so the URLs are /current-affairs/<language> and
    # /current-affairs/<language>/<month> in production (cleanUrls in
    # vercel.json). Registered in the manifest like every other generated index
    # page, so the sitemap, the SEO gate and the reachability rule above all
    # pick them up in this run - and each carries the same "generated, do not
    # edit" marker as the rest.
    ca_page_entries = []
    for _page in ca_section.get("pages", []):
        _html = ca_section_page({**_page, "index": index,
                                 "all_languages": ca_section.get("languages", [])})
        _path = ROOT / _page["file"]
        _path.parent.mkdir(parents=True, exist_ok=True)
        _path.write_text(_html, encoding="utf-8")
        expected.add(_page["file"])
        ca_page_entries.append({
            "file": _page["file"],
            "url": _page["url"],
            "title": _page["title"],
            "description": _page["description"],
        })
        ctx["pages"].append((_page["file"], page_main(_html), {
            "id": _page["file"], "url": f'/{_page["file"]}', "type": "page",
            "template": "", "title": _page["title"], "lang": "en",
            "subjects": [], "exams": [], "tags": [], "hub": "current-affairs.html",
        }))
    if ca_page_entries:
        info(f"current affairs pages: {len(ca_page_entries)} page(s) written "
             f"under current-affairs/")

    # ---- stale output removal --------------------------------------------
    # Every writer above has registered its files in `expected` by now, so a
    # page nobody produced any more (a deleted draft, a retired tag archive)
    # is removed exactly once, here.
    removed = []
    for fn in sorted(os.listdir(ROOT)):
        if fn.endswith(".html") and fn.startswith(GEN_PREFIXES) and fn not in expected:
            (ROOT / fn).unlink()
            removed.append(fn)
    # Nested routes live one level down (pyq/<slug>/index.html), which the root
    # scan above cannot see into: an exam folder that no longer exists, or a
    # slug that was renamed in its metadata.json, is cleaned up here - the
    # directory with it, so no empty route is left behind on disk.
    pyq_dir = ROOT / "pyq"
    if pyq_dir.is_dir():
        for name in sorted(os.listdir(pyq_dir)):
            if name.startswith("."):
                continue
            sub = pyq_dir / name
            if sub.is_dir():
                for fn in sorted(os.listdir(sub)):
                    rel = f"pyq/{name}/{fn}"
                    if fn.endswith(".html") and rel not in expected:
                        (sub / fn).unlink()
                        removed.append(rel)
                if not [n for n in os.listdir(sub)
                        if n != ".DS_Store" and not n.startswith(".")]:
                    sub.rmdir()
            elif name.endswith(".html") and f"pyq/{name}" not in expected:
                sub.unlink()
                removed.append(f"pyq/{name}")
        if not [n for n in os.listdir(pyq_dir)
                if n != ".DS_Store" and not n.startswith(".")]:
            try:
                pyq_dir.rmdir()
            except OSError:
                pass
    pa_dir = ROOT / "pa"
    if pa_dir.is_dir():
        for fn in sorted(os.listdir(pa_dir)):
            if fn.endswith(".html") and fn.startswith(GEN_PREFIXES) and \
                    f"pa/{fn}" not in expected:
                (pa_dir / fn).unlink()
                removed.append(f"pa/{fn}")
        leftovers = [n for n in os.listdir(pa_dir) if n != ".DS_Store"]
        if not leftovers:
            for n in os.listdir(pa_dir):
                if n != ".DS_Store":
                    (pa_dir / n).unlink()
            try:
                pa_dir.rmdir()
            except OSError:
                pass
    # The Current Affairs section is two directories deep
    # (current-affairs/<language>/[<month>/]), which the root scan above cannot
    # see into: a language folder, or a month folder, that no longer exists on
    # disk is cleaned up here - and the directories they leave empty go with
    # them, so no empty route survives.
    ca_dir = ROOT / "current-affairs"
    if ca_dir.is_dir():
        for sub in sorted(p for p in ca_dir.rglob("*") if p.is_file()):
            rel = sub.relative_to(ROOT).as_posix()
            if sub.suffix == ".html" and rel not in expected:
                sub.unlink()
                removed.append(rel)
        for sub in sorted((p for p in ca_dir.rglob("*") if p.is_dir()),
                          key=lambda p: len(p.parts), reverse=True):
            try:
                sub.rmdir()
            except OSError:
                pass                            # still holds a file: keep it
        try:
            ca_dir.rmdir()
        except OSError:
            pass
    if removed:
        warn("stale content pages removed: " + ", ".join(removed))

    # ---- Phase 3: content graph + homepage engine -------------------------
    articles, landing_pages = [], []
    for _path, _key, _slot in (
            (ROOT / "data" / "articles.json", "articles", "articles"),
            (ROOT / "data" / "landing-manifest.json", "pages", "landing")):
        try:
            value = json.loads(_path.read_text(encoding="utf-8")).get(_key, [])
        except Exception as e:
            warn(f"{_path.name} unreadable: {e}")
            value = []
        if _slot == "articles":
            articles = value
        else:
            landing_pages = value
    write_content_graph(ctx, index, exams, articles, landing_pages,
                        [r for r in rendered if r["lang"] == "en"])

    # ---- Study subject registry ------------------------------------------
    # data/study-manifest.json: the folders on disk plus the counts above, for
    # the Study menu in core.js and the subject grid on study.html. Written
    # before the content manifest so a single build always leaves both files
    # describing the same run.
    study_manifest = study_material.build(all_records[STUDY_DIR], study_registry())
    info(f"study subjects: {len(study_manifest['subjects'])} folder(s), "
         f"{study_manifest['total']} material(s) -> data/study-manifest.json")

    # ---- Rank 2 Blueprint document shelf ---------------------------------
    # data/proof-manifest.json: every scan in assets/proof/, with the byte size
    # and file type measured off the file itself. The Blueprint's Official
    # Documents section reads it and grows a card for each new drop - so
    # publishing a scan is a file plus `npm run publish`, never an HTML edit.
    proof_manifest = proof_documents.build()
    filled = sum(1 for s in proof_manifest["slots"] if s["doc"])
    info(f"proof: {proof_manifest['total']} scan(s), {filled}/"
         f"{len(proof_manifest['slots'])} slot(s) filled -> data/proof-manifest.json")

    # ---- manifest ---------------------------------------------------------
    # `drops` is the scanner's inventory, carried through byte for byte: the
    # manifest is the single list the site, the sitemap and the SEO gate read,
    # so nothing here re-derives what scripts/build_content_manifest.ts found.
    manifest = {
        "version": 3,
        "domain": DOMAIN,
        "hubs": hubs_out,
        "pages": [{
            "file": ARCHIVES_FILE,
            "url": f"{DOMAIN}/archives",
            "title": ARCHIVES_TITLE,
            "description": ARCHIVES_DESC,
        }] + phase4_manifest + pyq_page_entries + ca_page_entries,
        "items": sorted(manifest_items, key=lambda r: r["file"]),
        "pdfs": pdfs,
        "drops": drops,
        "counts": {c: len(all_records[c]) + len(punjabi[c]) for c in HUBS},
        "generatedBy": "scripts/build_content.py",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    info(f"manifest: {len(hubs_out)} hubs, {len(manifest_items)} document page(s), "
         f"{len(pdfs)} pdf record(s), {len(drops)} pdf drop(s) -> "
         f"data/content-manifest.json")

    # ---- report -----------------------------------------------------------
    for w in warnings:
        print(f"  \u26a0 {w}")
    for n in notes:
        print(f"  \u2139 {n}")
    if errors:
        print()
        for e in errors:
            print(f"  \u274c {e}")
        print(f"\n\u274c content build FAILED with {len(errors)} error(s).")
        return 1
    if strict and warnings:
        print(f"\n\u274c content build FAILED (--strict): {len(warnings)} warning(s).")
        return 1
    print("\n\u2705 Content build complete.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
