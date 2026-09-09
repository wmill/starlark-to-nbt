from __future__ import annotations

from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.execute import dense_to_dict
from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file, write_build_outputs
from starlark_to_nbt.serialize import DATA_VERSION_1_21_7, write_structure_nbt


EXAMPLES = Path(__file__).parents[1] / "examples"
EXAMPLE = EXAMPLES / "church.star"


def test_church_vertical_slice_and_deterministic_nbt(tmp_path):
    result = build_file(EXAMPLE, props={"width": 11, "length": 19, "height": 4})

    assert result.volume.bounds.size == Point(11, 10, 19)
    lower = result.volume.block_at(Point(5, 1, 0))
    upper = result.volume.block_at(Point(5, 2, 0))
    assert lower.block_type == upper.block_type == "minecraft:oak_door"
    assert lower.block_state["half"] == "lower"
    assert upper.block_state["half"] == "upper"
    assert lower.block_state["facing"] == upper.block_state["facing"] == "north"

    assemblies = [op for op in result.operations if op.assembly_name == "door"]
    pew_writes = [write for op in result.operations if "/Pew[" in op.provenance.component_path for write in op.writes]
    pew_paths = {op.provenance.component_path for op in result.operations if "/Pew[" in op.provenance.component_path}
    assert len(assemblies) == 1
    assert len(assemblies[0].writes) == 2
    assert len(pew_writes) == 2 * 7 * 3
    assert len(pew_paths) == 14
    lectern = result.volume.block_at(Point(5, 1, 16))
    assert lectern.block_type == "minecraft:lectern"
    assert lectern.block_state["facing"] == "south"
    assert all(
        result.volume.block_at(Point(x, 1, 17)).block_type == "minecraft:air"
        for x in range(1, 10)
    )
    roof_edge = result.volume.block_at(Point(0, 4, 9))
    assert roof_edge.block_type == "minecraft:oak_stairs"
    assert roof_edge.block_state["facing"] == "east"
    assert result.volume.block_at(Point(5, 9, 9)).block_type == "minecraft:oak_planks"
    assert all(result.volume.bounds.contains_point(write.pos) for op in result.operations for write in op.writes)

    dense = dense_to_dict(result.volume)
    assert dense["order"] == "y,z,x"
    assert dense["size"] == [11, 10, 19]

    first = tmp_path / "first.nbt"
    second = tmp_path / "second.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(result.volume, second)
    assert first.read_bytes() == second.read_bytes()

    decoded = nbtlib.load(first)
    assert int(decoded["DataVersion"]) == DATA_VERSION_1_21_7
    assert list(map(int, decoded["size"])) == [11, 10, 19]
    # Sparse template: only written voxels are listed; untouched cells are
    # absent so pasting preserves terrain.
    assert len(decoded["blocks"]) == len(result.volume.voxels)
    assert len(decoded["blocks"]) < 11 * 10 * 19
    assert len(decoded["entities"]) == 0
    palette_names = {str(entry["Name"]) for entry in decoded["palette"]}
    # The carved doorway is fully refilled by the door assembly, so no air
    # voxels survive into the palette.
    assert palette_names == {
        "minecraft:lectern", "minecraft:oak_door", "minecraft:oak_planks", "minecraft:oak_stairs",
        "minecraft:stone_bricks",
    }


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
        "minecraft:white_wool", "minecraft:glass", "minecraft:bookshelf",
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
         {"minecraft:stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:cracked_stone_bricks",
          "minecraft:iron_bars", "minecraft:chain", "minecraft:water"}),
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


def test_stone_pass_weathering_percentages_are_configurable_and_validated():
    source = EXAMPLES / "stone_pass_fortress.star"
    result = build_file(source)
    names = [voxel.block.block_type for voxel in result.volume.voxels.values()]
    stone_types = {
        "minecraft:stone_bricks", "minecraft:mossy_stone_bricks", "minecraft:cracked_stone_bricks",
    }
    stone_count = sum(name in stone_types for name in names)
    mossy_count = names.count("minecraft:mossy_stone_bricks")
    cracked_count = names.count("minecraft:cracked_stone_bricks")
    assert stone_count == 1174
    assert mossy_count == 165
    assert cracked_count == 74
    assert abs(mossy_count / stone_count - 0.15) < 0.01
    assert abs(cracked_count / stone_count - 0.07) < 0.01

    clean = build_file(source, props={"mossy_percent": 0.0, "cracked_percent": 0.0})
    clean_names = [voxel.block.block_type for voxel in clean.volume.voxels.values()]
    assert clean_names.count("minecraft:stone_bricks") == stone_count
    assert "minecraft:mossy_stone_bricks" not in clean_names
    assert "minecraft:cracked_stone_bricks" not in clean_names

    mossy = build_file(source, props={"mossy_percent": 1.0, "cracked_percent": 0.0})
    mossy_names = [voxel.block.block_type for voxel in mossy.volume.voxels.values()]
    assert mossy_names.count("minecraft:mossy_stone_bricks") == stone_count
    assert "minecraft:stone_bricks" not in mossy_names

    for props in [
        {"mossy_percent": -0.01},
        {"cracked_percent": 1.01},
        {"mossy_percent": 0.8, "cracked_percent": 0.3},
    ]:
        with pytest.raises(BuildError) as info:
            build_file(source, props=props)
        assert info.value.diagnostics[0].code == "starlark_error"


def test_build_outputs_replace_existing_nbt_and_metadata_sidecar(tmp_path):
    result = build_file(EXAMPLES / "frontier_outpost.star")
    output = tmp_path / "frontier.nbt"
    metadata = output.with_suffix(".meta.json")
    output.write_bytes(b"stale nbt")
    metadata.write_text("stale metadata\n", encoding="utf-8")

    write_build_outputs(result, output)

    decoded = nbtlib.load(output)
    assert list(map(int, decoded["size"])) == [29, 14, 29]
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
        ("procedural_slab_spiral.star", Point(25, 16, 25), 784, "ProceduralSlabSpiral",
         {"minecraft:smooth_stone_slab"}),
        ("procedural_rotunda.star", Point(19, 19, 19), 1453, "ProceduralRotunda",
         {"minecraft:smooth_stone", "minecraft:quartz_block", "minecraft:glass"}),
        ("procedural_twisting_spire.star", Point(9, 40, 9), 960, "ProceduralTwistingSpire",
         {"minecraft:purpur_block", "minecraft:end_stone_bricks",
          "minecraft:purpur_pillar", "minecraft:quartz_block"}),
        ("procedural_crystal_cave.star", Point(25, 7, 17), 1259, "ProceduralCrystalCave",
         {"minecraft:tuff", "minecraft:deepslate", "minecraft:dripstone_block", "minecraft:amethyst_block"}),
        ("procedural_fractal_tree.star", Point(12, 22, 14), 349, "ProceduralFractalTree",
         {"minecraft:oak_wood", "minecraft:oak_leaves"}),
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


def test_procedural_slab_spiral_is_a_hollow_round_half_step_corkscrew():
    result = build_file(EXAMPLES / "procedural_slab_spiral.star")

    # The circular annulus leaves both the central shaft and the square
    # footprint's corners empty through the full height.
    assert all(result.volume.block_at(Point(12, y, 12)).block_type == "minecraft:air"
               for y in range(16))
    assert all(result.volume.block_at(Point(x, y, z)).block_type == "minecraft:air"
               for x, z in [(0, 0), (0, 24), (24, 0), (24, 24)]
               for y in range(16))

    # Successive wedges alternate slab halves, then climb into the next block
    # cell. The second turn repeats the same footprint eight blocks higher.
    expected = [
        (Point(24, 0, 12), "bottom"),
        (Point(22, 0, 16), "top"),
        (Point(20, 1, 20), "bottom"),
        (Point(24, 8, 12), "bottom"),
        (Point(22, 8, 16), "top"),
        (Point(20, 9, 20), "bottom"),
        (Point(22, 15, 8), "top"),
    ]
    for pos, slab_type in expected:
        slab = result.volume.block_at(pos)
        assert slab.block_type == "minecraft:smooth_stone_slab"
        assert slab.block_state == {"type": slab_type, "waterlogged": "false"}

    # Cardinal edge cells exist at their angular heights, proving the outer
    # ring reaches the circle while its diagonal corners remain clipped.
    assert result.volume.block_at(Point(12, 2, 24)).block_type == "minecraft:smooth_stone_slab"
    assert result.volume.block_at(Point(0, 4, 12)).block_type == "minecraft:smooth_stone_slab"
    assert result.volume.block_at(Point(12, 6, 0)).block_type == "minecraft:smooth_stone_slab"


def test_procedural_rotunda_shell_is_hollow_with_periodic_windows():
    result = build_file(EXAMPLES / "procedural_rotunda.star")
    assert result.volume.block_at(Point(9, 0, 9)).block_type == "minecraft:smooth_stone"
    assert result.volume.block_at(Point(9, 0, 1)).block_type == "minecraft:smooth_stone"
    # Interior is hollow, not a solid disk of blocks under the dome.
    assert result.volume.block_at(Point(9, 4, 9)).block_type == "minecraft:air"
    # The dome apex is a deliberate open oculus.
    assert result.volume.block_at(Point(9, 18, 9)).block_type == "minecraft:air"
    # The dome's base layer is a ring, not a disk: present at the outer edge,
    # absent at the center of that same height.
    assert result.volume.block_at(Point(18, 9, 9)).block_type == "minecraft:glass"
    assert result.volume.block_at(Point(9, 9, 9)).block_type == "minecraft:air"
    # Both window and plain wall columns exist in the annulus.
    assert result.volume.block_at(Point(0, 1, 9)).block_type == "minecraft:glass"
    assert result.volume.block_at(Point(1, 1, 5)).block_type == "minecraft:quartz_block"


def test_procedural_twisting_spire_ring_offset_cycles_through_table():
    result = build_file(EXAMPLES / "procedural_twisting_spire.star")
    # Level 1's offset table entry [1, 1] shifts the ring's corner to (2, 2).
    assert result.volume.block_at(Point(2, 2, 2)).block_type == "minecraft:end_stone_bricks"
    # Level 0's corner position is now vacated at level 1's height.
    assert result.volume.block_at(Point(0, 2, 0)).block_type == "minecraft:air"
    # Level 4 wraps back to offset table entry [0, 0], reusing the origin corner.
    assert result.volume.block_at(Point(0, 8, 0)).block_type == "minecraft:purpur_block"
    # Ring interior is hollow.
    assert result.volume.block_at(Point(3, 0, 3)).block_type == "minecraft:air"


def test_procedural_crystal_cave_hash_scatter_is_deterministic_and_bounded():
    result = build_file(EXAMPLES / "procedural_crystal_cave.star")
    # Bounding-box corner sits outside the ellipse: proves the footprint
    # isn't a rectangle.
    assert result.volume.block_at(Point(0, 3, 0)).block_type == "minecraft:air"
    # A known non-scatter interior cell stays hollow.
    assert result.volume.block_at(Point(3, 3, 6)).block_type == "minecraft:air"
    assert any(v.block.block_type == "minecraft:dripstone_block" for v in result.volume.voxels.values())
    assert any(v.block.block_type == "minecraft:amethyst_block" for v in result.volume.voxels.values())

    first_dripstone = {p for p, v in result.volume.voxels.items() if v.block.block_type == "minecraft:dripstone_block"}
    second = build_file(EXAMPLES / "procedural_crystal_cave.star")
    second_dripstone = {p for p, v in second.volume.voxels.items() if v.block.block_type == "minecraft:dripstone_block"}
    assert first_dripstone == second_dripstone


def test_procedural_fractal_tree_terminal_tips_get_leaf_blobs_without_overwriting_wood():
    result = build_file(EXAMPLES / "procedural_fractal_tree.star")
    assert result.volume.block_at(Point(4, 0, 6)).block_type == "minecraft:oak_wood"
    leaf_voxels = [v for v in result.volume.voxels.values() if v.block.block_type == "minecraft:oak_leaves"]
    assert len(leaf_voxels) > 0
    assert leaf_voxels[0].block.block_state["persistent"] == "true"


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


def test_redstone_showcase_is_labeled_interactive_and_deterministic(tmp_path):
    source = EXAMPLES / "redstone_showcase.star"
    result = build_file(source)
    assert result.volume.bounds.size == Point(82, 12, 90)
    assert result.metadata.to_dict() == {"ground_level": 3, "y_offset": -3}

    first = tmp_path / "redstone-1.nbt"
    second = tmp_path / "redstone-2.nbt"
    write_build_outputs(result, first)
    write_build_outputs(build_file(source), second)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".meta.json").read_bytes() == second.with_suffix(".meta.json").read_bytes()
    assert first.with_suffix(".meta.json").read_text() == '{\n  "ground_level": 3,\n  "y_offset": -3\n}\n'

    decoded = nbtlib.load(first)
    signs = [
        entry for entry in decoded["blocks"]
        if "nbt" in entry and "front_text" in entry["nbt"]
    ]
    assert len(signs) == 70
    headings = {
        str(entry["nbt"]["front_text"]["messages"][0])
        for entry in signs
    }
    assert {
        "REDSTONE LAB", "NOT", "OR", "NOR", "NAND", "AND", "XOR", "XNOR",
        "T FLIP-FLOP", "PULSE EXTENDER", "REPEATER CLOCK",
        "HOPPER CLOCK", "PISTON BRIDGE", "2x2 PISTON DOOR", "ITEM SORTER",
        "LAMP MATRIX", "ANALOG METER",
    } <= headings

    palette_names = {str(entry["Name"]) for entry in decoded["palette"]}
    assert {
        "minecraft:lever", "minecraft:stone_button", "minecraft:redstone_lamp",
        "minecraft:copper_bulb", "minecraft:comparator", "minecraft:hopper",
        "minecraft:sticky_piston",
    } <= palette_names

    blocks = {tuple(map(int, entry["pos"])): entry for entry in decoded["blocks"]}

    def decoded_block(pos):
        entry = blocks[pos]
        return decoded["palette"][int(entry["state"])], entry.get("nbt")

    assert list(map(int, decoded["size"])) == [82, 12, 90]
    assert {str(decoded["palette"][int(e["state"])]["Properties"]["rotation"])
            for e in signs} == {"8"}
    # Matrix controls are wall-mounted against individual backing blocks.
    for x in range(68, 73):
        for y in range(3, 6):
            spec, _ = decoded_block((x, y, 76))
            assert str(spec["Name"]) == "minecraft:lever"
            assert str(spec["Properties"]["facing"]) == "north"
            assert str(decoded_block((x, y, 77))[0]["Name"]) == "minecraft:smooth_stone"
            assert str(decoded_block((x, y, 78))[0]["Name"]) == "minecraft:redstone_lamp"
    # Each analog sample has its own north-output diode and numbered lamp.
    for x in range(64, 79):
        assert str(decoded_block((x, 4, 55))[0]["Name"]) == "minecraft:redstone_wire"
        spec, _ = decoded_block((x, 4, 54))
        assert str(spec["Name"]) == "minecraft:repeater"
        assert str(spec["Properties"]["facing"]) == "south"
        assert str(decoded_block((x, 4, 53))[0]["Name"]) == "minecraft:redstone_lamp"
    # Empty input, onward line and reject; supplies are separate from transport.
    for pos in [(50, 8, 77), (51, 7, 82), (50, 4, 77)]:
        assert not decoded_block(pos)[1]["Items"]
    for pos, facing in [((50, 7, 77), "south"), ((50, 7, 78), "east")] + [
            ((51, 7, z), "south") for z in range(78, 82)]:
        spec, nbt = decoded_block(pos)
        assert str(spec["Name"]) == "minecraft:hopper"
        assert str(spec["Properties"]["facing"]) == facing
        assert not nbt["Items"]
    analog_supply = decoded_block((63, 3, 49))[1]["Items"]
    assert len({str(i["id"]) for i in analog_supply}) == 15
    assert all(int(i["count"]) == 1 for i in analog_supply)
    # The repaired clock and door survive serialization with their drive paths.
    assert str(decoded_block((49, 4, 54))[0]["Properties"]["extended"]) == "true"
    assert str(decoded_block((50, 4, 54))[0]["Name"]) == "minecraft:piston_head"
    for x, facing in [(48, "east"), (53, "west")]:
        assert str(decoded_block((x, 4, 55))[0]["Properties"]["facing"]) == facing
    for x in (47, 54):
        assert str(decoded_block((x, 4, 56))[0]["Name"]) == "minecraft:redstone_wire"
        assert str(decoded_block((x, 4, 57))[0]["Name"]) == "minecraft:redstone_lamp"
    for x in (30, 31):
        for y in (3, 4):
            for z in range(75, 79):
                assert (x, y, z) not in blocks
    supply = decoded_block((46, 3, 72))[1]["Items"]
    assert [(str(i["id"]), int(i["count"])) for i in supply] == [
        ("minecraft:redstone", 32), ("minecraft:cobblestone", 32)]
    assert [int(i["count"]) for i in decoded_block((50, 6, 77))[1]["Items"]] == [41, 1, 1, 1, 1]
    for x in range(9, 12):
        for y in (1, 2):
            assert str(decoded_block((x, y, 78))[0]["Name"]) == "minecraft:air"


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


def test_redstone_gallery_has_separate_stations_and_walkable_approaches():
    volume = build_file(EXAMPLES / "redstone_showcase.star").volume

    def name(x, y, z):
        voxel = volume.voxels.get(Point(x, y, z))
        return voxel.block.block_type if voxel else "minecraft:air"

    # The full inter-station aisles have a floor and two blocks of headroom.
    for x in range(82):
        for z in range(90):
            if x in (20, 21, 40, 41, 60, 61) or z in (22, 23, 44, 45, 66, 67):
                assert name(x, 2, z) == "minecraft:polished_andesite"
                assert name(x, 3, z) in ("minecraft:air", "minecraft:dark_oak_sign")
                assert name(x, 4, z) == "minecraft:air"
    # North and south door approaches, plus the passage itself, are two high.
    for x in (30, 31):
        for z in range(72, 84):
            for y in (3, 4):
                assert name(x, y, z) == "minecraft:air"
            assert name(x, 2, z) != "minecraft:air"
    # Bridge moving blocks start north of the trench; banks and bypass remain.
    for x in range(9, 12):
        assert name(x, 2, 77) == "minecraft:smooth_stone"
        assert name(x, 2, 78) == "minecraft:air"
        assert name(x, 2, 80) == "minecraft:polished_andesite"
    for x in (8, 12):
        assert name(x, 2, 78) == "minecraft:polished_andesite"
        assert name(x, 3, 78) == name(x, 4, 78) == "minecraft:air"
    # Continuous two-wide stair access to the elevated sorter inventories.
    for i in range(5):
        for x in (53, 54):
            stair = volume.block_at(Point(x, 3 + i, 71 + i))
            assert stair.block_type == "minecraft:deepslate_tile_stairs"
            assert stair.block_state["facing"] == "south"
            assert name(x, 4 + i, 71 + i) == name(x, 5 + i, 71 + i) == "minecraft:air"
    for x in (53, 54):
        for z in range(76, 84):
            assert name(x, 7, z) == "minecraft:deepslate_tiles"
            assert name(x, 8, z) == name(x, 9, z) == "minecraft:air"
    # Each control/inventory is within interaction range of clear floor or
    # the sorter balcony. Exclude circuit pads from candidate standing cells.
    standing = []
    for x in range(82):
        for z in range(90):
            for y, floor in [(3, "minecraft:polished_andesite"), (8, "minecraft:deepslate_tiles")]:
                if (name(x, y - 1, z) == floor
                        and name(x, y, z) in ("minecraft:air", "minecraft:dark_oak_sign")
                        and name(x, y + 1, z) == "minecraft:air"):
                    standing.append((x + 0.5, y + 1.62, z + 0.5))
    interactive = {"minecraft:lever", "minecraft:stone_button", "minecraft:barrel",
                   "minecraft:hopper", "minecraft:light_weighted_pressure_plate"}
    for pos, voxel in volume.voxels.items():
        if voxel.block.block_type in interactive:
            distance_squared = min((x - pos.x - 0.5) ** 2 + (y - pos.y - 0.5) ** 2
                                   + (z - pos.z - 0.5) ** 2 for x, y, z in standing)
            assert distance_squared < 4.5 ** 2, (pos, voxel.block.block_type)


def test_moonspire_magical_city_preserves_landmarks_furnishings_and_metadata(tmp_path):
    source = EXAMPLES / "moonspire_magical_city.star"
    result = build_file(source)
    assert result.volume.bounds.size == Point(63, 59, 67)
    assert len(result.volume.voxels) == 56893
    assert result.metadata.to_dict() == {"ground_level": 10, "y_offset": -10}
    for pos, material in [
        (Point(31, 57, 18), "minecraft:end_rod"),  # observatory pinnacle
        (Point(4, 36, 4), "minecraft:amethyst_block"),  # guardian tower
        (Point(31, 18, 45), "minecraft:sea_lantern"),  # floating crystal core
        (Point(31, 5, 66), "minecraft:quartz_stairs"),  # descending approach
        (Point(10, 11, 12), "minecraft:air"),  # hollow guild-house interior
    ]:
        assert result.volume.block_at(pos).block_type == material

    first = tmp_path / "moonspire-1.nbt"
    second = tmp_path / "moonspire-2.nbt"
    write_build_outputs(result, first)
    write_build_outputs(build_file(source), second)
    assert first.read_bytes() == second.read_bytes()
    assert first.with_suffix(".meta.json").read_bytes() == second.with_suffix(".meta.json").read_bytes()
    assert first.with_suffix(".meta.json").read_text() == '{\n  "ground_level": 10,\n  "y_offset": -10\n}\n'

    decoded = nbtlib.load(first)
    assert list(map(int, decoded["size"])) == [63, 59, 67]
    chests = [entry["nbt"] for entry in decoded["blocks"]
              if str(decoded["palette"][int(entry["state"])]["Name"]) == "minecraft:chest"]
    assert len(chests) == 6
    for chest in chests:
        assert [(str(item["id"]), int(item["count"])) for item in chest["Items"]] == [
            ("minecraft:amethyst_shard", 16)]
    headings = {str(entry["nbt"]["front_text"]["messages"][0])
                for entry in decoded["blocks"]
                if "nbt" in entry and "front_text" in entry["nbt"]}
    assert headings == {"MOONSPIRE", "Moonlit Library", "Alchemist's Rest", "Starlight Inn",
                        "Crystal Atelier", "Astral Cartography", "Enchanter's House"}
