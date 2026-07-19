"""Stress harness: every library component must build standalone (at its
showcase size, via the min_size root fallback) and under all four rotations,
with every write landing inside the root bounds."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.model import Point

SHOWCASE = Path(__file__).parents[1] / "lib" / "showcase.star"


def _component_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))


COMPONENT_NAMES = _component_names()


def test_showcase_names_cover_all_library_constructors():
    lib_dir = SHOWCASE.parent
    exported = set()
    for star in lib_dir.glob("*.star"):
        if star.name == "showcase.star":
            continue
        exported |= set(re.findall(r"^def ([A-Z]\w*)\(", star.read_text(encoding="utf-8"), re.M))
    assert exported == set(COMPONENT_NAMES)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
def test_component_builds_standalone(name):
    result = build_file(SHOWCASE, props={"name": name})
    assert len(result.volume.voxels) > 0 or len(result.entities) > 0
    assert all(result.volume.bounds.contains_point(write.pos)
               for op in result.operations for write in op.writes)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_component_builds_under_rotation(name, rotation):
    result = build_file(SHOWCASE, entry="rotated", props={"name": name, "rotation": rotation})
    assert len(result.volume.voxels) > 0 or len(result.entities) > 0
    assert all(result.volume.bounds.contains_point(write.pos)
               for op in result.operations for write in op.writes)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
def test_rotations_preserve_voxel_count(name):
    counts = {
        rotation: len(build_file(SHOWCASE, entry="rotated",
                                 props={"name": name, "rotation": rotation}).volume.voxels)
        for rotation in (0, 90, 180, 270)
    }
    assert len(set(counts.values())) == 1, counts


def test_horse_rotations_preserve_entity_and_yaw():
    for rotation in (0, 90, 180, 270):
        result = build_file(SHOWCASE, entry="rotated", props={"name": "Horse", "rotation": rotation})
        assert len(result.entities) == 1
        assert result.entities[0].entity.yaw == rotation
        assert result.volume.bounds.contains_point(result.entities[0].pos)


def test_straight_staircase_ascends_south_one_level_per_row():
    result = build_file(SHOWCASE, props={"name": "StraightStaircase"})
    for z in range(4):
        assert result.volume.block_at(Point(0, z, z)).block_state["facing"] == "south"
        assert Point(0, z + 1, z) not in result.volume.voxels


def test_ladder_and_counter_face_south_and_rotate():
    ladder = build_file(SHOWCASE, entry="rotated", props={"name": "Ladder", "rotation": 90})
    assert {v.block.block_state["facing"] for v in ladder.volume.voxels.values()} == {"west"}
    counter = build_file(SHOWCASE, props={"name": "KitchenCounter"})
    barrels = [v.block for v in counter.volume.voxels.values() if v.block.block_type == "minecraft:barrel"]
    assert barrels and {b.block_state["facing"] for b in barrels} == {"south"}


def test_footbridge_rails_connect_along_run_and_to_deck():
    result = build_file(SHOWCASE, props={"name": "Footbridge"})
    left = result.volume.block_at(Point(0, 1, 3))
    right = result.volume.block_at(Point(3, 1, 3))
    assert left.block_state == {"north": "true", "south": "true", "east": "true"}
    assert right.block_state == {"north": "true", "south": "true", "west": "true"}


def test_gable_roof_closes_triangular_ends():
    result = build_file(SHOWCASE, props={"name": "GableRoof"})
    # Showcase size is GableRoof(7, 9): the base of the triangle, between the
    # two eave stairs, must be solid at both gable ends, not open air.
    assert result.volume.block_at(Point(3, 0, 0)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(3, 0, 8)).block_type == "minecraft:oak_planks"
    assert result.volume.block_at(Point(2, 1, 0)).block_type == "minecraft:oak_planks"


def test_crop_plot_has_irrigated_farmland_and_mature_crops():
    result = build_file(SHOWCASE, props={"name": "CropPlot"})
    assert result.volume.block_at(Point(3, 0, 3)).block_type == "minecraft:water"
    assert result.volume.block_at(Point(2, 0, 3)).block_state["moisture"] == "7"
    assert result.volume.block_at(Point(2, 1, 3)).block_state["age"] == "7"


def test_flower_canopy_and_hay_patterns_are_alternating():
    flowers = build_file(SHOWCASE, props={"name": "FlowerBed"})
    assert flowers.volume.block_at(Point(1, 1, 1)).block_type == "minecraft:poppy"
    assert flowers.volume.block_at(Point(2, 1, 1)).block_type == "minecraft:dandelion"
    stall = build_file(SHOWCASE, props={"name": "MarketStall"})
    assert stall.volume.block_at(Point(0, 3, 1)).block_type == "minecraft:red_wool"
    assert stall.volume.block_at(Point(1, 3, 1)).block_type == "minecraft:white_wool"
    hay = build_file(SHOWCASE, props={"name": "HayBaleStack"})
    axes = {v.block.block_state["axis"] for v in hay.volume.voxels.values()}
    assert axes == {"x", "z"}


def test_stone_fortifications_have_openings_battlements_and_rotating_hardware():
    wall = build_file(SHOWCASE, props={"name": "BattlementWall"})
    assert wall.volume.block_at(Point(0, 5, 0)).block_type == "minecraft:stone_bricks"
    assert Point(1, 5, 0) not in wall.volume.voxels

    tower = build_file(SHOWCASE, props={"name": "SquareTower"})
    assert tower.volume.block_at(Point(3, 2, 0)).block_type == "minecraft:air"

    gatehouse = build_file(SHOWCASE, props={"name": "Gatehouse"})
    assert gatehouse.volume.block_at(Point(4, 0, 2)).block_type == "minecraft:air"
    assert gatehouse.volume.block_at(Point(4, 0, 4)).block_type == "minecraft:iron_bars"

    bridge = build_file(SHOWCASE, entry="rotated", props={"name": "Drawbridge", "rotation": 90})
    chains = [v.block for v in bridge.volume.voxels.values() if v.block.block_type == "minecraft:chain"]
    assert chains and {chain.block_state["axis"] for chain in chains} == {"x"}


def test_timber_fortifications_have_tips_atomic_gate_and_rotating_ladder():
    wall = build_file(SHOWCASE, props={"name": "PalisadeWall"})
    assert wall.volume.block_at(Point(0, 5, 0)).block_type == "minecraft:spruce_log"
    assert Point(1, 5, 0) not in wall.volume.voxels

    gate = build_file(SHOWCASE, props={"name": "PalisadeGate"})
    doors = [op for op in gate.operations if op.assembly_name == "double_door"]
    assert len(doors) == 1 and len(doors[0].writes) == 4

    tower = build_file(SHOWCASE, entry="rotated", props={"name": "Watchtower", "rotation": 90})
    ladders = [v.block for v in tower.volume.voxels.values() if v.block.block_type == "minecraft:ladder"]
    assert ladders and {ladder.block_state["facing"] for ladder in ladders} == {"west"}
    assert len(ladders) == 7
    assert tower.volume.block_at(Point(3, 6, 2)).block_type == "minecraft:ladder"
