# Turn the repository into skills you can defend

Use this as a six-week sequence at roughly 8-12 focused hours per week, not a promise of how fast you will learn. Rebuild and explain each layer yourself. Commit your own decisions and incident notes.

| Week | Work | Demonstrable finish |
|---|---|---|
| 1 | Linux processes, permissions, TCP/DNS/TLS; inspect Dockerfile, API, volumes and networks | Explain one request from browser to database; run CRUD and stop/restart without losing data |
| 2 | NGINX, TLS, CRS blocking, rate limits and secrets hygiene | Show a legitimate request succeeding and local attack probes returning 403; explain a false positive |
| 3 | Vault lifecycle, policies, AppRole, Agent and rotation | Show a read-only token unable to write; rotate a key without restarting the API |
| 4 | Prometheus, PromQL, Grafana, Alertmanager, JSON logs and ELK | Trigger a real alert, correlate a request ID and write an incident note |
| 5 | Git branches/PRs, CI gates, image tags/digests, release/rollback, backup/restore | A green pipeline on your repository; a recovered failed release; an isolated restore with measured duration |
| 6 | Terraform state/plan, AWS basics, Ansible idempotence and kind | Explain the cloud plan; complete one optional VM or Kubernetes exercise and record actual results |

Your highest-value additions for internships are Linux/networking fluency, Git/CI/CD, Bash/Python, Terraform, one cloud provider and Kubernetes basics. Do not postpone applying until you know every tool in this repository. Show clear evidence for the parts you have actually practiced.

## Suggested Git issues

1. Explain and diagram the request and secret flows.
2. Rebuild the API image and prove it runs without root.
3. Verify TLS and WAF behavior; record a harmless false-positive investigation.
4. Demonstrate Vault policy denial and API-key rotation.
5. Add one useful dashboard panel and justify the metric.
6. Diagnose a database outage using readiness and logs.
7. Restore a backup and record task count and duration.
8. Run CI on a pull request and explain each failure gate.
9. Deploy a new image and perform a rollback.
10. Complete the kind exercise or optional Terraform/Ansible VM.

For each issue, write acceptance criteria before implementation and attach your own command output or screenshot after it passes. Do not fabricate green badges or timings.

## Ten-minute interview demonstration

| Time | Show | Explain |
|---|---|---|
| 0-1 min | Architecture diagram and `make status` | Ownership boundaries and why profiles exist |
| 1-2 min | Web board and a task | Request path, authentication, persistence |
| 2-3 min | `make smoke` | WAF versus application validation; trusted TLS |
| 3-4 min | `make rotate-key` | Policy, AppRole and Agent render lifecycle |
| 4-6 min | Grafana, then `make drill` | Scrape versus end-to-end probe; alert pending/firing/resolved |
| 6-7 min | Kibana request ID, if full mode is ready | Structured logs and what you deliberately do not log |
| 7-8 min | Isolated restore evidence | Backup success versus recoverability |
| 8-9 min | CI run and tested image tag | Artifact identity and release gates |
| 9-10 min | Your incident note and next improvement | Tradeoffs, limitations and what you learned |

Pre-pull images and practice before the interview. Keep all keys and root material off-screen. If full ELK does not fit your laptop, show real previously captured evidence and say so.

## CV wording - use after you run and understand the relevant features

**English title:** AtlasOps - DevOps / DevSecOps Portfolio Lab

- Built a Docker Compose platform for a Python/PostgreSQL service with NGINX TLS, ModSecurity/OWASP CRS, and Vault AppRole-based secret delivery.
- Automated CI tests, container security scans and versioned image publishing; implemented health-checked releases, rollback and isolated database restore drills.
- Instrumented the service with Prometheus/Grafana and centralized JSON logs with Elasticsearch, Logstash and Kibana; documented incident investigation and recovery.

**French title:** AtlasOps - Projet personnel DevOps / DevSecOps

- Conteneurisation d'une API Python/PostgreSQL avec Docker Compose, reverse proxy NGINX/TLS, WAF ModSecurity/OWASP CRS et gestion des secrets avec Vault/AppRole.
- Automatisation des tests CI, scans de securite et publication d'images versionnees ; deploiement avec controle de sante, retour arriere et tests de restauration.
- Supervision avec Prometheus/Grafana et centralisation des logs JSON dans ELK ; redaction de procedures d'exploitation et de reprise.

Add Terraform/AWS, Ansible or Kubernetes to these bullets only after completing the corresponding exercise. Add a number only if you measured it, such as your actual restore duration or test count. Label this **personal project**, not employment or production experience.

## Questions to prepare

- What is the difference between a process being alive and a service being ready?
- Why is Docker group membership effectively root access?
- Why can changing a secret file fail to rotate an existing PostgreSQL password?
- How does Vault Agent get its first credential, and what happens when that credential expires?
- Does stopping Vault instantly revoke a key already cached by the application?
- Why does a WAF not replace parameterized SQL or authentication?
- Why are route templates better than task IDs as Prometheus labels?
- What does p95 mean, and why is it misleading with almost no traffic?
- How do you prove a backup is recoverable?
- Which tool owns infrastructure, host configuration and application deployment?
- What could make an image rollback fail after a schema change?
- What would you change before exposing this system to the internet?
