# Technician names in the backlog comparison

The private localhost backlog sidecar is installed independently of the operational app.
Apply the zero-context unified technician-names.patch (git apply --unidiff-zero) to its verified backlog_sidecar.py and copy
backlog_technician_names.py into the same application directory.

The adapter reuses TechnicianDirectory from the existing Imperium source path.
The optional --technicians-file argument defaults to C:\\DominiumMain\\config\\technicians.json.
This catalog is newer than the legacy Imperium runtime catalog. Names reload on
file modification; no additional Imperium or TOA calls are needed.

Only GET /api/backlog/year/compare is enriched. Existing report clients receive
technician = NAME (LOGIN), plus explicit technician_login and technician_name.
The SQLite route login, grouping identity, contracts, historical dates/codes and
counts are preserved. Unknown logins and pre-existing names pass through unchanged.
No WhatsApp messages, OS writes, stock changes or new public endpoints are involved.

Before rollout, test the existing report formatter against the same comparison
before/after enrichment. Back up the sidecar, verify no read job is running,
restart only the verified listener on 9342, and compare authenticated GET results.
Rollback: restore the backed-up sidecar and restart with the existing
ensure-backlog-sidecar.ps1 launcher.

19 November 2026 lookup: the current catalog and bot registry identified 16 of the
17 selected-route technicians. Z705513 is not in the inspected registrations.
Do not infer a name or change technician ownership to hide the missing mapping.
