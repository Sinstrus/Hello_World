"""Backward-compatible wrapper around ``fetch_structure_orders`` CLI."""
from __future__ import annotations

import pathlib
import sys
from typing import Iterable, Optional

_HELPER_DIR = pathlib.Path(__file__).resolve().parent
if str(_HELPER_DIR) not in sys.path:
    sys.path.insert(0, str(_HELPER_DIR))

import fetch_structure_orders  # type: ignore  # noqa: E402


def main(argv: Optional[Iterable[str]] = None) -> int:
    return fetch_structure_orders.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
