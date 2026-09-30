"""study_material.py - writes data/study-manifest.json.

The Study system reads its shape straight off disk:

    content/study-material/<subject>/<language>/<chapter>/<part file>

so this module's whole job is to walk that tree and write down what it found:
which subjects exist, which languages each one is published in, which chapters
sit under each language, and which parts make up each chapter. A folder added
today is a row tomorrow - there is no list of subjects, languages or chapters
anywhere in this file to append to.

Mirrors scripts/books_engine.py: a small module build_content.py calls once,
writing one generated file. It is deliberately timestamp-free - ci.sh's final
`git diff --exit-code` would otherwise drift on the clock alone - and sorted by
`order`, then name, so the nav, the Study root grid, the subject pages and the
sitemap all read the same rows in the same order.

Owned by the Study system only. The item-level records (title, description,
size, badges, dates, search haystack) live in data/content-manifest.json - the
canonical document list the sitemap, the SEO gate and the search index all
read. This file is the tree above them: ids and order, joined to those records
by `file`, never a second copy of them.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
COLL = "study-material"
OUT = ROOT / "data" / "study-manifest.json"

DEFAULT_ICON = "\U0001f4da"        # books
DEFAULT_COLOR = "#4f46e5"          # the site's brand indigo


def folders(base):
    """Sub-folder ids of `base`, sorted.

    Hidden folders and anything prefixed `_` are the publisher's own business
    and never become rows; every other folder is content by definition."""
    base = Path(base)
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def decorate(folder, registry):
    """Optional presentation from content/study-material/metadata.json.

    Everything here is decoration: a folder is a subject whether or not it is
    listed, and a subject listed with no folder is ignored, so nothing in the
    registry can invent a page."""
    cfg = ((registry or {}).get("subjects") or {}).get(folder) or {}
    name = str(cfg.get("name") or folder.replace("-", " ").title())
    return {
        "id": folder,
        "name": name,
        "icon": str(cfg.get("icon") or DEFAULT_ICON),
        "color": str(cfg.get("color") or DEFAULT_COLOR),
        "description": str(cfg.get("description") or ""),
        "order": int(cfg.get("order") if isinstance(cfg.get("order"), (int, float))
                     else 100),
    }


def _bc():
    """The Study helpers build_content.py already owns.

    Imported lazily because build_content imports this module at load time and
    calls it only once the build is running - by then the module is complete.
    One implementation of "what is a language called" and "what is this folder
    called" is the point: the page, the hub, the search row and this tree must
    never disagree about a name."""
    import build_content as bc
    return bc


def language_universe(all_records):
    """Every language the site has discovered, in display order.

    The site's own two languages come first and always appear - that is what a
    subject with no folder of its own still offers its reader - and any
    language folder found anywhere is added after them. Creating a new
    language means creating a folder; no list here needs editing."""
    bc = _bc()
    found = {}
    for subject in folders(CONTENT / COLL):
        for lang in folders(CONTENT / COLL / subject):
            info = bc.study_lang(lang)
            if info["id"]:
                found.setdefault(info["id"], info)
    for rec in all_records:
        lid = str(rec.get("studyLanguage") or "")
        if lid and lid not in found:
            info = bc.study_lang(lid)
            found[lid] = dict(info, id=lid,
                              name=str(rec.get("studyLanguageName") or "")
                              or info["name"] or lid)

    rank = {code: i for i, code in enumerate(bc.STUDY_LANG)}
    universe = [dict(cfg, id=code) for code, cfg in bc.STUDY_LANG.items()]
    seen = {e["id"] for e in universe}
    universe += [found[k] for k in sorted(found) if k not in seen]
    universe.sort(key=lambda e: (rank.get(e["id"], len(rank)),
                                 e["name"].lower(), e["id"]))
    return universe


def language_rows(subject, records, universe):
    """The languages this subject is published in, with their chapter tree.

    Chapters and parts come from the folders; a record that sits deeper or
    shallower than the documented shape still lands under the folders it does
    have, so nothing can be published but invisible."""
    bc = _bc()
    base = CONTENT / COLL / subject
    by_lang = {}
    for lang in folders(base):
        info = bc.study_lang(lang)
        lid = info["id"] or lang
        chapters = by_lang.setdefault(lid, {})
        for chapter in folders(base / lang):
            chapters.setdefault(chapter,
                                {"id": chapter,
                                 "name": bc.study_nice_name(chapter),
                                 "parts": []})

    for rec in records:
        lid = str(rec.get("studyLanguage") or "") or "en"
        chapters = by_lang.setdefault(lid, {})
        chapter_id = str(rec.get("studyChapter") or "")
        node = chapters.setdefault(
            chapter_id or "part",
            {"id": chapter_id or "part",
             "name": str(rec.get("studyChapterName") or ""),
             "parts": []})
        if not node["name"]:
            node["name"] = str(rec.get("studyChapterName") or "") or \
                bc.study_nice_name(chapter_id or Path(str(rec.get("file")
                                                           )).stem)
        node["parts"].append({"file": str(rec.get("file") or ""),
                              "n": int(rec.get("studyPart") or 1)})

    rows = []
    for entry in universe:
        lid = entry["id"]
        chapters = []
        for node in (by_lang.get(lid) or {}).values():
            node["parts"].sort(key=lambda p: (p["n"], p["file"]))
            node["parts"] = [p for p in node["parts"] if p["file"]]
            chapters.append(node)
        chapters.sort(key=lambda c: (c["name"].lower(), c["id"]))
        rows.append({"id": lid, "name": entry["name"],
                     "native": entry.get("native") or "",
                     "flag": entry.get("flag") or "",
                     "count": sum(len(c["parts"]) for c in chapters),
                     "chapters": chapters})
    return rows


def build(records, registry=None):
    """-> data/study-manifest.json. `records` are the Study Material documents
    the build published this run (already stamped with subject, language,
    chapter, part and dates)."""
    by_subject = {}
    for rec in records:
        by_subject.setdefault(str(rec.get("studySubject") or ""), []).append(rec)

    universe = language_universe(records)

    rows = []
    for folder in folders(CONTENT / COLL):
        row = decorate(folder, registry)
        mine = by_subject.get(folder, [])
        row["count"] = len(mine)
        row["newest"] = max(
            (str(r.get("updated") or r.get("published") or "")[:10]
             for r in mine), default="")
        row["totalSize"] = sum(int(r.get("size") or 0) for r in mine)
        row["languages"] = language_rows(folder, mine, universe)
        row["chapters"] = sum(len(l["chapters"]) for l in row["languages"])
        rows.append(row)
    rows.sort(key=lambda r: (r["order"], r["name"].lower(), r["id"]))

    manifest = {
        "version": 2,
        "domain": "https://houseofaspirants.in",
        "languages": [{"id": e["id"], "name": e["name"],
                       "native": e.get("native") or "",
                       "flag": e.get("flag") or ""} for e in universe],
        "subjects": rows,
        "total": sum(r["count"] for r in rows),
        "generatedBy": "scripts/study_material.py",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return manifest
