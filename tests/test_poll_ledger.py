"""Non-busy WAIT poll-ledger helper."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLL = ROOT / "scripts" / "poll-ledger.sh"


def test_poll_ledger_matches_task_row(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        """PHASE: FIX
TASK D1 | CODED=f REVIEWED=f MERGED=f
TASK D2 | CODED=t REVIEWED=t MERGED=t
""",
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            str(POLL),
            "--ledger",
            str(ledger),
            "--task",
            "D2",
            "--expect",
            "MERGED=t",
            "--timeout",
            "1",
            "--interval",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout


def test_poll_ledger_times_out(tmp_path: Path) -> None:
    ledger = tmp_path / "progress.md"
    ledger.write_text("TASK D1 | MERGED=f\n", encoding="utf-8")
    r = subprocess.run(
        [
            str(POLL),
            "--ledger",
            str(ledger),
            "--task",
            "D1",
            "--expect",
            "MERGED=t",
            "--timeout",
            "1",
            "--interval",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1


def test_poll_ledger_multi_task_only_matches_target(tmp_path: Path) -> None:
    """Later TASK rows must not satisfy --expect for an earlier task (Codex P2)."""
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        """PHASE: FIX
TASK D1 | CODED=f REVIEWED=f MERGED=f
TASK D2 | CODED=t REVIEWED=t MERGED=t
""",
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            str(POLL),
            "--ledger",
            str(ledger),
            "--task",
            "D1",
            "--expect",
            "MERGED=t",
            "--timeout",
            "1",
            "--interval",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, (
        "D1 MERGED=f must not match because D2 MERGED=t leaked into block: "
        + r.stdout
        + r.stderr
    )