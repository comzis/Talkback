#!/bin/sh
# Install the Mac reranker as a user agent so it starts at login.
# The process listens on 127.0.0.1:11435. __ROOT__ in the plist is replaced
# with this checkout.

set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
label=com.talkback.rerank-host
dest="$HOME/Library/LaunchAgents/${label}.plist"
domain="gui/$(id -u)"

mkdir -p "$HOME/Library/LaunchAgents" "$root/logs"
sed "s|__ROOT__|${root}|g" "$root/scripts/${label}.plist" > "$dest"

launchctl bootout "${domain}/${label}" 2>/dev/null || true
launchctl bootstrap "$domain" "$dest"
launchctl enable "${domain}/${label}"
echo "Installed ${dest}"
echo "The reranker listens on 127.0.0.1:11435. Logs: ${root}/logs/rerank-host.log"
