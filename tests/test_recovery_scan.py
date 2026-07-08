"""Tests for the hermetic resume-time recovery scanner."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from lib import recovery_scan as rs  # noqa: E402


def _prs(*items: dict[str, object]) -> str:
    return json.dumps(list(items))


def _wt(branch: str, path: str = "/tmp/wt", extra: str = "") -> str:
    suffix = f"\n{extra.strip()}" if extra.strip() else ""
    return f"worktree {path}\nHEAD {'1' * 40}\nbranch refs/heads/{branch}{suffix}\n"


def _first(report: dict[str, object]) -> dict[str, object]:
    return report["rows"][0]  # type: ignore[index,return-value]


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "recovery_scan_cli",
        REPO_ROOT / "scripts" / "recovery_scan.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "render_dashboard_for_recovery_scan_coverage",
        REPO_ROOT / "scripts" / "render-dashboard.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> tuple[int, str, str]:
    cli = _load_cli()
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "argv", ["recovery_scan.py", *argv])
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main()
    return rc, out.getvalue(), err.getvalue()


def test_acceptance_merged_row_absent_worktree_pr_merged_is_dead_cleanup() -> None:
    ledger = "TASK T1 | BRANCH=fleet/done PR=12 WT=/tmp/done MERGED=true WT_CLEAN=false\n"
    worktrees = _wt("main", "/repo")
    prs = _prs(
        {
            "number": 12,
            "headRefName": "fleet/done",
            "state": "MERGED",
            "mergedAt": "2026-06-24T00:00:00Z",
        }
    )

    row = _first(rs.scan_recovery(ledger, worktrees, prs))

    assert row["classification"] == rs.CLASS_DEAD
    assert row["action"] == rs.ACTION_CLEANUP_WORKTREE
    assert row["signals"] == {
        "ledger_flag": "merged",
        "worktree_present": False,
        "scm_state": rs.SCM_MERGED,
    }


def test_acceptance_ledger_false_pr_merged_is_partial_escalate() -> None:
    ledger = "TASK T2 | BRANCH=fleet/disagree PR=13 MERGED=false WT=/tmp/disagree\n"
    prs = _prs(
        {
            "number": 13,
            "headRefName": "fleet/disagree",
            "state": "MERGED",
            "mergedAt": "2026-06-24T00:00:00Z",
        }
    )

    row = _first(rs.scan_recovery(ledger, _wt("fleet/disagree", "/tmp/disagree"), prs))

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["action"] == rs.ACTION_ESCALATE
    assert row["signals"]["scm_state"] == rs.SCM_MERGED  # type: ignore[index]


def test_acceptance_worktree_with_no_ledger_row_is_orphan() -> None:
    report = rs.scan_recovery("", _wt("fleet/orphan"), "[]")

    row = _first(report)
    assert row["kind"] == "orphan"
    assert row["classification"] == rs.CLASS_ORPHAN
    assert row["action"] == rs.ACTION_ESCALATE
    assert report["summary"] == {"live": 0, "dead": 0, "partial": 0, "orphan": 1}


def test_acceptance_orphan_pr_merged_and_clean_archives() -> None:
    prs = _prs(
        {
            "number": 14,
            "headRefName": "fleet/orphan",
            "state": "MERGED",
            "mergedAt": "2026-06-24T00:00:00Z",
        }
    )

    row = _first(rs.scan_recovery("", _wt("fleet/orphan"), prs))

    assert row["classification"] == rs.CLASS_ORPHAN
    assert row["action"] == rs.ACTION_ARCHIVE_ORPHAN
    assert row["signals"]["uncommitted_changes"] is False  # type: ignore[index]


@pytest.mark.parametrize(
    "prs",
    [
        _prs({"number": 15, "headRefName": "fleet/orphan", "state": "OPEN", "mergedAt": None}),
        "[]",
    ],
)
def test_acceptance_orphan_open_or_absent_never_archives(prs: str) -> None:
    row = _first(rs.scan_recovery("", _wt("fleet/orphan"), prs))

    assert row["classification"] == rs.CLASS_ORPHAN
    assert row["action"] == rs.ACTION_ESCALATE


def test_orphan_dirty_even_when_merged_escalates() -> None:
    prs = _prs(
        {
            "number": 16,
            "headRefName": "fleet/orphan",
            "state": "MERGED",
            "mergedAt": "2026-06-24T00:00:00Z",
        }
    )

    row = _first(rs.scan_recovery("", _wt("fleet/orphan", extra="dirty true"), prs))

    assert row["action"] == rs.ACTION_ESCALATE
    assert row["signals"]["uncommitted_changes"] is True  # type: ignore[index]


def test_merged_ledger_row_with_dirty_worktree_escalates_instead_of_cleanup() -> None:
    ledger = "TASK T1 | BRANCH=fleet/done PR=12 WT=/tmp/done MERGED=true\n"
    prs = _prs(
        {
            "number": 12,
            "headRefName": "fleet/done",
            "state": "MERGED",
            "mergedAt": "2026-06-24T00:00:00Z",
        }
    )

    row = _first(
        rs.scan_recovery(
            ledger,
            _wt("fleet/done", "/tmp/done", extra="dirty true"),
            prs,
        )
    )

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["action"] == rs.ACTION_ESCALATE
    assert row["signals"]["uncommitted_changes"] is True  # type: ignore[index]


def test_live_rows_continue_and_closed_unmerged_rows_redrive() -> None:
    live = rs.scan_recovery(
        "TASK Live | BRANCH=fleet/live PR=17 MERGED=false\n",
        _wt("fleet/live"),
        _prs({"number": 17, "headRefName": "fleet/live", "state": "OPEN", "mergedAt": None}),
    )
    redrive = rs.scan_recovery(
        "TASK Closed | BRANCH=fleet/closed PR=18 MERGED=false\n",
        "",
        _prs({"number": 18, "headRefName": "fleet/closed", "state": "CLOSED", "mergedAt": None}),
    )

    assert _first(live)["classification"] == rs.CLASS_LIVE
    assert _first(live)["action"] == rs.ACTION_CONTINUE
    assert _first(redrive)["classification"] == rs.CLASS_PARTIAL
    assert _first(redrive)["action"] == rs.ACTION_RE_DRIVE


@pytest.mark.parametrize(
    ("resume_flag", "expected_action"),
    [
        (" RESUME_COUNT=3", rs.ACTION_ESCALATE),
        (" RESUME_COUNT=1", rs.ACTION_CONTINUE),
        ("", rs.ACTION_CONTINUE),
    ],
)
def test_resume_attempt_cap_escalates_only_after_budget_burned(
    resume_flag: str, expected_action: str
) -> None:
    row = _first(
        rs.scan_recovery(
            f"TASK Resume | BRANCH=fleet/resume PR=24 MERGED=false{resume_flag}\n",
            _wt("fleet/resume"),
            _prs({"number": 24, "headRefName": "fleet/resume", "state": "OPEN", "mergedAt": None}),
        )
    )

    assert row["classification"] == rs.CLASS_LIVE
    assert row["action"] == expected_action


def test_resume_attempt_cap_escalates_redrive_action() -> None:
    row = _first(
        rs.scan_recovery(
            "TASK Redrive | BRANCH=fleet/redrive PR=25 MERGED=false RESUME_COUNT=3\n",
            "",
            _prs({"number": 25, "headRefName": "fleet/redrive", "state": "CLOSED", "mergedAt": None}),
        )
    )

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["action"] == rs.ACTION_ESCALATE


def test_ledger_terminal_contradicted_by_open_pr_escalates() -> None:
    row = _first(
        rs.scan_recovery(
            "TASK T3 | BRANCH=fleet/open PR=19 MERGED=true\n",
            _wt("fleet/open"),
            _prs({"number": 19, "headRefName": "fleet/open", "state": "OPEN", "mergedAt": None}),
        )
    )

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["action"] == rs.ACTION_ESCALATE


def test_table_rows_branch_suffix_pr_number_and_unknown_values() -> None:
    ledger = (
        "| TASK | BRANCH | PR# | WT | MERGED | WT_CLEAN |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| T4 | fleet/suffix | #20 | /tmp/suffix | maybe | maybe |\n"
    )
    prs = _prs({"number": "20", "headRefName": "suffix", "state": "OPEN", "mergedAt": None})

    row = _first(rs.scan_recovery(ledger, "", prs))

    assert row["task_id"] == "T4"
    assert row["pr_number"] == 20
    assert row["classification"] == rs.CLASS_LIVE
    assert row["signals"]["ledger_flag"] == "unknown"  # type: ignore[index]


def test_parsers_cover_malformed_and_alternate_shapes() -> None:
    assert rs.parse_ledger_rows("noise\n") == []
    assert rs.parse_ledger_rows("noise | still not a task\nTASK good | BRANCH=fleet/good\n")[
        0
    ].task_id == "good"
    assert rs.parse_ledger_rows(
        "| ID | BRANCH | MERGED |\n"
        "| --- | --- | --- |\n"
        "| wrong | shape |\n"
        "| T7 | fleet/table | false |\n"
    )[0].task_id == "T7"
    assert rs.parse_worktrees("worktree /tmp/bare\nbare\nclean false\n")[0].uncommitted_changes
    separated = rs.parse_worktrees(
        "worktree /tmp/one\nbranch refs/heads/fleet/one\n\n"
        "worktree /tmp/two\nbranch refs/heads/fleet/two\n"
    )
    assert [wt.branch for wt in separated] == ["fleet/one", "fleet/two"]
    assert rs.parse_pr_list("") == []
    assert rs.parse_pr_list(json.dumps([{"number": None, "headRefName": None, "state": 7}, []]))[
        0
    ].state == "7"
    assert rs._branch_matches(None, "fleet/x") is False
    with pytest.raises(ValueError, match="pr list JSON must be a list"):
        rs.parse_pr_list("{}")


def test_ambiguous_scm_state_escalates() -> None:
    row = _first(
        rs.scan_recovery(
            "TASK T5 | BRANCH=fleet/ambiguous MERGED=true\n",
            "",
            _prs(
                {"number": 21, "headRefName": "fleet/ambiguous", "state": "OPEN", "mergedAt": None},
                {
                    "number": 22,
                    "headRefName": "fleet/ambiguous",
                    "state": "MERGED",
                    "mergedAt": "2026-06-24T00:00:00Z",
                },
            ),
        )
    )

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["signals"]["scm_state"] == rs.SCM_AMBIGUOUS  # type: ignore[index]


def test_missing_worktree_and_pr_for_unmerged_row_escalates() -> None:
    row = _first(rs.scan_recovery("TASK T8 | BRANCH=fleet/missing MERGED=false\n", "", "[]"))

    assert row["classification"] == rs.CLASS_PARTIAL
    assert row["action"] == rs.ACTION_ESCALATE


def test_cli_success_outputs_json_and_uses_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text("TASK T6 | BRANCH=fleet/cli PR=23 MERGED=false\n", encoding="utf-8")
    calls: list[tuple[list[str], dict[str, object]]] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(argv: list[str], **kwargs: object) -> Result:
        calls.append((argv, kwargs))
        if argv[:3] == ["git", "-C", str(tmp_path)]:
            return Result(_wt("fleet/cli"))
        if argv[:3] == ["git", "-C", "/tmp/wt"]:
            return Result("")
        return Result(_prs({"number": 23, "headRefName": "fleet/cli", "state": "OPEN", "mergedAt": None}))

    cli = _load_cli()
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["recovery_scan.py", str(ledger), "--repo", str(tmp_path), "--base", "main"])
    out, err = io.StringIO(), io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main()

    assert rc == 0
    assert err.getvalue() == ""
    assert json.loads(out.getvalue())["rows"][0]["action"] == rs.ACTION_CONTINUE
    assert calls[2][0][-2:] == ["--base", "main"]
    assert calls[2][1]["cwd"] == tmp_path


def test_cli_worktree_text_marks_status_failures_dirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli = _load_cli()

    class Result:
        stderr = ""

        def __init__(self, stdout: str, returncode: int = 0) -> None:
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(argv: list[str], **kwargs: object) -> Result:
        if argv[:3] == ["git", "-C", str(tmp_path)]:
            return Result(_wt("fleet/cli", "/tmp/wt"))
        return Result("", returncode=128)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    text = cli._worktree_text(tmp_path)

    assert "dirty true" in text


def test_cli_worktree_text_preserves_existing_clean_signals_and_blank_records(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cli = _load_cli()
    raw = (
        "worktree /tmp/one\n"
        "branch refs/heads/fleet/one\n"
        "clean true\n"
        "\n"
        "worktree /tmp/two\n"
        "branch refs/heads/fleet/two\n"
    )
    status_calls: list[list[str]] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(argv: list[str], **kwargs: object) -> Result:
        if argv[:3] == ["git", "-C", str(tmp_path)]:
            return Result(raw)
        status_calls.append(argv)
        return Result(" M touched.py\n")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    text = cli._worktree_text(tmp_path)

    assert "clean true" in text
    assert "\n\nworktree /tmp/two" in text
    assert "dirty true" in text
    assert status_calls == [["git", "-C", "/tmp/two", "status", "--porcelain"]]


def test_cli_reports_input_and_command_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rc, out, err = _run_cli(monkeypatch, str(tmp_path / "missing.md"), "--repo", str(tmp_path))
    assert rc == 1
    assert out == ""
    assert "recovery-scan:" in err

    ledger = tmp_path / "progress.md"
    ledger.write_text("", encoding="utf-8")
    cli = _load_cli()

    class BadResult:
        returncode = 2
        stdout = ""
        stderr = "no worktree"

    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: BadResult())
    monkeypatch.setattr(sys, "argv", ["recovery_scan.py", str(ledger), "--repo", str(tmp_path)])
    out_buf, err_buf = io.StringIO(), io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        assert cli.main() == 1
    assert out_buf.getvalue() == ""
    assert "no worktree" in err_buf.getvalue()


def test_global_coverage_dashboard_pipe_parser_non_task_line() -> None:
    dashboard = _load_dashboard()

    assert dashboard._parse_pipe_rows("not a task row\n", "fixture.md") == []


# --- Finding 27: ledger parser must not double-count dual-format tasks --------


def test_ledger_rows_deduplicate_task_present_in_both_pipe_and_table_form() -> None:
    ledger = (
        "TASK Dual | BRANCH=fleet/dual PR=30 MERGED=false RESUME_COUNT=2\n"
        "\n"
        "| TASK | BRANCH | MERGED |\n"
        "| --- | --- | --- |\n"
        "| Dual | fleet/dual | false |\n"
        "| Solo | fleet/solo | false |\n"
    )

    rows = rs.parse_ledger_rows(ledger)

    task_ids = [row.task_id for row in rows]
    assert task_ids.count("Dual") == 1
    assert sorted(task_ids) == ["Dual", "Solo"]
    # The pipe shape wins the collision: its explicit flags survive.
    dual = next(row for row in rows if row.task_id == "Dual")
    assert dual.flags["RESUME_COUNT"] == "2"


def test_scan_does_not_double_count_dual_format_row() -> None:
    ledger = (
        "TASK Dup | BRANCH=fleet/dup PR=31 MERGED=false\n"
        "| TASK | BRANCH | MERGED |\n"
        "| --- | --- | --- |\n"
        "| Dup | fleet/dup | false |\n"
    )
    prs = _prs({"number": 31, "headRefName": "fleet/dup", "state": "OPEN", "mergedAt": None})

    report = rs.scan_recovery(ledger, _wt("fleet/dup"), prs)

    assert report["summary"]["live"] == 1
    assert len([row for row in report["rows"] if row.get("task_id") == "Dup"]) == 1


# --- Finding 26: malformed gh JSON must not crash the advisory scan -----------


def test_parse_pr_list_tolerates_malformed_json() -> None:
    assert rs.parse_pr_list("not json at all") == []
    assert rs.parse_pr_list('[{"number": 1, ') == []  # truncated gh payload


def test_scan_recovery_survives_unparseable_pr_list() -> None:
    report = rs.scan_recovery(
        "TASK T9 | BRANCH=fleet/scan MERGED=false\n",
        _wt("fleet/scan"),
        "}{ truncated gh output",
    )

    # The scan still classifies from ledger + worktree signals instead of crashing.
    assert _first(report)["classification"] == rs.CLASS_LIVE
    assert _first(report)["signals"]["scm_state"] == rs.SCM_ABSENT  # type: ignore[index]


# --- Finding 11: the bounded resume budget must actually be written -----------


def test_increment_resume_count_initializes_then_escalates(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        "noise line\nTASK Loop | BRANCH=fleet/loop PR=40 MERGED=false\n",
        encoding="utf-8",
    )
    prs = _prs({"number": 40, "headRefName": "fleet/loop", "state": "CLOSED", "mergedAt": None})

    # A row that has never been resumed re-drives.
    before = _first(rs.scan_recovery(ledger.read_text(encoding="utf-8"), "", prs))
    assert before["action"] == rs.ACTION_RE_DRIVE

    counts = [rs.increment_resume_count(ledger, "Loop") for _ in range(rs.MAX_RESUME_ATTEMPTS)]
    assert counts == [1, 2, 3]
    assert "noise line\n" in ledger.read_text(encoding="utf-8")

    # Once the budget is burned the same row escalates instead of looping.
    after = _first(rs.scan_recovery(ledger.read_text(encoding="utf-8"), "", prs))
    assert after["action"] == rs.ACTION_ESCALATE


def test_increment_resume_count_bumps_existing_counter(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        "TASK Keep | BRANCH=fleet/keep RESUME_COUNT=1 MERGED=false\n",
        encoding="utf-8",
    )

    assert rs.increment_resume_count(ledger, "Keep") == 2

    rows = rs.parse_ledger_rows(ledger.read_text(encoding="utf-8"))
    assert rows[0].flags["RESUME_COUNT"] == "2"


def test_increment_resume_count_missing_task_leaves_ledger_untouched(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    original = "TASK Other | BRANCH=fleet/other MERGED=false\n"
    ledger.write_text(original, encoding="utf-8")

    assert rs.increment_resume_count(ledger, "Absent") == -1
    assert ledger.read_text(encoding="utf-8") == original
    # No staging file is left behind by the no-op path.
    assert list(tmp_path.glob(".progress.md.*.tmp")) == []


def test_increment_resume_count_is_atomic_and_cleans_tmp_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text("TASK Boom | BRANCH=fleet/boom MERGED=false\n", encoding="utf-8")

    def explode(src: object, dst: object) -> None:
        raise OSError("simulated rename failure")

    monkeypatch.setattr(rs.os, "replace", explode)

    with pytest.raises(OSError, match="simulated rename failure"):
        rs.increment_resume_count(ledger, "Boom")

    # Original is intact and the staging tmp was unlinked on the failure path.
    assert ledger.read_text(encoding="utf-8") == "TASK Boom | BRANCH=fleet/boom MERGED=false\n"
    assert list(tmp_path.glob(".progress.md.*.tmp")) == []



def test_increment_resume_count_table_format_initializes_then_escalates(tmp_path: Path) -> None:
    """BUG-004: table-format ledgers must receive RESUME_COUNT writes."""
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        "noise line\n"
        "| TASK | BRANCH | PR | MERGED |\n"
        "| --- | --- | --- | --- |\n"
        "| Loop | fleet/loop | 40 | false |\n"
        "| Other | fleet/other | 41 | false |\n",
        encoding="utf-8",
    )
    prs = _prs({"number": 40, "headRefName": "fleet/loop", "state": "CLOSED", "mergedAt": None})

    before = next(
        row
        for row in rs.scan_recovery(ledger.read_text(encoding="utf-8"), "", prs)["rows"]
        if row.get("task_id") == "Loop"
    )
    assert before["action"] == rs.ACTION_RE_DRIVE

    counts = [rs.increment_resume_count(ledger, "Loop") for _ in range(rs.MAX_RESUME_ATTEMPTS)]
    assert counts == [1, 2, 3]
    text = ledger.read_text(encoding="utf-8")
    assert "noise line\n" in text
    rows = {row.task_id: row for row in rs.parse_ledger_rows(text)}
    assert rows["Loop"].flags["RESUME_COUNT"] == "3"
    assert not (rows["Other"].flags.get("RESUME_COUNT") or "").strip()

    after = next(
        row
        for row in rs.scan_recovery(text, "", prs)["rows"]
        if row.get("task_id") == "Loop"
    )
    assert after["action"] == rs.ACTION_ESCALATE


def test_increment_resume_count_table_format_bumps_existing_column(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        "| TASK | BRANCH | MERGED | RESUME_COUNT |\n"
        "| --- | --- | --- | --- |\n"
        "| Keep | fleet/keep | false | 1 |\n",
        encoding="utf-8",
    )

    assert rs.increment_resume_count(ledger, "Keep") == 2
    rows = rs.parse_ledger_rows(ledger.read_text(encoding="utf-8"))
    assert rows[0].flags["RESUME_COUNT"] == "2"


def test_increment_resume_count_prefers_pipe_row_over_table_duplicate(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        "TASK Dual | BRANCH=fleet/dual MERGED=false RESUME_COUNT=1\n"
        "| TASK | BRANCH | MERGED | RESUME_COUNT |\n"
        "| --- | --- | --- | --- |\n"
        "| Dual | fleet/dual | false | 9 |\n",
        encoding="utf-8",
    )

    assert rs.increment_resume_count(ledger, "Dual") == 2
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert "RESUME_COUNT=2" in lines[0]
    assert "9" in lines[3]


def test_pipe_row_task_id_helper_rejects_non_task_lines() -> None:
    assert rs._pipe_row_task_id("not a task | x=1\n") is None
    assert rs._pipe_row_task_id("TASK NoPipe BRANCH=fleet/x\n") is None
    assert rs._pipe_row_task_id("TASK Yes | BRANCH=fleet/x\n") == "Yes"
