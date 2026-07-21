from __future__ import annotations

from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.execute import dense_to_dict
from starlark_to_nbt.ir import Phase
from starlark_to_nbt.model import Point
from starlark_to_nbt.pipeline import build_file, write_build_outputs
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

    assert result.metadata.ground_level == 0
    assert result.metadata.y_offset == 0
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


def test_medieval_manor_matches_reference_scale_profile_and_interior(tmp_path):
    source = EXAMPLES / "medieval_manor.star"
    result = build_file(source)

    assert result.volume.bounds.size == Point(20, 18, 18)
    assert result.metadata.to_dict() == {"ground_level": 1, "y_offset": -1}
    assert len(result.volume.voxels) == 1621

    # The west entrance is a rotated, atomic double door reached from the
    # gravel path, and both main floors retain their stair landings.
    assert result.volume.block_at(Point(0, 0, 8)).block_type == "minecraft:gravel"
    lower = result.volume.block_at(Point(3, 1, 8))
    upper = result.volume.block_at(Point(3, 2, 8))
    assert lower.block_type == upper.block_type == "minecraft:oak_door"
    assert lower.block_state["facing"] == upper.block_state["facing"] == "west"
    assert lower.block_state["half"] == "lower"
    assert upper.block_state["half"] == "upper"
    assert result.volume.block_at(Point(10, 4, 8)).block_type == "minecraft:oak_stairs"
    assert result.volume.block_at(Point(10, 4, 9)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(10, 9, 13)).block_type == "minecraft:oak_stairs"
    assert result.volume.block_at(Point(10, 9, 14)).block_type == "minecraft:oak_slab"

    # Source-like material bands and the oversized roof make this a manor,
    # despite the training description calling the original a small house.
    assert result.volume.block_at(Point(3, 3, 10)).block_type == "minecraft:stone_bricks"
    assert result.volume.block_at(Point(3, 6, 10)).block_type == "minecraft:birch_planks"
    assert result.volume.block_at(Point(9, 12, 4)).block_type == "minecraft:white_wool"
    assert result.volume.block_at(Point(1, 16, 8)).block_type == "minecraft:oak_slab"
    assert result.volume.block_at(Point(2, 11, 8)).block_type == "minecraft:glass"
    assert result.volume.block_at(Point(17, 11, 8)).block_type == "minecraft:glass"
    assert result.volume.block_at(Point(15, 1, 12)).block_type == "minecraft:enchanting_table"
    assert result.volume.block_at(Point(14, 5, 4)).block_type == "minecraft:red_bed"

    paths = {op.provenance.component_path for op in result.operations}
    assert any("DecorativeRoof" in path for path in paths)
    assert any("GroundFloorInterior" in path for path in paths)
    assert any("UpperFloorInterior" in path for path in paths)

    first = tmp_path / "manor-1.nbt"
    second = tmp_path / "manor-2.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(source).volume, second)
    assert first.read_bytes() == second.read_bytes()

    decoded = nbtlib.load(first)
    assert len(decoded["blocks"]) == 1621
    assert len(decoded["blocks"]) < 20 * 18 * 18
    palette = {str(entry["Name"]) for entry in decoded["palette"]}
    assert {
        "minecraft:stone_bricks", "minecraft:oak_planks", "minecraft:birch_planks",
        "minecraft:white_wool", "minecraft:glass_pane", "minecraft:bookshelf",
        "minecraft:brewing_stand", "minecraft:enchanting_table",
    } <= palette
    stocked = [entry for entry in decoded["blocks"] if "nbt" in entry and "Items" in entry["nbt"]]
    assert len(stocked) == 7
    assert any(len(entry["nbt"]["Items"]) >= 3 for entry in stocked)


def test_keep_stress_build_is_deterministic(tmp_path):
    result = build_file(EXAMPLES / "keep.star")

    assert result.volume.bounds.size == Point(33, 20, 33)
    assert len(result.volume.voxels) > 4000
    # The keep's ground floor occupies the foundation layer, so its walking
    # surface aligns with the lower half of the south door at Y=1.
    assert result.volume.block_at(Point(11, 0, 11)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(16, 1, 22)).block_type == "minecraft:oak_door"
    # A north-wall-backed ladder passes through the first upper floor.
    assert result.volume.block_at(Point(11, 1, 11)).block_type == "minecraft:ladder"
    assert result.volume.block_at(Point(11, 6, 11)).block_type == "minecraft:ladder"
    assert result.volume.block_at(Point(12, 6, 11)).block_type == "minecraft:oak_planks"
    # Tower arrow slits are carved and never refilled, so they survive into
    # the template as explicit air that clears the cell on paste.
    assert any(v.block.block_type == "minecraft:air" for v in result.volume.voxels.values())
    # Towers are placed at all four rotations and stay identical in mass.
    tower_counts: dict[str, int] = {}
    for op in result.operations:
        path = op.provenance.component_path
        if "/SquareTower/" in path or path.endswith("/SquareTower"):
            key = path.split("/SquareTower")[0]
            tower_counts[key] = tower_counts.get(key, 0) + len(op.writes)
    assert len(tower_counts) == 4
    assert len(set(tower_counts.values())) == 1

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(EXAMPLES / "keep.star").volume, second)
    assert first.read_bytes() == second.read_bytes()


def test_mega_castle_bounds_entities_content_and_determinism(tmp_path):
    result = build_file(EXAMPLES / "mega_castle.star")
    assert result.volume.bounds.size == Point(48, 40, 48)
    assert result.metadata.to_dict() == {"ground_level": 1, "y_offset": -1}
    assert len(result.volume.voxels) > 10_000
    palette = {voxel.block.block_type for voxel in result.volume.voxels.values()}
    assert len(palette) >= 20

    horses = [item for item in result.entities if item.entity.entity_type == "minecraft:horse"]
    assert len(horses) == 4
    assert {item.entity.nbt["Variant"] for item in horses} == {0, 256, 512, 768}
    assert all(10 <= item.pos.x < 21 and 28 <= item.pos.z < 41 for item in horses)

    first, second = tmp_path / "castle-1.nbt", tmp_path / "castle-2.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(result.volume, second)
    assert first.read_bytes() == second.read_bytes()
    decoded = nbtlib.load(first)
    labels = {
        str(message)
        for entry in decoded["blocks"] if "nbt" in entry and "front_text" in entry["nbt"]
        for message in entry["nbt"]["front_text"]["messages"]
    }
    assert {
        "AETHERCOURT", "THRONE HALL", "ROYAL ARMORY", "ROYAL STABLES",
        "GUEST AZURE", "GUEST VIOLET", "GUEST GOLD", "GUEST JADE",
        "LIBRARY", "WAR COUNCIL",
    } <= labels
    stocked = [entry for entry in decoded["blocks"] if "nbt" in entry and "Items" in entry["nbt"]]
    assert len(stocked) >= 9

    # Both stair cores pass through the second floor and finish beside an
    # intact upper landing instead of terminating beneath the floor plate.
    for x in (12, 34):
        for step in range(9):
            stair = result.volume.block_at(Point(x, 2 + step, 14 + step))
            assert stair.block_type == "minecraft:dark_oak_stairs"
        for z in range(19, 22):
            assert result.volume.block_at(Point(x, 10, z)).block_type == "minecraft:air"
        assert result.volume.block_at(Point(x, 10, 22)).block_type == "minecraft:dark_oak_stairs"
        assert result.volume.block_at(Point(x, 10, 23)).block_type == "minecraft:polished_diorite"

        upper_x = 13 if x == 12 else 33
        assert result.volume.block_at(Point(x, 11, 22)).block_type == "minecraft:air"
        assert result.volume.block_at(Point(x, 12, 22)).block_type == "minecraft:air"
        for step in range(9):
            stair = result.volume.block_at(Point(upper_x, 11 + step, 22 - step))
            assert stair.block_type == "minecraft:dark_oak_stairs"
            assert stair.block_state["facing"] == "north"
        for z in range(15, 18):
            assert result.volume.block_at(Point(upper_x, 19, z)).block_type == "minecraft:air"
        assert result.volume.block_at(Point(upper_x, 19, 14)).block_type == "minecraft:dark_oak_stairs"
        assert result.volume.block_at(Point(upper_x, 19, 13)).block_type == "minecraft:polished_diorite"

    guest_paths = {
        op.provenance.component_path
        for op in result.operations
        if "GuestChamber" in op.provenance.component_path
    }
    assert guest_paths
    for point, bed_type in [
        (Point(16, 11, 10), "minecraft:blue_bed"),
        (Point(16, 11, 18), "minecraft:purple_bed"),
        (Point(28, 11, 10), "minecraft:yellow_bed"),
        (Point(28, 11, 18), "minecraft:green_bed"),
    ]:
        assert result.volume.block_at(point).block_type == bed_type


@pytest.mark.parametrize(
    ("filename", "size", "voxel_count", "representative", "palette"),
    [
        ("riverside_farmstead.star", Point(41, 16, 35), 1367, "Footbridge",
         {"minecraft:wheat", "minecraft:hay_block", "minecraft:ladder", "minecraft:barrel"}),
        ("market_square.star", Point(35, 7, 35), 474, "MarketStall",
         {"minecraft:red_wool", "minecraft:blue_wool", "minecraft:cornflower", "minecraft:lantern"}),
    ],
)
def test_village_examples_are_sparse_composed_and_deterministic(
        tmp_path, filename, size, voxel_count, representative, palette):
    source = EXAMPLES / filename
    result = build_file(source)
    assert result.volume.bounds.size == size
    assert len(result.volume.voxels) == voxel_count
    assert any(representative in op.provenance.component_path for op in result.operations)
    assert all(result.volume.bounds.contains_point(write.pos) for op in result.operations for write in op.writes)

    first = tmp_path / (filename + ".first.nbt")
    second = tmp_path / (filename + ".second.nbt")
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(source).volume, second)
    assert first.read_bytes() == second.read_bytes()
    decoded = nbtlib.load(first)
    assert len(decoded["blocks"]) == voxel_count
    assert voxel_count < size.x * size.y * size.z
    names = {str(entry["Name"]) for entry in decoded["palette"]}
    assert palette <= names


def test_riverside_farmstead_embeds_terrain_layers_and_raises_props():
    result = build_file(EXAMPLES / "riverside_farmstead.star")

    assert result.metadata.ground_level == 1
    assert result.metadata.y_offset == -1
    assert result.volume.block_at(Point(2, 0, 3)).block_type == "minecraft:cobblestone"
    assert result.volume.block_at(Point(0, 0, 17)).block_type == "minecraft:water"
    assert result.volume.block_at(Point(17, 0, 24)).block_type == "minecraft:dirt_path"
    assert result.volume.block_at(Point(29, 1, 4)).block_type == "minecraft:hay_block"
    assert result.volume.block_at(Point(5, 1, 26)).block_type == "minecraft:oak_log"
    assert result.volume.block_at(Point(12, 1, 15)).block_type == "minecraft:oak_fence"
    # The last stair tread and neighboring upper floor share a Y=6 walking surface.
    assert result.volume.block_at(Point(11, 5, 9)).block_type == "minecraft:oak_stairs"
    assert result.volume.block_at(Point(10, 5, 9)).block_type == "minecraft:oak_planks"
    # The upper floor resumes after the top tread while the stairwell stays open.
    assert result.volume.block_at(Point(11, 5, 10)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(12, 5, 12)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(11, 5, 8)).block_type == "minecraft:air"


def test_market_square_contains_rotated_stall_posts_and_benches():
    result = build_file(EXAMPLES / "market_square.star")

    assert result.metadata.ground_level == 1
    assert result.metadata.y_offset == -1
    assert result.volume.block_at(Point(16, 0, 0)).block_type == "minecraft:dirt_path"
    assert result.volume.block_at(Point(5, 0, 12)).block_type == "minecraft:cobblestone"
    assert result.volume.block_at(Point(16, 1, 16)).block_type == "minecraft:cobblestone"
    assert result.volume.block_at(Point(5, 1, 5)).block_type == "minecraft:oak_fence"
    # The east stall is rotated 90 degrees; its striped canopy runs along Z.
    assert result.volume.block_at(Point(27, 4, 5)).block_type == "minecraft:blue_wool"
    bench_states = {v.block.block_state["facing"] for v in result.volume.voxels.values()
                    if v.block.block_type == "minecraft:oak_stairs"}
    assert bench_states == {"east", "west"}


@pytest.mark.parametrize(
    ("filename", "size", "voxel_count", "representative", "palette"),
    [
        ("frontier_outpost.star", Point(29, 14, 29), 1405, "Watchtower",
         {"minecraft:spruce_log", "minecraft:dark_oak_door", "minecraft:ladder", "minecraft:hay_block"}),
        ("stone_pass_fortress.star", Point(35, 16, 21), 1597, "Gatehouse",
         {"minecraft:stone_bricks", "minecraft:iron_bars", "minecraft:chain", "minecraft:water"}),
    ],
)
def test_fortification_examples_are_sparse_composed_and_deterministic(
        tmp_path, filename, size, voxel_count, representative, palette):
    source = EXAMPLES / filename
    result = build_file(source)
    assert result.volume.bounds.size == size
    assert len(result.volume.voxels) == voxel_count
    assert any(representative in op.provenance.component_path for op in result.operations)
    assert all(result.volume.bounds.contains_point(write.pos) for op in result.operations for write in op.writes)

    first = tmp_path / (filename + ".first.nbt")
    second = tmp_path / (filename + ".second.nbt")
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(source).volume, second)
    assert first.read_bytes() == second.read_bytes()
    decoded = nbtlib.load(first)
    assert len(decoded["blocks"]) == voxel_count
    assert voxel_count < size.x * size.y * size.z
    names = {str(entry["Name"]) for entry in decoded["palette"]}
    assert palette <= names


def test_frontier_gate_and_stone_pass_defenses_are_aligned():
    frontier = build_file(EXAMPLES / "frontier_outpost.star")
    gate = frontier.volume.block_at(Point(13, 1, 28))
    assert gate.block_type == "minecraft:dark_oak_door"
    assert gate.block_state["facing"] == "south"
    assert frontier.volume.block_at(Point(13, 0, 17)).block_type == "minecraft:coarse_dirt"
    assert frontier.metadata.ground_level == 1
    assert frontier.metadata.y_offset == -1

    fortress = build_file(EXAMPLES / "stone_pass_fortress.star")
    assert fortress.volume.block_at(Point(16, 1, 12)).block_type == "minecraft:iron_bars"
    assert fortress.volume.block_at(Point(16, 2, 13)).block_state["axis"] == "z"
    assert fortress.volume.block_at(Point(0, 0, 13)).block_type == "minecraft:water"
    assert fortress.volume.block_at(Point(3, 5, 7)).block_type == "minecraft:air"


def test_build_outputs_write_deterministic_metadata_sidecar(tmp_path):
    result = build_file(EXAMPLES / "frontier_outpost.star")
    output = tmp_path / "frontier.nbt"
    write_build_outputs(result, output)

    metadata = output.with_suffix(".meta.json")
    assert metadata.read_text(encoding="utf-8") == '{\n  "ground_level": 1,\n  "y_offset": -1\n}\n'


@pytest.mark.parametrize(
    ("filename", "size", "voxel_count", "representative", "palette"),
    [
        ("procedural_facade.star", Point(29, 8, 1), 211, "WaveFriezePanel",
         {"minecraft:white_concrete", "minecraft:black_concrete", "minecraft:red_concrete", "minecraft:mossy_cobblestone"}),
        ("procedural_pavilion.star", Point(13, 8, 13), 260, "Wing",
         {"minecraft:andesite", "minecraft:lantern", "minecraft:poppy", "minecraft:dandelion"}),
        ("procedural_ziggurat.star", Point(15, 17, 15), 1943, "ProceduralZiggurat",
         {"minecraft:stone_bricks", "minecraft:deepslate_bricks", "minecraft:blackstone",
          "minecraft:polished_blackstone", "minecraft:gilded_blackstone"}),
        ("procedural_spiral_stair.star", Point(9, 23, 9), 805, "ProceduralSpiralStair",
         {"minecraft:deepslate_tiles", "minecraft:polished_deepslate", "minecraft:cobbled_deepslate_stairs"}),
    ],
)
def test_procedural_examples_are_sparse_composed_and_deterministic(
        tmp_path, filename, size, voxel_count, representative, palette):
    source = EXAMPLES / filename
    result = build_file(source)
    assert result.volume.bounds.size == size
    assert len(result.volume.voxels) == voxel_count
    assert any(representative in op.provenance.component_path for op in result.operations)
    assert all(result.volume.bounds.contains_point(write.pos) for op in result.operations for write in op.writes)

    first = tmp_path / (filename + ".first.nbt")
    second = tmp_path / (filename + ".second.nbt")
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(source).volume, second)
    assert first.read_bytes() == second.read_bytes()
    decoded = nbtlib.load(first)
    assert len(decoded["blocks"]) == voxel_count
    assert voxel_count < size.x * size.y * size.z
    names = {str(entry["Name"]) for entry in decoded["palette"]}
    assert palette <= names


def test_procedural_facade_patterns_vary_by_formula():
    result = build_file(EXAMPLES / "procedural_facade.star")
    # Checkerboard: adjacent cells alternate.
    assert result.volume.block_at(Point(1, 0, 0)).block_type == "minecraft:white_concrete"
    assert result.volume.block_at(Point(2, 0, 0)).block_type == "minecraft:black_concrete"
    # Gradient: bottom and top rows land on different palette bands.
    assert result.volume.block_at(Point(8, 0, 0)).block_type == "minecraft:red_concrete"
    assert result.volume.block_at(Point(8, 7, 0)).block_type == "minecraft:magenta_concrete"


def test_procedural_pavilion_wing_is_stamped_at_all_four_rotations():
    result = build_file(EXAMPLES / "procedural_pavilion.star")
    lanterns = {(p.x, p.y, p.z) for p, v in result.volume.voxels.items() if v.block.block_type == "minecraft:lantern"}
    assert lanterns == {(1, 3, 6), (6, 3, 1), (6, 3, 11), (11, 3, 6)}


def test_procedural_ziggurat_gradient_and_crown():
    result = build_file(EXAMPLES / "procedural_ziggurat.star")
    assert result.volume.block_at(Point(0, 0, 0)).block_type == "minecraft:stone_bricks"
    assert result.volume.block_at(Point(7, 12, 7)).block_type == "minecraft:gilded_blackstone"
    # The wave-formula crown adds merlons above the topmost level.
    assert any(p.y >= 15 for p in result.volume.voxels)


def test_procedural_spiral_stair_uses_full_blocks_at_walkable_corners():
    result = build_file(EXAMPLES / "procedural_spiral_stair.star")
    corners = [
        Point(2, 1, 2),
        Point(6, 5, 2),
        Point(6, 9, 6),
        Point(2, 13, 6),
        Point(2, 17, 2),
    ]
    assert all(result.volume.block_at(pos).block_type == "minecraft:polished_deepslate"
               for pos in corners)
    assert result.volume.block_at(Point(3, 2, 2)).block_state["facing"] == "east"
    assert result.volume.block_at(Point(5, 10, 6)).block_state["facing"] == "west"


def test_claude_pergola_sign_carries_glowing_block_entity_text(tmp_path):
    result = build_file(EXAMPLES / "claude_pergola.star")
    assert result.volume.bounds.size == Point(11, 7, 13)
    assert result.metadata.ground_level == 1

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(build_file(EXAMPLES / "claude_pergola.star").volume, second)
    assert first.read_bytes() == second.read_bytes()

    decoded = nbtlib.load(first)
    # Block-entity data rides on block instances; the palette stays Name+Properties.
    assert all("nbt" not in entry for entry in decoded["palette"])
    with_nbt = [entry for entry in decoded["blocks"] if "nbt" in entry]
    assert len(with_nbt) == 1
    sign = with_nbt[0]
    assert str(decoded["palette"][int(sign["state"])]["Name"]) == "minecraft:oak_sign"
    front = sign["nbt"]["front_text"]
    assert [str(message) for message in front["messages"]] == ["", "Designed by", "Claude ☺", ""]
    assert str(front["color"]) == "orange"
    assert int(front["has_glowing_text"]) == 1
    assert int(sign["nbt"]["is_waxed"]) == 1


def test_container_helpers_pack_items_and_loot():
    from starlark_to_nbt.starlark_runtime import container_nbt, loot_nbt

    value = container_nbt(["minecraft:apple", {"id": "minecraft:bread", "count": 3},
                           {"slot": 8, "id": "minecraft:coal"}, "minecraft:stick"],
                          id="minecraft:barrel")
    assert value == {"id": "minecraft:barrel", "Items": [
        {"Slot": 0, "id": "minecraft:apple", "count": 1},
        {"Slot": 1, "id": "minecraft:bread", "count": 3},
        {"Slot": 8, "id": "minecraft:coal", "count": 1},
        {"Slot": 9, "id": "minecraft:stick", "count": 1},
    ]}
    with pytest.raises(ValueError, match="container item"):
        container_nbt([{"id": "minecraft:coal", "Count": 4}])
    assert loot_nbt("minecraft:chests/simple_dungeon", seed=7) == {
        "id": "minecraft:chest", "LootTable": "minecraft:chests/simple_dungeon", "LootTableSeed": 7,
    }


def test_showcase_containers_serialize_block_entity_items(tmp_path):
    showcase = Path(__file__).parents[1] / "lib" / "showcase.star"

    result = build_file(showcase, props={"name": "Chest"})
    output = tmp_path / "chest.nbt"
    write_structure_nbt(result.volume, output)
    decoded = nbtlib.load(output)
    (chest,) = list(decoded["blocks"])
    items = chest["nbt"]["Items"]
    assert [(int(i["Slot"]), str(i["id"]), int(i["count"])) for i in items] == [
        (0, "minecraft:bread", 3), (1, "minecraft:apple", 1),
    ]

    result = build_file(showcase, props={"name": "Barrel"})
    write_structure_nbt(result.volume, output)
    (barrel,) = list(nbtlib.load(output)["blocks"])
    assert str(barrel["nbt"]["LootTable"]) == "minecraft:chests/simple_dungeon"
    assert "Items" not in barrel["nbt"]
