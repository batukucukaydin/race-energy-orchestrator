#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

INTERVAL="${1:-8}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $ROOT_DIR" >&2
  exit 1
fi

echo "Watching $ROOT_DIR every ${INTERVAL}s"
echo "Stop with Ctrl+C"

last_state=""
while true; do
  current_state="$(git status --porcelain)"
  if [[ -n "$current_state" && "$current_state" != "$last_state" ]]; then
    "$ROOT_DIR/scripts/git-sync-once.sh" || true
    last_state="$(git status --porcelain)"
  fi
  sleep "$INTERVAL"
done
