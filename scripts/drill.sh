#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dc=(bash scripts/compose.sh)
recover() { "${dc[@]}" start api >/dev/null; }
trap recover EXIT INT TERM
"${dc[@]}" stop api
printf 'API stopped. Waiting up to 150 seconds for AtlasApiDown (15 s scrape + 1 m pending).\n'
python3 - <<'PY'
import json,time,urllib.request
for attempt in range(50):
    with urllib.request.urlopen('http://127.0.0.1:9090/api/v1/alerts',timeout=5) as r:
        alerts=json.load(r)['data']['alerts']
    if any(a['labels']['alertname']=='AtlasApiDown' and a['state']=='firing' for a in alerts):
        print('PASS: AtlasApiDown is firing.'); break
    time.sleep(3)
else: raise SystemExit('Alert did not fire; inspect Prometheus rules and targets.')
PY
recover
trap - EXIT INT TERM
python3 scripts/ops.py smoke
printf 'Recovery confirmed. The alert resolves after the next successful evaluation.\n'
