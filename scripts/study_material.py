"""study_material.py - writes data/study-manifest.json.

The Study nav and the Study page need the same list: which subject folders
exist, what each one is called, and how much material is in it. This module
derives that list from the folder names on disk plus the records the build just
published, so a folder dropped into content/study-material/ today appears in
the header menu tomorrow with a correct count on it - no list to append to, no
count to keep in step by hand.

Mirrors scripts/books_engine.py: a small module build_content.py calls once,
writing one generated file. It is deliberately timestamp-free - ci.sh's final
`git diff --exit-code` would otherwise drift on the clock alone - and sorted by
`order` then name so the nav, the Study root grid and the sitemap all read the
same rows in the same order.

Owned by the Study system only. The item-level records live in
data/content-manifest.json (the canonical document list the sitemap, the SEO
gate and the search index all read); this file is the subject registry above
them, not a second copy of them.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
COLL = "study-material"
OUT = ROOT / "data" / "study-manifest.json"

# Every file ever dropped in, listed under every folder that exists - a folder
# with nothing in it still belongs to the menu (that is where the next file
# goes), and a file without a folder cannot exist by construction.
DEFAULT_ICON = "\U0001f4da"        # books
DEFAULT_COLOR = "#4f46e5"          # the site's brand indigo


def folders():
    """Subject folder ids, straight off disk. Sorted for a deterministic build."""
    base = CONTENT / COLL
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def decorate(folder, registry):
    """Optional presentation from content/study-material/metadata.json.

    Everything here is decoration: name, icon, colour, order, blurb. The
    subject itself exists because its folder does, so a registry entry can
    never invent a page or hide one."""
    cfg = (registry or {}).get("subjects", {}).get(folder) or {}
    if isinstance(cfg, str):
        cfg = {"name": cfg}
    if not isinstance(cfg, dict):
        cfg = {}
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


def build(records, registry=None):
    """-> data/study-manifest.json. `records` are the Study Material documents
    the build published this run (already stamped with studySubject, dates)."""
    by_subject = {}
    for rec in records:
        by_subject.setdefault(str(rec.get("studySubject") or ""), []).append(rec)

    rows = []
    for folder in folders():
        row = decorate(folder, registry)
        mine = by_subject.get(folder, [])
        row["count"] = len(mine)
        row["newest"] = max(
            (str(r.get("updated") or r.get("published") or "")[:10]
             for r in mine), default="")
        row["totalSize"] = sum(int(r.get("size") or 0) for r in mine)
        rows.append(row)
    rows.sort(key=lambda r: (r["order"], r["name"].lower(), r["id"]))

    manifest = {
        "version": 1,
        "domain": "https://houseofaspirants.in",
        "subjects": rows,
        "total": sum(r["count"] for r in rows),
        "generatedBy": "scripts/study_material.py",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return manifest
