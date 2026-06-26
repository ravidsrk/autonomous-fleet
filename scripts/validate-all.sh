#!/usr/bin/env bash
# Run all autonomous-fleet validators and tests.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=lib/venv-bootstrap.sh
source "$ROOT/scripts/lib/venv-bootstrap.sh"
bootstrap_validation_venv "$ROOT"

echo "== validate-skills =="
./scripts/validate-skills.sh

echo ""
echo "== validate-fleet-outcome =="
./scripts/validate-fleet-outcome.sh

echo ""
echo "== validate-goal-condition =="
./scripts/validate-goal-condition.sh --scan-docs

echo ""
echo "== validate-run-archive =="
# Run-archive scheme (engine.md ARCHIVE_ENABLED). Default scan looks under
# .fleet/runs/ for any run_id-shaped directories. No archives = exit 0 (the
# discipline is gated on artifact production, not on a directory existing).
"$VENV_PYTHON" scripts/validate_run_archive.py
# Plus the canonical example fixture (Commit A scaffolding). The fixture
# directory is named `example-fixture/` (not the YYYYMMDDTHHMMSSZ-... form)
# so the default run-id-pattern scan above intentionally skips it. We pass
# it as an explicit positional so the validator hits it every CI run; the
# manifest's run_id field IS a regex-valid id, so the cross-checks still
# match. See `.fleet/runs/example-fixture/README.md`.
if [[ -d .fleet/runs/example-fixture ]]; then
  "$VENV_PYTHON" scripts/validate_run_archive.py .fleet/runs/example-fixture
fi

echo ""
echo "== verify-blind-fix (Layer 3) =="
# Layer 3 (anti-anchoring) verifier. Spec: references/blind-fix.md.
# Scans every .fleet/runs/<run_id>/ archive that contains a
# p0-review-findings.json and validates each finding has a valid
# blind-fix file (canonical or explicit chain path). No archives = exit 0.
# The glob `.fleet/runs/*/` includes the canonical `example-fixture/`
# directory along with any real run_id-shaped directories.
shopt -s nullglob
bf_status=0
for run_dir in .fleet/runs/*/; do
  if [[ -f "$run_dir/p0-review-findings.json" ]]; then
    if ! "$VENV_PYTHON" scripts/verify_blind_fix.py "$run_dir"; then
      bf_status=1
    fi
  fi
done
shopt -u nullglob
if (( bf_status != 0 )); then
  echo "verify-blind-fix: at least one archive failed Layer 3" >&2
  exit 1
fi

echo "== verify-sha-pin =="
# A reviewer PASS is bound to the reviewed SHA. If a sha-pin.json's reviewed_sha has
# diverged from the branch HEAD, REVIEWED is OUTDATED. No sha-pin.json = exit 0.
shopt -s nullglob
sp_status=0
for run_dir in .fleet/runs/*/; do
  if ! "$VENV_PYTHON" scripts/verify_sha_pin.py "$run_dir"; then
    sp_status=1
  fi
done
shopt -u nullglob
if (( sp_status != 0 )); then
  echo "verify-sha-pin: at least one reviewed SHA is outdated" >&2
  exit 1
fi

echo "== verify-round-budget =="
# A task that exhausted its review-round budget must have gone BLOCKED, not MERGED.
shopt -s nullglob
rb_status=0
for run_dir in .fleet/runs/*/; do
  if ! "$VENV_PYTHON" scripts/verify_round_budget.py "$run_dir"; then
    rb_status=1
  fi
done
shopt -u nullglob
if (( rb_status != 0 )); then
  echo "verify-round-budget: a task exceeded its round budget without BLOCKED" >&2
  exit 1
fi

echo "== registry-lint =="
# The mission/adapter registry must match the on-disk catalog + skills-lock.
if ! "$VENV_PYTHON" scripts/registry_lint.py .; then
  echo "registry-lint: the catalog has drifted from the registry" >&2
  exit 1
fi

echo ""
echo "== verify-reviewer-sandbox =="
# The reviewer is read-only: its producer slug must not be attributed any
# diff/commit kind on the candidate branch. No reviewed manifests = exit 0.
shopt -s nullglob
rs_status=0
for run_dir in .fleet/runs/*/; do
  if ! "$VENV_PYTHON" scripts/verify_reviewer_sandbox.py "$run_dir"; then
    rs_status=1
  fi
done
shopt -u nullglob
if (( rs_status != 0 )); then
  echo "verify-reviewer-sandbox: a reviewer was attributed a write on the candidate" >&2
  exit 1
fi

echo ""
echo "== validate-namespacing =="
# Every recorded worktree path + branch must carry the run's -<run_short>
# suffix so parallel runs/checkouts never collide. No archives = exit 0.
shopt -s nullglob
ns_status=0
for run_dir in .fleet/runs/*/; do
  if ! "$VENV_PYTHON" scripts/validate_namespacing.py "$run_dir"; then
    ns_status=1
  fi
done
shopt -u nullglob
if (( ns_status != 0 )); then
  echo "validate-namespacing: a recorded branch/worktree is not run-namespaced" >&2
  exit 1
fi

echo ""
echo "== validate-trace (telemetry contract) =="
# Trace stream (engine.md TRACE EMISSION). One JSONL line per state
# transition; the schema is the dashboard contract (vibe-kanban, Agent View,
# custom). Empty/missing = exit 0 (the discipline is gated on artifact
# production, not on a directory existing). Picks up the example-fixture
# trace.jsonl along with any real-run trace files.
shopt -s nullglob
tr_status=0
for trace_file in .fleet/runs/*/trace.jsonl; do
  if ! "$VENV_PYTHON" scripts/emit_trace.py validate "$trace_file"; then
    tr_status=1
  fi
done
shopt -u nullglob
if (( tr_status != 0 )); then
  echo "validate-trace: at least one archive failed schema validation" >&2
  exit 1
fi

echo ""
echo "== validate-headless (mechanical dry-run wiring) =="
./scripts/validate-headless.sh

echo ""
echo "== pytest + coverage (100% gate) =="
"$VENV_PYTHON" -m coverage run --source=scripts -m pytest tests/ -q
"$VENV_PYTHON" -m coverage report --fail-under=100

echo ""
echo "All checks passed."
