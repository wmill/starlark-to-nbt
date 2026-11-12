"""Shared corpus paths for the corpus-level tests (scripts/golden.py builds the corpus itself)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "lib" / "showcase.star"


def showcase_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))
