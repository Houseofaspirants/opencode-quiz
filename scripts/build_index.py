#!/usr/bin/env python3
"""
 ============================================================================
  HOUSE OF ASPIRANTS QUIZ PORTAL - AUTO INDEX BUILDER (Python fallback)
 ----------------------------------------------------------------------------
  Byte-for-shape identical output to scripts/build-index.mjs. Use this when
  Node is not installed:   python3 scripts/build_index.py

  Scans the  questions/  folder and generates:
    • data/index.json   -> the single manifest consumed by the front-end
    • sitemap.xml       -> SEO sitemap (rebuilt on every deploy)

  HIERARCHY (3 levels, config-driven):
      Subject  →  Category  →  Topic (one .json file)  →  Quiz

    • Categories come from data/subjects.json ("categories" key per subject).
      Subjects without that key keep the original FLAT layout:
      questions/<subject>/*.json  →  topics directly under the subject.
    • Topic files are ALWAYS auto-detected inside their folder:
        questions/gk/polity/constitution.json   →  Polity › Constitution
      Add a file = a topic card appears. Edit = updated. Delete = removed.
      No topic name is ever hardcoded.
    • A category folder that exists on disk but is missing from the config is
      auto-appended, so nothing you upload can stay invisible.

  ADMIN WORKFLOW (NO CODE, EVER):
    1. Drop a JSON file into a category folder, e.g.
         questions/gk/polity/constitution.json
    2. Push to GitHub  ->  Vercel runs this script automatically
    3. Subject › Category › Topic appears. Edit = update. Delete = removed.

  IMPORTANT:
    • This script NEVER creates, generates or modifies questions.
    • It only READS your files and counts them.
    • Errors never crash the build: bad files are reported and skipped.
 ============================================================================
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUESTIONS_DIR = os.path.join(ROOT, "questions")
DATA_DIR = os.path.join(ROOT, "data")

WARNINGS = 0


def warn(msg):
    global WARNINGS
    print(f"  \u26A0 {msg}")
    WARNINGS += 1


def info(msg):
    print(f"  \u2714 {msg}")


def _reject_constant(name):
    """JSON.parse rejects NaN / Infinity / -Infinity — so must we (parity)."""
    raise ValueError(f"Invalid JSON constant: {name}")


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh, parse_constant=_reject_constant)


def humanize(topic_id):
    """Mirror of build-index.mjs humanize(): 'punjabi-mcq-10' -> 'Punjabi Mcq 10'."""
    s = re.sub(r"[-_]+", " ", str(topic_id))
    return re.sub(r"\b([a-z])", lambda m: m.group(1).upper(), s)


def slug(text):
    """Mirror of build-index.mjs slug(): 'Geography & Environment' -> 'geography-environment'."""
    s = str(text).strip().lower()
    s = re.sub(r"[&/\\]+", " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def has_json(directory):
    return any(f.endswith(".json") for f in os.listdir(directory))


def number(value, default=0):
    """Mirror of JS Number(value) || default (NaN/0/falsy -> default)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f == 0 or f in (float("inf"), float("-inf")):  # NaN / 0 / inf
        return default
    return int(f) if f == int(f) else f


def mtime_ms(full):
    """st_mtime*1000 — emitted as an int when whole (matches JSON.stringify)."""
    ms = os.stat(full).st_mtime * 1000
    return int(ms) if ms == int(ms) else ms


def by_name(item):
    return (str(item["name"]).lower(), item["id"])


def iso_now():
    # JS new Date().toISOString() -> millisecond precision
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


print("\n\U0001F50D House of Aspirants - building quiz index...\n")

# ---------------------------------------------------------------- 1. CONFIG
site_path = os.path.join(DATA_DIR, "site.json")
subjects_path = os.path.join(DATA_DIR, "subjects.json")
site = read_json(site_path) if os.path.exists(site_path) else {}
meta = read_json(subjects_path) if os.path.exists(subjects_path) else {"subjects": []}


def config_subject(subject_id):
    for m in meta.get("subjects") or []:
        if isinstance(m, dict) and m.get("id") == subject_id:
            return m
    return None


def config_categories(subject_id):
    """Configured categories for a subject, or None when the subject has none.
    Accepts plain strings ('Polity') or objects ({name, folder, icon})."""
    m = config_subject(subject_id)
    cat_list = m.get("categories") if isinstance(m, dict) else None
    if not isinstance(cat_list, list):
        return None
    out = []
    seen = set()
    for raw in cat_list:
        if not raw:
            continue
        is_str = isinstance(raw, str)
        name = str(raw) if is_str else str(raw.get("name") or raw.get("id") or "").strip()
        if not name:
            continue
        if is_str:
            folder = slug(name)
            cat_id = slug(name)
            icon = ""
        else:
            folder = str(raw.get("folder") or raw.get("id") or slug(name)).strip()
            cat_id = str(raw.get("id") or slug(name)).strip()
            icon = str(raw.get("icon") or "")
        if cat_id in seen:
            continue
        seen.add(cat_id)
        out.append({"id": cat_id, "name": name, "folder": folder, "icon": icon})
    return out


# ------------------------------------------------- 2. SUBJECT CONTAINERS
subjects = {}  # id -> dict (insertion-ordered, like the JS Map)


def ensure_subject(subject_id, extra=None):
    if subject_id not in subjects:
        subjects[subject_id] = {
            "id": subject_id,
            "name": humanize(subject_id),
            "short": humanize(subject_id),
            "icon": "\U0001F4D8",
            "color": "#6366f1",
            "description": "",
            "order": 99,
            "topics": [],
            "categories": [],
            "_topicsById": {},
            "_cats": None,  # {folderKey: category} when hierarchical
        }
    if extra:
        subjects[subject_id].update(extra)  # updates in place: key order kept
    return subjects[subject_id]


def ensure_category(subject, key, preset=None):
    preset = preset or {}
    if subject["_cats"] is None:
        subject["_cats"] = {}
    if key not in subject["_cats"]:
        subject["_cats"][key] = {
            "id": preset.get("id") or key,
            "name": preset.get("name") or humanize(key),
            "folder": preset.get("folder") or "",
            "icon": preset.get("icon") or "\U0001F4C1",
            "topics": [],
            "_topicsById": {},
        }
    return subject["_cats"][key]


# --------------------------------------------- 3. SCAN questions/ FOLDER
#  Flat subject     : questions/<subject>/*.json
#  Hierarchical     : questions/<subject>/<category>/*.json
#  Every *.json file becomes exactly one Topic. No file = no topic.
question_files = []  # {subjectId, file, full, rel, categoryId?}

if not os.path.isdir(QUESTIONS_DIR):
    warn("questions/ folder not found. Create it - subjects are detected from it.")
else:
    top_entries = sorted(
        (e for e in os.listdir(QUESTIONS_DIR)
         if os.path.isdir(os.path.join(QUESTIONS_DIR, e))),
        key=lambda n: (n.lower(), n),
    )
    for subject_id in top_entries:
        subject_dir = os.path.join(QUESTIONS_DIR, subject_id)
        sub_dirs = sorted(
            d for d in os.listdir(subject_dir)
            if os.path.isdir(os.path.join(subject_dir, d))
        )

        cfg_cats = config_categories(subject_id)
        # JS: !!cfgCats — even an EMPTY list ("categories": []) means
        # hierarchical; only a MISSING key keeps the subject flat.
        hierarchical = cfg_cats is not None or any(
            has_json(os.path.join(subject_dir, d)) for d in sub_dirs
        )

        if not hierarchical:
            # ---- FLAT subject (unchanged original behaviour) ------------
            ensure_subject(subject_id)
            for fname in sorted(os.listdir(subject_dir)):
                if not fname.endswith(".json"):
                    continue
                question_files.append({
                    "subjectId": subject_id,
                    "file": fname,
                    "full": os.path.join(subject_dir, fname),
                    "rel": f"questions/{subject_id}/{fname}",
                })
            continue

        # ---- HIERARCHICAL subject: config order first, disk folders next
        subject = ensure_subject(subject_id)
        if cfg_cats:
            for c in cfg_cats:
                ensure_category(subject, slug(c["folder"]), c)

        for sub in sub_dirs:
            sub_path = os.path.join(subject_dir, sub)
            files = sorted(f for f in os.listdir(sub_path) if f.endswith(".json"))
            key = slug(sub)
            # Config match by slug(folder) | slug(name) | id — tolerant of naming.
            preset = None
            for c in cfg_cats or []:
                if slug(c["folder"]) == key or slug(c["name"]) == key or c["id"] == key:
                    preset = c
                    break
            if preset:
                cat = ensure_category(subject, slug(preset["folder"]), preset)
            else:
                cat = ensure_category(subject, key, {
                    "id": key,
                    "name": humanize(sub.strip()),
                    "folder": sub.strip(),
                    "icon": "",
                })
                if files:
                    info(f"{subject_id}/{sub}/ - not in subjects.json, auto-added as category \"{cat['name']}\"")
            for fname in files:
                question_files.append({
                    "subjectId": subject_id,
                    "file": fname,
                    "categoryId": cat["id"],
                    "full": os.path.join(sub_path, fname),
                    "rel": f"questions/{subject_id}/{sub}/{fname}",
                })

        # JSON sitting directly in a hierarchical subject's root: never hide it
        for fname in sorted(os.listdir(subject_dir)):
            if not fname.endswith(".json"):
                continue
            warn(
                f"{subject_id}/{fname} - not inside a category folder. "
                f"Move it into questions/{subject_id}/<category>/ so it shows under a category."
            )
            ensure_category(subject, "uncategorized", {
                "id": "uncategorized", "name": "Uncategorized", "folder": "",
            })
            question_files.append({
                "subjectId": subject_id,
                "file": fname,
                "categoryId": "uncategorized",
                "full": os.path.join(subject_dir, fname),
                "rel": f"questions/{subject_id}/{fname}",
            })

total_questions = 0
quiz_count = 0

for item in question_files:
    subject_id = item["subjectId"]
    rel = item["rel"]
    full = item["full"]
    category_id = item.get("categoryId")
    topic_id = re.sub(r"\.json$", "", item["file"])

    try:
        data = read_json(full)
    except Exception as err:  # invalid JSON, unreadable file
        warn(f"{rel} - invalid JSON, skipped: {err}")
        continue

    # Accept: [ ...questions ]  OR  { "questions": [ ... ] } OR { "mcqs": [...] }
    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict):
        questions = data.get("questions") or data.get("mcqs") or data.get("quiz") or []
    else:
        questions = []

    if not isinstance(questions, list):
        warn(f'{rel} - "questions" must be an array. File skipped.')
        continue

    # Validate shape only (we never look at, generate or judge answer content).
    ok = True
    for i, q in enumerate(questions):
        # Non-object entries (a bare string/number) behave the way JS does
        # property access on them: no crash, just the usual missing-q warnings.
        qd = q if isinstance(q, dict) else {}
        opts = qd.get("options") or qd.get("opts")
        correct = qd.get("correct")
        if correct is None:
            correct = qd.get("answer")
        if correct is None:
            correct = qd.get("key")
        if not q or not (qd.get("q") or qd.get("question")):
            warn(f'{rel} - Q{i + 1} missing "q" text. Skipped file.')
            ok = False
        elif not isinstance(opts, list) or len(opts) < 2:
            warn(f'{rel} - Q{i + 1} needs an "options" array. Skipped file.')
            ok = False
        elif correct is None or correct == "":
            warn(f'{rel} - Q{i + 1} missing "correct" answer. Skipped file.')
            ok = False
    if not ok:
        continue

    subject = ensure_subject(subject_id)
    is_empty = len(questions) == 0  # valid file, but 0 questions yet

    if isinstance(data, dict):
        name = data.get("topic") or data.get("title") or humanize(topic_id)
        description = data.get("description") or ""
        time_limit = number(data.get("timeLimit"))
    else:
        name = humanize(topic_id)
        description = ""
        time_limit = 0

    record = {
        "id": topic_id,
        "name": name,
        "description": description,
        "file": rel,
        "count": len(questions),
        "empty": is_empty,
        "available": not is_empty,  # an "available" quiz = one that has questions
        "timeLimit": time_limit,
        "updatedAt": mtime_ms(full),
    }
    if category_id:
        record["category"] = category_id

    if topic_id in subject["_topicsById"]:
        warn(f'{rel} - topic id "{topic_id}" already exists in subject "{subject_id}". Rename this file.')
    subject["_topicsById"][topic_id] = record

    target_cat = None
    if category_id and subject.get("_cats"):
        for c in subject["_cats"].values():
            if c["id"] == category_id:
                target_cat = c
                break
    if target_cat:
        if topic_id in target_cat["_topicsById"]:
            warn(f'{rel} - duplicate topic id in category "{target_cat["id"]}". Rename this file.')
        target_cat["_topicsById"][topic_id] = record

    total_questions += len(questions)
    if not is_empty:
        quiz_count += 1

# ------------------------------- 4. REGISTER SUBJECTS FROM CONFIG + FOLDERS
for m in meta.get("subjects") or []:
    if not isinstance(m, dict) or not m.get("id"):
        continue
    is_num = isinstance(m.get("order"), (int, float)) and not isinstance(m.get("order"), bool)
    s = ensure_subject(m["id"], {
        "name": m.get("name") or humanize(m["id"]),
        "short": m.get("short") or m.get("name") or humanize(m["id"]),
        "icon": m.get("icon") or "\U0001F4D8",
        "color": m.get("color") or "#6366f1",
        "description": m.get("description") or "",
        "order": m["order"] if is_num else 99,  # JS: typeof m.order === "number"
    })
    s["_fromConfig"] = True

# --------------------------------------------------------- 5. FINAL SHAPE
output_subjects = []
for s in subjects.values():
    topics = sorted(s["_topicsById"].values(), key=by_name)
    categories = []
    if s["_cats"]:
        for c in s["_cats"].values():
            c_topics = sorted(c["_topicsById"].values(), key=by_name)
            cat_out = {k: v for k, v in c.items() if k not in ("_topicsById",)}
            cat_out["topics"] = c_topics  # existing key: value replaced in place
            categories.append(cat_out)
    s.pop("_topicsById", None)
    s.pop("_cats", None)
    s.pop("_fromConfig", None)
    s["topics"] = topics        # existing keys: order kept (matches {...s, topics, categories})
    s["categories"] = categories
    output_subjects.append(s)

output_subjects.sort(key=lambda a: (a["order"], str(a["name"]).lower()))

count_topics = sum(len(s["topics"]) for s in output_subjects)
count_categories = sum(len(s["categories"]) for s in output_subjects)

index = {
    "version": 2,
    "generatedAt": iso_now(),
    "stats": {
        "subjects": len(output_subjects),
        "categories": count_categories,
        "topics": count_topics,          # every JSON file = one topic
        "quizzes": quiz_count,           # topics that currently hold questions
        "questions": total_questions,
        "studentsPracticed": number(site.get("studentsPracticed")),
    },
    "site": site,
    "subjects": output_subjects,
}

os.makedirs(DATA_DIR, exist_ok=True)
with open(os.path.join(DATA_DIR, "index.json"), "w", encoding="utf-8") as fh:
    # ensure_ascii=False matches JSON.stringify (emoji written raw); no trailing
    # newline matches the .mjs output byte-for-shape.
    json.dump(index, fh, indent=2, ensure_ascii=False)

info(
    f'data/index.json - {index["stats"]["subjects"]} subjects, '
    f'{index["stats"]["categories"]} categories, {index["stats"]["topics"]} topics, '
    f'{index["stats"]["quizzes"]} quizzes, {index["stats"]["questions"]} questions'
)
if index["stats"]["questions"] == 0:
    print("  \u2139 Database is EMPTY (as intended). Add questions/<subject>/<category>/<topic>.json to publish a quiz.")

# ----------------------------------------------------------- 6. SITEMAP
if site.get("url"):
    base = str(site["url"]).rstrip("/")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # ONLY indexable URLs are listed. (bookmarks/progress/result are indexable
    # utility pages — the 404 page and runtime noindex modes stay out.)
    urls = [
        {"loc": f"{base}/", "p": "1.0"},
        {"loc": f"{base}/mock", "p": "0.9"},
        {"loc": f"{base}/leaderboard", "p": "0.7"},
        {"loc": f"{base}/result", "p": "0.6"},
        {"loc": f"{base}/bookmarks", "p": "0.5"},
        {"loc": f"{base}/progress", "p": "0.5"},
        {"loc": f"{base}/about", "p": "0.6"},
        {"loc": f"{base}/contact", "p": "0.6"},
        {"loc": f"{base}/privacy", "p": "0.4"},
        {"loc": f"{base}/terms", "p": "0.4"},
    ]
    for s in output_subjects:
        urls.append({"loc": f"{base}/subject?subject={s['id']}", "p": "0.9"})
        for c in s["categories"]:
            urls.append({"loc": f"{base}/subject?subject={s['id']}&category={c['id']}", "p": "0.85"})
        for t in (x for x in s["topics"] if x["available"]):
            cat = f"&category={t['category']}" if t.get("category") else ""
            urls.append({"loc": f"{base}/quiz?subject={s['id']}&topic={t['id']}{cat}", "p": "0.8"})

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        loc = u["loc"].replace("&", "&amp;")
        lines.append(
            f'  <url><loc>{loc}</loc><lastmod>{today}</lastmod>'
            f'<changefreq>daily</changefreq><priority>{u["p"]}</priority></url>'
        )
    lines.append("</urlset>")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    info(f"sitemap.xml - {len(urls)} URLs")

print("\n\u2705 Index build complete.\n")
if WARNINGS > 0:
    print(f"\u26A0\uFE0F {WARNINGS} warning(s) above - fix those JSON files so their quizzes publish.\n")
