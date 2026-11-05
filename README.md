# AtlasOps

A local DevOps portfolio lab: ship a Python task API through TLS and a WAF, obtain secrets from Vault, observe it, rotate its key, test backups, and recover a failed release.

Built for a learner targeting DevOps internships in Morocco. Research checked **5 November 2026**. Read [the job-market evidence](docs/JOB_MARKET.md), [runbooks](docs/RUNBOOKS.md), [learning plan](docs/LEARNING_PLAN.md), and [validation record](docs/VALIDATION.md). The [36-page handbook](docs/AtlasOps_DevOps_Handbook.pdf) explains the complete build and the tradeoffs; [PDF build instructions](docs/PDF_BUILD.md) are included.

## Start here

Use a Linux machine or VM with Docker Engine and the Docker Compose v2 plugin (2.24+), Python 3.10+, OpenSSL, curl, Git and Make. Ubuntu 22.04/24.04 amd64 is the documented target. Docker must already be running and accessible to your user.

```bash
cd atlasops
make up
```

This generates local credentials and a 30-day self-signed certificate, starts PostgreSQL and persistent Vault, initializes/unseals Vault, creates a least-privilege AppRole, starts the API/WAF/NGINX and monitoring, then runs HTTPS/WAF/API checks. The first run downloads images and builds the app. No cloud account is required.

Open **https://localhost:8443**. The browser will warn about the lab certificate; confirm it is your local lab before accepting, or import `.certs/server.crt` into a dedicated testing profile. Scripts trust this specific certificate; they do not disable TLS verification.

```bash
cat .secrets/api-key                 # Paste into the web board; keep it private.
cat .secrets/grafana-password        # Grafana username: admin.
```

Secrets are intentionally never committed or included in the delivered archive. `make down` stops containers and preserves volumes. `make up` unseals Vault on a later start. Changing generated database-password files does not change an already initialized database password.

## Choose the size of the lab

| Command | Starts | Suggested host allocation, not measured minimum |
|---|---|---|
| `make lite` | API, PostgreSQL, Vault/Agent, NGINX, WAF | 4 GB RAM, 2 CPUs |
| `make up` | Lite + Prometheus, Grafana, Alertmanager, Blackbox | 8 GB RAM, 4 CPUs |
| `make full` | Monitoring + Elasticsearch, Logstash, Kibana | 16 GB RAM, 4 CPUs, 15 GB free disk |

Switching to a smaller profile does not stop previously started optional services. Use `make down` first when reducing the stack. Full logging mode disables Elasticsearch mmap for this small lab, so a host `vm.max_map_count` change is not required. This trades some performance for easier local startup.

## What is included

| Skill | Concrete evidence |
|---|---|
| Docker / Compose | Multi-stage nonroot API image, health dependencies, isolated networks, profiles and named volumes |
| NGINX / ModSecurity | TLS 1.2/1.3 ingress, rate limits, OWASP CRS in blocking mode, local XSS/SQLi probes |
| HashiCorp Vault | Persistent Raft storage, initialization/unseal, KV v2, read-only AppRole, Agent template, hot rotation and snapshots |
| Prometheus / Grafana | Application metrics, TLS/readiness probe, five alert rules and a provisioned six-panel dashboard |
| ELK | Structured application/ingress logs, Logstash file offsets and persistent queue, seven-day indices, Kibana data view |
| Make / Python / Bash | Repeatable startup, smoke tests, backups, isolated restore, release and rollback, bounded traffic generator |
| CI/CD | GitHub Actions tests, PostgreSQL integration, runtime smoke/drills, Trivy gates, publishing the exact tested image to GHCR |
| Terraform / AWS | Optional VPC, subnet, route, security group, SSH key and encrypted EC2 instance; no apply runs automatically |
| Ansible | Idempotent preparation of a dedicated Ubuntu Docker host |
| Kubernetes | Separate kind exercise with StatefulSet, PVC, Secret, Deployment, probes, resource limits and explicit context |

Vault and Terraform are different **HashiCorp products**. Terraform creates infrastructure; Ansible configures a host; Compose runs this application's services; Vault manages access to secrets.

## Architecture

```mermaid
flowchart TD
  Browser["Browser / HTTPS 8443"] --> Edge["NGINX: TLS + rate limits"]
  Edge --> WAF["ModSecurity + OWASP CRS"]
  WAF --> API["Python task API"]
  API --> DB["PostgreSQL"]
  Vault["Vault KV v2"] --> Agent["Vault Agent / AppRole"]
  Agent --> Secret["Rendered API-key file"]
  Secret --> API
```

Prometheus scrapes the API and probes the complete HTTPS path through Blackbox. Grafana queries Prometheus; Alertmanager displays routed alerts. API and NGINX write JSON logs to a shared volume that Logstash reads into Elasticsearch; Kibana searches those documents. No service mounts `/var/run/docker.sock`.

## Local interfaces

All published ports bind to `127.0.0.1`.

| Service | Local URL | Access |
|---|---|---|
| App | https://localhost:8443 | API key for task data |
| HTTP redirect | http://localhost:8080 | Redirects to HTTPS |
| Grafana | http://localhost:3000/d/atlasops | `admin` + generated password |
| Prometheus | http://localhost:9090 | Local lab only |
| Alertmanager | http://localhost:9093 | Local UI; no notifications sent |
| Vault | http://localhost:8200 | Root recovery material is local; never give it to the app |
| Kibana | http://localhost:5601 | Local lab only; logging profile |
| Elasticsearch | http://localhost:9200 | Local lab only; logging profile |

The API, PostgreSQL, and WAF have no published host ports. `/metrics` is blocked at public ingress and scraped internally.

## Demonstrate the project

```bash
make smoke             # TLS, auth, CRUD, WAF block, hidden metrics
make load              # 100 local requests, bounded to roughly 5/s
make rotate-key        # New key works; previous key stops working
make backup            # Prints a .backups/...dump path
make restore-test FILE=.backups/REPLACE_WITH_ACTUAL_DUMP.dump
make drill             # Stops API, waits for alert, recovers automatically
make verify            # Prometheus HTTPS probe + Grafana
make verify-full       # Also requires at least one ELK document
make config-check      # Native tools in containers; pull Logstash if necessary
```

Refresh the AppRole bootstrap credential with `make vault-refresh` after 24 hours. If Vault restarts and seals, run `make vault-unseal`. A cached rendered key survives a Vault outage; this is explicitly documented and is not an instantaneous revocation guarantee.

## Tests and delivery

```bash
make dev-install
make test
# Optional real PostgreSQL integration:
TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/TEST_DB' make test
# Optional native Vault integration:
VAULT_BIN=/absolute/path/to/vault make test
```

Push the source to your own repository to run `.github/workflows/ci.yml`. Successful `main` pushes publish an image under `ghcr.io/OWNER/REPOSITORY:COMMIT_SHA`. No repository was created or published for you. Configure repository Actions/package permissions as required by your GitHub account. Fork pull requests cannot publish.

```bash
make deploy IMAGE=ghcr.io/OWNER/REPOSITORY:COMMIT_SHA VERSION=COMMIT_SHA
make rollback
```

Deployment pulls/uses a distinct image, waits for API readiness, recreates the proxy layers, checks the complete path and records the previous image. A failed gate triggers restoration of the old image. A short interruption is possible. This is a controlled single-host release, not zero-downtime blue/green deployment.

`make up` builds source only when `APP_IMAGE=atlasops-api:local`. After a release, it preserves the selected release image. To return to source development, explicitly set `APP_IMAGE=atlasops-api:local` and `APP_VERSION=local` in `.env` before running `make up`.

`make lock` resolves downloaded infrastructure images to immutable digests in `compose.lock.yaml`; the wrapper automatically includes that file. The releasable API is deliberately excluded. Review the lock and use `git add -f compose.lock.yaml` if committing it. Changing `.env` image tags does not override an existing lock: remove/recreate that lock deliberately before upgrading. Retest after updates.

## Scope and limits

This is an educational single-host platform, not a production-ready multi-tenant service. Vault uses one recovery share and local HTTP on an isolated Docker network. The root recovery material remains on the host to make the lab restartable. ELK and management UIs rely on loopback isolation; ELK security is disabled. The shared API key has no user roles. No multi-node HA, public certificate automation, external alert delivery, dynamic DB credential leases, automated schema migrations or off-host backups are claimed.

The full container stack must still be exercised on a Docker host. See the exact performed and pending checks in `docs/VALIDATION.md` before claiming results on your CV. Cloud and Kubernetes extensions are separate exercises and are not prerequisites for the main project.
