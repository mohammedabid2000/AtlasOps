#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
files=(-f compose.yaml)
if [[ -f compose.lock.yaml ]]; then files+=(-f compose.lock.yaml); fi
exec docker compose --env-file .env "${files[@]}" "$@"
