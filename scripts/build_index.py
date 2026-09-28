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
from urllib.parse import quote

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


# --------------------------------------------------------------- languages --
# A language bucket is a folder named for the language of the files inside it
# (questions/<subject>/<Language>/…).  It is a TRANSLATION axis, not a
# syllabus category: "Punjabi" is not a lane of Current Affairs, it is the same
# content in another language.  Two translations of one set are paired up by
# resolve_language_pairs() below and shipped as ONE topic carrying variants.
LANG_FOLDERS = {
    "english": "en", "eng": "en", "en": "en",
    "punjabi": "pa", "panjabi": "pa", "pa": "pa", "gurmukhi": "pa",
}


def lang_code(dirname):
    """'Punjabi' | 'English' | 'pa' -> 'pa' | 'en', else None.
    The .strip() keeps legacy folders that once shipped with a trailing space
    classified correctly (see git history for 'English ')."""
    key = str(dirname).strip().lower()
    return LANG_FOLDERS.get(key) or LANG_FOLDERS.get(slug(dirname))


# A language can also be written into a FILE name, which is how a translation
# that has no folder of its own ships:
#     questions/gk/punjab-gk/sikhism-part1-20-mcqs.json          (English)
#     questions/gk/punjab-gk/sikhism-part1-20-mcqs-punjabi.json  (Punjabi)
#     questions/gk/punjab-gk/sikhism-part1-20-mcqs.hi.json       (Hindi)
# The dotted form takes ANY 2-3 letter code, so a new language is data-only:
# drop `topic.ta.json` next to `topic.en.json` and Tamil is available, with no
# table below to extend. The word form needs a table because `…-mcq` and
# `…-ta` are indistinguishable by shape alone.
LANG_WORDS = {
    "english": "en", "eng": "en", "en": "en",
    "punjabi": "pa", "panjabi": "pa", "gurmukhi": "pa", "pa": "pa",
    "hindi": "hi", "hi": "hi",
    "tamil": "ta", "ta": "ta",
    "marathi": "mr", "mr": "mr",
    "gujarati": "gu", "gu": "gu",
}
MARKER_RX = re.compile(r"[-_](" + "|".join(LANG_WORDS) + r")$", re.I)
DOTTED_RX = re.compile(r"\.([a-z]{2,3})$")
# Not languages, even though they are 2-3 letters (`sikhism.pdf.json`).
NON_LANG_SUFFIXES = {"pdf", "txt", "doc", "md", "csv", "xml", "zip"}


def lang_from_stem(stem):
    """`('sikhism-part1-20-mcqs', 'pa')` from `sikhism-part1-20-mcqs-punjabi`.

    Both markers sit at the END of the stem (never a token in the middle of
    one) and may stack (`topic-punjabi.en`), so this runs until there is left
    to strip; a dotted code wins over a word marker when both appear.

    -> (base, lang), where `base` is what the topic's id is built from: the
    file name with its language removed, so no topic id ever carries one.
    """
    base, word_lang, dotted_lang = stem, "", ""
    for _ in range(4):
        m = DOTTED_RX.search(base)
        if m and m.group(1) not in NON_LANG_SUFFIXES:
            dotted_lang, base = m.group(1), base[:m.start()]
            continue
        m = MARKER_RX.search(base)
        if m:
            if not dotted_lang:
                word_lang = LANG_WORDS[m.group(1).lower()]
            base = base[:m.start()]
            continue
        break
    return base, dotted_lang or word_lang


def lang_files(subject_id, subject_dir, bucket):
    """Every .json under a language bucket, directly or one folder deeper.

    The repo has both shapes in use:
        questions/current-affairs/Punjabi/*.json
        questions/current-affairs/English/july/*.json
    Returns [(full_path, rel_path), …] in a deterministic order so the Python
    and Node twins walk the folders identically.
    """
    base = os.path.join(subject_dir, bucket)
    out = []
    for fname in sorted(f for f in os.listdir(base) if f.endswith(".json")):
        out.append((os.path.join(base, fname),
                    f"questions/{subject_id}/{bucket}/{fname}"))
    for d in sorted(x for x in os.listdir(base)
                    if os.path.isdir(os.path.join(base, x))):
        sub_base = os.path.join(base, d)
        for fname in sorted(f for f in os.listdir(sub_base) if f.endswith(".json")):
            out.append((os.path.join(sub_base, fname),
                        f"questions/{subject_id}/{bucket}/{d}/{fname}"))
    return out


PART_RX = re.compile(r"part[-_ ]?(\d+)", re.I)


def set_topic_of(data):
    """The name of a whole question SET.

    The house format is a bare array of questions, where `topic` sits on every
    question rather than on the file - so look at the file first, then fall
    back to question 0.
    """
    if isinstance(data, dict):
        return str(data.get("topic") or data.get("title") or "")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return str(data[0].get("topic") or data[0].get("title") or "")
    return ""


def set_key(data, base):
    """The JSON-topic + part identity of one question set: `…-2026/part1`.

    'current-affairs-july-2026-part1-geography-environment' (en) and
    'current-affairs-july-2026-part1-punjabi' (pa) describe the same set even
    though their stems differ everywhere but the part token, so this key - not
    the stem - is what links them. Empty when the file carries no part token:
    those are covered by the stem key (language markers removed) instead.
    """
    m = PART_RX.search(base)
    if not m:
        return ""
    topic = slug(set_topic_of(data))
    part = f"part{int(m.group(1))}"
    return f"{topic}/{part}" if topic else part


def questions_of(data):
    """The question array inside a file, whichever house shape it uses."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        q = data.get("questions") or data.get("mcqs") or data.get("quiz")
        return q if isinstance(q, list) else []
    return []


def variant_title(data, stem_id, part, set_topic):
    """The title one translation of a set carries - the rule the record loop
    has always used for the primary file, applied to every translation too."""
    if isinstance(data, dict):
        name = data.get("topic") or data.get("title") or humanize(stem_id)
    else:
        name = humanize(stem_id)
    # Parts 1-4 of one month all carry the same JSON "topic", so without this
    # they would be four identically named cards - and four identical <title>s.
    if part and set_topic:
        name = f"{set_topic} - Part {part}"
    return name


def answer_index(qd, opts):
    """The option a question marks correct, resolved the way the site does it:
    an int index, a letter, or the option's own text."""
    value = None
    for key in ("correct", "answer", "key"):
        if qd.get(key) not in (None, ""):
            value = qd.get(key)
            break
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 1 and text.isalpha():
            letter = ord(text.upper()) - 65
            if 0 <= letter < len(opts):
                return letter
        for i, opt in enumerate(opts):
            if str(opt).strip().lower() == text.lower():
                return i
        return text
    return value


def translation_problem(primary, other):
    """The first way two translations of one set disagree, as one sentence.

    Question count, question ids, answer and option count must line up or a
    language switch would silently point saved answers at a different
    question. A warning only - a partial translation must never take the site
    down - and never more than one line per pair, so a broken pair cannot bury
    the build log.
    """
    a, b = primary["questions"], other["questions"]
    rel_a, rel_b = primary["item"]["rel"], other["item"]["rel"]
    if len(a) != len(b):
        return f"{rel_b} has {len(b)} questions, {rel_a} has {len(a)}"
    for i, (qa, qb) in enumerate(zip(a, b), 1):
        da = qa if isinstance(qa, dict) else {}
        db = qb if isinstance(qb, dict) else {}
        ida, idb = da.get("id"), db.get("id")
        if isinstance(ida, int) != isinstance(idb, int):
            return f"{rel_b} Q{i} has an id in only one of the two files"
        if isinstance(ida, int) and ida != idb:
            return f"{rel_b} Q{i} carries id {idb}, {rel_a} has {ida}"
        opts_a = da.get("options") or da.get("opts") or []
        opts_b = db.get("options") or db.get("opts") or []
        opts_a = opts_a if isinstance(opts_a, list) else []
        opts_b = opts_b if isinstance(opts_b, list) else []
        if len(opts_a) != len(opts_b):
            return (f"{rel_b} Q{i} has {len(opts_b)} options, "
                    f"{rel_a} has {len(opts_a)}")
        if answer_index(da, opts_a) != answer_index(db, opts_b):
            return (f"{rel_b} Q{i} answers differently from {rel_a} "
                    f"(the two files disagree on the correct option)")
    return ""


GURMUKHI_RX = re.compile(r"[\u0a00-\u0a7f]")


def has_gurmukhi(questions):
    """True when the questions are written in Gurmukhi script.

    Used only for files that did NOT come from a language folder, where the
    folder name gives no signal. Script is an observed property of the text,
    not a guess about intent.
    """
    for q in questions:
        qd = q if isinstance(q, dict) else {}
        opts = qd.get("options") or qd.get("opts") or []
        if not isinstance(opts, list):
            opts = []
        text = " ".join([str(qd.get("question") or qd.get("q") or ""),
                         str(qd.get("explanation") or "")]
                        + [str(o) for o in opts])
        if GURMUKHI_RX.search(text):
            return True
    return False


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
    """st_mtime in WHOLE milliseconds (nanoseconds truncated).

    The Node twin (scripts/build-index.mjs) must emit the same bytes, and a
    sub-millisecond float never round-trips identically through two JSON
    writers: `1790441705167.7627` (Python) vs `1790441705167.763` (JS) is
    enough to fail the parity gate in scripts/ci.sh step 3.
    """
    return os.stat(full).st_mtime_ns // 1_000_000


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

        # Peel language buckets off BEFORE the flat/hierarchical decision: a
        # folder named for a language holds translations of one question set
        # ("Punjabi" is not a syllabus lane of Current Affairs), so it must
        # never become a category or decide the subject's layout. An explicit
        # category with the same name still wins.
        configured = set()
        for c in cfg_cats or []:
            for k in (c.get("folder"), c.get("name"), c.get("id")):
                if k:
                    configured.add(slug(k))
        lang_buckets = [d for d in sub_dirs
                        if lang_code(d) and slug(d) not in configured]
        if lang_buckets:
            sub_dirs = [d for d in sub_dirs if d not in lang_buckets]
            for bucket in lang_buckets:
                for full, rel in lang_files(subject_id, subject_dir, bucket):
                    question_files.append({
                        "subjectId": subject_id,
                        "file": os.path.basename(full),
                        "full": full,
                        "rel": rel,
                        "lang": lang_code(bucket),
                    })

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

# ------------------------------ 3b. PAIR THE TRANSLATIONS OF ONE SET ------
def resolve_language_pairs(items):
    """Collapse every translation of one question set to a single topic.

    A Punjabi file and its English twin describe the SAME questions, so
    shipping both as separate topics would double the library and put two
    near-identical cards on the page. The primary file becomes the topic and
    its siblings ride along as `variants` - which is also what gives the quiz
    page a language switch without leaving the question you are on.

    Two files are linked inside one subject+category when EITHER key matches:
      * their stems are the same once language markers are removed
        (`sikhism-part1-20-mcqs` / `sikhism-part1-20-mcqs-punjabi`), or
      * their JSON topic + part token match
        (`…-part1-geography-environment` / `…-part1-punjabi`).
    The stem key is what pairs files that live in a CATEGORY folder, which the
    language-bucket pass never sees; the set key pairs folders whose stems
    differ everywhere but the part number.

    Files in the SAME language are never linked: two English files sharing a
    key are two topics (or a duplicate to be warned about), never a pair - so
    grouping can add a translation to a set but can never swallow a file.
    """
    staged = []
    for item in items:
        base, marker_lang = lang_from_stem(re.sub(r"\.json$", "", item["file"]))
        lang = item.get("lang") or marker_lang
        try:
            data = read_json(item["full"])
        except Exception:
            data = None  # the record loop reports the parse error for us
        questions = questions_of(data)
        # No folder and no marker: the script the questions are written in is
        # the only honest signal left (see has_gurmukhi).
        lang = lang or ("pa" if has_gurmukhi(questions) else "en")
        part_m = PART_RX.search(base)
        item["lang"] = lang          # the record loop reads these two
        item["base"] = base
        staged.append({
            "item": item, "lang": lang, "base": base,
            "data": data, "questions": questions,
            "part": int(part_m.group(1)) if part_m else 0,
            "topic": set_topic_of(data),
        })

    # --- union-find over the two keys, refusing any union that would put two
    # files of one language in the same group -----------------------------
    parent = list(range(len(staged)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    root_langs = {i: {s["lang"]} for i, s in enumerate(staged)}

    def keys_for(st):
        scope = f'{st["item"]["subjectId"]}|{st["item"].get("categoryId") or ""}'
        set_key_value = set_key(st["data"], st["base"])
        return (f"{scope}|stem:{slug(st['base'])}",
                f"{scope}|set:{set_key_value}" if set_key_value else None)

    claimed = {}
    for pos, st in enumerate(staged):
        for key in keys_for(st):
            if key is None:
                continue
            other = claimed.setdefault(key, pos)
            if other == pos or staged[other]["lang"] == st["lang"]:
                continue                      # one language = one file per key
            a, b = find(other), find(pos)
            if a == b or (root_langs[a] & root_langs[b]):
                continue                      # joining would collide a language
            if b < a:
                a, b = b, a                   # lower position roots the group
            parent[b] = a
            root_langs[a] = root_langs[a] | root_langs.pop(b, set())

    out, emitted = [], set()
    for pos in range(len(staged)):
        root = find(pos)
        if root in emitted:
            continue
        emitted.add(root)
        members = [staged[p] for p in range(len(staged)) if find(p) == root]
        if len(members) == 1:
            out.append(members[0]["item"])    # nothing to pair: file untouched
            continue
        # Every translation, ordered so both twins build the same bytes.
        members.sort(key=lambda m: (m["lang"], m["item"]["file"]))
        # The English file owns the topic id/URL when it exists (descriptive
        # stems); the QUIZ page still decides what to SHOW from the reader's
        # language preference, which defaults to Punjabi.
        primary = next((m for m in members if m["lang"] == "en"), members[0])
        for m in members:
            if m is primary:
                continue
            problem = translation_problem(primary, m)
            if problem:
                warn(f"Translation mismatch: {problem}")
        variants = {}
        for m in members:
            variants.setdefault(m["lang"], m["item"]["rel"])
        it = dict(primary["item"])
        it["variants"] = variants
        it["part"] = primary["part"]
        it["setTopic"] = primary["topic"]
        # Each translation's OWN title and question count: the manifest shows
        # what a reader would really get in each language, and the counts are
        # the numbers the mismatch warning above compares.
        it["titles"] = {m["lang"]: variant_title(m["data"], m["base"],
                                                 m["part"], m["topic"])
                        for m in members}
        it["counts"] = {m["lang"]: len(m["questions"]) for m in members}
        out.append(it)
    return out


question_files = resolve_language_pairs(question_files)

total_questions = 0
quiz_count = 0

for item in question_files:
    subject_id = item["subjectId"]
    rel = item["rel"]
    full = item["full"]
    category_id = item.get("categoryId")
    # ONE id per topic, and never a language inside it: `…-punjabi` is the
    # same topic as its English twin, so the id comes from the marker-stripped
    # stem the pairing pass worked out (quiz?subject=…&topic=<this>).
    topic_id = item.get("base") or re.sub(r"\.json$", "", item["file"])

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
        description = data.get("description") or ""
        time_limit = number(data.get("timeLimit"))
    else:
        description = ""
        time_limit = 0

    # Parts 1-4 of one month all carry the same JSON "topic", so without this
    # they would be four identically named cards - and four identical <title>s.
    name = variant_title(data, topic_id, item.get("part") or 0,
                         item.get("setTopic") or "")

    # Language: a folder named for it is authoritative, then the file name,
    # then - for a file carrying neither - the script the questions are
    # written in. `variants` lists the translations that really exist on disk
    # - every badge and the quiz page's language switch are driven by this
    # field, never by an assumption.
    lang = item.get("lang") or ("pa" if has_gurmukhi(questions) else "en")
    variants = item.get("variants") or {lang: rel}
    # One topic object, every language it ships in - the shape the manifest
    # and the front end both read:
    #   { id: "sikhism-part1-20-mcqs", availableLanguages: ["en", "pa"] }
    titles = item.get("titles") or {lang: name}
    counts = item.get("counts") or {lang: len(questions)}

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
    record["language"] = lang
    record["variants"] = variants
    record["availableLanguages"] = sorted(variants)
    record["titles"] = titles
    record["counts"] = counts

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

# ---------------------------------------------- 4b. LANDING PAGE CROSS-REF
# data/landing-manifest.json is written by scripts/build_landing_pages.py.
# When a static landing page exists for an entity, its record carries a
# "landing" path so (a) the front-end canonicalises the query-string URL onto
# it and (b) the sitemap lists the clean URL instead. No manifest (or a page
# the generator has not built yet) keeps today's query-string behaviour.
LANDING = {}
land_path = os.path.join(DATA_DIR, "landing-manifest.json")
if os.path.exists(land_path):
    try:
        for _p in read_json(land_path).get("pages", []):
            _f = str(_p.get("file", ""))
            if _f.endswith(".html") and os.path.exists(os.path.join(ROOT, _f)):
                LANDING[(_p.get("type"), _p.get("entity"))] = "/" + _f[:-5]
            else:
                warn(f"landing-manifest: file missing for {_f or _p.get('url', '?')}")
    except Exception as e:
        warn(f"landing-manifest.json unreadable: {e}")


def _land(kind, entity):
    return LANDING.get((kind, entity))


for s in output_subjects:
    _lk = _land("subject", s["id"])
    if _lk:
        s["landing"] = _lk
    for c in s["categories"]:
        _lk = _land("category", f'{s["id"]}/{c["id"]}')
        if _lk:
            c["landing"] = _lk
        for t in c["topics"]:
            _lk = _land("quiz", f'{s["id"]}/{t["id"]}')
            if _lk:
                t["landing"] = _lk
    for t in s["topics"]:
        _lk = _land("quiz", f'{s["id"]}/{t["id"]}')
        if _lk:
            t["landing"] = _lk

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

# ------------------------------------------------------ 5b. QUIZ MANIFEST
# data/quiz-manifest.json is the multilingual TOPIC manifest: one entry per
# topic with its id, subject, the languages it ships in, its question count and
# each language's own title. It is derived from the exact records above in the
# same pass, so it can never drift from data/index.json, and it carries no
# timestamp - byte-stable, so both twins can be diffed on it in scripts/ci.sh.
# The site itself reads index.json (one request, no second fetch per page); this
# manifest is the flat contract for tooling and for future front ends.


def manifest_topic(s, t):
    return {
        "id": t["id"],
        "subject": s["id"],
        "category": t.get("category") or "",
        "availableLanguages": t["availableLanguages"],
        "count": t["count"],
        "counts": t["counts"],
        "titles": t["titles"],
        "variants": t["variants"],
    }


# One entry per TOPIC, once: a subject's `topics` list already holds its
# categorized topics too (they are also listed under `categories[].topics`), so
# walking only `s["topics"]` keeps every topic exactly once.
quiz_manifest = {"version": 1, "topics": [
    manifest_topic(s, t)
    for s in output_subjects
    for t in s["topics"]
]}

with open(os.path.join(DATA_DIR, "quiz-manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(quiz_manifest, fh, indent=2, ensure_ascii=False)

info(f'data/quiz-manifest.json - {len(quiz_manifest["topics"])} topic(s), '
     f'{sum(len(t["availableLanguages"]) for t in quiz_manifest["topics"])} translation(s)')

# ----------------------------------------------------------- 6. SITEMAP
if site.get("url"):
    base = str(site["url"]).rstrip("/")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # ONLY indexable URLs are listed. (bookmarks/progress/result are indexable
    # utility pages — the 404 page and runtime noindex modes stay out.)
    urls = [
        {"loc": f"{base}/", "p": "1.0"},
        {"loc": f"{base}/punjab-exams", "p": "0.9"},
        {"loc": f"{base}/faq", "p": "0.9"},
        {"loc": f"{base}/articles", "p": "0.8"},
        {"loc": f"{base}/mock", "p": "0.9"},
        {"loc": f"{base}/leaderboard", "p": "0.7"},
        {"loc": f"{base}/result", "p": "0.6"},
        {"loc": f"{base}/bookmarks", "p": "0.5"},
        {"loc": f"{base}/progress", "p": "0.5"},
        {"loc": f"{base}/about", "p": "0.6"},
        {"loc": f"{base}/contact", "p": "0.6"},
        {"loc": f"{base}/privacy", "p": "0.4"},
        {"loc": f"{base}/terms", "p": "0.4"},
        {"loc": f"{base}/editorial-policy", "p": "0.4"},
    ]
    # Study guides — config-driven from data/articles.json (same registry the
    # /articles hub, Related Articles modules and Article schema read).
    guides_path = os.path.join(DATA_DIR, "articles.json")
    if os.path.exists(guides_path):
        try:
            for a in read_json(guides_path).get("articles", []):
                page = str(a.get("url", ""))
                if page.endswith(".html") and os.path.exists(os.path.join(ROOT, page)):
                    urls.append({"loc": f"{base}/{page[:-5]}", "p": "0.7"})
                else:
                    warn(f"articles.json: page file missing for {a.get('id', '?')} ({page})")
        except Exception as e:
            warn(f"articles.json unreadable: {e}")
    # Study notes, magazine, strategy, live sessions, recruitment and PDFs -
    # config-driven from data/content-manifest.json (written by
    # scripts/build_content.py, which runs before this builder).
    content_path = os.path.join(DATA_DIR, "content-manifest.json")
    if os.path.exists(content_path):
        try:
            cm = read_json(content_path)
            for hub in cm.get("hubs", []):
                u, f = str(hub.get("url", "")), str(hub.get("file", ""))
                if u.startswith(base) and os.path.exists(os.path.join(ROOT, f)):
                    urls.append({"loc": u, "p": "0.8"})
                else:
                    warn(f"content-manifest: hub missing for {f or hub.get('collection', '?')}")
            for item in cm.get("items", []):
                u, f = str(item.get("url", "")), str(item.get("file", ""))
                if u.startswith(base) and os.path.exists(os.path.join(ROOT, f)):
                    urls.append({"loc": u, "p": "0.6"})
                else:
                    warn(f"content-manifest: page missing for {f or item.get('title', '?')}")
            # Generated index pages (archives.html today) - same contract as
            # hubs: the URL only ships when the file really exists on disk.
            for page in cm.get("pages", []):
                u, f = str(page.get("url", "")), str(page.get("file", ""))
                if u.startswith(base) and os.path.exists(os.path.join(ROOT, f)):
                    urls.append({"loc": u, "p": "0.7"})
                else:
                    warn(f"content-manifest: index page missing for {f or page.get('title', '?')}")
        except Exception as e:
            warn(f"content-manifest.json unreadable: {e}")
    for s in output_subjects:
        # Static landing page wins over the query-string variant; an entity the
        # generator has not built yet keeps the URL it has today.
        sl = _land("subject", s["id"])
        urls.append({"loc": (base + sl) if sl else f"{base}/subject?subject={s['id']}",
                     "p": "0.9"})
        for c in s["categories"]:
            cl = _land("category", f'{s["id"]}/{c["id"]}')
            urls.append({"loc": (base + cl) if cl
                         else f"{base}/subject?subject={s['id']}&category={c['id']}",
                         "p": "0.85"})
        for t in (x for x in s["topics"] if x["available"]):
            tl = _land("quiz", f'{s["id"]}/{t["id"]}')
            if tl:
                urls.append({"loc": base + tl, "p": "0.8"})
            else:
                # Mirrors encodeURIComponent() in build-index.mjs so the local
                # (Python) and deploy (Node) builders emit byte-identical XML.
                # (encodeURIComponent leaves A-Za-z0-9 and -_.!~*'() alone.)
                cat = ""
                if t.get("category"):
                    raw = str(t["category"])
                    cat = "&category=" + quote(raw, safe="-_.!~*'()")
                urls.append({"loc": f"{base}/quiz?subject={s['id']}&topic={t['id']}{cat}",
                             "p": "0.8"})
    # Landing pages with no query-string variant: topic guides, exam pages and
    # subject clusters. (Subject, category and quiz landing pages are covered
    # by the loops above.)
    for _kind, _path in sorted(LANDING.items()):
        if _kind[0] in ("topic", "exam", "cluster"):
            urls.append({"loc": base + _path,
                         "p": {"topic": "0.8", "exam": "0.85",
                               "cluster": "0.7"}[_kind[0]]})

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
