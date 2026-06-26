---
finding_id: F-001
reviewer: grok
---

# Blind fix for F-001

The point of creation is `scripts/lib/fleet_run.py:progress_text_for_mission:239` —
the function joins `docs/` with `{mission}-progress.md` instead of calling
`mission_registry.progress_path(mission)`, so remapped missions like
`adversarial-review-and-fix` never open `docs/arch-build-progress.md`.

The shape of the fix is a one-line resolution change: import `progress_path`
from `lib.mission_registry` and open `source_root / progress_path(mission)`.
Add a regression test asserting the adversarial mission excerpt contains the
arch-build ledger header.

Pre-commit confidence: 90/100.