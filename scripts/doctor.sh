#!/usr/bin/env bash
set -euo pipefail
for tool in docker python3 openssl curl make; do
  command -v "$tool" >/dev/null || { printf 'Missing prerequisite: %s\n' "$tool"; exit 1; }
done
docker info >/dev/null 2>&1 || { printf 'Docker daemon is not accessible. Start Docker and check your permissions.\n'; exit 1; }
docker compose version
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 10), 'Host Python 3.10+ is required'
PY
docker compose --env-file .env -f compose.yaml --profile monitoring --profile logging config --quiet
printf 'Prerequisites and Compose configuration passed. Full ELK mode: recommend 16 GB host RAM and 15 GB free disk.\n'
