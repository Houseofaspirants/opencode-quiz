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


# ---------------------------------------------------------------- hierarchy -
# One folder can hold a lot, and General Knowledge holds the most. A
# *hierarchy* is an optional grouping declared in
# content/study-material/metadata.json that folds existing subject folders
# under one card and gives the reader two more steps before the language
# step - Region, then Category, then (only when the category declares one)
# Sub Category.
#
# Three rules keep it as honest as the rest of the shelf:
#   1. a declared node may only name folders that exist - a folder nobody
#      listed is still a subject, and a listed folder with no directory is
#      dropped rather than rendered as a card that leads nowhere;
#   2. every number on every card is measured off the records behind those
#      folders, so nothing here can claim a chapter nobody published;
#   3. with the block absent, nothing at all changes: every folder keeps
#      rendering exactly the subject card it renders today.
def _hierarchies(registry):
    """{"gk": {name, icon, color, order, description, regions: [...]}}."""
    raw = (registry or {}).get("hierarchies")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def _pages_of(rec):
    """Page count of one file, or 0 when it has none.

    `pdfPages` is the count read out of the PDF itself; for a PDF the build
    also stamps reading minutes as one page a minute, so that is the fallback.
    An .md or .json has no pages and honestly reports none."""
    try:
        n = int(rec.get("pdfPages") or 0)
    except (TypeError, ValueError):
        n = 0
    if n > 0:
        return n
    if str(rec.get("type") or "").lower() == "pdf":
        try:
            return max(0, int(rec.get("readingMinutes") or 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _stats(recs):
    """Measured facts for one node: files, distinct chapters, pages, newest."""
    chapters = sorted({str(r.get("studyChapter") or "").strip()
                       for r in recs if str(r.get("studyChapter") or "").strip()})
    return {
        "files": len(recs),
        "chapters": len(chapters),
        "pages": sum(_pages_of(r) for r in recs),
        "totalSize": sum(int(r.get("size") or 0) for r in recs),
        "newest": max((str(r.get("updated") or r.get("published") or "")[:10]
                       for r in recs), default=""),
    }


def _records_for(folders, by_subject):
    """Every record filed under any of `folders`, in folder order."""
    out = []
    for fid in folders:
        out.extend(by_subject.get(fid, []) or [])
    return out


def _merge_languages(row_by_folder, folders):
    """Language rows from several folders, merged into one list.

    A chapter written in two languages is one chapter in two rows; a chapter
    that somehow lands under two folders is counted once."""
    merged, seen = [], {}
    for fid in folders:
        row = row_by_folder.get(fid)
        if not row:
            continue
        for lang in (row.get("languages") or []):
            key = str(lang.get("id") or "")
            node = seen.get(key)
            if node is None:
                node = {"id": key, "name": str(lang.get("name") or ""),
                        "native": str(lang.get("native") or ""),
                        "flag": str(lang.get("flag") or ""),
                        "count": 0, "chapters": []}
                seen[key] = node
                merged.append(node)
            node["count"] += int(lang.get("count") or 0)
            have = {c["id"] for c in node["chapters"]}
            for ch in (lang.get("chapters") or []):
                if ch["id"] in have:
                    continue
                node["chapters"].append(ch)
                have.add(ch["id"])
    for node in merged:
        node["chapters"].sort(key=lambda c: (str(c["name"]).lower(), c["id"]))
    # The site's own languages are always on offer - that is what a category
    # with no files of its own still offers its reader - and any other
    # language earns its place by having something in it. This keeps a
    # folder-name artefact out of a category card without ever removing a
    # language somebody actually published in.
    site = set(_bc().STUDY_LANG)
    merged = [n for n in merged if n["count"] > 0 or n["id"] in site]
    merged.sort(key=lambda n: (str(n["name"]).lower(), n["id"]))
    return merged


def _languages_of_sub(languages, claimed):
    """The same language rows narrowed to the chapters one sub head claims."""
    out = []
    for lang in languages:
        chapters = [c for c in (lang.get("chapters") or []) if c["id"] in claimed]
        if not chapters:
            continue
        out.append({**{k: lang[k] for k in ("id", "name", "native", "flag")},
                    "count": sum(len(c.get("parts") or []) for c in chapters),
                    "chapters": chapters})
    return out


def build_hierarchies(registry, by_subject, row_by_folder):
    """-> (hierarchy subject rows, folder ids they claim).

    The rows look like any other subject row - id, name, icon, colour, count -
    so the Study root grid, the header menu and `study.html?subject=<id>` all
    keep working without knowing a hierarchy exists. The extra `hierarchy`
    key carries the two steps underneath it and is only read by a renderer
    that recognises it."""
    claimed_all, rows = set(), []
    for hid, cfg in _hierarchies(registry).items():
        regions_out, region_folders = [], []
        for reg in (cfg.get("regions") or []):
            if not isinstance(reg, dict):
                continue
            cats_out, cat_folders = [], []
            for cat in (reg.get("categories") or []):
                if not isinstance(cat, dict):
                    continue
                # A category reads from folders that exist. One that names
                # nothing real is dropped rather than shipped as a dead card.
                folders = [str(f) for f in (cat.get("folders") or [])
                           if str(f) in row_by_folder]
                if not folders:
                    continue
                recs = _records_for(folders, by_subject)
                languages = _merge_languages(row_by_folder, folders)
                subs_out, claimed_ch = [], set()
                for sub in (cat.get("subCategories") or []):
                    if not isinstance(sub, dict):
                        continue
                    ids = {str(c) for c in (sub.get("chapters") or [])}
                    if not ids:
                        continue                      # a head with nothing in it
                    mine = [r for r in recs
                            if str(r.get("studyChapter") or "") in ids]
                    if not mine:
                        continue                      # ids that do not exist
                    real = {str(r.get("studyChapter") or "") for r in mine}
                    subs_out.append({
                        "id": str(sub.get("id") or sub.get("name") or ""),
                        "name": str(sub.get("name") or ""),
                        "description": str(sub.get("description") or ""),
                        "chapters": sorted(real),
                        "stats": _stats(mine),
                        "languages": _languages_of_sub(languages, ids),
                    })
                    claimed_ch |= real
                cats_out.append({
                    "id": str(cat.get("id") or cat.get("name") or ""),
                    "name": str(cat.get("name") or ""),
                    "description": str(cat.get("description") or ""),
                    "folders": folders,
                    "stats": _stats(recs),
                    "languages": languages,
                    "subCategories": subs_out,
                    "claimedChapters": sorted(claimed_ch),
                })
                cat_folders += folders
            if not cats_out:
                continue
            reg_recs = _records_for(cat_folders, by_subject)
            regions_out.append({
                "id": str(reg.get("id") or reg.get("name") or ""),
                "name": str(reg.get("name") or ""),
                "description": str(reg.get("description") or ""),
                "stats": dict(_stats(reg_recs), categories=len(cats_out)),
                "categories": cats_out,
            })
            region_folders += cat_folders
        if not regions_out:
            continue

        mine = _records_for(region_folders, by_subject)
        stats = _stats(mine)
        stats["categories"] = sum(len(r["categories"]) for r in regions_out)
        stats["regions"] = len(regions_out)
        claimed_all |= set(region_folders)
        rows.append({
            "id": hid,
            "name": str(cfg.get("name") or hid),
            "icon": str(cfg.get("icon") or DEFAULT_ICON),
            "color": str(cfg.get("color") or DEFAULT_COLOR),
            "description": str(cfg.get("description") or ""),
            "order": int(cfg["order"]) if isinstance(cfg.get("order"),
                                                      (int, float)) else 100,
            "count": stats["files"],
            "newest": stats["newest"],
            "totalSize": stats["totalSize"],
            "chapters": stats["chapters"],
            "languages": [],
            "hierarchy": {
                "id": hid,
                "name": str(cfg.get("name") or hid),
                "description": str(cfg.get("description") or ""),
                "stats": stats,
                "regions": regions_out,
            },
        })
    return rows, claimed_all


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

    # A hierarchy folds folders into one card. The folders keep their own rows
    # - `study.html?subject=history` is linked from every History material
    # page and must keep resolving - they are simply marked `hidden` so the
    # shelf grid and the header menu list the group instead of its parts.
    by_id = {r["id"]: r for r in rows}
    hier_rows, claimed = build_hierarchies(registry, by_subject, by_id)
    for r in rows:
        if r["id"] in claimed:
            r["hidden"] = True
    rows.extend(hier_rows)

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
