#!/usr/bin/env bash
# Explicit local release, health gate, and recovery. Database migrations are not run.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p .state
dc=(bash scripts/compose.sh)
current=$("${dc[@]}" ps -q api)
[[ -n "$current" ]] || { printf 'Start the stack before deploying.\n'; exit 1; }
old_image=$(docker inspect --format '{{.Config.Image}}' "$current")
old_version=$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$current" | sed -n 's/^APP_VERSION=//p')
if [[ ${1:-} == --rollback ]]; then
  [[ -f .state/previous-release.json ]] || { printf 'No previous release recorded.\n'; exit 1; }
  new_image=$(python3 -c 'import json; print(json.load(open(".state/previous-release.json"))["image"])')
  new_version=$(python3 -c 'import json; print(json.load(open(".state/previous-release.json"))["version"])')
else
  new_image=${1:-}
  new_version=${2:-}
fi
[[ "$new_image" =~ ^[a-zA-Z0-9][a-zA-Z0-9./_:@-]+$ && "$new_version" =~ ^[a-zA-Z0-9._-]+$ ]] || {
  printf 'Use: make deploy IMAGE=registry/name:immutable-tag VERSION=git-sha\n'; exit 1;
}
[[ "$new_image" != "$old_image" ]] || { printf 'Use a distinct release image tag or digest.\n'; exit 1; }
docker image inspect "$new_image" >/dev/null 2>&1 || docker pull "$new_image"
persist_env() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys
p=Path('.env'); lines=p.read_text().splitlines()
lines=[line for line in lines if not line.startswith(('APP_IMAGE=','APP_VERSION='))]
p.write_text('\n'.join(lines)+f'\nAPP_IMAGE={sys.argv[1]}\nAPP_VERSION={sys.argv[2]}\n')
PY
}
switch_to() {
  APP_IMAGE="$1" APP_VERSION="$2" "${dc[@]}" up -d --no-deps --no-build --wait --wait-timeout 120 api || return 1
  # WAF upstream name resolution occurs when its Nginx configuration is loaded.
  "${dc[@]}" up -d --no-deps --force-recreate waf nginx || return 1
  python3 scripts/ops.py smoke || return 1
}
if switch_to "$new_image" "$new_version"; then
  python3 - "$old_image" "$old_version" <<'PY'
import json,sys
from pathlib import Path
Path('.state/previous-release.json').write_text(json.dumps({'image':sys.argv[1],'version':sys.argv[2]}))
PY
  persist_env "$new_image" "$new_version"
  printf 'Release verified and recorded: %s\n' "$new_version"
else
  printf 'Release failed its health gate; restoring the previous image.\n'
  if switch_to "$old_image" "$old_version"; then
    persist_env "$old_image" "$old_version"
    printf 'Previous release restored successfully.\n'
  else
    printf 'Recovery also failed. Inspect make status and make logs.\n'
  fi
  exit 1
fi
