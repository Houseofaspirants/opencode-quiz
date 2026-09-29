#!/usr/bin/env bash
# publish.sh — scan the content, publish it, gate it, commit it.
#
#   ./publish.sh
#
# Any failing command stops the run before anything is committed, so a broken
# build can never become the committed tree.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n\033[1m· %s\033[0m\n' "$1"; }

# The first failure is the error the operator needs to see: which command, on
# which line, with which exit status. `set -e` stops the run either way.
trap 's=$?; printf "\n\033[1;31mFAIL\033[0m (exit %s): %s\n" "$s" "$BASH_COMMAND" >&2; exit "$s"' ERR

step "1/5 npm run content"
npm run content

step "2/5 python3 scripts/build_content.py"
python3 scripts/build_content.py

step "3/5 python3 scripts/build_index.py"
python3 scripts/build_index.py

step "4/5 python3 scripts/build_landing_pages.py"
python3 scripts/build_landing_pages.py

step "5/5 bash scripts/ci.sh"
bash scripts/ci.sh

git add -A

if git diff --cached --quiet; then
  echo "================================="
  echo "✅ NOTHING NEW TO PUBLISH"
  echo "================================="
  exit 0
fi

git commit -m "publish content"

echo "================================="
echo "✅ WEBSITE PUBLISHED SUCCESSFULLY"
echo "================================="
