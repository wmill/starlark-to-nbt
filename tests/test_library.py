"""Stress harness: every library component must build standalone (at its
showcase size, via the min_size root fallback) and under all four rotations,
with every write landing inside the root bounds."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.model import BuildError, Point

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


def test_repeater_carries_delay_and_rotates_facing():
    rep = build_file(SHOWCASE, props={"name": "Repeater"})   # output faces south
    south = rep.volume.block_at(Point(0, 0, 0))
    assert south.block_type == "minecraft:repeater"
    assert south.block_state["delay"] == "3"
    # Java's stored diode facing points from output toward input.
    assert south.block_state["facing"] == "north"
    turned = build_file(SHOWCASE, entry="rotated", props={"name": "Repeater", "rotation": 90})
    assert turned.volume.block_at(Point(0, 0, 0)).block_state["facing"] == "east"


def test_gate_has_solid_base_with_dust_on_top_and_inverting_torch():
    gate = build_file(SHOWCASE, props={"name": "NotGate"})   # base smooth_stone at y=0
    assert gate.volume.block_at(Point(0, 0, 0)).block_type == "minecraft:smooth_stone"
    assert gate.volume.block_at(Point(0, 1, 0)).block_type == "minecraft:redstone_wire"   # input dust
    torch = gate.volume.block_at(Point(0, 1, 2))
    assert torch.block_type == "minecraft:redstone_wall_torch"
    assert torch.block_state["facing"] == "south"
    assert gate.volume.block_at(Point(0, 1, 3)).block_type == "minecraft:redstone_wire"   # output dust
    # The inverting torch's facing rotates with the component.
    turned = build_file(SHOWCASE, entry="rotated", props={"name": "NotGate", "rotation": 90})
    torches = [v.block for v in turned.volume.voxels.values()
               if v.block.block_type == "minecraft:redstone_wall_torch"]
    assert torches and {t.block_state["facing"] for t in torches} == {"west"}


def test_dispenser_carries_container_nbt_and_extended_piston_is_atomic():
    disp = build_file(SHOWCASE, props={"name": "Dispenser"})   # Dispenser(["minecraft:arrow"])
    block = disp.volume.block_at(Point(0, 0, 0))
    assert block.block_type == "minecraft:dispenser"
    assert block.block_nbt is not None
    assert block.block_nbt["Items"][0]["id"] == "minecraft:arrow"

    piston = build_file(SHOWCASE, props={"name": "Piston"})     # Piston(sticky=True, extended=True)
    assemblies = [op for op in piston.operations if op.assembly_name == "piston"]
    assert len(assemblies) == 1 and len(assemblies[0].writes) == 2
    head = piston.volume.block_at(Point(0, 0, 1))
    assert head.block_type == "minecraft:piston_head" and head.block_state["type"] == "sticky"


def test_redstone_analog_primitives_and_copper_memory_have_valid_states():
    plate = build_file(SHOWCASE, props={"name": "WeightedPressurePlate"})
    assert plate.volume.block_at(Point(0, 0, 0)).block_state == {"power": "7"}

    wire = build_file(SHOWCASE, props={"name": "RedstoneWire"})
    assert wire.volume.block_at(Point(0, 0, 0)).block_state == {"power": "0"}

    bulb = build_file(SHOWCASE, props={"name": "CopperBulb"})
    assert bulb.volume.block_at(Point(0, 0, 0)).block_state == {
        "lit": "false", "powered": "false",
    }


def test_xor_has_isolated_inputs_product_torches_and_centered_output():
    xor = build_file(SHOWCASE, props={"name": "XorGate"})
    assert xor.volume.bounds.size == Point(5, 2, 7)
    assert xor.volume.block_at(Point(0, 1, 2)).block_state["facing"] == "north"
    assert xor.volume.block_at(Point(4, 1, 2)).block_state["facing"] == "north"
    assert xor.volume.block_at(Point(2, 1, 3)).block_type == "minecraft:redstone_wall_torch"
    assert xor.volume.block_at(Point(1, 1, 3)).block_state["facing"] == "east"
    assert xor.volume.block_at(Point(3, 1, 3)).block_state["facing"] == "west"
    assert xor.volume.block_at(Point(0, 1, 4)).block_type == "minecraft:redstone_wall_torch"
    assert xor.volume.block_at(Point(4, 1, 4)).block_type == "minecraft:redstone_wall_torch"
    output = xor.volume.block_at(Point(2, 1, 6))
    assert output.block_type == "minecraft:repeater"
    assert output.block_state["facing"] == "north"


def test_pulse_extender_delayed_branch_reaches_bulb_side_input():
    extender = build_file(SHOWCASE, props={"name": "PulseExtender"})
    assert extender.volume.block_at(Point(3, 1, 3)).block_type == "minecraft:redstone_wire"
    delayed_output = extender.volume.block_at(Point(2, 1, 3))
    assert delayed_output.block_type == "minecraft:repeater"
    assert delayed_output.block_state["facing"] == "east"
    assert extender.volume.block_at(Point(1, 1, 3)).block_type == "minecraft:copper_bulb"


def test_redstone_clock_has_diode_input_lock_and_explicit_output():
    clock = build_file(SHOWCASE, props={"name": "RedstoneClock"})
    assert clock.volume.bounds.size == Point(5, 2, 8)
    assert clock.volume.block_at(Point(1, 1, 1)).block_state["facing"] == "north"
    assert clock.volume.block_at(Point(2, 1, 3)).block_state["facing"] == "south"
    assert clock.volume.block_at(Point(2, 1, 4)).block_type == "minecraft:lever"
    assert clock.volume.block_at(Point(4, 1, 7)).block_state["facing"] == "north"


def test_item_sorter_has_overflow_safe_filter_inventory_and_locked_extractor():
    sorter = build_file(SHOWCASE, props={"name": "ItemSorter"})
    filter_hopper = sorter.volume.block_at(Point(1, 3, 1))
    assert filter_hopper.block_type == "minecraft:hopper"
    assert [item["count"] for item in filter_hopper.block_nbt["Items"]] == [41, 1, 1, 1, 1]
    assert filter_hopper.block_nbt["Items"][0]["id"] == "minecraft:redstone"
    assert {item["id"] for item in filter_hopper.block_nbt["Items"][1:]} == {
        "minecraft:light_gray_stained_glass_pane",
    }
    extractor = sorter.volume.block_at(Point(1, 2, 1))
    assert extractor.block_state == {"facing": "south", "enabled": "false"}


def test_extended_pistons_cover_all_six_facings_atomically(tmp_path):
    redstone = SHOWCASE.parent / "redstone.star"
    source = tmp_path / "pistons.star"
    source.write_text(
        f'load("{redstone}", "Piston")\n'
        'def build(facing="up"):\n'
        '    return Piston(sticky=True, facing=facing, extended=True)\n',
        encoding="utf-8",
    )
    expected = {
        "down": (Point(1, 2, 1), Point(0, 0, 0)),
        "up": (Point(1, 2, 1), Point(0, 1, 0)),
        "north": (Point(1, 1, 2), Point(0, 0, 0)),
        "south": (Point(1, 1, 2), Point(0, 0, 1)),
        "west": (Point(2, 1, 1), Point(0, 0, 0)),
        "east": (Point(2, 1, 1), Point(1, 0, 0)),
    }
    for facing, (size, head_pos) in expected.items():
        result = build_file(source, props={"facing": facing})
        assert result.volume.bounds.size == size
        assert result.volume.block_at(head_pos).block_type == "minecraft:piston_head"
        assemblies = [op for op in result.operations if op.assembly_name == "piston"]
        assert len(assemblies) == 1 and len(assemblies[0].writes) == 2


def test_redstone_argument_ranges_fail_in_starlark(tmp_path):
    redstone = SHOWCASE.parent / "redstone.star"
    source = tmp_path / "invalid.star"
    source.write_text(
        f'load("{redstone}", "Repeater")\n'
        'def build():\n'
        '    return Repeater(delay=5)\n',
        encoding="utf-8",
    )
    with pytest.raises(BuildError, match="delay must be between 1 and 4"):
        build_file(source)
