# DOMINIUM site import bridge

Hostinger authenticates the operator and validates role and CSRF before the import middleware uses its server-only relay token. The Worker checks that token and forwards only four import routes to a fixed Workers VPC service on `127.0.0.1:8765`.

The named tunnel is `dominium-import-server` (`cb6a307b-66f4-4f64-be2a-c0dcbb61db1a`). It uses the existing Cloudflare account; no zone, DNS or TOA authentication changes are needed. The endpoint is `https://dominium-import-bridge.jogador743.workers.dev`. Workers VPC is currently an open beta; check its availability/pricing before changing the account plan.

The Worker `IMPORT_TOKEN` secret must match the existing `DOMINIUM_DESC_REVIEW_CONNECTION.token` deployment secret. Hostinger reads that token from the private release configuration, never a browser asset. No credentials belong in this directory.

On the Windows server, the connector and its restart supervision are installed under `C:\DominiumRuntime\ImportBridge`. The named connector can restart without changing the endpoint. The Python runtime must already be running; this bridge never starts application workers or logs into TOA.

Deployment: run Node bridge tests, the repository quality gate, deploy `wrangler.jsonc` using the existing authorized Wrangler session, and publish the Hostinger release through its existing workflow. Set the Worker secret through stdin from the authorized private token file, never a command argument.

Verification must use `GET /api/import-targets` and `POST /api/imports/preview`. Never use `/commit` as a smoke test. POSTs are not retried. If a commit response is lost, inspect import history and exact OS state before repeating.
