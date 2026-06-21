#!/usr/bin/env python3
"""Read-only fleet dashboard (move #8): render the ledgers into one HTML file.

Per the research call: "A thin read-only dashboard ... Don't build a live-terminal
GUI." This parses the docs ledgers (docs/*-progress.md task rows + docs/*-readiness.md
fleet-outcome YAML) and sorts every task into ComposioHQ AO's four attention zones
(Working / Needs you / In review / Ready to merge), then emits a single static,
self-contained HTML file. No daemon, no JS, no network: re-run it to refresh.

Zone mapping (AO dashboard-language: Working -> Needs you -> In review -> Ready to
merge), derived from the per-task lifecycle flags CODED/PR_OPEN/REVIEWED/MERGED:
  - merged                                  -> done (collapsed footer, not a zone)
  - reviewed, not merged                    -> Ready to merge
  - PR open, not reviewed                   -> In review
  - blocked / max-rounds / FAIL note        -> Needs you
  - coded or in flight                      -> Working

Stdlib + pyyaml only.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.fleet_outcome import parse_readiness, split_frontmatter  # noqa: E402

ZONES = ("Working", "Needs you", "In review", "Ready to merge")

# Flag-column markdown table header (review-fix / doc-sync / test-coverage style).
_FLAG_KEYS = ("CODED", "WRITTEN", "PR_OPEN", "REVIEWED", "MERGED", "ACCEPT")
_TRUE = frozenset({"t", "true", "yes", "y", "x", "done"})
_NEEDS_YOU = re.compile(r"\b(block|blocked|stuck|fail|escalat|max.?round|needs?.?you)\b", re.I)


def _truthy(val: str) -> bool:
    return val.strip().strip("`*").lower() in _TRUE


def _parse_pipe_rows(text: str, source: str) -> list[dict[str, Any]]:
    """Parse `TASK <name> | KEY=v | CODED=f PR_OPEN=f ... | NOTE=...` rows
    (arch-build-progress.md style)."""
    tasks: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("TASK ") or "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        name = cells[0][len("TASK ") :].strip()
        flags: dict[str, str] = {}
        note = ""
        meta: dict[str, str] = {}
        for cell in cells[1:]:
            for tok in cell.split():
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    if k in _FLAG_KEYS:
                        flags[k] = v
                    else:
                        meta[k] = v
            m = re.search(r"NOTE=(.*)$", cell)
            if m:
                note = m.group(1).strip()
        tasks.append(
            {
                "name": name,
                "flags": flags,
                "note": note,
                "meta": meta,
                "source": source,
            }
        )
    return tasks


def _parse_table_rows(text: str, source: str) -> list[dict[str, Any]]:
    """Parse a markdown flag table whose header contains TASK + flag columns."""
    lines = text.splitlines()
    tasks: list[dict[str, Any]] = []
    header: list[str] | None = None
    for line in lines:
        if "|" not in line:
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        upper = [c.upper() for c in cells]
        if header is None:
            if "TASK" in upper and any(k in upper for k in _FLAG_KEYS):
                header = upper
            continue
        if set("".join(cells)) <= set("-: "):
            continue  # separator row
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        name = row.get("TASK", "").strip("`*").strip()
        if not name or name.upper() == "TASK":
            continue
        flags = {k: row[k] for k in _FLAG_KEYS if k in row}
        note = row.get("NOTE", "")
        meta = {k: v for k, v in row.items() if k not in _FLAG_KEYS and k != "TASK"}
        tasks.append(
            {"name": name, "flags": flags, "note": note, "meta": meta, "source": source}
        )
    return tasks


def parse_progress(path: Path) -> list[dict[str, Any]]:
    """Task rows from a progress ledger, trying both ledger formats."""
    text = path.read_text(encoding="utf-8")
    source = path.name
    tasks = _parse_pipe_rows(text, source)
    tasks += _parse_table_rows(text, source)
    return tasks


def zone_for(task: dict[str, Any]) -> str:
    """Map a task's flags + note to one of ZONES, or 'Done'."""
    flags = task["flags"]
    note = task.get("note", "") or ""

    def f(key: str) -> bool:
        return _truthy(flags.get(key, "f"))

    if f("MERGED"):
        return "Done"
    if _NEEDS_YOU.search(note):
        return "Needs you"
    if f("REVIEWED"):
        return "Ready to merge"
    if f("PR_OPEN"):
        return "In review"
    return "Working"


def build_model(repo: Path) -> dict[str, Any]:
    """Parse all progress + readiness docs under repo/docs into a render model."""
    docs = repo / "docs"
    zones: dict[str, list[dict[str, Any]]] = {z: [] for z in ZONES}
    done: list[dict[str, Any]] = []
    for path in sorted(docs.glob("*-progress.md")):
        for task in parse_progress(path):
            z = zone_for(task)
            (done if z == "Done" else zones[z]).append(task)

    outcomes: list[dict[str, Any]] = []
    for path in sorted(docs.glob("*-readiness.md")):
        try:
            outcome = parse_readiness(path)
        except (ValueError, yaml.YAMLError):
            # A malformed readiness doc must not crash the whole dashboard; skip it.
            continue
        outcome = {**outcome, "_source": path.name}
        outcomes.append(outcome)

    return {"zones": zones, "done": done, "outcomes": outcomes}


# Color discipline borrowed from AO dashboard-language: grayscale by default,
# color rationed to mean something. working=orange, needs-you=amber,
# in-review=neutral, ready=green.
_ZONE_COLOR = {
    "Working": "#f59f4c",
    "Needs you": "#e8c14a",
    "In review": "#9ba1aa",
    "Ready to merge": "#74b98a",
}
_STATUS_COLOR = {"done": "#74b98a", "partial": "#e8c14a", "blocked": "#ef6b6b"}


def _esc(val: Any) -> str:
    return html.escape(str(val), quote=True)


def _card(task: dict[str, Any]) -> str:
    flags = " ".join(
        f"{k}={v}" for k, v in task["flags"].items() if k in _FLAG_KEYS
    )
    note = task.get("note") or ""
    note_html = f'<div class="note">{_esc(note)}</div>' if note else ""
    return (
        '<div class="card">'
        f'<div class="task">{_esc(task["name"])}</div>'
        f'<div class="src">{_esc(task["source"])}</div>'
        f'<div class="flags">{_esc(flags)}</div>'
        f"{note_html}"
        "</div>"
    )


def render_html(model: dict[str, Any]) -> str:
    cols = []
    for zone in ZONES:
        cards = "".join(_card(t) for t in model["zones"][zone])
        count = len(model["zones"][zone])
        cols.append(
            f'<section class="zone" style="--glow:{_ZONE_COLOR[zone]}">'
            f'<h2>{_esc(zone)} <span class="count">{count}</span></h2>'
            f'<div class="cards">{cards or "<div class=empty>none</div>"}</div>'
            "</section>"
        )
    board = "".join(cols)

    rows = []
    for o in model["outcomes"]:
        status = str(o.get("status", ""))
        color = _STATUS_COLOR.get(status, "#9ba1aa")
        rows.append(
            "<tr>"
            f"<td>{_esc(o.get('_source', ''))}</td>"
            f"<td>{_esc(o.get('mission', ''))}</td>"
            f'<td><span class="pill" style="background:{color}">{_esc(status)}</span></td>'
            f"<td class=num>{_esc(o.get('prs_merged', ''))}</td>"
            f"<td class=num>{_esc(o.get('cost_estimate', ''))}</td>"
            "</tr>"
        )
    outcome_table = "".join(rows) or '<tr><td colspan=5 class=empty>no readiness docs</td></tr>'

    done_n = len(model["done"])
    done_names = ", ".join(_esc(t["name"]) for t in model["done"])

    return _TEMPLATE.format(
        board=board,
        outcome_table=outcome_table,
        done_n=done_n,
        done_names=done_names or "none",
    )


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fleet dashboard</title>
<style>
  :root {{
    --bg:#0a0b0d; --card:#15171b; --line:rgba(255,255,255,.06);
    --t1:#f4f5f7; --t2:#9ba1aa; --t3:#646a73;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--t1);
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  header {{ padding:18px 24px; border-bottom:1px solid var(--line); }}
  header h1 {{ margin:0; font-size:15px; font-weight:600; letter-spacing:.2px; }}
  header p {{ margin:4px 0 0; color:var(--t3); font-size:12px; }}
  .board {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; padding:18px 24px; }}
  .zone {{ border-radius:10px; padding:10px; background:rgba(255,255,255,.015);
    border-top:2px solid var(--glow); }}
  .zone h2 {{ margin:2px 4px 10px; font-size:12px; font-weight:600; color:var(--t2);
    text-transform:uppercase; letter-spacing:.6px; }}
  .count {{ color:var(--t3); font-variant-numeric:tabular-nums; }}
  .cards {{ display:flex; flex-direction:column; gap:8px; }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:8px;
    padding:8px 10px; }}
  .task {{ font-size:13px; font-weight:600; }}
  .src {{ color:var(--t3); font-size:11px;
    font-family:ui-monospace,"JetBrains Mono",monospace; }}
  .flags {{ color:var(--t2); font-size:11px; margin-top:4px;
    font-family:ui-monospace,"JetBrains Mono",monospace; }}
  .note {{ color:var(--t2); font-size:11px; margin-top:4px; }}
  .empty {{ color:var(--t3); font-size:11px; padding:4px; }}
  section.outcomes {{ padding:6px 24px 28px; }}
  section.outcomes h2 {{ font-size:12px; color:var(--t2); text-transform:uppercase;
    letter-spacing:.6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; }}
  th, td {{ text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); }}
  th {{ color:var(--t3); font-weight:500; }}
  td.num {{ font-variant-numeric:tabular-nums; font-family:ui-monospace,monospace; }}
  .pill {{ color:#0a0b0d; border-radius:5px; padding:1px 7px; font-size:11px;
    font-weight:600; }}
  .done {{ padding:0 24px 28px; color:var(--t3); font-size:12px; }}
</style></head>
<body>
<header>
  <h1>Fleet dashboard</h1>
  <p>Read-only render of docs/*-progress.md + docs/*-readiness.md into the four attention zones. Re-run render-dashboard.py to refresh.</p>
</header>
<div class="board">{board}</div>
<section class="outcomes">
  <h2>Fleet outcomes (readiness)</h2>
  <table>
    <thead><tr><th>doc</th><th>mission</th><th>status</th><th>PRs</th><th>cost</th></tr></thead>
    <tbody>{outcome_table}</tbody>
  </table>
</section>
<div class="done">Done ({done_n}): {done_names}</div>
</body></html>
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repo root containing docs/ (default: this repo)",
    )
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("fleet-dashboard.html"),
        help="Output HTML path (default: fleet-dashboard.html)",
    )
    args = p.parse_args()

    if not (args.repo / "docs").is_dir():
        p.error(f"{args.repo}/docs not found")

    model = build_model(args.repo)
    out_html = render_html(model)
    args.out.write_text(out_html, encoding="utf-8")
    total = sum(len(v) for v in model["zones"].values())
    print(
        f"wrote {args.out} "
        f"({total} active tasks across {len(ZONES)} zones, "
        f"{len(model['done'])} done, {len(model['outcomes'])} readiness docs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
