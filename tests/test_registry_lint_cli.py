"""Tests for the registry-lint CLI wrapper and the missing-dir lint path.

The lib functions are exercised by tests/test_fleet_registry_consistency.py; this
file covers ``scripts/registry_lint.py`` (the thin CLI) in-process so the
repository-wide 100% coverage gate sees the wrapper, plus the
``lint_shipped_mission_dirs`` missing-dir branch with a synthetic registry.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import registry_lint as rl  # noqa: E402


def _run_cli(*argv: str, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    spec = importlib.util.spec_from_file_location(
        "registry_lint_cli", REPO_ROOT / "scripts" / "registry_lint.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out, err = io.StringIO(), io.StringIO()
    old_argv, old_env = sys.argv, os.environ.copy()
    sys.argv = ["registry_lint.py", *argv]
    if env:
        os.environ.update(env)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            rc = mod.main()
    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_env)
    return rc, out.getvalue(), err.getvalue()


def test_cli_passes_on_real_repo():
    rc, _, err = _run_cli(str(REPO_ROOT))
    assert rc == 0, err


def test_cli_kill_switch_disables():
    rc, _, err = _run_cli(str(REPO_ROOT), env={"FLEET_DISABLE_REGISTRY_LINT": "1"})
    assert rc == 0
    assert "DISABLED" in err and "FLEET_DISABLE_REGISTRY_LINT" in err


def test_cli_fails_and_reports_on_empty_root(tmp_path: Path):
    # No skills/ dir at all -> every shipped mission's dir is missing -> exit 1.
    rc, _, err = _run_cli(str(tmp_path))
    assert rc == 1
    assert "registry-lint:" in err


def test_missing_shipped_dir_is_flagged(tmp_path: Path):
    # Synthetic registry: a shipped mission whose skill dir does not exist.
    missions = {"ghost": {"shipped": True, "skill_dir": "ghost-mission-xyz"}}
    errors = rl.lint_shipped_mission_dirs(tmp_path, missions)
    assert any("ghost" in e and "ghost-mission-xyz" in e for e in errors)


def test_external_source_skill_on_disk_is_not_drift(tmp_path: Path):
    # CI vendors an external skill (skill-creator from anthropics/skills) into
    # skills/; it is on disk and in the lock with a non-local source. That must
    # NOT register as drift (this is the exact case that failed CI on the first push).
    creator = tmp_path / "skills" / "skill-creator"
    creator.mkdir(parents=True)
    (creator / "SKILL.md").write_text("---\nname: skill-creator\n---\n")
    lock = {
        "version": 1,
        "skills": {
            "skill-creator": {"source": "anthropics/skills", "sourceType": "github"}
        },
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock))
    errors = rl.lint_skills_lock(tmp_path)
    assert not any("skill-creator" in e for e in errors), errors


# --- lockfile content-hash integrity (finding 58) ---------------------------


def _make_skill(root: Path, name: str, body: str = "hello\n") -> Path:
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n{body}", encoding="utf-8")
    (skill_dir / "extra.txt").write_text("aux\n", encoding="utf-8")
    return skill_dir


def test_content_hash_is_deterministic_and_path_sensitive(tmp_path: Path):
    a = _make_skill(tmp_path, "alpha")
    first = rl.content_hash(a)
    assert first == rl.content_hash(a)
    assert len(first) == 64
    # Renaming a file changes the digest even when bytes are identical.
    (a / "extra.txt").rename(a / "renamed.txt")
    assert rl.content_hash(a) != first
    # Changing content changes the digest.
    (a / "renamed.txt").write_text("different\n", encoding="utf-8")
    assert rl.content_hash(a) != first


def test_real_repo_lock_hashes_are_verified():
    # Self-consistency: the committed lock's computedHash values must match the
    # content hashes recomputed from the shipped skill dirs on disk.
    assert rl.lint_lock_hashes(REPO_ROOT) == []
    assert rl.lint_external_source_pins(REPO_ROOT) == []


def test_lock_hash_mismatch_is_flagged(tmp_path: Path):
    skill = _make_skill(tmp_path, "doc-sync")
    good = rl.content_hash(skill)
    lock = {
        "version": 1,
        "skills": {
            "doc-sync": {"source": rl.LOCAL_LOCK_SOURCE, "computedHash": good},
        },
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    assert rl.lint_lock_hashes(tmp_path) == []

    # Mutate the body so the on-disk hash drifts from the locked value.
    (skill / "SKILL.md").write_text("---\nname: doc-sync\n---\nMUTATED\n", encoding="utf-8")
    errors = rl.lint_lock_hashes(tmp_path)
    assert len(errors) == 1
    assert "doc-sync computedHash mismatch" in errors[0]


def test_lock_hash_skips_non_verifiable_rows(tmp_path: Path):
    # A bare-string row, an external row, and a local row without computedHash
    # are all skipped by the hash verifier (no false positives).
    creator = tmp_path / "skills" / "skill-creator"
    creator.mkdir(parents=True)
    (creator / "SKILL.md").write_text("---\nname: skill-creator\n---\n", encoding="utf-8")
    lock = {
        "version": 1,
        "skills": {
            "bare": "local-row",
            "skill-creator": {
                "source": "anthropics/skills",
                "computedHash": "0" * 64,
            },
            "no-hash": {"source": rl.LOCAL_LOCK_SOURCE},
        },
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    assert rl.lint_lock_hashes(tmp_path) == []


def test_lock_hash_local_row_with_hash_but_missing_dir_is_flagged(tmp_path: Path):
    lock = {
        "version": 1,
        "skills": {
            "ghost": {"source": rl.LOCAL_LOCK_SOURCE, "computedHash": "0" * 64},
        },
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    errors = rl.lint_lock_hashes(tmp_path)
    assert errors == [
        "skills-lock.json: ghost has computedHash but no skills/ghost/ on disk"
    ]


def test_lock_hash_propagates_load_errors(tmp_path: Path):
    # No lock file at all -> the shared loader's error surfaces unchanged.
    assert rl.lint_lock_hashes(tmp_path) == ["skills-lock.json: missing"]


# --- external-source pinning (finding 58) -----------------------------------


def test_unpinned_external_source_is_flagged(tmp_path: Path):
    lock = {
        "version": 1,
        "skills": {
            "local": {"source": rl.LOCAL_LOCK_SOURCE},
            "bare": "local-row",
            "skill-creator": {"source": "anthropics/skills", "sourceType": "github"},
        },
    }
    (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    errors = rl.lint_external_source_pins(tmp_path)
    assert len(errors) == 1
    assert "external source 'anthropics/skills' for skill-creator is not pinned" in errors[0]


def test_pinned_external_source_passes(tmp_path: Path):
    for field in ("ref", "commit", "tag", "sha"):
        lock = {
            "version": 1,
            "skills": {
                "skill-creator": {"source": "anthropics/skills", field: "abc123"},
            },
        }
        (tmp_path / "skills-lock.json").write_text(json.dumps(lock), encoding="utf-8")
        assert rl.lint_external_source_pins(tmp_path) == [], field


def test_external_pins_propagates_load_errors(tmp_path: Path):
    assert rl.lint_external_source_pins(tmp_path) == ["skills-lock.json: missing"]
