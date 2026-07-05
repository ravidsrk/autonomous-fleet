#!/usr/bin/env python3
"""CLI shim for :mod:`lib.fleet_verify`."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.fleet_verify import main  # noqa: E402


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
