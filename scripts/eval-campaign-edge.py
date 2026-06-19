#!/usr/bin/env python3
"""Evaluate a campaign if-edge against a fleet-outcome readiness doc."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.fleet_outcome import eval_edge, parse_readiness, pick_next_node

import yaml


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--readiness", type=Path, required=True, help="Readiness doc path")
    p.add_argument("--expr", help="Single if expression to evaluate")
    p.add_argument("--campaign", type=Path, help="Campaign YAML file")
    p.add_argument("--current-node", help="Current campaign node id")
    args = p.parse_args()

    outcome = parse_readiness(args.readiness)

    if args.expr:
        result = eval_edge(args.expr, outcome)
        print(json.dumps({"expr": args.expr, "result": result}))
        return 0 if result else 1

    if args.campaign and args.current_node:
        campaign = yaml.safe_load(args.campaign.read_text(encoding="utf-8"))
        nxt = pick_next_node(campaign, args.current_node, outcome)
        print(json.dumps({"current": args.current_node, "next": nxt}))
        return 0

    p.error("provide --expr or (--campaign and --current-node)")


if __name__ == "__main__":
    raise SystemExit(main())