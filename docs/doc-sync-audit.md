# doc-sync audit — autonomous-fleet

Latest audit: **v0.2.0 metrics pass** (2026-06-27, `main`).

> Historical passes: 2026-06-20 community-skills (below); first trial at bottom.

## DRIFT INDEX (2026-06-27)

| ID | Area | Doc said | Code truth | Status |
|----|------|----------|------------|--------|
| D15 | README version badge | 0.1.0 | `VERSION` = 0.2.0 | **CLOSED** |
| D16 | README test metrics | 37 files / 936 tests | 53 files (auto-guarded) | **CLOSED** |
| D17 | README skill count (layout) | implied 20 | 12 under `skills/` + 12 exploratory | **CLOSED** |
| D18 | Orca headless | unspecified | interactive-only; `run-*.sh` grok\|claude\|codex | **CLOSED** |

Guard: `tests/test_readme_drift.py` fails CI if README counts drift again.

## DRIFT INDEX (2026-06-20)

| ID | Area | Doc said | Code truth | Status |
|----|------|----------|------------|--------|
| D6 | README skills table | 18 skills listed; no `setup-autonomous-fleet` | 20 publishable skills under `skills/` | **CLOSED** |
| D7 | README starter install | Omits `setup-autonomous-fleet` | `./scripts/install-skills.sh` installs it | **CLOSED** |
| D8 | README layout / references | No `community-skills.md`, `external-dogfood/` | Shipped in core + `docs/` | **CLOSED** |
| D9 | README validate §3 | No `--repo` external campaign example | `run-campaign.sh --repo PATH` | **CLOSED** |
| D10 | doc-sync-readiness.md | "19/19 pass" | 20 skills + `validate-all.sh` | **CLOSED** |
| D11 | composition-e2e-audit D3/D5 | "19 skills" | 20 skills | **CLOSED** |
| D12 | research-skill-composition §1 | "17 skills published" | 20 skills | **CLOSED** |
| D13 | skills-lock.json | Missing `setup-autonomous-fleet` entry | Refreshed via `npx skills add` | **CLOSED** |
| D14 | composition-e2e-reasoning follow-up | Only repo-health gemoji dogfood | ship-with-proof evidence added | **CLOSED** |

No code-bug findings (`code_bug_findings: 0`).

## Verified

```bash
./scripts/validate-all.sh                    # 12 skills, fleet-outcome, goals, pytest
./scripts/run-campaign.sh grok --preset ship-with-proof --dry-run
./scripts/run-campaign.sh grok --preset repo-health --repo /tmp/gemoji --dry-run  # when gemoji cloned
```

---

## Historical — first trial (superseded)

> Superseded by `composition-e2e-audit.md` and earlier readiness on `fleet/composition-e2e-base`.
> Kept for history — items D1–D4 closed via PR #1 and README updates.

| ID | Area | Resolution |
|----|------|------------|
| D1 | `.agents/` copies not symlinks | CLOSED — documented in README |
| D2 | skill-creator not bundled | CLOSED — step 1 in README |
| D3 | `.agents/` gitignored | CLOSED — documented in README |
| D4 | validate-skills needs skill-creator | CLOSED — documented in README §Validate |