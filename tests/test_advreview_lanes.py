"""Structural rails for adversarial-review-and-fix remediation lanes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "adversarial-review-and-fix" / "SKILL.md"


def read_skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def section(text: str, heading: str, next_heading: str | None = None) -> str:
    start = text.index(heading)
    if next_heading is None:
        return text[start:]
    end = text.index(next_heading, start)
    return text[start:end]


def squash(text: str) -> str:
    return " ".join(text.split())


CONTRADICTION_MARKERS = (
    "IGNORE the preceding",
    "IGNORE THE PRECEDING",
    "OVERRIDE",
    "DISREGARD",
    "ignore the above",
)


def assert_no_contradiction_markers(text: str) -> None:
    for marker in CONTRADICTION_MARKERS:
        assert marker not in text


def test_three_lane_remediation_section_has_all_lanes() -> None:
    text = read_skill()
    lanes = section(text, "THREE-LANE REMEDIATION", "ROLE PIPELINE")
    lanes_flat = squash(lanes)

    # Engine reference present — LANE PATTERN lives in the trigger-loaded
    # engine-autonomy.md (engine.md core split, 0.3.0).
    assert "engine-autonomy.md" in lanes
    assert "LANE PATTERN" in lanes
    # Mission-specific ledger flags still recorded per lane.
    assert "Lane A" in lanes
    assert "Lane B" in lanes
    assert "Lane 0" in lanes
    assert "`MERGED=true`" in lanes
    assert "`HUMAN_GATED=true`" in lanes
    assert "`CODE_CLOSED=true, OPS_QUEUED=true`" in lanes
    assert "`DECISIONS.md`" in lanes
    assert "Never auto-merge" in lanes
    assert "`HUMAN_ACTION_REQUIRED:<finding-id>`" in lanes
    assert "`docs/arch-ops-actions.md`" in lanes
    assert "`lane: A|B|0`" in lanes
    assert "auto-merge it without a human gate" not in lanes
    assert "SHOULD execute the human-only action itself" not in lanes
    assert "without waiting" not in lanes
    assert_no_contradiction_markers(lanes)


def test_evid_flag_is_ledger_and_fix_loop_gate() -> None:
    text = read_skill()
    ledger = section(text, "LEDGER", "TASK STRUCTURE")
    ledger_flat = squash(ledger)
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")

    # Engine reference for EVID definition (relocated to engine-autonomy.md
    # by the engine.md core split, 0.3.0).
    assert "engine-autonomy.md" in ledger
    assert "FROZEN-ARTIFACT CLOSE TEST" in ledger
    # Mission-specific ledger flags still present.
    assert "`CODED EVID PR_OPEN REVIEWED MERGED ACCEPT`" in ledger
    # Mission-specific EVID repro example carried in the ledger section.
    assert "EVID=true" in ledger_flat
    assert "only when it no longer reproduces" in ledger_flat
    # The fix-loop section still wires EVID as the gate before OPEN_PR.
    assert "Before OPEN_PR" in tasks
    assert "EXACT reproduction from the" in tasks
    assert "finding's Evidence block" in tasks
    assert "sets `EVID`" in tasks
    assert "Reviewer independently" in tasks
    assert "re-runs the same Evidence reproduction" in tasks
    assert "sets `EVID` only when it no longer reproduces" in squash(tasks)
    assert "set `EVID` immediately without re-running" not in tasks
    assert "even when the finding still reproduces" not in tasks
    assert_no_contradiction_markers(ledger)
    assert_no_contradiction_markers(tasks)


def test_root_cause_clusters_have_foundation_independent_schema() -> None:
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    defaults = section(text, "DECISION DEFAULTS", None)

    assert "root-cause CLUSTERS" in tasks
    assert "`FOUNDATION|INDEPENDENT`" in tasks
    assert "`touches:` file-list" in tasks
    assert "`CLOSES=[ids]`" in tasks
    assert "Finalize root-cause CLUSTERS" in tasks
    assert "FOUNDATION cluster's root cause once" in tasks
    assert "dependent findings" in tasks
    assert "inherit" in tasks
    assert "Fixing a FOUNDATION cluster's root cause once closes its dependent findings" in defaults
    assert "`CLOSED via PR#n`" in defaults
    assert (
        "Fixing a FOUNDATION cluster's root cause once closes its dependent findings only when "
        "the shared PR satisfies every dependent finding's Evidence and acceptance gates"
    ) in squash(defaults)
    assert "auto-closes ALL dependents unconditionally" not in defaults
    assert "skip each dependent" not in defaults
    assert_no_contradiction_markers(tasks)
    assert_no_contradiction_markers(defaults)


def test_decision_defaults_exercise_fixes_like_production() -> None:
    text = read_skill()
    defaults = section(text, "DECISION DEFAULTS", None)

    assert "Fixes must be exercised the way production runs them, not just CI-green" in defaults
    assert "`docs/secure-ship-e2e.md`" in defaults
    assert "same invocation, wiring, and result path production uses" in defaults
    assert (
        "validation is not terminal evidence unless it traverses the same invocation, wiring, "
        "and result path production uses."
    ) in squash(defaults)
    assert "CI-green IS sufficient terminal evidence" not in defaults
    assert "skip the production invocation" not in defaults
    assert_no_contradiction_markers(defaults)


def test_p0_review_requires_schema_verified_findings_doc() -> None:
    """Commit 1 of the 2026-06-22 competitor-audit follow-ups: the P0-REVIEW
    task MUST emit a JSON findings doc conformant to the shipped schema, and
    the coordinator MUST halt on schema/verify failure rather than feeding
    unverified findings to the fix loop. Pin the wording so a future edit
    can't silently drop the gate."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")

    # The schema asset path is referenced verbatim — both reviewers and
    # adapter authors grep for this to find the artifact.
    assert "autonomous-fleet-core/assets/fleet-review-findings.schema.json" in tasks
    # The verifier CLI invocation is documented inline so coordinators don't
    # have to guess.
    assert "<SUBSTRATE>/verify_findings.py" in tasks
    # The HALT semantics are explicit. Don't soften them.
    assert "the run HALTS at P0-REVIEW" in tasks
    assert "MUST NOT enter the fix loop" in tasks
    # The doctrine reference is linked from the mission, not duplicated.
    assert "autonomous-fleet-core/references/review-findings.md" in tasks
    assert_no_contradiction_markers(tasks)


def test_skeptic_re_verifies_confirmed_set() -> None:
    """The skeptic narrows scope; re-verification catches the case where
    narrowing invalidates the original quoted_line."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")

    assert "p0-skeptic-findings.json" in tasks
    assert "CONFIRMED set" in tasks
    assert_no_contradiction_markers(tasks)


def test_fix_loop_consumes_only_verified_findings() -> None:
    """The safety property: the fix loop NEVER consumes unverified findings.
    This is the corpus-grounded counter to reviewer hallucination."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    flat = squash(tasks)

    assert "FIX LOOP consumes ONLY the verified set" in flat
    assert "never fed to a builder" in flat
    # Explicit anti-pattern: the orchestrator gates the loop, not the
    # builder's good faith. Pin the rationale.
    assert "orchestrator gates the loop" in flat
    assert_no_contradiction_markers(tasks)


def test_t_final_surfaces_verification_metrics_and_halts_on_leak() -> None:
    """T-FINAL pins unverified_findings == 0 as a precondition for done."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    flat = squash(tasks)

    for metric in (
        "verified_findings",
        "unverified_findings",
        "auto_applicable_findings",
        "human_gated_findings",
    ):
        assert metric in tasks, f"T-FINAL must surface {metric}"
    # HARD precondition is non-negotiable. Squashed because the wording spans
    # a markdown line break in the mission body.
    assert "HARD precondition for `status: done`" in flat
    # On leak, partial status, not done. Pin the exact word.
    assert "status: partial" in flat
    assert_no_contradiction_markers(tasks)


# ───────────────────────────────────────────────────────────────────────
# Commit 3 — ANTI-ANCHORING blind-fix-first protocol in Phase 1 FIX LOOP
# ───────────────────────────────────────────────────────────────────────


def test_fix_loop_wires_anti_anchoring_blind_fix_protocol() -> None:
    """The FIX LOOP must explicitly require the fresh build-blind reviewer to
    write a blind fix BEFORE opening the candidate diff, with the file path,
    audit-trail property (mtime ordering), and the ROOT_CAUSE_DEPTH bridge."""
    text = read_skill()
    fix_loop = section(text, "**FIX LOOP [Phase 1]**", "**T-FINAL")
    flat = squash(fix_loop)

    # The ordering claim: BEFORE opening the diff. This is the discipline.
    assert "BEFORE" in fix_loop
    # The file-path convention. Operators may grep for this path; pin it.
    assert ".fleet/runs/<run_id>/reviewer-blind-fix" in fix_loop
    # The three required fields of the blind-fix file. Pin to prevent
    # softening to "write some text somewhere".
    assert "point of creation" in flat.lower() or "POINT OF CREATION" in fix_loop
    assert "confidence" in flat.lower()

    # The ROOT_CAUSE_DEPTH bridge: a candidate at different call-stack depth
    # triggers root_cause_depth and the schema-required cascade_impact.
    # Without this bridge, anti-anchoring and ROOT_CAUSE_DEPTH are two
    # disconnected disciplines instead of a composed one.
    assert "ROOT_CAUSE_DEPTH" in fix_loop
    assert "category: root_cause_depth" in fix_loop or "root_cause_depth" in flat
    assert "cascade_impact" in fix_loop

    # The audit-trail property: a blind-fix file mtime-AFTER findings file is
    # a protocol violation. Without this, the order is unenforceable.
    assert "mtime" in flat.lower()

    # Canonical-discipline cross-reference, so doctrine readers know where the
    # protocol lives (blind-fix.md carries ANTI-ANCHORING after the engine split).
    assert "blind-fix.md" in fix_loop
    assert "ANTI-ANCHORING" in fix_loop
    assert_no_contradiction_markers(fix_loop)


def test_t_final_records_root_cause_audited_when_applicable() -> None:
    """T-FINAL must set root_cause_audited at the top level of fleet-outcome
    when a review mission filed any root_cause_depth findings, mirroring the
    optional-cross-cutting shape of unverified_assumptions / sources_logged."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    flat = squash(tasks)

    # The field name and the discipline reference. Pin both so a rename
    # without an engine.md update is caught.
    assert "root_cause_audited" in tasks
    assert "ROOT_CAUSE_DEPTH" in tasks

    # The semantics: true = every cascade re-EVIDed, false = at least one
    # deferred. Pin both branches.
    assert "true" in flat
    assert "false" in flat or "False" in flat

    # Cross-reference to deferred_missions. A `false` MUST result in a deferred
    # mission, otherwise the discipline is silently downgraded. Pin the link.
    assert "deferred_missions" in tasks

    # Omit-when-N/A rule. Without this, non-applicable readiness docs would
    # carry meaningless assertions.
    assert "Omit" in tasks or "omit" in tasks.lower()

    assert_no_contradiction_markers(tasks)


# ───────────────────────────────────────────────────────────────────────
# Commit 4 — T-FINAL run-archive manifest wiring
# ───────────────────────────────────────────────────────────────────────


def test_t_final_writes_run_archive_manifest_before_shipping() -> None:
    """T-FINAL must explicitly call out the manifest-writing step, the
    validator CLI, the three mtime-ordering invariants (so reviewers know
    what 'archive failed' means), the archive_enabled HARD precondition for
    status=done, and the run_id field. Without any of these, the discipline
    decays into 'and maybe also write a manifest somewhere'."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    flat = squash(tasks)

    # Engine cross-reference — the canonical discipline lives in engine.md.
    assert "engine-recovery.md ARCHIVE_ENABLED" in tasks

    # The mechanics: write_manifest + validate_run_archive.py. Pin both
    # names so a rename doesn't silently break operator scripts.
    assert "fleet_run.write_manifest" in flat or "fleet_run.write_manifest" in tasks
    assert "<SUBSTRATE>/validate_run_archive.py" in tasks

    # The three mtime-ordering invariants are mentioned explicitly. A
    # reviewer who sees a validator failure must know WHY it failed; the
    # SKILL is the first place they'll look. Don't make them grep engine.md.
    assert "blind_fix before findings" in flat
    assert "verify_summary after findings" in flat
    assert "readiness with the latest mtime" in flat

    # The hard-gate: archive_enabled=false incompatible with status=done.
    # Pin both halves so a softening to soft-warning fails.
    assert "archive_enabled: false" in tasks
    assert "incompatible with" in flat
    assert "status: done" in tasks

    # run_id is set alongside archive_enabled so post-hoc tools can jump
    # straight to the archive. Pin to prevent it being dropped as "optional".
    assert "`run_id: <run_id>`" in tasks or "run_id: <run_id>" in tasks

    # Omission rule. Without it, missions that emitted no artifacts would
    # carry meaningless `archive_enabled: false` assertions.
    assert "OMIT" in tasks or "omit" in tasks.lower()
    assert_no_contradiction_markers(tasks)


def test_archive_doctrine_block_in_skill_anchored_after_root_cause_audited() -> None:
    """Within T-FINAL, the assertion blocks have a deliberate order:
    schema-verified findings -> root_cause_audited -> archive (manifest).
    Archive is LAST because it manifests every prior artifact. Pin so a
    reordering doesn't accidentally tell operators to write the manifest
    before the findings exist."""
    text = read_skill()
    tasks = section(text, "TASK STRUCTURE", "Runtime goal")
    rca_idx = tasks.index("ROOT_CAUSE_DEPTH attestation")
    arch_idx = tasks.index("Run-archive manifest")
    assert rca_idx < arch_idx, (
        "Run-archive manifest block must come AFTER ROOT_CAUSE_DEPTH "
        "attestation — the archive manifests artifacts including the "
        "RCD-related findings, so RCD must be settled first"
    )
