# First external run with autonomously-landed PRs — doc-sync on ravidsrk/gemoji

**Status:** DONE (2026-07-03) · **Run:** `20260703T054520Z-doc-sync-3e8173`
**Archive:** [`.fleet/runs/20260703T054520Z-doc-sync-3e8173/`](../../.fleet/runs/20260703T054520Z-doc-sync-3e8173/) (validates: manifest + sha256 + mtime ordering + findings-independence; trace: 20 events, 0 invalid)
**Closes:** framework issue #76 (M1 "Prove it")

## What happened

`doc-sync` ran end-to-end against `ravidsrk/gemoji` (fork **hard-synced to
upstream `github/gemoji` master** immediately before the run, so all drift was
real upstream drift, not residue of the 2026-06-19 interactive dogfood):

| PR | Task | Content | Review |
|----|------|---------|--------|
| [gemoji#8](https://github.com/ravidsrk/gemoji/pull/8) | T-FIX-contributing | D-001..D-003 (Ruby version claim, release-script description) | PASS, fresh reviewer |
| [gemoji#9](https://github.com/ravidsrk/gemoji/pull/9) | T-FIX-comments | D-004..D-007 (release comment, `edit_emoji` overstatement, category provenance, `db:generate` description) | PASS, fresh reviewer |
| [gemoji#10](https://github.com/ravidsrk/gemoji/pull/10) | T-FINAL | audit (all CLOSED) + ledger + readiness | **round 1 FAIL → fix → round 2 PASS** |

`fleet-outcome`: `status: done`, `prs_merged: 3`, `drift_open: 0`,
`code_bug_findings: 1` (deferred to `bug-batch`: `Emoji.edit_emoji` is add-only;
stale aliases stay resolvable — the comment now tells the truth, the behaviour
was deliberately not changed by a doc mission).

## Topology (recorded honestly)

- **Coordinator:** claude-code adapter, interactive coordinator session.
- **Builders:** fresh `codex exec -s workspace-write` per task (sandboxed:
  workspace writes only, no network).
- **Reviewers:** fresh `codex exec` per PR, given ONLY the PR diff +
  acceptance criteria — build-blind as separate processes, same-vendor
  (single-vendor caveat per engine.md; codex reviewed codex).
- **Integrator:** coordinator via `gh` — push, PR, conflict-aware merge-commit
  merges, remote branch deletion. Every outward action went through the
  coordinator host's permission surface.

**What this run is NOT:** a single-process headless run. The
`run-mission-headless.sh codex --yolo` path (codex
`--dangerously-bypass-approvals-and-sandbox`) was **denied by the host
permission layer** (auto-mode classifier) — an unattended sandbox-bypass run
requires explicit operator opt-in outside auto mode. That denial is recorded in
the run's DECISIONS and remains the honest gap for a fully-headless external
run.

## The review discipline earned its keep

Round 1 of the T-FINAL review **failed the PR** for self-attesting its own
merge state (`prs_merged: 3`, `REVIEWED/MERGED=t` written before the merge
they describe) and for branch-deletion claims contradicted by stale
remote-tracking refs. The fix round rewrote both as verifiable-after-the-fact
claims routed to the run archive. The FAIL→fix→PASS trail is in
`review-pr10-verdict.md` and the trace.

## Verify it yourself

```bash
python scripts/validate_run_archive.py .fleet/runs/20260703T054520Z-doc-sync-3e8173
python scripts/emit_trace.py validate .fleet/runs/20260703T054520Z-doc-sync-3e8173/trace.jsonl
gh pr list --repo ravidsrk/gemoji --state merged --limit 3
```
