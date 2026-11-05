# Validation record

Checked on **5 November 2026**. This record distinguishes executable tests, configuration checks and work requiring a Docker/cloud host.

| Check | Result | Meaning / limitation |
|---|---|---|
| Python test suite with native Vault enabled | **25 passed, 1 skipped**, 27.83 seconds | Includes application behavior, persistence with SQLite, configuration checks and a real Vault/Agent integration test |
| PostgreSQL-specific test | **Skipped here** | No PostgreSQL server was available; a real PostgreSQL service is configured in CI |
| Real Vault 2.1.1 + Vault Agent | **Passed** | Persistent Raft server initialization, leader readiness, AppRole login, allowed read, denied write/unrelated read, template rendering, key rotation, snapshot, seal/unseal |
| Docker Compose 2.39.4 configuration | **Passed** | Full monitoring/logging model parsed by Compose; no containers executed |
| Prometheus 3.13.5 promtool | **Passed** | Five alert rules, alert timing test and config syntax; the native config check changed only the mounted rule-file path to a local path |
| Alertmanager 0.28.1 amtool | **Passed** | Configuration valid; one local receiver, no external delivery |
| Ansible 2.21.6 syntax check | **Passed** | No host provisioning was performed |
| Terraform 1.13.4 formatting and HCL parsing | **Passed** | AWS provider 6.72.0 initialized and lock file created |
| Terraform provider-backed validate | **Blocked by this runtime** | Provider could not create its local Unix socket: operation not permitted. Run terraform validate and plan on your machine; neither is claimed passed |
| JavaScript syntax check | **Passed** | Browser automation not performed; Chromium download was unavailable |
| Docker Hub / Elastic image manifests | **14 references resolved** | Availability only; see image-manifests.json. This is not execution or a security scan |
| Full Docker stack, WAF runtime, PostgreSQL backup/restore, ELK ingestion and release recovery | **Not executed here** | Docker daemon unavailable. Executable smoke, verification, configuration and drill commands are supplied; CI runs these on a Docker runner |
| AWS apply / Ansible run / kind cluster | **Not executed** | No account or host mutations, no cloud spend |
| Trivy security scans / GitHub Actions workflow | **Not executed here** | Workflow is supplied; a green CI run and clean scans are not claimed |

The test suite emits one upstream Starlette warning about future migration from httpx to httpx2 in its TestClient. Tests passed with the pinned httpx dependency; this warning is not suppressed.

A genuine integration issue was found and fixed during validation: Vault's unseal response can arrive before the Raft leader becomes active. Bootstrap now waits for a healthy active leader before writing mounts and policies. The subsequent native Vault test passed.

A final startup review also checked two cases with mocked Compose: the development image is built, while a selected release image is preserved on restart. Both passed; this is an orchestration check, not a container execution test. Shell syntax was checked after the change.

## Your acceptance sequence

```bash
make up
make smoke
make rotate-key
make backup
make restore-test FILE=.backups/ACTUAL_FILE.dump
make drill
make full
make verify-full
make config-check
```

For the optional AWS extension, run `terraform fmt -check`, `terraform init`, `terraform validate` and an account-specific `terraform plan` before considering an apply. For Kubernetes, complete `make k8s-up` and inspect pod health in the explicitly named context.

Do not copy this record into a CV as proof that you personally operated the stack. Complete the exercises, collect your own results and describe this as a personal learning project.
