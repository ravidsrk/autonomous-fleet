# composition-e2e — doc-sync audit (DRIFT INDEX)

Dogfood campaign on `autonomous-fleet` after worker-skills + fleet-outcome + campaigns shipped.

| ID | Area | Doc said | Code truth | Status |
|----|------|----------|------------|--------|
| D1 | README layout | Only `validate-skills.sh`, `install-skills.sh` | Also `validate-fleet-outcome.sh`, `eval-campaign-edge.py`, `validate_fleet_outcome.py`, `lib/fleet_outcome.py`, `tests/` | OPEN → this PR |
| D2 | README validate §3 | Only skill validation | `validate-fleet-outcome.sh` validates readiness YAML | OPEN → this PR |
| D3 | install-skills.sh | "16 fleet skills" | 18 skills (`fleet-program` + umbrella) | OPEN → this PR |
| D4 | doc-sync-readiness.md | No `fleet-outcome` frontmatter | Required per fleet-outcome.md | OPEN → retrofit in this run |
| D5 | doc-sync-readiness.md | "16/16 pass" | 18 skills | OPEN → this PR |

No code-bug findings (`code_bug_findings: 0`).