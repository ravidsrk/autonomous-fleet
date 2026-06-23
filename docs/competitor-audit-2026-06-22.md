# Competitor audit — 2026-06-22 (borrowed patterns)

In-repo record of the external audit the 4-layer verification substrate was adapted from.
Reference docs and `engine.md` cite this file (item numbers below) instead of a private
machine path.

## Status & provenance discipline

These patterns are **research-sourced** (an external scan of competing agent frameworks), then
**adapted into the fleet and validated by the in-repo substrate** — the JSON schemas
(`assets/fleet-review-findings.schema.json`, `assets/fleet-run-manifest.schema.json`), the Python
implementation (`scripts/lib/{verify_findings,stop_verify,fleet_run}.py`), and the test suite
(`tests/test_{review_findings_schema,verify_findings,stop_verify,run_archive}.py`) all enforce them.

Per [CONTRIBUTING.md](../CONTRIBUTING.md)'s Distillation Discipline, research-sourced patterns are
validated before they sit in `engine.md`. Here the validation is implementation + tests rather than
a fleet `*-progress.md` run. **Not yet validated by an external end-to-end fleet run** — that
remains a follow-up (see `docs/external-dogfood/`).

## Frameworks reviewed
- **SWE-Review** (Wang et al., 2026) — agentic review prompt; "write your proposed fix before
  reading the patch" step.
- **claude-code-orchestra** — `.claude/hooks/stop-verify.sh`, an mtime-window evidence scan.
- **multi-llm-plugin-cc** — `stop-review-gate-hook.mjs`, the `{decision:"block"}` Stop-hook JSON contract.
- (also surveyed: GodModeSkill, xreview)

## Borrowed patterns (cited by number)
- **#2 — stop-verify gate.** mtime-window evidence scan (claude-code-orchestra) + the
  `{decision:"block"}` JSON contract (multi-llm-plugin-cc), composed for the fleet's
  progress.md/readiness.md ledger format. → strict mode / RUNTIME ENFORCEMENT GATE.
- **#3 — root-cause depth.** A finding must trace cascade impact, not just the surface symptom
  (SWE-Review HARD RULE). → `category: root_cause_depth` schema constraint.
- **#4 — anti-anchoring / blind-fix.** Propose the fix before reading the existing patch, so the
  reviewer isn't anchored by the author's framing (SWE-Review step 3). → blind-fix-first protocol +
  mtime ordering.
- **#8 — run-archive.** A per-run manifest-audited file trail (composed for the fleet across the
  multi-vendor patterns surveyed). → `.fleet/runs/<run_id>/` + manifest schema.
