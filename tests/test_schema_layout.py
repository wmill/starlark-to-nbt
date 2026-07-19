from __future__ import annotations

import pytest

from starlark_to_nbt.ir import BuildMetadata, Fill, Fixed, Group, Inset, PlaceBlock, Repeat, Split
from starlark_to_nbt.layout import resolve
from starlark_to_nbt.model import Axis, BlockSpec, Box, BuildError, Point
from starlark_to_nbt.schema import parse_node


STONE = BlockSpec("minecraft:stone")


def leaf():
    return PlaceBlock(Point(0, 0, 0), STONE, "structure")


def test_schema_rejects_unknown_fields_and_bool_coordinates():
    with pytest.raises(BuildError, match="unknown fields"):
        parse_node({"kind": "group", "children": [], "surprise": 1})
    with pytest.raises(BuildError, match="expected an integer"):
        parse_node({"kind": "place_block", "pos": [True, 0, 0], "block": {"block_type": "minecraft:stone"}})


def test_root_component_parses_typed_metadata():
    node = parse_node({
        "kind": "component",
        "name": "Embedded",
        "props": {},
        "min_size": [1, 2, 1],
        "metadata": {"ground_level": 1},
        "body": {"kind": "place_block", "pos": [0, 0, 0], "block": {"block_type": "minecraft:stone"}},
    })
    assert node.metadata == BuildMetadata(1)
    assert node.metadata.y_offset == -1


@pytest.mark.parametrize(
    "metadata", [{"ground_level": True}, {"ground_level": -1}, {"surprise": 1}],
)
def test_schema_rejects_invalid_metadata(metadata):
    with pytest.raises(BuildError, match="invalid_metadata"):
        parse_node({
            "kind": "component", "name": "Invalid", "props": {}, "metadata": metadata,
            "body": {"kind": "group", "children": []},
        })


def test_schema_rejects_metadata_on_nested_components():
    with pytest.raises(BuildError, match="metadata_not_root"):
        parse_node({
            "kind": "component", "name": "Root", "props": {},
            "body": {
                "kind": "component", "name": "Nested", "props": {},
                "metadata": {"ground_level": 1},
                "body": {"kind": "group", "children": []},
            },
        })


def test_split_allocates_fixed_and_fill_with_deterministic_remainder():
    node = Split(Axis.X, (Fill(), Fixed(2), Fill()), (leaf(), leaf(), leaf()))
    resolved = resolve(node, Box.from_size(Point(9, 1, 1)))
    assert [child.region.extent(Axis.X) for child in resolved.children] == [4, 2, 3]
    assert [child.region.min.x for child in resolved.children] == [0, 4, 6]
    assert resolved.children[-1].region.max.x == 9


def test_split_and_repeat_report_insufficient_space():
    split_node = Split(Axis.X, (Fixed(3), Fixed(3)), (leaf(), leaf()))
    with pytest.raises(BuildError, match="split_overflow"):
        resolve(split_node, Box.from_size(Point(5, 1, 1)))

    repeat_node = Repeat(Axis.Z, 3, 2, 1, leaf())
    with pytest.raises(BuildError, match="repeat_overflow"):
        resolve(repeat_node, Box.from_size(Point(1, 1, 7)))


def test_explicit_repeat_allocates_gaps_and_paths():
    node = Repeat(Axis.Z, 3, 1, 2, leaf())
    resolved = resolve(node, Box.from_size(Point(2, 1, 8)))
    assert [(child.region.min.z, child.region.max.z) for child in resolved.children] == [(0, 1), (3, 4), (6, 7)]
    assert [child.path for child in resolved.children] == ["Repeat/item[0]", "Repeat/item[1]", "Repeat/item[2]"]


def test_inset_allocates_inner_box_and_rejects_collapse():
    amounts = {Axis.X: (1, 2), Axis.Y: (1, 0), Axis.Z: (2, 1)}
    resolved = resolve(Inset(amounts, leaf()), Box.from_size(Point(8, 3, 9)))
    assert resolved.children[0].region == Box(Point(1, 1, 2), Point(6, 3, 8))
    with pytest.raises(BuildError, match="inset_collapsed"):
        resolve(Inset({Axis.X: (1, 1), Axis.Y: (0, 0), Axis.Z: (0, 0)}, leaf()), Box.from_size(Point(2, 1, 1)))
