#!/usr/bin/env python3
"""new_content.py | scaffold a draft from one of the seventeen content templates.

The templates live in scripts/content_engine.py next to the recommendation
engine, so a scaffold arrives with the front-matter contract of its format and
the body outline the editor is expected to fill. Nothing is published from
here: the file lands in content/_drafts/, which the builder deliberately does
not read, until an editor moves it into its collection.

    python3 scripts/new_content.py --list
    python3 scripts/new_content.py --type study-note --slug ancient-history
    python3 scripts/new_content.py --type personal-note --slug revision-loop
    python3 scripts/new_content.py --type success-story --slug first-attempt
    python3 scripts/new_content.py --type study-note --slug ch --pa   # Punjabi

Every collection has a folder and a hub page of its own (17 of them, listed by
--list), so a new template only has to add its TEMPLATES entry and its builder
picks up validation, rendering, navigation, search, filters and the sitemap.
"""

import argparse
import pathlib
import re
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from content_engine import TEMPLATES, scaffold_for          # noqa: E402
from build_content import HUBS, REQUIRED_FIELDS, ALIASES    # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "content" / "_drafts"

PLACEHOLDER_DESC = (
    "Draft placeholder - replace this line with a 140 to 160 character "
    "description of what this page really covers, in the words an aspirant "
    "would search."
)

# A scaffold is valid the moment it is moved into its collection: the builder
# validates every file it loads (draft or not), so each required field the
# collection asks for arrives with a real, checkable value and a note about
# what to replace it with. `draft: true` keeps it off every page meanwhile.
_REQUIRED_DEFAULTS = {
    "published": lambda: (date.today().isoformat(),
                          "change to the real publish date"),
    "date": lambda: (date.today().isoformat(), "change to the session date"),
    "month": lambda: (date.today().strftime("%Y-%m"), "change to the issue month"),
    "subject": lambda: ("gk", "one of: gk, quant, reasoning, punjabi, english, "
                              "computer, current-affairs"),
    "exam": lambda: ("Punjab Police", "the exam this story is about"),
    "exams": lambda: (["Punjab Police"], "every exam this document serves"),
    "category": lambda: ("Study Plans", "pick the subtype this document is"),
    "post": lambda: ("Punjab Police Constable", "the post notified"),
    "official_url": lambda: ("https://punjabpolice.gov.in/",
                             "the official notification page (.gov.in)"),
    "file": lambda: ("assets/docs/", "path to the real file, or drop the field"),
}


def required_defaults(collection, present):
    """The front-matter lines a new stub still needs for its collection."""
    have = {ln.split(":", 1)[0].strip() for ln in present
            if not ln.startswith("#") and ":" in ln}
    have |= {ALIASES.get(k, k) for k in list(have)}      # publishDate -> published
    out = []
    for key in REQUIRED_FIELDS.get(collection, []):
        if key in have or key in ("title", "description") or key not in _REQUIRED_DEFAULTS:
            continue
        value, hint = _REQUIRED_DEFAULTS[key]()
        out.append(f"# {key} - {hint}")
        out.append(f"{key}: {value}")
    return out


def build_stub(template_key, slug, punjabi=False):
    lines, tpl = scaffold_for(template_key)
    extra = required_defaults(tpl["collection"], lines)
    injected = {ln.split(":", 1)[0].strip() for ln in extra
                if not ln.startswith("#")}
    front = ["---"]
    for line in lines:
        # a commented-out placeholder for a field we are about to inject would
        # only tell the editor two different things
        if line.startswith("#") and line.lstrip("#").split(":", 1)[0].strip() in injected:
            continue
        if line == "title:":
            front.append("title: " + (
                f"ਡ੍ਰਾਫਟ {slug}" if punjabi
                else f"Draft {tpl['label'].lower()} ({slug})"))
        elif line == "description:":
            front.append(f"description: {PLACEHOLDER_DESC}")
        elif line == "language: en":
            front.append("language: pa" if punjabi else line)
        else:
            front.append(line)
    front += extra
    front.append("---")

    intro = [
        f"<!-- {tpl['label']} template - {tpl['summary']} -->",
        "",
        "Fill every section, set `published:` and flip `draft: false` when the",
        "editorial review is done.",
    ]
    if punjabi:
        intro += ["", "ਪੰਜਾਬੀ ਪਾਠ ਇੱਥੇ ਲਿਖੋ - ਫਰੰਟ ਮੈਟਰ ਵਿੱਚ ਪਹਿਲਾਂ ਤੋਂ `language: pa` ਸੈੱਟ ਹੈ।"]
    sections = [f"{h}\n\n<!-- fill this section -->"
                for h in tpl["outline"]]
    return ("\n".join(front) + "\n\n" + "\n".join(intro) + "\n\n"
            + "\n\n".join(sections) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", dest="kind",
                    help="template key (see --list)")
    ap.add_argument("--slug", help="lowercase letters, digits and hyphens")
    ap.add_argument("--pa", action="store_true",
                    help="also write the Punjabi variant (.pa.md) - the "
                         "English original it pairs with is created next to it")
    ap.add_argument("--list", action="store_true", help="list the templates")
    ap.add_argument("--stdout", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)

    if args.list:
        print("Available content templates:\n")
        for key, tpl in TEMPLATES.items():
            hub = HUBS[tpl["collection"]]
            print(f"  {key:26s} -> content/{hub['dir']}/  "
                  f"({tpl['label']})  hub: {hub['file']}")
        print("\npython3 scripts/new_content.py --type <key> --slug <slug>")
        return 0

    if not args.kind or not args.slug:
        ap.error("--type and --slug are required (or use --list)")
    if args.kind not in TEMPLATES:
        ap.error(f"unknown template {args.kind!r}; run --list")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.slug):
        ap.error("slug must be lowercase letters, digits and hyphens")

    coll = TEMPLATES[args.kind]["collection"]
    folder = HUBS[coll]["dir"]
    base = DRAFTS / folder
    # A Punjabi variant needs the English original it pairs with (the builder
    # refuses a .pa.md with no source document), so --pa writes the pair.
    targets = [(base / f"{args.slug}.md",
                build_stub(args.kind, args.slug, punjabi=False))]
    if args.pa:
        targets.append((base / f"{args.slug}.pa.md",
                        build_stub(args.kind, args.slug, punjabi=True)))

    if args.stdout:
        for _, text in targets:
            print(text, end="")
        return 0
    clash = [p for p, _ in targets if p.exists()]
    if clash:
        for p in clash:
            print(f"refusing to overwrite {p.relative_to(ROOT)}", file=sys.stderr)
        return 1

    for out, text in targets:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    rels = [p.relative_to(ROOT) for p, _ in targets]
    print(f"  ✓ drafted {rels[0]}  ({TEMPLATES[args.kind]['label']} template)")
    for extra in rels[1:]:
        print(f"    + {extra}  (its Punjabi edition)")
    print(f"    collection: content/{folder}/   hub: {HUBS[coll]['file']}")
    print("\nNext:")
    print(f"  1. Fill the front matter and body in {rels[0]}"
          + (f" and {rels[1]}" if len(rels) > 1 else ""))
    print(f"  2. Move it: mv content/_drafts/{folder}/* content/{folder}/")
    print("  3. Build:   python3 scripts/build_content.py")
    print("  4. Gate:    bash scripts/ci.sh")
    print("\ncontent/_drafts/ is ignored by the builder, so an unfinished draft "
          "never reaches a page,")
    print("the sitemap, the feed or the search index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
