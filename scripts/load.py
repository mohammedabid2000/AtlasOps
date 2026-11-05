#!/usr/bin/env python3
"""Small, bounded local traffic generator; no arbitrary targets."""
import argparse
from pathlib import Path
import time
from ops import app_request, ROOT
p = argparse.ArgumentParser()
p.add_argument('--requests', type=int, default=100)
args = p.parse_args()
if not 1 <= args.requests <= 1000:
    p.error('Use 1 to 1000 requests')
key = (ROOT / '.secrets/api-key').read_text().strip()
counts = {}
start = time.monotonic()
for _ in range(args.requests):
    code, _ = app_request('/api/tasks', key=key)
    counts[code] = counts.get(code, 0) + 1
    time.sleep(.2)
print({'requests': args.requests, 'elapsed_seconds': round(time.monotonic()-start,2), 'statuses':counts})
