# Risk Tiers

<!-- demoted from engine.md (issue #84) -->
═══════════════════════════════════════════════════════════
EMPIRICAL RISK TIERS — which missions to trust unattended (cross-agent merge rates from arXiv
2601.15195, MSR 2026 AIDev dataset, 33,596 agent-authored PRs).
═══════════════════════════════════════════════════════════
- Tier 1 (~62–84% cross-agent, run unattended): doc-sync (~84% documentation), test-coverage
  (~61.5% test), dependency-update (~74% build / ~84% chore), cleanup (~84% chore).
- Tier 2 (~64–79% cross-agent, full review gate, glance at the control artifact): bug-batch
  (~64% fix, reproduce-first), adversarial-review-and-fix, targeted-migration,
  design-integration (no direct category in the study — treat as Tier 2).
- Tier 3 (high blast radius, review the frozen scope/architecture artifact, expect rework):
  take-product-to-completion (no direct category in the study).
- No standalone performance mission — performance is the worst category (~55% cross-agent); keep
  human-gated.
