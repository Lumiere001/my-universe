#!/bin/sh
# Render mockup HTML -> docs/images PNG (2x). Usage: ./render.sh [name ...]
cd "$(dirname "$0")"
OUT=../../docs/images
for n in ${@:-chat-1-conversation chat-2-confirm chat-3-encourage}; do
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 --window-size=1200,860 --virtual-time-budget=4000 \
    --screenshot="$PWD/$OUT/$n.png" "file://$PWD/$n.html" 2>/dev/null
done
