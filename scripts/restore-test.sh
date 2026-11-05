#!/usr/bin/env bash
# Restore into a separate temporary database; never replace the active database.
set -euo pipefail
cd "$(dirname "$0")/.."
file=${1:-}
[[ -f "$file" ]] || { printf 'Usage: make restore-test FILE=.backups/postgres-....dump\n'; exit 1; }
sha256sum -c "${file}.sha256"
dc=(bash scripts/compose.sh)
restore_db="atlasops_restore_$(date +%s)_${RANDOM}"
cleanup() { "${dc[@]}" exec -T db dropdb -U postgres --if-exists "$restore_db" >/dev/null; }
trap cleanup EXIT
"${dc[@]}" exec -T db createdb -U postgres "$restore_db"
"${dc[@]}" exec -T db pg_restore -U postgres --exit-on-error --single-transaction -d "$restore_db" < "$file"
"${dc[@]}" exec -T db psql -U postgres -d "$restore_db" -v ON_ERROR_STOP=1 -c 'SELECT count(*) AS recovered_tasks FROM tasks;'
printf 'PASS: backup restored into an isolated database and queried. Live data was preserved.\n'
