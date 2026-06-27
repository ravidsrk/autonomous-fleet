"""Tests for adapter requires-block preflight checks."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.adapter_preflight import Intent, check, load_requires  # noqa: E402


def _which_factory(found: set[str]):
    def which(binary: str) -> str | None:
        return f"/usr/bin/{binary}" if binary in found else None

    return which


def _runner(returncode: int, calls: list[list[str]]):
    def run(args: list[str], **kwargs):
        calls.append(args)
        assert kwargs == {"capture_output": True, "text": True, "check": False}
        return SimpleNamespace(returncode=returncode)

    return run


def test_wiring_only_skips_all_checks() -> None:
    failures = check(
        {
            "bins": ["definitely-not-a-real-bin-xyz"],
            "env": ["NEEDED_TOKEN"],
            "auth": [{"check": "gh auth status"}],
        },
        Intent(wiring_only=True),
        which=_which_factory(set()),
        environ={},
    )
    assert failures == []


def test_missing_bin_failure_names_binary() -> None:
    failures = check(
        {"bins": ["definitely-not-a-real-bin-xyz"], "env": [], "auth": []},
        Intent(),
        which=_which_factory(set()),
    )

    assert failures == ["missing required binary: definitely-not-a-real-bin-xyz"]


def test_auth_gated_on_scm_is_skipped_for_no_scm_intent() -> None:
    calls: list[list[str]] = []
    failures = check(
        {
            "bins": ["git", "gh"],
            "env": [],
            "auth": [{"check": "gh auth status", "skip_if_intent": "no_scm"}],
        },
        {"scm": False},
        which=_which_factory({"git"}),
        run=_runner(1, calls),
    )

    assert failures == []
    assert calls == []


def test_auth_gated_on_scm_runs_and_fails_with_scm_intent() -> None:
    calls: list[list[str]] = []
    failures = check(
        {
            "bins": ["git", "gh"],
            "env": [],
            "auth": [{"check": "gh auth status", "skip_if_intent": "no_scm"}],
        },
        {"scm": True},
        which=_which_factory({"git", "gh"}),
        run=_runner(1, calls),
    )

    assert failures == ["auth check failed (1): gh auth status"]
    assert calls == [["gh", "auth", "status"]]


def test_failures_are_aggregated_for_bins_env_and_auth() -> None:
    calls: list[list[str]] = []
    failures = check(
        {
            "bins": ["git", "missing-one"],
            "env": ["NEEDED_TOKEN"],
            "auth": [{"check": "gh auth status"}],
        },
        Intent(scm=True),
        which=_which_factory({"git"}),
        run=_runner(2, calls),
        environ={},
    )

    assert failures == [
        "missing required binary: missing-one",
        "missing required env var: NEEDED_TOKEN",
        "auth check failed (2): gh auth status",
    ]
    assert calls == [["gh", "auth", "status"]]


def test_scalar_auth_entry_reports_failure_without_raising() -> None:
    calls: list[list[str]] = []
    failures = check(
        {"bins": [], "env": [], "auth": ["gh auth status"]},
        Intent(scm=True),
        which=_which_factory(set()),
        run=_runner(0, calls),
    )

    assert failures == ["malformed auth entry (expected mapping): 'gh auth status'"]
    assert calls == []


def test_auth_entry_missing_check_key_reports_failure() -> None:
    calls: list[list[str]] = []
    failures = check(
        {"bins": [], "env": [], "auth": [{"skip_if_intent": "no_scm"}]},
        Intent(scm=True),
        which=_which_factory(set()),
        run=_runner(0, calls),
    )

    assert failures == [
        "malformed auth entry (missing 'check'): {'skip_if_intent': 'no_scm'}"
    ]
    assert calls == []


def test_auth_entry_with_empty_check_reports_failure() -> None:
    calls: list[list[str]] = []
    failures = check(
        {"bins": [], "env": [], "auth": [{"check": ""}]},
        Intent(scm=True),
        which=_which_factory(set()),
        run=_runner(0, calls),
    )

    assert failures == ["malformed auth entry (missing 'check'): {'check': ''}"]
    assert calls == []


def test_load_requires_reads_fenced_yaml_requires_block(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "SKILL.md").write_text(
        """# Adapter

## PRECONDITIONS

```yaml requires
bins: [git, gh]
env: [TOKEN]
auth:
  - check: "gh auth status"
    skip_if_intent: "no_scm"
intent_gated:
  scm: "willClaimExistingPR"
```
""",
        encoding="utf-8",
    )

    assert load_requires(adapter) == {
        "bins": ["git", "gh"],
        "env": ["TOKEN"],
        "auth": [{"check": "gh auth status", "skip_if_intent": "no_scm"}],
        "intent_gated": {"scm": "willClaimExistingPR"},
    }


def test_load_requires_rejects_missing_block(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "SKILL.md").write_text("# Adapter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing fenced yaml requires-block"):
        load_requires(adapter)


def test_load_requires_rejects_non_mapping_block(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "SKILL.md").write_text(
        "```yaml requires\n- git\n```\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a YAML mapping"):
        load_requires(adapter)
