# Operating AtlasOps

## Start, stop and inspect

```bash
make up
make status
bash scripts/compose.sh logs --tail=80 api vault-agent nginx
make down
```

Use `make full` for ELK. `down` preserves data. There is intentionally no convenient production-data wipe target. Never use `docker compose down -v` on a lab you want to preserve. CI uses `-v` only on its disposable runner.

## API unavailable

1. Check the external path: `curl --cacert .certs/server.crt https://localhost:8443/health/ready`.
2. Check `make status`. A running container can still be unhealthy.
3. If the API cannot connect to PostgreSQL, inspect `bash scripts/compose.sh logs --tail=60 db api`. Check service DNS, initialized database roles and password-file consistency.
4. If the rendered secret is missing, inspect Vault and Agent health. Run `make vault-unseal` after Vault restarts; run `make vault-refresh` when the AppRole SecretID expires.
5. If the API is healthy but ingress fails, inspect NGINX and WAF logs; validate configurations with `nginx -t` inside both containers.
6. If an IP changed during a manual API recreation, recreate the WAF so it resolves the new upstream. The release script already does this.
7. Confirm recovery with `make smoke` and wait for the next Prometheus evaluation to resolve alerts.

`/health/live` only proves the process responds. `/health/ready` also checks the database and a usable rendered API key. Do not restart an otherwise healthy application repeatedly just because a dependency is temporarily down.

## Demonstrate an incident

Run `make drill` with monitoring active. It stops the API, waits for the actual `AtlasApiDown` firing state and starts the API again. Its exit trap attempts recovery even when interrupted. Watch Prometheus Alerts and Alertmanager locally. Capture the observed detection and recovery times in `docs/EVIDENCE_TEMPLATE.md`; do not replace them with guessed results.

For a database-only incident, use `bash scripts/compose.sh stop db`, observe readiness failures while process liveness remains up, then `bash scripts/compose.sh start db`. Run this manually on your disposable lab, not during a release. API reconnection uses SQLAlchemy pool pre-ping. If startup happens while DB is unavailable, bounded startup retries eventually fail visibly.

## Rotate the API key

```bash
make rotate-key
cat .secrets/api-key
```

The script writes a new value to Vault KV v2 and saves the new local client key. Agent polls static secrets every 10 seconds and atomically replaces its rendered file. The API re-reads that file per authenticated request. The script verifies the new key works and the old key fails; it does not restart the API. Allow up to 90 seconds for the bounded check.

If confirmation times out, do not lose the new key or keep retrying rotations. Inspect Agent health, use `make vault-refresh`, and test the current `.secrets/api-key`. The browser holds the old key in memory until you reconnect it.

The AppRole token lasts 10 minutes and can renew up to one hour; Agent re-authenticates as needed. The bootstrap SecretID lasts 24 hours. Reissue it with `make vault-refresh`. This bounded credential is deliberately not an unattended production identity solution.

## Vault restart and recovery

Vault runs in persistent server mode, not `-dev`. Its Raft data survives normal restarts. After a process restart it seals; `make vault-unseal` uses the local recovery share. If `.secrets/vault-init.json` is missing for an existing Vault volume, startup stops and requires the original material. It never silently reinitializes or overwrites a mismatched Vault.

`make vault-snapshot` writes a Raft snapshot into `.backups`. Treat it and recovery material as sensitive. The repository does not implement automated Vault snapshot restore; follow the official Raft restore guide in an isolated clone and preserve the original unseal material. A Vault snapshot alone is not a PostgreSQL backup.

Production upgrades: multiple independently held recovery shares or cloud auto-unseal; TLS between clients and Vault; audited human access; short-lived workload identity; root-token revocation after configuring a replacement administrator; off-host encrypted snapshots. Do not revoke the lab root token first and then expect its helper scripts to keep working.

## Database backup and isolated restore

```bash
make backup
# Replace the following path with the printed output:
make restore-test FILE=.backups/postgres-YYYYMMDDTHHMMSS-NNN.dump
```

`pg_dump --format=custom` produces a logical snapshot. The script writes a temporary file, renames only on success and records SHA-256. The restore script checks the hash, creates a unique temporary database in the same PostgreSQL instance, restores in a single transaction and queries `tasks`. An exit trap removes only that temporary database. It never replaces `atlasops`.

A passing restore drill confirms that this dump can be restored and queried, not that you have automatic disaster recovery. An off-host copy is still required to survive loss of the VM. Define an RPO (maximum acceptable data loss) and RTO (maximum acceptable recovery duration), choose a backup frequency, then measure the restore. A proposed daily backup implies up to about 24 hours of data loss; this project does not schedule that job for you.

## Release and rollback

```bash
docker build -t atlasops-api:demo-v2 .
make deploy IMAGE=atlasops-api:demo-v2 VERSION=demo-v2
make rollback
```

Use a unique tag or registry digest for every release. The script inspects the running image, checks the new one, switches the API, recreates proxies, runs the complete smoke test and only then records the new desired image in `.env`. If a gate fails, it attempts to restore the previous image and reports failure. The previous release is in `.state/previous-release.json`.

This process can interrupt traffic. Database schema v1 is created at app startup; no destructive migrations run. If you later add schema changes, use an expand/migrate/contract approach and test old/new compatibility. Rolling back an image does not undo an incompatible database migration.

## Investigate logs

After `make full`, open Kibana Discover, select the `atlasops-*` data view, and set the time window to the last 15 minutes. Try:

```text
service: "atlasops-api" and status >= 500
service: "nginx" and status: 403
request_id: "COPY_A_REAL_REQUEST_ID"
```

API logs use route templates, status, duration and request IDs. They omit bodies, keys and query strings. NGINX logs also omit query strings and headers. WAF audit output excludes request headers/bodies; it is not part of this file-ingestion pipeline. An ingress 403 plus an isolated WAF log check is the expected investigation route.

Logstash remembers offsets in its data volume and has a persistent queue. Delivery is not exactly-once: a crash or rotation can produce duplicates. The API rotates four 2 MB files. Run `make rotate-logs` to rotate NGINX logs; automation of that task is left to the host operator. Elasticsearch indices use seven-day retention after `make elastic-setup`. Vault audit logs are separate and also require an operator retention policy for longer use.

If Discover is empty: run `make load`; check `make verify-full`; inspect Logstash for parse or permission errors; check Elasticsearch health and the selected time window. Restarting Logstash should not require deleting its sincedb.

## Common failures

| Symptom | Likely cause / action |
|---|---|
| Permission denied for Docker | Start the daemon, use appropriate permissions, reconnect after group membership change |
| Port already allocated | Stop the conflicting local service; do not casually expose the lab on all interfaces |
| Certificate error | Expired 30-day certificate or wrong hostname/CA; renew in the local lab and restart NGINX/Blackbox |
| 401 after rotation | Reconnect the web board with the new key |
| Vault sealed after restart | `make vault-unseal` |
| Agent auth errors after a day | `make vault-refresh` |
| Database password authentication failed | Existing DB retained its original password; restore matching secret or rotate role deliberately |
| 502 after manual API replacement | Recreate WAF and NGINX; use release script next time |
| ELK exits / is slow | Check memory limits and host resources; use monitoring profile first |
| Grafana says No data | Generate traffic and wait for scrape/rate windows; inspect Prometheus targets |
| Trivy fails CI | Inspect the exact advisory and upgrade/retest; do not convert the gate to an unconditional pass |

## Certificate renewal in this disposable lab

Keep a copy of the old cert if needed, then generate a replacement with the same SANs. This operation changes local trust; update the dedicated browser profile and restart the probe to reload its CA. Never replace certs belonging to another service.

```bash
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
  -keyout .certs/server.key -out .certs/server.crt \
  -subj '/C=MA/O=AtlasOps Lab/CN=localhost' \
  -addext 'subjectAltName=DNS:localhost,DNS:nginx,IP:127.0.0.1'
chmod 600 .certs/server.key
chmod 644 .certs/server.crt
bash scripts/compose.sh restart nginx blackbox
make smoke
make verify
```
