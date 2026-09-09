from __future__ import annotations

from collections import deque
from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file, write_build_outputs

ROOT = Path(__file__).parents[1]
SHOWCASE = ROOT / "lib" / "showcase.star"
EXAMPLE = ROOT / "examples" / "bsp_dungeon.star"
STONE_BRICKS = {
    "minecraft:stone_bricks",
    "minecraft:mossy_stone_bricks",
    "minecraft:cracked_stone_bricks",
}


def test_compact_dungeon_has_topology_stats_atomic_doors_and_supported_lights():
    result = build_file(SHOWCASE, props={"name": "BspDungeon"})
    props = result.component_ir.props
    assert props["room_count"] >= 2
    assert props["connection_count"] == props["room_count"] - 1
    doors = [op for op in result.operations if op.assembly_name == "bsp_dungeon_door"]
    assert doors and all(len(op.writes) == 4 for op in doors)
    assert props["wide_connection_count"] > 0
    assert any(v.block.block_type == "minecraft:stone_brick_stairs"
               for v in result.volume.voxels.values())
    assert not any(v.block.block_type == "minecraft:torch"
                   for v in result.volume.voxels.values())
    wall_torches = [p for p, v in result.volume.voxels.items()
                    if v.block.block_type in {"minecraft:wall_torch",
                                              "minecraft:soul_wall_torch"}]
    assert len(wall_torches) == props["wall_torch_count"]
    assert len(wall_torches) == 2 * (props["room_count"] - props["mob_room_count"])
    lanterns = [p for p, v in result.volume.voxels.items()
                if v.block.block_type == "minecraft:lantern"]
    assert lanterns
    assert all(result.volume.block_at(p + Point(0, 1, 0)).block_type == "minecraft:stone_bricks"
               for p in lanterns)


def test_dungeon_wall_picker_is_cached_by_coordinate(tmp_path):
    source = tmp_path / "picked_walls.star"
    source.write_text(
        f'load("{ROOT / "lib" / "dungeons.star"}", "BspDungeon")\n'
        'SEEN = {}\n'
        'def pick_wall(material, x, y, z):\n'
        '    key = "%s,%s,%s" % (x, y, z)\n'
        '    if key in SEEN:\n'
        '        fail("wall picker called twice for one coordinate")\n'
        '    SEEN[key] = True\n'
        '    if (x + y + z) % 2 == 0:\n'
        '        return "minecraft:mossy_stone_bricks"\n'
        '    return material\n'
        'def build():\n'
        '    return BspDungeon(width=20, length=20, room_height=4, '
        'min_room_size=5, target_leaf_size=12, max_depth=2, '
        'surface_entrance=False, wall_picker=pick_wall)\n',
        encoding="utf-8",
    )
    result = build_file(source)
    names = {voxel.block.block_type for voxel in result.volume.voxels.values()}
    assert {"minecraft:stone_bricks", "minecraft:mossy_stone_bricks"} <= names


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
    base_torch_facings = {v.block.block_state["facing"] for v in base.volume.voxels.values()
                          if v.block.block_type == "minecraft:wall_torch"}
    torch_facings = {v.block.block_state["facing"] for v in turned.volume.voxels.values()
                     if v.block.block_type == "minecraft:wall_torch"}
    turns = {
        0: {"north": "north", "east": "east", "south": "south", "west": "west"},
        90: {"north": "east", "east": "south", "south": "west", "west": "north"},
        180: {"north": "south", "east": "west", "south": "north", "west": "east"},
        270: {"north": "west", "east": "north", "south": "east", "west": "south"},
    }
    assert door_facings == {turns[rotation][facing] for facing in base_door_facings}
    assert stair_facings == {turns[rotation][facing] for facing in base_stair_facings}
    assert torch_facings == {turns[rotation][facing] for facing in base_torch_facings}


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
    write_build_outputs(result, first)
    write_build_outputs(build_file(EXAMPLE), second)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".meta.json").read_bytes() == second.with_suffix(".meta.json").read_bytes()
    assert first.with_suffix(".meta.json").read_text() == '{\n  "ground_level": 10,\n  "y_offset": -10\n}\n'

    # The validated door geometry survives sparse structure serialization.
    decoded = nbtlib.load(first)
    palette = [str(entry["Name"]) for entry in decoded["palette"]]
    blocks = {
        Point(*map(int, entry["pos"])): palette[int(entry["state"])]
        for entry in decoded["blocks"]
    }
    assert list(map(int, decoded["size"])) == [96, 15, 96]
    for x in (47, 48):
        for z in (0, 1, 2):
            assert blocks[Point(x, 10, z)] == "minecraft:polished_andesite"
        for step in range(10):
            y, z = 10 - step, 3 + step
            assert blocks[Point(x, y, z)] == "minecraft:stone_brick_stairs"
            assert blocks[Point(x, y + 1, z)] == "minecraft:air"
            assert blocks[Point(x, y + 4, z)] in STONE_BRICKS
    surface_doors = [entry for entry in decoded["blocks"]
                     if int(entry["pos"][1]) in (11, 12) and int(entry["pos"][2]) == 0
                     and palette[int(entry["state"])] == "minecraft:oak_door"]
    assert len(surface_doors) == 4
    assert {str(decoded["palette"][int(e["state"])]["Properties"]["hinge"])
            for e in surface_doors} == {"left", "right"}
    door = next(op for op in result.operations
                if op.assembly_name == "bsp_dungeon_door" and op.writes[0].pos.y == 1)
    occupied = {write.pos for write in door.writes}
    for lower in [write for write in door.writes if write.block.block_state["half"] == "lower"]:
        front = {
            "north": Point(0, 0, -1), "south": Point(0, 0, 1),
            "east": Point(1, 0, 0), "west": Point(-1, 0, 0),
        }[lower.block.block_state["facing"]]
        side = Point(front.z, 0, -front.x)
        for height in (0, 1):
            anchor = lower.pos + Point(0, height, 0)
            for neighbor in (anchor + side, anchor - side):
                if neighbor not in occupied:
                    assert blocks[neighbor] in STONE_BRICKS
            assert blocks[anchor + front] == blocks[anchor - front] == "minecraft:air"
        for height in (2, 3):
            assert blocks[lower.pos + Point(0, height, 0)] in STONE_BRICKS


def test_reference_rooms_are_furnished_by_type():
    result = build_file(EXAMPLE)
    props = result.component_ir.props
    assert props["mob_room_count"] > 0
    assert props["furnished_room_count"] > props["mob_room_count"]

    by_type = {}
    for voxel in result.volume.voxels.values():
        by_type.setdefault(voxel.block.block_type, []).append(voxel)

    # All room lighting is wall-mounted; the count prop matches the voxels.
    assert "minecraft:torch" not in by_type
    torches = (by_type["minecraft:wall_torch"]
               + by_type.get("minecraft:soul_wall_torch", []))
    assert len(torches) == props["wall_torch_count"]

    # Mob rooms each carry exactly one spawner with a known mob, and no light.
    spawners = by_type["minecraft:spawner"]
    assert len(spawners) == props["mob_room_count"]
    assert all(v.block.block_nbt["SpawnData"]["entity"]["id"]
               in {"minecraft:zombie", "minecraft:skeleton", "minecraft:spider"}
               for v in spawners)

    # Treasure chests roll the dungeon loot table; armoury chests hold gear.
    chests = by_type["minecraft:chest"]
    assert any(v.block.block_nbt.get("LootTable") == "minecraft:chests/simple_dungeon"
               for v in chests)
    assert any(v.block.block_nbt.get("Items") for v in chests)

    assert "minecraft:bookshelf" in by_type
    assert "minecraft:skeleton_skull" in by_type
    assert any(e.entity.entity_type == "minecraft:armor_stand"
               for e in result.entities)


def test_reference_dungeon_has_seeded_height_biased_weathering():
    result = build_file(EXAMPLE)
    assert result.component_ir.props["mossy_percent"] == 0.15
    assert result.component_ir.props["cracked_percent"] == 0.07

    by_height = {}
    names = []
    for point, voxel in result.volume.voxels.items():
        name = voxel.block.block_type
        if name not in STONE_BRICKS:
            continue
        names.append(name)
        by_height.setdefault(point.y, []).append(name)

    def ratio(height, material):
        layer = by_height[height]
        return layer.count(material) / len(layer)

    assert ratio(1, "minecraft:mossy_stone_bricks") > ratio(
        3, "minecraft:mossy_stone_bricks")
    assert ratio(3, "minecraft:mossy_stone_bricks") > ratio(
        5, "minecraft:mossy_stone_bricks")
    cracked_ratio = names.count("minecraft:cracked_stone_bricks") / len(names)
    assert abs(cracked_ratio - 0.07) < 0.02

    clean = build_file(EXAMPLE, props={"mossy_percent": 0.0, "cracked_percent": 0.0})
    clean_names = [voxel.block.block_type for voxel in clean.volume.voxels.values()]
    assert clean_names.count("minecraft:stone_bricks") == len(names)
    assert "minecraft:mossy_stone_bricks" not in clean_names
    assert "minecraft:cracked_stone_bricks" not in clean_names


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
    {"mossy_percent": -0.01},
    {"cracked_percent": 1.01},
    {"mossy_percent": 0.8, "cracked_percent": 0.3},
])
def test_invalid_dungeon_controls_fail_through_starlark_diagnostics(props):
    with pytest.raises(BuildError, match="starlark_error"):
        build_file(EXAMPLE, props=props)


@pytest.mark.parametrize("props", [
    {"seed": 0, "room_height": 3, "burial_depth": 0, "wide_corridor_chance": 0.0},
    {"seed": 17, "wide_corridor_chance": 1.0},
    {"seed": 101, "burial_depth": 6},
    {"seed": 102},
    {"seed": 17, "room_height": 7},
    {"seed": 20250721, "width": 96, "length": 96},
])
def test_entrance_has_continuous_floor_enclosed_stairs_and_wide_connected_paths(props):
    result = build_file(EXAMPLE, props={"width": 48, "length": 48, **props})
    volume = result.volume
    level = result.component_ir.props["surface_level"]
    height = result.component_ir.props["room_height"]
    center = result.volume.bounds.size.x // 2
    for x in (center - 1, center):
        for z in (0, 1, 2):
            assert volume.block_at(Point(x, level, z)).block_type == "minecraft:polished_andesite"
        for step in range(level):
            y, z = level - step, 3 + step
            tread = volume.block_at(Point(x, y, z))
            assert tread.block_type == "minecraft:stone_brick_stairs"
            assert tread.block_state["facing"] == "north"
            assert volume.block_at(Point(x, y - 1, z)).block_type == "minecraft:polished_andesite"
            for dy in (1, 2, 3):
                assert volume.block_at(Point(x, y + dy, z)).block_type in {
                    "minecraft:air", "minecraft:wall_torch"}
            assert volume.block_at(Point(x, y + 4, z)).block_type in STONE_BRICKS
            for side in (center - 2, center + 1):
                for dy in range(5):
                    assert volume.block_at(Point(side, y + dy, z)).block_type in STONE_BRICKS

    if height > 4:
        for x in range(center - 2, center + 2):
            for y in range(6, height + 2):
                assert volume.block_at(Point(x, y, level + 2)).block_type in STONE_BRICKS

    # Identify the emitted full-height tunnel carvings, independently of their
    # generation order. Every cell must remain part of a connected 2x2 route.
    corridors = set()
    for op in result.operations:
        if op.kind != "carve_region" or len(op.writes) != height:
            continue
        cells = {(w.pos.x, w.pos.z) for w in op.writes}
        if len(cells) == 1 and {w.pos.y for w in op.writes} == set(range(1, height + 1)):
            corridors.update(cells)
    assert corridors
    walkable = set()
    for p, voxel in volume.voxels.items():
        if p.y != 1 or voxel.block.block_type not in {"minecraft:air", "minecraft:oak_door"}:
            continue
        above = volume.voxels.get(p + Point(0, 1, 0))
        floor = volume.voxels.get(p - Point(0, 1, 0))
        if (above and above.block.block_type in {"minecraft:air", "minecraft:oak_door"}
                and floor and floor.block.block_type == "minecraft:polished_andesite"):
            walkable.add((p.x, p.z))
    assert corridors <= walkable
    anchors = {(x, z) for x, z in walkable
               if {(x + 1, z), (x, z + 1), (x + 1, z + 1)} <= walkable}
    start = next(anchor for anchor in anchors if anchor in corridors)
    seen, queue = {start}, deque([start])
    while queue:
        x, z = queue.popleft()
        for neighbor in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            if neighbor in anchors and neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    for x, z in corridors:
        assert any(anchor in seen for anchor in ((x, z), (x - 1, z), (x, z - 1), (x - 1, z - 1))), (x, z)
