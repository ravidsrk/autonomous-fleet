#!/usr/bin/env bash
# autonomous-fleet stop-verify hook — Claude Code Stop hook entry point.
#
# This is the thin shell wrapper Claude Code's hook system invokes. It
# delegates to scripts/stop_verify.py which does the actual evidence scan
# and emits the {decision:"block", reason:"..."} JSON CC expects on stdout.
#
# How CC invokes this:
#   1. Worker reaches a Stop event (session terminating, "done" declared)
#   2. CC pipes a JSON {session_id, cwd, last_assistant_message, ...} to stdin
#   3. CC reads stdout — if it contains {"decision":"block"}, session is
#      refused and the worker must address the reason before stopping
#   4. CC reads stderr — surfaces to the operator (and the agent context)
#      regardless of allow/block
#
# Install: copy this file to .claude/hooks/stop-verify.sh in any repo, then
# register it in .claude/settings.json's `hooks.Stop` array. See
# references/strict-mode.md for the full installation walkthrough.
#
# Why a wrapper (not a direct python invocation): adapters install via
# `cp` into per-project .claude dirs, and the Python CLI's path varies
# (worktrees, venvs, monorepos). A shell wrapper resolves the autonomous-
# fleet checkout once and forwards.
#
# Lineage: claude-code-orchestra/.claude/hooks/stop-verify.sh (mtime-window
# evidence scan) + multi-llm-plugin-cc/stop-review-gate-hook.mjs
# (ALLOW/BLOCK contract). Composed for autonomous-fleet's EVID/WT_CLEAN
# /e2e_verified disciplines.

set -uo pipefail
# NB: no `set -e` — we MUST emit a valid hook response even if a subshell
# fails, otherwise CC sees an empty stdout and assumes "no decision" =
# allow. That's actually the safe default (fail-open), but we want it to
# happen explicitly via _emit_decision, not as a side effect of a crashed
# wrapper.

# ── Resolve the autonomous-fleet repo path ────────────────────────────
# Operators set AUTONOMOUS_FLEET_HOME to the checkout root. If unset, we
# walk up from this script's location — works when the hook is installed
# as a SYMLINK from .claude/hooks/ to skills/autonomous-fleet-adapter-claude-code/assets/hooks/.
# Candidates, first hit wins (issue #82 — skills-install repos have no
# framework clone; the bundled substrate ships the CLI):
#   1. $FLEET_SUBSTRATE/stop_verify.py   — explicit substrate dir
#   2. $AUTONOMOUS_FLEET_HOME/scripts/…  — explicit clone root (legacy)
#   3. walk-up from this script: the clone's scripts/ (clone symlink
#      layout — BEFORE the worker repo's copy so a stale bundle never
#      shadows the clone the wrapper shipped from)
#   4. <cwd>/.agents/skills/autonomous-fleet-core/assets/substrate/…
#      (Claude Code runs Stop hooks with cwd = the worker repo), then —
#      when the wrapper was copied into <repo>/.claude/hooks/ — that
#      repo's .agents substrate
this_script="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${BASH_SOURCE[0]}")"
walkup_root="$(cd "$(dirname "$this_script")/../../../.." && pwd)"
hookdir_root="$(cd "$(dirname "$this_script")/../.." && pwd)"  # <repo>/.claude/hooks -> <repo>
CLI=""
# Order note (codex review on #114): the clone walk-up comes BEFORE the
# cwd .agents substrate so a wrapper invoked from a framework clone never
# gets shadowed by a stale bundled copy in the worker repo.
for candidate in \
  "${FLEET_SUBSTRATE:+$FLEET_SUBSTRATE/stop_verify.py}" \
  "${AUTONOMOUS_FLEET_HOME:+$AUTONOMOUS_FLEET_HOME/scripts/stop_verify.py}" \
  "$walkup_root/scripts/stop_verify.py" \
  "$PWD/.agents/skills/autonomous-fleet-core/assets/substrate/stop_verify.py" \
  "$hookdir_root/.agents/skills/autonomous-fleet-core/assets/substrate/stop_verify.py"; do
  if [ -n "$candidate" ] && [ -f "$candidate" ]; then
    CLI="$candidate"
    break
  fi
done
if [ -z "$CLI" ]; then
  # Same fail-open discipline as the Python CLI: a missing CLI must NOT
  # trap a session. Log + ALLOW (silent stdout).
  echo "stop-verify: warning — stop_verify.py not found (tried FLEET_SUBSTRATE, AUTONOMOUS_FLEET_HOME, clone walk-up, .agents substrate); allowing session end." >&2
  exit 0
fi

# Pass the CC stdin JSON through verbatim. Default to 30-min window; operators
# can override via STOP_VERIFY_WINDOW_MIN env var, kept as an env knob (not
# a hooks.json arg) because the hooks.json layout differs across CC versions
# and env vars are the lowest-common-denominator config surface.
WINDOW_MIN="${STOP_VERIFY_WINDOW_MIN:-30}"
EXTRA_ARGS=()
if [ -n "${STOP_VERIFY_STRICT_PROGRESS:-}" ]; then
  EXTRA_ARGS+=(--strict-progress)
fi
if [ -n "${STOP_VERIFY_EXPLAIN:-}" ]; then
  EXTRA_ARGS+=(--explain)
fi
if [ -n "${STOP_VERIFY_MIN_KINDS:-}" ]; then
  EXTRA_ARGS+=(--min-kinds "$STOP_VERIFY_MIN_KINDS")
fi

# "$@" is forwarded last so operator-supplied flags (`--repo`, `--explain`,
# etc., useful when invoking the wrapper by hand from a terminal) override
# our env-derived defaults via argparse's last-wins behavior.
exec python3 "$CLI" --window-min "$WINDOW_MIN" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} "$@"
