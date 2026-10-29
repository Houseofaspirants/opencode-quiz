#!/usr/bin/env python3
"""r2_switch.py - move the site's PDFs from Vercel to Cloudflare R2, in one go.

    python3 scripts/r2_switch.py https://files.houseofaspirants.in

Run it only after `node scripts/r2_sync.mjs` has uploaded every PDF. It refuses
to switch anything until:
  1. `node scripts/r2_sync.mjs --check` says every PDF is on R2, and
  2. a PDF answers 200 from the public domain, with the CORS headers the
     on-page reader (assets/js/pdf-reader.js) needs.

Then it:
  * data/site.json  -> files.pdfBase = <base>   (builders + core.js link there)
  * vercel.json     -> the old PDF redirects point straight at R2; two 301
                       rules send every other /content/*.pdf and
                       /assets/pdfs/*.pdf to R2 (old WhatsApp / Google links);
                       buildCommand stops rebuilding on Vercel (the PDFs are no
                       longer uploaded there, so a rebuild would drop every PDF
                       page - the committed output, gated by ci.sh, is served)
  * .vercelignore   -> PDFs are never uploaded to Vercel again
  * sw.js           -> VERSION bump, so every visitor gets the new core.js
  * rebuilds the site so every page links to R2.

Review with `git diff`, then commit and push as usual.
`--undo` puts site.json / vercel.json / .vercelignore back the way they were.
"""
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "data" / "site.json"
VERCEL = ROOT / "vercel.json"
IGNORE = ROOT / ".vercelignore"
SW = ROOT / "sw.js"
IGNORE_LINES = ["# PDFs are served from Cloudflare R2 (scripts/r2_switch.py) - never upload them to Vercel",
                "content/**/*.pdf", "content/**/*.PDF", "assets/pdfs/*.pdf"]
PREBUILT = "echo 'prebuilt: committed output is served; PDFs live on Cloudflare R2'"
REBUILD = "bash scripts/build_site.sh"
LOCAL_PDF = re.compile(r"^/(?:content|assets/pdfs)/.*\.pdf$", re.I)
CATCH_ALL = [
    ("/content/:path(.*\\.(?:pdf|PDF))", "{base}/content/:path"),
    ("/assets/pdfs/:path(.*\\.(?:pdf|PDF))", "{base}/assets/pdfs/:path"),
]


def die(msg):
    print(f"\n✗ {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd):
    print(f"\n· {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def read_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_pdf_base(base):
    """Edits data/site.json as text, so the hand formatting stays as it is."""
    src = SITE.read_text(encoding="utf-8")
    src = re.sub(r',\s*"files"\s*:\s*\{[^{}]*\}', "", src)  # drop an old block
    if base:
        i = src.rstrip().rfind("}")
        body = src[:i].rstrip()
        src = body + f',\n  "files": {{ "pdfBase": {json.dumps(base)} }}\n}}\n'
    json.loads(src)  # still valid JSON, or stop here
    SITE.write_text(src, encoding="utf-8")


def probe(base):
    """One real PDF must answer from R2 with CORS + range support."""
    sample = sorted((ROOT / "assets" / "pdfs").glob("*.pdf"))[:1] or \
        sorted((ROOT / "content").rglob("*.pdf"))[:1]
    if not sample:
        die("no PDF found to test with")
    rel = sample[0].relative_to(ROOT).as_posix()
    url = f"{base}/{urllib.request.quote(rel)}"
    req = urllib.request.Request(url, headers={
        "Origin": "https://houseofaspirants.in", "Range": "bytes=0-1023",
        "User-Agent": "hoa-r2-switch"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status, h = r.status, r.headers
    except Exception as e:  # noqa: BLE001
        die(f"{url} did not answer ({e}). Is the custom domain connected to the bucket?")
    print(f"  {url} -> HTTP {status}")
    if status not in (200, 206):
        die("the public domain does not serve the PDF yet")
    acao = h.get("Access-Control-Allow-Origin", "")
    if acao not in ("*", "https://houseofaspirants.in"):
        die("no Access-Control-Allow-Origin header - add r2-cors.json to the bucket's CORS policy")
    expose = h.get("Access-Control-Expose-Headers", "").lower()
    if status == 206 and "content-range" not in expose:
        die("CORS policy must expose Content-Range (see r2-cors.json) or the PDF reader breaks")
    print("  ✓ public, CORS ok" + (", range requests ok" if status == 206 else ""))


def switch(base):
    run(["node", "scripts/r2_sync.mjs", "--check"])
    print("\n· checking the public domain")
    probe(base)

    set_pdf_base(base)
    print(f"\n✓ data/site.json: files.pdfBase = {base}")

    v = read_json(VERCEL)
    v["buildCommand"] = PREBUILT
    reds = v.setdefault("redirects", [])
    moved = 0
    for r in reds:
        d = r.get("destination", "")
        if LOCAL_PDF.match(d):
            r["destination"] = base + d
            moved += 1
    sources = {r.get("source") for r in reds}
    for src, dest in CATCH_ALL:
        if src not in sources:
            reds.append({"source": src, "destination": dest.format(base=base), "statusCode": 301})
    write_json(VERCEL, v)
    print(f"✓ vercel.json: {moved} old PDF redirect(s) now go straight to R2, catch-all 301s added, "
          "Vercel rebuild off")

    IGNORE.write_text("\n".join(IGNORE_LINES) + "\n", encoding="utf-8")
    print("✓ .vercelignore: PDFs are no longer uploaded to Vercel")

    sw = SW.read_text(encoding="utf-8")
    m = re.search(r'const VERSION = "hoa-v(\d+)";', sw)
    if m:
        n = int(m.group(1)) + 1
        SW.write_text(sw.replace(m.group(0), f'const VERSION = "hoa-v{n}";', 1), encoding="utf-8")
        print(f"✓ sw.js: VERSION hoa-v{n}")

    run(["node", "scripts/build_content_manifest.ts"])
    run(["python3", "scripts/build_content.py"])
    run(["node", "scripts/build-index.mjs"])
    run(["python3", "scripts/build_landing_pages.py"])
    run(["node", "scripts/clean-links.mjs"])
    print("\n✅ Switched. Check `git diff`, then commit + push. After Vercel deploys, open one\n"
          "   PDF page and one old /content/…pdf link to confirm both reach files.houseofaspirants.in.")


def undo():
    set_pdf_base(None)
    v = read_json(VERCEL)
    v["buildCommand"] = REBUILD
    catch = {s for s, _ in CATCH_ALL}
    v["redirects"] = [r for r in v.get("redirects", []) if r.get("source") not in catch]
    for r in v["redirects"]:
        d = r.get("destination", "")
        m = re.match(r"^https://[^/]+(/(?:content|assets/pdfs)/.*\.pdf)$", d, re.I)
        if m:
            r["destination"] = m.group(1)
    write_json(VERCEL, v)
    if IGNORE.exists():
        lines = [ln for ln in IGNORE.read_text(encoding="utf-8").splitlines() if ln not in IGNORE_LINES]
        if any(ln.strip() for ln in lines):
            IGNORE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            IGNORE.unlink()
    print("✓ undone: site.json, vercel.json, .vercelignore restored - now rebuild (npm run publish)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--undo"]:
        undo()
    elif len(args) == 1 and re.match(r"^https://[a-z0-9.-]+$", args[0].rstrip("/")):
        switch(args[0].rstrip("/"))
    else:
        die("usage: python3 scripts/r2_switch.py https://files.houseofaspirants.in   (or --undo)")
