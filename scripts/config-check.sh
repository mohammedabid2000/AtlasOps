#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dc=(bash scripts/compose.sh)
"${dc[@]}" --profile monitoring --profile logging config --quiet
"${dc[@]}" --profile monitoring run --rm --no-deps --entrypoint promtool prometheus check config /etc/prometheus/prometheus.yml
"${dc[@]}" --profile monitoring run --rm --no-deps -w /etc/prometheus --entrypoint promtool prometheus test rules alerts.test.yml
"${dc[@]}" --profile monitoring run --rm --no-deps --entrypoint amtool alertmanager check-config /etc/alertmanager/alertmanager.yml
"${dc[@]}" exec -T nginx nginx -t
"${dc[@]}" exec -T waf nginx -t
"${dc[@]}" --profile logging run --rm --no-deps logstash --config.test_and_exit
printf 'PASS: Compose, Prometheus config/rules, Alertmanager, both Nginx layers, Logstash.\n'
