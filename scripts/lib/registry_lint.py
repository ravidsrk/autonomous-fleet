"""Consistency checks for the fleet mission registry and shipped skill catalogs."""

from __future__ import annotations

import hashlib
import json
import re
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Mapping

import yaml

from .fleet_registry import MISSIONS

LOCAL_LOCK_SOURCE = "ravidsrk/autonomous-fleet"
_MISSION_COMPONENT_RE = re.compile(r"fleet-component:\s*[\"']?mission[\"']?")

# Fields that, if present on a lock row, count as pinning an external source to a
# concrete revision. The external `npx skills` installer records a bare repo slug
# ("anthropics/skills") with no revision, so without one of these the vendored copy
# is unpinned and can drift silently against upstream.
_PIN_FIELDS = ("ref", "commit", "tag", "sha")


def content_hash(skill_dir: Path) -> str:
    """Deterministic sha256 over a skill directory's tracked content.

    Hashes every regular file under ``skill_dir`` in sorted POSIX-relative-path
    order, mixing in the path itself so a rename changes the digest. This is the
    canonical hash the lock's ``computedHash`` values are reconciled against; it
    is self-consistent (recomputable offline) rather than a reproduction of the
    external installer's opaque hashing.
    """
    digest = hashlib.sha256()
    files = sorted(p for p in skill_dir.rglob("*") if p.is_file())
    for path in files:
        rel = path.relative_to(skill_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def shipped_missions(
    missions: Mapping[str, Mapping[str, Any]] = MISSIONS,
) -> dict[str, Mapping[str, Any]]:
    return {
        mission_id: row
        for mission_id, row in missions.items()
        if row.get("shipped") is True
    }


def _skill_dirs_on_disk(root: Path) -> set[str]:
    return {path.parent.name for path in (root / "skills").glob("*/SKILL.md")}


def _mission_skill_dirs_on_disk(root: Path) -> set[str]:
    dirs: set[str] = set()
    for skill_path in sorted((root / "skills").glob("*/SKILL.md")):
        text = skill_path.read_text(encoding="utf-8")
        if _MISSION_COMPONENT_RE.search(text):
            dirs.add(skill_path.parent.name)
    return dirs


def lint_shipped_mission_dirs(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    errors: list[str] = []
    shipped = shipped_missions(missions)
    shipped_dirs = {str(row["skill_dir"]) for row in shipped.values()}

    for mission_id, row in shipped.items():
        skill_dir = str(row["skill_dir"])
        skill_file = root / "skills" / skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(
                f"{mission_id}: shipped:true points to missing skills/{skill_dir}/SKILL.md"
            )

    for skill_dir in sorted(_mission_skill_dirs_on_disk(root) - shipped_dirs):
        errors.append(
            f"skills/{skill_dir}/SKILL.md is a mission skill but has no shipped:true registry row"
        )

    return errors


def lint_catalog_mentions(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    errors: list[str] = []
    catalogs = {
        "README.md": root / "README.md",
        "skills/autonomous-fleet/SKILL.md": root / "skills" / "autonomous-fleet" / "SKILL.md",
    }

    for label, path in catalogs.items():
        if not path.is_file():
            errors.append(f"{label}: missing catalog file")
            continue
        text = path.read_text(encoding="utf-8")
        for mission_id in sorted(shipped_missions(missions)):
            if mission_id not in text:
                errors.append(f"{label}: missing shipped mission {mission_id}")

    return errors


def _load_lock_skills(root: Path) -> tuple[dict[str, Any], list[str]]:
    lock_path = root / "skills-lock.json"
    if not lock_path.is_file():
        return {}, ["skills-lock.json: missing"]
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        return {}, [f"skills-lock.json: invalid JSON: {exc.msg}"]
    skills = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(skills, dict):
        return {}, ["skills-lock.json: missing skills mapping"]
    return skills, []


def _local_lock_skill_dirs(skills: Mapping[str, Any]) -> set[str]:
    dirs: set[str] = set()
    for name, row in skills.items():
        source = row.get("source") if isinstance(row, dict) else None
        if source in (None, LOCAL_LOCK_SOURCE):
            dirs.add(name)
    return dirs


def lint_skills_lock(root: Path) -> list[str]:
    skills, errors = _load_lock_skills(root)
    if errors:
        return errors

    # Skills installed from another source (e.g. anthropics/skills -> skill-creator,
    # which CI vendors into skills/) are legitimately on disk without a local lock row.
    # Exclude them from the on-disk set so the check stays apples-to-apples with the
    # local-source lock dirs; only fleet-owned drift should surface here.
    external = {
        name
        for name, row in skills.items()
        if isinstance(row, dict) and row.get("source") not in (None, LOCAL_LOCK_SOURCE)
    }
    expected = _skill_dirs_on_disk(root) - external
    actual = _local_lock_skill_dirs(skills)
    missing = sorted(expected - actual)
    stale = sorted(actual - expected)

    if missing:
        errors.append(f"skills-lock.json: missing shipped skill dirs: {', '.join(missing)}")
    if stale:
        errors.append(f"skills-lock.json: stale skill dirs not on disk: {', '.join(stale)}")

    return errors


def lint_lock_hashes(root: Path) -> list[str]:
    """Verify each locked ``computedHash`` matches the on-disk skill content.

    Recomputes :func:`content_hash` for every locally-sourced skill row that
    carries a ``computedHash`` and fails on any drift. Rows without a hash (e.g.
    externally-vendored skills or minimal synthetic fixtures) are skipped here;
    directory-name reconciliation is handled by :func:`lint_skills_lock`.
    """
    skills, errors = _load_lock_skills(root)
    if errors:
        return errors

    for name in sorted(skills):
        row = skills[name]
        if not isinstance(row, dict):
            continue
        if row.get("source") not in (None, LOCAL_LOCK_SOURCE):
            continue
        expected = row.get("computedHash")
        if not isinstance(expected, str):
            continue
        skill_dir = root / "skills" / name
        if not (skill_dir / "SKILL.md").is_file():
            errors.append(
                f"skills-lock.json: {name} has computedHash but no skills/{name}/ on disk"
            )
            continue
        actual = content_hash(skill_dir)
        if actual != expected:
            errors.append(
                f"skills-lock.json: {name} computedHash mismatch "
                f"(locked {expected[:12]}…, on disk {actual[:12]}…); "
                f"refresh the lock or revert the content change"
            )

    return errors


def lint_external_source_pins(root: Path) -> list[str]:
    """Flag external lock rows that are not pinned to a concrete revision.

    A bare ``"anthropics/skills"`` slug tracks a moving branch; require a
    ``ref``/``commit``/``tag``/``sha`` so the vendored copy is reproducible.
    """
    skills, errors = _load_lock_skills(root)
    if errors:
        return errors

    for name in sorted(skills):
        row = skills[name]
        if not isinstance(row, dict):
            continue
        source = row.get("source")
        if source in (None, LOCAL_LOCK_SOURCE):
            continue
        pin_value = next(
            (row[field] for field in _PIN_FIELDS if isinstance(row.get(field), str) and row[field]),
            None,
        )
        if not pin_value:
            errors.append(
                f"skills-lock.json: external source {source!r} for {name} is not pinned "
                f"(add one of {', '.join(_PIN_FIELDS)})"
            )
            continue
        upper = pin_value.upper()
        if "TODO" in upper or "PLACEHOLDER" in upper:
            errors.append(
                f"skills-lock.json: external source {source!r} for {name} uses placeholder pin {pin_value!r}"
            )

    return errors


def lint_no_skill_version_literals_in_tests(root: Path) -> list[str]:
    """Tests hard-coding a CURRENT skill's version break on every routine bump
    (ebd33d3, PR #112). Precisely: flag `version: "X.Y.Z"` literals whose X.Y.Z
    equals any version in skills-lock.json today. Self-contained fixture
    frontmatter (conventionally `0.0.1`-style) and pinned schema versions are
    unaffected (issue #90)."""
    errors: list[str] = []
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return errors
    skills, load_errors = _load_lock_skills(root)
    if load_errors:
        return errors  # lock problems are lint_skills_lock's job
    current = {
        row.get("version")
        for row in skills.values()
        if isinstance(row, dict) and isinstance(row.get("version"), str)
    }
    patterns = {v: re.compile(r'(?<!schema_)version: "' + re.escape(v) + '"') for v in current}
    for path in sorted(tests_dir.glob("*.py")):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for v, pat in patterns.items():
                if pat.search(line):
                    errors.append(
                        f"{path.relative_to(root)}:{i}: literal of CURRENT skill version "
                        f"{v!r} in a test — breaks on the next bump (use a version-agnostic "
                        f"pattern; see CONTRIBUTING 'Skill versioning policy')"
                    )
    return errors


_ROUTING_DOCS = (
    "skills/autonomous-fleet/SKILL.md",
    "skills/autonomous-fleet/references/missions.md",
    "skills/fleet-program/SKILL.md",
    "skills/fleet-program/references/campaigns.md",
    "skills/fleet-program/references/programs.md",
    "skills/autonomous-fleet-core/references/community-skills.md",
)

_EXPLORATORY_MARKERS = ("exploratory", "archived", "demoted", "not yet", "pending promotion")


_ADAPTER_CONTRACT = "skills/autonomous-fleet-core/references/adapter-contract.md"
_COPY_SPAN = 160  # chars of canonical text that count as a re-inlined copy


def lint_adapter_contract_single_source(root: Path) -> list[str]:
    """Adapters must POINT at the shared contract, never re-inline it
    (issue #89): every adapter references adapter-contract.md, and no
    adapter contains a >=_COPY_SPAN-char verbatim span of it."""
    errors: list[str] = []
    adapters = sorted(root.glob("skills/autonomous-fleet-adapter-*/SKILL.md"))
    if not adapters:
        return errors  # fixture/minimal repos without adapters need no contract
    canon_path = root / _ADAPTER_CONTRACT
    if not canon_path.is_file():
        return [f"{_ADAPTER_CONTRACT}: missing canonical adapter contract"]
    canon = " ".join(canon_path.read_text(encoding="utf-8").split())
    # stride 1 (codex on #130): a sampled stride left 160-198 char re-inlines
    # startable between windows; sizes are small enough for the exact scan.
    spans = [canon[i:i + _COPY_SPAN] for i in range(0, max(1, len(canon) - _COPY_SPAN + 1))]
    for path in adapters:
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        if "adapter-contract.md" not in text:
            errors.append(f"{rel}: does not reference references/adapter-contract.md (issue #89)")
        if "CONTINUE_WORKER binding:" not in text:
            errors.append(
                f"{rel}: missing its 'CONTINUE_WORKER binding:' line — the one "
                f"runtime-specific part of the shared contract (issue #89)"
            )
        for span in spans:
            if span in flat:
                errors.append(
                    f"{rel}: re-inlines a {_COPY_SPAN}-char span of adapter-contract.md "
                    f"(single-source it; drift lint, issue #89)"
                )
                break
    return errors


def lint_mission_state_docs(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    """The registry (fleet_registry.MISSIONS) is the single source of mission
    state (issue #92). Routing docs must not present an exploratory mission as
    first-class: any line naming one must carry an exploratory/archived marker
    on the line or in its enclosing section heading; and every shipped mission
    must appear in the missions catalog."""
    errors: list[str] = []
    shipped = {m for m, row in missions.items() if row["shipped"] is True}
    exploratory = {m for m, row in missions.items() if row["shipped"] is not True}

    catalog = root / "skills/autonomous-fleet/references/missions.md"
    if catalog.is_file():
        text = catalog.read_text(encoding="utf-8")
        for m in sorted(shipped):
            if m not in text:
                errors.append(f"{catalog.relative_to(root)}: shipped mission {m!r} missing from the catalog")

    for rel in _ROUTING_DOCS:
        path = root / rel
        if not path.is_file():
            continue
        heading = ""
        lines = path.read_text(encoding="utf-8").splitlines()
        # Block-wise: a blank-line-delimited paragraph/table shares one
        # context — a marker anywhere in the block (or its section heading)
        # marks every mission named in it.
        block_start = 0
        blocks: list[tuple[int, list[str]]] = []
        cur: list[str] = []
        for idx, line in enumerate(lines):
            if line.strip() == "":
                if cur:
                    blocks.append((block_start, cur))
                cur = []
                block_start = idx + 1
            else:
                cur.append(line)
        if cur:
            blocks.append((block_start, cur))
        for start, block in blocks:
            if block and block[0].startswith("#"):
                heading = block[0].lower()
            block_text = " ".join(block).lower()
            marked = any(k in block_text for k in _EXPLORATORY_MARKERS) or any(
                k in heading for k in _EXPLORATORY_MARKERS
            )
            if marked:
                continue
            for offset, line in enumerate(block):
                for m in exploratory:
                    if f"`{m}`" in line or f" {m} " in f" {line} ":
                        errors.append(
                            f"{rel}:{start + offset + 1}: exploratory mission {m!r} "
                            f"presented without an exploratory/archived marker in its "
                            f"block or section heading (registry is the single source "
                            f"— issue #92)"
                        )
    return errors


def _campaign_yaml_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    campaigns_dir = root / "scripts" / "campaigns"
    if campaigns_dir.is_dir():
        paths.extend(sorted(campaigns_dir.glob("*.yaml")))
    dogfood_dir = root / "docs" / "external-dogfood"
    if dogfood_dir.is_dir():
        paths.extend(sorted(dogfood_dir.glob("*campaign*.yaml")))
    # Top-level docs/ examples too (issue #94): docs/composition-e2e-campaign.yaml
    # is advertised as a --campaign example and previously evaded this scan.
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.glob("*.yaml")):
            if path not in paths:
                paths.append(path)
    return paths


def _campaign_allows_exploratory_nodes(spec: Mapping[str, Any]) -> bool:
    return spec.get("allow_exploratory_nodes") is True or spec.get("exploratory") is True


def _exploratory_mission_skill_exists(root: Path, mission: str) -> bool:
    return (
        root / "docs" / "exploratory" / "missions" / mission / "SKILL.md"
    ).is_file()


def _campaign_is_archived(spec: Mapping[str, Any]) -> bool:
    status = spec.get("status")
    if isinstance(status, str) and "archived" in status.lower():
        return True
    nodes = spec.get("nodes")
    return not isinstance(nodes, dict) or not nodes


def lint_campaign_missions(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    errors: list[str] = []
    shipped_ids = set(shipped_missions(missions))

    for path in _campaign_yaml_paths(root):
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path.relative_to(root)}: invalid YAML: {exc}")
            continue
        if not isinstance(spec, dict):
            continue
        if _campaign_is_archived(spec):
            continue
        nodes = spec.get("nodes") or {}
        campaign_id = spec.get("campaign", path.stem)
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                continue
            mission = node.get("mission")
            if not isinstance(mission, str) or not mission:
                continue
            if mission not in missions:
                errors.append(
                    f"{path.relative_to(root)}: node {node_id!r} references unknown mission {mission!r}"
                )
            elif mission not in shipped_ids:
                if _campaign_allows_exploratory_nodes(spec):
                    if not _exploratory_mission_skill_exists(root, mission):
                        errors.append(
                            f"{path.relative_to(root)}: node {node_id!r} references exploratory "
                            f"mission {mission!r} but docs/exploratory/missions/{mission}/SKILL.md "
                            f"is missing"
                        )
                else:
                    errors.append(
                        f"{path.relative_to(root)}: node {node_id!r} references unshipped mission {mission!r} "
                        f"(campaign {campaign_id!r}; archive the campaign or promote the mission)"
                    )
    return errors


def lint_registry(
    root: Path, missions: Mapping[str, Mapping[str, Any]] = MISSIONS
) -> list[str]:
    return (
        lint_shipped_mission_dirs(root, missions)
        + lint_catalog_mentions(root, missions)
        + lint_skills_lock(root)
        + lint_lock_hashes(root)
        + lint_no_skill_version_literals_in_tests(root)
        + lint_mission_state_docs(root, missions)
        + lint_adapter_contract_single_source(root)
        + lint_external_source_pins(root)
        + lint_campaign_missions(root, missions)
    )
