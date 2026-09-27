#!/usr/bin/env python3
"""new_content.py | scaffold a draft from one of the eleven content templates.

The templates live in scripts/content_engine.py next to the recommendation
engine, so a scaffold arrives with the front-matter contract of its format and
the body outline the editor is expected to fill. Nothing is published from
here: the file lands in content/_drafts/, which the builder deliberately does
not read, until an editor moves it into its collection.

    python3 scripts/new_content.py --list
    python3 scripts/new_content.py --type study-note --slug ancient-history
    python3 scripts/new_content.py --type book-review --slug laxmi-publication
    python3 scripts/new_content.py --type study-note --slug ch -pa   # Punjabi
"""

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from content_engine import TEMPLATES, scaffold_for          # noqa: E402
from build_content import HUBS                               # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "content" / "_drafts"

PLACEHOLDER_DESC = (
    "Draft placeholder - replace this line with a 140 to 160 character "
    "description of what this page really covers, in the words an aspirant "
    "would actually search for."
)


def build_stub(template_key, slug, punjabi=False):
    lines, tpl = scaffold_for(template_key)
    front = ["---"]
    for line in lines:
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
                    help="write the Punjabi variant (.pa.md) instead")
    ap.add_argument("--list", action="store_true", help="list the templates")
    ap.add_argument("--stdout", action="store_true", help="print, do not write")
    args = ap.parse_args(argv)

    if args.list:
        print("Available content templates:\n")
        for key, tpl in TEMPLATES.items():
            print(f"  {key:26s} -> content/{tpl['collection']}/  "
                  f"({tpl['label']})")
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
    name = f"{args.slug}.pa.md" if args.pa else f"{args.slug}.md"
    out = DRAFTS / folder / name
    text = build_stub(args.kind, args.slug, punjabi=args.pa)

    if args.stdout:
        print(text, end="")
        return 0
    if out.exists():
        print(f"refusing to overwrite {out.relative_to(ROOT)}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    rel = out.relative_to(ROOT)
    print(f"  ✓ drafted {rel}  ({TEMPLATES[args.kind]['label']} template)")
    print(f"    collection: content/{folder}/   hub: {HUBS[coll]['file']}")
    print("\nNext:")
    print(f"  1. Fill the front matter and body in {rel}")
    print(f"  2. Move it: mv {rel} content/{folder}/")
    print("  3. Build:   python3 scripts/build_content.py")
    print("  4. Gate:    bash scripts/ci.sh")
    print("\ncontent/_drafts/ is ignored by the builder, so an unfinished draft "
          "never reaches a page,")
    print("the sitemap, the feed or the search index.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
