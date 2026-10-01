"""current_affairs.py | House of Aspirants - the Current Affairs section.

Current Affairs has exactly one home: the Current Affairs door in the top
navigation. Everything under it is discovered from the files on disk:

    content/current-affairs/<language>/<Month YYYY>/<file>.pdf
                       e.g. content/current-affairs/punjabi/August 2026/x.pdf

The two levels below the collection are the registration:

  * `<language>/`   - which language the issue is written in. The folder name
                      is the language, and one this site has never seen
                      becomes a language of its own on the next build;
  * `<Month YYYY>/` - which month the issue belongs to. It has to name both
                      the month and the year, because the URL promises both:
                      /current-affairs/punjabi/august-2026. A folder that
                      does not is warned about and its files still publish on
                      the language page - a month page is simply never
                      invented for a folder that never said when it was.

One build yields the whole section:

    /current-affairs                       - the hub, language chooser first
    /current-affairs/<language>            - Daily, Magazine, PDFs, Archives
    /current-affairs/<language>/<month>    - one month, newest first

Nothing here is a list anybody maintains: adding a month is a folder, adding a
file is a file, and `npm run publish` is the only command. The HTML is rendered
by scripts/build_content.py (the same place pyq/<exam>/index.html comes from),
because that is where the shared head, schema graph and chrome live.

Mirrors scripts/pyq_collection.py: one module build_content.py calls once,
returning page descriptors - no timestamps, so ci.sh's final
`git diff --exit-code` cannot drift on the clock.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://houseofaspirants.in"
BRAND = "House of Aspirants"
SOURCE = "content/current-affairs"
SEGMENT = SOURCE.split("/", 1)[1]           # "current-affairs"

MONTH_NUM = {name: i for i, name in enumerate((
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december"), 1)}

# Presentation order only - Punjabi first, then English. Every language found
# on disk still publishes; this decides which card comes first, and a folder
# nobody has named here falls through to alphabetical order after them.
LANGUAGE_ORDER = ("punjabi", "english")


def month_folder(folder):
    """'August 2026' -> ('august-2026', 'August 2026', 2026, 8); else ''.

    The month page publishes at /current-affairs/<language>/august-2026, so
    the folder has to carry both halves of that promise. A folder that does
    not says nothing about when its files belong to, and this build will not
    guess a date the publisher never wrote down."""
    m = re.match(r"^([A-Za-z]+)[\s_\-]+(\d{4})$", str(folder or "").strip())
    if not m:
        return "", "", 0, 0
    month, year = m.group(1), int(m.group(2))
    key = month.lower()
    num = MONTH_NUM.get(key)
    if not num:
        return "", "", 0, 0
    return f"{key}-{year}", f"{month.capitalize()} {year}", year, num


def _order(folder):
    try:
        return LANGUAGE_ORDER.index(folder), ""
    except ValueError:
        return len(LANGUAGE_ORDER), folder


def build(records, drops, lang_facts, warn, info):
    """Group this run's Current Affairs documents into the section's pages.

    `records`  the published current-affairs documents (scripts/build_content)
    `drops`    the PDF scanner's inventory, keyed by repository-relative path
    `lang_facts(folder)` -> {id, code, name, native, flag}: the same language
               display facts the Study shelf renders its cards from, so the
               language cards on /current-affairs and on Study cannot drift.
    """
    by_path = {str(d.get("path") or ""): d for d in drops or []}
    languages = {}
    unplaced = 0

    for rec in records:
        path = str(rec.get("path") or rec.get("pdf") or "")
        parts = Path(path).parts
        if SEGMENT not in parts:
            unplaced += 1
            continue
        tail = list(parts[parts.index(SEGMENT) + 1:])
        if len(tail) < 3:                    # <language>/<month>/<file>
            warn(f"{path}: not under content/current-affairs/<language>/"
                 f"<Month YYYY>/ - published on the hub only")
            unplaced += 1
            continue

        folder, month_name = tail[0], tail[1]
        slug, label, year, num = month_folder(month_name)
        if not slug:
            warn(f"{path}: month folder {month_name!r} does not read as "
                 f"'<Month> <YYYY>' (e.g. 'August 2026') - listed on the "
                 f"language page, but it gets no month URL")

        drop = by_path.get(path, {})
        item = {
            "file": str(rec.get("file") or ""),
            "url": str(rec.get("url") or ""),
            "title": str(rec.get("title") or ""),
            "description": str(rec.get("description") or ""),
            "published": str(rec.get("published") or ""),
            "pages": int(drop.get("pages") or rec.get("pdfPages") or 0),
            "size": str(drop.get("sizeLabel") or ""),
            "language": folder,
        }

        lang = languages.setdefault(folder, {
            "folder": folder, **lang_facts(folder), "items": [], "months": {},
        })
        lang["items"].append(item)
        if slug:
            month = lang["months"].get(slug)
            if month is None:
                month = lang["months"][slug] = {
                    "slug": slug, "label": label, "year": year, "num": num,
                    "items": [],
                }
            month["items"].append(item)

    pages, lang_rows = [], []
    for folder in sorted(languages, key=_order):
        lang = languages[folder]
        name = lang.get("name") or folder.replace("-", " ").title()
        base = f"{SEGMENT}/{folder}"
        months = sorted(lang["months"].values(),
                        key=lambda m: (m["year"], m["num"]), reverse=True)
        # The newest file in this language, for the "what is here" line -
        # read off the records, never written by hand.
        newest = max((i["published"] for i in lang["items"]), default="")

        row = {
            **lang,
            "kind": "language",
            "name": name,
            "months": months,
            "count": len(lang["items"]),
            "newest": newest,
            "file": f"{base}/index.html",
            "url": f"{DOMAIN}/{base}",
            "title": f"{name} Current Affairs | {BRAND}",
            "description": (
                f"Current affairs for Punjab exams in {name}: monthly issues, "
                f"the practice set and every PDF to read or download, with no "
                f"sign-up and no email wall."
            ),
            "keywords": (f"{name} current affairs, Punjab current affairs "
                         f"{name}, current affairs magazine PDF, current "
                         f"affairs download"),
        }
        row["language"] = {k: row[k] for k in
                           ("folder", "id", "code", "name", "native", "flag")}
        lang_rows.append(row)
        pages.append(row)

        for month in months:
            month["kind"] = "month"
            month["file"] = f"{base}/{month['slug']}/index.html"
            month["url"] = f"{DOMAIN}/{base}/{month['slug']}"
            month["title"] = f"{month['label']} {name} Current Affairs | {BRAND}"
            month["description"] = (
                f"The {month['label']} current affairs archive in {name}: "
                f"{len(month['items'])} document"
                f"{'s' if len(month['items']) != 1 else ''} to read online or "
                f"download as a PDF, plus the magazine issue and the practice "
                f"set.")
            month["keywords"] = (
                f"{name} current affairs {month['label']}, current affairs "
                f"PDF {month['label']}, Punjab current affairs archive")
            month["language"] = {k: row[k] for k in
                                 ("folder", "id", "code", "name", "native",
                                  "flag")}
            month["newest"] = max((i["published"] for i in month["items"]),
                                  default="")
            pages.append(month)

    if lang_rows:
        info(f"current affairs section: {len(lang_rows)} language(s), "
             f"{sum(len(l['months']) for l in lang_rows)} month(s), "
             f"{sum(l['count'] for l in lang_rows)} document(s)")
    else:
        info("current affairs section: no file under content/current-affairs/"
             "<language>/<Month YYYY>/ - no language or month page this run")
    if unplaced:
        info(f"current affairs section: {unplaced} document(s) outside the "
             f"<language>/<Month YYYY> layout (hub listing only)")

    return {"languages": lang_rows, "pages": pages}
