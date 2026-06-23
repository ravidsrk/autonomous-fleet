"""Evidence detection library for the stop-verify hook gate.

The stop-verify gate is the runtime counterpart of the engine.md disciplines
EVID, WT_CLEAN, and e2e_verified. Today those disciplines are aspirational —
the builder self-attests in the readiness doc. This library, paired with
`scripts/stop_verify.py`, makes them ENFORCEABLE by refusing to let a worker
end its Claude Code session unless verifiable evidence is on disk inside a
freshness window.

This is build-blindness made executable. The exact pattern is borrowed from:
- claude-code-orchestra `.claude/hooks/stop-verify.sh` (mtime-window evidence
  scan against fixtures: pytest_cache, coverage, Playwright PNGs)
- multi-llm-plugin-cc `stop-review-gate-hook.mjs` (the
  ALLOW:/BLOCK: contract — fresh LLM call that returns a verdict line)

Composed for autonomous-fleet's specific disciplines (EVID, WT_CLEAN,
e2e_verified) rather than copied 1:1, because we have a ledger format the
upstream patterns don't have.

The library is intentionally side-effect free: it inspects the filesystem
and returns a verdict object. The CLI translates that into Claude Code's
Stop-hook JSON.

Decision contract: see `Verdict` below. The CLI maps:
  Verdict.allow=True  -> exit 0, no JSON   (session may end)
  Verdict.allow=False -> exit 0, JSON {decision:"block", reason:<text>}
                        (Claude Code refuses to terminate the session)

Lineage cites: /workspace/audit-work/borrowable-patterns-report.md #2.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# Default freshness window: 30 minutes. Matches both upstream patterns
# (claude-code-orchestra hardcoded 30, multi-llm timeout 15min). 30min is
# the longest gap between "evidence ran" and "agent declares done" that the
# fleet's real runs produce in steady state — anything longer is a smell.
DEFAULT_WINDOW_MIN = 30

# Lower bound — we won't accept a window so small that ordinary disk-cache
# updates can't legitimately fall inside it (causes false BLOCKs).
MIN_WINDOW_SEC = 30

# Upper bound — windows wider than 24h defeat the entire point of the gate
# (any artifact from the previous workday "proves" today's run). Cap it.
MAX_WINDOW_SEC = 24 * 60 * 60

# YAML directives lifted into engine.md flags. Detector greps progress docs
# for these literal substrings since the ledger format is markdown, not
# parseable YAML. The flag MUST appear with "=true" (not bare "EVID") so a
# discussion of EVID in prose can't satisfy the gate.
EVID_PATTERN = re.compile(r"\bEVID\s*=\s*true\b", re.IGNORECASE)
WT_CLEAN_PATTERN = re.compile(r"\bWT_CLEAN\s*=\s*true\b", re.IGNORECASE)

# fleet-outcome YAML frontmatter detection. Conservative: we only verify the
# readiness doc EXISTS, was touched in window, and contains the literal
# `e2e_verified: true` line (or status: done with no e2e claim required by
# the mission). The deep YAML validation is the validate_fleet_outcome.py
# job, not the stop-verify hook.
E2E_VERIFIED_PATTERN = re.compile(r"^\s*e2e_verified:\s*true\s*$", re.MULTILINE)
STATUS_DONE_PATTERN = re.compile(r"^\s*status:\s*done\s*$", re.MULTILINE)

# Run-archive verify-summary contract (Commit 1's verify_findings.py
# --summary-out). If the worker emitted a passing summary in window, that's
# the highest-grade EVID: the schema-verified findings audit ran clean.
VERIFY_SUMMARY_REL_PATTERNS = [
    ".fleet/runs/*/p0-verify-summary.json",
    ".fleet/runs/*/p0-skeptic-verify-summary.json",
    ".fleet/runs/*/verify-summary.json",
]

# Test-artifact patterns. Lifted from claude-code-orchestra's hook but
# expanded for Python/Node/Rust/Go because autonomous-fleet adapters touch
# all four. mtime-windowed.
TEST_ARTIFACT_GLOBS = [
    "**/.pytest_cache/v/lastfailed",
    "**/.pytest_cache/v/nodeids",
    "**/coverage/**/*.json",
    "**/coverage.xml",
    "**/htmlcov/index.html",
    "**/test-results/**/*.xml",
    "**/junit*.xml",
    "**/target/test-report*/**",  # Rust cargo-nextest
    "**/test-results.json",  # vitest/jest --reporter=json
]

# Screenshot/E2E patterns — a recent Playwright/Puppeteer PNG is among the
# strongest e2e_verified signals because it proves the app actually rendered.
E2E_ARTIFACT_GLOBS = [
    "**/playwright-report/**/*.html",
    "**/playwright-report/**/*.png",
    "**/test-results/**/*.png",
    "**/screenshots/**/*.png",
    "**/*.spec.ts.png",  # playwright trace screenshots
]


@dataclass
class EvidenceHit:
    """A single piece of evidence the detector found inside the window.

    `kind` is a short categorical label so the CLI can compose a human-readable
    reason string ("blocked: 0 EVID, 0 WT_CLEAN, 0 test runs in last 30min").
    `path` is the on-disk path that satisfied this evidence.
    `mtime_age_sec` is how old the artifact is — used to short-circuit
    duplicate evidence and to drive the BLOCK message ordering (freshest first).
    """

    kind: str
    path: Path
    mtime_age_sec: float
    detail: str = ""


@dataclass
class Verdict:
    """The output of a stop-verify run. CLI translates to CC's Stop-hook JSON.

    `allow=True` -> session may terminate. evidence list documents WHY.
    `allow=False` -> session must continue. `reason` is what the agent sees.

    `evidence` is always populated so an `--explain` invocation can show what
    DID match even when the verdict is BLOCK (some evidence may have been
    found but the threshold wasn't met).
    """

    allow: bool
    reason: str = ""
    evidence: list[EvidenceHit] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class StopVerifyConfig:
    """Knobs the operator can flip per install. All optional; defaults are
    the conservative "strict mode" baseline.

    `window_sec` — how far back we look. Default 30min. See bounds above.
    `repo_root` — where to scan. Resolved to absolute path.
    `progress_glob` — where ledger files live. Project convention is
        docs/*-progress.md but missions like landing-page-convergence use
        docs/<slug>-progress.md too. Glob covers both.
    `readiness_glob` — where readiness docs live. Same convention as the
        validator's collect_readiness_paths.
    `runs_dir` — Commit 4 run-archive root (defaults to .fleet/runs).
    `require_progress_flag` — when True, BOTH EVID=true AND WT_CLEAN=true must
        appear in some progress doc touched in window (in addition to test
        evidence). The default is conservative-but-not-paranoid: progress
        flags OR a passing verify-summary count.
    `min_evidence_kinds` — how many DISTINCT evidence kinds must match. Default
        1 (any one is enough; matches upstream patterns). Operators can raise
        this to 2 or 3 for paranoid modes.
    `disabled` — kill switch via env var STOP_VERIFY_DISABLED=1 or config.
        Returns allow=True with reason="disabled" so the hook is inert.
    """

    window_sec: int = DEFAULT_WINDOW_MIN * 60
    repo_root: Path = Path.cwd()
    progress_glob: str = "docs/*-progress.md"
    readiness_glob: str = "docs/*-readiness.md"
    runs_dir: str = ".fleet/runs"
    require_progress_flag: bool = False
    min_evidence_kinds: int = 1
    disabled: bool = False

    def normalised(self) -> "StopVerifyConfig":
        """Return a copy with window/repo_root clamped + resolved. Callers
        get a single trusted shape regardless of where the config came from
        (CLI args, env vars, config file)."""
        window = max(MIN_WINDOW_SEC, min(self.window_sec, MAX_WINDOW_SEC))
        return StopVerifyConfig(
            window_sec=window,
            repo_root=self.repo_root.resolve(),
            progress_glob=self.progress_glob,
            readiness_glob=self.readiness_glob,
            runs_dir=self.runs_dir,
            require_progress_flag=self.require_progress_flag,
            min_evidence_kinds=max(1, self.min_evidence_kinds),
            disabled=self.disabled,
        )


# ───────────────────────────────────────────────────────────────────────
# Detectors. Each returns a list of EvidenceHit. mtime-windowed.
# ───────────────────────────────────────────────────────────────────────


def _iter_glob_safe(root: Path, pattern: str):
    """Path.glob can raise PermissionError or follow symlinks into infinite
    loops on weird trees. Wrap so the hook never crashes on a hostile FS
    layout — a crash here is a worse failure than a missed evidence hit."""
    try:
        yield from root.glob(pattern)
    except (OSError, ValueError):
        # ValueError covers Path.glob's "Non-relative patterns are unsupported"
        # when an operator types an absolute glob. We swallow and move on
        # because a malformed config should not break the gate.
        return


def _mtime_age(p: Path, now: float) -> float | None:
    try:
        return now - p.stat().st_mtime
    except OSError:
        return None


def detect_progress_flag_evidence(cfg: StopVerifyConfig, now: float) -> list[EvidenceHit]:
    """Grep `docs/*-progress.md` ledger files for `EVID=true` / `WT_CLEAN=true`
    that appeared in a file MODIFIED within the window. The mtime check is
    what makes the flag fresh — stale progress docs from last month's run
    SHOULD NOT count."""
    hits: list[EvidenceHit] = []
    for path in _iter_glob_safe(cfg.repo_root, cfg.progress_glob):
        age = _mtime_age(path, now)
        if age is None or age > cfg.window_sec:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # We count each ledger doc that contains EVID=true as ONE evidence
        # hit. We don't try to count per-row EVIDs — that's the readiness
        # validator's job, not the gate's.
        if EVID_PATTERN.search(text):
            hits.append(
                EvidenceHit(
                    kind="evid_flag",
                    path=path,
                    mtime_age_sec=age,
                    detail="EVID=true in ledger (mtime in window)",
                )
            )
        if WT_CLEAN_PATTERN.search(text):
            hits.append(
                EvidenceHit(
                    kind="wt_clean_flag",
                    path=path,
                    mtime_age_sec=age,
                    detail="WT_CLEAN=true in ledger (mtime in window)",
                )
            )
    return hits


def detect_readiness_evidence(cfg: StopVerifyConfig, now: float) -> list[EvidenceHit]:
    """A readiness doc that was touched in window AND contains either
    `e2e_verified: true` or `status: done` is strong evidence the run actually
    finished. The validator catches structural problems; the gate just needs
    a fresh, signed-off readiness."""
    hits: list[EvidenceHit] = []
    for path in _iter_glob_safe(cfg.repo_root, cfg.readiness_glob):
        age = _mtime_age(path, now)
        if age is None or age > cfg.window_sec:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if E2E_VERIFIED_PATTERN.search(text):
            hits.append(
                EvidenceHit(
                    kind="e2e_verified",
                    path=path,
                    mtime_age_sec=age,
                    detail="e2e_verified: true in readiness frontmatter",
                )
            )
        # status:done is weaker than e2e_verified (the validator may not have
        # finished checking the fleet-outcome block), but a fresh readiness
        # doc with status:done is still meaningful evidence the worker did
        # the T-FINAL write.
        elif STATUS_DONE_PATTERN.search(text):
            hits.append(
                EvidenceHit(
                    kind="status_done",
                    path=path,
                    mtime_age_sec=age,
                    detail="status: done in readiness frontmatter",
                )
            )
    return hits


def detect_verify_summary_evidence(cfg: StopVerifyConfig, now: float) -> list[EvidenceHit]:
    """A Commit-1 verify_findings.py --summary-out artifact in window proves
    the schema-verified review findings audit ran. We additionally inspect
    the JSON to confirm `unverified_findings == 0` — a failing verify is NOT
    evidence the run can stop. (The schema gate already blocks the fix loop
    on unverified > 0; this is belt-and-braces for the stop hook.)"""
    hits: list[EvidenceHit] = []
    for pattern in VERIFY_SUMMARY_REL_PATTERNS:
        for path in _iter_glob_safe(cfg.repo_root, pattern):
            age = _mtime_age(path, now)
            if age is None or age > cfg.window_sec:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict):
                continue
            unverified = payload.get("unverified_findings")
            if isinstance(unverified, int) and unverified == 0:
                hits.append(
                    EvidenceHit(
                        kind="verify_summary",
                        path=path,
                        mtime_age_sec=age,
                        detail=(
                            f"{payload.get('verified_findings', '?')}/"
                            f"{payload.get('total_findings', '?')} findings verified, 0 unverified"
                        ),
                    )
                )
    return hits


def detect_test_artifact_evidence(cfg: StopVerifyConfig, now: float) -> list[EvidenceHit]:
    """Test-runner artifacts (pytest cache, coverage report, jest results,
    junit XML, cargo-nextest reports) touched in window. The upstream
    claude-code-orchestra hook hardcoded a Python-only list; we expand for
    fleet's polyglot adapters but cap the number of hits we report per glob
    to keep the BLOCK reason readable."""
    hits: list[EvidenceHit] = []
    seen_dirs: set[Path] = set()
    for pattern in TEST_ARTIFACT_GLOBS:
        for path in _iter_glob_safe(cfg.repo_root, pattern):
            age = _mtime_age(path, now)
            if age is None or age > cfg.window_sec:
                continue
            # De-duplicate by parent dir so one cache dir of 200 files is
            # ONE evidence hit, not 200.
            if path.parent in seen_dirs:
                continue
            seen_dirs.add(path.parent)
            hits.append(
                EvidenceHit(
                    kind="test_artifact",
                    path=path,
                    mtime_age_sec=age,
                    detail=f"test artifact matched {pattern}",
                )
            )
    return hits


def detect_e2e_artifact_evidence(cfg: StopVerifyConfig, now: float) -> list[EvidenceHit]:
    """Playwright/screenshot evidence. A PNG from a real browser render is
    the strongest single signal of e2e_verified short of a production
    invocation log."""
    hits: list[EvidenceHit] = []
    seen_dirs: set[Path] = set()
    for pattern in E2E_ARTIFACT_GLOBS:
        for path in _iter_glob_safe(cfg.repo_root, pattern):
            age = _mtime_age(path, now)
            if age is None or age > cfg.window_sec:
                continue
            if path.parent in seen_dirs:
                continue
            seen_dirs.add(path.parent)
            hits.append(
                EvidenceHit(
                    kind="e2e_artifact",
                    path=path,
                    mtime_age_sec=age,
                    detail=f"e2e artifact matched {pattern}",
                )
            )
    return hits


# ───────────────────────────────────────────────────────────────────────
# Orchestrator. Composes detectors into a single Verdict.
# ───────────────────────────────────────────────────────────────────────


def _env_disabled() -> bool:
    """Operator escape hatch: STOP_VERIFY_DISABLED=1 turns the gate into a
    no-op. Required for adapter test harnesses that need to drive Claude
    Code sessions without artifact requirements (e.g. the headless campaign
    runner during dry-runs). The env var is checked at the entrypoint, not
    deep in a detector, so the kill switch is easy to audit."""
    # Case-insensitive so operators don't get bitten by STOP_VERIFY_DISABLED=TRUE
    # vs ...=true. The strip() handles trailing newlines from shell-sourced
    # env files.
    return os.environ.get("STOP_VERIFY_DISABLED", "").strip().lower() in {"1", "true", "yes"}


def _format_block_reason(
    cfg: StopVerifyConfig, counts: dict[str, int], evidence: list[EvidenceHit]
) -> str:
    """Render the BLOCK message the agent sees. The contract is: explain
    WHAT was missing, in PLAIN ENGLISH, and tell the agent EXACTLY what to
    do. Upstream patterns confirm: a vague BLOCK message produces a worker
    that retries the same broken approach."""
    minutes = cfg.window_sec // 60
    have = [f"{kind}={n}" for kind, n in sorted(counts.items()) if n > 0]
    have_str = ", ".join(have) if have else "no evidence kinds matched"

    lines = [
        f"stop-verify: BLOCKED — no fleet-outcome-grade evidence in the last {minutes}min.",
        f"  evidence found: {have_str}",
        f"  required: at least {cfg.min_evidence_kinds} distinct kind(s) "
        "from {evid_flag, wt_clean_flag, e2e_verified, status_done, verify_summary, "
        "test_artifact, e2e_artifact}",
        "",
        "To unblock:",
        "  - Run the fix's own EVID reproduction (the exact curl/test/script from the "
        "finding's Evidence block) and set EVID=true in the ledger.",
        "  - Run the test suite end-to-end (pytest / jest / cargo test / go test).",
        "  - Write the readiness doc with `status: done` (and `e2e_verified: true` if the "
        "mission requires it).",
        "  - Or, for verified review missions, run scripts/verify_findings.py --summary-out.",
        "",
        "If this is a no-edit turn (status/diagnostic only), set STOP_VERIFY_DISABLED=1 in "
        "the worker env or remove the Stop hook for that adapter.",
    ]
    return "\n".join(lines)


def evaluate(cfg: StopVerifyConfig | None = None) -> Verdict:
    """The library entry point. Runs every detector, composes a verdict.

    Caller responsibility: pass a config or accept defaults. Library does NOT
    read env vars beyond STOP_VERIFY_DISABLED (the kill switch); everything
    else flows through the config so tests can pin behavior."""
    cfg = (cfg or StopVerifyConfig()).normalised()

    if cfg.disabled or _env_disabled():
        return Verdict(allow=True, reason="stop-verify disabled", counts={"disabled": 1})

    now = time.time()
    all_evidence: list[EvidenceHit] = []
    all_evidence.extend(detect_progress_flag_evidence(cfg, now))
    all_evidence.extend(detect_readiness_evidence(cfg, now))
    all_evidence.extend(detect_verify_summary_evidence(cfg, now))
    all_evidence.extend(detect_test_artifact_evidence(cfg, now))
    all_evidence.extend(detect_e2e_artifact_evidence(cfg, now))

    counts: dict[str, int] = {}
    for e in all_evidence:
        counts[e.kind] = counts.get(e.kind, 0) + 1

    distinct_kinds = sum(1 for v in counts.values() if v > 0)

    # Strict-progress mode: BOTH flags must appear in ledger, ON TOP OF
    # whatever other evidence is present. Designed for operators who want
    # the stronger discipline.
    if cfg.require_progress_flag:
        if counts.get("evid_flag", 0) == 0 or counts.get("wt_clean_flag", 0) == 0:
            return Verdict(
                allow=False,
                reason=_format_block_reason(cfg, counts, all_evidence)
                + "\n  ALSO: strict-progress mode requires both EVID=true AND WT_CLEAN=true "
                "in a ledger file modified in window.",
                evidence=all_evidence,
                counts=counts,
            )

    if distinct_kinds < cfg.min_evidence_kinds:
        return Verdict(
            allow=False,
            reason=_format_block_reason(cfg, counts, all_evidence),
            evidence=all_evidence,
            counts=counts,
        )

    # ALLOW. Reason still populated so --explain can show what cleared the gate.
    kinds_str = ", ".join(sorted(k for k in counts if counts[k] > 0))
    return Verdict(
        allow=True,
        reason=f"stop-verify: ALLOW — evidence kinds matched: {kinds_str}",
        evidence=all_evidence,
        counts=counts,
    )
