# Archived exploratory missions

These mission designs are parked, not deleted. They remain available as historical source material under this archive, but they are excluded from the active exploratory mission set until they earn fresh evidence and a clear reason to exist beside the shipped surface.

| Mission | Why it is parked |
|---|---|
| `security-cso-audit/` | Overlaps the shipped `adversarial-review-and-fix` mission: its CSO/security-audit loop is a subset of the shipped adversarial audit-and-fix surface without separate run evidence proving a distinct lane. |
| `landing-page-convergence/` | Overlaps active `design-integration`: single-page convergence is narrower than the design-integration mission's whole-product design adoption path. |
| `release-document/` | Doc-only tail without enforcement machinery: it describes post-ship documentation and deploy checklist work, but does not yet prove a gated loop with run artifacts. |
| `devex-audit/` | Doc-only tail without enforcement machinery: it freezes scorecards and gap indexes, but lacks an enforced close loop backed by real-run evidence. |
| `product-framing/` | Doc-only tail without enforcement machinery: it freezes a product spec before implementation, but does not yet prove the downstream enforcement path. |
| `legacy-rebuild/` | High blast radius without evidence: a full rebuild has the largest preservation burden and needs stronger proof than doctrine before it can stay active. |

## Un-parking rule

A parked mission may leave `archive/` only when its promotion PR cites the standard evidence triple:

1. a real-run `docs/<mission>-progress.md`,
2. a matching `docs/<mission>-readiness.md` with a valid `fleet-outcome` block, and
3. an external-repo run archive under `.fleet/runs/` or `docs/external-dogfood/`.

If the mission overlaps a shipped or active mission, the PR must also include a written differentiation argument explaining why this mission should exist separately instead of being folded into the overlapping shipped surface.
