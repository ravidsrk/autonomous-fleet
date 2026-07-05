"""Session-wide hermeticity shims so env-dependent tests pass on bare runners.

Several tests drive the real headless/campaign shell scripts. Those scripts run
an adapter preflight that shells out to ``gh auth status`` and perform git
operations that need an author/committer identity. On a developer machine both
happen to be present, so the suite passed locally while failing on a bare CI
runner (unauthenticated ``gh``, no global git identity) — the failures were
environment coupling, not logic.

This fixture makes the suite hermetic:

* a fake **authenticated** ``gh`` earliest on ``PATH`` — the runtime auth under
  test is exercised through the fake ``codex``/``grok`` binaries each test
  installs; the real ``gh`` login state is not a unit-under-test, so shimming it
  removes the coupling without weakening any assertion. (The ``adapter_preflight``
  unit tests inject their own ``run``/``which`` doubles and never reach this.)
* a deterministic **git identity** via ``GIT_AUTHOR_*`` / ``GIT_COMMITTER_*`` so
  ``git commit`` works without a global ``user.email``/``user.name``.

Both are restored at session teardown.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _hermetic_ci_env(tmp_path_factory: pytest.TempPathFactory):
    fake_bin = tmp_path_factory.mktemp("hermetic-bin")
    gh = fake_bin / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "# Test shim: report an authenticated gh so adapter-preflight's\n"
        "# `gh auth status` passes on bare runners. Real gh login is not the\n"
        "# unit under test (runtime auth is exercised via fake codex/grok).\n"
        'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then\n'
        '  echo "Logged in to github.com (test shim)" 1>&2\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)

    prev_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{fake_bin}{os.pathsep}{prev_path}"

    git_identity = {
        "GIT_AUTHOR_NAME": "Fleet Test",
        "GIT_AUTHOR_EMAIL": "fleet-test@example.invalid",
        "GIT_COMMITTER_NAME": "Fleet Test",
        "GIT_COMMITTER_EMAIL": "fleet-test@example.invalid",
    }
    prev_identity = {key: os.environ.get(key) for key in git_identity}
    os.environ.update(git_identity)

    try:
        yield
    finally:
        os.environ["PATH"] = prev_path
        for key, value in prev_identity.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
