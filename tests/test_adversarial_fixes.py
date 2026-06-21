"""Regression tests for the 9 confirmed adversarial-review findings (docs/arch-build-review.md).

One test (or group) per finding, asserting the bug is closed.
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "scripts" / "run-sandboxed.sh"
sys.path.insert(0, str(ROOT / "scripts"))


def _classify(cmd: str) -> str:
    # Invoke with SEPARATE argv (shlex.split), exactly how the real exec path receives the command.
    # Passing a single joined string would mask the argv-boundary bug round-3 review found.
    return subprocess.run(
        [str(SANDBOX), "--classify", *shlex.split(cmd)], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()


# --- run-sandboxed.sh: command-prefix bypass, bash -c, reset --hard, gh/infra false positives ---

@pytest.mark.parametrize("cmd", [
    "command rm -rf /etc", "env git push --force", "exec git push --force",
    "xargs rm -rf /etc", "nice rm -rf /etc", "sudo command rm -rf /etc",
    "git status ; command rm -rf /etc",                 # standalone ; operator token, 2nd stmt denied
    "/bin/rm -rf /etc", "/usr/bin/git push --force",     # basename (absolute path) bypass
    "env -u FOO rm -rf /etc", "nice -n 5 git push --force",  # wrapper-option-operand bypass
    "nohup sudo -u root rm -rf /etc", "ionice -c 2 rm -rf /etc",
    "command command rm -rf /etc",                       # stacked wrappers
    "timeout 5 rm -rf /etc", "flock /tmp/lock git push --force",  # command-runner wrappers
    "doas -u root rm -rf /etc", "chrt -f 99 rm -rf /etc", "taskset -c 0 git push --force",
    "bash -c 'rm -rf /etc'", "sh -c 'git push --force'",  # bash -c embedded
    "bash -ec 'rm -rf /etc'", "sh -ec 'git push --force'", "bash -xc 'rm -rf /etc'",  # bundled -c
    "env -S 'rm -rf /etc'", "env --split-string='git push --force'",  # env split-string runs a cmd
    "bash -c '>/tmp/log rm -rf /etc'",                   # redirection-before-command in bash -c
    "bash -c 'cd /tmp & rm -rf /etc'", "bash -c 'true & git push --force'",  # single & background op
    "git reset --hard origin", "git reset --hard @{upstream}", "git reset --hard origin/main",  # reset
    "gh pr merge 5", "gh repo delete acme/x",            # gh structural
])
def test_dangerous_commands_denied(cmd):
    assert _classify(cmd) == "DENY", f"{cmd!r} must DENY"


@pytest.mark.parametrize("cmd", [
    'echo "terraform apply"', "echo gh pr merge done",  # substring false positives, now ALLOW
    "echo rm -rf foo",                                  # echo of a dangerous string is not a wrapper
    "env echo rm -rf /etc", "time -p echo gh pr merge",  # data-consumer under a wrapper stays safe
    "command rm file.txt", "nice -n 5 ls", "env FOO=bar git status",  # wrappers over SAFE commands
    "ls -la", "git pull", "git commit -am wip",
])
def test_safe_commands_allowed(cmd):
    assert _classify(cmd) == "ALLOW", f"{cmd!r} must ALLOW"


@pytest.mark.parametrize("cmd", [
    "git reset --hard HEAD~1", "terraform apply", "gh release create v1",
])
def test_recoverable_commands_ask(cmd):
    assert _classify(cmd) == "ASK", f"{cmd!r} must ASK"


@pytest.mark.parametrize("argv", [
    ["bash", "-ec", "rm -rf {v}"],
    ["env", "-S", "rm -rf {v}"],
    ["command", "rm", "-rf", "{v}"],
    ["bash", "-c", 'rm "$@"', "_", "-rf", "{v}"],   # positional-param construction -> fail safe
    ["bash", "-c", "cd /tmp & rm -rf {v}"],          # single & background operator
    ["bash", "-c", "rm \\\n-rf {v}"],                # backslash-newline line continuation
])
def test_real_exec_path_refuses_and_does_not_run(tmp_path, argv):
    # The strongest test: invoke the REAL exec path (no --classify) and prove the rm did NOT run.
    victim = tmp_path / "victim"
    victim.mkdir()
    cmd = [str(SANDBOX)] + [a.format(v=str(victim)) for a in argv]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0, f"{cmd} should be refused"
    assert victim.exists(), f"{cmd} reached exec and deleted the victim dir"


# --- fleet_outcome.py: NaN/inf in cost_estimate, metrics, and eval_edge ordering ---

from lib.fleet_outcome import eval_edge, pick_next_node, validate_outcome  # noqa: E402


def test_pick_next_node_missing_metric_edge_skipped_not_crash():
    # F2: an edge gating on an absent metric must be skipped (not crash), so a valid `always`
    # fallback after it is still reachable.
    camp = {"edges": {"audit": [{"to": "hotfix", "if": "p2_open > 0"}, {"to": "ship", "if": "always"}]}}
    assert pick_next_node(camp, "audit", {"metrics": {}}) == "ship"


def test_validate_cli_malformed_yaml_fails_one_doc_not_batch(tmp_path):
    # F3: a malformed-YAML doc fails independently; the batch completes (exit 1, both seen).
    good = tmp_path / "a-readiness.md"
    good.write_text(
        "---\nfleet-outcome:\n  mission: doc-sync\n  status: done\n  repo: /r\n"
        "  base_branch: b\n  prs_merged: 1\n  metrics: {drift_open: 0, code_bug_findings: 0}\n---\n"
    )
    bad = tmp_path / "b-readiness.md"
    bad.write_text("---\nfleet-outcome:\n  bad: : indent\n---\n")
    cli = ROOT / "scripts" / "validate_fleet_outcome.py"
    r = subprocess.run([sys.executable, str(cli), str(good), str(bad)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1
    assert "OK" in r.stdout and "FAIL" in r.stdout

BASE = {
    "mission": "doc-sync", "status": "done", "repo": "/r", "base_branch": "b",
    "prs_merged": 1, "metrics": {"drift_open": 0, "code_bug_findings": 0},
}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_cost_estimate_rejects_non_finite(bad):
    assert any("cost_estimate" in e for e in validate_outcome({**BASE, "cost_estimate": bad}))


def test_metric_rejects_non_finite():
    bad = {**BASE, "metrics": {"drift_open": float("nan"), "code_bug_findings": 0}}
    assert any("finite" in e for e in validate_outcome(bad))


def test_eval_edge_non_finite_raises():
    out = {**BASE, "metrics": {"drift_open": float("nan"), "code_bug_findings": 0}}
    with pytest.raises(ValueError):
        eval_edge("drift_open > 0", out)


@pytest.mark.parametrize("expr", [
    "status == blocked now",   # trailing token on equality -> was silently False
    "status != done extra",
    "drift_open == 0 == 1",
    "drift_open >= 5 extra",   # trailing token on ordering -> was a crash
])
def test_eval_edge_trailing_token_raises_not_silent_wrong_branch(expr):
    # A malformed multi-token operand must hit the documented "unsupported expression -> log + skip"
    # path, not silently evaluate to a wrong boolean and misroute the campaign.
    with pytest.raises(ValueError):
        eval_edge(expr, {"status": "blocked", "metrics": {"drift_open": 6}, "drift_open": 6})


@pytest.mark.parametrize("expr,ctx,expected", [
    ("status == blocked", {"status": "blocked"}, True),
    ("status != done", {"status": "blocked"}, True),
    ("drift_open == 0", {"metrics": {"drift_open": 0}}, True),
    ("drift_open > 4", {"metrics": {"drift_open": 5}}, True),
])
def test_eval_edge_legit_single_token_still_works(expr, ctx, expected):
    assert eval_edge(expr, ctx) is expected


# --- render-dashboard.py: malformed YAML must not crash the whole render ---

def test_dashboard_survives_malformed_yaml(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a-progress.md").write_text("# x\nPHASE: DONE\n")
    (docs / "bad-readiness.md").write_text("---\nfleet-outcome:\n  mission: x\n  m: [unclosed\n---\n")
    out = tmp_path / "o.html"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render-dashboard.py"), "--repo", str(tmp_path), "-o", str(out)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert out.exists()


# --- coupling-graph.py: relative imports must produce an edge (not be dropped) ---

def test_coupling_resolves_relative_imports(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from . import b\nfrom .b import thing\n")
    (pkg / "b.py").write_text("thing = 1\n")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "coupling-graph.py"), str(tmp_path), "--json"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    # a.py imports b.py via a relative import -> they must be coupled (same cluster).
    clusters = data.get("clusters", [])
    coupled = any(
        any("a.py" in f for f in c) and any("b.py" in f for f in c)
        for c in clusters
    )
    assert coupled, f"relative import not resolved into a cluster: {data}"
