from __future__ import annotations

import pytest

from starlark_to_nbt.execute import execute
from starlark_to_nbt.ir import (
    BlockOperation, BlockWrite, BuildMetadata, DoorSupportedOnBothSides, Phase,
    ValidatorPlacement,
)
from starlark_to_nbt.model import BlockSpec, Box, BuildError, Point, Provenance
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.validators import validator_diagnostics

BOUNDS = Box.from_size(Point(7, 4, 7))
ROOT = Provenance("Root", BOUNDS)
DOOR_OWNER = Provenance("Root/body/Door", BOUNDS)
STONE = BlockSpec("minecraft:stone")


def door_operation(facing: str = "south", name: str = "door") -> BlockOperation:
    states = {"facing": facing, "hinge": "left", "open": "false", "powered": "false"}
    return BlockOperation(Phase.FIXTURE, "place_assembly", (
        BlockWrite(Point(3, 1, 3), BlockSpec("minecraft:oak_door", {**states, "half": "lower"})),
        BlockWrite(Point(3, 2, 3), BlockSpec("minecraft:oak_door", {**states, "half": "upper"})),
    ), DOOR_OWNER, name, 1)


def structure_operation(points: list[Point], block: BlockSpec = STONE) -> BlockOperation:
    return BlockOperation(
        Phase.STRUCTURE, "test", tuple(BlockWrite(point, block) for point in points),
        DOOR_OWNER, sequence=0,
    )


def diagnostics(operations: list[BlockOperation], ground_level: int = 0):
    volume = execute(operations, BOUNDS)
    placement = ValidatorPlacement(DoorSupportedOnBothSides("door"), ROOT)
    return validator_diagnostics(
        [placement], operations, volume, BOUNDS, BuildMetadata(ground_level),
    )


def test_door_with_full_height_jambs_and_clear_passage_passes():
    jambs = [Point(x, y, 3) for x in (2, 4) for y in (1, 2)]
    assert diagnostics([structure_operation(jambs), door_operation()]) == []


def test_door_reports_missing_jamb_and_blocked_passage_cells():
    jambs = [Point(2, 1, 3), Point(2, 2, 3), Point(4, 1, 3)]
    obstruction = BlockOperation(
        Phase.STRUCTURE, "test", (BlockWrite(Point(3, 2, 4), STONE),),
        DOOR_OWNER, sequence=0,
    )
    errors = diagnostics([structure_operation(jambs), obstruction, door_operation()])
    assert [error.code for error in errors] == ["door_not_supported", "doorway_obstructed"]
    assert errors[0].details["side"] == "left"
    assert errors[0].details["half"] == "upper"
    assert errors[1].details["direction"] == "front"


def test_door_validator_uses_rotated_facing_for_jambs():
    jambs = [Point(3, y, z) for z in (2, 4) for y in (1, 2)]
    assert diagnostics([structure_operation(jambs), door_operation("east")]) == []


def test_unwritten_buried_jambs_are_terrain_when_passage_is_explicit_air():
    air = BlockSpec("minecraft:air")
    passage = [Point(3, y, z) for y in (1, 2) for z in (2, 4)]
    assert diagnostics(
        [structure_operation(passage, air), door_operation()], ground_level=4,
    ) == []


def test_validator_rejects_malformed_target_and_ignores_out_of_scope_assembly():
    malformed = BlockOperation(
        Phase.FIXTURE, "place_assembly", (BlockWrite(Point(1, 1, 1), STONE),),
        DOOR_OWNER, "door", 0,
    )
    outside = BlockOperation(
        Phase.FIXTURE, "place_assembly", (BlockWrite(Point(5, 1, 5), STONE),),
        Provenance("Other", BOUNDS), "door", 2,
    )
    errors = diagnostics([malformed, outside])
    assert [error.code for error in errors] == ["invalid_validator_target"]


def test_validator_reports_selector_with_no_targets():
    assert [error.code for error in diagnostics([])] == ["validator_no_targets"]


def test_declared_validator_fails_the_build_pipeline(tmp_path):
    source = tmp_path / "unsupported_door.star"
    source.write_text(
        '''def build():
    state = {"facing": "south", "hinge": "left", "open": "false", "powered": "false"}
    return component(
        name="UnsupportedDoor",
        props={},
        min_size=[5, 4, 5],
        validators=[validator("door_supported_on_both_sides", assembly="door")],
        body=group([
            fill_region([1, 1, 2], [2, 3, 3], block("minecraft:stone")),
            place_assembly([2, 1, 2], "door", [1, 2, 1], [
                {"pos": [0, 0, 0], "block": block("minecraft:oak_door", dict(state, half="lower"))},
                {"pos": [0, 1, 0], "block": block("minecraft:oak_door", dict(state, half="upper"))},
            ]),
        ]),
    )
''',
        encoding="utf-8",
    )
    with pytest.raises(BuildError) as error:
        build_file(source)
    assert {diagnostic.code for diagnostic in error.value.diagnostics} == {
        "door_not_supported",
    }
