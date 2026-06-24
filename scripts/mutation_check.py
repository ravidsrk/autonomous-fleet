#!/usr/bin/env python3
"""Standing mutation gate: a regression test FOR the test suite.

Reads tests/mutations.yaml — a manifest of `{id, file, find, replace, guards}` entries, each a
representative bug in the code-under-test plus the test(s) that MUST catch it. For each mutation it
applies the find->replace, runs the guard tests, and asserts they FAIL (the bug was caught). A
mutation whose guard tests still PASS SURVIVED: the guarding test is weak/tautological/inert. Any
survivor (or a stale manifest entry whose `find` no longer matches) fails the gate.

Source files are mutated in place, so restore is defended three ways: a per-mutation try/finally, a
SIGINT/SIGTERM handler, and a final in-memory restore of any active mutation. A target file may have
uncommitted changes before the gate runs; the restore point is the exact file content read before
each mutation, so pre-commit mutation checks do not require committing first and do not clobber real
work.

Usage: python scripts/mutation_check.py [--manifest PATH] [--id ID ...] [-q]
Exit 0 = every mutation caught; 1 = a survivor or stale entry; 2 = unsafe preconditions.
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
_ACTIVE: dict[Path, str] = {}  # file -> original text, for emergency restore


def _restore_all() -> None:
    for path, original in list(_ACTIVE.items()):
        try:
            path.write_text(original, encoding="utf-8")
        except OSError:
            pass
    _ACTIVE.clear()


def _on_signal(signum, _frame):  # pragma: no cover - signal path
    _restore_all()
    sys.exit(130)


def _run_guards(guards: list[str]) -> bool:
    """Return True if the guard tests FAILED (i.e. the mutation was CAUGHT)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", *guards, "-q", "-x"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return r.returncode != 0


def run(manifest_path: Path, only: set[str] | None, quiet: bool) -> int:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    mutations = manifest.get("mutations", [])
    if only:
        mutations = [m for m in mutations if m["id"] in only]
    if not mutations:
        print("no mutations selected", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    survived: list[str] = []
    stale: list[str] = []
    caught = 0
    for m in mutations:
        mid, rel = m["id"], m["file"]
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        occ = original.count(m["find"])
        if occ == 0:
            stale.append(mid)
            print(f"  STALE      {mid}  (find-string absent in {rel})")
            continue
        n = 0 if m.get("all") else 1
        mutated = original.replace(m["find"], m["replace"], n)
        _ACTIVE[path] = original
        try:
            path.write_text(mutated, encoding="utf-8")
            hit = _run_guards(m["guards"])
        finally:
            path.write_text(original, encoding="utf-8")
            _ACTIVE.pop(path, None)
        if hit:
            caught += 1
            if not quiet:
                print(f"  caught     {mid}")
        else:
            survived.append(mid)
            print(f"  SURVIVED   {mid}  ({rel}: guards {m['guards']} did not catch it)")

    # Belt-and-suspenders: ensure nothing was left mutated without using git checkout,
    # which would clobber legitimate pre-existing local edits.
    _restore_all()

    total = len(mutations)
    print(f"\n{total} mutations: {caught} caught, {len(survived)} survived, {len(stale)} stale")
    if survived:
        print(f"WEAK TESTS (mutation survived): {survived}", file=sys.stderr)
    if stale:
        print(f"STALE MANIFEST ENTRIES (update find-string): {stale}", file=sys.stderr)
    return 1 if (survived or stale) else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=ROOT / "tests" / "mutations.yaml")
    p.add_argument("--id", action="append", dest="ids", help="run only these mutation id(s)")
    p.add_argument("-q", "--quiet", action="store_true", help="only print survivors/stale")
    args = p.parse_args()
    try:
        return run(args.manifest, set(args.ids) if args.ids else None, args.quiet)
    finally:
        _restore_all()


if __name__ == "__main__":
    raise SystemExit(main())
