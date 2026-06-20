#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $ROOT_DIR" >&2
  exit 1
fi

if [[ -z "$(git status --porcelain)" ]]; then
  echo "No changes to commit."
  exit 0
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
branch="$(git branch --show-current)"

git add -A
git commit -m "autosync: ${timestamp}"

if git remote get-url origin >/dev/null 2>&1; then
  if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
    git push
  else
    git push -u origin "$branch"
  fi
else
  echo "Commit created locally. No origin remote configured yet."
fi
