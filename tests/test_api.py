"""The public Python API over the Rust core.

minecraft-mcp-api's starlark-service (runner.py) depends on build_source
with loader options, BuildResult.volume (bounds, voxels, entities),
.metadata, serialize.write_structure_nbt, and BuildError/Diagnostic.
"""
from __future__ import annotations

import gzip
from collections import Counter
from pathlib import Path

import nbtlib
import pytest

import starlark_to_nbt
from starlark_to_nbt.model import AIR, BlockSpec, Box, BuildError, Point
from starlark_to_nbt.pipeline import build_file, build_source, evaluate_source, write_build_outputs
from starlark_to_nbt.serialize import write_structure_nbt

ROOT = Path(__file__).resolve().parents[1]


def test_fingerprint_names_the_compiled_core():
    fingerprint = starlark_to_nbt.build_fingerprint()
    engine, version, digest = fingerprint.split("-")
    assert (engine, len(digest)) == ("rust", 16)
    assert version == starlark_to_nbt._core.version()


def test_result_views_agree_with_each_other():
    result = build_file(ROOT / "examples" / "cottage.star")
    volume = result.volume
    assert isinstance(volume.bounds, Box)
    assert volume.voxels, "cottage writes blocks"
    assert all(volume.block_at(point) == voxel.block for point, voxel in volume.voxels.items())
    assert volume.block_at(Point(-5, -5, -5)) == AIR
    assert list(volume.voxels) == sorted(volume.voxels, key=lambda p: (p.y, p.z, p.x))
    # Every voxel's block was written by some operation, at that cell.
    written = {write.pos: write.block for op in result.operations for write in op.writes}
    assert all(written[point] == voxel.block for point, voxel in volume.voxels.items())
    assert [op.sequence for op in result.operations] == list(range(len(result.operations)))
    assert volume.entities is result.entities
    assert result.root_props == {"width": 13, "length": 11, "wall_height": 5}


def test_runner_usage_end_to_end(tmp_path):
    """What starlark_service/runner.py does with a build."""
    library = tmp_path / "library" / "hut"
    library.mkdir(parents=True)
    (library / "v1.star").write_text(
        'load("../lib/structural.star", "Floor")\n\ndef Hut():\n    return Floor(3, 3)\n', encoding="utf-8")
    source = 'load("../library/hut/v1.star", "Hut")\n\ndef build():\n    return Hut()\n'
    result = build_source(source, props={}, root_size=None, base_dir=ROOT / "scripts",
                          loader_root=ROOT, mounts={"library": tmp_path / "library"})
    output = tmp_path / "out.nbt"
    write_structure_nbt(result.volume, output)
    counts = Counter(voxel.block.block_type for voxel in result.volume.voxels.values())
    assert sum(counts.values()) == len(result.volume.voxels) == len(nbtlib.load(output)["blocks"])
    assert (result.metadata.ground_level, result.metadata.y_offset) == (0, 0)
    assert result.volume.bounds.size.to_list() == list(map(int, nbtlib.load(output)["size"]))


def test_outputs_are_deterministic(tmp_path):
    for attempt in ("a", "b"):
        write_build_outputs(build_file(ROOT / "examples" / "church.star"), tmp_path / f"{attempt}.nbt", tmp_path / attempt)
    assert (tmp_path / "a.nbt").read_bytes() == (tmp_path / "b.nbt").read_bytes()
    for name in ("component-ir.json", "resolved.json", "operations.json", "entities.json", "dense.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
    assert gzip.decompress((tmp_path / "a.nbt").read_bytes())[:3] == b"\x0a\x00\x00"


def test_diagnostics_become_build_errors():
    source = ('def build():\n    return component("C", {}, group([place_block([0, 0, 0], block("minecraft:stone")),'
              ' place_block([0, 0, 0], block("minecraft:dirt"))]), min_size=[1, 1, 1])\n')
    with pytest.raises(BuildError) as info:
        build_source(source)
    diagnostic = info.value.diagnostics[0]
    assert (diagnostic.code, diagnostic.component_path, diagnostic.coordinates) == ("block_conflict", "C", Point(0, 0, 0))
    assert diagnostic.details == {"existingComponent": "C"}
    assert str(info.value) == "block_conflict: C: cannot overwrite minecraft:stone from C"


def test_evaluate_source_returns_the_raw_tree():
    tree = evaluate_source('def build(n):\n    return block("minecraft:stone", {"n": str(n)})\n', props={"n": 3})
    assert tree == {"block_type": "minecraft:stone", "block_state": {"n": "3"}}
    with pytest.raises(BuildError) as info:
        evaluate_source("def build(:\n", "bad.star")
    assert info.value.diagnostics[0].code == "starlark_error"
    assert BlockSpec("minecraft:stone") != AIR
