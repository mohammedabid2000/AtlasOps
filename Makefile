SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help init doctor lite up full down status logs test dev-install smoke verify verify-full rotate-key vault-refresh vault-unseal backup restore-test vault-snapshot drill load deploy rollback lock config-check elastic-setup rotate-logs k8s-up k8s-down

help:
	@printf 'AtlasOps: make lite | up | full | down | status | smoke | test\n'
	@printf 'Operations: rotate-key | vault-refresh | backup | restore-test FILE=... | drill\n'
	@printf 'Delivery: deploy IMAGE=... VERSION=... | rollback | lock | config-check\n'
	@printf 'Optional: k8s-up | k8s-down. Read docs before cloud deployment.\n'
init:
	python3 scripts/ops.py init
doctor: init
	bash scripts/doctor.sh
lite:
	bash scripts/up.sh lite
up:
	bash scripts/up.sh monitoring
full:
	bash scripts/up.sh full
down:
	bash scripts/compose.sh --profile monitoring --profile logging down
status:
	bash scripts/compose.sh --profile monitoring --profile logging ps -a
logs:
	bash scripts/compose.sh --profile monitoring --profile logging logs --tail=80
dev-install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
test:
	.venv/bin/python -m pytest -q tests
smoke:
	python3 scripts/ops.py smoke
verify:
	python3 scripts/ops.py verify
verify-full:
	python3 scripts/ops.py verify-full
rotate-key:
	python3 scripts/ops.py rotate
vault-refresh:
	python3 scripts/ops.py vault-bootstrap
	bash scripts/compose.sh up -d --force-recreate vault-agent
vault-unseal:
	python3 scripts/ops.py vault-unseal
backup:
	bash scripts/backup.sh
restore-test:
	bash scripts/restore-test.sh "$(FILE)"
vault-snapshot:
	python3 scripts/ops.py vault-snapshot
drill:
	bash scripts/drill.sh
load:
	python3 scripts/load.py --requests 100
deploy:
	bash scripts/deploy.sh "$(IMAGE)" "$(VERSION)"
rollback:
	bash scripts/deploy.sh --rollback
lock:
	python3 scripts/lock-images.py
config-check:
	bash scripts/config-check.sh
elastic-setup:
	python3 scripts/ops.py elastic-setup
rotate-logs:
	bash scripts/rotate-logs.sh
k8s-up:
	bash scripts/k8s.sh up
k8s-down:
	bash scripts/k8s.sh down
