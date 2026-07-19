from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.schema import parse_node
from starlark_to_nbt.serialize import write_structure_nbt
from starlark_to_nbt.starlark_runtime import evaluate_source


def placement(entity):
    return {"kind": "place_entity", "pos": [0, 0, 0], "entity": entity}


def test_entity_schema_validates_id_orientation_nbt_and_reserved_fields():
    node = parse_node(placement({"entity_type": "minecraft:horse", "yaw": 12, "pitch": -45,
                                 "nbt": {"Tame": True, "Tags": ["royal"]}}))
    assert node.entity.yaw == 12.0
    assert node.entity.nbt["Tags"] == ["royal"]
    for entity in [
        {"entity_type": "horse"},
        {"entity_type": "minecraft:horse", "yaw": float("inf")},
        {"entity_type": "minecraft:horse", "pitch": 91},
        {"entity_type": "minecraft:horse", "nbt": {"UUID": [1, 2, 3, 4]}},
    ]:
        with pytest.raises(BuildError):
            parse_node(placement(entity))


def test_runtime_constructors_and_nested_rotation():
    source = '''
def build():
    pony = component("Pony", {}, place_entity([1, 0, 2], entity("minecraft:horse", yaw=5)), min_size=[3, 2, 4])
    inner = transform([0, 0, 0], 90, [3, 2, 4], pony)
    return component("Root", {}, transform([0, 0, 0], 90, [4, 2, 3], inner), min_size=[3, 2, 4])
'''
    node = evaluate_source(source, "entity.star", "build", {})
    from starlark_to_nbt.layout import resolve
    from starlark_to_nbt.lowering import lower_all
    from starlark_to_nbt.model import Box
    result = lower_all(resolve(node, Box.from_size(Point(3, 2, 4))))
    assert len(result.entities) == 1
    assert result.entities[0].entity.yaw == 185


def test_entity_structure_serialization_is_centered_ordered_and_deterministic(tmp_path):
    source = '''
def build():
    return component("Entities", {}, group([
        place_entity([2, 0, 3], entity("minecraft:horse", {"Tame": True}, yaw=90, pitch=10)),
        place_entity([0, 1, 0], entity("minecraft:armor_stand")),
    ]), min_size=[4, 3, 5])
'''
    star = tmp_path / "entities.star"
    star.write_text(source)
    result = build_file(star)
    first, second = tmp_path / "one.nbt", tmp_path / "two.nbt"
    write_structure_nbt(result.volume, first)
    write_structure_nbt(result.volume, second)
    assert first.read_bytes() == second.read_bytes()
    entities = nbtlib.load(first)["entities"]
    assert list(map(int, entities[0]["blockPos"])) == [2, 0, 3]
    assert list(map(float, entities[0]["pos"])) == [2.5, 0.0, 3.5]
    assert list(map(float, entities[0]["nbt"]["Rotation"])) == [90.0, 10.0]
    assert "UUID" not in entities[0]["nbt"]


def test_entity_anchor_overflow_is_diagnostic(tmp_path):
    star = tmp_path / "overflow.star"
    star.write_text('def build():\n    return component("Bad", {}, place_entity([1, 0, 0], entity("minecraft:pig")), min_size=[1, 1, 1])\n')
    with pytest.raises(BuildError, match="entity_component_overflow"):
        build_file(star)
