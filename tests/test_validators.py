"""Declared validators end to end. The door validator's unit cases live in
crates/stnbt-core/src/validators.rs."""
from __future__ import annotations

import pytest

from starlark_to_nbt.model import BuildError
from starlark_to_nbt.pipeline import build_file


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
