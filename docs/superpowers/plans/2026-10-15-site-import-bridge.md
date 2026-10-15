# Site import bridge implementation plan

**Goal:** Restore the existing Hostinger CSV import flow without changing DNS, TOA sessions or automatic closure workers.

**Architecture:** An authenticated Workers VPC endpoint connects through a named tunnel to the existing loopback runtime. Hostinger keeps session, operational role and CSRF enforcement and uses its existing private relay credential. Only import targets, preview, commit and audit history are reachable. CSV bytes, filename, target and approval hashes pass unchanged. Requests are never automatically retried.

**Constraints:** No real imports or closures for validation. Preserve all current UI and city routing. Never expose runtime configuration or credentials. A disconnected commit has an uncertain outcome and must be checked before repeating.

1. Write and run regression tests for authentication, CSRF, route isolation, payload integrity, large files, upstream failures and no retries.
2. Implement the Hostinger middleware and VPC Worker; package the middleware and increase only import JSON limits to match the local runtime.
3. Run focused tests and the repository quality gate in this isolated checkout.
4. Deploy the private bridge, install tunnel restart supervision and publish the current deployed site branch with the narrow fix.
5. Verify unauthorized requests are blocked, authorized preview reaches the existing parser, and the local closure/import services remain active. Do not submit a commit to production.

Review focus: malicious URL/query, missing deployment credential, body above the old 256 KB limit, dropped response after commit, tunnel reconnect with the same identity.
