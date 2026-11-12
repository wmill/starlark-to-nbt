"""Golden parity manifest for the Rust core rewrite (docs/rust-core-plan.md).

Builds a fixed corpus through the public pipeline API and records, per case,
the sha256 of the *decompressed* structure NBT plus the .meta.json contents.
Known-bad inputs record their diagnostic codes and component paths instead.
Because it only uses pipeline.build_file/build_source/write_build_outputs,
the same script checks whichever engine is active.

    uv run python scripts/golden.py            # (re)write tests/golden/manifest.json
    uv run python scripts/golden.py --check    # compare against it; exit 1 on drift
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from starlark_to_nbt.model import BuildError
from starlark_to_nbt.pipeline import BuildResult, build_file, build_source, write_build_outputs

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "golden" / "manifest.json"
SHOWCASE = ROOT / "lib" / "showcase.star"

# Inline sources that must fail. Each entry exercises a different stage.
FAILURES: dict[str, str] = {
    "schema_unknown_kind": 'def build():\n    return {"kind": "nope"}\n',
    "schema_bad_identifier": (
        'def build():\n'
        '    return component("C", {}, place_block([0, 0, 0], block("Stone")), min_size=[1, 1, 1])\n'
    ),
    "layout_split_overflow": (
        'def build():\n'
        '    return component("C", {}, split("x", [fixed(3), fixed(3)], [group([]), group([])]),'
        ' min_size=[4, 1, 1])\n'
    ),
    "execute_root_overflow": (
        'def build():\n'
        '    return component("C", {}, place_block([5, 0, 0], block("minecraft:stone")),'
        ' min_size=[2, 1, 1])\n'
    ),
    "execute_block_conflict": (
        'def build():\n'
        '    return component("C", {}, group([\n'
        '        place_block([0, 0, 0], block("minecraft:stone")),\n'
        '        place_block([0, 0, 0], block("minecraft:dirt")),\n'
        '    ]), min_size=[1, 1, 1])\n'
    ),
    "support_unsupported_wire": (
        'def build():\n'
        '    return component("C", {}, place_block([0, 1, 0], block("minecraft:redstone_wire")),'
        ' min_size=[1, 2, 1])\n'
    ),
    "starlark_error": 'def build():\n    return place_block([0, 0, 0])\n',
}


def _showcase_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))


def _cases() -> dict[str, Callable[[], BuildResult]]:
    cases: dict[str, Callable[[], BuildResult]] = {}
    for path in sorted((ROOT / "examples").glob("*.star")):
        cases[f"example/{path.stem}"] = lambda p=path: build_file(p)
    cases["example/church@11x4x19"] = lambda: build_file(
        ROOT / "examples" / "church.star", props={"width": 11, "length": 19, "height": 4})
    for name in _showcase_names():
        cases[f"showcase/{name}"] = lambda n=name: build_file(SHOWCASE, props={"name": n})
        for rotation in (90, 180, 270):
            cases[f"showcase/{name}@{rotation}"] = lambda n=name, r=rotation: build_file(
                SHOWCASE, entry="rotated", props={"name": n, "rotation": r})
    return cases


def _record(result: BuildResult, workdir: Path) -> dict[str, Any]:
    nbt_path = workdir / "out.nbt"
    write_build_outputs(result, nbt_path)
    payload = gzip.decompress(nbt_path.read_bytes())
    meta = json.loads(nbt_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    return {"nbt_sha256": hashlib.sha256(payload).hexdigest(), "nbt_bytes": len(payload), "meta": meta}


def _failure(source: str) -> dict[str, Any]:
    try:
        build_source(source, filename="<golden>")
    except BuildError as exc:
        # Messages are compared too, except starlark_error, whose text is the
        # engine's rendered traceback rather than ours.
        return {"diagnostics": [
            [d.code, d.component_path] + ([] if d.code == "starlark_error" else [d.message])
            for d in exc.diagnostics
        ]}
    return {"diagnostics": "UNEXPECTED SUCCESS"}


def generate() -> dict[str, Any]:
    out: dict[str, Any] = {"builds": {}, "failures": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for name, build in _cases().items():
            out["builds"][name] = _record(build(), Path(tmp))
    for name, source in FAILURES.items():
        out["failures"][name] = _failure(source)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="compare instead of writing")
    args = parser.parse_args()
    current = generate()
    if not args.check:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {len(current['builds'])} builds, {len(current['failures'])} failures to {MANIFEST}")
        return 0
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    drift = []
    for section in ("builds", "failures"):
        for name in sorted(expected[section].keys() | current[section].keys()):
            if expected[section].get(name) != current[section].get(name):
                drift.append(f"{section}/{name}: expected {expected[section].get(name)}, "
                             f"got {current[section].get(name)}")
    for line in drift:
        print(line)
    print(f"{len(drift)} drifted of {len(current['builds']) + len(current['failures'])} cases")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
