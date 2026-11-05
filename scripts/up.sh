#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/ops.py init
bash scripts/doctor.sh
dc=(bash scripts/compose.sh)
"${dc[@]}" up -d init db vault
python3 scripts/ops.py vault-bootstrap
# Renew AppRole on every startup, including after its 24-hour bootstrap credential expired.
"${dc[@]}" up -d --force-recreate vault-agent
profiles=()
if [[ ${1:-monitoring} != lite ]]; then profiles+=(--profile monitoring); fi
if [[ ${1:-monitoring} == full ]]; then profiles+=(--profile logging); fi
# Build only the development image. A later restart must preserve an explicitly
# deployed release image instead of replacing its immutable tag with local code.
configured_image=$("${dc[@]}" config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["api"]["image"])')
if [[ "$configured_image" == atlasops-api:local ]]; then
  "${dc[@]}" build api
fi
"${dc[@]}" "${profiles[@]}" up -d --no-build --wait --wait-timeout 240
if [[ ${1:-monitoring} == full ]]; then python3 scripts/ops.py elastic-setup; fi
python3 scripts/ops.py smoke
if [[ ${1:-monitoring} != lite ]]; then python3 scripts/ops.py verify; fi
printf 'Open https://localhost:8443. See README.md for credentials and dashboards.\n'
