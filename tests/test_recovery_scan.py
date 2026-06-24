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
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_run(argv: list[str], **kwargs: object) -> Result:
        calls.append(argv)
        if argv[:3] == ["git", "-C", str(tmp_path)]:
            return Result(_wt("fleet/cli"))
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
    assert calls[1][-2:] == ["--base", "main"]


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
