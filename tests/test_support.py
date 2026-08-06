from __future__ import annotations

import pytest

from starlark_to_nbt.execute import execute
from starlark_to_nbt.ir import BlockOperation, BlockWrite, BuildMetadata, Phase
from starlark_to_nbt.model import BlockSpec, Box, BuildError, Point, Provenance
from starlark_to_nbt.support import validate_support

BOUNDS = Box.from_size(Point(4, 4, 4))
PROVENANCE = Provenance("Test", BOUNDS)

STONE = BlockSpec("minecraft:stone")
DUST = BlockSpec("minecraft:redstone_wire")


def volume_of(*writes, bounds=BOUNDS):
    operations = [
        BlockOperation(phase, "test", (BlockWrite(Point(*pos), block),), PROVENANCE, None, sequence)
        for sequence, (phase, pos, block) in enumerate(writes)
    ]
    return execute(operations, bounds)


def check(*writes, bounds=BOUNDS, ground_level=0):
    validate_support(volume_of(*writes, bounds=bounds), bounds, BuildMetadata(ground_level))


def test_dust_on_solid_passes():
    check(
        (Phase.STRUCTURE, (1, 0, 1), STONE),
        (Phase.FIXTURE, (1, 1, 1), DUST),
    )


def test_dust_over_unwritten_interior_cell_fails():
    with pytest.raises(BuildError, match="unsupported_block") as error:
        check((Phase.FIXTURE, (1, 2, 1), DUST))
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.coordinates == Point(1, 2, 1)
    assert diagnostic.component_path == "Test"
    assert diagnostic.details["support"] == [1, 1, 1]


def test_dust_over_terrain_below_ground_level_passes():
    check((Phase.FIXTURE, (1, 2, 1), DUST), ground_level=3)


def test_standalone_part_at_structure_floor_passes():
    bounds = Box.from_size(Point(1, 1, 1))
    check((Phase.FIXTURE, (0, 0, 0), DUST), bounds=bounds)


def test_dust_on_carved_air_fails():
    with pytest.raises(BuildError, match="unsupported_block"):
        check(
            (Phase.STRUCTURE, (1, 0, 1), STONE),
            (Phase.CARVE, (1, 0, 1), BlockSpec("minecraft:air")),
            (Phase.FIXTURE, (1, 1, 1), DUST),
        )


def test_dust_on_non_solid_support_fails():
    repeater = BlockSpec("minecraft:repeater", {"facing": "north"})
    with pytest.raises(BuildError, match="rests on minecraft:repeater"):
        check(
            (Phase.STRUCTURE, (1, 0, 1), STONE),
            (Phase.FIXTURE, (1, 1, 1), repeater),
            (Phase.FIXTURE, (1, 2, 1), DUST),
        )


def test_wall_torch_needs_block_behind_facing():
    torch = BlockSpec("minecraft:redstone_wall_torch", {"facing": "south", "lit": "true"})
    check(
        (Phase.STRUCTURE, (1, 1, 1), STONE),
        (Phase.FIXTURE, (1, 1, 2), torch),
    )
    with pytest.raises(BuildError, match="unsupported_block"):
        check((Phase.FIXTURE, (1, 1, 2), torch))


def test_plain_wall_torch_needs_block_behind_facing():
    torch = BlockSpec("minecraft:wall_torch", {"facing": "east"})
    check(
        (Phase.STRUCTURE, (1, 1, 1), STONE),
        (Phase.FIXTURE, (2, 1, 1), torch),
    )
    with pytest.raises(BuildError, match="unsupported_block"):
        check((Phase.FIXTURE, (2, 1, 1), torch))


def test_plain_torch_needs_block_below():
    torch = BlockSpec("minecraft:torch")
    check(
        (Phase.STRUCTURE, (1, 0, 1), STONE),
        (Phase.FIXTURE, (1, 1, 1), torch),
    )
    with pytest.raises(BuildError, match="unsupported_block"):
        check((Phase.FIXTURE, (1, 2, 1), torch))


def test_lever_face_determines_support_cell():
    floor_lever = BlockSpec("minecraft:lever", {"face": "floor", "facing": "south"})
    check(
        (Phase.STRUCTURE, (1, 0, 1), STONE),
        (Phase.FIXTURE, (1, 1, 1), floor_lever),
    )
    wall_button = BlockSpec("minecraft:stone_button", {"face": "wall", "facing": "south"})
    check(
        (Phase.STRUCTURE, (1, 1, 1), STONE),
        (Phase.FIXTURE, (1, 1, 2), wall_button),
    )
    with pytest.raises(BuildError, match="unsupported_block"):
        check(
            (Phase.STRUCTURE, (1, 0, 2), STONE),  # below, but wall face needs behind
            (Phase.FIXTURE, (1, 1, 2), wall_button),
        )


def test_pressure_plate_needs_block_below():
    plate = BlockSpec("minecraft:light_weighted_pressure_plate", {"power": "0"})
    with pytest.raises(BuildError, match="unsupported_block"):
        check((Phase.FIXTURE, (1, 1, 1), plate))


def test_all_violations_reported_in_one_error():
    with pytest.raises(BuildError) as error:
        check(
            (Phase.FIXTURE, (1, 1, 1), DUST),
            (Phase.FIXTURE, (2, 1, 1), DUST),
        )
    assert len(error.value.diagnostics) == 2
    assert all(d.code == "unsupported_block" for d in error.value.diagnostics)


def test_non_attachable_blocks_are_ignored():
    check((Phase.STRUCTURE, (1, 2, 1), BlockSpec("minecraft:redstone_lamp", {"lit": "false"})))
