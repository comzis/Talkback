#!/bin/sh
# Stop the login reranker and remove its user agent.

set -eu
label=com.talkback.rerank-host
dest="$HOME/Library/LaunchAgents/${label}.plist"
domain="gui/$(id -u)"

launchctl bootout "${domain}/${label}" 2>/dev/null || true
rm -f "$dest"
echo "Removed ${label}"
