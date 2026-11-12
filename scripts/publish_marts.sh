#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/data/marts"
[ -d "$SRC" ] || { echo "faltan data/marts; corré make marts" >&2; exit 1; }

if [ -n "${GITHUB_TOKEN:-}" ]; then
    REMOTE="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
else
    REMOTE="$(git -C "$ROOT" remote get-url origin)"
fi
WORK="$(mktemp -d "${TMPDIR:-/tmp}/canasta-data.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/marts"
cp "$SRC"/*.parquet "$WORK/marts/"

cd "$WORK"
git init -q
git checkout -q -b data
git add marts
git -c user.name="canasta-bot" \
    -c user.email="canasta@users.noreply.github.com" \
    commit -q -m "data: marts $(date -u +%F)"
git remote add origin "$REMOTE"
git push -f origin data

echo "publicado: $(git rev-parse --short HEAD) en rama data"
