#!/usr/bin/env bash
# Usage: ./deploy.sh [host] [module]   — sync module(s) to <host>:~/tv/modules/
set -euo pipefail
HOST=${1:-pizero}
MOD=${2:-}
cd "$(dirname "$0")"
SRC=modules/${MOD:+$MOD/}
DST=tv/modules/${MOD:+$MOD/}   # relative to remote $HOME
rsync -az --exclude '__pycache__' --exclude '*.log' "$SRC" "$HOST:$DST"
echo "deployed ${MOD:-all modules} -> $HOST:$DST"
