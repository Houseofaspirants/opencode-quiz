#!/usr/bin/env python3
"""Google Rich Results compatibility check for houseofaspirants.in.

seo_check.py validates JSON-LD against *our* rules; this script validates the
same markup against the property lists Google documents for each feature, so
"eligible" here means "meets Google's published requirement list", not "Google
will display it" (display is always Google's own decision).

Features checked, with their source:
  Article        developers.google.com/search/docs/appearance/structured-data/article
  Breadcrumb     .../structured-data/breadcrumb
  FAQ            .../structured-data/faqpage
  Education Q&A  .../structured-data/education-qa     (Quiz / Question / Answer)
  Organization   .../structured-data/organization
  Speakable      .../structured-data/speakable
  Sitelinks search box (SearchAction) — feature retired December 2024

Usage:
    python3 scripts/rich_results_check.py                # static HTML
    python3 scripts/rich_results_check.py --live <file>  # captured runtime JSON-LD
                                                         # (###label marker format)

Exit code 0 = every feature present meets Google's required property list.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://houseofaspirants.in"

# Google's own words, compressed: (feature, required properties, note)
RETIRED = "feature retired by Google (December 2024) - markup stays valid schema.org"
FAQ_NOTE = ("valid markup, but Google only displays FAQ rich results for "
            "well-known, authoritative government and health websites")


def walk(o):
    """Every dict in the document that carries a type."""
    out = []
    if isinstance(o, dict):
        if "@type" in o:
            out.append(o)
        for v in o.values():
            out.extend(walk(v))
    elif isinstance(o, list):
        for v in o:
            out.extend(walk(v))
    return out


def types_of(n):
    t = n.get("@type")
    return [t] if isinstance(t, str) else (t or [])


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def check(doc):
    """-> list of (feature, status, detail) for one page's entity graph."""
    nodes = walk(doc)
    found, out = {}, []

    def add(feature, status, detail):
        out.append((feature, status, detail))

    # ---------------------------------------------------------------- Article
    for n in nodes:
        if set(types_of(n)) & {"Article", "NewsArticle", "BlogPosting"}:
            rec = ["headline", "image", "datePublished", "dateModified",
                   "author", "publisher", "mainEntityOfPage", "description"]
            have = [k for k in rec if k in n]
            missing = [k for k in rec if k not in n]
            author = n.get("author")
            if isinstance(author, dict) and "@id" in author and "@type" not in author:
                pass  # author resolved by @id elsewhere in the graph
            elif isinstance(author, dict) and not author.get("name"):
                missing.append("author.name")
            img = n.get("image")
            if isinstance(img, dict):
                if "width" not in img or "height" not in img:
                    missing.append("image.width/height")
            add("Article", "ELIGIBLE" if not missing else "ELIGIBLE (thin)",
                f"{len(have)}/{len(rec)} recommended present"
                + (f"; missing {', '.join(missing)}" if missing else ""))

    # ------------------------------------------------------------- Breadcrumb
    for n in nodes:
        if types_of(n) != ["BreadcrumbList"]:
            continue
        items = as_list(n.get("itemListElement"))
        bad = [f"item {i} missing {p}"
               for i, it in enumerate(items, 1)
               for p in ("position", "name", "item") if p not in it]
        if not items:
            add("Breadcrumb", "FAIL", "itemListElement empty")
        elif bad:
            add("Breadcrumb", "FAIL", "; ".join(bad))
        elif len(items) < 2:
            add("Breadcrumb", "FAIL", "fewer than 2 crumbs")
        else:
            add("Breadcrumb", "PASS",
                f"{len(items)} crumbs, each with position + name + item")

    # -------------------------------------------------------------------- FAQ
    for n in nodes:
        if "FAQPage" not in types_of(n):
            continue
        qs = as_list(n.get("mainEntity"))
        if not qs:
            add("FAQ", "FAIL", "mainEntity missing (Google-required)")
            continue
        bad = [f"Q{i} missing " + ",".join(p for p in ("name", "acceptedAnswer")
                                          if p not in q)
               for i, q in enumerate(qs, 1)
               if not ({"name", "acceptedAnswer"} <= set(q))]
        bad += [f"Q{i} acceptedAnswer.text missing"
                for i, q in enumerate(qs, 1)
                if isinstance(q.get("acceptedAnswer"), dict)
                and "text" not in q["acceptedAnswer"]]
        add("FAQ", "FAIL" if bad else "VALID (not displayable)",
            "; ".join(bad) if bad else f"{len(qs)} Q/A pairs - {FAQ_NOTE}")

    # --------------------------------------------------- Education Q&A (Quiz)
    for n in nodes:
        if "Quiz" not in types_of(n):
            continue
        parts = [p for p in as_list(n.get("hasPart"))
                 if isinstance(p, dict) and "@type" in p]
        if not parts:
            add("Education Q&A", "FAIL",
                "Quiz.hasPart missing/empty (Google-required: Question nodes)")
            continue
        bad = []
        for i, q in enumerate(parts, 1):
            miss = [p for p in ("text", "eduQuestionType", "acceptedAnswer")
                    if p not in q]
            if q.get("eduQuestionType") not in (None, "Flashcard"):
                miss.append("eduQuestionType must be the fixed value 'Flashcard'")
            aa = q.get("acceptedAnswer")
            if isinstance(aa, dict) and "text" not in aa:
                miss.append("acceptedAnswer.text")
            if miss:
                bad.append(f"Q{i}: {', '.join(miss)}")
        rec = "about" if "about" in n else "about (recommended)"
        add("Education Q&A", "FAIL" if bad else "ELIGIBLE",
            "; ".join(bad) if bad else
            f"{len(parts)} Question nodes, all with text + "
            f"eduQuestionType:Flashcard + acceptedAnswer.text; {rec}")

    # ------------------------------------------------------------ Organization
    for n in nodes:
        if not set(types_of(n)) & {"Organization", "EducationalOrganization"}:
            continue
        rec = ["name", "alternateName", "url", "logo", "sameAs"]
        missing = [k for k in rec if k not in n]
        logo = n.get("logo")
        if isinstance(logo, dict) and "url" not in logo:
            missing.append("logo.url")
        add("Organization", "ELIGIBLE" if not missing else "ELIGIBLE (thin)",
            f"{len(rec) - len(missing)}/{len(rec)} recommended present"
            + (f"; missing {', '.join(missing)}" if missing else "")
            + " (no physical address published - none claimed)")

    # -------------------------------------------------------------- Speakable
    for n in nodes:
        sp = n.get("speakable")
        if not isinstance(sp, dict):
            continue
        has_sel, has_xpath = "cssSelector" in sp, "xPath" in sp
        if has_sel == has_xpath:   # neither, or both (Google forbids both)
            add("Speakable", "FAIL",
                "needs exactly one of cssSelector / xPath")
        else:
            sel = sp.get("cssSelector") or sp.get("xPath")
            add("Speakable", "PASS",
                f"{len(as_list(sel))} selector(s) targeting visible answer text")

    # ------------------------------------------------ SearchAction / sitelinks
    for n in nodes:
        pa = n.get("potentialAction")
        if isinstance(pa, dict) and "SearchAction" in types_of(pa):
            ok = isinstance(pa.get("target"), dict) and "urlTemplate" in pa["target"]
            add("Sitelinks search box", "VALID (feature retired)",
                "SearchAction + EntryPoint present - " + RETIRED if ok
                else "SearchAction target must be EntryPoint + urlTemplate")

    found = {f for f, _, _ in out}
    if not out:
        add("(no Google feature types on this page)", "-", "valid schema.org only")
    return out


def load_static():
    docs = []
    for path in sorted(ROOT.glob("*.html")):
        src = path.read_text(encoding="utf-8")
        blocks = [b for b in re.findall(
            r'<script type="application/ld\+json"(?: id="[^"]*")?>(.*?)</script>',
            src, re.S) if b.strip()]
        merged = {"@context": "https://schema.org", "@graph": []}
        for b in blocks:
            try:
                d = json.loads(b)
            except json.JSONDecodeError as e:
                docs.append((path.name, {"__error__": str(e)}))
                merged = None
                break
            merged["@graph"].extend(d.get("@graph") or
                                    [k for k in [d] if k.get("@type")])
        if merged:
            docs.append((path.name, merged))
    return docs


def load_live(path):
    """Marker format: a line '###label' starts a block, raw JSON follows."""
    docs, label, buf = [], None, []
    for line in open(path, encoding="utf-8").read().split("\n"):
        if line.startswith("###"):
            if label is not None:
                docs.append((label, json.loads("\n".join(buf).strip())))
            label, buf = line[3:].strip(), []
        elif label is not None:
            buf.append(line)
    if label is not None:
        docs.append((label, json.loads("\n".join(buf).strip())))
    return docs


def main():
    args = sys.argv[1:]
    if args and args[0] == "--live":
        docs = load_live(args[1])
        title = f"runtime JSON-LD captured from {os.path.basename(args[1])}"
    else:
        docs = load_static()
        title = "static HTML"

    failures = 0
    print(f"Google Rich Results compatibility - {title}")
    print("=" * 76)
    for label, doc in docs:
        if "__error__" in doc:
            print(f"{label}\n  PARSE ERROR {doc['__error__']}")
            failures += 1
            continue
        rows = check(doc)
        if rows == [] or rows[0][0].startswith("(no Google"):
            continue
        print(label)
        for feature, status, detail in rows:
            if status == "FAIL":
                failures += 1
            flag = "FAIL" if status == "FAIL" else "ok  "
            print(f"  {flag} {feature:<24} {status:<24} {detail}")
        print()
    print("=" * 76)
    if failures:
        print(f"RESULT: FAIL - {failures} feature(s) missing Google-required properties")
        return 1
    print("RESULT: PASS - every feature present meets Google's published "
          "requirement list")
    print("note: eligibility != display; Google decides what to show")
    return 0


if __name__ == "__main__":
    sys.exit(main())
