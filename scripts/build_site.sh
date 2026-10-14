#!/usr/bin/env bash
# Rebuild from source on every deployment, including deleted content.
set -euo pipefail
cd "$(dirname "$0")/.."
node scripts/build_content_manifest.ts
python3 scripts/build_content.py
node scripts/build-index.mjs
python3 scripts/build_landing_pages.py
node scripts/clean-links.mjs
