"""Dump a script's raw tagged-dict tree and root size as JSON, for
crates/stnbt-core/examples/bench_stages.rs.

    uv run python scripts/dump_tree.py examples/moonspire_magical_city.star out.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from starlark_to_nbt.pipeline import build_file, evaluate_source


def main() -> None:
    source, out = Path(sys.argv[1]), Path(sys.argv[2])
    tree = evaluate_source(source.read_text(encoding="utf-8"), str(source), base_dir=source.resolve().parent)
    root = build_file(source).volume.bounds.size
    out.write_text(json.dumps({"tree": tree, "root_size": root.to_list()}), encoding="utf-8")


if __name__ == "__main__":
    main()
