"""Coverage for this session's new code via IN-PROCESS main() invocation.

The CLIs are exercised elsewhere via subprocess, which coverage.py cannot see (separate process).
These call main() in-process with monkeypatched argv so the CLI bodies + error paths are covered AND
behaviour is asserted (not coverage padding).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str, fname: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / fname)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cg = _load("coupling_graph_cov", "coupling-graph.py")
rd = _load("render_dashboard_cov", "render-dashboard.py")
vfo = _load("vfo_cov", "validate_fleet_outcome.py")


def _pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("from . import b\nfrom .b import thing\nimport os\n")
    (pkg / "b.py").write_text("thing = 1\n")
    return tmp_path


# --- coupling-graph.py: the CLI main() (json + human summary + bad path) ---

def test_coupling_main_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cg", str(_pkg(tmp_path)), "--json"])
    assert cg.main() == 0
    data = json.loads(capsys.readouterr().out)
    assert "clusters" in data and "hubs" in data and "files" in data
    assert data["edges"], data
    assert ["pkg/a.py", "pkg/__init__.py"] in data["edges"]
    assert ["pkg/a.py", "pkg/b.py"] in data["edges"]

    expected_cluster = {"pkg/__init__.py", "pkg/a.py", "pkg/b.py"}
    assert any(expected_cluster <= set(cluster) and len(cluster) >= 3 for cluster in data["clusters"])


def test_coupling_main_human_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cg", str(_pkg(tmp_path))])
    assert cg.main() == 0
    out = capsys.readouterr().out
    assert "files:" in out and "clusters" in out and "hubs" in out


def test_coupling_main_rejects_non_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cg", str(tmp_path / "does-not-exist")])
    with pytest.raises(SystemExit):  # argparse p.error -> SystemExit
        cg.main()


# --- render-dashboard.py: the CLI main() writes the HTML ---

def test_dashboard_main_writes_html(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x-progress.md").write_text("# x\nPHASE: DONE\n")
    out = tmp_path / "o.html"
    monkeypatch.setattr(sys, "argv", ["rd", "--repo", str(tmp_path), "-o", str(out)])
    assert rd.main() == 0
    assert out.exists() and out.read_text().strip()


# --- validate_fleet_outcome.py: the error paths added this session ---

def test_validate_main_malformed_yaml_path(tmp_path, monkeypatch, capsys):
    # exercises the (ValueError, yaml.YAMLError) except added in the close-gaps work (F3 fix)
    doc = tmp_path / "bad-readiness.md"
    doc.write_text("---\nfleet-outcome:\n  m: [unclosed\n---\n")
    monkeypatch.setattr(sys, "argv", ["v", str(doc)])
    rc = vfo.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out and "invalid" in out


def test_validate_main_not_found_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["v", str(tmp_path / "missing-readiness.md")])
    rc = vfo.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out


# ─────────────────────────────────────────────────────────────────────
# Commit 4 — in-process CLI + shape-error coverage for run-archive
# ─────────────────────────────────────────────────────────────────────

vra = _load("vra_cov", "validate_run_archive.py")

from lib import fleet_run as _fr  # noqa: E402


def test_vra_main_no_archives(tmp_path, monkeypatch, capsys):
    """Default scan with no archives → exit 0, friendly message."""
    monkeypatch.setattr(sys, "argv", ["v", "--repo-root", str(tmp_path)])
    rc = vra.main()
    assert rc == 0
    assert "No run-archives" in capsys.readouterr().out


def test_vra_main_quiet_suppresses_ok(tmp_path, monkeypatch, capsys):
    """--quiet: passing archives don't print OK lines."""
    import time

    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    fd = arch / "f.json"; fd.write_text("{}")
    time.sleep(1.05)
    rd = arch / "r.md"; rd.write_text("x")
    _fr.write_manifest(arch, run_id=rid, mission="doc-sync", files=[
        _fr.file_entry_for(fd, arch, kind="findings", producer="r"),
        _fr.file_entry_for(rd, arch, kind="readiness", producer="t"),
    ])
    monkeypatch.setattr(sys, "argv", ["v", "--quiet", str(arch)])
    rc = vra.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" not in out


def test_vra_main_explicit_path_not_a_directory(tmp_path, monkeypatch, capsys):
    not_a_dir = tmp_path / "file.txt"; not_a_dir.write_text("x")
    monkeypatch.setattr(sys, "argv", ["v", str(not_a_dir)])
    rc = vra.main()
    assert rc == 1
    assert "not a directory" in capsys.readouterr().out


def test_vra_main_no_checksums_missing_manifest(tmp_path, monkeypatch, capsys):
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    # No manifest.json written.
    monkeypatch.setattr(sys, "argv", ["v", "--no-checksums", str(arch)])
    rc = vra.main()
    assert rc == 1
    assert "manifest.json missing" in capsys.readouterr().out


def test_vra_main_no_checksums_invalid_json(tmp_path, monkeypatch, capsys):
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    (arch / "manifest.json").write_text("{not json")
    monkeypatch.setattr(sys, "argv", ["v", "--no-checksums", str(arch)])
    rc = vra.main()
    assert rc == 1
    assert "invalid manifest JSON" in capsys.readouterr().out


def test_vra_main_no_checksums_happy(tmp_path, monkeypatch, capsys):
    """--no-checksums on a valid manifest: passes without hashing."""
    import time

    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    fd = arch / "f.json"; fd.write_text("{}")
    time.sleep(1.05)
    rd = arch / "r.md"; rd.write_text("x")
    _fr.write_manifest(arch, run_id=rid, mission="doc-sync", files=[
        _fr.file_entry_for(fd, arch, kind="findings", producer="r"),
        _fr.file_entry_for(rd, arch, kind="readiness", producer="t"),
    ])
    # Tamper after manifest — --no-checksums must NOT catch this.
    fd.write_text("x")
    monkeypatch.setattr(sys, "argv", ["v", "--no-checksums", str(arch)])
    rc = vra.main()
    assert rc == 0


# ─── fleet_run shape-error paths (covers _validate_shape branches) ───


def test_validate_payload_rejects_non_dict():
    errs = _fr.validate_manifest_payload([], check_files_on_disk=False)
    assert any("must be an object" in e for e in errs)


def test_validate_payload_missing_required_fields():
    errs = _fr.validate_manifest_payload({}, check_files_on_disk=False)
    for f in ("schema_version", "run_id", "mission", "created_utc", "files"):
        assert any(f"missing required field '{f}'" in e for e in errs), (f, errs)


def test_validate_payload_wrong_schema_version():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": "9.9",
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("schema_version must be" in e for e in errs), errs


def test_validate_payload_malformed_created_utc():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "yesterday",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("created_utc" in e and "ISO 8601" in e for e in errs), errs


def test_validate_payload_non_list_files():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": "not a list",
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("files must be a non-empty list" in e for e in errs), errs


def test_validate_payload_non_dict_file_entry():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": ["not a dict"],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("must be an object" in e for e in errs), errs


def test_validate_payload_file_entry_missing_fields():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{}],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    for f in ("path", "kind", "sha256", "mtime_utc", "producer", "bytes"):
        assert any(f"missing field '{f}'" in e for e in errs), (f, errs)


def test_validate_payload_absolute_path_rejected():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "/etc/passwd", "kind": "other",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("escapes archive directory" in e for e in errs), errs


def test_validate_payload_malformed_sha256():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "not-hex", "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("sha256 must be 64 hex chars" in e for e in errs), errs


def test_validate_payload_malformed_mtime():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "yesterday",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("mtime_utc not a valid UTC ISO 8601" in e for e in errs), errs


def test_validate_payload_empty_producer():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "   ", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("producer must be a non-empty string" in e for e in errs), errs


def test_validate_payload_negative_bytes():
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": -1,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("bytes must be a non-negative int" in e for e in errs), errs


def test_validate_payload_bool_bytes_rejected():
    """bool is a subclass of int in Python; the lib explicitly excludes it."""
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": True,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("bytes must be a non-negative int" in e for e in errs), errs


def test_validate_payload_ordering_skips_malformed_mtime():
    """The ordering check must skip entries with malformed mtime (those are
    already reported by the shape check; double-reporting would noise the
    output). Pin the silent-skip path."""
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {
                "path": "blind.md", "kind": "blind_fix",
                "sha256": "0"*64, "mtime_utc": "BAD",
                "producer": "r", "bytes": 0,
            },
            {
                "path": "f.json", "kind": "findings",
                "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
                "producer": "r", "bytes": 0,
            },
        ],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    # Shape error reported, but NOT the ordering violation (blind_fix has no
    # parseable mtime so the ordering check skips it).
    assert any("mtime_utc not a valid" in e for e in errs)
    assert not any("ANTI-ANCHORING" in e for e in errs)


# ─── write_manifest optional fields coverage ───


def test_write_manifest_with_optional_fields(tmp_path):
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    f = arch / "x.txt"; f.write_text("x")
    entry = _fr.file_entry_for(f, arch, kind="other", producer="r")
    path = _fr.write_manifest(
        arch, run_id=rid, mission="doc-sync", files=[entry],
        coordinator="claude-code", base_branch="main", notes="a note",
    )
    payload = json.loads(path.read_text())
    assert payload["coordinator"] == "claude-code"
    assert payload["base_branch"] == "main"
    assert payload["notes"] == "a note"


def test_write_manifest_invalid_run_id(tmp_path):
    f = tmp_path / "x"; f.write_text("x")
    with pytest.raises(ValueError, match="invalid run_id"):
        _fr.write_manifest(
            tmp_path, run_id="not-valid", mission="doc-sync",
            files=[_fr.FileEntry(path="x", kind="other", sha256="0"*64,
                                  mtime_utc="2026-06-23T14:18:33Z",
                                  producer="r", bytes=1)],
        )


def test_validate_files_on_disk_skips_missing_path_field(tmp_path):
    """The on-disk validator must gracefully skip entries whose path field is
    missing/non-string (shape check already reported them) instead of raising."""
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [
            {"kind": "findings", "sha256": "0"*64,
             "mtime_utc": "2026-06-23T14:18:33Z", "producer": "r", "bytes": 0},
        ],
    }
    errs = _fr.validate_manifest_payload(payload, archive_root=arch)
    # Shape reports missing path; on-disk check did not raise.
    assert any("missing field 'path'" in e for e in errs)


def test_validate_payload_malformed_run_id_in_manifest(tmp_path):
    """A manifest with a malformed run_id (not matching the format) must be
    rejected. Covers line 339."""
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": "freeform-run-id",
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    assert any("does not match required format" in e for e in errs), errs


def test_validate_payload_ordering_skips_unparseable_iso(monkeypatch):
    """The mtime regex matches but fromisoformat raises ValueError (impossible
    given the regex but defensive). Cover the except branch by monkeypatching
    fromisoformat to raise."""
    import datetime as _dt
    real = _dt.datetime.fromisoformat

    def boom(s):
        if "2026-06-23T14:18:33" in s:
            raise ValueError("synthetic")
        return real(s)

    monkeypatch.setattr(_fr, "datetime", type("D", (), {
        "fromisoformat": staticmethod(boom),
        "now": staticmethod(_dt.datetime.now),
        "strptime": staticmethod(_dt.datetime.strptime),
        "fromtimestamp": staticmethod(_dt.datetime.fromtimestamp),
    }))
    rid = _fr.allocate_run_id("doc-sync")
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "x.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, check_files_on_disk=False)
    # Doesn't crash; no ordering errors for this single entry.
    assert not any("ANTI-ANCHORING" in e for e in errs)


def test_validate_files_on_disk_file_not_found(tmp_path):
    """Manifest claims a file at a path that doesn't exist. Cover lines 507-508."""
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": "does-not-exist.json", "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, archive_root=arch)
    assert any("file not found at" in e for e in errs), errs


def test_validate_files_on_disk_non_string_path(tmp_path):
    """A file entry whose path field is non-string is skipped by the on-disk
    check (shape check already reported it). Covers line 493."""
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": [{
            "path": 123, "kind": "findings",
            "sha256": "0"*64, "mtime_utc": "2026-06-23T14:18:33Z",
            "producer": "r", "bytes": 0,
        }],
    }
    errs = _fr.validate_manifest_payload(payload, archive_root=arch)
    # Shape reports it; on-disk silently skips. No "file not found" because the
    # on-disk loop continues before trying to resolve.
    assert not any("file not found at" in e for e in errs)


# ─── validate_run_archive.py CLI: in-process coverage of remaining branches ───


def test_vra_collect_archives_returns_empty_when_no_fleet_dir(tmp_path):
    archives = vra.collect_archives(tmp_path)
    assert archives == []


def test_vra_main_reports_failure_lines(tmp_path, monkeypatch, capsys):
    """Cover the FAIL branch lines (121-124): print FAIL header + indented
    error lines."""
    import time
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    fd = arch / "f.json"; fd.write_text("{}")
    time.sleep(1.05)
    rd = arch / "r.md"; rd.write_text("x")
    _fr.write_manifest(arch, run_id=rid, mission="doc-sync", files=[
        _fr.file_entry_for(fd, arch, kind="findings", producer="r"),
        _fr.file_entry_for(rd, arch, kind="readiness", producer="t"),
    ])
    # Tamper after manifest written so checksum fails.
    fd.write_text("y" * 50)
    monkeypatch.setattr(sys, "argv", ["v", str(arch)])
    rc = vra.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert f"FAIL {arch.resolve()}" in out
    assert "  - " in out


def test_validate_files_on_disk_skips_non_dict_entry(tmp_path):
    """The on-disk loop must also skip non-dict entries (mirroring the
    shape check's tolerance). Cover line 495's continue."""
    rid = _fr.allocate_run_id("doc-sync")
    arch = _fr.ensure_archive_dir(tmp_path, rid)
    payload = {
        "schema_version": _fr.SCHEMA_VERSION,
        "run_id": rid,
        "mission": "doc-sync",
        "created_utc": "2026-06-23T14:18:33Z",
        "files": ["not a dict entry"],
    }
    errs = _fr.validate_manifest_payload(payload, archive_root=arch)
    # Shape reports it; on-disk loop did not raise.
    assert any("must be an object" in e for e in errs)


def test_vra_collect_archives_when_fleet_runs_doesnt_exist(tmp_path):
    """Line 39: when .fleet/runs/ doesn't exist, return []. Covers the early
    return — already tested indirectly but pin it directly."""
    # No .fleet/runs/ directory at all
    assert vra.collect_archives(tmp_path) == []
    # Even when .fleet/ exists without .fleet/runs/
    (tmp_path / ".fleet").mkdir()
    assert vra.collect_archives(tmp_path) == []


def test_vra_collect_archives_returns_sorted_run_id_dirs(tmp_path):
    """Cover line 39's `return sorted(...)` branch: .fleet/runs/ exists with
    run-id-shaped directories AND operator scratch dirs, returns only the
    valid run_id dirs, sorted."""
    base = tmp_path / ".fleet" / "runs"
    base.mkdir(parents=True)
    # Three valid run_ids out of timestamp order to exercise sort().
    valid_a = base / "20260623T141833Z-doc-sync-aaaaaa"
    valid_b = base / "20260101T000000Z-doc-sync-bbbbbb"
    valid_c = base / "20260315T120000Z-doc-sync-cccccc"
    for d in (valid_a, valid_b, valid_c):
        d.mkdir()
    # Operator scratch should be filtered out.
    (base / "scratch-notes").mkdir()
    # A file (not a dir) under .fleet/runs/ — must also be skipped.
    (base / "README.md").write_text("notes")
    archives = vra.collect_archives(tmp_path)
    paths = [p.name for p in archives]
    assert paths == [valid_b.name, valid_c.name, valid_a.name], paths


# ═════════════════════════════════════════════════════════════════════════
# Commits 1-3 — coverage for error-path branches added since baseline 100%
# ═════════════════════════════════════════════════════════════════════════

from lib import verify_findings as _vf  # noqa: E402
from lib import stop_verify as _sv  # noqa: E402

sv_cli = _load("sv_cli_cov", "stop_verify.py")
mc_mod = _load("mc_cov", "mutation_check.py")


def _vf_min_finding(**overrides):
    base = {
        "id": "F-001",
        "severity": "high",
        "category": "bug",
        "claim": "Real claim text describing the bug.",
        "evidence": {
            "file_path": "src/main.py",
            "quoted_line": "x = 1",
        },
        "fix_alternatives": [
            {"label": "A", "description": "Do X", "effort": "moderate"},
        ],
        "confidence": 85,
        "fix_strategy": "ask",
    }
    base.update(overrides)
    return base


def _vf_min_doc(**overrides):
    base = {
        "schema_version": "1.0",
        "mission": "adversarial-review-and-fix",
        "review_id": "r1",
        "findings": [_vf_min_finding()],
        "verdict": {"decision": "approve", "reasoning": "ok"},
    }
    base.update(overrides)
    return base


# --- verify_findings.py: validate_findings_doc error branches ---

def test_vf_mission_blank_string_rejected():
    """Line 90: mission='  ' (whitespace-only) must produce the
    'mission must be a non-empty string' error."""
    errs = _vf.validate_findings_doc(_vf_min_doc(mission="   "))
    assert any("mission must be a non-empty string" in e for e in errs), errs


def test_vf_mission_non_string_rejected():
    """Line 90 (companion): mission as a non-string is rejected with the same
    schema-discipline message."""
    errs = _vf.validate_findings_doc(_vf_min_doc(mission=42))
    assert any("mission must be a non-empty string" in e for e in errs), errs


def test_vf_findings_not_a_list_rejected():
    """Line 104: findings must be a list; a string is rejected by type name."""
    errs = _vf.validate_findings_doc(_vf_min_doc(findings="not a list"))
    assert any("findings must be a list, got str" in e for e in errs), errs


def test_vf_verdict_not_an_object_rejected():
    """Line 113: verdict must be a dict object — a string fails the gate."""
    errs = _vf.validate_findings_doc(_vf_min_doc(verdict="approve"))
    assert any("verdict must be an object" in e for e in errs), errs


def test_vf_finding_entry_not_a_dict_rejected():
    """Line 135: a findings[idx] that isn't a dict short-circuits with a
    type-name error and stops downstream key checks for that entry."""
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=["not a dict"]))
    assert any("findings[0]: must be an object, got str" in e for e in errs), errs


def test_vf_finding_missing_required_field():
    """Line 139: each missing top-level finding field is independently
    reported with a 'missing required field' error."""
    bare = {"id": "F-001"}
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bare]))
    for field in ("severity", "category", "claim", "evidence", "fix_alternatives",
                  "confidence", "fix_strategy"):
        assert any(f"missing required field '{field}'" in e for e in errs), (field, errs)


def test_vf_finding_id_pattern_violation():
    """Line 144: id 'lowercase-1' fails the ^[A-Z]+-[0-9]+$ schema regex."""
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[_vf_min_finding(id="lowercase-1")]))
    assert any("id must match ^[A-Z]+-[0-9]+$" in e for e in errs), errs


def test_vf_finding_claim_blank_rejected():
    """Line 163: claim '   ' is whitespace-only and must be rejected, so a
    reviewer can't ship an empty claim that bypasses the audit."""
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[_vf_min_finding(claim="   ")]))
    assert any("claim must be a non-empty string" in e for e in errs), errs


def test_vf_evidence_omission_then_other_violations_still_reported():
    """Line 167 (`pass # already reported`): a finding with evidence key
    omitted produces ONE 'missing required field evidence' error but does NOT
    crash the downstream alts/conf checks — they continue and surface their
    own errors."""
    f = _vf_min_finding(confidence=999)
    f.pop("evidence")
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[f]))
    assert any("missing required field 'evidence'" in e for e in errs), errs
    # Confidence error still surfaces — the per-finding loop didn't short-circuit.
    assert any("confidence must be int 0-100" in e for e in errs), errs


def test_vf_evidence_not_a_dict_rejected():
    """Line 169: evidence='not a dict' fails the 'evidence must be an object'
    check — exactly the doctrine line."""
    errs = _vf.validate_findings_doc(
        _vf_min_doc(findings=[_vf_min_finding(evidence="not a dict")])
    )
    assert any("evidence must be an object" in e for e in errs), errs


def test_vf_evidence_file_path_blank_rejected():
    """Line 177: evidence.file_path='  ' (whitespace) is rejected — an empty
    path can't be grep-verified, so we refuse it at schema time."""
    bad = _vf_min_finding(evidence={"file_path": "   ", "quoted_line": "x"})
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    assert any("evidence.file_path must be a non-empty string" in e for e in errs), errs


def test_vf_fix_alternatives_omission_then_other_violations_still_reported():
    """Line 191 (`pass`): omitting fix_alternatives entirely reports a
    'missing required field' error but does NOT block per-finding processing."""
    f = _vf_min_finding(confidence=999)
    f.pop("fix_alternatives")
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[f]))
    assert any("missing required field 'fix_alternatives'" in e for e in errs), errs
    assert any("confidence must be int 0-100" in e for e in errs), errs


def test_vf_fix_alternative_entry_not_a_dict_rejected():
    """Lines 201-202: a fix_alternatives[j] that isn't a dict is reported and
    the loop CONTINUES (no key checks attempted on the non-dict)."""
    bad = _vf_min_finding(fix_alternatives=["not a dict"])
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    assert any("fix_alternatives[0] must be an object" in e for e in errs), errs
    # The 'continue' on line 202 means no follow-on missing-key errors for this entry.
    assert not any("fix_alternatives[0] missing 'label'" in e for e in errs), errs


def test_vf_fix_alternative_missing_keys_reported():
    """Line 205: each missing key in a fix_alternatives entry produces its own
    'missing' error (label/description/effort)."""
    bad = _vf_min_finding(fix_alternatives=[{"label": "A"}])  # missing description, effort
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    for key in ("description", "effort"):
        assert any(f"fix_alternatives[0] missing '{key}'" in e for e in errs), (key, errs)


def test_vf_fix_alternative_label_pattern_violation():
    """Line 209: label 'AB' fails the single-uppercase ^[A-Z]$ pattern."""
    bad = _vf_min_finding(
        fix_alternatives=[{"label": "AB", "description": "x", "effort": "minimal"}]
    )
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    assert any("label must match ^[A-Z]$" in e for e in errs), errs


def test_vf_fix_alternative_effort_invalid_rejected():
    """Line 220: effort='huge' is not in the allowed
    {minimal, moderate, large} set — reject with the enumeration error."""
    bad = _vf_min_finding(
        fix_alternatives=[{"label": "A", "description": "x", "effort": "huge"}]
    )
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    assert any("effort must be one of" in e for e in errs), errs


def test_vf_fix_alternative_description_blank_rejected():
    """Line 227: description='   ' (whitespace-only) is rejected — no empty
    fix descriptions allowed."""
    bad = _vf_min_finding(
        fix_alternatives=[{"label": "A", "description": "   ", "effort": "minimal"}]
    )
    errs = _vf.validate_findings_doc(_vf_min_doc(findings=[bad]))
    assert any("description must be non-empty" in e for e in errs), errs


# --- verify_finding_against_source: OSError read branch ---

def test_vf_verify_unreadable_source_downgrades(tmp_path, monkeypatch):
    """OSError raised while reading the cited file must be caught and convert
    the finding to verified=False with an 'unreadable:' reason."""
    src = tmp_path / "src" / "main.py"
    src.parent.mkdir(parents=True)
    src.write_text("contents")
    real_open = Path.open

    def boom(self, *a, **kw):
        if self.name == "main.py":
            raise OSError("synthetic permission denied")
        return real_open(self, *a, **kw)

    monkeypatch.setattr(Path, "open", boom)
    finding = _vf_min_finding(
        evidence={"file_path": "src/main.py", "quoted_line": "contents"}
    )
    _vf.verify_finding_against_source(finding, repo_root=tmp_path)
    assert finding["verified"] is False
    assert finding["verify_reason"].startswith("unreadable:"), finding


# --- verify_findings_doc: defensive non-list / non-dict branches ---

def test_vf_verify_findings_doc_with_non_list_findings_returns_zero(tmp_path):
    """Line 340: when doc['findings'] isn't a list the summary returns
    all-zero counts (no crash). This protects the verify pass from a
    structurally broken doc that somehow got past the structural gate."""
    summary = _vf.verify_findings_doc({"findings": "not a list"}, repo_root=tmp_path)
    assert summary == {
        "total_findings": 0,
        "verified_findings": 0,
        "unverified_findings": 0,
        "unverified_ids": [],
        "auto_applicable_findings": 0,
        "human_gated_findings": 0,
    }


def test_vf_verify_findings_doc_skips_non_dict_findings(tmp_path):
    """Line 356: a non-dict entry inside the findings list is silently
    skipped — the loop continues, total_findings reflects the list length but
    the non-dict contributes nothing to verified/unverified counts."""
    src = tmp_path / "code.py"; src.write_text("x = 1\n")
    good = _vf_min_finding(evidence={"file_path": "code.py", "quoted_line": "x = 1"})
    doc = {"findings": ["not a dict", good]}
    summary = _vf.verify_findings_doc(doc, repo_root=tmp_path)
    assert summary["total_findings"] == 2
    assert summary["verified_findings"] == 1
    assert summary["unverified_findings"] == 0


# ─────────────────────────────────────────────────────────────────────
# scripts/lib/stop_verify.py — defensive FS error branches
# ─────────────────────────────────────────────────────────────────────


def test_sv_iter_glob_safe_swallows_value_error(tmp_path, monkeypatch):
    """Lines 201-205: Path.glob may raise ValueError for invalid patterns
    (absolute globs on older Pythons). _iter_glob_safe must swallow and
    return nothing, so a malformed config never crashes the gate."""
    real_glob = Path.glob

    def boom_glob(self, pattern, *a, **kw):
        raise ValueError("Non-relative patterns are unsupported")

    monkeypatch.setattr(Path, "glob", boom_glob)
    out = list(_sv._iter_glob_safe(tmp_path, "/absolute/glob"))
    assert out == []
    # Sanity: the unpatched glob behaves normally.
    monkeypatch.setattr(Path, "glob", real_glob)
    assert isinstance(list(_sv._iter_glob_safe(tmp_path, "*")), list)


def test_sv_iter_glob_safe_swallows_os_error(tmp_path, monkeypatch):
    """Line 201 (companion): an OSError from Path.glob (e.g. permission
    denied walking a hostile FS) must be swallowed."""
    def boom(self, pattern, *a, **kw):
        raise PermissionError("no read")

    monkeypatch.setattr(Path, "glob", boom)
    assert list(_sv._iter_glob_safe(tmp_path, "*")) == []


def test_sv_mtime_age_returns_none_on_broken_symlink(tmp_path):
    """Lines 211-212: a broken symlink raises FileNotFoundError on stat();
    _mtime_age must return None (treated as 'no fresh evidence here') rather
    than crash the detector loop."""
    target = tmp_path / "nope"
    link = tmp_path / "broken-link"
    link.symlink_to(target)  # target doesn't exist
    assert _sv._mtime_age(link, now=0.0) is None


def test_sv_detect_readiness_swallows_unreadable(tmp_path):
    """Lines 265-266: a path matching the readiness glob whose read_text
    raises OSError (here: a directory at that path, not a file) is silently
    skipped — no crash, no false-positive evidence."""
    docs = tmp_path / "docs"; docs.mkdir()
    # Create a DIRECTORY where the glob expects a file. Path.read_text on a
    # directory raises IsADirectoryError (an OSError subclass).
    bogus = docs / "x-readiness.md"
    bogus.mkdir()
    cfg = _sv.StopVerifyConfig(repo_root=tmp_path).normalised()
    import time as _t
    # Touch the mtime to be fresh
    hits = _sv.detect_readiness_evidence(cfg, _t.time())
    assert hits == []  # OSError caught -> no hit recorded


def test_sv_detect_e2e_artifact_skips_stale(tmp_path):
    """Line 365: an e2e artifact older than the freshness window must hit the
    `if age is None or age > cfg.window_sec: continue` branch and produce no
    hit. Without this skip, last week's screenshots would 'prove' today's run."""
    import os as _os
    shot_dir = tmp_path / "screenshots"; shot_dir.mkdir()
    stale = shot_dir / "old.png"; stale.write_bytes(b"\x89PNG")
    # Force mtime to 2 hours ago; default window is 30 minutes.
    old_t = _os.path.getmtime(stale) - 2 * 60 * 60
    _os.utime(stale, (old_t, old_t))
    cfg = _sv.StopVerifyConfig(repo_root=tmp_path).normalised()
    import time as _t
    hits = _sv.detect_e2e_artifact_evidence(cfg, _t.time())
    assert [h for h in hits if h.kind == "e2e_artifact"] == []


def test_sv_detect_e2e_artifact_deduplicates_by_parent_dir(tmp_path):
    """Lines 365 & 367: when two e2e artifacts share a parent dir, the second
    must hit the `if path.parent in seen_dirs: continue` branch and only one
    EvidenceHit per parent is emitted (cap on report noise)."""
    shot_dir = tmp_path / "screenshots"
    shot_dir.mkdir()
    # Two PNGs in the same dir; both fresh.
    (shot_dir / "a.png").write_bytes(b"\x89PNG")
    (shot_dir / "b.png").write_bytes(b"\x89PNG")
    cfg = _sv.StopVerifyConfig(repo_root=tmp_path).normalised()
    import time as _t
    hits = _sv.detect_e2e_artifact_evidence(cfg, _t.time())
    # Exactly ONE hit because the second is deduplicated by parent dir.
    e2e_hits = [h for h in hits if h.kind == "e2e_artifact"]
    assert len(e2e_hits) == 1, [h.path for h in hits]


def test_sv_read_capped_skips_oversized_ledger(tmp_path):
    """_read_capped over-cap branch: a progress ledger larger than
    MAX_LEDGER_BYTES is treated as no-evidence rather than OOM-read."""
    docs = tmp_path / "docs"
    docs.mkdir()
    big = docs / "x-progress.md"
    big.write_bytes(b"EVID=true\n" + b"x" * (_sv.MAX_LEDGER_BYTES + 1))
    cfg = _sv.StopVerifyConfig(repo_root=tmp_path).normalised()
    import time as _t
    assert _sv.detect_progress_flag_evidence(cfg, _t.time()) == []


def test_sv_read_capped_skips_oversized_verify_summary(tmp_path):
    """Verify-summary detector skips an oversized summary JSON (raw is None)."""
    run = tmp_path / ".fleet" / "runs" / "20260101T000000Z-doc-sync-abc123"
    run.mkdir(parents=True)
    summary = run / "verify-summary.json"
    summary.write_bytes(
        b'{"unverified_findings": 0}\n' + b" " * (_sv.MAX_SUMMARY_BYTES + 1)
    )
    cfg = _sv.StopVerifyConfig(repo_root=tmp_path).normalised()
    import time as _t
    assert _sv.detect_verify_summary_evidence(cfg, _t.time()) == []


# ─────────────────────────────────────────────────────────────────────
# scripts/stop_verify.py CLI — config-loading + explain branches
# ─────────────────────────────────────────────────────────────────────


def test_sv_cli_isatty_returns_empty_hook_input(monkeypatch):
    """Line 62: when stdin is a TTY (operator running by hand) _read_hook_input
    short-circuits to {} so a no-stdin invocation works."""
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    assert sv_cli._read_hook_input() == {}


def test_sv_cli_stdin_read_raises_os_error_returns_empty(monkeypatch):
    """Lines 65-66: when sys.stdin.read() raises OSError, _read_hook_input
    swallows it and returns {} — the hook never crashes the worker."""
    class FakeStdin:
        def isatty(self):
            return False
        def read(self):
            raise OSError("broken pipe")
    monkeypatch.setattr(sys, "stdin", FakeStdin())
    assert sv_cli._read_hook_input() == {}


def test_sv_cli_resolve_repo_falls_back_to_cwd(monkeypatch, tmp_path):
    """Line 97: with no --repo arg, no CLAUDE_PROJECT_DIR env, and no cwd in
    hook_input, _resolve_repo returns Path.cwd() — the documented last-resort
    fallback."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = sv_cli._resolve_repo(None, {})
    assert resolved == Path.cwd()


def test_sv_cli_explain_prints_counts_and_evidence(tmp_path, monkeypatch, capsys):
    """Lines 125-126 and 128-134: --explain on a verdict carrying evidence
    prints the per-kind counts AND an indented evidence row per hit (newest
    first), to stderr. Drive it through a real ALLOW evaluate() so the codepath
    runs end-to-end."""
    docs = tmp_path / "docs"; docs.mkdir()
    (docs / "x-progress.md").write_text("PHASE: BUILD\nEVID=true\nWT_CLEAN=true\n")
    monkeypatch.delenv("FLEET_DISABLE_STOP_VERIFY", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "sv", "--repo", str(tmp_path),
        "--window-min", "60",
        "--explain",
    ])
    # Patch stdin so _read_hook_input returns {} via TTY path.
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    rc = sv_cli.main()
    assert rc == 0
    err = capsys.readouterr().err
    # Counts and at least one evidence row printed to stderr.
    assert "stop-verify: ALLOW" in err
    assert "evid_flag" in err or "wt_clean_flag" in err
    assert "evidence (newest first):" in err
    # Indented [kind] row present.
    assert "[evid_flag]" in err or "[wt_clean_flag]" in err


# ─────────────────────────────────────────────────────────────────────
# scripts/mutation_check.py — caught branch + main() CLI
# ─────────────────────────────────────────────────────────────────────


def _mc_require_clean(rel: str):
    import subprocess as _sp
    r = _sp.run(
        ["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True
    )
    if r.stdout.strip():
        pytest.skip(f"{rel} has uncommitted changes; mutation-check needs it clean")


def test_mc_run_reports_caught_when_guard_fails(tmp_path, capsys, monkeypatch):
    """Lines 105-107: a mutation whose guard tests FAIL counts as 'caught' and
    is printed with the 'caught' label (when not quiet). Pin the positive path
    by stubbing _run_guards to True (=guard failed = mutation caught) — we are
    proving the gate's accounting of a caught mutation, not the subprocess
    plumbing (which test_mutation_check.py already exercises end-to-end)."""
    _mc_require_clean("README.md")
    import yaml as _yaml
    manifest = tmp_path / "m.yaml"
    manifest.write_text(_yaml.safe_dump({"mutations": [
        {
            "id": "real-catch",
            "file": "README.md",
            "find": "autonomous-fleet",
            "replace": "AUTOFLEET-REMOVED",
            "guards": ["unused-because-stubbed"],
        }
    ]}))
    monkeypatch.setattr(mc_mod, "_run_guards", lambda _guards: True)
    rc = mc_mod.run(manifest, None, quiet=False)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "caught" in out and "real-catch" in out
    # README restored by the per-mutation finally block.
    assert "autonomous-fleet" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_mc_run_quiet_suppresses_caught_print(tmp_path, capsys, monkeypatch):
    """Line 106 negative complement: with quiet=True the caught-branch must
    NOT print the 'caught   <id>' line — only survivors/stale are shown."""
    _mc_require_clean("README.md")
    import yaml as _yaml
    manifest = tmp_path / "m.yaml"
    manifest.write_text(_yaml.safe_dump({"mutations": [
        {
            "id": "quiet-catch",
            "file": "README.md",
            "find": "autonomous-fleet",
            "replace": "AUTOFLEET-REMOVED",
            "guards": ["unused"],
        }
    ]}))
    monkeypatch.setattr(mc_mod, "_run_guards", lambda _guards: True)
    rc = mc_mod.run(manifest, None, quiet=True)
    out = capsys.readouterr().out
    assert rc == 0
    assert "caught     quiet-catch" not in out


def test_mc_main_entry_point_with_tmp_manifest(tmp_path, monkeypatch):
    """Lines 125-133: main() parses --manifest, --id and -q; calls run() and
    the finally block invokes _restore_all() unconditionally. Drive it with a
    caught-mutation manifest (guards stubbed) so main() returns 0 AND the
    --id filter actually narrows the run set (one of two manifest entries
    runs)."""
    _mc_require_clean("README.md")
    import yaml as _yaml
    manifest = tmp_path / "m.yaml"
    manifest.write_text(_yaml.safe_dump({"mutations": [
        {
            "id": "main-caught",
            "file": "README.md",
            "find": "autonomous-fleet",
            "replace": "AUTOFLEET-REMOVED",
            "guards": ["unused"],
        },
        {
            "id": "other-id",
            "file": "README.md",
            "find": "autonomous-fleet",
            "replace": "X",
            "guards": ["unused"],
        }
    ]}))
    monkeypatch.setattr(mc_mod, "_run_guards", lambda _guards: True)
    monkeypatch.setattr(sys, "argv", [
        "mutation_check", "--manifest", str(manifest),
        "--id", "main-caught", "-q",
    ])
    assert mc_mod.main() == 0
    # README restored by the finally block.
    assert "autonomous-fleet" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_mc_main_finally_restores_active_files_on_exception(tmp_path, monkeypatch):
    """Lines 132-133: main()'s finally block must call _restore_all() even
    when run() raises. We seed _ACTIVE with a tmp file pretending to be a
    mid-flight mutation, make run() raise, and assert the tmp file is
    restored."""
    probe = tmp_path / "probe.txt"
    probe.write_text("ORIGINAL")
    mc_mod._ACTIVE[probe] = "ORIGINAL"
    probe.write_text("MUTATED")

    def boom(*a, **kw):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(mc_mod, "run", boom)
    monkeypatch.setattr(sys, "argv", ["mutation_check"])
    with pytest.raises(RuntimeError, match="synthetic"):
        mc_mod.main()
    # finally clause invoked _restore_all() and the probe is restored.
    assert probe.read_text() == "ORIGINAL"
    assert probe not in mc_mod._ACTIVE
