#!/usr/bin/env python3
"""
build_index.py — Python fallback of scripts/build-index.mjs
(Identical output. Use this if Node.js is not installed:
    python3 scripts/build_index.py
On Vercel the Node version runs automatically.)

Reads  questions/**/*.json  and generates:
    • data/index.json   (manifest the site consumes)
    • sitemap.xml       (SEO)

NEVER creates or modifies questions. Empty database = normal.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = ROOT / "questions"
DATA_DIR = ROOT / "data"

warnings = []


def humanize(i: str) -> str:
    return re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), re.sub(r"[-_]+", " ", i))


def read_json(p: Path):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


print("\n\U0001F50D House of Aspirants - building quiz index...\n")

site = read_json(DATA_DIR / "site.json") if (DATA_DIR / "site.json").exists() else {}
meta = read_json(DATA_DIR / "subjects.json") if (DATA_DIR / "subjects.json").exists() else {}

subjects = {}  # id -> dict


def ensure_subject(sid: str) -> dict:
    if sid not in subjects:
        subjects[sid] = {
            "id": sid, "name": humanize(sid), "short": humanize(sid),
            "icon": "\U0001F4D8", "color": "#6366f1", "description": "",
            "order": 99, "topics": [], "_topicsById": {},
        }
    return subjects[sid]


# --------------------------------------------------------------- 1. SCAN ---
question_files = []
if not QUESTIONS_DIR.exists():
    warnings.append("questions/ folder not found. Create it - subjects are detected from it.")
else:
    for folder in sorted(p for p in QUESTIONS_DIR.iterdir() if p.is_dir()):
        for f in sorted(folder.glob("*.json")):
            question_files.append((folder.name, f))

total_questions = 0
quiz_count = 0

for sid, full in question_files:
    rel = f"questions/{sid}/{full.name}"
    topic_id = full.stem
    try:
        data = read_json(full)
    except Exception as e:  # noqa: BLE001 - report any parse error, keep building
        warnings.append(f"{rel} - invalid JSON, skipped: {e}")
        continue

    questions = data if isinstance(data, list) else (
        data.get("questions") or data.get("mcqs") or data.get("quiz") or []
    )
    if not isinstance(questions, list):
        warnings.append(f'{rel} - "questions" must be an array. File skipped.')
        continue

    # Validate shape only (never inspect/generate content).
    ok = True
    for i, q in enumerate(questions, 1):
        opts = (q or {}).get("options") or (q or {}).get("opts")
        correct = None
        if isinstance(q, dict):
            correct = q.get("correct")
            if correct is None:
                correct = q.get("answer")
            if correct is None:
                correct = q.get("key")
        if not q or not (q.get("q") or q.get("question")):
            warnings.append(f'{rel} - Q{i} missing "q" text. Skipped file.')
            ok = False
        elif not isinstance(opts, list) or len(opts) < 2:
            warnings.append(f'{rel} - Q{i} needs an "options" array. Skipped file.')
            ok = False
        elif correct is None or correct == "":
            warnings.append(f'{rel} - Q{i} missing "correct" answer. Skipped file.')
            ok = False
    if not ok:
        continue

    subj = ensure_subject(sid)
    is_empty = len(questions) == 0
    name = topic_id
    description = ""
    time_limit = 0
    if isinstance(data, dict):
        name = data.get("topic") or data.get("title") or humanize(topic_id)
        description = data.get("description") or ""
        time_limit = int(data.get("timeLimit") or 0)

    subj["_topicsById"][topic_id] = {
        "id": topic_id, "name": name, "description": description,
        "file": f"questions/{sid}/{full.name}",
        "count": len(questions), "empty": is_empty,
        "available": not is_empty, "timeLimit": time_limit,
        "updatedAt": int(full.stat().st_mtime * 1000),
    }
    total_questions += len(questions)
    if not is_empty:
        quiz_count += 1

# ------------------------------------------- 2. REGISTER CONFIG SUBJECTS ---
for m in meta.get("subjects", []):
    if not m or "id" not in m:
        continue
    s = ensure_subject(m["id"])
    s.update({
        "name": m.get("name") or humanize(m["id"]),
        "short": m.get("short") or m.get("name") or humanize(m["id"]),
        "icon": m.get("icon") or "\U0001F4D8",
        "color": m.get("color") or "#6366f1",
        "description": m.get("description") or "",
        "order": m["order"] if isinstance(m.get("order"), int) else 99,
    })

# --------------------------------------------------------- 3. FINAL SHAPE ---
output = []
for s in subjects.values():
    topics = sorted(s.pop("_topicsById").values(),
                    key=lambda t: (t["name"].lower(), t["id"]))
    s["topics"] = topics
    output.append(s)
output.sort(key=lambda s: (s["order"], s["name"]))

count_topics = sum(len(s["topics"]) for s in output)

now = datetime.now(timezone.utc)
generated_at = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

index = {
    "version": 1,
    "generatedAt": generated_at,
    "stats": {
        "subjects": len(output),
        "topics": count_topics,
        "quizzes": quiz_count,
        "questions": total_questions,
        "studentsPracticed": int(site.get("studentsPracticed") or 0),
    },
    "site": site,
    "subjects": output,
}

DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "index.json").write_text(
    json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f'  \u2714 data/index.json - {len(output)} subjects, {count_topics} topics, '
      f'{quiz_count} quizzes, {total_questions} questions')
if total_questions == 0:
    print("  \u2139 Database is EMPTY (as intended). "
          "Add questions/<subject>/<topic>.json to publish a quiz.")

# ----------------------------------------------------------- 4. SITEMAP ----
if site.get("url"):
    base = str(site["url"]).rstrip("/")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # ONLY indexable URLs are listed. Local-only pages (bookmarks, progress,
    # result) declare noindex and must stay out of the sitemap.
    urls = [
        (f"{base}/", "1.0"), (f"{base}/mock", "0.9"),
        (f"{base}/leaderboard", "0.7"), (f"{base}/about", "0.6"),
        (f"{base}/contact", "0.6"), (f"{base}/privacy", "0.4"),
        (f"{base}/terms", "0.4"),
    ]
    for s in output:
        urls.append((f"{base}/subject?subject={s['id']}", "0.9"))
        for t in s["topics"]:
            if t["available"]:
                urls.append((f"{base}/quiz?subject={s['id']}&topic={t['id']}", "0.8"))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, p in urls:
        xml.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod>"
                   f"<changefreq>daily</changefreq><priority>{p}</priority></url>")
    xml.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")
    print(f"  \u2714 sitemap.xml - {len(urls)} URLs")

print("\n\u2705 Index build complete.\n")
for w in warnings:
    print(f"  \u26A0 {w}")
if warnings:
    # Same behaviour as the Node version: bad files are reported and skipped,
    # the build itself still succeeds (exit code 0).
    print(f"\n\u26A0\uFE0F {len(warnings)} warning(s) above - fix those JSON files "
          "so their quizzes publish.\n")
sys.exit(0)
