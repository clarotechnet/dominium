# TOA lookup private bridge implementation plan

**Goal:** Restore the existing Buscar no TOA action after its old quick tunnel expired.
**Architecture:** Route only POST /api/toa-live/lookup through the existing authenticated Worker and IMPORT_SERVICE on port 8765. Preserve the backend lookup, profile validation, Hostinger session/CSRF checks and all close restrictions.
**Execution:** Native in the existing isolated worktree, authorized by the user's request to fix the action.

## Constraints and review focus

- Only admin/controller may invoke this POST. No connect, close, inventory or arbitrary route is added.
- Preserve JSON, remove browser credentials at the private boundary, cap lookup bodies at 64 KiB.
- Accept exactly one known profile query parameter and reject extra parameters/path encodings.
- No automatic retry; a failed lookup must stay an explicit error.
- Deploy Worker before Hostinger; keep previous source for rollback. Do not restart Chrome or close an OS.

## Task 1: Restore transport and verify

- [x] Add failing tests in tests/test_operational_relay.js and integrations/import_bridge/worker.test.mjs for routing, JSON, roles, profile checks, body size and upstream errors.
- [x] Add allowedToaLookup to deploy/hostinger-web/operational-policy.js; use it in operational-relay.js and worker.mjs. Keep the existing backend unchanged.
- [x] Run focused tests, full quality gate and Hostinger release build. Review the final diff against the constraints.
- [ ] Back up and deploy Worker source; publish tested source to GitHub main using the existing Hostinger workflow.
- [ ] Verify authenticated lookup of contract 4321295 and the live UI when its login is available. Record actual tests and remaining blockers.

Verification: 4 new tests failed before implementation; 23 focused tests passed afterward. Full gate: 960 Python tests, 22 skipped; JavaScript, Ruff and build passed. Hostinger release: 3 dependency/build tests passed. Fresh reviewer found no blocking issues. Legacy loopback POST lookup returned one Natal activity in 11.49 seconds; no backend session/CSRF regression.
