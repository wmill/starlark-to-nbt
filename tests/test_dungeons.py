from __future__ import annotations

from collections import deque
from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.serialize import write_structure_nbt

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "lib" / "showcase.star"
EXAMPLE = ROOT / "examples" / "bsp_dungeon.star"


def test_compact_dungeon_has_topology_stats_atomic_doors_and_supported_lights():
    result = build_file(SHOWCASE, props={"name": "BspDungeon"})
    props = result.component_ir.props
    assert props["room_count"] >= 2
    assert props["connection_count"] == props["room_count"] - 1
    doors = [op for op in result.operations if op.assembly_name == "bsp_dungeon_door"]
    assert doors and all(len(op.writes) == 2 for op in doors)
    assert props["wide_connection_count"] > 0
    assert any(v.block.block_type == "minecraft:stone_brick_stairs"
               for v in result.volume.voxels.values())
    torches = [p for p, v in result.volume.voxels.items()
               if v.block.block_type == "minecraft:torch"]
    assert len(torches) == 2 * props["room_count"]
    lanterns = [p for p, v in result.volume.voxels.items()
                if v.block.block_type == "minecraft:lantern"]
    assert lanterns
    assert all(result.volume.block_at(p + Point(0, 1, 0)).block_type == "minecraft:stone_bricks"
               for p in lanterns)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_dungeon_rotations_preserve_voxels_and_rotate_directional_states(rotation):
    base = build_file(SHOWCASE, props={"name": "BspDungeon"})
    turned = build_file(SHOWCASE, entry="rotated",
                        props={"name": "BspDungeon", "rotation": rotation})
    assert len(turned.volume.voxels) == len(base.volume.voxels)
    base_door_facings = {v.block.block_state["facing"] for v in base.volume.voxels.values()
                         if v.block.block_type == "minecraft:oak_door"}
    door_facings = {v.block.block_state["facing"] for v in turned.volume.voxels.values()
                    if v.block.block_type == "minecraft:oak_door"}
    base_stair_facings = {v.block.block_state["facing"] for v in base.volume.voxels.values()
                          if v.block.block_type == "minecraft:stone_brick_stairs"}
    stair_facings = {v.block.block_state["facing"] for v in turned.volume.voxels.values()
                     if v.block.block_type == "minecraft:stone_brick_stairs"}
    turns = {
        0: {"north": "north", "east": "east", "south": "south", "west": "west"},
        90: {"north": "east", "east": "south", "south": "west", "west": "north"},
        180: {"north": "south", "east": "west", "south": "north", "west": "east"},
        270: {"north": "west", "east": "north", "south": "east", "west": "south"},
    }
    assert door_facings == {turns[rotation][facing] for facing in base_door_facings}
    assert stair_facings == {turns[rotation][facing] for facing in base_stair_facings}


def test_reference_is_sparse_connected_and_has_surface_metadata(tmp_path):
    result = build_file(EXAMPLE)
    assert result.volume.bounds.size == Point(96, 15, 96)
    assert result.metadata.to_dict() == {"ground_level": 10, "y_offset": -10}
    assert len(result.volume.voxels) < 96 * 15 * 96
    assert any(v.block.block_type == "minecraft:stone_brick_stairs"
               for v in result.volume.voxels.values())
    assert any(v.block.block_type == "minecraft:lantern"
               for v in result.volume.voxels.values())

    # All explicit dungeon-level walk cells belong to one connected component.
    walkable = {Point(p.x, 1, p.z) for p, v in result.volume.voxels.items()
                if p.y == 1 and v.block.block_type in {"minecraft:air", "minecraft:oak_door"}}
    start = next(iter(walkable))
    seen = {start}
    queue = deque([start])
    while queue:
        p = queue.popleft()
        for delta in (Point(1, 0, 0), Point(-1, 0, 0), Point(0, 0, 1), Point(0, 0, -1)):
            neighbor = p + delta
            if neighbor in walkable and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    assert seen == walkable

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(EXAMPLE).volume, second)
    assert first.read_bytes() == second.read_bytes()

    # The validated door geometry survives sparse structure serialization.
    decoded = nbtlib.load(first)
    palette = [str(entry["Name"]) for entry in decoded["palette"]]
    blocks = {
        Point(*map(int, entry["pos"])): palette[int(entry["state"])]
        for entry in decoded["blocks"]
    }
    door = next(op for op in result.operations
                if op.assembly_name == "bsp_dungeon_door" and op.writes[0].pos.y == 1)
    lower = door.writes[0]
    front = {
        "north": Point(0, 0, -1), "south": Point(0, 0, 1),
        "east": Point(1, 0, 0), "west": Point(-1, 0, 0),
    }[lower.block.block_state["facing"]]
    side = Point(front.z, 0, -front.x)
    for height in (0, 1):
        anchor = lower.pos + Point(0, height, 0)
        assert blocks[anchor + side] == blocks[anchor - side] == "minecraft:stone_bricks"
        assert blocks[anchor + front] == blocks[anchor - front] == "minecraft:air"


def test_seed_changes_geometry_without_changing_reference_bounds():
    first = build_file(EXAMPLE, props={"seed": 101})
    repeated = build_file(EXAMPLE, props={"seed": 101})
    different = build_file(EXAMPLE, props={"seed": 102})
    assert first.volume.bounds == repeated.volume.bounds == different.volume.bounds
    assert first.volume.voxels == repeated.volume.voxels
    assert first.volume.voxels != different.volume.voxels


def test_entrance_disabled_uses_exact_low_footprint(tmp_path):
    source = tmp_path / "without_entrance.star"
    source.write_text(
        f'load("{ROOT / "lib" / "dungeons.star"}", "BspDungeon")\n'
        'def build():\n'
        '    return BspDungeon(width=20, length=20, room_height=4, '
        'min_room_size=5, target_leaf_size=12, max_depth=2, '
        'surface_entrance=False)\n',
        encoding="utf-8",
    )
    result = build_file(source)
    assert result.volume.bounds.size == Point(20, 6, 20)
    assert result.component_ir.props["surface_level"] == 0
    assert result.component_ir.props["burial_depth"] == 4


@pytest.mark.parametrize("props", [
    {"width": 8},
    {"length": 20, "burial_depth": 8},
    {"room_height": 2},
    {"target_leaf_size": 5},
    {"max_depth": -1},
    {"wide_corridor_chance": -0.1},
    {"wide_corridor_chance": 1.1},
    {"light_spacing": 0},
    {"burial_depth": -1},
])
def test_invalid_dungeon_controls_fail_through_starlark_diagnostics(props):
    with pytest.raises(BuildError, match="starlark_error"):
        build_file(EXAMPLE, props=props)
