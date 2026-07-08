# DECISIONS — adversarial-review-and-fix c6c486

## Self-orientation

| Field | Value |
|-------|-------|
| repo | `ravidsrk/autonomous-fleet` |
| REPO_ROOT | `/workspace` |
| MAINTAINER | Cursor Agent `<cursoragent@cursor.com>` |
| BRANCH_PREFIX | `cursor/` |
| BASE | `cursor/adversarial-review-base-256a` off `main`@e9e541b |
| Adapter | `autonomous-fleet-adapter-grok` (same-vendor-instructed review) |
| LEDGER_DIR | `.fleet/docs/` (docs-site Starlight probe) |
| RUN_ID | `20260708T184204Z-adversarial-review-and-fix-c6c486` |
| RUN_SHORT | `c6c486` |
| SUBSTRATE | `/workspace/scripts` |
| AUTHORSHIP_MODE | `attributed` |
| reviewer_mode | `same-vendor-instructed` |

## ASSUMPTIONS

1. Scope = entire autonomous-fleet app (skills, scripts, substrate, CI, action, docs-site tooling).
2. Fresh-run: ignore prior review docs; write `docs/adversarial-review-fresh.md`.
3. Out of scope: BASE→main promotion, production deploy, secret rotation, load/prod verification.
4. SCM: `gh` authenticated as `cursor`; PRs merge into BASE with `--merge` (never squash).
5. Lane B findings open as draft `do-not-merge` PRs; never auto-merge.

## Skeptic decisions

- SEC-006 DO_NOT_FIX (version-tolerant auth probe).
- SEC-005/009/004/010/ARCH-004/ARCH-005 → Lane B (ask / human-gate or draft-both).
- OPS-001 narrowed: fatal only on real-run archive emit; dry-run cleanup stays non-fatal.
- Wave 1 Lane A: SEC-001, SEC-002, SEC-003, ARCH-001, ARCH-002, BUG-001 (FOUNDATION first).

## Lane B human gates (c6c486) — draft-both, do not auto-merge

Each finding below has two variants. Operator picks one; neither is auto-merged.

### SEC-004 — SHA-pin GitHub Actions
- **A:** Pin every `uses:` in `action.yml` + workflows to full commit SHAs; Dependabot for bumps.
- **B:** Vendor critical Actions locally (`uses: ./…`) for the composite entrypoint only.
- **Status:** HUMAN_GATED — policy/maintenance choice.

### SEC-005 — Reviewer fallback without real sandbox
- **A:** Refuse `--role reviewer` when neither sandbox-exec nor bwrap is present (unless `FLEET_SECURITY_OVERRIDE_ACK=1`).
- **B:** Keep fallback but emit `SECURITY=DEGRADED` in manifest and fail fleet-verify on that flag.
- **Status:** HUMAN_GATED — skeptic narrowed to low; documented degraded mode.

### SEC-009 — Registry-lint kill switch vs supply-chain pins
- **A:** Require `FLEET_SECURITY_OVERRIDE_ACK` for `FLEET_DISABLE_REGISTRY_LINT` (match sha-pin).
- **B:** Split lint: doc-drift remains disableable; pin/hash checks fail-closed.
- **Status:** HUMAN_GATED — intentional escape hatch today.

### ARCH-004 — Unregistered exploratory SKILL trees
- **A:** Add `MISSIONS` rows for scaffold-align / contract-first-build / agents-layer + lint on-disk ⊆ registry.
- **B:** Remove the three SKILL trees until promotion-ready.
- **Status:** HUMAN_GATED — handoff campaign currently archived/empty.

### ARCH-005 — Archive collector filter mismatch
- **A:** Unify both CLIs on `RUN_ID_PATTERN` via shared `collect_run_archives()`.
- **B:** Keep loose namespacing scan; WARN on non-canonical basenames.
- **Status:** HUMAN_GATED — gate inconsistency, lower blast radius.

### SEC-010 — Stop-verify fail-open on missing repo
- **A:** Opt-in `FLEET_STOP_VERIFY_STRICT=1` → BLOCK when repo missing.
- **B:** Always BLOCK on bad repo (breaking for path drift).
- **Status:** HUMAN_GATED — default allow is intentional operator escape.

### SEC-006 — DO_NOT_FIX (confirmed by skeptic)
Version-tolerant auth probe + timeout watchdog; fail-closed would break validated compatibility.

