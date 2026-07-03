#!/usr/bin/env python3
"""Sync the Python verification substrate into autonomous-fleet-core's assets.

``npx skills add`` copies only ``skills/`` — the enforcement substrate under
``scripts/`` never reached skills-install users, reducing the four verification
layers to prose on the documented install path (issue #80). This script copies
the engine-referenced Python validators (plus ``scripts/lib``) into
``skills/autonomous-fleet-core/assets/substrate/`` so they travel with the
skill, and writes ``substrate-manifest.json`` pinning the core skill version
and a sha256 per bundled file.

The bundle is a build artifact kept in lockstep by CI: ``--check`` (run by
validate-all) fails when the committed bundle drifts from ``scripts/``.

Shell wrappers (``preflight.sh``, ``validate-fleet-outcome.sh``,
``run-sandboxed.sh``) are NOT bundled — they assume the framework-clone layout
(repo venv, ``skills/`` at root). Install-mode resolution for those is issue
#81/#82; the Python entrypoints here are the actual gates.

Usage:
  python scripts/sync_substrate_assets.py            # write/refresh the bundle
  python scripts/sync_substrate_assets.py --check    # verify parity (exit 1 on drift)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DEST = ROOT / "skills" / "autonomous-fleet-core" / "assets" / "substrate"
CORE_SKILL_MD = ROOT / "skills" / "autonomous-fleet-core" / "SKILL.md"
MANIFEST_NAME = "substrate-manifest.json"

# The engine-referenced Python enforcement set. Deliberately explicit: adding a
# CLI here is a distribution decision, not a side effect.
CLI_ALLOWLIST = (
    "validate_run_archive.py",
    "verify_findings.py",
    "stop_verify.py",
    "verify_blind_fix.py",
    "recovery_scan.py",
    "emit_trace.py",
    "validate_fleet_outcome.py",
    "validate_namespacing.py",
    "verify_sha_pin.py",
    "verify_nudge_dedup.py",
    "verify_stacked_pr.py",
    "verify_hook_signal.py",
    "verify_round_budget.py",
)

REQUIREMENTS = "PyYAML>=6.0\n"


def _core_version() -> str:
    text = CORE_SKILL_MD.read_text(encoding="utf-8")
    m = re.search(r'version:\s*"([^"]+)"', text)
    return m.group(1) if m else "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_sources() -> dict[str, Path]:
    """Relative-dest-path -> source file. Lib ships whole (*.py only)."""
    sources: dict[str, Path] = {}
    for name in CLI_ALLOWLIST:
        src = SCRIPTS / name
        if not src.is_file():
            raise SystemExit(f"sync-substrate: allowlisted CLI missing: {src}")
        sources[name] = src
    for src in sorted((SCRIPTS / "lib").glob("*.py")):
        sources[f"lib/{src.name}"] = src
    return sources


def sync() -> None:
    sources = _bundle_sources()
    if DEST.exists():
        shutil.rmtree(DEST)
    (DEST / "lib").mkdir(parents=True)
    manifest: dict[str, object] = {
        "core_version": _core_version(),
        "source": "scripts/ (synced by scripts/sync_substrate_assets.py)",
        "files": {},
    }
    for rel, src in sources.items():
        dst = DEST / rel
        shutil.copy2(src, dst)
        manifest["files"][rel] = _sha256(dst)  # type: ignore[index]
    (DEST / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    manifest["files"]["requirements.txt"] = _sha256(DEST / "requirements.txt")  # type: ignore[index]
    (DEST / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    try:
        dest_label = str(DEST.relative_to(ROOT))
    except ValueError:  # out-of-tree DEST (tests, custom layouts)
        dest_label = str(DEST)
    print(f"sync-substrate: bundled {len(manifest['files'])} files -> {dest_label}")  # type: ignore[arg-type]


def check() -> int:
    sources = _bundle_sources()
    errors: list[str] = []
    manifest_path = DEST / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"sync-substrate: missing {manifest_path}; run scripts/sync_substrate_assets.py", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"sync-substrate: unreadable manifest: {exc}", file=sys.stderr)
        return 1
    listed = manifest.get("files", {}) if isinstance(manifest, dict) else {}

    for rel, src in sources.items():
        dst = DEST / rel
        if not dst.is_file():
            errors.append(f"missing bundled file: {rel}")
            continue
        if _sha256(src) != _sha256(dst):
            errors.append(f"bundle drift: {rel} differs from scripts/ source")
        if listed.get(rel) != _sha256(dst):
            errors.append(f"manifest drift: {rel} hash stale in {MANIFEST_NAME}")
    expected = set(sources) | {"requirements.txt"}
    for rel in listed:
        if rel not in expected:
            errors.append(f"orphan bundled file listed: {rel}")
    # Walk the bundle itself: a stray file ON DISK (bad merge, manual edit,
    # renamed CLI) must not ship silently even when the manifest looks clean.
    for path in sorted(DEST.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(DEST).as_posix()
        if rel not in expected and rel != MANIFEST_NAME:
            errors.append(f"orphan file on disk in bundle: {rel}")
    if manifest.get("core_version") != _core_version():
        errors.append(
            f"manifest core_version {manifest.get('core_version')!r} != SKILL.md {_core_version()!r}"
        )
    for msg in errors:
        print(f"sync-substrate: {msg}", file=sys.stderr)
    if errors:
        print("sync-substrate: bundle drifted; run scripts/sync_substrate_assets.py and commit", file=sys.stderr)
        return 1
    print(f"sync-substrate: bundle in sync ({len(expected)} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify parity; exit 1 on drift")
    args = parser.parse_args()
    if args.check:
        return check()
    sync()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
