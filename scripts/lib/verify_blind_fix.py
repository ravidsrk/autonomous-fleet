"""Library for Layer 3 (blind-fix) verification.

Mechanical guard for the anti-anchoring protocol defined in
`skills/autonomous-fleet-core/references/blind-fix.md`. Kept jsonschema-free
(matches verify_findings.py convention) so the validation venv stays minimal.

Layered like verify_findings:
- `verify_blind_fix_doc(run_dir, findings_doc)` — primary entrypoint, returns
  a summary dict suitable for `--summary-out` consumers.
- Small helpers for each invariant so tests can target individual failure
  modes.

See `references/blind-fix.md` for the spec and `tests/test_verify_blind_fix.py`
for the failure-mode coverage.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Stub patterns that count as "the reviewer didn't really do the blind fix."
_STUB_PATTERNS = (
    re.compile(r"^\s*todo\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*n/?a\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*see\s+pr\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*tbd\s*$", re.IGNORECASE | re.MULTILINE),
)

# Heuristic: a blind-fix file that contains a unified diff marker has almost
# certainly been written AFTER the reviewer opened the candidate patch.
_DIFF_MARKERS = (
    re.compile(r"^diff --git ", re.MULTILINE),
    re.compile(r"^\+\+\+ b/", re.MULTILINE),
    re.compile(r"^--- a/", re.MULTILINE),
)

# A point-of-creation statement is file:[function:]line shaped. We accept a
# range of formats so reviewers aren't forced into one style.
_POINT_OF_CREATION = re.compile(
    r"""
    (?P<file>[A-Za-z0-9_./\-]+
        \.(?:py|js|ts|tsx|jsx|rb|go|rs|java|kt|cpp|c|h|hpp|cs|md|yaml|yml|json|sh|bash))
    (?:
        :\s*(?P<symbol>[A-Za-z_][A-Za-z0-9_.]*)
    )?
    \s*[:#]\s*L?(?P<line>\d+)
    """,
    re.VERBOSE,
)

_CONFIDENCE = re.compile(
    r"confidence[^0-9]{0,20}(?P<n>\d{1,3})\s*(?:/\s*100|%)?",
    re.IGNORECASE,
)

# Strip front-matter and headings before measuring content length.
_HEADING = re.compile(r"^#{1,6}\s.*$", re.MULTILINE)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


@dataclass
class BlindFixFinding:
    """Per-finding verifier result."""

    finding_id: str
    blind_fix_path: Path | None
    ok: bool
    reasons: list[str] = field(default_factory=list)
    blind_fix_mtime: float | None = None
    findings_mtime: float | None = None


def _normalize(text: str) -> str:
    """Strip front-matter + headings so length/stub checks measure content."""
    text = _FRONTMATTER.sub("", text)
    text = _HEADING.sub("", text)
    return text.strip()


def _has_point_of_creation(text: str) -> bool:
    return _POINT_OF_CREATION.search(text) is not None


def _has_confidence(text: str) -> int | None:
    match = _CONFIDENCE.search(text)
    if match is None:
        return None
    try:
        raw = match.group("n")
    except IndexError:
        # Defensive: pattern was monkey-patched / shadowed without the named
        # group. Treat as no confidence found.
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if 0 <= value <= 100:
        return value
    return None


def _has_diff_marker(text: str) -> bool:
    return any(pattern.search(text) for pattern in _DIFF_MARKERS)


def _has_stub(text: str) -> bool:
    return any(pattern.search(text) for pattern in _STUB_PATTERNS)


def _candidate_paths(run_dir: Path, finding_id: str, reviewer: str | None) -> list[Path]:
    """Canonical + multi-reviewer locations for the blind-fix file."""
    paths = [run_dir / f"reviewer-blind-fix-{finding_id}.md"]
    if reviewer:
        paths.append(run_dir / reviewer / f"reviewer-blind-fix-{finding_id}.md")
    return paths


def _resolve_explicit(run_dir: Path, declared: str) -> Path | None:
    """Resolve a finding's declared blind_fix_chain.path safely inside run_dir."""
    if not declared:
        return None
    # Path containment: reject absolute paths and parent escapes (matches
    # verify_findings hardening from PR 38).
    if os.path.isabs(declared):
        return None
    candidate = (run_dir / declared).resolve()
    try:
        run_dir_resolved = run_dir.resolve()
    except OSError:
        return None
    try:
        candidate.relative_to(run_dir_resolved)
    except ValueError:
        return None
    return candidate


def _check_file(path: Path, findings_mtime: float | None) -> tuple[bool, list[str], float | None]:
    """Run all per-file invariants. Returns (ok, reasons, mtime)."""
    reasons: list[str] = []
    if not path.is_file():
        return False, [f"missing: {path}"], None
    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        return False, [f"stat failed: {exc}"], None

    if findings_mtime is not None and mtime > findings_mtime:
        reasons.append(
            f"mtime({path.name})={mtime:.0f} > findings.mtime={findings_mtime:.0f} "
            "(blind-fix must precede findings)"
        )

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return False, reasons + [f"read failed: {exc}"], mtime

    body = _normalize(text)
    if len(body) < 80:
        reasons.append(f"content too short ({len(body)} chars; stub?)")
    if _has_stub(body):
        reasons.append("matches stub pattern (TODO/N/A/see PR/TBD)")
    if _has_diff_marker(text):
        reasons.append("contains diff marker (---/+++/diff --git) — likely written AFTER candidate patch")
    if not _has_point_of_creation(body):
        reasons.append("missing point-of-creation (file:[symbol]:line)")
    if _has_confidence(body) is None:
        reasons.append("missing pre-commit confidence (0–100)")

    return not reasons, reasons, mtime


def verify_blind_fix_doc(
    findings_doc: dict[str, Any],
    *,
    run_dir: Path,
    findings_path: Path | None = None,
) -> dict[str, Any]:
    """Verify Layer 3 (blind-fix) invariants for a findings document.

    Args:
        findings_doc: parsed p0-review-findings.json (already schema-validated).
        run_dir: the run-archive directory (`.fleet/runs/<run_id>/`).
        findings_path: optional path to the findings doc, used to read its
            mtime. If None, mtime ordering is skipped (test setups can pass
            None to focus on content checks).

    Returns:
        Summary dict with `findings`, `verified_blind_fix`, `unverified_blind_fix`,
        and per-finding results.
    """
    run_dir = Path(run_dir)
    findings_mtime: float | None = None
    if findings_path is not None:
        try:
            findings_mtime = findings_path.stat().st_mtime
        except OSError:
            # Findings doc's mtime is unreadable — skip the ordering check.
            # Content checks on each blind-fix file still run.
            findings_mtime = None

    reviewer_block = findings_doc.get("reviewer") or {}
    reviewer_slug: str | None = None
    if isinstance(reviewer_block, dict):
        raw_role = reviewer_block.get("role") or reviewer_block.get("model")
        if isinstance(raw_role, str) and raw_role.strip():
            reviewer_slug = raw_role.strip()

    results: list[BlindFixFinding] = []
    raw_findings = findings_doc.get("findings") or []
    skipped_non_dict = 0
    for finding in raw_findings:
        if not isinstance(finding, dict):
            skipped_non_dict += 1
            continue
        finding_id = str(finding.get("id") or "").strip()
        if not finding_id:
            results.append(
                BlindFixFinding(
                    finding_id="<missing>",
                    blind_fix_path=None,
                    ok=False,
                    reasons=["finding missing id"],
                )
            )
            continue

        explicit: Path | None = None
        chain = finding.get("blind_fix_chain")
        if isinstance(chain, dict):
            declared = chain.get("path")
            if isinstance(declared, str) and declared.strip():
                resolved = _resolve_explicit(run_dir, declared.strip())
                if resolved is None:
                    results.append(
                        BlindFixFinding(
                            finding_id=finding_id,
                            blind_fix_path=None,
                            ok=False,
                            reasons=[f"blind_fix_chain.path escapes run_dir or is absolute: {declared!r}"],
                            findings_mtime=findings_mtime,
                        )
                    )
                    continue
                explicit = resolved

        candidates = [explicit] if explicit is not None else _candidate_paths(
            run_dir, finding_id, reviewer_slug
        )

        chosen: Path | None = None
        for candidate in candidates:
            if candidate is None:
                continue
            if candidate.is_file():
                chosen = candidate
                break

        if chosen is None:
            results.append(
                BlindFixFinding(
                    finding_id=finding_id,
                    blind_fix_path=None,
                    ok=False,
                    reasons=[
                        "no blind-fix file at expected locations: "
                        + ", ".join(
                            str(p.relative_to(run_dir)) if p.is_absolute() and run_dir in p.parents else str(p)
                            for p in candidates
                            if p is not None
                        )
                    ],
                    findings_mtime=findings_mtime,
                )
            )
            continue

        ok, reasons, mtime = _check_file(chosen, findings_mtime)
        results.append(
            BlindFixFinding(
                finding_id=finding_id,
                blind_fix_path=chosen,
                ok=ok,
                reasons=reasons,
                blind_fix_mtime=mtime,
                findings_mtime=findings_mtime,
            )
        )

    verified = sum(1 for r in results if r.ok)
    return {
        "findings": len(results),
        "verified_blind_fix": verified,
        "unverified_blind_fix": len(results) - verified,
        "skipped_non_dict": skipped_non_dict,
        "results": [
            {
                "finding_id": r.finding_id,
                "blind_fix_path": str(r.blind_fix_path) if r.blind_fix_path else None,
                "ok": r.ok,
                "reasons": list(r.reasons),
                "blind_fix_mtime": r.blind_fix_mtime,
                "findings_mtime": r.findings_mtime,
            }
            for r in results
        ],
    }
