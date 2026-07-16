from __future__ import annotations

import pytest

from starlark_to_nbt.execute import SparseVolume, _execute_operation, execute
from starlark_to_nbt.ir import AssemblyBlock, BlockOperation, BlockWrite, Component, Phase, PlaceAssembly
from starlark_to_nbt.layout import resolve
from starlark_to_nbt.lowering import lower
from starlark_to_nbt.model import AIR, BlockSpec, Box, BuildError, Point, Provenance, Transform


BOUNDS = Box.from_size(Point(4, 4, 4))
PROVENANCE = Provenance("Test", BOUNDS)


def operation(phase, writes, kind="test", assembly=None, sequence=0):
    return BlockOperation(phase, kind, tuple(BlockWrite(Point(*pos), block) for pos, block in writes),
                          PROVENANCE, assembly, sequence)


def test_quarter_turn_rotates_coordinates_and_facing_four_times():
    point = Point(0, 0, 0)
    block = BlockSpec("minecraft:oak_stairs", {"facing": "south"})
    size = Point(2, 1, 2)
    for _ in range(4):
        transform = Transform(Point(0, 0, 0), 90, size)
        point = transform.apply_point(point)
        block = block.transformed(transform)
    assert point == Point(0, 0, 0)
    assert block.block_state["facing"] == "south"


def test_structure_phase_allows_identical_rewrites_but_rejects_differing_blocks():
    stone = BlockSpec("minecraft:stone")
    volume = execute([
        operation(Phase.STRUCTURE, [((1, 1, 1), stone), ((2, 1, 1), stone)], sequence=0),
        operation(Phase.STRUCTURE, [((2, 1, 1), stone), ((3, 1, 1), stone)], sequence=1),
    ], BOUNDS)
    assert volume.block_at(Point(2, 1, 1)) == stone

    with pytest.raises(BuildError, match="block_conflict"):
        execute([
            operation(Phase.STRUCTURE, [((1, 1, 1), stone)], sequence=0),
            operation(Phase.STRUCTURE, [((1, 1, 1), BlockSpec("minecraft:oak_planks"))], sequence=1),
        ], BOUNDS)


def test_fixture_phase_rejects_even_identical_overlaps():
    lantern = BlockSpec("minecraft:lantern")
    with pytest.raises(BuildError, match="block_conflict"):
        execute([
            operation(Phase.FIXTURE, [((1, 1, 1), lantern)], sequence=0),
            operation(Phase.FIXTURE, [((1, 1, 1), lantern)], sequence=1),
        ], BOUNDS)


def test_fixture_phase_fill_region_lowers_into_fixture_operations():
    from starlark_to_nbt.ir import FillRegion
    node = Component("Carpet", {}, FillRegion(Box.from_size(Point(2, 1, 2)),
                                              BlockSpec("minecraft:red_carpet"), "fixture"))
    operations = lower(resolve(node, Box.from_size(Point(2, 1, 2))))
    assert [op.phase for op in operations] == [Phase.FIXTURE]
    assert len(operations[0].writes) == 4


def test_phases_allow_carve_then_fixture_but_reject_solid_overwrite():
    stone = BlockSpec("minecraft:stone")
    door = BlockSpec("minecraft:oak_door", {"half": "lower"})
    volume = execute([
        operation(Phase.STRUCTURE, [((1, 1, 1), stone)], sequence=0),
        operation(Phase.CARVE, [((1, 1, 1), AIR)], sequence=1),
        operation(Phase.FIXTURE, [((1, 1, 1), door)], sequence=2),
    ], BOUNDS)
    assert volume.block_at(Point(1, 1, 1)) == door

    with pytest.raises(BuildError, match="block_conflict"):
        execute([
            operation(Phase.STRUCTURE, [((1, 1, 1), stone)], sequence=0),
            operation(Phase.FIXTURE, [((1, 1, 1), door)], sequence=1),
        ], BOUNDS)


def test_assembly_operation_is_atomic_on_collision():
    stone = BlockSpec("minecraft:stone")
    door = BlockSpec("minecraft:oak_door")
    volume = SparseVolume(BOUNDS, {})
    _execute_operation(volume, operation(Phase.STRUCTURE, [((1, 2, 1), stone)]))
    assembly = operation(Phase.FIXTURE, [((1, 1, 1), door), ((1, 2, 1), door)], "place_assembly", "door")
    with pytest.raises(BuildError, match="block_conflict"):
        _execute_operation(volume, assembly)
    assert volume.block_at(Point(1, 1, 1)) == AIR
    assert volume.block_at(Point(1, 2, 1)) == stone


def test_declared_assembly_bounds_must_fit_even_when_a_cell_is_unoccupied():
    door = BlockSpec("minecraft:oak_door")
    node = Component(
        "Door", {}, PlaceAssembly(Point(0, 0, 0), "door", Point(1, 2, 1),
                                  (AssemblyBlock(Point(0, 0, 0), door),)),
    )
    with pytest.raises(BuildError, match="assembly_overflow"):
        lower(resolve(node, Box.from_size(Point(1, 1, 1))))
