#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in kind kubectl docker; do command -v "$tool" >/dev/null || { printf 'Install %s first.\n' "$tool"; exit 1; }; done
if [[ ${1:-up} == down ]]; then
  kind delete cluster --name atlasops
  exit 0
fi
python3 scripts/ops.py init
if ! kind get clusters | grep -qx atlasops; then kind create cluster --name atlasops; fi
kc=(kubectl --context kind-atlasops)
docker build -t atlasops-api:local .
kind load docker-image atlasops-api:local --name atlasops
"${kc[@]}" apply -f k8s/namespace.yaml
"${kc[@]}" -n atlasops create secret generic atlasops-db --from-file=password=.secrets/db-password --from-file=admin-password=.secrets/db-admin-password --dry-run=client -o yaml | "${kc[@]}" apply -f -
"${kc[@]}" -n atlasops create secret generic atlasops-api --from-file=api-key=.secrets/api-key --dry-run=client -o yaml | "${kc[@]}" apply -f -
"${kc[@]}" -n atlasops create configmap db-init --from-file=10-atlas.sh=infra/postgres/init.sh --dry-run=client -o yaml | "${kc[@]}" apply -f -
"${kc[@]}" apply -f k8s/app.yaml
"${kc[@]}" -n atlasops rollout status statefulset/db --timeout=180s
"${kc[@]}" -n atlasops rollout status deployment/api --timeout=180s
printf 'App migration lab ready (separate database). Open via:\n'
printf 'kubectl --context kind-atlasops -n atlasops port-forward --address 127.0.0.1 svc/api 8088:8000\n'
