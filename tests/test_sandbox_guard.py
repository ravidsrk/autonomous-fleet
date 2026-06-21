"""Guard tests for scripts/run-sandboxed.sh blast-radius classifier.

These drive the REAL shell script via its ``--classify`` (dry-run) mode, so no
filesystem is mutated: the script prints DENY|ASK|ALLOW and exits 0 without
exec. The table mirrors omnigent's nessie blast_radius unit tests (the source
this classifier was ported from), so a regression here means the bash port
diverged from the policy it replaces — a worker could then run a destructive
command the static deny-list and the omnigent policy both catch.

A few cases also assert the exec-mode exit codes (DENY=2, ASK=3, ALLOW execs)
to prove the verdict actually gates the wrapped command, not just the report.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "scripts" / "run-sandboxed.sh"


def _classify(*argv: str) -> str:
    """
    Return the blast-radius verdict the script assigns to *argv*.

    Runs ``run-sandboxed.sh --classify <argv...>``, which prints DENY|ASK|ALLOW
    and exits 0 without exec — hermetic, mutates nothing.

    :param argv: The command line to classify, already split into argv (the
        common case the wrapper sees), e.g. ``("git", "push", "--force")``.
    :returns: The verdict string, e.g. ``"DENY"``.
    """
    r = subprocess.run(
        [str(SANDBOX), "--classify", *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    return r.stdout.strip()


# Irreversible → DENY. Covers every flag / path / refspec form plus the
# evasions the static deny-list missed: split + long rm flags, root children,
# sudo / env-prefix unwrap, git -C, +/: push refspecs, statement chaining.
_DENY = [
    ("git", "push", "--force", "origin", "main"),  # force-push (long flag)
    ("git", "push", "-f"),  # force-push (short flag)
    ("git", "push", "-uf", "origin", "main"),  # force via bundled short option
    ("git", "push", "-df", "origin", "main"),  # delete/force via bundled short option
    ("git", "push", "origin", "+main"),  # force-push via +refspec
    ("git", "push", "origin", "--delete", "main"),  # remote-branch deletion
    ("git", "push", "-d", "origin", "main"),  # deletion via short option
    ("git", "push", "origin", ":main"),  # deletion via :refspec
    ("git", "push", "--mirror", "origin"),  # mirrors force updates + deletions
    ("git", "push", "--prune", "origin"),  # deletes remote refs missing locally
    ("git", "-C", "repo", "push", "-d", "origin", "main"),  # deletion after a git global option
    ("rm", "-rf", "/"),  # whole root
    ("rm", "-rf", "/etc"),  # root child (deny-list matched only bare /)
    ("rm", "-rf", "/usr/local"),  # path under a system dir
    ("rm", "-r", "-f", "/"),  # split recursive/force flags
    ("rm", "--recursive", "--force", "/"),  # long flags
    ("rm", "-rf", "~"),  # whole home dir
    ("rm", "-rf", "$HOME"),
    ("sudo", "rm", "-rf", "/var"),  # leading sudo
    ("sudo", "-n", "rm", "-rf", "/var"),  # sudo option before the command
    ("sudo", "--", "rm", "-rf", "/var"),  # sudo option terminator
    ("sudo", "-u", "root", "rm", "-rf", "/var"),  # sudo option with a separate value
    ("CI=1", "rm", "-rf", "/etc"),  # shell env assignment before the command
    ("CI=1", "sudo", "-n", "rm", "-rf", "/var"),  # env assignment before sudo
    ("sudo", "-n", "git", "push", "-d", "origin", "main"),  # deletion through sudo
    ("CI=1", "git", "push", "-d", "origin", "main"),  # env assignment before git push
    ("git", "reset", "--hard", "origin/main"),  # hard-reset to a remote ref
    ("gh", "pr", "merge", "42"),  # merge a PR (irreversible to the base branch)
    ("gh", "repo", "delete", "owner/x"),  # delete a repo
    # Statement chaining inside a single embedded command string.
    ("bash", "-c", "cd repo && rm -rf /etc"),
    ("sh", "-c", "git status; git push -f"),
]

# Outward / destructive-but-recoverable → ASK (the wrapper refuses too, but at
# the softer tier: a human re-runs by hand).
_ASK = [
    ("git", "push", "origin", "main"),  # ordinary outward push
    ("git", "push", "-u", "origin", "main"),  # set-upstream is outward, not force/delete
    ("git", "push", "-o", "ci.skip", "origin", "main"),  # push-option value, not a destructive flag
    ("git", "push", "-o=fast", "origin", "main"),  # attached push-option must not over-match `f`
    ("rm", "-rf", "build"),  # recursive rm of a relative (recoverable) path
    ("rm", "-r", "node_modules"),  # recursive, no force, relative
    ("rm", "-rf", "/home/u/proj/build"),  # scoped path under /home, not a system dir
    ("rm", "-rf", "/opt/app/cache"),  # scoped path under /opt
    ("terraform", "apply"),  # infra apply
    ("tofu", "destroy"),  # opentofu destroy
    ("kubectl", "apply", "-f", "x.yaml"),
    ("gh", "release", "create", "v1"),  # publish a release
    ("CI=1", "rm", "-rf", "build"),  # env assignment does not make scoped cleanup catastrophic
    ("CI=1", "git", "push", "origin", "main"),  # env assignment preserves ordinary-push ASK tier
]

# Reads / tests / edits / local git → ALLOW. Includes the over-match traps the
# robust tokenizer must not fall into.
_ALLOW = [
    ("git", "status"),
    ("git", "commit", "-m", "wip"),
    ("git", "merge", "--no-ff", "nessie/t1"),
    ("git", "worktree", "add", ".worktrees/t1", "-b", "nessie/t1"),
    ("pytest", "tests/", "-q"),
    ("rm", "file.txt"),  # non-recursive single-file delete
    ("rm", "-f", "stale.log"),  # force without recursion
    ("rm", "--", "-rf"),  # `--` ends flags: deletes a file literally named "-rf"
    ("git", "commit", "-m", "push to main soon"),  # "push" only in the commit message
    ("git", "push-notes", "--ref", "x"),  # not the `push` subcommand
    ("ls", "-la"),
]


@pytest.mark.parametrize("argv", _DENY, ids=[" ".join(a) for a in _DENY])
def test_classifier_denies_irreversible(argv: tuple[str, ...]) -> None:
    """Catastrophic commands classify DENY in every flag / path / refspec form."""
    assert _classify(*argv) == "DENY"


@pytest.mark.parametrize("argv", _ASK, ids=[" ".join(a) for a in _ASK])
def test_classifier_asks_recoverable(argv: tuple[str, ...]) -> None:
    """Outward / recoverable commands classify ASK (not DENY, not ALLOW)."""
    assert _classify(*argv) == "ASK"


@pytest.mark.parametrize("argv", _ALLOW, ids=[" ".join(a) for a in _ALLOW])
def test_classifier_allows_safe(argv: tuple[str, ...]) -> None:
    """Reads / tests / edits / local git classify ALLOW; the tokenizer must not over-match."""
    assert _classify(*argv) == "ALLOW"


def test_deny_refuses_with_exit_2() -> None:
    """A DENY verdict refuses before exec with exit 2 (no fs mutation: --classify proved the
    verdict; here we run WITHOUT --classify but on a command that is refused before any exec)."""
    r = subprocess.run(
        [str(SANDBOX), "rm", "-rf", "/"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
    assert "REFUSED" in r.stderr


def test_ask_refuses_with_exit_3() -> None:
    """An ASK verdict refuses before exec with exit 3 (the wrapper is non-interactive)."""
    r = subprocess.run(
        [str(SANDBOX), "git", "push", "origin", "main"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 3, (r.returncode, r.stdout, r.stderr)
    assert "REFUSED" in r.stderr


def test_allow_execs_and_scrubs_credential_env() -> None:
    """An ALLOW verdict execs the wrapped command; credential-shaped env is scrubbed first.

    Runs ``env`` (a harmless read) with secret-shaped vars set and asserts they
    are absent from the child while PATH survives — proving the env scrub still
    runs on the ALLOW path after the classifier extension.
    """
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "AWS_SECRET_ACCESS_KEY": "shh",
        "GH_TOKEN": "ghp_x",
        "MY_API_KEY": "k",
    }
    r = subprocess.run(
        [str(SANDBOX), "env"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert "AWS_SECRET_ACCESS_KEY" not in r.stdout
    assert "GH_TOKEN" not in r.stdout
    assert "MY_API_KEY" not in r.stdout
    assert "PATH=" in r.stdout


def test_classify_mode_does_not_exec() -> None:
    """``--classify`` reports the verdict and exits 0 without running the command.

    Uses a command that would FAIL loudly if executed (a binary that does not
    exist); --classify must still exit 0, proving it never reached exec.
    """
    r = subprocess.run(
        [str(SANDBOX), "--classify", "this-binary-does-not-exist-9f3a", "--boom"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert r.stdout.strip() == "ALLOW"
