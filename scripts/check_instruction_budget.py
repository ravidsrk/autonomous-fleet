#!/usr/bin/env python3
"""Fail CI when the composed per-run instruction surface exceeds the budget.

The deep architecture review measured ~42K tokens of mandatory pre-task
instructions per single-mission run and found no counterpressure against
doctrine growth (issue #87). This check composes the mandatory surface —
umbrella SKILL + core SKILL + the core references the SKILL mandates +
the LARGEST adapter SKILL + the LARGEST shipped-mission SKILL — measures
it in bytes (a stable, tokenizer-free proxy), and fails when it exceeds
the budget recorded in ``docs/instruction-budget.json``.

Raising the budget is a deliberate act: edit the JSON in the same commit
that grows the corpus, and justify it in the commit message. The slim
always-read engine core has its own line cap so trigger-loaded doctrine
cannot silently creep back into ``references/engine.md``.

Usage:
  python scripts/check_instruction_budget.py            # check (exit 1 over budget)
  python scripts/check_instruction_budget.py --update   # rewrite byte budget to current + headroom
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET_FILE = ROOT / "docs" / "instruction-budget.json"
UPDATE_HEADROOM = 1.05  # --update records current size + 5%
ENGINE_CORE = "skills/autonomous-fleet-core/references/engine.md"
DEFAULT_ENGINE_CORE_MAX_LINES = 300
ENGINE_TRIGGER_REFERENCES = (
    "skills/autonomous-fleet-core/references/engine-autonomy.md",
    "skills/autonomous-fleet-core/references/engine-workers.md",
    "skills/autonomous-fleet-core/references/engine-review.md",
    "skills/autonomous-fleet-core/references/engine-recovery.md",
)

CORE_MANDATORY = (
    "skills/autonomous-fleet/SKILL.md",
    "skills/autonomous-fleet-core/SKILL.md",
    ENGINE_CORE,
    "skills/autonomous-fleet-core/references/composition.md",
    "skills/autonomous-fleet-core/references/community-skills.md",
    "skills/autonomous-fleet-core/references/fleet-outcome.md",
    "skills/autonomous-fleet-core/references/runtime-goals.md",
)

SHIPPED_MISSIONS = ("doc-sync", "test-coverage", "adversarial-review-and-fix")


def _size(rel: str) -> int:
    return (ROOT / rel).stat().st_size


def _line_count(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8").splitlines())


def composed_surface() -> dict[str, int]:
    """Relative path -> bytes for the worst-case mandatory composition."""
    surface = {rel: _size(rel) for rel in CORE_MANDATORY}

    def _composition(skill_md: Path) -> dict[Path, int]:
        """SKILL.md plus the skill's own references/ — adapters mandate them
        (e.g. orca-platform.md), so the worst case is the composed size."""
        files = {skill_md: skill_md.stat().st_size}
        for ref in sorted(skill_md.parent.glob("references/*.md")):
            files[ref] = ref.stat().st_size
        return files

    adapters = sorted(ROOT.glob("skills/autonomous-fleet-adapter-*/SKILL.md"))
    missions = [
        p for m in SHIPPED_MISSIONS if (p := ROOT / "skills" / m / "SKILL.md").is_file()
    ]
    for group in (adapters, missions):
        if not group:
            continue
        biggest = max((_composition(p) for p in group), key=lambda c: sum(c.values()))
        for path, size in biggest.items():
            surface[str(path.relative_to(ROOT))] = size
    return surface


def engine_core_line_count() -> int:
    """Current always-read engine core line count."""
    return _line_count(ENGINE_CORE)


def _valid_ref_list(refs: object) -> bool:
    return (
        isinstance(refs, list)
        and bool(refs)
        and all(isinstance(ref, str) and ref for ref in refs)
    )


def trigger_loaded_references(budget: dict[str, object]) -> tuple[str, ...]:
    """Registered trigger-loaded references from the budget file."""
    refs = budget["trigger_loaded_references"]
    if not _valid_ref_list(refs):
        raise ValueError("trigger_loaded_references must be a non-empty list of strings")
    return tuple(refs)


def missing_registered_references(refs: tuple[str, ...]) -> tuple[str, ...]:
    """Registered trigger-loaded references that are absent on disk."""
    return tuple(ref for ref in refs if not (ROOT / ref).is_file())


def _update_reference_list(existing: dict[str, object]) -> list[str]:
    refs = existing.get("trigger_loaded_references", list(ENGINE_TRIGGER_REFERENCES))
    if not _valid_ref_list(refs):
        return list(ENGINE_TRIGGER_REFERENCES)
    return refs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update", action="store_true",
        help=f"rewrite {BUDGET_FILE.name} to current size + {int((UPDATE_HEADROOM - 1) * 100)}%% headroom",
    )
    args = parser.parse_args()

    surface = composed_surface()
    total = sum(surface.values())

    if args.update:
        try:
            existing = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, ValueError):
            existing = {}
        max_engine_lines = int(
            existing.get("max_engine_core_lines", DEFAULT_ENGINE_CORE_MAX_LINES)
        )
        BUDGET_FILE.write_text(
            json.dumps(
                {
                    "max_bytes": int(total * UPDATE_HEADROOM),
                    "max_engine_core_lines": max_engine_lines,
                    "trigger_loaded_references": _update_reference_list(existing),
                    "note": (
                        "Composed mandatory instruction surface cap (issue #87). "
                        "Raising this is a deliberate act — justify it in the commit "
                        "that grows the corpus. Measured by scripts/check_instruction_budget.py. "
                        "The always-read engine core is separately capped by max_engine_core_lines."
                    ),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"instruction-budget: recorded max_bytes={int(total * UPDATE_HEADROOM)} (current {total})")
        return 0

    try:
        budget = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
        if not isinstance(budget, dict):
            raise ValueError("budget JSON must be an object")
        max_bytes = int(budget["max_bytes"])
        max_engine_lines = int(budget["max_engine_core_lines"])
        registered_refs = trigger_loaded_references(budget)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"instruction-budget: unreadable {BUDGET_FILE.name}: {exc}", file=sys.stderr)
        return 1

    engine_lines = engine_core_line_count()
    missing_refs = missing_registered_references(registered_refs)

    for rel, size in sorted(surface.items(), key=lambda kv: -kv[1]):
        print(f"  {size:>7}  {rel}")
    print(f"instruction-budget: composed surface {total} bytes (~{total // 4} tokens), budget {max_bytes}")
    print(f"instruction-budget: {ENGINE_CORE} {engine_lines} lines, cap {max_engine_lines}")
    print(f"instruction-budget: registered trigger-loaded engine refs {len(registered_refs)}")

    failed = False
    if total > max_bytes:
        print(
            f"instruction-budget: OVER BUDGET by {total - max_bytes} bytes. Either slim the "
            f"corpus (prefer: demote unwired doctrine to on-demand references) or raise "
            f"docs/instruction-budget.json max_bytes in this commit with justification.",
            file=sys.stderr,
        )
        failed = True
    if engine_lines > max_engine_lines:
        print(
            f"instruction-budget: ENGINE CORE OVER LINE CAP by {engine_lines - max_engine_lines} "
            f"lines ({ENGINE_CORE} has {engine_lines}, cap {max_engine_lines}). Move doctrine "
            f"to trigger-loaded references instead of growing the always-read core.",
            file=sys.stderr,
        )
        failed = True
    if missing_refs:
        print(
            "instruction-budget: registered trigger-loaded references missing:\n"
            + "\n".join(f"  {ref}" for ref in missing_refs),
            file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
