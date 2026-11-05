# Architecture decisions

## ADR 001: a small application, substantial operations

The task board has CRUD endpoints, a persistent database and a shared API key. Its purpose is to make release, observability and recovery behavior visible. A complex business domain would consume time without strengthening the targeted internship skills. The consequence is that this is not a complete multi-user SaaS application.

## ADR 002: Compose as the reference platform

The learner already understands Docker and NGINX. Compose provides a small reproducible environment where network and lifecycle behavior can be explained. Kubernetes is a separate migration lab so orchestration concepts can be learned without duplicating every operational system at once. Neither is high availability on a single machine.

## ADR 003: two proxy layers

The outer NGINX owns certificates, safe access logging, rate limiting and public route restrictions. The OWASP image owns ModSecurity and the CRS lifecycle. This uses a maintained WAF image and keeps the NGINX configuration familiar. It costs one extra hop and requires recreating the WAF when the API address changes.

## ADR 004: an actual Vault server and Agent

Vault uses persistent integrated storage and explicit initialization/unseal, not development mode. AppRole grants only reads on one KV v2 path; Agent renders a key into a file that the app reloads. The local root recovery material and one recovery share are intentional lab compromises. PostgreSQL passwords remain Compose file secrets: this project does not claim Vault dynamic database credentials.

## ADR 005: file-based log collection

API and NGINX write sanitized JSON into a shared volume. Logstash reads the files, persists offsets and queues events. This avoids giving a collector privileged Docker socket access. It requires rotation management, can duplicate events after failure, and is not a complete fleet-wide logging design.

## ADR 006: controlled release and optional cloud

CI validates and publishes the exact image that passed runtime checks. A host-side command performs the release and rollback. This avoids embedding permanent SSH credentials into CI and makes deployment observable to the operator. It has a brief interruption and is not automatic continuous deployment. Terraform provisions a private demo VM reachable through a restricted SSH rule, with dashboards still on loopback.
