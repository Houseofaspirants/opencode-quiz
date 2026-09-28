#!/usr/bin/env bash
# ci.sh — the Phase 0 gate. Run it locally (`bash scripts/ci.sh`) and in CI.
#
#   1. scan every PDF drop (node), rebuild every content page from that
#      inventory (python), then re-read it back and prove the scanner and the
#      builder derive the same document from the same file name
#   2. rebuild the manifest with both builders (byte-parity when Node exists)
#   3. rebuild the SEO landing set
#   4. type-check the browser scripts (tsc --noEmit over jsconfig.json)
#   5. run scripts/seo_check.py
#   6. run scripts/rich_results_check.py
#   7. prove the committed tree is exactly what those builders emit
#
# Step 7 is what makes "the gates passed" meaningful: a green seo_check on a
# stale checkout proves nothing. Only the four files that legitimately carry a
# run timestamp are normalised back to their committed value first, so a real
# content drift still fails the diff.
#
# Exit code 0 = every gate passed and the working tree matches the builders.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m· %s\033[0m\n' "$1"; }

step "1/7 content — node scripts/build_content_manifest.ts + python3 scripts/build_content.py"
if ! command -v node >/dev/null 2>&1; then
  echo "FAIL: node is required - scripts/build_content_manifest.ts writes the" >&2
  echo "      PDF inventory (drops) that scripts/build_content.py publishes from." >&2
  exit 1
fi
node scripts/build_content_manifest.ts   # content/** -> data/content-manifest.json
python3 scripts/build_content.py         # publish from `drops`, never from a walk
node scripts/build_content_manifest.ts --check   # committed inventory == disk

# The scanner and the publisher must derive the identical document from one
# file name, or a drop would be described one way and published another.
step "1/7 derivation parity — TS scanner vs python builder"
FIXTURES=(
  "mobile phone"
  "Mobile Phone"
  "Current Affairs July 2026"
  "current affairs july-2026"
  "PPSC 2024 PYQ"
  "CA August (english)"
  "current affairs August(punjabi)"
  "Sheet 2026-08-12"
  "sept 2026"
  "2026-07"
  "notes of punjab history"
  "ਮੋਬਾਈਲ ਫੋਨ"
  "ਪੰਜਾਬੀ ਨੋਟ"
  "ਪੰਜਾਬੀ ਟੈਸਟ 2026-09-15"
  "ਸਿੰਘ"
  "ਗੁਰਮੁਖੀ ਨੋਟ"
  "ਪੰਜਾਬੀ (english)"
  "SI-2 notes"
  "  spaced  out  "
  "!!!"
)
node scripts/build_content_manifest.ts --derive "${FIXTURES[@]}" > /tmp/hoa-derive-ts.json
python3 - "${FIXTURES[@]}" <<'PY' > /tmp/hoa-derive-py.json
import json, sys
sys.path.insert(0, "scripts")
import build_content as bc
rows = [{"stem": s, "title": bc.pdf_title_from_name(s),
         "slug": bc.pdf_slug_from_name(s), "date": bc.pdf_date_from_name(s)}
        for s in sys.argv[1:]]
print(json.dumps(rows, ensure_ascii=False, indent=2))
PY
if ! diff -u /tmp/hoa-derive-py.json /tmp/hoa-derive-ts.json; then
  echo "FAIL: build_content.py and build_content_manifest.ts disagree on" >&2
  echo "      title/slug/date for a file name (see the fixture diff above)." >&2
  exit 1
fi
echo "  derivation parity OK (${#FIXTURES[@]} names, both implementations agree)"

step "2/7 manifest — python3 scripts/build_index.py"
python3 scripts/build_index.py

if command -v node >/dev/null 2>&1; then
  step "3/7 manifest parity — node scripts/build-index.mjs"
  cp data/index.json /tmp/hoa-index.py.json
  cp data/quiz-manifest.json /tmp/hoa-quiz-manifest.py.json
  cp sitemap.xml /tmp/hoa-sitemap.py.xml
  node scripts/build-index.mjs
  # volatile fields (generatedAt, lastmod) are allowed to differ between runs
  norm() { grep -v -e '"generatedAt"' -e '<lastmod>' || true; }
  if ! diff -u <(norm < /tmp/hoa-index.py.json) <(norm < data/index.json); then
    echo "FAIL: build_index.py and build-index.mjs disagree on data/index.json" >&2
    exit 1
  fi
  # quiz-manifest.json carries no timestamp, so it must match byte for byte -
  # it is the multilingual topic contract (id, languages, counts, titles).
  if ! diff -u /tmp/hoa-quiz-manifest.py.json data/quiz-manifest.json; then
    echo "FAIL: build_index.py and build-index.mjs disagree on data/quiz-manifest.json" >&2
    exit 1
  fi
  if ! diff -u <(norm < /tmp/hoa-sitemap.py.xml) <(norm < sitemap.xml); then
    echo "FAIL: build_index.py and build-index.mjs disagree on sitemap.xml" >&2
    exit 1
  fi
  echo "  parity OK (both builders emit the same bytes)"
else
  step "3/7 manifest parity — skipped (node not installed; CI runs it)"
fi

step "4/7 type check — tsc --noEmit (jsconfig.json)"
if npx --yes --package typescript@5.6.3 tsc --version >/dev/null 2>&1; then
  npx --yes --package typescript@5.6.3 tsc --noEmit -p jsconfig.json
  echo "  type check OK (0 errors)"
else
  echo "  type check skipped (typescript unavailable offline; CI runs it)"
fi

step "5/7 landing pages — python3 scripts/build_landing_pages.py"
python3 scripts/build_landing_pages.py

step "6/7 gates"
python3 scripts/seo_check.py
python3 scripts/rich_results_check.py

step "7/7 committed tree matches the builders"
python3 - <<'PY'
"""Rewrite the four run-timestamped fields to their committed values."""
import re
import subprocess
from pathlib import Path

# file -> (regex, replace_all). The committed match is authoritative: the
# builders stamp "now" into these fields, so a run on another day must not
# look like content drift.
VOLATILE = {
    "data/index.json": [(r'"generatedAt": "[^"]*"', False)],
    "data/landing-manifest.json": [(r'"generatedAt": "[^"]*"', False)],
    "SEO-LANDING-REPORT.md": [(r"Generated by `scripts/build_landing_pages\.py` on [^.]*\.", False)],
    "sitemap.xml": [(r"<lastmod>[^<]*</lastmod>", True)],   # one per URL
}
for path, patterns in VOLATILE.items():
    head = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True,
                          text=True, check=True).stdout
    p = Path(path)
    work = p.read_text(encoding="utf-8")
    changed = False
    for pat, replace_all in patterns:
        m = re.search(pat, head)
        if not m:
            continue
        repl = m.group(0).replace("\\", "\\\\")
        work, n = re.subn(pat, repl, work,
                          count=0 if replace_all else 1)
        changed = changed or n > 0
    if changed:
        p.write_text(work, encoding="utf-8")
        print(f"  normalised timestamps in {path}")
PY

if ! git diff --exit-code; then
  echo "FAIL: the committed tree does not match what the builders emit." >&2
  echo "      Commit the regenerated files (or fix the builder)." >&2
  exit 1
fi
echo "  committed tree matches the builders"
echo
echo "ALL GATES GREEN"
