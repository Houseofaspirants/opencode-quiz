#!/usr/bin/env bash
# watch_service.sh — run the content watcher in the background on macOS.
#
# The watcher (scripts/watch_content.mjs) is what actually publishes; this
# script only puts it under launchd so it survives a terminal closing and a
# computer restarting.
#
#   bash scripts/watch_service.sh install     # start now + at every login
#   bash scripts/watch_service.sh status      # is it alive?
#   bash scripts/watch_service.sh logs        # follow its output
#   bash scripts/watch_service.sh restart     # bounce it
#   bash scripts/watch_service.sh stop        # stop now (returns at next login)
#   bash scripts/watch_service.sh uninstall   # stop and forget
#
# Equivalent npm entry point for watching in the foreground: `npm run watch`.
set -euo pipefail

LABEL="com.houseofaspirants.content-watch"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/houseofaspirants-content-watch.log"
DOMAIN="gui/$(id -u)"

# launchd's PATH is nearly empty; bake the interpreter in as an absolute path.
NODE="$(command -v node || true)"
if [ -z "$NODE" ]; then
  for candidate in /opt/homebrew/bin/node /usr/local/bin/node; do
    [ -x "$candidate" ] && NODE="$candidate" && break
  done
fi
[ -n "$NODE" ] || { echo "✗ node not found — install Node.js first" >&2; exit 1; }

# XML-escapes a path for the plist (the repo folder name contains a space,
# which is legal; an ampersand or angle bracket would not be).
esc() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"

write_plist() {
  cat >"$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>${LABEL}</string>
	<key>ProgramArguments</key>
	<array>
		<string>$(esc "$NODE")</string>
		<string>$(esc "$ROOT/scripts/watch_content.mjs")</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$(esc "$ROOT")</string>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
	</dict>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<dict>
		<key>SuccessfulExit</key>
		<false/>
	</dict>
	<key>ThrottleInterval</key>
	<integer>30</integer>
	<key>StandardOutPath</key>
	<string>$(esc "$LOG")</string>
	<key>StandardErrorPath</key>
	<string>$(esc "$LOG")</string>
</dict>
</plist>
XML
  plutil -lint "$PLIST" >/dev/null
}

unload() { launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; }
loaded() { launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }

case "${1:-}" in
  install)
    unload
    write_plist
    launchctl bootstrap "$DOMAIN" "$PLIST"
    launchctl enable "$DOMAIN/$LABEL" 2>/dev/null || true
    echo "✓ content watcher installed and started"
    echo "  starts automatically every time you log in"
    echo "  status : bash scripts/watch_service.sh status"
    echo "  logs   : bash scripts/watch_service.sh logs"
    ;;

  status)
    if loaded; then
      echo "✓ loaded in launchd"
      launchctl print "$DOMAIN/$LABEL" | grep -E 'state =|pid =|last exit code =' | sed 's/^ */  /'
    else
      echo "✗ not loaded in launchd"
    fi
    if pgrep -f "scripts/watch_content.mjs" >/dev/null 2>&1; then
      echo "✓ process running (pid $(pgrep -f 'scripts/watch_content.mjs' | tr '\n' ' '))"
    else
      echo "✗ process not running"
    fi
    echo "  log: $LOG"
    ;;

  logs)
    [ -f "$LOG" ] || { echo "no log yet at $LOG"; exit 0; }
    tail -n 100 -f "$LOG"
    ;;

  restart)
    if loaded; then
      launchctl kickstart -k "$DOMAIN/$LABEL"
      echo "✓ restarted"
    else
      exec "$0" install
    fi
    ;;

  start)
    if loaded; then
      launchctl kickstart "$DOMAIN/$LABEL"
      echo "✓ started"
    else
      exec "$0" install
    fi
    ;;

  stop)
    unload
    echo "✓ stopped — it will come back at your next login; use 'uninstall' to disable"
    ;;

  uninstall)
    unload
    rm -f "$PLIST"
    echo "✓ uninstalled (log kept at $LOG)"
    ;;

  *)
    sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
