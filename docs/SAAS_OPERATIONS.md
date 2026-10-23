# ARIA Managed SaaS Operations

## Required Production Configuration

- `ARIA_SAAS_MODE=true`
- `ARIA_CREDENTIALS_KEY`: a Fernet key used to encrypt tenant credentials.
- `ARIA_BOOTSTRAP_ADMIN_EMAIL`, `ARIA_BOOTSTRAP_ADMIN_PASSWORD`, and `ARIA_BOOTSTRAP_TENANT`: used once to create the first organization administrator.
- `ARIA_COOKIE_SECURE=true`: required behind HTTPS.
- `ARIA_ALLOWED_ORIGINS`: the exact HTTPS browser origin, for example `https://aria.example.com`.
- `ARIA_ALLOWED_HOSTS`: the public hostname only, for example `aria.example.com`.

Customer traffic authenticates with HTTP-only `aria_session` cookies. Do not expose `ARIA_API_KEY` to browser users; it is only for non-SaaS/internal deployments.

Use `GET /api/health` only for process liveness. Configure load balancers and Docker health checks to call `GET /api/health/ready`; it returns `503` until credential encryption, tenant metadata, the run manager, and writable run storage are ready.

Run `make migrate-saas` during deployment before starting API workers. Migrations are ordered SQL files in `aria/api/migrations/` and are tracked in `schema_migrations`.

## Data Layout

Each run is stored under `data/runs/<tenant-id>/<run-id>/`. Customer credentials are stored under `credentials/tenants/<tenant-id>/credentials.json` and are encrypted when `ARIA_CREDENTIALS_KEY` is configured.

The production compose stack includes Redis for in-run collector deduplication. Redis keys are scoped to the exact run (`aria:run:<run-id>:...`), so collection state never crosses tenant or run boundaries. Redis is not the durable research-job queue; a multi-worker deployment still requires a durable queue before horizontal job execution is enabled.

## Backup And Restore

Stop workers or place the service in maintenance mode before taking a consistent backup. Archive `data/aria_saas.db`, `data/runs/`, and `credentials/tenants/` together. Keep the credential encryption key in a separate secret manager; without it encrypted credentials cannot be restored.

To restore, deploy the same ARIA version, restore those paths with restrictive permissions, configure the original `ARIA_CREDENTIALS_KEY`, and start the service. Test restoration in a non-production environment before relying on a backup.

## Scaling Path

SQLite is appropriate only for local development and a small controlled beta. Before concurrent production use, move tenant/user/session/audit metadata to PostgreSQL, run research in durable workers backed by Redis or another queue, and move run artifacts to tenant-prefix object storage. Preserve tenant ownership checks at every API and storage boundary.
