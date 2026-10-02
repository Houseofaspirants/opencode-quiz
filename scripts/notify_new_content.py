#!/usr/bin/env python3
"""notify_new_content.py | announce new uploads on the Telegram channel.

Runs in GitHub Actions after every push to main (.github/workflows/notify.yml).
It compares the site's generated manifests BEFORE and AFTER the push, finds
what is new - MCQ sets, study material, current affairs, PYQ papers, books -
and posts one Punjabi message per new item on the Telegram channel, with the
direct link to the page where it lives.

It also sends a plain-text copy of every message to the owner's own Telegram
chat (TELEGRAM_OWNER_CHAT_ID, optional) so it can be forwarded to WhatsApp in
one copy-paste - WhatsApp Channels have no official posting API.

    python3 scripts/notify_new_content.py --before <sha> [--after HEAD] [--dry-run]

Environment (GitHub repo -> Settings -> Secrets and variables -> Actions):
    TELEGRAM_BOT_TOKEN      secret - from @BotFather (the bot must be a channel admin)
    TELEGRAM_CHANNEL        variable, optional - default @HouseOfAspirant
    TELEGRAM_OWNER_CHAT_ID  variable, optional - your own chat id for the WhatsApp copy

Without a token it prints the messages and sends nothing, so it is safe to run
anywhere. Standard library only.
"""

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://houseofaspirants.in"
MAX_SINGLE = 5          # more new items than this in one push -> one digest message


# --------------------------------------------------------------- loading ----
def git_json(sha, path):
    """A JSON file as it was at commit `sha` ({} when it did not exist)."""
    if not sha or set(sha) == {"0"}:
        return {}
    try:
        out = subprocess.run(["git", "show", f"{sha}:{path}"], capture_output=True,
                             check=True).stdout
        return json.loads(out.decode("utf-8"))
    except (subprocess.CalledProcessError, ValueError):
        return {}


def quiz_sets(index):
    """{topic id: record} for every published MCQ set in data/index.json."""
    out = {}
    for s in index.get("subjects", []) or []:
        for t in s.get("topics", []) or []:
            if not t.get("available"):
                continue
            out[f'{s.get("id")}/{t.get("id")}'] = {
                "kind": "quiz",
                "title": t.get("name") or t.get("id"),
                "subject": s.get("name") or s.get("id"),
                "subject_id": s.get("id"),
                "count": t.get("count") or 0,
                "langs": sorted((t.get("variants") or {}).keys()),
                "url": SITE + (t.get("landing") or
                               f'/quiz?subject={s.get("id")}&topic={t.get("id")}'),
            }
    return out


def content_items(manifest):
    """{url: record} for study material, current affairs and PYQ pages."""
    out = {}
    items = manifest.get("items", []) or []
    if isinstance(items, dict):
        items = list(items.values())
    for it in items:
        url = it.get("url")
        if not url:
            continue
        out[url] = {
            "kind": it.get("collection") or "content",
            "title": it.get("title") or "",
            "lang": it.get("lang") or "",
            "url": url,
        }
    return out


def book_items(books):
    out = {}
    for b in books.get("books", []) or []:
        out[b.get("id")] = {"kind": "book", "title": b.get("title", ""),
                            "author": b.get("author", ""), "group": b.get("group", ""),
                            "url": f'{SITE}/book-{b.get("id")}'}
    return out


def collect(sha):
    return {
        "quiz": quiz_sets(git_json(sha, "data/index.json")),
        "content": content_items(git_json(sha, "data/content-manifest.json")),
        "book": book_items(git_json(sha, "data/books.json")),
    }


def new_items(before, after):
    found = []
    for group in ("quiz", "content", "book"):
        for key, rec in after[group].items():
            if key not in before[group]:
                found.append(rec)
    return merge_language_pairs(found)


def merge_language_pairs(items):
    """'…-en' and '…-pa' pages of the same material become one announcement."""
    out, seen = [], {}
    for it in items:
        if it["kind"] == "quiz":
            out.append(it)
            continue
        base = re.sub(r"-(en|pa|english|punjabi)$", "", it["url"].rstrip("/"))
        if base in seen:
            seen[base].setdefault("langs", []).append(it.get("lang"))
            continue
        it = dict(it, langs=[it.get("lang")] if it.get("lang") else [])
        seen[base] = it
        out.append(it)
    return out


# -------------------------------------------------------------- messages ----
HOOKS_QUIZ = [
    "🚨 ਨਵਾਂ ਟੈਸਟ LIVE ਹੋ ਗਿਆ! 🚨",
    "🔥 ਤਿਆਰੀ ਚੈੱਕ ਕਰਨ ਦਾ ਸਮਾਂ ਆ ਗਿਆ! 🔥",
    "⚡ ਨਵੇਂ Expected MCQs ਆ ਗਏ! ⚡",
    "🎯 ਅੱਜ ਦਾ ਚੈਲੰਜ ਤਿਆਰ ਹੈ! 🎯",
    "📢 ਪੇਪਰ ਤੋਂ ਪਹਿਲਾਂ ਇਹ ਟੈਸਟ ਜ਼ਰੂਰ ਦਿਓ! 📢",
    "🏆 Rank ਵਾਲੀ ਤਿਆਰੀ - ਨਵਾਂ ਸੈੱਟ LIVE! 🏆",
]
PUSH_QUIZ = [
    "ਕੀ ਤੁਸੀਂ {n} ਵਿੱਚੋਂ {target}+ ਲੈ ਸਕਦੇ ਹੋ? 🤔",
    "ਪੇਪਰ ਵਿੱਚ ਇਹੋ ਜਿਹੇ ਸਵਾਲ ਹੀ ਨੰਬਰ ਕੱਟਦੇ ਨੇ - ਹੁਣੇ ਆਪਣੀ ਗ਼ਲਤੀ ਲੱਭੋ 💪",
    "ਜੋ ਅੱਜ practice ਕਰੂ, ਓਹੀ merit list ਵਿੱਚ ਆਊ ✅",
    "ਸਿਰਫ਼ ਪੜ੍ਹਨਾ ਕਾਫ਼ੀ ਨਹੀਂ - ਟੈਸਟ ਦੇ ਕੇ ਦੇਖੋ ਕਿੰਨਾ ਯਾਦ ਹੈ 🧠",
    "ਤੁਹਾਡੇ ਮੁਕਾਬਲੇ ਵਾਲੇ ਇਹ ਟੈਸਟ ਦੇ ਰਹੇ ਨੇ - ਤੁਸੀਂ ਪਿੱਛੇ ਨਾ ਰਹੋ 🔥",
]
HOOKS_MATERIAL = [
    "📚 ਨਵਾਂ Study Material ਆ ਗਿਆ! 📚",
    "🆕 ਤਿਆਰੀ ਲਈ ਨਵੇਂ ਨੋਟਸ upload ਹੋ ਗਏ! 🆕",
    "📖 Exam-oriented ਨੋਟਸ - ਬਿਲਕੁਲ FREE! 📖",
    "✍️ Rank 2 ਵਾਲੇ ਤਰੀਕੇ ਨਾਲ ਬਣੇ ਨਵੇਂ ਨੋਟਸ! ✍️",
]
HOOKS_CA = [
    "🗞️ ਨਵਾਂ Current Affairs ਆ ਗਿਆ! 🗞️",
    "📰 Current Affairs - ਪੇਪਰ ਵਿੱਚ ਪੱਕੇ ਨੰਬਰ! 📰",
    "🔔 ਇਸ ਮਹੀਨੇ ਦੇ Current Affairs ਤਿਆਰ ਨੇ! 🔔",
]
HOOKS_PYQ = [
    "📜 ਪਿਛਲੇ ਸਾਲ ਦਾ ਪੇਪਰ upload ਹੋ ਗਿਆ! 📜",
    "🎯 ਅਸਲੀ ਪੇਪਰ ਦੇਖੋ - ਪਤਾ ਲੱਗੂ ਸਵਾਲ ਕਿਵੇਂ ਆਉਂਦੇ ਨੇ! 🎯",
]
HOOKS_BOOK = [
    "📕 Book shelf ਵਿੱਚ ਨਵੀਂ ਕਿਤਾਬ ਜੁੜੀ! 📕",
]
TAIL = "\n\n📲 ਦੋਸਤਾਂ ਨਾਲ share ਕਰੋ - ਤਿਆਰੀ ਮਿਲ ਕੇ ਹੁੰਦੀ ਹੈ!\n#HouseOfAspirants #PunjabPolice #PSSSB"


def pick(options, key):
    """The same item always gets the same line; different items get different ones."""
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest(), 16)
    return options[h % len(options)]


def lang_line(langs):
    langs = [l for l in langs if l]
    if "pa" in langs and "en" in langs:
        return "ਪੰਜਾਬੀ + English ਦੋਵਾਂ ਵਿੱਚ"
    if langs == ["pa"]:
        return "ਪੰਜਾਬੀ ਵਿੱਚ"
    if langs == ["en"]:
        return "English ਵਿੱਚ"
    return ""


def quiz_minutes(rec):
    secs = 60 if rec.get("subject_id") in ("reasoning", "quant") else 30
    return max(1, round(rec["count"] * secs / 60))


def message(rec):
    """(html_text, plain_text) for one new item."""
    e = html.escape
    k, url = rec["kind"], rec["url"]
    langs = lang_line(rec.get("langs") or [])
    if k == "quiz":
        n = rec["count"]
        lines = [f"<b>{pick(HOOKS_QUIZ, url)}</b>", "",
                 f"📝 <b>{e(rec['title'])}</b> ({n} MCQs)",
                 f"📘 ਵਿਸ਼ਾ: {e(rec['subject'])}"]
        if langs:
            lines.append(f"🌐 {langs}")
        lines += ["", pick(PUSH_QUIZ, url + "p").format(n=n, target=round(n * 0.8)), "",
                  f"⏱️ ਸਿਰਫ਼ {quiz_minutes(rec)} ਮਿੰਟ | ਹਰ ਜਵਾਬ ਦੀ ਵਿਆਖਿਆ | ਬਿਲਕੁਲ FREE",
                  "", f"👉 <b>ਹੁਣੇ ਟੈਸਟ ਦਿਓ:</b> {url}", "",
                  "ਆਪਣਾ score comment ਵਿੱਚ ਦੱਸੋ 👇"]
    elif k == "current-affairs":
        lines = [f"<b>{pick(HOOKS_CA, url)}</b>", "", f"🗞️ <b>{e(rec['title'])}</b>"]
        if langs:
            lines.append(f"🌐 {langs}")
        lines += ["", "Punjab Police, PSSSB, PPSC - ਹਰ ਪੇਪਰ ਵਿੱਚ Current Affairs ਦੇ ਪੱਕੇ ਨੰਬਰ ਹੁੰਦੇ ਨੇ। "
                  "ਪੜ੍ਹੋ, download ਕਰੋ ਅਤੇ revision ਲਈ ਰੱਖੋ 📥", "",
                  f"👉 <b>ਹੁਣੇ ਪੜ੍ਹੋ:</b> {url}"]
    elif k == "previous-year-questions":
        lines = [f"<b>{pick(HOOKS_PYQ, url)}</b>", "", f"📜 <b>{e(rec['title'])}</b>", "",
                 "ਜਿਹੜਾ ਪਿਛਲੇ ਪੇਪਰ ਸਮਝ ਲੈਂਦਾ ਹੈ, ਉਹ ਅਗਲਾ ਪੇਪਰ ਪਾਸ ਕਰ ਲੈਂਦਾ ਹੈ 💯", "",
                 f"👉 <b>ਪੇਪਰ ਦੇਖੋ:</b> {url}"]
    elif k == "book":
        lines = [f"<b>{pick(HOOKS_BOOK, url)}</b>", "", f"📕 <b>{e(rec['title'])}</b>",
                 f"✍️ {e(rec.get('author', ''))}", "",
                 f"ਕਿਉਂ ਪੜ੍ਹੀਏ ਅਤੇ ਕਿਸ ਲਈ ਹੈ - ਸਭ ਇੱਥੇ 👇", "", f"👉 {url}"]
    else:
        lines = [f"<b>{pick(HOOKS_MATERIAL, url)}</b>", "", f"📖 <b>{e(rec['title'])}</b>"]
        if langs:
            lines.append(f"🌐 {langs}")
        lines += ["", "ਪੜ੍ਹੋ, ਸਮਝੋ ਅਤੇ ਫਿਰ ਉਸੇ topic ਦੇ MCQs ਨਾਲ ਆਪਣੀ ਤਿਆਰੀ ਚੈੱਕ ਕਰੋ ✅", "",
                  f"👉 <b>ਹੁਣੇ ਖੋਲ੍ਹੋ:</b> {url}"]
    text = "\n".join(lines) + TAIL
    return text, re.sub(r"</?b>", "*", html.unescape(text)).replace("**", "")


def digest(items):
    lines = ["<b>🚀 House of Aspirants 'ਤੇ ਬਹੁਤ ਕੁਝ ਨਵਾਂ ਆ ਗਿਆ! 🚀</b>", ""]
    icons = {"quiz": "📝", "current-affairs": "🗞️", "previous-year-questions": "📜",
             "book": "📕"}
    for it in items[:15]:
        extra = f" ({it['count']} MCQs)" if it["kind"] == "quiz" else ""
        lines.append(f"{icons.get(it['kind'], '📖')} <b>{html.escape(it['title'])}</b>{extra}")
        lines.append(f"   👉 {it['url']}")
    if len(items) > 15:
        lines.append(f"…ਅਤੇ {len(items) - 15} ਹੋਰ - {SITE}")
    lines += ["", "ਸਭ ਕੁਝ ਬਿਲਕੁਲ FREE - ਅੱਜ ਹੀ ਸ਼ੁਰੂ ਕਰੋ 💪"]
    text = "\n".join(lines) + TAIL
    return text, re.sub(r"</?b>", "*", html.unescape(text)).replace("**", "")


# -------------------------------------------------------------- telegram ----
def send(token, chat, text, parse_html=True):
    data = {"chat_id": chat, "text": text, "disable_web_page_preview": "false"}
    if parse_html:
        data["parse_mode"] = "HTML"
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode(data).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("ok", False)
    except urllib.error.HTTPError as e:
        # Never print the URL - it contains the token.
        print(f"  ! Telegram refused the message ({e.code}): "
              f"{e.read().decode('utf-8', 'replace')[:200]}", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"  ! Telegram unreachable: {e.reason}", file=sys.stderr)
        return False


def wait_live(urls, limit=600):
    """Wait until the new pages answer 200 (Vercel deploys after the push)."""
    deadline = time.time() + limit
    pending = list(dict.fromkeys(urls))[:5]
    while pending and time.time() < deadline:
        still = []
        for u in pending:
            try:
                req = urllib.request.Request(u, method="HEAD",
                                             headers={"User-Agent": "HoA-notify"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    if r.status != 200:
                        still.append(u)
            except Exception:
                still.append(u)
        pending = still
        if pending:
            time.sleep(20)
    if pending:
        print(f"  ! still not live after {limit}s: {pending} - sending anyway")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--before", required=True, help="commit before the push")
    ap.add_argument("--after", default="HEAD", help="commit after the push")
    ap.add_argument("--dry-run", action="store_true", help="print, do not send")
    ap.add_argument("--wait-live", action="store_true",
                    help="wait for the new pages to be live before posting")
    a = ap.parse_args(argv)

    if not a.before or set(a.before) == {"0"}:
        print("First push of the branch - nothing to compare, nothing sent.")
        return 0

    items = new_items(collect(a.before), collect(a.after))
    if not items:
        print("No new MCQ set, material, current affairs, paper or book in this push.")
        return 0

    msgs = ([message(i) for i in items] if len(items) <= MAX_SINGLE
            else [digest(items)])
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.environ.get("TELEGRAM_CHANNEL", "").strip() or "@HouseOfAspirant"
    owner = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()
    dry = a.dry_run or not token

    print(f"{len(items)} new item(s) -> {len(msgs)} message(s) for {channel}"
          + (" [DRY RUN - nothing sent]" if dry else ""))
    if a.wait_live and not dry:
        wait_live([i["url"] for i in items])
    failed = 0
    for text, plain in msgs:
        print("-" * 60 + "\n" + text)
        if dry:
            continue
        if not send(token, channel, text):
            failed += 1
        if owner:
            send(token, owner, "📋 WhatsApp ਲਈ copy ਕਰੋ:\n\n" + plain, parse_html=False)
        time.sleep(2)            # stay well under Telegram's rate limit
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
