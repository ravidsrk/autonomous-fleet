"""Registry-lint rules (issue #90: version-literal guard)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_version_literal_lint_flags_and_exempts(tmp_path) -> None:
    """Issue #90: skill-version literals in tests fail; schema_version is a
    pinned contract and exempt."""
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    import json as _json
    import shutil as _shutil

    tests = tmp_path / "tests"
    tests.mkdir()
    _shutil.copy2(ROOT / "skills-lock.json", tmp_path / "skills-lock.json")
    lock = _json.loads((tmp_path / "skills-lock.json").read_text(encoding="utf-8"))
    a_current = next(iter(lock["skills"].values()))["version"]
    (tests / "test_bad.py").write_text(
        f'assert v == \'version: "{a_current}"\'\n', encoding="utf-8"
    )
    (tests / "test_ok.py").write_text(
        'assert \'schema_version: "1.0"\' in trace\n'
        'fixture = \'version: "0.0.1"\'\n', encoding="utf-8"
    )
    errors = lint_no_skill_version_literals_in_tests(tmp_path)
    assert len(errors) == 1
    assert "test_bad.py:1" in errors[0]
    assert lint_no_skill_version_literals_in_tests(tmp_path / "nope") == []


def test_real_repo_has_no_version_literals_in_tests() -> None:
    from pathlib import Path
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    assert lint_no_skill_version_literals_in_tests(Path(__file__).resolve().parents[1]) == []


def test_version_literal_lint_skips_on_lock_errors(tmp_path) -> None:
    """Lock problems are lint_skills_lock's job — this rule stays quiet."""
    from lib.registry_lint import lint_no_skill_version_literals_in_tests

    (tmp_path / "tests").mkdir()
    (tmp_path / "skills-lock.json").write_text("{not json", encoding="utf-8")
    assert lint_no_skill_version_literals_in_tests(tmp_path) == []


def test_mission_state_lint_clean_on_repo_and_catches_unmarked(tmp_path) -> None:
    """Issue #92: routing docs presenting an exploratory mission without a
    marker fail; the real repo is clean."""
    import shutil
    from lib.registry_lint import lint_mission_state_docs

    assert lint_mission_state_docs(ROOT) == []

    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copytree(ROOT / "scripts" / "lib", repo / "scripts" / "lib")
    doc = repo / "skills" / "autonomous-fleet" / "references"
    doc.mkdir(parents=True)
    (doc / "missions.md").write_text(
        "# catalog\n\n| intent | mission |\n|---|---|\n| find bugs | `bug-batch` |\n",
        encoding="utf-8",
    )
    errors = lint_mission_state_docs(repo)
    assert any("bug-batch" in e and "missions.md:5" in e for e in errors)
    # shipped-mission catalog check also fires on this minimal repo
    assert any("shipped mission" in e for e in errors)


def test_adapter_contract_single_source_lint(tmp_path) -> None:
    """Issue #89: adapters must point at adapter-contract.md; a re-inlined
    canonical span fails."""
    import shutil
    from lib.registry_lint import lint_adapter_contract_single_source

    assert lint_adapter_contract_single_source(ROOT) == []

    repo = tmp_path / "repo"
    canon_src = ROOT / "skills/autonomous-fleet-core/references/adapter-contract.md"
    canon_dst = repo / "skills/autonomous-fleet-core/references/adapter-contract.md"
    canon_dst.parent.mkdir(parents=True)
    shutil.copy2(canon_src, canon_dst)
    bad = repo / "skills/autonomous-fleet-adapter-demo"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text(canon_src.read_text(encoding="utf-8"), encoding="utf-8")
    errors = lint_adapter_contract_single_source(repo)
    assert any("re-inlines" in e for e in errors)
    nobind = repo / "skills/autonomous-fleet-adapter-nobind"
    nobind.mkdir(parents=True)
    (nobind / "SKILL.md").write_text("see references/adapter-contract.md\n", encoding="utf-8")
    errors = lint_adapter_contract_single_source(repo)
    assert any("CONTINUE_WORKER binding" in e and "nobind" in e for e in errors)

    good = repo / "skills/autonomous-fleet-adapter-good"
    good.mkdir(parents=True)
    (good / "SKILL.md").write_text(
        "see references/adapter-contract.md\nCONTINUE_WORKER binding: none -> ALIAS\n",
        encoding="utf-8",
    )
    errors = lint_adapter_contract_single_source(repo)
    assert not any("adapter-good" in e for e in errors)
    canon_dst.unlink()
    assert lint_adapter_contract_single_source(repo) == [
        "skills/autonomous-fleet-core/references/adapter-contract.md: missing canonical adapter contract"
    ]
