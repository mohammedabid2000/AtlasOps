#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .backups
file=".backups/postgres-$(date -u +%Y%m%dT%H%M%S)-${RANDOM}.dump"
trap 'rm -f "${file}.tmp"' EXIT
bash scripts/compose.sh exec -T db pg_dump -U postgres -d atlasops --format=custom > "${file}.tmp"
mv "${file}.tmp" "$file"
sha256sum "$file" > "${file}.sha256"
printf '%s\n' "$file"
