"""Verify reviewer findings by grep-checking quoted_line against cited files.

Lineage: GodModeSkill work-converge.py lines ~234-275. The orchestrator runs a
whitespace-tolerant search for each finding's evidence.quoted_line in the cited
evidence.file_path. Findings whose quote can't be located are marked verified=false
and reported in fleet-outcome.metrics.unverified_findings — likely hallucination
from over-eager review.

The schema authority is
`skills/autonomous-fleet-core/assets/fleet-review-findings.schema.json`. Schema
shape validation lives in `validate_findings_doc`; per-finding source verification
lives in `verify_findings_doc`. They are separate so a malformed doc still produces
a useful structural error before we try to grep the filesystem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Cap source-file reads so a hostile or pathological repo can't OOM the verifier
# when a finding cites a multi-GB file (or a symlink to one).
MIN_QUOTE_NORM_LEN = 12
LINE_ANCHOR_SLACK = 2
MAX_SOURCE_BYTES = 8_000_000

# Schema fields the verifier touches. Full schema is the JSON Schema file; this
# duplicates only what the verifier needs to function without pulling jsonschema
# into runtime dependencies. Keep in sync with fleet-review-findings.schema.json.
_REQUIRED_TOP = ("schema_version", "mission", "review_id", "findings", "verdict")
_REQUIRED_FINDING = (
    "id",
    "severity",
    "category",
    "claim",
    "evidence",
    "fix_alternatives",
    "confidence",
    "fix_strategy",
)
_REQUIRED_EVIDENCE = ("file_path", "quoted_line")
_VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low"})
_VALID_CATEGORIES = frozenset({
    "bug", "security", "architecture", "performance",
    "style", "test", "root_cause_depth", "other",
})
_VALID_VERDICTS = frozenset({"approve", "request_changes", "partial"})
_VALID_STRATEGIES = frozenset({"auto", "ask"})
_VALID_EFFORTS = frozenset({"minimal", "moderate", "large"})
# Recognised id pattern: alpha prefix, dash, digits. Matches schema.
_ID_RE = re.compile(r"^[A-Z]+-[0-9]+$")
# Recognised fix-alternative label pattern: single uppercase letter.
_LABEL_RE = re.compile(r"^[A-Z]$")


def load_findings_doc(path: Path) -> dict[str, Any]:
    """Load a findings document from disk. Accepts .json only.

    The schema is JSON. We intentionally do NOT accept YAML here to keep the
    artifact format stable across hosts and to make grep/diff over historical
    archives predictable.
    """
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})") from exc


def validate_findings_doc(doc: dict[str, Any], label: str = "findings-doc") -> list[str]:
    """Structural validation. Returns a list of error strings (empty if clean).

    This is a hand-rolled subset of the JSON Schema — enough to catch the
    common reviewer-emitted shape errors before we hit the filesystem. Full
    JSON-Schema enforcement is a downstream `jsonschema` call if the operator
    installs the optional dependency; this function is the always-available
    floor.
    """
    errors: list[str] = []

    if not isinstance(doc, dict):
        return [f"{label}: top-level must be an object, got {type(doc).__name__}"]

    for key in _REQUIRED_TOP:
        if key not in doc:
            errors.append(f"{label}: missing required field '{key}'")

    if doc.get("schema_version") not in (None, "1.0"):
        errors.append(
            f"{label}: schema_version must be '1.0', got {doc.get('schema_version')!r}"
        )

    if "mission" in doc and not (isinstance(doc["mission"], str) and doc["mission"].strip()):
        errors.append(f"{label}: mission must be a non-empty string")

    if "review_id" in doc:
        rid = doc["review_id"]
        if not isinstance(rid, str) or not re.match(r"^[a-zA-Z0-9._/-]+$", rid):
            errors.append(
                f"{label}: review_id must match ^[a-zA-Z0-9._/-]+$, got {rid!r}"
            )

    findings = doc.get("findings")
    if findings is None:
        # Already reported by required-field check above
        pass
    elif not isinstance(findings, list):
        errors.append(f"{label}: findings must be a list, got {type(findings).__name__}")
    else:
        seen_ids: set[str] = set()
        for idx, finding in enumerate(findings):
            errors.extend(_validate_finding(finding, idx, seen_ids, label))

    verdict = doc.get("verdict")
    if verdict is not None:
        if not isinstance(verdict, dict):
            errors.append(f"{label}: verdict must be an object")
        else:
            decision = verdict.get("decision")
            if decision not in _VALID_VERDICTS:
                errors.append(
                    f"{label}: verdict.decision must be one of "
                    f"{sorted(_VALID_VERDICTS)}, got {decision!r}"
                )
            reasoning = verdict.get("reasoning")
            if not isinstance(reasoning, str) or not reasoning.strip():
                errors.append(f"{label}: verdict.reasoning must be a non-empty string")

    return errors


def _validate_finding(
    finding: Any, idx: int, seen_ids: set[str], label: str
) -> list[str]:
    errors: list[str] = []
    where = f"{label}: findings[{idx}]"

    if not isinstance(finding, dict):
        return [f"{where}: must be an object, got {type(finding).__name__}"]

    for key in _REQUIRED_FINDING:
        if key not in finding:
            errors.append(f"{where}: missing required field '{key}'")

    fid = finding.get("id")
    if isinstance(fid, str):
        if not _ID_RE.match(fid):
            errors.append(f"{where}: id must match ^[A-Z]+-[0-9]+$, got {fid!r}")
        elif fid in seen_ids:
            errors.append(f"{where}: duplicate id {fid!r}")
        else:
            seen_ids.add(fid)

    sev = finding.get("severity")
    if sev not in _VALID_SEVERITIES:
        errors.append(
            f"{where}: severity must be one of {sorted(_VALID_SEVERITIES)}, got {sev!r}"
        )

    cat = finding.get("category")
    if cat not in _VALID_CATEGORIES:
        errors.append(
            f"{where}: category must be one of {sorted(_VALID_CATEGORIES)}, got {cat!r}"
        )

    if "claim" in finding and not (isinstance(finding["claim"], str) and finding["claim"].strip()):
        errors.append(f"{where}: claim must be a non-empty string")

    evidence = finding.get("evidence")
    if evidence is None:
        pass  # already reported
    elif not isinstance(evidence, dict):
        errors.append(f"{where}: evidence must be an object")
    else:
        for key in _REQUIRED_EVIDENCE:
            if key not in evidence:
                errors.append(f"{where}: evidence missing '{key}'")
        if "file_path" in evidence and not (
            isinstance(evidence["file_path"], str) and evidence["file_path"].strip()
        ):
            errors.append(f"{where}: evidence.file_path must be a non-empty string")
        if "quoted_line" in evidence and not (
            isinstance(evidence["quoted_line"], str) and evidence["quoted_line"].strip()
        ):
            errors.append(f"{where}: evidence.quoted_line must be a non-empty string")
        if "line_number" in evidence:
            ln = evidence["line_number"]
            if type(ln) is not int or ln < 1:
                errors.append(
                    f"{where}: evidence.line_number must be a positive int, got {ln!r}"
                )

    alts = finding.get("fix_alternatives")
    if alts is None:
        pass
    elif not isinstance(alts, list) or not alts:
        errors.append(f"{where}: fix_alternatives must be a non-empty list")
    elif len(alts) > 4:
        errors.append(f"{where}: fix_alternatives must have at most 4 entries, got {len(alts)}")
    else:
        labels_seen: set[str] = set()
        recommended_count = 0
        for j, alt in enumerate(alts):
            if not isinstance(alt, dict):
                errors.append(f"{where}: fix_alternatives[{j}] must be an object")
                continue
            for key in ("label", "description", "effort"):
                if key not in alt:
                    errors.append(f"{where}: fix_alternatives[{j}] missing '{key}'")
            lab = alt.get("label")
            if isinstance(lab, str):
                if not _LABEL_RE.match(lab):
                    errors.append(
                        f"{where}: fix_alternatives[{j}].label must match ^[A-Z]$, got {lab!r}"
                    )
                elif lab in labels_seen:
                    errors.append(
                        f"{where}: fix_alternatives[{j}].label duplicate {lab!r}"
                    )
                else:
                    labels_seen.add(lab)
            eff = alt.get("effort")
            if eff not in _VALID_EFFORTS:
                errors.append(
                    f"{where}: fix_alternatives[{j}].effort must be one of "
                    f"{sorted(_VALID_EFFORTS)}, got {eff!r}"
                )
            if "description" in alt and not (
                isinstance(alt["description"], str) and alt["description"].strip()
            ):
                errors.append(
                    f"{where}: fix_alternatives[{j}].description must be non-empty"
                )
            if alt.get("recommended") is True:
                recommended_count += 1
        if recommended_count > 1:
            errors.append(
                f"{where}: fix_alternatives has {recommended_count} recommended=true; "
                "schema permits at most one"
            )

    conf = finding.get("confidence")
    if conf is not None:
        # bool is a subclass of int in Python; reject explicitly to keep the
        # confidence axis numeric.
        if type(conf) is not int or conf < 0 or conf > 100:
            errors.append(
                f"{where}: confidence must be int 0-100, got {conf!r}"
            )

    strat = finding.get("fix_strategy")
    if strat is not None and strat not in _VALID_STRATEGIES:
        errors.append(
            f"{where}: fix_strategy must be one of {sorted(_VALID_STRATEGIES)}, got {strat!r}"
        )

    if cat == "root_cause_depth":
        cascade = finding.get("cascade_impact")
        if not (isinstance(cascade, str) and cascade.strip()):
            errors.append(
                f"{where}: category=root_cause_depth requires non-empty cascade_impact"
            )

    return errors


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces. Matches GodModeSkill behavior."""
    return " ".join(text.split())


def verify_finding_against_source(
    finding: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Verify ONE finding's quoted_line is present in its cited file.

    Returns the finding dict, mutated in place with `verified: bool` and
    optionally `verify_reason: str`. The matching is whitespace-tolerant —
    runs of whitespace in both the quote and the source are collapsed to a
    single space before substring comparison. This handles tab-vs-space and
    line-wrap differences without losing the integrity of the check.

    Encoding errors are not fatal: we read with errors='replace' so a binary
    file under the cited path produces a clean 'quote not found' rather than a
    crash. Findings that cite genuinely unreadable paths are flagged as
    verified=false with a verify_reason.
    """
    evidence = finding.get("evidence") or {}
    quoted = (evidence.get("quoted_line") or "").strip()
    file_path = (evidence.get("file_path") or "").strip()

    if not quoted or not file_path:
        finding["verified"] = False
        finding["verify_reason"] = "evidence.file_path or quoted_line missing/empty"
        return finding

    # Containment: a finding is reviewer-produced (suspect) data. Constrain the
    # cited path to the repo so a malicious/hallucinated finding can't turn the
    # verifier into a read-anything primitive via an absolute path or ../ traversal.
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        target = candidate.resolve()
        target.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        finding["verified"] = False
        finding["verify_reason"] = "file_path escapes repo root"
        return finding

    if not target.exists():
        finding["verified"] = False
        finding["verify_reason"] = "file not found"
        return finding

    if not target.is_file():
        finding["verified"] = False
        finding["verify_reason"] = "path is not a regular file"
        return finding

    # Cap the read so a giant file can't OOM the verifier.
    try:
        with target.open("rb") as fh:
            raw = fh.read(MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        finding["verified"] = False
        finding["verify_reason"] = f"unreadable: {exc}"
        return finding
    if len(raw) > MAX_SOURCE_BYTES:
        finding["verified"] = False
        finding["verify_reason"] = f"file exceeds {MAX_SOURCE_BYTES}-byte read cap"
        return finding
    source = raw.decode("utf-8", errors="replace")

    quoted_norm = _normalize_whitespace(quoted)

    # Issue #98: specificity must come from the anchor OR the length. A
    # line-anchored quote may be short (the line number pins it); an
    # UN-anchored quote needs MIN_QUOTE_NORM_LEN normalized chars, because a
    # whitespace-tolerant whole-file substring match let "return" "verify"
    # against almost any file.
    line_number = evidence.get("line_number")
    if isinstance(line_number, int) and line_number >= 1:
        # Line-anchored: the quote must appear within ±LINE_ANCHOR_SLACK
        # lines of the cited line (small drift tolerated, global match not).
        lines = source.splitlines()
        lo = max(0, line_number - 1 - LINE_ANCHOR_SLACK)
        hi = min(len(lines), line_number + LINE_ANCHOR_SLACK)
        window_norm = _normalize_whitespace("\n".join(lines[lo:hi]))
        if quoted_norm in window_norm:
            finding["verified"] = True
            finding.pop("verify_reason", None)
        else:
            finding["verified"] = False
            finding["verify_reason"] = (
                f"quoted_line not found within ±{LINE_ANCHOR_SLACK} lines of "
                f"line_number {line_number}"
            )
        return finding

    if len(quoted_norm) < MIN_QUOTE_NORM_LEN:
        finding["verified"] = False
        finding["verify_reason"] = (
            f"quoted_line too short to verify un-anchored "
            f"(<{MIN_QUOTE_NORM_LEN} normalized chars; add evidence.line_number)"
        )
        return finding

    source_norm = _normalize_whitespace(source)
    if quoted_norm in source_norm:
        finding["verified"] = True
        # Remove any stale verify_reason from a prior verify pass.
        finding.pop("verify_reason", None)
    else:
        finding["verified"] = False
        finding["verify_reason"] = "quoted_line not found in cited file"

    return finding


def verify_findings_doc(
    doc: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    """Verify every finding in the doc against the source tree under repo_root.

    Mutates each finding in place with `verified` (and `verify_reason` on
    failure). Returns a summary dict with verified/unverified counts and the
    list of unverified finding IDs — exactly the shape we'll surface in
    fleet-outcome.metrics.
    """
    findings = doc.get("findings") or []
    if not isinstance(findings, list):
        return {
            "total_findings": 0,
            "verified_findings": 0,
            "unverified_findings": 0,
            "unverified_ids": [],
            "auto_applicable_findings": 0,
            "human_gated_findings": 0,
        }

    auto_applicable = 0
    human_gated = 0
    unverified_ids: list[str] = []
    verified_count = 0
    skipped = 0

    for finding in findings:
        if not isinstance(finding, dict):
            skipped += 1
            continue
        verify_finding_against_source(finding, repo_root)
        if finding.get("verified") is True:
            verified_count += 1
        else:
            unverified_ids.append(str(finding.get("id", "?")))
        # Count auto-applicable ONLY among verified findings — an unverified
        # finding never qualifies for auto-apply regardless of its declared
        # fix_strategy. This is what makes the schema *enforce* the discipline,
        # not just describe it.
        if (
            finding.get("verified") is True
            and finding.get("fix_strategy") == "auto"
            and isinstance(finding.get("confidence"), int)
            and finding["confidence"] >= 80
        ):
            auto_applicable += 1
        elif finding.get("verified") is True and finding.get("fix_strategy") == "ask":
            human_gated += 1

    return {
        # total = verified + unverified + skipped_non_dict (the counts reconcile).
        "total_findings": len(findings),
        "verified_findings": verified_count,
        "unverified_findings": len(unverified_ids),
        "unverified_ids": unverified_ids,
        "auto_applicable_findings": auto_applicable,
        "human_gated_findings": human_gated,
        "skipped_non_dict": skipped,
    }
