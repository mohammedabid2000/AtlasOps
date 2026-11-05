# AtlasOps security scope

This educational project is intended for your trusted local machine or a dedicated private demo VM. Keep all published endpoints bound to 127.0.0.1. Do not publish the management ports or disable host isolation while assuming the WAF secures the whole stack.

Generated keys, Vault recovery material, database dumps and Terraform state must not be committed. Local directories containing them are ignored by Git and source-build contexts. Before uploading screenshots, inspect them for credentials.

This project uses TLS at ingress, a blocking WAF, parameterized database access, nonroot application execution, per-service file secrets, a minimal Vault policy, bounded application metrics and sanitized application/NGINX logs. These controls do not constitute a security certification.

Known educational tradeoffs are described in README.md and docs/RUNBOOKS.md: single-host availability, local HTTP for Vault, one recovery-share holder, root material retained for helper scripts, unauthenticated loopback management UIs, ELK security disabled, persistent bootstrap credentials and a shared application API key.

Dependency and container scans are CI gates, not proof that a system has no vulnerabilities. Upgrade baselines deliberately, inspect advisories and rerun acceptance checks. Registry manifest availability is not a vulnerability scan.
