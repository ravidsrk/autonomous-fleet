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
FLEET_HOME="${AUTONOMOUS_FLEET_HOME:-}"
if [ -z "$FLEET_HOME" ]; then
  this_script="$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${BASH_SOURCE[0]}")"
  # this_script -> skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh
  # repo root   -> 4 levels up
  FLEET_HOME="$(cd "$(dirname "$this_script")/../../../.." && pwd)"
fi

CLI="$FLEET_HOME/scripts/stop_verify.py"
if [ ! -x "$CLI" ] && [ ! -f "$CLI" ]; then
  # Same fail-open discipline as the Python CLI: a missing CLI must NOT
  # trap a session. Log + ALLOW (silent stdout).
  echo "stop-verify: warning — CLI not found at $CLI; allowing session end." >&2
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
exec python3 "$CLI" --window-min "$WINDOW_MIN" "${EXTRA_ARGS[@]}" "$@"
