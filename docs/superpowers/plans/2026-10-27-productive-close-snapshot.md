# Productive close snapshot repair

Goal: restore the productive editor after backend rejected an obsolete approval hash.
Evidence: runtime trace14:28:06, IdOS2231965, _validated_close_operation1096
rejected approved_state_hash before the official API or material preparation.
Lookup refreshes backend snapshots, but the browser kept its previous order list
and mixed its hash with the lookup's newer identity/import scope. Installer GET
was separately missing from the private route policy; material inventory GET200.

Implementation (inline, existing isolated worktree):
- [x] RED: behavioral frontend tests prove fresh lookup updates only exact open
  rows, authorization fields remain from one complete response, older captures
  cannot replace newer list state, and unrelated/blocked/closed rows are refused.
- [x] GREEN: sync authorized lookup rows into current UI list; use one coherent
  row when preparing the editor and preserve materials/equipment drafts. Remove
  cross-response fallback in the direct close payload. Keep server guards intact.
- [x] Add exact GET installer to the existing read policy and regression tests;
  validate through real Worker read. No mutation endpoint is added.
- [x] Run full quality gate, packaging checks and independent review; publish
  Worker with rollback then website using prior authorized deployment scope.
- [x] Record tests and limits. Do not replay a real productive close without
  rechecking technician, equipment/materials and current Imperium state.

Verification:34 focused JS tests,949 Python/22skip,JS/Ruff/build and3release passed. Independent review found intervening-list freshness overwrite; RED/GREEN guard now refuses delayed response. Historical/manual sources remain supported. Productive payload is preserved in real prepare+submit behavioral test with9materials/equipment.

Published PR22/mainb8bf3e6, Workerf5170254; Actions40553080599 attempt2success after attempt1restart500. Public JavaScript hash and installer GET200 verified. Operational productive close remains pending, no real close replay.
