#!/usr/bin/env python3
"""Resolve pulled infrastructure images to digests; never lock the releasable API."""
import json
from pathlib import Path
import subprocess
import os
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
base=['docker','compose','--env-file','.env','-f','compose.yaml','--profile','monitoring','--profile','logging']
subprocess.run(base+['pull','--ignore-buildable'],check=True)
config=json.loads(subprocess.check_output(base+['config','--format','json']))
services={}
for name,service in config['services'].items():
    if name=='api': continue
    info=json.loads(subprocess.check_output(['docker','image','inspect',service['image']]))[0]
    digests=info.get('RepoDigests',[])
    if not digests: raise SystemExit(f'No repository digest for {name}; cannot lock')
    services[name]={'image':digests[0]}
# JSON is a YAML subset; Compose accepts this file as an override.
Path('compose.lock.yaml').write_text(json.dumps({'services':services},indent=2)+'\n')
print('Wrote compose.lock.yaml. Compose wrapper uses it automatically. Review and commit the lock intentionally.')
