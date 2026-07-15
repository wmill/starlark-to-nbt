from __future__ import annotations

from pathlib import Path

import nbtlib

from starlark_to_nbt.execute import dense_to_dict
from starlark_to_nbt.ir import Phase
from starlark_to_nbt.model import Point
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.serialize import DATA_VERSION_1_21_7, write_structure_nbt


EXAMPLE = Path(__file__).parents[1] / "examples" / "church.star"


def test_church_vertical_slice_and_deterministic_nbt(tmp_path):
    result = build_file(EXAMPLE, props={"width": 11, "length": 19, "height": 4})

    assert result.volume.bounds.size == Point(11, 4, 19)
    lower = result.volume.block_at(Point(5, 1, 0))
    upper = result.volume.block_at(Point(5, 2, 0))
    assert lower.block_type == upper.block_type == "minecraft:oak_door"
    assert lower.block_state["half"] == "lower"
    assert upper.block_state["half"] == "upper"
    assert lower.block_state["facing"] == upper.block_state["facing"] == "north"

    assemblies = [op for op in result.operations if op.assembly_name == "door"]
    pew_writes = [write for op in result.operations if op.phase == Phase.FIXTURE and op.assembly_name is None for write in op.writes]
    pew_paths = {op.provenance.component_path for op in result.operations if "/Pew[" in op.provenance.component_path}
    assert len(assemblies) == 1
    assert len(assemblies[0].writes) == 2
    assert len(pew_writes) == 2 * 8 * 3
    assert len(pew_paths) == 16
    assert all(result.volume.bounds.contains_point(write.pos) for op in result.operations for write in op.writes)

    dense = dense_to_dict(result.volume)
    assert dense["order"] == "y,z,x"
    assert dense["size"] == [11, 4, 19]

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(result.volume, second)
    assert first.read_bytes() == second.read_bytes()

    decoded = nbtlib.load(first)
    assert int(decoded["DataVersion"]) == DATA_VERSION_1_21_7
    assert list(map(int, decoded["size"])) == [11, 4, 19]
    assert len(decoded["blocks"]) == 11 * 4 * 19
    assert len(decoded["entities"]) == 0
    palette_names = {str(entry["Name"]) for entry in decoded["palette"]}
    assert {"minecraft:air", "minecraft:oak_door", "minecraft:oak_stairs", "minecraft:stone_bricks"} <= palette_names
