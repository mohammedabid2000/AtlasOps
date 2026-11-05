#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Atomic rename plus USR1 reopens Nginx files; Logstash tracks inode offsets.
bash scripts/compose.sh exec -T nginx sh -ec 'if [ -f /logs/nginx/access.jsonl ]; then mv /logs/nginx/access.jsonl /logs/nginx/access.jsonl.1; nginx -s reopen; fi'
printf 'Nginx log rotated. Application logs already rotate at 2 MB x 4 files.\n'
