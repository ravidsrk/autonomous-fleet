#!/usr/bin/env python3
"""CLI: Claude Code Stop-hook gate. Refuses session termination without
evidence that fleet disciplines (EVID, WT_CLEAN, e2e_verified) were satisfied.

Contract — Claude Code Stop hook:
  stdin:  JSON {session_id, cwd, last_assistant_message, ...} (per CC spec)
  stdout: JSON {decision:"block", reason:"..."} to refuse termination
          OR empty / non-decision JSON to allow termination
  exit:   0 always (CC treats non-zero as a hook error, not a block — we
          encode block via the JSON `decision` field, matching how
          multi-llm-plugin-cc's stop-review-gate-hook.mjs does it)

CLI flags:
  --repo PATH            Repo to scan (default: stdin's `cwd` or CWD)
  --window-min N         Freshness window in minutes (default 30)
  --strict-progress      Require EVID=true AND WT_CLEAN=true in ledger
  --min-kinds N          Minimum distinct evidence kinds (default 1)
  --explain              Human-readable verdict on stderr regardless of mode
  --json-out             Force JSON decision on stdout even if ALLOW
                         (useful when wired as `command` in hooks.json so
                         CC sees a {continue:true} payload)

Operator escape hatch (no flag — env-only so it survives subprocessing):
  STOP_VERIFY_DISABLED=1   Hook returns ALLOW immediately.

Exit codes (for harness use, NOT for CC):
  0  Verdict produced (allow OR block — semantics in the JSON decision)
  2  Usage error (bad stdin, bad --repo, etc.)

Hardening:
  - We NEVER raise to the CC harness. Any internal error is rendered as
    ALLOW with a stderr warning. A broken hook MUST NOT trap a worker
    mid-session — that's a worse failure than a missed gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.stop_verify import (  # noqa: E402
    StopVerifyConfig,
    Verdict,
    evaluate,
)


def _read_hook_input(timeout_sec: float = 2.0) -> dict:
    """Read CC's Stop-hook JSON from stdin. CC pipes a JSON object to stdin
    on hook invocation. If stdin is a TTY (interactive debug), or empty, or
    malformed, return {} — the rest of the CLI handles defaults.

    Why the swallow: an empty/malformed stdin is the OPERATOR running the
    CLI by hand to test it, not the harness invoking it. We don't want to
    error in either case."""
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        # Malformed — log on stderr but don't raise. The hook still runs.
        print(
            "stop-verify: warning — stdin was not valid JSON; continuing with defaults.",
            file=sys.stderr,
        )
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_repo(args_repo: str | None, hook_input: dict) -> Path:
    """Repo resolution order:
      1. --repo CLI flag (operator intent)
      2. CLAUDE_PROJECT_DIR env var (CC sets this when a project is loaded)
      3. hook_input["cwd"] (CC also passes the worker's CWD in the JSON)
      4. os.getcwd() (fallback)
    """
    if args_repo:
        return Path(args_repo).expanduser()
    env_cpd = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_cpd:
        return Path(env_cpd).expanduser()
    input_cwd = hook_input.get("cwd")
    if isinstance(input_cwd, str) and input_cwd:
        return Path(input_cwd).expanduser()
    return Path.cwd()


def _emit_decision(verdict: Verdict, *, force_json: bool) -> None:
    """Write the CC-compatible decision payload to stdout.

    BLOCK -> always emit JSON {decision:"block", reason:<text>}.
    ALLOW -> by default emit nothing (CC interprets silence as no decision,
             session terminates normally). With --json-out we emit
             {decision:"approve"} so harnesses that grep for a payload see
             one. This matches multi-llm-plugin-cc's actual behavior:
             they `logNote` to stderr on allow, emit JSON only on block."""
    if not verdict.allow:
        payload = {"decision": "block", "reason": verdict.reason}
        sys.stdout.write(json.dumps(payload) + "\n")
        return
    if force_json:
        payload = {"decision": "approve", "reason": verdict.reason}
        sys.stdout.write(json.dumps(payload) + "\n")


def _explain(verdict: Verdict) -> None:
    """Print a human-readable summary to stderr. Stderr (not stdout!) because
    CC reads stdout for the decision JSON; mixing them would corrupt the
    contract."""
    label = "ALLOW" if verdict.allow else "BLOCK"
    print(f"stop-verify: {label}", file=sys.stderr)
    if verdict.counts:
        for kind, n in sorted(verdict.counts.items()):
            print(f"  {kind}: {n}", file=sys.stderr)
    if verdict.evidence:
        print("  evidence (newest first):", file=sys.stderr)
        # Sort by freshness so the first lines are the most-recent artifacts.
        # An operator skimming stderr cares about "what fired the gate just now"
        # more than "what stale thing exists in the repo".
        for hit in sorted(verdict.evidence, key=lambda h: h.mtime_age_sec)[:8]:
            age_min = hit.mtime_age_sec / 60
            print(
                f"    [{hit.kind}] {hit.path} ({age_min:.1f}min old) — {hit.detail}",
                file=sys.stderr,
            )
    if verdict.reason and not verdict.allow:
        # On BLOCK, the reason itself is multi-line — print it after the
        # evidence so the operator sees the artifacts THEN the verdict.
        print("", file=sys.stderr)
        print(verdict.reason, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Claude Code Stop-hook: gate session termination on EVID/WT_CLEAN/e2e_verified evidence."
    )
    p.add_argument("--repo", help="Repo root to scan (default: CC's project dir, then CWD).")
    p.add_argument(
        "--window-min",
        type=int,
        default=30,
        help="Evidence freshness window in minutes (default 30; bounds 1..1440).",
    )
    p.add_argument(
        "--strict-progress",
        action="store_true",
        help="Require BOTH EVID=true AND WT_CLEAN=true in a ledger file modified in window.",
    )
    p.add_argument(
        "--min-kinds",
        type=int,
        default=1,
        help="Minimum distinct evidence kinds required (default 1).",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="Print human-readable verdict to stderr (for ad-hoc debugging).",
    )
    p.add_argument(
        "--json-out",
        action="store_true",
        help="Emit decision JSON even on ALLOW (default: silent on allow).",
    )
    args = p.parse_args(argv)

    try:
        hook_input = _read_hook_input()

        # Kill switch is checked FIRST — operators expect a disable env
        # to short-circuit the whole hook regardless of any other config error
        # (e.g. a stale --repo path baked into hooks.json from a previous repo
        # layout). If we waited until evaluate() this short-circuit would be
        # suppressed by a bad-repo warning, defeating the escape hatch.
        #
        # Two env vars are honored:
        #   STOP_VERIFY_DISABLED       — legacy name (kept for back-compat)
        #   FLEET_DISABLE_STOP_VERIFY  — Substrate-wide convention. See
        #                                scripts/lib/substrate_disable.py.
        # Setting either to 1/true/yes/on (case-insensitive) flips the gate
        # to an unconditional ALLOW with a decision-log entry. Both are
        # tested by the substrate-disable suite.
        from lib.substrate_disable import stop_verify_legacy_disabled

        if stop_verify_legacy_disabled():
            _emit_decision(
                Verdict(allow=True, reason="stop-verify disabled"),
                force_json=args.json_out,
            )
            return 0

        repo = _resolve_repo(args.repo, hook_input)
        if not repo.is_dir():
            # An ALLOW with a warning is the right call here — a bad --repo
            # is an operator config error, not a builder discipline failure,
            # and we already said the hook never traps a session.
            print(
                f"stop-verify: warning — repo not a directory: {repo}; allowing session end.",
                file=sys.stderr,
            )
            _emit_decision(Verdict(allow=True, reason="repo not found"), force_json=args.json_out)
            return 0

        cfg = StopVerifyConfig(
            window_sec=max(1, args.window_min) * 60,
            repo_root=repo,
            require_progress_flag=args.strict_progress,
            min_evidence_kinds=max(1, args.min_kinds),
        )
        verdict = evaluate(cfg)

        if args.explain:
            _explain(verdict)

        _emit_decision(verdict, force_json=args.json_out)
        return 0

    except Exception as exc:  # pragma: no cover - belt-and-braces fail-open
        # The hook MUST NOT trap a worker mid-session on internal error.
        # We allow + warn. A loud stderr line is the operator's signal to
        # investigate; the worker keeps moving.
        print(
            f"stop-verify: internal error ({type(exc).__name__}: {exc}); allowing session end.",
            file=sys.stderr,
        )
        _emit_decision(
            Verdict(allow=True, reason=f"internal error: {exc}"), force_json=args.json_out
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
