---
name: security-cso-audit
description: >-
  [Tier 2 · moderate autonomy · full review gate · security-specialist] Run a gstack-style CSO
  security audit (secrets archaeology, supply chain, CI/CD, OWASP, STRIDE, LLM/skill supply chain)
  with daily or comprehensive modes, freeze findings, then remediate confirmed issues one PR at a
  time with skeptic narrowing. Distinct from general adversarial-review-and-fix by infrastructure-
  first CSO lenses. Trigger on: "CSO audit", "security audit mission", "OWASP review", "threat
  model this repo", "run /cso as a fleet mission", "supply chain security pass".
license: MIT
compatibility: Requires git and gh CLI in the target repository
metadata:
  author: "ravidsrk"
  version: "1.0.0"
  tier: "2"
  fleet-component: "mission"
  recommended-bundle: gstack-security
  community-recommends:
    bundle: gstack-security
    skills:
      - cso
      - investigate
    mode: warn
status: exploratory
---

> **Status: exploratory.** Mapped from gstack `cso` + `investigate`; not yet field-proven.
> See `docs/exploratory/missions/README.md`.


# Mission: security-cso-audit

## Required skills

Before executing, activate these skills and read their full instructions:

1. `autonomous-fleet-core` — read `references/engine.md`, `references/composition.md`, safety refs
2. One runtime adapter: `autonomous-fleet-adapter-orca`, `autonomous-fleet-adapter-claude-code`,
   `autonomous-fleet-adapter-grok`, or `autonomous-fleet-adapter-codex`

```yaml community-recommends
bundle: gstack-security
skills:
  - cso
  - investigate
mode: warn
```

## Optional skills

| Skill | Activate when | If unavailable |
|-------|---------------|----------------|
| `cso` (gstack) | User invoked CSO / security audit explicitly | Mission T-AUDIT checklist |
| `investigate` (gstack) | Finding needs root-cause depth before fix | @claude investigate task |
| `careful` (gstack) | Destructive remediation commands possible | Core sandbox + careful prompts |
| `health` (gstack) | Composite scorecard requested | Mission readiness metrics only |

Community catalog: `autonomous-fleet-core` → `references/community-skills.md`. At most 2 optional
skills active.

## Worker skills

| Role | Skills | If unavailable |
|------|--------|----------------|
| @claude (CSO audit, skeptic) | `cso` when Optional active | Mission audit script |
| @codex (remediation builder) | `security-and-hardening` patterns | In-tree fix per frozen finding |
| @claude (fresh build-blind reviewer) | — | Mission review gate |
| @claude (integrator) | — | Ship gate |

Stage-9 cross-vendor rule: @codex builds; fresh @claude reviews without build context.

## Deferred missions

Record in `<LEDGER_DIR>/security-readiness.md` under **Recommended next missions**.

| Finding type | Route to |
|--------------|----------|
| General non-security architecture debt | `adversarial-review-and-fix` (shipped) |
| Dependency-only CVE sweep | `dependency-update` (exploratory) |
| Doc/runbook security gaps | `doc-sync` (shipped) |

## AUDIT MODE (user or default)

| Mode | gstack analogue | Confidence gate | Default when |
|------|-----------------|-----------------|--------------|
| **daily** | CSO daily pass | 8/10 to report | Routine CI/pre-ship |
| **comprehensive** | CSO monthly deep | 2/10 to report | Explicit user request |

Record mode in `<LEDGER_DIR>/security-progress.md` frontmatter.

## GOAL

Identify, freeze, and **close** confirmed security findings across secrets, dependencies, CI/CD,
application OWASP surface, threat model (STRIDE), and agent/skill supply chain — without fixing
phantom issues.

## ROLE PIPELINE

- @claude runs **CSO audit** (infrastructure-first ordering per gstack `/cso`).
- @claude **skeptic pass** splits confirmed vs refuted; only confirmed enter CLOSE-INDEX.
- @codex **remediates** one finding per PR with tests where applicable.
- Fresh build-blind @claude **reviews** each fix.
- @claude writes `<LEDGER_DIR>/security-readiness.md` with trend vs prior audit if exists.

## LEDGER

`<LEDGER_DIR>/security-progress.md` — phase flags + audit mode.

Frozen artifacts:
- `docs/security-findings.md` — ranked findings with Fix + acceptance + CODE vs CODE+OPS tag.
- `docs/security-close-index.md` — per-finding `OPEN | IN_PROGRESS | CLOSED | REFUTED`.

## TASK STRUCTURE

- **T-AUDIT [@claude]** — CSO pass: secrets archaeology, deps, CI/CD, OWASP, STRIDE, LLM/skill
  supply chain. Output `docs/security-findings.md` (DRAFT).
- **T-SKEPTIC [@claude, fresh session]** — refute weak findings; update REFUTED rows in close-index.
- **T-FREEZE [@claude]** — mark findings FROZEN; confirmed set is fix-loop input only.
- **T-CLOSE-LOOP [per confirmed finding]** — @codex fix → fresh @claude review → @claude ship →
  CLOSE-INDEX `CLOSED`.
- **T-FINAL [@claude]** — zero OPEN confirmed findings (or documented accepted risk with owner);
  output `<LEDGER_DIR>/security-readiness.md` with **`fleet-outcome` YAML** (`findings_confirmed`,
  `findings_closed`, `findings_refuted`, `audit_mode`).

## THREE-LANE REMEDIATION

Inherit engine LANE PATTERN. Tag each finding in close-index: `LANE_A` (implement+merge),
`LANE_B` (draft+human gate), `LANE_0` (refuse+surface). CSO daily mode defaults to reporting
only LANE_A candidates with confidence ≥ 8/10.

## Runtime goal

```
Mission security-cso-audit DONE: docs/security-close-index all confirmed rows CLOSED or
accepted-risk documented, <LEDGER_DIR>/security-readiness.md fleet-outcome.status done,
./scripts/validate-fleet-outcome.sh passes.
```

## DONE

Frozen findings addressed, skeptic-refuted items not fixed, all CLOSE-INDEX confirmed rows terminal,
`<LEDGER_DIR>/security-readiness.md` with valid fleet-outcome.

## DECISION DEFAULTS (mission-specific)

- Infrastructure before application surface (gstack CSO ordering).
- No fix without confirmed finding ID in close-index.
- Secrets in fixes: env vars only, never committed.
- Supply-chain findings need version pin evidence, not advisory text alone.
- Comprehensive mode may report low-confidence leads as `WATCH`; daily mode suppresses them.