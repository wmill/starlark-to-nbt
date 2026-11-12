"""Dump a script's raw tagged-dict tree and root size as JSON, for
crates/stnbt-core/examples/bench_stages.rs.

    uv run python scripts/dump_tree.py examples/moonspire_magical_city.star out.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from starlark_to_nbt import starlark_runtime
from starlark_to_nbt.pipeline import _root_size
from starlark_to_nbt.schema import parse_node


def main() -> None:
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    original = starlark_runtime.parse_node
    starlark_runtime.parse_node = lambda value, source_file=None: value
    try:
        tree = starlark_runtime.evaluate_file(source)
    finally:
        starlark_runtime.parse_node = original
    root = _root_size(parse_node(tree), {})
    out.write_text(json.dumps({"tree": tree, "root_size": root.to_list()}), encoding="utf-8")


if __name__ == "__main__":
    main()
