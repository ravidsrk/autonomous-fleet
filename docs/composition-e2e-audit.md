# composition-e2e — doc-sync audit (DRIFT INDEX)

Dogfood campaign on `autonomous-fleet` after worker-skills + fleet-outcome + campaigns shipped.

| ID | Area | Doc said | Code truth | Status |
|----|------|----------|------------|--------|
| D1 | README layout | Only `validate-skills.sh`, `install-skills.sh` | Full `scripts/` tree + `tests/` | **CLOSED** (PR #4–#5) |
| D2 | README validate §3 | Only skill validation | `validate-all.sh`, fleet-outcome, goal-condition | **CLOSED** |
| D3 | install-skills.sh | "16 fleet skills" | 19 publishable skills | **CLOSED** |
| D4 | doc-sync-readiness.md | No `fleet-outcome` frontmatter | Required per fleet-outcome.md | **CLOSED** |
| D5 | doc-sync-readiness.md | "16/16 pass" | 19 skills | **CLOSED** |

No code-bug findings (`code_bug_findings: 0`).