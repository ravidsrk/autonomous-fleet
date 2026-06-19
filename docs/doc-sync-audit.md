# doc-sync audit — autonomous-fleet

Frozen discovery artifact for T-AUDIT. Code is ground truth.

## DRIFT INDEX

| ID | Area | Doc location | Code truth | Status |
|----|------|--------------|------------|--------|
| D1 | Layout | README.md L93 | `.agents/skills/` holds **copies** installed by `npx skills add`, not symlinks (verified: regular files under `.agents/skills/doc-sync/`) | OPEN |
| D2 | Authoring | README.md L132 | `skill-creator` is **not** in the repo; `.agents/` is gitignored. Must be installed via step 1. | OPEN |
| D3 | Setup | README.md Layout | `.agents/` directory is gitignored (`.gitignore`); fresh clones have only `skills/` until install. | OPEN |
| D4 | Setup | README.md §Validate | `./scripts/validate-skills.sh` requires `skill-creator` at `.agents/skills/skill-creator/` — fails on fresh clone without step 1. | OPEN |

## Verified accurate

- `skills/` contains 16 publishable skills (matches table).
- `./scripts/validate-skills.sh` passes when skill-creator is installed.
- `./scripts/install-skills.sh` and `--all` match script implementation.
- `skills-lock.json` exists and is updated by `npx skills add`.

## Deferred (not doc drift)

- Mission SKILL.md files reference `@claude`/`@codex` role handles — Orca-oriented pipeline labels, not incorrect for Grok adapter (subagent roles). No README change.