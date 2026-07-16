from __future__ import annotations

from pathlib import Path

import nbtlib

from starlark_to_nbt.execute import dense_to_dict
from starlark_to_nbt.ir import Phase
from starlark_to_nbt.model import Point
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.serialize import DATA_VERSION_1_21_7, write_structure_nbt


EXAMPLES = Path(__file__).parents[1] / "examples"
EXAMPLE = EXAMPLES / "church.star"


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
    # Sparse template: only written voxels are listed; untouched cells are
    # absent so pasting preserves terrain.
    assert len(decoded["blocks"]) == len(result.volume.voxels)
    assert len(decoded["blocks"]) < 11 * 4 * 19
    assert len(decoded["entities"]) == 0
    palette_names = {str(entry["Name"]) for entry in decoded["palette"]}
    # The carved doorway is fully refilled by the door assembly, so no air
    # voxels survive into the palette.
    assert palette_names == {"minecraft:oak_door", "minecraft:oak_stairs", "minecraft:stone_bricks"}


def test_cottage_composes_library_components_via_load(tmp_path):
    result = build_file(EXAMPLES / "cottage.star")

    assert result.volume.bounds.size == Point(13, 13, 11)
    door_lower = result.volume.block_at(Point(6, 1, 10))
    assert door_lower.block_type == "minecraft:oak_door"
    # East shuttered window went through a 270-degree turn: south -> east.
    east_shutters = [v for p, v in result.volume.voxels.items()
                     if v.block.block_type == "minecraft:oak_trapdoor" and p.x == 12]
    assert east_shutters and all(v.block.block_state["facing"] == "east" for v in east_shutters)
    paths = {op.provenance.component_path for op in result.operations}
    assert any("TimberFrameWall" in path for path in paths)
    assert any("GableRoof" in path for path in paths)

    output = tmp_path / "cottage.nbt"
    write_structure_nbt(result.volume, output)
    decoded = nbtlib.load(output)
    assert len(decoded["blocks"]) == len(result.volume.voxels)


def test_keep_stress_build_is_deterministic(tmp_path):
    result = build_file(EXAMPLES / "keep.star")

    assert result.volume.bounds.size == Point(33, 20, 33)
    assert len(result.volume.voxels) > 4000
    # Tower arrow slits are carved and never refilled, so they survive into
    # the template as explicit air that clears the cell on paste.
    assert any(v.block.block_type == "minecraft:air" for v in result.volume.voxels.values())
    # Towers are placed at all four rotations and stay identical in mass.
    tower_counts: dict[str, int] = {}
    for op in result.operations:
        path = op.provenance.component_path
        if "/Tower/" in path or path.endswith("/Tower"):
            key = path.split("/Tower")[0]
            tower_counts[key] = tower_counts.get(key, 0) + len(op.writes)
    assert len(tower_counts) == 4
    assert len(set(tower_counts.values())) == 1

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(EXAMPLES / "keep.star").volume, second)
    assert first.read_bytes() == second.read_bytes()
