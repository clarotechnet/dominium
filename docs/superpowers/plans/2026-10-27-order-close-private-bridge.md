# Order close private bridge implementation plan

**Goal:** Restore the existing single-OS official API close action after the old quick tunnel expired.
**Architecture:** Use the existing Hostinger session/CSRF boundary and authenticated Worker to reach the unchanged Windows panel on port 8765. Allow only scoped POST /api/orders/<id>/close with official_http; do not introduce retries or change backend validation.
**Execution:** Inline in the existing isolated worktree. User has requested a functioning flow and already authorized publication/installation with backup.

## Constraints and review focus

- Authentication, admin/controller, CSRF, exact city and positive OS ID required.
- JSON object up to 64 KiB; reject DataSnap because the legacy panel does not preserve per-user DataSnap identity.
- Forward the original close scope/material/technician fields unchanged. No lookup/stock write expansion.
- One upstream request. Transport timeout, redirect or invalid response is uncertain, never successful and never automatically retried.
- Deploy Worker first with rollback available, then Hostinger. Preserve the Chrome session and Windows runtime.
- Verify through synthetic invalid inputs that cannot close an OS; query the candidate's current state. Do not replay the user's productive payload without reviewing its materials.

## Task 1: Repair and verify transport

- [x] Add regression tests for middleware authentication/CSRF, city and transport validation, successful/pending/rejected replies and uncertain single-call failures; run RED.
- [x] Implement order-close-proxy.js, exact route policy, Worker routing and release inclusion; run GREEN.
- [x] Run full quality gate and release checks. Review the complete diff.
- [x] Back up Worker, deploy, publish to main without overwriting concurrent changes and verify production safely.
- [x] Record actual results and distinguish transport verification from successful productive close.

Worker deployed45b3f101; safe canary reached backend400, anonymous401/viewer403.
Main push blocked by approval auto-review. Prepare draft PR; no equivalent merge
or direct Hostinger deploy attempted. See docs/agent/ORDER_CLOSE_PRIVATE_BRIDGE_20261027.md.

Authorized publication complete: PR21 merged858dc6a; Actions40548766963success, production smokes passed. UI requires login, productive close unverified.
