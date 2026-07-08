"""Tests for the run-archive scheme: fleet_run.py lib + validate_run_archive.py CLI.

The discipline being protected:
  - Deterministic run_id format (sortable, greppable, collision-resistant)
  - Manifest schema (path-escape safety, kind enum, sha256 integrity, size)
  - created_utc <= every files[].mtime_utc (run-start precedes accretion)
  - Cross-cutting mtime-ordering invariants that ENCODE Commits 1-3 disciplines:
    * blind_fix < findings (per producer)        — ANTI-ANCHORING
    * verify_summary > findings (per producer)   — stale-audit prevention
    * readiness has the latest mtime             — no post-readiness edits

A schema-clean manifest that violates the ordering invariants MUST fail
validation. That's the whole reason the validator exists — the schema alone
wouldn't catch a reviewer who wrote their blind fix AFTER reading the diff.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lib.fleet_run as fleet_run  # noqa: E402

from lib.fleet_run import (  # noqa: E402
    MAX_ARCHIVE_BYTES,
    RUN_ID_PATTERN,
    SCHEMA_VERSION,
    VALID_KINDS,
    FileEntry,
    allocate_run_id,
    archive_dir,
    ensure_archive_dir,
    file_entry_for,
    load_and_validate_manifest,
    parse_run_id,
    validate_manifest_payload,
    write_manifest,
)


# ───────────────────────────────────────────────────────────────────────
# Schema-lib agreement (drift defence)
# ───────────────────────────────────────────────────────────────────────


SCHEMA_PATH = (
    ROOT / "skills" / "autonomous-fleet-core" / "assets" / "fleet-run-manifest.schema.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists_and_is_valid_json():
    assert SCHEMA_PATH.is_file(), f"schema missing at {SCHEMA_PATH}"
    _schema()


def test_lib_schema_version_matches_schema_const():
    """The lib's SCHEMA_VERSION must equal the schema's pinned const. A mismatch
    means lib-written manifests would fail schema validation in any downstream
    tool that uses the JSON schema directly (e.g. an editor with jsonschema
    LSP). Pin to catch the drift at test time."""
    schema = _schema()
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION


def test_lib_valid_kinds_match_schema_enum():
    """The lib's VALID_KINDS must equal the schema's kind enum exactly. A
    new kind added to the schema without updating the lib means the lib's
    validator would reject manifests that the schema accepts (and vice versa).
    The two enforcement layers MUST agree."""
    schema = _schema()
    schema_kinds = set(schema["$defs"]["file_entry"]["properties"]["kind"]["enum"])
    assert VALID_KINDS == frozenset(schema_kinds)


def test_lib_run_id_regex_matches_schema_pattern():
    """The lib's RUN_ID_PATTERN must equal the schema's run_id pattern. The
    schema pattern is authoritative; the lib follows. A mismatch means a
    run_id accepted by one validator might be rejected by the other."""
    schema = _schema()
    assert RUN_ID_PATTERN.pattern == schema["properties"]["run_id"]["pattern"]


# ───────────────────────────────────────────────────────────────────────
# run_id allocator
# ───────────────────────────────────────────────────────────────────────


def test_allocate_run_id_produces_well_formed_id():
    """The happy path: a valid mission slug produces a run_id matching the
    deterministic regex. Pin so the format never drifts silently."""
    rid = allocate_run_id("adversarial-review-and-fix")
    assert RUN_ID_PATTERN.match(rid), f"allocated run_id is malformed: {rid}"
    # Round-trip parses cleanly.
    ts, mission, suffix = parse_run_id(rid)
    assert mission == "adversarial-review-and-fix"
    assert len(suffix) == 6
    assert ts.tzinfo == timezone.utc


def test_allocate_run_id_uses_provided_now():
    """Determinism: when `now` is passed explicitly, the timestamp portion
    matches it to the second. Without this, tests can't construct
    deterministic manifest payloads."""
    fixed = datetime(2026, 6, 23, 14, 18, 33, tzinfo=timezone.utc)
    rid = allocate_run_id("doc-sync", now=fixed)
    assert rid.startswith("20260623T141833Z-doc-sync-")


@pytest.mark.parametrize(
    "bad_mission",
    [
        "Bad-Mission",      # uppercase forbidden
        "-leading-hyphen",  # leading hyphen forbidden
        "trailing-hyphen-", # trailing hyphen forbidden
        "under_score",      # underscore forbidden
        "with space",       # space forbidden
        "",                 # empty forbidden
        "a",                # single char doesn't match the ends-alphanum-after-start regex
    ],
)
def test_allocate_run_id_rejects_invalid_mission_slugs(bad_mission):
    """Mission slugs are constrained because they're used as filename fragments
    downstream. Pin every disallowed shape so a regression that loosens the
    rule (e.g. accidentally accepting underscores) fails."""
    with pytest.raises(ValueError, match="mission slug"):
        allocate_run_id(bad_mission)


def test_allocate_run_id_concurrent_calls_dont_collide():
    """The 6-hex suffix exists for collision avoidance under same-second
    same-pid runs. 200 sequential calls must all produce unique ids — if any
    collide, the suffix entropy is insufficient and concurrent runs would
    overwrite each other's archives."""
    fixed = datetime(2026, 6, 23, 14, 18, 33, tzinfo=timezone.utc)
    ids = {allocate_run_id("test-mission", now=fixed) for _ in range(200)}
    assert len(ids) == 200, "run_id suffixes collided"


def test_parse_run_id_rejects_freeform_ids():
    """Operator-friendly names like `my-branch-test-run` MUST be rejected.
    Without this, post-hoc tools that index by run_id format would silently
    skip non-conforming runs."""
    for bad in ["test-run", "my-branch", "20260623-mission-abc", "20260623T141833Z-mission-tooLong"]:
        with pytest.raises(ValueError):
            parse_run_id(bad)


def test_parse_run_id_handles_mission_slugs_with_hyphens():
    """Mission slugs themselves may contain hyphens (adversarial-review-and-fix).
    Pin that the parser correctly splits on the LAST hyphen-suffix boundary,
    not the first hyphen it sees."""
    ts = datetime(2026, 6, 23, 14, 18, 33, tzinfo=timezone.utc)
    rid = allocate_run_id("adversarial-review-and-fix", now=ts)
    _, mission, suffix = parse_run_id(rid)
    assert mission == "adversarial-review-and-fix"
    assert len(suffix) == 6


# ───────────────────────────────────────────────────────────────────────
# Archive directory helpers
# ───────────────────────────────────────────────────────────────────────


def test_archive_dir_refuses_invalid_run_id(tmp_path):
    """archive_dir is a path-construction helper, but it MUST refuse invalid
    run_ids — without this, a typo'd run_id would silently create an archive
    at a path that no downstream tool can find."""
    with pytest.raises(ValueError, match="invalid run_id"):
        archive_dir(tmp_path, "not-a-valid-id")


def test_ensure_archive_dir_is_idempotent(tmp_path):
    """Workers may call ensure_archive_dir multiple times during a run (once
    at startup, again on retry). Two calls with the same run_id MUST return
    the same path and not raise."""
    rid = allocate_run_id("doc-sync")
    a = ensure_archive_dir(tmp_path, rid)
    b = ensure_archive_dir(tmp_path, rid)
    assert a == b
    assert a.is_dir()


def test_ensure_archive_dir_does_not_create_for_invalid_id(tmp_path):
    """Defence in depth: even on the create path, an invalid run_id must
    raise BEFORE filesystem mutation. Without this, a misnamed dir could
    leak onto disk."""
    with pytest.raises(ValueError):
        ensure_archive_dir(tmp_path, "freeform-name")


# ───────────────────────────────────────────────────────────────────────
# file_entry_for: path-escape safety + kind/producer validation
# ───────────────────────────────────────────────────────────────────────


def test_file_entry_for_rejects_path_outside_archive(tmp_path):
    """Path-escape attempt: a file living OUTSIDE the archive directory must
    be rejected at construction. Without this, a misconfigured worker could
    manifest a file from anywhere on the filesystem and the manifest would
    look legitimate."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    outside = tmp_path / "outside.txt"
    outside.write_text("not in archive", encoding="utf-8")
    with pytest.raises(ValueError, match="not inside archive root"):
        file_entry_for(outside, arch, kind="other", producer="test")


def test_file_entry_for_rejects_invalid_kind(tmp_path):
    """Pin the kind enum from the lib side too. A typo'd kind ('findng',
    'verify-summary' with hyphen) would silently mis-categorise files and
    bypass the mtime-ordering checks."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    f = arch / "x.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="kind must be one of"):
        file_entry_for(f, arch, kind="findng", producer="test")


def test_file_entry_for_rejects_empty_producer(tmp_path):
    """Empty producer breaks the per-producer mtime-ordering check (the
    blind_fix<findings invariant pairs by producer). An empty producer would
    silently bypass that check. Reject."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    f = arch / "x.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="producer must be a non-empty string"):
        file_entry_for(f, arch, kind="other", producer="")
    with pytest.raises(ValueError, match="producer must be a non-empty string"):
        file_entry_for(f, arch, kind="other", producer="   ")


def test_file_entry_for_computes_sha256_and_size(tmp_path):
    """Happy path: a real file produces a FileEntry with correct sha256 +
    size + relative path."""
    import hashlib

    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    content = b"hello fleet" * 100
    f = arch / "sub" / "file.bin"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(content)
    entry = file_entry_for(f, arch, kind="other", producer="test")
    assert entry.path == "sub/file.bin"
    assert entry.bytes == len(content)
    assert entry.sha256 == hashlib.sha256(content).hexdigest()
    # Finding 25: mtime_utc now carries MICROSECOND precision so same-second
    # artifacts no longer collide. The manifest schema (UTC_ISO_PATTERN)
    # accepts the fractional-seconds form.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$", entry.mtime_utc)
    from lib.fleet_run import UTC_ISO_PATTERN

    assert UTC_ISO_PATTERN.match(entry.mtime_utc)


# ───────────────────────────────────────────────────────────────────────
# write_manifest: cross-checks and required fields
# ───────────────────────────────────────────────────────────────────────


def _make_entry(arch: Path, name: str, kind: str, producer: str, content: str = "x") -> FileEntry:
    """Helper: drop a file in `arch` with `content`, return its FileEntry."""
    f = arch / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return file_entry_for(f, arch, kind=kind, producer=producer)


def test_write_manifest_round_trips(tmp_path):
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    entry = _make_entry(arch, "a.json", "findings", "reviewer-x")
    path = write_manifest(arch, run_id=rid, mission="doc-sync", files=[entry])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["run_id"] == rid
    assert payload["mission"] == "doc-sync"
    assert payload["files"][0]["path"] == "a.json"


def test_write_manifest_rejects_run_id_mission_mismatch(tmp_path):
    """The mission argument MUST match the slug embedded in run_id. A mismatch
    is almost always a coordinator bug (passed the wrong mission name to a
    worker); without this check the manifest would lie about which mission
    produced it."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    entry = _make_entry(arch, "a.json", "findings", "rx")
    with pytest.raises(ValueError, match="does not match run_id slug"):
        write_manifest(arch, run_id=rid, mission="dependency-update", files=[entry])


def test_write_manifest_rejects_empty_file_list(tmp_path):
    """An archive with no first-class artifacts has no audit trail to record.
    Pin so empty manifests never get written — they'd be silent
    discipline-bypass attempts ('look, the manifest exists!')."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    with pytest.raises(ValueError, match="at least one file entry"):
        write_manifest(arch, run_id=rid, mission="doc-sync", files=[])


# ───────────────────────────────────────────────────────────────────────
# validate_manifest_payload: shape + ordering + on-disk
# ───────────────────────────────────────────────────────────────────────


def test_validate_manifest_happy_path(tmp_path):
    """End-to-end: build an archive with files in the correct mtime order,
    write a manifest, validate. Zero errors. The validator's existence
    depends on this path being noisy-free."""
    rid = allocate_run_id("adversarial-review-and-fix")
    arch = ensure_archive_dir(tmp_path, rid)

    # blind_fix first, then findings, then verify_summary, then readiness last.
    # sleep(1.05) because mtime is second-resolution on most filesystems and
    # the invariants are strict-less-than.
    bf = arch / "blind-fix-F-001.md"
    bf.write_text("blind", encoding="utf-8")
    time.sleep(1.05)
    fd = arch / "findings.json"
    fd.write_text('{"findings":[]}', encoding="utf-8")
    time.sleep(1.05)
    vs = arch / "verify-summary.json"
    vs.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# done", encoding="utf-8")

    entries = [
        file_entry_for(bf, arch, kind="blind_fix", producer="reviewer-a"),
        file_entry_for(fd, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(vs, arch, kind="verify_summary", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="adversarial-review-and-fix", files=entries)
    payload, errs = load_and_validate_manifest(arch)
    assert errs == [], f"expected clean validation, got: {errs}"
    assert payload is not None and payload["run_id"] == rid


def test_validate_detects_anti_anchoring_violation(tmp_path):
    """The KEY discipline test: a blind_fix that's mtime-AFTER its findings
    violates Commit 3 ANTI-ANCHORING. The validator must catch this — without
    this check, a reviewer could write the blind fix after reading the diff
    and nobody would know."""
    rid = allocate_run_id("adversarial-review-and-fix")
    arch = ensure_archive_dir(tmp_path, rid)

    # findings FIRST, blind_fix AFTER — wrong order.
    fd = arch / "findings.json"
    fd.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    bf = arch / "blind-fix.md"
    bf.write_text("blind", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")

    entries = [
        file_entry_for(fd, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(bf, arch, kind="blind_fix", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="adversarial-review-and-fix", files=entries)
    _, errs = load_and_validate_manifest(arch)
    assert any("ANTI-ANCHORING" in e for e in errs), errs


def test_validate_detects_stale_verify_summary(tmp_path):
    """A verify_summary mtime BEFORE its findings is a stale audit from a
    previous run, mis-archived into this one. The validator must catch this —
    without it, an old summary could mask a failing new verification."""
    rid = allocate_run_id("adversarial-review-and-fix")
    arch = ensure_archive_dir(tmp_path, rid)

    # verify_summary FIRST, findings AFTER — wrong order.
    vs = arch / "verify-summary.json"
    vs.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    fd = arch / "findings.json"
    fd.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")

    entries = [
        file_entry_for(vs, arch, kind="verify_summary", producer="reviewer-a"),
        file_entry_for(fd, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="adversarial-review-and-fix", files=entries)
    _, errs = load_and_validate_manifest(arch)
    assert any("stale-audit" in e for e in errs), errs


def test_validate_detects_readiness_not_latest(tmp_path):
    """T-FINAL writes the readiness doc LAST. A file mtime-AFTER readiness
    means a later edit was made outside the run boundary, breaking the audit
    story. Catch it."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)

    fd = arch / "findings.json"
    fd.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")
    time.sleep(1.05)
    # Touch a later file.
    later = arch / "late-edit.md"
    later.write_text("oops", encoding="utf-8")

    entries = [
        file_entry_for(fd, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
        file_entry_for(later, arch, kind="diff", producer="builder"),
    ]
    write_manifest(arch, run_id=rid, mission="doc-sync", files=entries)
    _, errs = load_and_validate_manifest(arch)
    assert any("readiness-not-latest" in e for e in errs), errs


def test_per_producer_ordering_isolation(tmp_path):
    """A blind_fix from reviewer-A and findings from reviewer-B should NOT
    trigger the ordering check, because the check is per-producer. Without
    this isolation, two reviewers working in parallel would falsely flag
    each other's files."""
    rid = allocate_run_id("adversarial-review-and-fix")
    arch = ensure_archive_dir(tmp_path, rid)

    # reviewer-B writes findings FIRST.
    fd_b = arch / "findings-b.json"
    fd_b.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    # reviewer-A writes blind_fix AFTER reviewer-B's findings — but that's
    # fine because they're different producers.
    bf_a = arch / "blind-fix-a.md"
    bf_a.write_text("blind", encoding="utf-8")
    time.sleep(1.05)
    fd_a = arch / "findings-a.json"
    fd_a.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")

    entries = [
        file_entry_for(fd_b, arch, kind="findings", producer="reviewer-b"),
        file_entry_for(bf_a, arch, kind="blind_fix", producer="reviewer-a"),
        file_entry_for(fd_a, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="adversarial-review-and-fix", files=entries)
    _, errs = load_and_validate_manifest(arch)
    # No ordering errors for reviewer-a's blind_fix-vs-findings-b cross-pair.
    # reviewer-a's own findings ARE after reviewer-a's blind_fix, so clean.
    assert not any("ANTI-ANCHORING" in e for e in errs), errs


def _ordering_payload(rid: str, mission: str, files: list[dict]) -> dict:
    """Minimal manifest payload for exercising _validate_ordering on exact
    mtime strings (no filesystem mutation, so we control sub-second values)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": mission,
        "created_utc": "2026-06-23T14:18:00Z",
        "files": files,
    }


def _ofile(path: str, kind: str, producer: str, mtime: str) -> dict:
    return {
        "path": path,
        "kind": kind,
        "sha256": "0" * 64,
        "mtime_utc": mtime,
        "producer": producer,
        "bytes": 0,
    }


def test_validate_same_second_blind_fix_and_findings_pass(tmp_path):
    """Finding 25: a blind_fix and its findings written in the SAME wall-clock
    second (identical mtime_utc) MUST validate. Pre-fix, _utc_from_mtime
    rounded to whole seconds and the strict comparison flagged this as an
    ANTI-ANCHORING / stale-audit false positive. The tie-break treats an exact
    tie as compliant; same-microsecond writes pass for all three invariants."""
    rid = allocate_run_id("adversarial-review-and-fix")
    same = "2026-06-23T14:18:33.412900Z"
    payload = _ordering_payload(
        rid,
        "adversarial-review-and-fix",
        [
            _ofile("blind-fix.md", "blind_fix", "reviewer-a", same),
            _ofile("findings.json", "findings", "reviewer-a", same),
            _ofile("verify-summary.json", "verify_summary", "reviewer-a", same),
            _ofile("readiness.md", "readiness", "t-final", same),
        ],
    )
    errs = validate_manifest_payload(payload, check_files_on_disk=False)
    assert errs == [], errs


def test_validate_created_utc_after_file_mtime_fails():
    """BUG-001 / ARCHIVE-01: created_utc later than any files[].mtime_utc MUST
    fail validation. Format-only checks previously let finalize-time stamps
    pass even when they post-dated accretion mtimes."""
    rid = allocate_run_id("doc-sync")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        # created_utc AFTER the only file mtime — clock-skew / finalize stamp.
        "created_utc": "2026-06-23T15:00:00Z",
        "files": [
            _ofile(
                "findings.json",
                "findings",
                "reviewer-a",
                "2026-06-23T14:18:33Z",
            ),
        ],
    }
    errs = validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("created_utc-precedes-files" in e for e in errs), errs
    assert any("findings.json" in e for e in errs), errs


def test_validate_created_utc_equal_to_file_mtime_passes():
    """Equality policy: created_utc <= min(mtime) — same-second run-start and
    first artifact write are compliant (not a strict <)."""
    rid = allocate_run_id("doc-sync")
    same = "2026-06-23T14:18:33Z"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": same,
        "files": [_ofile("findings.json", "findings", "reviewer-a", same)],
    }
    errs = validate_manifest_payload(payload, check_files_on_disk=False)
    assert errs == [], errs


def test_write_manifest_defaults_created_utc_to_run_id_timestamp(tmp_path):
    """BUG-001 / ARCHIVE-02: omitting created_utc must stamp run-start (from
    the run_id), not finalize/_utc_now, so created_utc precedes file mtimes."""
    fixed = datetime(2026, 6, 23, 14, 18, 0, tzinfo=timezone.utc)
    rid = allocate_run_id("doc-sync", now=fixed)
    arch = ensure_archive_dir(tmp_path, rid)
    entry = _make_entry(arch, "a.json", "findings", "reviewer-x")
    path = write_manifest(arch, run_id=rid, mission="doc-sync", files=[entry])
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["created_utc"] == "2026-06-23T14:18:00Z"
    created_dt = datetime.fromisoformat(payload["created_utc"].replace("Z", "+00:00"))
    mtime_dt = datetime.fromisoformat(
        payload["files"][0]["mtime_utc"].replace("Z", "+00:00")
    )
    assert mtime_dt >= created_dt
    _, errs = load_and_validate_manifest(arch)
    assert errs == [], errs


def test_validate_subsecond_ordering_still_catches_violation(tmp_path):
    """The tie-break only forgives an EXACT tie. A blind_fix one MICROSECOND
    strictly after its findings is still an ANTI-ANCHORING violation, and a
    verify_summary one microsecond strictly before findings is still stale —
    genuinely-out-of-order artifacts continue to fail at sub-second resolution."""
    rid = allocate_run_id("adversarial-review-and-fix")
    payload = _ordering_payload(
        rid,
        "adversarial-review-and-fix",
        [
            # blind_fix AFTER findings by 1 microsecond — violation.
            _ofile("blind-fix.md", "blind_fix", "reviewer-a", "2026-06-23T14:18:33.000002Z"),
            _ofile("findings.json", "findings", "reviewer-a", "2026-06-23T14:18:33.000001Z"),
            # verify_summary BEFORE findings by 1 microsecond — stale.
            _ofile("verify.json", "verify_summary", "reviewer-a", "2026-06-23T14:18:33.000000Z"),
            _ofile("readiness.md", "readiness", "t-final", "2026-06-23T14:18:40.000000Z"),
        ],
    )
    errs = validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("ANTI-ANCHORING" in e for e in errs), errs
    assert any("stale-audit" in e for e in errs), errs


def test_validate_detects_missing_manifest(tmp_path):
    """A directory with no manifest.json is an ARCHIVE_ENABLED violation.
    Pin the exact error text so operators see the doctrine name."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    payload, errs = load_and_validate_manifest(arch)
    assert payload is None
    assert any("ARCHIVE_ENABLED violation" in e for e in errs), errs


def test_validate_detects_sha256_mismatch(tmp_path):
    """Manifest says file X has hash H; on disk file X has different content.
    The verifier MUST catch this — corruption or tampering both manifest as
    sha256 drift."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    fd = arch / "findings.json"
    fd.write_text("original", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")
    entries = [
        file_entry_for(fd, arch, kind="findings", producer="reviewer-a"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="doc-sync", files=entries)
    # Tamper AFTER manifest is written.
    fd.write_text("tampered with different length so size check ALSO catches", encoding="utf-8")
    _, errs = load_and_validate_manifest(arch)
    # Size catches it cheaply BEFORE sha256 (per the lib's fail-fast comment).
    # Either size or sha256 mismatch is acceptable evidence that the tamper
    # was detected.
    assert any(("sha256 mismatch" in e or "size mismatch" in e) for e in errs), errs


def test_validate_detects_path_escape_in_manifest(tmp_path):
    """A handcrafted manifest that smuggles a `..` path must be rejected.
    file_entry_for catches this at write time; we ALSO validate at read time
    because a malicious or buggy producer could write the manifest directly
    bypassing file_entry_for."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    # Handcraft a malicious manifest.
    malicious = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {
                "path": "../escaped.txt",
                "kind": "other",
                "sha256": "0" * 64,
                "mtime_utc": "2026-06-23T14:18:33Z",
                "producer": "evil",
                "bytes": 0,
            }
        ],
    }
    (arch / "manifest.json").write_text(json.dumps(malicious), encoding="utf-8")
    _, errs = load_and_validate_manifest(arch)
    assert any("escapes archive directory" in e or "escapes archive root" in e for e in errs), errs


def test_validate_detects_invalid_kind_in_manifest(tmp_path):
    """A manifest with a typo'd kind must be rejected. Without this, the
    typo would silently bypass the mtime-ordering checks (those gate on
    valid kinds only)."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    fd = arch / "a.json"
    fd.write_text("{}", encoding="utf-8")
    bad = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {
                "path": "a.json",
                "kind": "findng",  # typo
                "sha256": "0" * 64,
                "mtime_utc": "2026-06-23T14:18:33Z",
                "producer": "x",
                "bytes": 2,
            }
        ],
    }
    (arch / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")
    _, errs = load_and_validate_manifest(arch)
    assert any("kind 'findng' not in" in e for e in errs), errs


def test_validate_detects_run_id_mission_mismatch_in_manifest(tmp_path):
    """A manifest whose mission field doesn't match its run_id slug is lying
    about which mission produced it. Catch it."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    fd = arch / "a.json"
    fd.write_text("{}", encoding="utf-8")
    bad = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "dependency-update",  # mismatch
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {
                "path": "a.json",
                "kind": "findings",
                "sha256": __import__("hashlib").sha256(b"{}").hexdigest(),
                "mtime_utc": "2026-06-23T14:18:33Z",
                "producer": "x",
                "bytes": 2,
            }
        ],
    }
    (arch / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")
    _, errs = load_and_validate_manifest(arch)
    assert any("does not match run_id slug" in e for e in errs), errs


def test_validate_detects_malformed_json(tmp_path):
    """A manifest.json that isn't valid JSON must be reported clearly, not
    raise. Operators get an actionable error, not a stacktrace."""
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    (arch / "manifest.json").write_text("{not json", encoding="utf-8")
    payload, errs = load_and_validate_manifest(arch)
    assert payload is None
    assert any("invalid JSON" in e for e in errs), errs


# ───────────────────────────────────────────────────────────────────────
# validate_run_archive.py CLI
# ───────────────────────────────────────────────────────────────────────


CLI = ROOT / "scripts" / "validate_run_archive.py"


def test_cli_exits_zero_when_no_archives_present(tmp_path):
    r = subprocess.run(
        [sys.executable, str(CLI), "--repo-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "No run-archives" in r.stdout


def _build_good_archive(tmp_path: Path) -> Path:
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    fd = arch / "findings.json"
    fd.write_text("{}", encoding="utf-8")
    time.sleep(1.05)
    rd = arch / "readiness.md"
    rd.write_text("# r", encoding="utf-8")
    entries = [
        file_entry_for(fd, arch, kind="findings", producer="rx"),
        file_entry_for(rd, arch, kind="readiness", producer="t-final"),
    ]
    write_manifest(arch, run_id=rid, mission="doc-sync", files=entries)
    return arch


def test_cli_exits_zero_for_clean_archive(tmp_path):
    arch = _build_good_archive(tmp_path)
    r = subprocess.run(
        [sys.executable, str(CLI), str(arch)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout


def test_cli_exits_one_for_broken_archive(tmp_path):
    arch = _build_good_archive(tmp_path)
    # Corrupt the findings file post-manifest.
    (arch / "findings.json").write_text("tampered", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(CLI), str(arch)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "FAIL" in r.stdout


def test_cli_no_checksums_flag_skips_hashing(tmp_path):
    """--no-checksums lets operators run a cheap pre-flight that still catches
    schema + ordering bugs. Pin: a tampered file passes --no-checksums but
    fails the full validator."""
    arch = _build_good_archive(tmp_path)
    (arch / "findings.json").write_text("tampered", encoding="utf-8")
    # --no-checksums passes (it skips the sha256 + size check).
    r_quick = subprocess.run(
        [sys.executable, str(CLI), "--no-checksums", str(arch)],
        capture_output=True,
        text=True,
    )
    assert r_quick.returncode == 0, r_quick.stdout + r_quick.stderr
    # Full validator catches it.
    r_full = subprocess.run(
        [sys.executable, str(CLI), str(arch)],
        capture_output=True,
        text=True,
    )
    assert r_full.returncode == 1


def test_cli_default_scan_picks_up_only_valid_run_id_dirs(tmp_path):
    """A non-run-id directory under .fleet/runs/ (operator scratch, README,
    etc.) MUST be ignored by the default scan. Without this, a stray dir
    would fail validation and block the build."""
    arch = _build_good_archive(tmp_path)
    # Operator drops a scratch dir under .fleet/runs/.
    scratch = arch.parent / "scratch-notes"
    scratch.mkdir()
    (scratch / "notes.md").write_text("just notes", encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(CLI), "--repo-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # Scratch dir does NOT appear in output.
    assert "scratch-notes" not in r.stdout


# ───────────────────────────────────────────────────────────────────────
# Direct payload validator tests (no filesystem mutation)
# ───────────────────────────────────────────────────────────────────────


def test_validate_payload_with_check_files_on_disk_false_skips_io(tmp_path):
    """When operators want to validate a manifest BEFORE the run produces its
    files (e.g. a dry-run preview), check_files_on_disk=False skips the I/O
    layer. Schema + ordering still apply. Pin so the cheap path stays cheap."""
    rid = allocate_run_id("doc-sync")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {
                "path": "findings.json",
                "kind": "findings",
                "sha256": "0" * 64,
                "mtime_utc": "2026-06-23T14:18:33Z",
                "producer": "rx",
                "bytes": 0,
            },
            {
                "path": "readiness.md",
                "kind": "readiness",
                "sha256": "0" * 64,
                "mtime_utc": "2026-06-23T14:18:34Z",
                "producer": "t-final",
                "bytes": 0,
            },
        ],
    }
    errs = validate_manifest_payload(
        payload, archive_root=tmp_path, check_files_on_disk=False
    )
    assert errs == [], errs


# ───────────────────────────────────────────────────────────────────────
# Integration: fleet-outcome validator's archive_enabled gate
# ───────────────────────────────────────────────────────────────────────


from lib.fleet_outcome import validate_outcome  # noqa: E402


_BASE_OUTCOME = {
    "mission": "doc-sync",
    "status": "done",
    "repo": "/r",
    "base_branch": "b",
    "prs_merged": 1,
    "reviewer_mode": "cross-vendor-structural",
    "metrics": {"drift_open": 0, "code_bug_findings": 0},
}


def test_fleet_outcome_validator_accepts_archive_enabled_true():
    """When archive_enabled=true accompanies status=done, the outcome
    validates."""
    assert validate_outcome({**_BASE_OUTCOME, "archive_enabled": True}) == []


def test_fleet_outcome_validator_rejects_archive_enabled_false_with_status_done():
    """The hard gate: a fleet-outcome with status=done and
    archive_enabled=false is rejected. This is the only cross-cutting
    discipline field that gates status=done from the validator (others
    are doc-prose enforced). Pin the rule and the error message."""
    errs = validate_outcome({**_BASE_OUTCOME, "archive_enabled": False})
    assert any("archive_enabled=false" in e for e in errs), errs
    # The error names the doctrine so operators know what to fix.
    assert any("ARCHIVE_ENABLED" in e for e in errs), errs


def test_fleet_outcome_validator_allows_archive_enabled_false_when_partial():
    """archive_enabled=false is only incompatible with status=done. With
    status=partial it's fine — the run is explicitly NOT claiming completion."""
    payload = {**_BASE_OUTCOME, "status": "partial", "archive_enabled": False}
    assert validate_outcome(payload) == []


def test_fleet_outcome_validator_accepts_omission():
    """Missions that produced no first-class artifacts OMIT the field
    entirely. Pin so non-applicable missions aren't forced to assert
    discipline they don't participate in."""
    payload = dict(_BASE_OUTCOME)
    assert "archive_enabled" not in payload
    assert validate_outcome(payload) == []


def test_fleet_outcome_validator_rejects_non_bool_archive_enabled():
    """Bool only. String 'true', int 1, etc. would silently coerce in some
    YAML parsers; reject so the semantic is unambiguous."""
    for bad in ["true", 1, 0, "yes", None]:
        errs = validate_outcome({**_BASE_OUTCOME, "archive_enabled": bad, "status": "partial"})
        assert any("archive_enabled" in e for e in errs), (bad, errs)


def test_fleet_outcome_validator_accepts_well_formed_run_id():
    rid = allocate_run_id("doc-sync")
    payload = {**_BASE_OUTCOME, "run_id": rid, "archive_enabled": True}
    assert validate_outcome(payload) == []


@pytest.mark.parametrize(
    "bad_rid",
    [
        "branch-name",                                # freeform
        "20260623T14-doc-sync-abc",                   # wrong timestamp shape
        "20260623T141833Z-Doc-Sync-abc123",           # uppercase mission
        "20260623T141833Z-doc-sync-toolong",          # 7-char suffix
        "20260623T141833Z-doc-sync-zzzzzz",           # non-hex suffix
    ],
)
def test_fleet_outcome_validator_rejects_malformed_run_id(bad_rid):
    payload = {**_BASE_OUTCOME, "run_id": bad_rid, "archive_enabled": True}
    errs = validate_outcome(payload)
    assert any("run_id" in e for e in errs), (bad_rid, errs)


# ───────────────────────────────────────────────────────────────────────
# Canonical example fixture (Commit A scaffolding)
# ───────────────────────────────────────────────────────────────────────


def test_example_fixture_archive_validates():
    """The .fleet/runs/example-fixture/ archive is the canonical input every
    validator in validate-all.sh exercises. It MUST validate end-to-end:

    1. The manifest validator accepts schema + on-disk integrity + every
       mtime-ordering invariant (blind_fix < findings, verify_summary >
       findings, readiness is latest).
    2. The Layer 1 source-verifier returns ``unverified_findings: 1`` (the
       fixture intentionally includes one simulated hallucination so the
       downgrade path is exercised) and ``verified_findings: 1`` (the
       real, greppable line in scripts/coupling-graph.py).

    A regression in any of those layers fails this test before the rest of
    the suite even runs. The generator is ``scripts/_build_example_fixture.py``
    — regenerate and recommit if the schemas change.
    """
    fixture_dir = ROOT / ".fleet" / "runs" / "example-fixture"
    assert fixture_dir.is_dir(), (
        "missing canonical fixture: regenerate with "
        "`python scripts/_build_example_fixture.py`"
    )

    # Manifest validator over the fixture.
    payload, errors = load_and_validate_manifest(fixture_dir)
    assert errors == [], errors
    assert payload is not None
    assert payload["mission"] == "adversarial-review-and-fix"

    # Cross-check validate_manifest_payload directly (smoke test of the
    # public lib API used by the validate_run_archive.py CLI).
    direct = validate_manifest_payload(
        payload, archive_root=fixture_dir, check_files_on_disk=True
    )
    assert direct == []

    # Layer 1 source-verifier over the fixture's findings doc.
    from lib.verify_findings import (  # noqa: E402
        load_findings_doc,
        verify_findings_doc,
    )

    doc = load_findings_doc(fixture_dir / "p0-review-findings.json")
    summary = verify_findings_doc(doc, ROOT)
    # The fixture has exactly two findings: one verified (real line in
    # scripts/coupling-graph.py) and one simulated hallucination.
    assert summary["total_findings"] == 2
    assert summary["verified_findings"] == 1
    assert summary["unverified_findings"] == 1
    assert summary["unverified_ids"] == ["F-002"]


# ── 5 MB archive cap (references/run-archive.md) ──────────────────────────
def _cap_manifest(nbytes: int) -> dict:
    return {
        "schema_version": "1.0",
        "run_id": "20260101T000000Z-doc-sync-abc123",
        "mission": "doc-sync",
        "created_utc": "2026-01-01T00:00:00Z",
        "files": [
            {
                "path": "p0-review-findings.json",
                "kind": "findings",
                "sha256": "a" * 64,
                "mtime_utc": "2026-01-01T00:00:01Z",
                "producer": "p0-reviewer",
                "bytes": nbytes,
            }
        ],
    }


def test_size_cap_allows_under_5mb():
    errs = validate_manifest_payload(_cap_manifest(1000), check_files_on_disk=False)
    assert not any("cap" in e for e in errs)


def test_size_cap_rejects_over_5mb():
    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1), check_files_on_disk=False
    )
    assert any("cap" in e for e in errs)


def test_size_cap_over_with_root_no_lfs(tmp_path):
    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1),
        archive_root=tmp_path,
        check_files_on_disk=False,
    )
    assert any("cap" in e for e in errs)


def test_size_cap_lfs_escape(tmp_path):
    # The LFS rule that tracks the oversized file exempts the archive; the
    # comment / blank / non-lfs lines exercise the .gitattributes parser.
    (tmp_path / ".gitattributes").write_text(
        "# lfs config\n\n*.txt text\np0-review-findings.json filter=lfs diff=lfs\n"
    )
    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1),
        archive_root=tmp_path,
        check_files_on_disk=False,
    )
    assert not any("cap" in e for e in errs)


def test_size_cap_unrelated_lfs_pattern_still_fails(tmp_path):
    # An LFS rule that does NOT match the oversized file must not exempt it.
    (tmp_path / ".gitattributes").write_text("*.response filter=lfs\n")
    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1),
        archive_root=tmp_path,
        check_files_on_disk=False,
    )
    assert any("cap" in e for e in errs)


def test_size_cap_gitattributes_unreadable(tmp_path):
    (tmp_path / ".gitattributes").mkdir()  # read_text -> IsADirectoryError (OSError)
    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1),
        archive_root=tmp_path,
        check_files_on_disk=False,
    )
    assert any("cap" in e for e in errs)


def test_over_cap_manifest_skips_on_disk_hash_and_size_walk(tmp_path, monkeypatch):
    """Once the manifest declares too many non-LFS bytes, validation must stop
    before touching attacker-controlled archive files. A wrong on-disk file
    proves the disk walk did not add size or sha errors after the cap failure."""
    (tmp_path / "p0-review-findings.json").write_text("wrong content", encoding="utf-8")

    def fail_if_hashed(path: Path) -> str:
        raise AssertionError(f"unexpected hash of {path}")

    monkeypatch.setattr(fleet_run, "_sha256_file", fail_if_hashed)

    errs = validate_manifest_payload(
        _cap_manifest(MAX_ARCHIVE_BYTES + 1),
        archive_root=tmp_path,
        check_files_on_disk=True,
    )

    assert any("exceed the" in e and "byte cap" in e for e in errs), errs
    assert not any("size mismatch" in e or "sha256 mismatch" in e for e in errs), errs


def test_manifest_entry_with_bool_bytes_refuses_to_hash_unsized_file(tmp_path, monkeypatch):
    """A bool is an int subclass in Python; the disk validator must still reject
    it before size comparison/hashing, or a one-byte hostile file can be hashed
    despite lacking a trustworthy integer byte count."""
    (tmp_path / "p0-review-findings.json").write_text("x", encoding="utf-8")

    def fail_if_hashed(path: Path) -> str:
        raise AssertionError(f"unexpected hash of {path}")

    monkeypatch.setattr(fleet_run, "_sha256_file", fail_if_hashed)
    manifest = _cap_manifest(1)
    manifest["files"][0]["bytes"] = True

    errs = validate_manifest_payload(
        manifest,
        archive_root=tmp_path,
        check_files_on_disk=True,
    )

    assert any("bytes must be a non-negative int" in e for e in errs), errs
    assert any("missing or non-integer 'bytes'; refusing to hash" in e for e in errs), errs
    assert not any("sha256 mismatch" in e for e in errs), errs



def test_worker_lifeline_and_synthetic_lifecycle_trace_preserve_causal_edges():
    """The dry-run trace helpers emit externally visible primitive ordering:
    COMMIT must point at the worker spawn, and the optional T-FINAL event must
    be present only when the caller asks the helper to emit it."""

    class FakeEmitter:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str, dict]] = []

        def emit(self, primitive: str, role: str, status: str, **kwargs) -> str:
            self.calls.append((primitive, role, status, kwargs))
            return f"event-{len(self.calls)}"

    emitter = FakeEmitter()
    spawn_id, commit_id = fleet_run.emit_worker_commit_lifeline(
        emitter, task_id="task-1", worker_role="FIXER"
    )

    assert (spawn_id, commit_id) == ("event-1", "event-2")
    assert emitter.calls[1] == (
        "COMMIT",
        "FIXER",
        "succeeded",
        {"task_id": "task-1", "parent_event": spawn_id},
    )

    ids = fleet_run.emit_dryrun_lifecycle_trace(
        emitter,
        mission="doc-sync",
        task_id="task-2",
        runtime="codex",
        include_t_final=True,
        manifest_name="manifest.json",
        file_count=3,
        abort_status="blocked",
    )

    assert ids["dispatch"] == "event-3"
    assert ids["t_final"] == "event-13"
    assert emitter.calls[-1] == (
        "T-FINAL",
        "INTEGRATOR",
        "succeeded",
        {"details": {"manifest": "manifest.json", "files": 3}},
    )


def test_progress_parsing_and_headless_archive_capture_runtime_response(tmp_path):
    """A headless dry-run archive is the public audit artifact for a runtime
    probe: progress text drives trace statuses, JSON runtime output is archived,
    and the manifest validates after T-FINAL refreshes the trace checksum."""
    from lib.mission_registry import progress_path as mission_progress_path

    source = tmp_path / "source"
    progress = source / mission_progress_path("doc-sync")
    progress.parent.mkdir(parents=True, exist_ok=True)
    progress.write_text(
        "TASK task-9\nPHASE: DONE\nREVIEWED=t\nMERGED=f\nMISSION: doc-sync\n"
        + ("x" * 3000),
        encoding="utf-8",
    )
    runtime_response = tmp_path / "response.out"
    runtime_response.write_text('{"ok": true}\n', encoding="utf-8")

    assert fleet_run.progress_text_for_mission(source, "doc-sync").startswith("TASK task-9")
    assert len(fleet_run.progress_excerpt_for_mission(source, "doc-sync")) == 2500
    fallback = fleet_run.progress_text_for_mission(source, "unknown-mission")
    assert "MISSION: unknown-mission" in fallback

    plan = fleet_run.plan_dryrun_trace_from_progress(
        progress.read_text(encoding="utf-8"), mission="doc-sync", runtime="grok"
    )
    assert plan.task_id == "task-9"
    assert plan.inspect_status == "succeeded"
    assert plan.merge_status == "started"
    assert plan.goal_blocked_status == "skipped"
    assert "MISSION:doc-sync" in plan.note

    arch, run_id, primitives = fleet_run.write_headless_dryrun_archive(
        tmp_path,
        mission="doc-sync",
        runtime="grok",
        progress_source_root=source,
        runtime_response_path=runtime_response,
    )

    assert parse_run_id(run_id)[1] == "doc-sync"
    assert "T-FINAL" in primitives
    assert (arch / "headless-runtime-response.json").is_file()
    payload, errs = load_and_validate_manifest(arch)
    assert errs == [], errs
    assert payload is not None
    assert payload["coordinator"] == "headless-dryrun-grok"
    assert payload["base_branch"] == "main"
    assert "Runtime capture: headless-runtime-response.json." in payload["notes"]
    assert any(entry["path"] == "headless-runtime-response.json" for entry in payload["files"])
    # ARCHIVE-02: created_utc is run-start (run_id timestamp), not finalize.
    run_ts, _, _ = parse_run_id(run_id)
    assert payload["created_utc"] == run_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    created_dt = datetime.fromisoformat(
        payload["created_utc"].replace("Z", "+00:00")
    )
    for entry in payload["files"]:
        mtime_dt = datetime.fromisoformat(
            entry["mtime_utc"].replace("Z", "+00:00")
        )
        assert mtime_dt >= created_dt, (
            f"{entry['path']}: mtime {entry['mtime_utc']} < created_utc "
            f"{payload['created_utc']}"
        )

    empty_response = tmp_path / "empty-response.out"
    empty_response.write_text("", encoding="utf-8")
    alias_arch, _alias_run_id, alias_primitives = fleet_run.record_headless_run(
        tmp_path / "alias",
        mission="doc-sync",
        runtime="codex",
        progress_source_root=tmp_path / "missing-source",
        runtime_response_path=empty_response,
    )
    assert alias_arch.is_dir()
    assert "T-FINAL" in alias_primitives
    assert not (alias_arch / "headless-runtime-response.txt").exists()


def test_runtime_response_archive_name_uses_first_byte_without_parsing(tmp_path):
    json_response = tmp_path / "json.out"
    json_response.write_text("[1]\n", encoding="utf-8")
    text_response = tmp_path / "text.out"
    text_response.write_text("\n{\"json_after_newline\": true}\n", encoding="utf-8")
    empty_response = tmp_path / "empty.out"
    empty_response.write_text("", encoding="utf-8")

    class StatRaises:
        def is_file(self) -> bool:
            return True

        def stat(self):
            raise OSError("stat failed")

    class OpenRaises:
        def open(self, mode: str):
            raise OSError("open failed")

    assert fleet_run._runtime_response_has_content(json_response) is True
    assert fleet_run._runtime_response_has_content(empty_response) is False
    assert fleet_run._runtime_response_has_content(StatRaises()) is False
    assert fleet_run._runtime_response_archive_name(json_response) == "headless-runtime-response.json"
    assert fleet_run._runtime_response_archive_name(text_response) == "headless-runtime-response.txt"
    assert fleet_run._runtime_response_archive_name(empty_response) == "headless-runtime-response.txt"
    assert fleet_run._runtime_response_archive_name(OpenRaises()) == "headless-runtime-response.txt"


def test_manifest_writer_and_payload_shape_surface_actionable_errors(tmp_path):
    rid = allocate_run_id("doc-sync")
    arch = ensure_archive_dir(tmp_path, rid)
    artifact = arch / "a.txt"
    artifact.write_text("x", encoding="utf-8")
    entry = file_entry_for(artifact, arch, kind="other", producer="writer")

    with pytest.raises(ValueError, match="invalid run_id"):
        write_manifest(arch, run_id="not-a-run-id", mission="doc-sync", files=[entry])

    assert validate_manifest_payload(["not", "a", "manifest"]) == [
        "manifest: manifest must be an object"
    ]

    bad = {
        "schema_version": "9.9",
        "run_id": "bad-run-id",
        "mission": "doc-sync",
        "created_utc": "not-a-date",
        "files": [
            "not-a-dict",
            {
                "path": "",
                "kind": "other",
                "sha256": "0" * 64,
                "mtime_utc": "2026-01-01T00:00:00Z",
                "producer": "writer",
                "bytes": 0,
            },
            {
                "path": "bad-metadata.txt",
                "kind": "other",
                "sha256": "0" * 64,
                "mtime_utc": "not-a-date",
                "producer": "writer",
            },
            {
                "path": "missing.txt",
                "kind": "other",
                "sha256": "0" * 64,
                "mtime_utc": "2026-99-99T00:00:00Z",
                "producer": " ",
                "bytes": 1,
            },
        ],
    }

    errs = validate_manifest_payload(bad, archive_root=arch)

    assert any("schema_version must be" in e for e in errs), errs
    assert any("run_id 'bad-run-id' does not match" in e for e in errs), errs
    assert any("created_utc 'not-a-date' not a valid" in e for e in errs), errs
    assert any("manifest.files[0]: must be an object" in e for e in errs), errs
    assert any("manifest.files[2]: missing field 'bytes'" in e for e in errs), errs
    assert any("manifest.files[2]: mtime_utc not a valid" in e for e in errs), errs
    assert any("producer must be a non-empty string" in e for e in errs), errs
    assert any("file not found" in e and "missing.txt" in e for e in errs), errs

# --- independence invariant (issue #77) ------------------------------------

_IDENTICAL_SHA = "5de7255673c5b84e48e1f2900e213edeaec8cc16f4c556ec60107cec926c3306"
_OTHER_SHA = "a" * 64


def _findings_entry(path: str, producer: str, sha: str) -> dict:
    return {
        "path": path,
        "kind": "findings",
        "sha256": sha,
        "mtime_utc": "2026-06-26T20:05:00Z",
        "producer": producer,
        "bytes": 10,
    }


def test_independence_rejects_identical_findings_from_different_producers():
    """Issue #77: the 8358f1 fixture shipped reviewer + skeptic findings with
    one sha256 and validation passed. Cross-producer identical findings must
    now fail."""
    errs = validate_manifest_payload(
        {
            "files": [
                _findings_entry("p0-review-findings.json", "p0-reviewer-grok", _IDENTICAL_SHA),
                _findings_entry("p0-skeptic-findings.json", "p0-skeptic-grok", _IDENTICAL_SHA),
            ]
        }
    )
    assert any("independent-review violation" in e for e in errs), errs


def test_independence_allows_distinct_findings_from_different_producers():
    errs = validate_manifest_payload(
        {
            "files": [
                _findings_entry("p0-review-findings.json", "p0-reviewer-grok", _IDENTICAL_SHA),
                _findings_entry("p0-skeptic-findings.json", "p0-skeptic-grok", _OTHER_SHA),
            ]
        }
    )
    assert not any("independent-review" in e for e in errs), errs


def test_independence_ignores_same_producer_duplicates():
    """A producer archiving its own findings under two names is not an
    independence violation (other checks own that); only cross-producer
    identity is."""
    errs = validate_manifest_payload(
        {
            "files": [
                _findings_entry("p0-review-findings.json", "p0-reviewer-grok", _IDENTICAL_SHA),
                _findings_entry("p0-review-findings-copy.json", "p0-reviewer-grok", _IDENTICAL_SHA),
            ]
        }
    )
    assert not any("independent-review" in e for e in errs), errs


def test_independence_skips_non_findings_and_malformed_sha():
    errs = validate_manifest_payload(
        {
            "files": [
                _findings_entry("a.json", "reviewer", _IDENTICAL_SHA),
                {**_findings_entry("b.json", "skeptic", _IDENTICAL_SHA), "kind": "other"},
                {**_findings_entry("c.json", "third", "not-a-sha"), "sha256": "not-a-sha"},
                "not-a-dict",
            ]
        }
    )
    assert not any("independent-review" in e for e in errs), errs
