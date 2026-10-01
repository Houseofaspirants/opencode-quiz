#!/usr/bin/env python3
"""mcq_import.py | turn plain-text MCQs (English or Punjabi) into a quiz file.

Write your questions the way you already write them in notes, Word or a
Telegram post, save as .txt (or .docx), and run:

    python3 scripts/mcq_import.py my-polity-set.txt
    python3 scripts/mcq_import.py my-polity-set-pa.txt          # Punjabi copy
    python3 scripts/mcq_import.py my-set.txt --dry-run          # check only

Then `npm run publish` as usual - the quiz, its landing page, the sitemap and
the homepage cards all come from the file this script writes.

INPUT FORMAT (every label is optional except the questions themselves)
-----------------------------------------------------------------------
    Topic: Indian Constitution Part 1
    Subject: gk
    Category: polity
    Difficulty: Medium            <- default for every question below

    1. Which article abolishes untouchability?
    A) Article 14
    B) Article 17
    C) Article 21
    D) Article 32
    Answer: B
    Explanation: Article 17 abolishes untouchability.

    2. ਪੰਜਾਬ ਦੀ ਰਾਜਧਾਨੀ ਕਿਹੜੀ ਹੈ?
    (ੳ) ਅੰਮ੍ਰਿਤਸਰ
    (ਅ) ਚੰਡੀਗੜ੍ਹ
    (ੲ) ਲੁਧਿਆਣਾ
    (ਸ) ਜਲੰਧਰ
    ਉੱਤਰ: ਅ
    ਵਿਆਖਿਆ: ...

Accepted variations:
  * question numbers  1.  1)  Q1.  Q.1  Q1:  ਪ੍ਰਸ਼ਨ 1.
  * option labels     A)  (A)  A.  a)  (a)  ੳ)  (ੳ)  1)  (1)
  * answer lines      Answer: / Ans: / Correct: / ਉੱਤਰ: / ਸਹੀ ਉੱਤਰ:
                      followed by a letter (B), a Gurmukhi letter (ਅ), a
                      number (2) or the exact option text
  * or mark the right option with a trailing *  or  ✓  instead
  * Explanation: / Solution: / ਵਿਆਖਿਆ: / ਹੱਲ:  (may run over several lines)
  * Difficulty: Easy|Medium|Hard on its own line inside a question

WHERE THE FILE GOES
-------------------
    questions/<subject>/<category>/<slug>.json            (English)
    questions/<subject>/<category>/<slug>-punjabi.json    (Punjabi)

Language is detected from the text (Gurmukhi -> Punjabi) unless you pass
--lang. Give the English and Punjabi copies the same Topic: line and they
become ONE quiz with a language switch, exactly like the Sikhism sets. When
both copies exist, the script also checks they agree: same number of
questions and the same correct option for every question.

Standard library only - runs on any Mac with python3, no installs.
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QDIR = ROOT / "questions"

SUBJECTS = ("gk", "quant", "reasoning", "punjabi", "english", "computer",
            "current-affairs")

GURMUKHI = re.compile(r"[਀-੿]")

# Option letters in every script people use for MCQs. Index = option number.
LATIN = "abcdefgh"
GURMUKHI_LETTERS = ["ੳ", "ਅ", "ੲ", "ਸ", "ਹ", "ਕ"]

OPT_LABEL = r"(?:[A-Ha-h]|[1-8]|ੳ|ਅ|ੲ|ਸ|ਹ|ਕ)"
RE_OPTION = re.compile(
    rf"^\s*(?:\(\s*(?P<l1>{OPT_LABEL})\s*\)|(?P<l2>{OPT_LABEL})\s*[\).:\-])\s*(?P<text>.+?)\s*$")
RE_QUESTION = re.compile(
    r"^\s*(?:Q(?:uestion)?\.?\s*|ਪ੍ਰਸ਼ਨ\s*|ਸਵਾਲ\s*)?(?P<n>\d{1,4})\s*[\).:\-]\s*(?P<text>.+?)\s*$",
    re.IGNORECASE)
RE_ANSWER = re.compile(
    r"^\s*(?:answer|ans|correct(?:\s+answer)?|right\s+answer|key|ਸਹੀ\s*ਉੱਤਰ|ਸਹੀ\s*ਜਵਾਬ|ਉੱਤਰ|ਜਵਾਬ)\s*[:：\-–.]?\s*(?P<v>.+?)\s*$",
    re.IGNORECASE)
RE_EXPL = re.compile(
    r"^\s*(?:explanation|expl|solution|sol|reason|ਵਿਆਖਿਆ|ਹੱਲ|ਵਿਆਖਿਆ/ਹੱਲ)\s*[:：\-–]\s*(?P<v>.*)$",
    re.IGNORECASE)
RE_DIFF = re.compile(r"^\s*(?:difficulty|level|ਪੱਧਰ)\s*[:：\-]\s*(?P<v>.+?)\s*$",
                     re.IGNORECASE)
RE_HEADER = re.compile(
    r"^\s*(?P<k>topic|title|subject|category|difficulty|description|tags)\s*:\s*(?P<v>.*?)\s*$",
    re.IGNORECASE)
RE_KEY_HEAD = re.compile(
    r"^\s*(?:answer\s*key|answers|key|ਉੱਤਰ\s*ਕੁੰਜੀ|ਉੱਤਰ\s*ਮਾਲਾ|ਉੱਤਰ|ਜਵਾਬ)\s*[:：\-]?\s*$",
    re.IGNORECASE)
RE_KEY_PAIR = re.compile(rf"(\d{{1,4}})\s*[\.\-\):=]\s*\(?\s*({OPT_LABEL})\s*\)?(?![\w\u0A00-\u0A7F])")
RE_MARK = re.compile(r"\s*(?:\*|✓|✔|\(correct\)|\[correct\])\s*$", re.IGNORECASE)

DIFFICULTIES = {"easy": "Easy", "medium": "Medium", "moderate": "Medium",
                "hard": "Hard", "difficult": "Hard",
                "ਆਸਾਨ": "Easy", "ਸੌਖਾ": "Easy", "ਦਰਮਿਆਨਾ": "Medium", "ਔਖਾ": "Hard"}


def label_index(label):
    """'B' / 'b' / '2' / 'ਅ' -> 1."""
    label = label.strip().strip("()").strip()
    if not label:
        return None
    if label in GURMUKHI_LETTERS:
        return GURMUKHI_LETTERS.index(label)
    if label.isdigit():
        n = int(label)
        return n - 1 if 1 <= n <= 8 else None
    if len(label) == 1 and label.lower() in LATIN:
        return LATIN.index(label.lower())
    return None


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def read_source(path):
    """Text of a .txt/.md/.docx file. .docx is read with zipfile (no installs)."""
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        xml = re.sub(r"</w:p>", "\n", xml)
        xml = re.sub(r"<w:tab/>", "\t", xml)
        xml = re.sub(r"<w:br/>", "\n", xml)
        text = re.sub(r"<[^>]+>", "", xml)
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                     ("&quot;", '"'), ("&apos;", "'")):
            text = text.replace(a, b)
        return text
    return path.read_text(encoding="utf-8-sig")


def split_inline_options(line):
    """'A) x  B) y  C) z  D) w' on one line -> four option lines."""
    parts = re.split(r"\s+(?=\(?(?:[B-Hb-h]|ਅ|ੲ|ਸ|ਹ)\)\s)", line)
    if len(parts) >= 2 and all(RE_OPTION.match(p) for p in parts):
        return parts
    return [line]


def parse(text):
    """Return (header dict, list of raw question dicts, list of errors)."""
    header, questions, errors = {}, [], []
    key = {}          # answer key block at the end: {question number: label}
    in_key = False
    cur = None
    mode = None  # "q" (question continues), "expl" (explanation continues)

    lines = []
    for ln in text.splitlines():
        lines.extend(split_inline_options(ln.rstrip()))

    def close():
        if cur is not None:
            questions.append(cur)

    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            if mode == "q":
                mode = None
            continue

        if RE_KEY_HEAD.match(line) and cur is not None:
            in_key = True
            close()
            cur = None
            continue
        if in_key:
            pairs = RE_KEY_PAIR.findall(line)
            if pairs:
                for n, lab in pairs:
                    key[int(n)] = lab
                continue
            in_key = False

        m = RE_HEADER.match(line)
        if m and cur is None:
            header[m.group("k").lower()] = m.group("v")
            continue

        m = RE_QUESTION.match(line)
        # "1) text" is ambiguous: a new question, or option 1 of a set whose
        # options are numbered. Treat it as an option when the current
        # question has no answer yet, the number is the next option number,
        # earlier options (if any) were numbered too, and - for the very first
        # option - the question text ends like a question ("?" or ":").
        numbered_option = bool(
            m and cur is not None
            and cur["answer_raw"] is None and cur["marked"] is None
            and len(cur["options"]) < 4
            and not re.match(r"^\s*(q|ਪ੍ਰਸ਼ਨ|ਸਵਾਲ)", line, re.IGNORECASE)
            and int(m.group("n")) == len(cur["options"]) + 1
            and all(l.isdigit() for l in cur["labels"])
            and (cur["options"] or cur["question"].rstrip().endswith(("?", ":", "？", "।")))
        )
        if m and not numbered_option:
            close()
            cur = {"line": i, "n": int(m.group("n")), "question": m.group("text"),
                   "options": [], "labels": [], "answer_raw": None,
                   "marked": None, "explanation": "", "difficulty": None}
            mode = "q"
            continue

        if cur is None:
            continue

        m = RE_ANSWER.match(line)
        if m and cur["options"]:
            cur["answer_raw"] = m.group("v")
            mode = None
            continue

        m = RE_EXPL.match(line)
        if m:
            cur["explanation"] = m.group("v").strip()
            mode = "expl"
            continue

        m = RE_DIFF.match(line)
        if m:
            cur["difficulty"] = m.group("v")
            continue

        m = RE_OPTION.match(line)
        if m and mode != "expl":
            label = m.group("l1") or m.group("l2")
            text_ = m.group("text")
            if RE_MARK.search(text_):
                text_ = RE_MARK.sub("", text_)
                cur["marked"] = len(cur["options"])
            cur["options"].append(text_.strip())
            cur["labels"].append(label)
            mode = None
            continue

        if mode == "expl":
            cur["explanation"] = (cur["explanation"] + " " + line).strip()
        elif mode == "q" and not cur["options"]:
            cur["question"] += " " + line
        else:
            errors.append(f"line {i}: could not understand: {line[:70]}")

    close()
    for q in questions:
        if q["answer_raw"] is None and q["marked"] is None and q["n"] in key:
            q["answer_raw"] = key[q["n"]]
    return header, questions, errors


def resolve(raw, default_diff, topic, subject_label):
    """Raw dict -> site question dict, or (None, error)."""
    q = raw
    where = f"Q{q['n']} (line {q['line']})"
    opts = q["options"]
    if len(opts) < 2:
        return None, f"{where}: needs at least 2 options, found {len(opts)}"
    if len(opts) > 4:
        return None, f"{where}: has {len(opts)} options - the quiz shows at most 4"
    if len(set(o.strip().lower() for o in opts)) != len(opts):
        return None, f"{where}: two options are the same"

    ans = None
    if q["answer_raw"]:
        v = q["answer_raw"].strip()
        # "B", "(b)", "B) Article 17", "ਅ", "2"
        m = re.match(rf"^\(?\s*({OPT_LABEL})\s*\)?(?:[\).:\-\s]|$)", v)
        if m:
            ans = label_index(m.group(1))
        if ans is None:
            for k, o in enumerate(opts):
                if v.strip().lower() == o.strip().lower():
                    ans = k
                    break
    if ans is None and q["marked"] is not None:
        ans = q["marked"]
    if ans is None:
        return None, f"{where}: no answer found (add 'Answer: B' or mark the option with *)"
    if ans >= len(opts):
        return None, f"{where}: answer points to option {ans + 1} but there are only {len(opts)}"

    diff = DIFFICULTIES.get((q["difficulty"] or default_diff or "").strip().lower(),
                            None)
    out = {
        "id": 0,
        "subject": subject_label,
        "topic": topic,
        "difficulty": diff or "Medium",
        "question": re.sub(r"\s+", " ", q["question"]).strip(),
        "options": opts,
        "answer": ans,
    }
    if q["explanation"]:
        out["explanation"] = q["explanation"]
    return out, None


def find_sibling(dest, lang):
    """The other-language copy of `dest`, if it exists."""
    stem = dest.stem
    if lang == "pa":
        base = re.sub(r"-punjabi$", "", stem)
        cand = [dest.with_name(base + ".json"), dest.with_name(base + "-en.json")]
    else:
        base = re.sub(r"-en$", "", stem)
        cand = [dest.with_name(base + "-punjabi.json"), dest.with_name(base + "-pa.json")]
    return next((c for c in cand if c.exists()), None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", type=Path, help=".txt / .md / .docx file of MCQs")
    ap.add_argument("--subject", help=f"one of {', '.join(SUBJECTS)} (or Subject: line)")
    ap.add_argument("--category", help="GK category folder, e.g. polity (or Category: line)")
    ap.add_argument("--topic", help="quiz title (or Topic: line)")
    ap.add_argument("--lang", choices=("en", "pa"), help="force language (default: detect)")
    ap.add_argument("--slug", help="file name without .json (default: from topic)")
    ap.add_argument("--dry-run", action="store_true", help="check only, write nothing")
    ap.add_argument("--skip-bad", action="store_true",
                    help="write the valid questions even if some were rejected")
    ap.add_argument("--force", action="store_true", help="overwrite an existing file")
    a = ap.parse_args(argv)

    if not a.source.is_file():
        sys.exit(f"✗ file not found: {a.source}")

    text = read_source(a.source)
    header, raw, errors = parse(text)

    subject = (a.subject or header.get("subject") or "").strip().lower()
    category = slugify(a.category or header.get("category") or "")
    topic = (a.topic or header.get("topic") or header.get("title") or "").strip()
    if not topic:
        topic = re.sub(r"[-_]+", " ", a.source.stem).strip().title()
    lang = a.lang or ("pa" if len(GURMUKHI.findall(text)) > len(text) * 0.05 else "en")

    if subject not in SUBJECTS:
        sys.exit(f"✗ subject must be one of: {', '.join(SUBJECTS)} "
                 f"(add 'Subject: gk' at the top, or --subject gk)")
    if subject == "gk" and not category:
        subj_json = json.loads((ROOT / "data" / "subjects.json").read_text("utf-8"))
        subj_list = subj_json if isinstance(subj_json, list) else subj_json.get("subjects", [])
        cats = next((s.get("categories") for s in subj_list if s.get("id") == "gk"), []) or []
        names = ", ".join(c["folder"] if isinstance(c, dict) else slugify(c) for c in cats)
        sys.exit(f"✗ GK needs a category (add 'Category: polity'). Options: {names}")

    subject_label = header.get("subject_label") or topic.split(" Part")[0].split(" - ")[0]
    warnings = []
    questions = []
    for q in raw:
        item, err = resolve(q, header.get("difficulty"), topic, subject_label)
        if err:
            errors.append(err)
        else:
            questions.append(item)
    for k, q in enumerate(questions, 1):
        q["id"] = k

    nums = [q["n"] for q in raw]
    if nums and nums != list(range(nums[0], nums[0] + len(nums))):
        warnings.append(f"question numbers are not in sequence: {nums[:30]}"
                      " - a question may have been merged into another")

    seen = {}
    for q in questions:
        key = re.sub(r"\W+", "", q["question"].lower())
        if key in seen:
            warnings.append(f"Q{q['id']} repeats Q{seen[key]}: {q['question'][:60]}")
        seen.setdefault(key, q["id"])

    slug = slugify(a.slug or topic)
    folder = QDIR / subject / category if category else QDIR / subject
    dest = folder / (f"{slug}-punjabi.json" if lang == "pa" else f"{slug}.json")

    print(f"\n  Topic     {topic}")
    print(f"  Language  {'Punjabi' if lang == 'pa' else 'English'}")
    print(f"  Questions {len(questions)} ready, {len(raw) - len(questions)} rejected")
    print(f"  File      {dest.relative_to(ROOT)}")
    if questions:
        spread = {}
        for q in questions:
            spread["ABCD"[q["answer"]]] = spread.get("ABCD"[q["answer"]], 0) + 1
        print("  Answers   " + "  ".join(f"{k}:{spread.get(k, 0)}" for k in "ABCD"))
        top = max(spread.values())
        if len(questions) >= 10 and top / len(questions) > 0.5:
            warnings.append("more than half the answers are the same letter - "
                          "check the answer key, or shuffle options")

    sibling = find_sibling(dest, lang)
    if sibling and questions:
        try:
            other = json.loads(sibling.read_text("utf-8"))
            other = other if isinstance(other, list) else other.get("questions", [])
            if len(other) != len(questions):
                errors.append(f"{sibling.name} has {len(other)} questions, this file has "
                              f"{len(questions)} - both languages should match")
            else:
                bad = [str(i + 1) for i, (x, y) in enumerate(zip(other, questions))
                       if isinstance(x.get("answer"), int) and x.get("answer") != y["answer"]]
                if bad:
                    errors.append(f"answer differs from {sibling.name} on Q{', Q'.join(bad)}")
                else:
                    print(f"  Pair      matches {sibling.name} (same count, same answers)")
        except (OSError, ValueError):
            pass

    if warnings:
        print("\n  Worth a look (file is still written):")
        for w in warnings:
            print(f"   · {w}")
    if errors:
        print("\n  Must fix:")
        for e in errors:
            print(f"   ! {e}")

    if not questions:
        sys.exit("\n✗ nothing to write")
    if errors and not a.skip_bad:
        sys.exit("\n✗ nothing written - fix the lines above and run again "
                 "(or --skip-bad to write only the good questions)")
    if a.dry_run:
        print("\n  Dry run - nothing written.")
        return 0
    if dest.exists() and not a.force:
        sys.exit(f"\n✗ {dest.relative_to(ROOT)} already exists - use --force to replace it")

    folder.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\n✓ wrote {dest.relative_to(ROOT)}  →  now run: npm run publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
