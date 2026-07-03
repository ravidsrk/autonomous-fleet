"""Structural tests for engine-level discipline rails."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "skills" / "autonomous-fleet-core" / "references" / "engine.md"


def read_engine() -> str:
    return ENGINE.read_text(encoding="utf-8")


def section(text: str, heading: str, next_heading: str) -> str:
    start = text.index(heading)
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


def test_continue_worker_is_optional_with_spawn_fallback() -> None:
    """CONTINUE_WORKER must be an OPTIONAL primitive that aliases to SPAWN_WORKER.

    Deleting the alias-fallback clause (so adapters without restore have no
    documented behaviour) must fail this test.
    """
    engine = squash(read_engine())
    assert "CONTINUE_WORKER" in engine
    assert "ALIAS it to `SPAWN_WORKER`" in engine
    assert "OPTIONAL, like" in engine


def test_self_orientation_defines_reference_input_as_read_only() -> None:
    text = read_engine()
    orientation = section(
        text,
        "SELF-ORIENTATION",
        "ORCHESTRATOR DIRECTIVE",
    )
    orientation_flat = squash(orientation)

    assert "REFERENCE-INPUT" in orientation
    assert "TARGET vs REFERENCE dual-path" in orientation
    assert "reference repo/path" in orientation
    assert "read-only" in orientation
    assert "adapts FROM" in orientation
    assert "NEVER write" in orientation
    assert "TARGET" in orientation
    assert "open a PR against it" in orientation
    assert (
        "treat it as read-only material the fleet reads and adapts FROM; NEVER write to it, "
        "make it a TARGET, or open a PR against it."
    ) in orientation_flat
    assert "IS a writable TARGET" not in orientation
    assert "SHOULD write to it" not in orientation
    assert_no_contradiction_markers(orientation)


def test_result_state_gate_rejects_green_checkmark_inflation() -> None:
    text = read_engine()
    gate = section(
        text,
        "RESULT-STATE TERMINATION GATE",
        "SIGNAL RECONCILIATION",
    )

    assert "NECESSARY BUT NOT SUFFICIENT" in gate
    assert "NEVER terminate" in gate
    assert "`GOAL_COMPLETE` / `DONE`" in gate
    assert "query the actual result, not exit codes" in gate
    assert "e2e_verified" in gate
    assert "docs/secure-ship-e2e.md" in gate
    assert (
        "A green test/validator suite is NECESSARY BUT NOT SUFFICIENT. NEVER terminate "
        "(`GOAL_COMPLETE` / `DONE`) on green checkmarks alone. Verify the real end-to-end "
        "RESULT STATE: query the actual result, not exit codes"
    ) in squash(gate)
    assert "you MAY terminate" not in gate
    assert "do NOT bother to verify" not in gate
    assert_no_contradiction_markers(gate)


def test_frozen_scope_boundary_caps_run_scope() -> None:
    text = read_engine()
    gate = section(
        text,
        "FROZEN SCOPE BOUNDARY",
        "WORKER PLACEMENT",
    )

    assert "caps the WHOLE run's" in gate
    assert "current build" in gate
    assert "DECISIONS.md" in gate
    assert "roadmap" in gate
    assert "Reviewers FAIL any PR adding out-of-boundary work" in gate
    assert (
        "Do not add newly discovered ideas, optional features, refactors, or nice-to-haves "
        "to the current build."
    ) in squash(gate)
    assert "You MAY add newly discovered ideas" not in gate
    assert_no_contradiction_markers(gate)


def test_draft_both_and_gate_is_a_human_gated_decision_outcome() -> None:
    text = read_engine()
    gate = section(
        text,
        "COORDINATOR BEHAVIORS",
        "AUTONOMY ENFORCEMENT",
    )

    assert "draft-both-and-gate" in gate
    assert "draft both variants" in gate
    assert "DECISIONS.md" in gate
    assert "HALT for the human" in gate
    assert "third decision outcome beside proceed and defer" in gate
    assert "must not fabricate" in gate
    assert "coordinator must not pick a default and must not ship one variant" in gate
    assert "stop the affected task wave, and HALT for the human" in gate
    assert "do NOT HALT" not in gate
    assert "SHOULD pick a default" not in gate
    assert_no_contradiction_markers(gate)


def test_research_discipline_allows_throwaway_spike() -> None:
    text = read_engine()
    research = section(
        text,
        "RESEARCH DISCIPLINE",
        "MODEL & COST ROUTING",
    )

    assert "SPIKE" in research
    assert "load-bearing unknown" in research
    assert "ONE throwaway proof" in research
    assert "before the freeze" in research
    assert "record findings" in research
    assert "discard" in research
    assert "not documentation lookup" in research
    research_flat = squash(research)
    assert "record findings in `docs/research-notes.md`, then discard it" in research_flat
    assert "is not kept as build output" in research_flat
    assert "SHOULD be kept as build output" not in research
    assert "do NOT discard" not in research
    assert_no_contradiction_markers(research)


def test_context_handoff_proactive_rollup_is_not_duplicated() -> None:
    text = read_engine()
    handoff = section(
        text,
        "CONTEXT HANDOFF",
        "PLAN/DAG VALIDATION GATE",
    )

    assert text.count("Carry forward the") == 1
    assert handoff.count("PROACTIVE (don't wait for the cliff)") == 1
    assert (
        "Carry forward the rolling summary + the next ready wave, not the full history."
    ) in squash(handoff)
    assert "Carry forward the full history" not in handoff
    assert "do NOT roll up or summarize" not in handoff
    assert_no_contradiction_markers(handoff)


def test_wt_clean_is_tracked_across_pipeline_handoff_and_terminate() -> None:
    text = read_engine()
    autonomy = section(
        text,
        "AUTONOMY ENFORCEMENT",
        "RESULT-STATE TERMINATION GATE",
    )
    handoff = section(
        text,
        "CONTEXT HANDOFF",
        "PLAN/DAG VALIDATION GATE",
    )
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )
    pipeline_flat = squash(pipeline)

    assert "WT_CLEAN=true" in autonomy
    assert "merged but uncleaned task" in autonomy
    assert "NOT terminal" in autonomy

    assert "HANDOFF CARRIES" in handoff
    assert "WT path or environment id" in handoff
    assert "WT_CLEAN" in handoff

    assert "TASK ROW" in pipeline
    assert "WT_CLEAN" in pipeline
    assert "verify MERGED + branch-deleted FIRST" in pipeline
    assert "NEVER remove the active worktree" in pipeline_flat
    assert "NEVER remove a worktree whose branch is unmerged" in pipeline_flat
    assert "NEVER remove a worktree with uncommitted changes" in pipeline_flat
    assert "try X, fall back to Y" in pipeline
    assert "T_FINAL WORKTREE-ORPHAN SWEEP" in pipeline
    assert "orphan worktree" in pipeline
    assert "IGNORE those guard clauses" not in pipeline
    assert "remove any worktree unconditionally" not in pipeline
    assert_no_contradiction_markers(autonomy)
    assert_no_contradiction_markers(handoff)
    assert_no_contradiction_markers(pipeline)


def test_feature_fix_done_requires_regression_catching_test() -> None:
    text = read_engine()
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )
    pipeline_flat = squash(pipeline)

    assert "DONE CONDITION: regression-catching test" in pipeline
    assert "feature/fix task cannot set REVIEWED" in pipeline_flat
    assert "cannot be done" in pipeline_flat
    assert "regression-catching test" in pipeline
    assert "would FAIL if the repaired behavior broke again" in pipeline_flat
    assert "build-blind reviewer explicitly asserts" in pipeline_flat
    assert "not coverage padding" in pipeline_flat
    assert (
        "A feature/fix task cannot set REVIEWED and cannot be done unless it includes a "
        "regression-catching test that would FAIL if the repaired behavior broke again."
    ) in pipeline_flat
    assert "MAY set REVIEWED" not in pipeline
    assert "no test at all" not in pipeline
    assert "return PASS regardless" not in pipeline
    assert_no_contradiction_markers(pipeline)


def test_first_merge_spot_check_blocks_later_waves_on_fail() -> None:
    text = read_engine()
    pipeline = section(
        text,
        "PR-PER-TASK PIPELINE",
        "TRUST BOUNDARIES",
    )

    assert "FIRST-MERGE SPOT-CHECK" in pipeline
    assert "After the first task merges into BASE" in pipeline
    assert "preserved the branch commit count" in pipeline
    assert "authored by MAINTAINER" in pipeline
    assert "trailer usage matches the recorded AUTHORSHIP_MODE" in pipeline
    assert "PR branch is deleted" in pipeline
    assert "secret-scan ran" in pipeline
    assert "FIRST_MERGE_SPOT_CHECK=PASS or FAIL" in pipeline
    assert "block later waves" in pipeline
    assert (
        "On FAIL, block later waves and repair the merge pipeline before any further SHIP step."
    ) in squash(pipeline)
    assert "do NOT block later waves" not in pipeline
    assert "keep shipping" not in pipeline
    assert_no_contradiction_markers(pipeline)


def test_secret_scrub_is_gated_on_human_confirmed_rotation() -> None:
    text = read_engine()
    hygiene = section(
        text,
        "ROTATE-BEFORE-SCRUB PRECONDITION",
        "COMMIT & AUTHORSHIP",
    )
    hygiene_flat = squash(hygiene)

    assert "ROTATE-BEFORE-SCRUB PRECONDITION" in hygiene
    assert "git-history purge" in hygiene
    assert "repository secret-scrub" in hygiene
    assert "file-tracked `ROTATION_CONFIRMED=yes`" in hygiene
    assert "set by a human" in hygiene
    assert "does not scrub history yet" in hygiene
    assert "false safety" in hygiene
    assert "already-committed secret is already compromised" in hygiene_flat
    assert (
        "hard-gated on a file-tracked `ROTATION_CONFIRMED=yes` boolean that was set by a human"
    ) in hygiene_flat
    assert "does not scrub history yet" in hygiene_flat
    assert "PROCEEDS to scrub history immediately" not in hygiene
    assert "scrub anyway" not in hygiene
    assert_no_contradiction_markers(hygiene)


def test_strict_mode_doctrine_block_wires_stop_verify_hook_and_lineage() -> None:
    """Commit 2 of the 2026-06-22 competitor-audit follow-ups: the engine
    must carry a STRICT MODE block that names the stop-verify hook, the
    install path, the three discipline levels, the lineage citation, and
    the fail-open guarantee. A future edit that softens any of these
    properties should fail this test."""
    text = read_engine()
    sm = section(
        text,
        "RUNTIME ENFORCEMENT GATE",
        "INFLATION POST-MORTEM",
    )
    sm_flat = squash(sm)

    # The asset path operators install — pin so it can't drift without breaking
    # the strict-mode.md install instructions in lock-step.
    assert "skills/autonomous-fleet-adapter-claude-code/assets/hooks/stop-verify.sh" in sm
    # The doctrine doc is linked, not duplicated.
    assert "references/strict-mode.md" in sm
    # All three discipline levels named.
    assert "Loose" in sm
    assert "Strict" in sm
    assert "Paranoid" in sm
    # The CC contract is named: this is what closes the loop.
    assert '{decision:"block"' in sm or "decision:\"block\"" in sm
    # The named failure mode (self-attested completion) is called out so the
    # gate's PURPOSE survives prose edits.
    assert "SELF-ATTESTED COMPLETION" in sm
    # Fail-open is non-negotiable — a paranoid future edit that tries to make
    # this fail-closed must be caught.
    assert "Fail-open by design" in sm_flat or "fail-open by design" in sm_flat.lower()
    # Lineage citation — keeps the audit trail intact.
    assert "claude-code-orchestra" in sm
    assert "multi-llm-plugin-cc" in sm
    assert "competitor-audit-2026-06-22.md" in sm
    # The gate is one more layer ON TOP OF existing disciplines, NOT a
    # replacement. This is the most-mis-read property of the doctrine.
    assert "not a replacement" in sm_flat
    assert_no_contradiction_markers(sm)


def test_strict_mode_block_anchors_after_result_state_termination_gate() -> None:
    """The two sections are conceptually paired: RESULT-STATE says "green
    isn't enough", STRICT MODE gives the mechanical enforcement. They MUST
    sit next to each other so a reader gets the disciplinary motivation
    before the mechanism."""
    text = read_engine()
    rs_idx = text.index("RESULT-STATE TERMINATION GATE")
    sm_idx = text.index("RUNTIME ENFORCEMENT GATE")
    inflation_idx = text.index("INFLATION POST-MORTEM")
    assert rs_idx < sm_idx < inflation_idx, (
        "STRICT MODE must sit between RESULT-STATE TERMINATION GATE and "
        "INFLATION POST-MORTEM to preserve the result-state -> enforcement "
        "narrative"
    )

def test_root_cause_depth_doctrine_block_present_with_hard_rule_and_schema_hook() -> None:
    """Commit 3 of the 2026-06-22 competitor-audit follow-ups: the engine
    must carry a ROOT_CAUSE_DEPTH block that defines the HARD RULE in
    SWE-Review's verbatim language, names the schema-enforcement (cascade_impact
    REQUIRED when category=root_cause_depth), and cites the source. A future
    edit that softens the HARD RULE to a suggestion must fail this test."""
    text = read_engine()
    rcd = section(
        text,
        "ROOT_CAUSE_DEPTH: a fix at the wrong call-stack depth",
        "ANTI-ANCHORING:",
    )
    rcd_flat = squash(rcd)

    # The defining contrast with the existing EVID and e2e_verified disciplines.
    # ROOT_CAUSE_DEPTH is the UPSTREAM check; pin so the doctrine doesn't
    # collapse into a redundant restatement of either.
    assert "EVID" in rcd
    assert "e2e_verified" in rcd
    assert "call-stack depth" in rcd or "call stack depth" in rcd

    # The HARD RULE language is verbatim from SWE-Review. Pin all four bullets so
    # future paraphrasing cannot weaken the discipline.
    assert "HARD RULE" in rcd
    assert "EVEN WHEN TESTS PASS" in rcd or "even when tests pass" in rcd.lower()
    assert "different/shallower location" in rcd_flat
    assert "doesn't fix the root cause but it prevents the crash" in rcd_flat
    assert "point of USE instead of fixing the point of CREATION" in rcd_flat
    assert "fixes ONE manifestation but the root cause can trigger the same issue via other paths" in rcd_flat

    # The schema-enforcement hook — this is what makes the discipline
    # MECHANICAL rather than aspirational. Without this, ROOT_CAUSE_DEPTH is
    # just prose; with it, the verifier rejects miscategorised symptom-fixes.
    assert "cascade_impact" in rcd
    assert "REQUIRED" in rcd or "required" in rcd
    assert "category: root_cause_depth" in rcd or "`category: root_cause_depth`" in rcd

    # Lineage citation. Keeps the audit trail intact for future contributors.
    assert "SWE-Review" in rcd
    assert "Wang" in rcd  # primary citation
    assert "competitor-audit-2026-06-22.md" in rcd
    assert_no_contradiction_markers(rcd)


def test_anti_anchoring_doctrine_block_defines_blind_fix_protocol() -> None:
    """The blind-fix protocol is procedural: the order of operations IS the
    discipline. Pin the file-path convention, the mtime-ordering audit
    property, and the three required contents of the blind-fix file."""
    text = read_engine()
    aa = section(
        text,
        "ANTI-ANCHORING:",
        "RESULT-STATE TERMINATION GATE",
    )
    aa_flat = squash(aa)

    # The mechanical heart: blind fix BEFORE candidate diff.
    assert "BEFORE" in aa
    assert "blind fix" in aa.lower() or "blind-fix" in aa.lower()
    # Path convention — operators install hook scripts that look for this path.
    assert ".fleet/runs/" in aa
    assert "reviewer-blind-fix" in aa
    # The three required fields in the blind-fix file. Pin so future edits
    # can't reduce the discipline to "just write a paragraph somewhere".
    assert "POINT OF CREATION" in aa or "point of creation" in aa.lower()
    assert "confidence" in aa.lower()
    # The audit-trail property: mtime ordering. Without this, the protocol is
    # unverifiable — a reviewer could write the blind fix AFTER reading the
    # diff and the orchestrator would never know.
    assert "mtime" in aa.lower()
    assert "AFTER" in aa or "after" in aa.lower()

    # Names build-blindness as the existing rule it COMPLEMENTS (not replaces).
    # The three reviewer-discipline rules must be distinguishable in prose.
    assert "build-blind" in aa.lower() or "build conversation" in aa.lower()

    # Lineage citation.
    assert "SWE-Review" in aa
    assert "competitor-audit-2026-06-22.md" in aa
    assert_no_contradiction_markers(aa)


def test_new_disciplines_anchor_before_result_state_termination_gate() -> None:
    """ROOT_CAUSE_DEPTH and ANTI-ANCHORING are UPSTREAM defenses (prevent the
    symptom-fix from happening) whereas RESULT-STATE TERMINATION GATE is the
    post-hoc check (the fix may have passed CI but didn't fix reality). The
    upstream-then-downstream narrative ordering MUST be preserved."""
    text = read_engine()
    rcd_idx = text.index("ROOT_CAUSE_DEPTH: a fix at the wrong call-stack depth")
    aa_idx = text.index("ANTI-ANCHORING: reviewer commits its own fix")
    rs_idx = text.index("RESULT-STATE TERMINATION GATE")
    sm_idx = text.index("RUNTIME ENFORCEMENT GATE")
    inflation_idx = text.index("INFLATION POST-MORTEM")
    # All five blocks live in this exact order.
    assert rcd_idx < aa_idx < rs_idx < sm_idx < inflation_idx, (
        "ROOT_CAUSE_DEPTH and ANTI-ANCHORING must sit before RESULT-STATE "
        "TERMINATION GATE so the reader gets upstream-defense -> "
        "post-hoc-gate -> runtime-enforcement in that order"
    )


# ───────────────────────────────────────────────────────────────────────
# Commit 4 — ARCHIVE_ENABLED doctrine block
# ───────────────────────────────────────────────────────────────────────


def test_archive_enabled_doctrine_block_present_with_all_four_hard_rules() -> None:
    """The engine must carry an ARCHIVE_ENABLED block defining four HARD RULES
    (layout, manifest, mtime-ordering, archive_enabled precondition), the
    deterministic run_id format, and a retention policy. Pin all four rules
    so a future edit that drops one (especially the mtime-ordering rules,
    which encode Commits 1-3 disciplines) fails this test."""
    text = read_engine()
    # End-anchor uses the FULL next-section heading text (not just
    # "INFLATION POST-MORTEM") because that phrase appears multiple times
    # IN-PROSE inside the ARCHIVE_ENABLED block (referencing the next-run
    # chaining machinery). The section() helper cuts at the FIRST occurrence,
    # which would slice mid-paragraph. The full heading text is unique.
    arch = section(
        text,
        "ARCHIVE_ENABLED: every run leaves a manifest-audited file trail",
        'INFLATION POST-MORTEM: break the "we already shipped that" trap on re-runs.',
    )
    arch_flat = squash(arch)

    # The block names BOTH neighboring disciplines (STRICT MODE which detects,
    # INFLATION POST-MORTEM which chains). Without this composition, the
    # archive is just storage — with it, the archive is the substrate that
    # makes the other commits enforceable.
    assert "STRICT MODE" in arch
    assert "INFLATION POST-MORTEM" in arch

    # The deterministic run_id format. Pin to prevent freeform run-ids from
    # creeping back in via a "let's just use the branch name" PR.
    assert "YYYYMMDDTHHMMSSZ-<mission>-<short-hash>" in arch
    assert ".fleet/runs/" in arch

    # All four HARD RULES present. Word-pin each so a paraphrase that
    # weakens any of them fails the test.
    assert "HARD RULE — archive layout" in arch
    assert "HARD RULE — manifest" in arch
    assert "HARD RULE — mtime ordering invariants" in arch
    assert "HARD RULE — `archive_enabled: true` is a precondition" in arch

    # Mtime-ordering invariants are where Commits 1-3 disciplines become
    # auditable. Pin each invariant. Without these, the archive is files
    # in a folder; with these, the archive is a discipline-enforcement
    # mechanism.
    assert "blind_fix" in arch and "BEFORE every `findings`" in arch
    assert "verify_summary" in arch and "AFTER the `findings`" in arch
    assert "readiness" in arch and "LATEST mtime" in arch

    # archive_enabled precondition for status=done. Pin so a future loosening
    # to "soft warning" fails.
    assert "precondition for `status: done`" in arch
    assert "status: partial" in arch

    # Manifest schema location. Pin so the schema file can't be moved without
    # also updating the doctrine.
    assert "fleet-run-manifest.schema.json" in arch

    # Retention policy explicit. Without this, operators won't know whether
    # the engine garbage-collects archives.
    assert "does not garbage-collect" in arch_flat or "Retention" in arch
    assert "out-of-band" in arch

    # Lineage citation.
    assert "competitor-audit-2026-06-22.md" in arch
    assert_no_contradiction_markers(arch)


def test_archive_enabled_block_anchors_between_strict_mode_and_inflation() -> None:
    """ARCHIVE_ENABLED sits BETWEEN STRICT MODE (which detects archive files)
    and INFLATION POST-MORTEM (which chains across archives). The ordering
    encodes the narrative: detection → substrate → cross-run chaining.
    Reordering breaks the reader's path through the doctrine."""
    text = read_engine()
    sm_idx = text.index("RUNTIME ENFORCEMENT GATE")
    arch_idx = text.index("ARCHIVE_ENABLED: every run leaves")
    inflation_idx = text.index("INFLATION POST-MORTEM")
    assert sm_idx < arch_idx < inflation_idx, (
        "ARCHIVE_ENABLED must sit between STRICT MODE and INFLATION "
        "POST-MORTEM to preserve detection -> substrate -> chaining narrative"
    )

def test_trace_emission_doctrine_block_present_with_dashboard_contract() -> None:
    """The engine must carry a TRACE EMISSION block that names the dashboard
    contract, the "emit-before-ledger-commit" invariant, the schema-version
    pin, and the degraded-telemetry escape hatch. Pin every clause so a
    future edit that drops any of them (especially the ordering rule)
    fails this test.

    Pairs with `tests/test_emit_trace.py::test_doctrine_emit_before_ledger_write`
    which enforces the same ordering at runtime.
    """
    text = read_engine()
    trace = section(
        text,
        "TRACE EMISSION",
        "CONTEXT HANDOFF",
    )

    # Dashboard-contract framing. vibe-kanban, Agent View, and custom
    # dashboards are interchangeable consumers — pin so the doctrine
    # doesn't drift into "the trace is for vibe-kanban".
    assert "vibe-kanban" in trace
    assert "Agent View" in trace
    assert "custom dashboards" in trace
    assert "interchangeable consumers" in trace

    # The core invariant. The whole point of the doctrine.
    trace_flat = squash(trace)
    assert "SHOULD emit a trace event BEFORE the ledger" in trace
    assert "the LEDGER is the authoritative loop state" in trace
    assert "trace first, ledger second" in trace_flat

    # Schema is the contract: pinned at 1.0, breaking changes need a new id.
    assert 'schema_version: "1.0"' in trace
    assert "NEW `$id`" in trace
    assert "fleet-trace.schema.json" in trace

    # Degraded-telemetry escape hatch.
    assert "NOT a hard error" in trace
    assert "trace_emission_degraded: true" in trace
    assert "fleet-outcome.yaml" in trace

    # Landscape gap closure.
    assert "Gap 8" in trace

    assert_no_contradiction_markers(trace)


def test_trace_emission_block_anchors_after_signal_reconciliation() -> None:
    """TRACE EMISSION sits AFTER SIGNAL RECONCILIATION and BEFORE CONTEXT
    HANDOFF. The ordering encodes the narrative: reconciled state ->
    emit the transition -> survive context limits."""
    text = read_engine()
    sig_idx = text.index("SIGNAL RECONCILIATION")
    trace_idx = text.index("TRACE EMISSION")
    handoff_idx = text.index("CONTEXT HANDOFF")
    assert sig_idx < trace_idx < handoff_idx, (
        "TRACE EMISSION must sit between SIGNAL RECONCILIATION and "
        "CONTEXT HANDOFF to preserve reconcile -> emit -> survive narrative"
    )


def test_write_lock_discipline_block_present_with_two_lock_kinds() -> None:
    """The engine must carry a WRITE-LOCK DISCIPLINE block that names
    both lock kinds, the steal preconditions, and the implementation
    pointer. Pair with tests/test_locks.py which enforces the runtime
    behaviour.
    """
    text = read_engine()
    block = section(
        text,
        "WRITE-LOCK DISCIPLINE",
        "CONTEXT HANDOFF",
    )

    # Both lock kinds are named with their lifetimes.
    assert "CONSTRUCTION LOCK" in block
    assert "REQUEST LOCK" in block
    assert "Long-held" in block
    assert "Short-held" in block

    # The asymmetry rule: construction MAY hold request, not vice versa.
    flat = squash(block)
    assert "construction lock MAY hold a request lock" in flat
    assert "long-held request lock) is forbidden" in flat

    # Steal preconditions: confirmed-dead signal from SIGNAL RECONCILIATION.
    assert "SIGNAL RECONCILIATION" in block
    assert "dead-worker detection" in block
    assert "Stealing without a confirmed-dead signal is a protocol violation" in block

    # Implementation pointer so engine readers can find the code.
    assert "<SUBSTRATE>/lib/locks.py" in block
    assert ".fleet/runs/<run_id>/locks/" in block

    assert_no_contradiction_markers(block)


def test_write_lock_discipline_block_anchors_after_trace_emission() -> None:
    """WRITE-LOCK DISCIPLINE sits AFTER TRACE EMISSION and BEFORE
    CONTEXT HANDOFF. The ordering encodes the narrative: emit the
    transition -> serialize the mutation -> survive context limits.
    """
    text = read_engine()
    trace_idx = text.index("TRACE EMISSION")
    lock_idx = text.index("WRITE-LOCK DISCIPLINE")
    handoff_idx = text.index("CONTEXT HANDOFF")
    assert trace_idx < lock_idx < handoff_idx, (
        "WRITE-LOCK DISCIPLINE must sit between TRACE EMISSION and "
        "CONTEXT HANDOFF to preserve emit -> serialize -> survive narrative"
    )

def test_substrate_kill_switch_block_present_and_complete() -> None:
    """SUBSTRATE KILL-SWITCH CONVENTION block must list all 4 layers
    with their env-var names, the Layer 2 legacy alias, the truthy
    semantics, the implementation pointer, and the doctrine reference.
    Drift here means the bench can't measure what it claims."""
    text = read_engine()
    block = section(
        text,
        "SUBSTRATE KILL-SWITCH CONVENTION",
        "CONTEXT HANDOFF",
    )

    # All 4 layer env vars.
    for var in (
        "FLEET_DISABLE_VERIFY_FINDINGS",
        "FLEET_DISABLE_STOP_VERIFY",
        "FLEET_DISABLE_BLIND_FIX",
        "FLEET_DISABLE_RUN_ARCHIVE",
    ):
        assert var in block, f"engine.md kill-switch block missing {var}"

    # One knob per layer — no legacy aliases. Pin it: if someone
    # re-adds STOP_VERIFY_DISABLED to the doctrine block, this fails.
    assert "STOP_VERIFY_DISABLED" not in block
    assert "back-compat" not in block
    assert "legacy alias" not in block

    # Truthy semantics and the strict-allow-list intent.
    flat = squash(block)
    assert "case-insensitive" in flat
    assert "1`/`true`/`yes`/`on`" in flat or "1/true/yes/on" in flat

    # Disable contract semantics.
    assert "treat the layer's verdict as PASS" in block
    assert "BEFORE arg parsing" in block

    # Bench tie-in (this is why the convention exists at all).
    assert "bench-adversarial.sh" in block
    assert "falsifiable comparator" in block

    # Implementation + doctrine pointers.
    assert "<SUBSTRATE>/lib/substrate_disable.py" in block
    assert "references/substrate-disable-knobs.md" in block

    assert_no_contradiction_markers(block)


def test_substrate_kill_switch_block_anchors_after_write_lock() -> None:
    """SUBSTRATE KILL-SWITCH sits AFTER WRITE-LOCK DISCIPLINE and BEFORE
    CONTEXT HANDOFF. Ordering encodes: serialize -> escape-hatch ->
    survive."""
    text = read_engine()
    lock_idx = text.index("WRITE-LOCK DISCIPLINE")
    kill_idx = text.index("SUBSTRATE KILL-SWITCH CONVENTION")
    handoff_idx = text.index("CONTEXT HANDOFF")
    assert lock_idx < kill_idx < handoff_idx


def test_layer2_scoped_to_claude_code_only() -> None:
    """Issue #83: Layer 2 (stop-gate) ships for Claude Code only; the engine
    and strict-mode reference must say so rather than implying multi-runtime
    enforcement."""
    engine = (ROOT / "skills/autonomous-fleet-core/references/engine.md").read_text(encoding="utf-8")
    assert "SHIPPED FOR CLAUDE CODE ONLY" in engine
    strict = (ROOT / "skills/autonomous-fleet-core/references/strict-mode.md").read_text(encoding="utf-8")
    assert "shipped for **Claude Code\n> only**" in strict or "Claude Code only" in strict


def test_engine_defers_knob_registry_and_ledger_authority() -> None:
    """Issue #85: engine.md must not duplicate the knob registry (stale copy
    contradiction) and must state ledger-authoritative / trace-telemetry
    consistently with the fail-soft emission bullet."""
    engine = (ROOT / "skills/autonomous-fleet-core/references/engine.md").read_text(encoding="utf-8")
    assert "substrate-disable-knobs.md" in engine
    assert "nine knobs" in engine
    assert "the LEDGER is the authoritative loop state" in engine
    assert 'trace is the source of truth for "what happened"' not in engine


def test_research_discipline_is_host_conditional() -> None:
    """Issue #86: the worker preamble must not mandate a tool most hosts lack;
    tool binding resolves at SELF-ORIENTATION with a native-web-search
    fallback, and workers may only invoke confirmed-present tools."""
    engine = (ROOT / "skills/autonomous-fleet-core/references/engine.md").read_text(encoding="utf-8")
    assert "host-conditional tooling" in engine
    assert "NEVER invoke a research tool it has not confirmed exists" in engine
    preamble = engine.split("RESEARCH: before coding against any external fact")[1][:500]
    assert "monid" not in preamble
    assert "native web" in preamble


def test_authorship_mode_is_a_deliberate_documented_policy() -> None:
    """Issue #102: authorship is an explicit policy with rationale, defaulting
    to attributed (agent trailers), never an inherited no-trailer default."""
    engine = (ROOT / "skills/autonomous-fleet-core/references/engine.md").read_text(encoding="utf-8")
    assert "AUTHORSHIP_MODE" in engine
    assert "`attributed` (DEFAULT)" in engine
    assert "Co-Authored-By" in engine
    assert "never impersonate a DIFFERENT human" in engine
    assert "No agent/tool trailers." not in engine
