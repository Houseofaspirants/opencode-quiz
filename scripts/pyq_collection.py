"""pyq_collection.py - writes data/pyq-manifest.json.

Previous Year Questions is a folder-per-exam collection:

    content/previous-year-questions/<exam>/
        metadata.json                 title, slug, organization, category, languages
        overview.en.md                the English overview
        overview.pa.md                the Punjabi overview
        2026-question-paper.pdf       the official paper
        2026-official-answer-key.pdf  the official key (optional)

The PDF scanner (scripts/build_content_manifest.ts) has already listed every
one of those files in data/content-manifest.json with the exam folder as its
`category`, so this module never walks content/ for the papers: it groups the
drops it is handed by exam folder, pairs paper and key on the four-digit year
and writes down what it found.

Rules that keep the page honest:

  * a year is a row when its question paper exists; the answer-key cell then
    reads "Not published" until the conducting body's key is dropped beside it.
    Nothing is invented to fill a cell, and a paper whose key has not appeared
    still publishes - requirement, not an oversight;
  * a key with no paper beside it is warned about and published anyway, so a
    file is never hidden from the reader;
  * a PDF at the collection root belongs to no exam. It keeps the standalone
    page every drop already gets, and never reaches a table;
  * `languages` and the two overview files are read, never guessed: an
    overview renders only when its file exists.

Mirrors scripts/study_material.py: one module build_content.py calls once,
writing one generated file, sorted and timestamp-free so ci.sh's final
`git diff --exit-code` cannot drift on the clock.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLL = "previous-year-questions"
CONTENT = ROOT / "content" / COLL
OUT = ROOT / "data" / "pyq-manifest.json"
DOMAIN = "https://houseofaspirants.in"

# The two file names the collection recognises. Anything else in an exam
# folder is a document of some other kind and keeps its own page.
# An optional suffix names one of several files for the same year - a shift,
# a set, a date or a subject: 2021-question-paper-27-aug-shift-1.pdf,
# 2022-official-answer-key-set-b.pdf. The suffix becomes the file's label.
PAPER_RE = re.compile(r"^(\d{4})-question-paper(?:-?([a-z0-9][a-z0-9-]*))?\.pdf$",
                      re.IGNORECASE)
KEY_RE = re.compile(r"^(\d{4})-official-answer-key(?:-?([a-z0-9][a-z0-9-]*))?\.pdf$",
                    re.IGNORECASE)
MONTHS = {m.lower(): m for m in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
                                 "Aug", "Sep", "Oct", "Nov", "Dec")}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
LANGS = ("en", "pa")
REQUIRED = ("title", "slug", "organization", "category", "languages")


def year_of(filename):
    """The year both patterns name, or "" when the file is neither."""
    for rx in (PAPER_RE, KEY_RE):
        m = rx.match(str(filename or ""))
        if m:
            return m.group(1)
    return ""


def label_of(filename):
    """The human label a file's suffix carries: `27-aug-shift-1` -> "27 Aug,
    Shift 1", `set-b-revised` -> "Set B Revised", a bare `2` -> "Paper 2".
    "" when the file has no suffix."""
    name = str(filename or "")
    m = PAPER_RE.match(name) or KEY_RE.match(name)
    if not m or not m.group(2):
        return ""
    words = [w for w in m.group(2).lower().split("-") if w]
    if len(words) == 1 and words[0].isdigit():
        return f"Paper {words[0]}"
    out, phrase, i = [], [], 0

    def flush():
        if phrase:
            out.append(" ".join(phrase))
            phrase.clear()

    while i < len(words):
        w = words[i]
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if w in ("set", "shift", "paper") and nxt and len(nxt) <= 2:
            flush()
            out.append(f"{w.title()} {nxt.upper() if w == 'set' else nxt}")
            i += 2
            continue
        if w.isdigit() and nxt in MONTHS:
            flush()
            out.append(f"{int(w)} {MONTHS[nxt]}")
            i += 2
            continue
        if w in MONTHS:
            phrase.append(MONTHS[w])
        elif len(w) <= 3 and not w.isdigit() and w not in ("all", "set", "and", "the", "of"):
            phrase.append(w.upper())
        else:
            phrase.append(w.title())
        i += 1
    flush()
    return ", ".join(out)


def claims(drop):
    """True when this drop is published as a download inside an exam page's
    table instead of earning a page of its own: it sits in an exam folder and
    is named the way the collection names a paper or an answer key."""
    return (str(drop.get("folder") or "") == COLL
            and bool(str(drop.get("category") or "").strip())
            and bool(year_of(drop.get("filename"))))


def file_row(drop):
    """The download cell: the file, its size and its page count - every value
    measured by the scanner, none of them derived from the file name."""
    return {
        "path": str(drop.get("path") or ""),
        "filename": str(drop.get("filename") or ""),
        "label": label_of(drop.get("filename")),
        "title": str(drop.get("title") or ""),
        "size": int(drop.get("size") or 0),
        "sizeLabel": str(drop.get("sizeLabel") or ""),
        "pages": int(drop.get("pages") or 0),
        "language": str(drop.get("language") or "en"),
        "published": str(drop.get("published") or ""),
        "modified": str(drop.get("modified") or ""),
    }


def _sidecar(folder, err):
    """content/previous-year-questions/<exam>/metadata.json -> dict, or None.

    Every field the collection publishes is stated here; the build never
    guesses an organisation or a category, and a folder without a sidecar is
    an error rather than a half-described page."""
    where = f"content/{COLL}/{folder.name}/metadata.json"
    path = folder / "metadata.json"
    if not path.is_file():
        err(f"{where}: missing - an exam folder is described by its "
            f"metadata.json (title, slug, organization, category, languages)")
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        err(f"{where}: unreadable JSON ({e})")
        return None
    if not isinstance(meta, dict):
        err(f"{where}: must be a JSON object")
        return None
    for key in REQUIRED:
        if meta.get(key) in (None, "", [], {}):
            err(f"{where}: missing required field {key!r}")
            return None
    if not SLUG_RE.fullmatch(str(meta["slug"]).strip()):
        err(f"{where}: slug {meta['slug']!r} must be lowercase letters, digits "
            f"and hyphens only")
        return None
    langs = meta["languages"]
    if not isinstance(langs, list) or not langs:
        err(f"{where}: languages must be a non-empty list (en, pa)")
        return None
    bad = [str(l) for l in langs if str(l) not in LANGS]
    if bad:
        err(f"{where}: languages {bad} not one of {', '.join(LANGS)}")
        return None
    return meta


def _overview(folder, lang):
    """The overview for one language - "" when the file is not there, so an
    exam that has never been written up still publishes its table."""
    path = folder / f"overview.{lang}.md"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _description(title, organization):
    """140-160 characters: the window every meta description on the site sits
    in. Built from the sidecar's own fields only - never from a year count,
    which changes the moment a paper lands and would rewrite the page's meta
    description on every publish."""
    return (f"{title} from {organization} - question papers and official "
            f"answer keys by year, with a download for each document.")


def build(drops, err, warn, info=None):
    """-> manifest dict, written by build_content.py. Returns {} when no exam
    folder exists yet - an empty collection publishes nothing, rather than an
    empty page pretending to be one.

    The folders on disk are the exams, exactly as they are the Study system's
    subjects: a folder with a sidecar publishes whether or not a paper has
    been dropped into it yet, so the first PDF of an exam is a file plus
    `npm run publish` and never a page rebuild."""
    groups = {}
    for drop in drops or []:
        if str(drop.get("folder") or "") != COLL:
            continue
        rel = Path(str(drop.get("path") or "")).parts
        if len(rel) != 4:
            err(f"{drop.get('path')}: papers must sit directly in their exam "
                f"folder (content/{COLL}/<exam>/<file>.pdf)")
            continue
        exam = str(drop.get("category") or "").strip()
        if not exam:
            # The collection root: no exam owns this file, so it is not part
            # of any table and keeps the standalone page it has today.
            continue
        groups.setdefault(exam, []).append(drop)

    if not CONTENT.is_dir():
        return {}
    # Hidden folders and anything the publisher prefixes with `_` are never
    # rows; every other folder is an exam by definition.
    folders = sorted(p.name for p in CONTENT.iterdir()
                     if p.is_dir() and not p.name.startswith((".", "_")))

    exams, taken = [], {}
    for folder in folders:
        base = CONTENT / folder
        meta = _sidecar(base, err)
        if meta is None:
            continue
        if folder not in groups:
            warn(f"content/{COLL}/{folder}: no question paper dropped yet - "
                 f"the exam publishes with an empty table until one is")

        slug = str(meta["slug"]).strip()
        if slug in taken:
            err(f"content/{COLL}/{folder}/metadata.json: slug {slug!r} is "
                f"already claimed by {taken[slug]}")
            continue
        taken[slug] = folder

        rows, others = {}, []
        for drop in groups.get(folder, []):
            name = str(drop.get("filename") or "")
            m = PAPER_RE.match(name)
            if m:
                # A list, not a slot: a year that ran in more than one shift
                # keeps every paper, and the table names each one.
                rows.setdefault(int(m.group(1)),
                                {"year": m.group(1), "papers": []}
                                )["papers"].append(drop)
                continue
            m = KEY_RE.match(name)
            if m:
                rows.setdefault(int(m.group(1)),
                                {"year": m.group(1), "papers": []}
                                ).setdefault("keys", []).append(drop)
                continue
            others.append(drop)

        papers = []
        for year in sorted(rows, reverse=True):
            slot = rows[year]
            by_name = lambda d: str(d.get("filename") or "")
            sheets = sorted(slot.get("papers") or [], key=by_name)
            keys = sorted(slot.get("keys") or [], key=by_name)
            if keys and not sheets:
                warn(f"content/{COLL}/{folder}/{keys[0].get('filename')}: an "
                     f"answer key with no {year} question paper beside it - "
                     f"published as a row with the paper cell marked Not "
                     f"published")
            key_rows = [file_row(d) for d in keys]
            papers.append({
                "year": slot["year"],
                "papers": [file_row(d) for d in sheets],
                "key": key_rows[0] if key_rows else None,
                "keys": key_rows,
            })

        title = str(meta["title"]).strip()
        langs = [str(l) for l in meta["languages"]]
        overview = {lang: _overview(base, lang) for lang in LANGS}
        for lang in langs:
            if not overview.get(lang):
                warn(f"content/{COLL}/{folder}: languages lists {lang!r} but "
                     f"overview.{lang}.md is missing - that block stays off "
                     f"the page rather than being filled in")
        years = len(papers)
        exam = {
            "id": folder,
            "slug": slug,
            "title": title,
            "organization": str(meta["organization"]).strip(),
            "exam": str(meta.get("exam") or folder).strip(),
            "category": str(meta["category"]).strip(),
            "languages": langs,
            "description": str(meta.get("description") or "").strip()
                           or _description(title,
                                           str(meta["organization"]).strip()),
            "overview": {k: v for k, v in overview.items() if v},
            "papers": papers,
            "others": [file_row(d) for d in
                       sorted(others, key=lambda d: str(d.get("filename") or ""))],
            "years": years,
            "count": sum(len(p["papers"]) for p in papers),
            "keys": sum(1 for p in papers if p["key"]),
            "keyFiles": sum(len(p["keys"]) for p in papers),
            "file": f"pyq/{slug}/index.html",
            "url": f"{DOMAIN}/pyq/{slug}",
            "hub": "previous-year-questions.html",
        }
        exams.append(exam)

    if not exams:
        return {}
    exams.sort(key=lambda e: e["title"].lower())
    manifest = {
        "version": 1,
        "domain": DOMAIN,
        "total": len(exams),
        "papers": sum(e["count"] for e in exams),
        "keys": sum(e["keys"] for e in exams),
        "exams": exams,
        "generatedBy": "scripts/pyq_collection.py",
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    if info:
        info(f"pyq: {len(exams)} exam folder(s), {manifest['papers']} paper(s), "
             f"{manifest['keys']} answer key(s) -> data/pyq-manifest.json")
    return manifest
