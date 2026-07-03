# Adapter shared contract — single-sourced blocks (issue #89)

Every adapter previously carried these blocks as verbatim copy-paste; any
engine contract change was a 5-file lockstep edit with nothing catching
drift. The canonical text lives HERE; adapters state a pointer plus ONLY
their runtime-specific bindings (a drift lint fails an adapter that
re-inlines a copy).

## RESUMABILITY + REVIEWER ISOLATION (Wave 3 contract)

- run_short: every isolated branch and worktree carries the active run's 6-hex suffix
  (`<BRANCH_PREFIX><slug>-<run_short>`, `../<repo>-<slug>-<run_short>`, run_short = the 6-hex tail of
  the run_id) so parallel runs/checkouts never collide on a bare slug.
  `<SUBSTRATE>/validate_namespacing.py` enforces this.
- CONTINUE_WORKER(role, placement, session_handle): bind to the runtime's restore command — the
  ADAPTER declares it (its Primitive Support Matrix row + a `CONTINUE_WORKER binding:` line);
  no restore command -> ALIAS to SPAWN_WORKER (idempotent relaunch). Re-attach only for
  `live`-classified rows (per `recovery_scan.py`); never re-attach a session whose PR merged or
  branch is gone. When a row's `RESUME_COUNT` hits `MAX_RESUME_ATTEMPTS` (3), escalate instead of
  continuing.
- Reviewer isolation: when role==reviewer, launch the worker via
  `scripts/run-sandboxed.sh --role reviewer -- <reviewer-cli>` (framework clone only) so the
  candidate tree is read-only and only `.fleet/runs/<run_id>/` is writable.
