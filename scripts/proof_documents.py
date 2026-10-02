"""proof_documents.py - writes data/proof-manifest.json.

The Rank 2 Blueprint is a trust page: every claim on it should be checkable
against a document rather than taken on faith. That means the owner adds
scans over time - a result card one week, an answer sheet the next - and the
page has to grow with them without anyone touching its HTML.

So this module is a folder walker with one job:

    assets/proof/<anything>.pdf|jpg|png|webp   -> data/proof-manifest.json

Drop a file in, run `npm run publish`, and the Official Documents section
gains a card with a preview, a download, a file-type badge and a real byte
size. There is no list of documents anywhere in this file or in the page: a
name nobody has thought of yet still lands in `extra` and is shown rather
than silently dropped.

Mirrors scripts/study_material.py - a small module build_content.py calls
once, writing one generated file. It is deliberately derived from file bytes
and names only: no clock, no `stat().st_mtime`, no `git log`. Every one of
those changes under a fresh clone or a re-checkout, and ci.sh's final
`git diff --exit-code` would then fail on a machine that never saw the drop.

Optional sidecar: assets/proof/metadata.json

    {
      "official-result.jpg": {
        "title": "Final result letter",
        "note": "Released by the Punjab Police Recruitment Board.",
        "uploaded": "2026-10-04",
        "questions": [
          {"n": 1, "text": "...", "selected": "B", "correct": "C",
           "explanation": "..."}
        ]
      }
    }

Every key is optional and every entry is keyed by the file's own name, so the
sidecar is a set of corrections to what the folder already says, never a
second inventory of it. `title`, `note` and `uploaded` are the only human
strings here; `bytes`, `size` and the file-type badge are always measured.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "proof-manifest.json"

# Folders scanned, in order. The first is the canonical one; the second is the
# path proof.js has always documented for the homepage gallery, kept so a scan
# dropped where the old instructions said still reaches the blueprint.
DIRS = ("assets/proof", "assets/img/proof")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}

# The cards the blueprint shows, in reading order. `keys` are filename tokens -
# lower-cased, punctuation folded to `-` - that claim the slot. `optional` slots
# only exist once a file claims them, so a page with no appointment letter does
# not carry an empty appointment card.
SLOTS = (
    {"id": "result",      "label": "Result Card",          "keys": ("result", "marksheet", "mark-sheet", "scorecard"), "optional": True},
    {"id": "merit",       "label": "Merit List",           "keys": ("merit",)},
    {"id": "paper-1",     "label": "Paper 1 Answer Sheet", "keys": ("paper-1", "answer-sheet-1", "answersheet-1", "sheet-1")},
    {"id": "paper-2",     "label": "Paper 2 Answer Sheet", "keys": ("paper-2", "answer-sheet-2", "answersheet-2", "sheet-2")},
    {"id": "paper-3",     "label": "Paper 3 Answer Sheet", "keys": ("paper-3", "answer-sheet-3", "answersheet-3", "sheet-3")},
    {"id": "appointment", "label": "Appointment Letter",   "keys": ("appointment",), "optional": True},
    {"id": "training",    "label": "Training Photos",      "keys": ("training", "joining"), "optional": True},
)


def fold(name):
    """Filename stem -> a punctuation-agnostic key. `Paper 1 (a).PDF` -> `paper-1-a`."""
    stem = re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")
    return stem


def human_size(n):
    """1_234_567 -> '1.2 MB'. Decimal units, the same ones a browser shows."""
    if n < 1024:
        return f"{n} B"
    for unit, div in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        if n < div * 1024:
            return f"{n / div:.1f} {unit}"
    return f"{n / 1024 ** 4:.1f} TB"


def load_sidecar(base):
    """assets/proof/metadata.json, or {} when it is absent or not a dict."""
    p = base / "metadata.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def title_from_name(name):
    """`part-1-answer-sheet.pdf` -> `Part 1 answer sheet` (last-resort label)."""
    stem = re.sub(r"[-_]+", " ", Path(name).stem).strip()
    stem = re.sub(r"\s+", " ", stem)
    return (stem[:1].upper() + stem[1:]) if stem else "Document"


def collect():
    """Every document on disk, first copy winning, with its sidecar corrections.

    `assets/img/proof/foo.png` loses to `assets/proof/foo.png` when both exist:
    the canonical folder is walked first and `seen` keeps its copy.
    """
    found, seen, sidecar = [], set(), {}
    for rel in DIRS:
        base = ROOT / rel
        if not base.is_dir():
            continue
        sidecar.update(load_sidecar(base))
        for p in sorted(base.iterdir()):
            if not p.is_file() or p.name.lower() == "metadata.json":
                continue
            if p.suffix.lower() not in IMAGE_EXT and p.suffix.lower() != ".pdf":
                continue
            if p.name in seen:
                continue
            seen.add(p.name)
            found.append((p, rel))
    return found, sidecar


def claim_slot(key, over):
    """Which slot a filename takes, an explicit `slot` in the sidecar winning.

    Falls back to the first slot whose token appears anywhere in the name, and
    finally to `None` - an unmatched document still ships, in `extra`, because
    "there is no slot for it" is not a reason to hide a proof.
    """
    forced = over.get("slot")
    if isinstance(forced, str):
        for s in SLOTS:
            if s["id"] == forced:
                return s
    for s in SLOTS:
        for k in s["keys"]:
            if k in key:
                return s
    return None


def build():
    """Scan the folders and write data/proof-manifest.json. Returns the manifest."""
    found, sidecar = collect()
    placed = {s["id"]: None for s in SLOTS}
    extra = []

    for p, rel in found:
        key = fold(p.name)
        over = sidecar.get(p.name)
        if not isinstance(over, dict):
            over = {}
        # `"hidden": true` in metadata.json keeps a file off every page
        # (a duplicate scan, a superseded copy) without deleting it.
        if over.get("hidden") is True:
            continue
        try:
            size = p.stat().st_size
        except OSError:                      # vanished mid-scan: not a document
            continue
        doc = {
            "file": f"{rel}/{p.name}".replace("\\", "/"),
            "name": p.name,
            "kind": "pdf" if p.suffix.lower() == ".pdf" else "image",
            "type": p.suffix.lower().lstrip(".").upper(),
            "bytes": size,
            "size": human_size(size),
            "uploaded": str(over.get("uploaded") or ""),
            "title": str(over.get("title") or ""),
            "note": str(over.get("note") or ""),
            "questions": [q for q in (over.get("questions") or [])
                          if isinstance(q, dict)],
        }
        slot = claim_slot(key, over)
        if slot is None:
            extra.append({"id": "", "slot": None,
                          "label": doc["title"] or title_from_name(p.name),
                          "required": False, "analytics": "", "doc": doc})
            continue
        if placed[slot["id"]] is None:
            placed[slot["id"]] = doc
        else:
            # Two files claim one slot: the first (alphabetical, sidecar-
            # overridden) holds the card, the rest become visible extras.
            extra.append({"id": f'{slot["id"]}-{key}', "slot": slot["id"],
                          "label": f"{slot['label']} · {doc['name']}",
                          "required": False, "analytics": "", "doc": doc})

    slots = []
    for s in SLOTS:
        doc = placed[s["id"]]
        if doc is None and s.get("optional"):
            continue
        slots.append({
            "id": s["id"],
            "slot": s["id"],
            "label": s["label"],
            "required": not s.get("optional"),
            "analytics": s["id"] if s["id"] in ("paper-1", "paper-2", "paper-3") else "",
            "doc": doc,
        })
    slots.extend(extra)

    manifest = {
        "$note": ("Generated by scripts/proof_documents.py from assets/proof/ - "
                  "never hand-edited. Add a scan, run `npm run publish`. "
                  "assets/proof/metadata.json supplies title/note/uploaded/questions."),
        "version": 1,
        "dirs": list(DIRS),
        "slots": slots,
        "total": len(found),
    }
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build()
    have = sum(1 for s in m["slots"] if s["doc"])
    print(f"proof: {m['total']} file(s), {have}/{len(m['slots'])} card(s) filled "
          f"-> data/proof-manifest.json")
