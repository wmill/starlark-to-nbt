"""Positioning helpers preserve explicit-transform geometry and validation."""

import hashlib
from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file, build_source
from starlark_to_nbt.serialize import write_structure_nbt

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("explicit", [False, True])
def test_at_matches_transform_including_entities_and_states(tmp_path, rotation, explicit):
    child = '''component("Part", {}, group([
        place_block([0,0,0], block("minecraft:oak_stairs", {"facing":"south"})),
        place_entity([1,0,2], entity("minecraft:pig", yaw=0)),
    ]), min_size=[2,1,3])'''
    positioned = f"at([1,0,1], {child}, rotation={rotation}" + (", size=[3,1,4])" if explicit else ")")
    size = "[3,1,4]" if explicit else "[2,1,3]"
    original = f"transform([1,0,1], {rotation}, {size}, {child})"
    decoded = []
    for i, expression in enumerate((original, positioned)):
        result = build_source(f"def build():\n    return {expression}\n", root_size=Point(8,2,8))
        output = tmp_path / f"{i}.nbt"
        write_structure_nbt(result.volume, output)
        decoded.append(nbtlib.load(output))
    assert decoded[0] == decoded[1]
    assert len(decoded[1]["entities"]) == 1
    assert len(decoded[1]["blocks"]) == 1


@pytest.mark.parametrize("expression,code", [
    ('at([0,0,0], group([]))', "missing_component_size"),
    ('at([0,0,0], group([]), size=[0,1,1])', "invalid_ir"),
    ('at([0,0,0], group([]), size=[True,1,1])', "invalid_ir"),
    ('at([0,0,0], group([]), size=[1,1])', "invalid_ir"),
    ('at([0.5,0,0], group([]), size=[1,1,1])', "invalid_ir"),
    ('at([0,0,0], group([]), size=[1,1,1], rotation=45)', "invalid_ir"),
    ('at([0,0,0], group([]), size=[1,1,1], rotation=True)', "invalid_ir"),
    ('at([2,0,0], group([]), size=[1,1,1])', "transform_overflow"),
    ('at([0,0,0], component("Part", {}, group([]), min_size=[2,1,1]), size=[1,1,1])', "component_too_small"),
])
def test_at_invalid_inputs(expression, code):
    with pytest.raises(BuildError) as error:
        build_source(f"def build():\n    return {expression}\n", root_size=Point(2,2,2))
    assert error.value.diagnostics[0].code == code


@pytest.mark.parametrize("name,digest", [
    ("cottage", "aa9a8b99497fe716523b5c4d83823e98b438fed406ccefb1a268b5cb00264dd0"),
    ("market_square", "9e7b5f79953b9f46f841a0bc357457dbbdc6bc5bfd1a93c2d956bbb0cd6d8345"),
])
def test_converted_examples_preserve_reference_nbt(tmp_path, name, digest):
    # Baselines captured from the original explicit-transform examples.
    result = build_file(ROOT / "examples" / f"{name}.star")
    output = tmp_path / "example.nbt"
    write_structure_nbt(result.volume, output)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == digest
    assert len(nbtlib.load(output)["blocks"]) == len(result.volume.voxels)
