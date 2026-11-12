"""Rust schema (crates/stnbt-core/src/schema.rs) vs Python schema.py.

Raw tagged-dict trees are captured from real examples and library
components. Each must parse to identical IR in both implementations
(compared as JSON text, so int/float and key order count). Seeded random
mutations of the smaller trees must then produce the same outcome: the same
IR, or the same first diagnostic (code, path, and message).
"""
from __future__ import annotations

import copy
import json
import random
import re
from pathlib import Path

import pytest

from starlark_to_nbt import _core, starlark_runtime
from starlark_to_nbt.model import BuildError
from starlark_to_nbt.pipeline import _jsonable
from starlark_to_nbt.schema import parse_node

pytestmark = pytest.mark.parity


ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "lib" / "showcase.star"
MUTATIONS_PER_TREE = 60
MUTANTS = [True, False, None, "x", "bogus", "minecraft:stone", -1, 0, 1, 90, 2.5, float("inf"),
           [], {}, [1, 2], [0, 0, 0], [1, 1, 1], {"kind": "nope"}, {"kind": "fill"}]


def _raw_tree(path: Path, entry: str = "build", props: dict | None = None):
    original = starlark_runtime.parse_node
    starlark_runtime.parse_node = lambda value, source_file=None: value
    try:
        return starlark_runtime.evaluate_file(path, entry, props or {})
    finally:
        starlark_runtime.parse_node = original


def _showcase_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))


def _python(tree, source_file):
    try:
        return "ok", json.dumps(_jsonable(parse_node(tree, source_file=source_file)))
    except BuildError as exc:
        return "error", [(d.code, d.component_path, d.message) for d in exc.diagnostics]


def _rust(tree, source_file):
    status, payload = _core.parse_ir(tree, source_file)
    if status == "ok":
        return "ok", json.dumps(payload)
    return "error", [tuple(item) for item in payload]


def _slots(value):
    """Every (container, key) position in the tree."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield value, key
            yield from _slots(item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield value, index
            yield from _slots(item)


LAYOUT_KINDS = {"component", "split", "inset", "repeat", "at", "transform"}
CHILD_KEYS = {"body", "child", "children"}


def _layout_slots(value):
    """Positions inside layout nodes' own fields (not their child subtrees)."""
    if isinstance(value, dict):
        if value.get("kind") in LAYOUT_KINDS:
            for key, item in value.items():
                yield value, key
                if key not in CHILD_KEYS:
                    yield from _slots(item)
        for key, item in value.items():
            yield from _layout_slots(item)
    elif isinstance(value, list):
        for item in value:
            yield from _layout_slots(item)


def _mutate(tree, rng: random.Random, slots=_slots):
    tree = copy.deepcopy(tree)
    container, key = rng.choice(list(slots(tree)))
    roll = rng.random()
    if isinstance(container, dict) and roll < 0.15:
        del container[key]
    elif isinstance(container, dict) and roll < 0.25:
        container["surprise"] = 1
    else:
        container[key] = copy.deepcopy(rng.choice(MUTANTS))
    return tree


EXAMPLES = sorted((ROOT / "examples").glob("*.star"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_parse_identically(path):
    tree = _raw_tree(path)
    assert _rust(tree, str(path)) == _python(tree, str(path))


def test_showcase_components_parse_identically_and_agree_under_mutation():
    rng = random.Random(20261111)
    outcomes = {"ok": 0, "error": 0}
    for name in _showcase_names():
        tree = _raw_tree(SHOWCASE, props={"name": name})
        assert _rust(tree, "showcase.star") == _python(tree, "showcase.star"), name
        for i in range(MUTATIONS_PER_TREE):
            mutated = _mutate(tree, rng)
            expected = _python(mutated, "showcase.star")
            assert _rust(mutated, "showcase.star") == expected, (name, i, expected)
            outcomes[expected[0]] += 1
    # Guard against a mutator that stops exercising the error paths.
    assert outcomes["error"] > outcomes["ok"] / 4, outcomes


# Examples that use split/inset/repeat/at/transform, metadata, and validators.
LAYOUT_EXAMPLES = ["church", "keep", "procedural_facade", "procedural_spiral_stair",
                   "redstone_showcase", "frontier_outpost", "rampart_ward"]


@pytest.mark.parametrize("stem", LAYOUT_EXAMPLES)
def test_layout_node_mutations_agree(stem):
    path = ROOT / "examples" / f"{stem}.star"
    tree = _raw_tree(path)
    rng = random.Random(stem)
    seen_errors = set()
    for i in range(150):
        mutated = _mutate(tree, rng, slots=_layout_slots)
        expected = _python(mutated, str(path))
        assert _rust(mutated, str(path)) == expected, (stem, i, expected)
        if expected[0] == "error":
            seen_errors.add(expected[1][0][2])
    assert len(seen_errors) >= 5, seen_errors


_STONE = {"block_type": "minecraft:stone"}
_EMPTY = {"kind": "group", "children": []}


def _comp(**fields):
    return {"kind": "component", "name": "C", "props": {}, "body": _EMPTY, **fields}


def _nested(**fields):
    return _comp(body=_comp(**fields))


# One input per reachable schema.py message (plus ordering edge cases).
# "object keys must be strings" and "props must contain only JSON-compatible
# values" cannot occur: starlark-pyo3 hands over JSON-shaped data.
HANDWRITTEN = {
    "not_object": [],
    "missing_kind": {"children": []},
    "unknown_kind": {"kind": "it's"},
    "missing_fields": {"kind": "repeat", "axis": "x"},
    "unknown_fields": {"kind": "group", "children": [], "b": 1, "a": 2},
    "name_empty": _comp(name=""),
    "props_not_object": _comp(props=[]),
    "source_not_object": _comp(source=[1]),
    "source_file_not_str": _comp(source={"file": 1}),
    "source_line_zero": _comp(source={"file": "f", "line": 0}),
    "source_falsy_falls_back": _comp(source={}),
    "metadata_not_root": _nested(metadata={"ground_level": 1}),
    "metadata_none_nested_ok": _nested(metadata=None),
    "metadata_unknown": _comp(metadata={"z": 1, "a": 2}),
    "metadata_negative": _comp(metadata={"ground_level": -1}),
    "metadata_not_object": _comp(metadata=3),
    "metadata_checked_after_body": _comp(metadata={"bad": 1}, body={"kind": "nope"}),
    "validators_not_list": _comp(validators={}),
    "validators_none": _comp(validators=None),
    "validator_unknown": _comp(validators=[{"kind": None}]),
    "validator_missing_kind": _comp(validators=[{}]),
    "validator_extra": _comp(validators=[{"kind": "door_supported_on_both_sides", "assembly": "d", "x": 1}]),
    "validator_empty_assembly": _comp(validators=[{"kind": "door_supported_on_both_sides", "assembly": ""}]),
    "min_size_zero": _comp(min_size=[1, 0, 1]),
    "min_size_after_body": _comp(min_size="bad", body={"kind": "nope"}),
    "group_children_not_list": {"kind": "group", "children": {}},
    "split_not_lists": {"kind": "split", "axis": "x", "sizes": {}, "children": []},
    "split_empty": {"kind": "split", "axis": "x", "sizes": [], "children": []},
    "split_mismatch": {"kind": "split", "axis": "x", "sizes": [{"kind": "fill"}], "children": [_EMPTY, _EMPTY]},
    "split_bad_axis": {"kind": "split", "axis": "w", "sizes": [{"kind": "fill"}], "children": [_EMPTY]},
    "split_axis_not_str": {"kind": "split", "axis": ["x"], "sizes": [{"kind": "fill"}], "children": [_EMPTY]},
    "size_unknown": {"kind": "split", "axis": "x", "sizes": [{"kind": 3}], "children": [_EMPTY]},
    "size_missing_kind": {"kind": "split", "axis": "x", "sizes": [{}], "children": [_EMPTY]},
    "size_fixed_zero": {"kind": "split", "axis": "x", "sizes": [{"kind": "fixed", "value": 0}], "children": [_EMPTY]},
    "size_fill_extra": {"kind": "split", "axis": "x", "sizes": [{"kind": "fill", "value": 1}], "children": [_EMPTY]},
    "inset_amounts_missing_axis": {"kind": "inset", "amounts": {"x": [0, 0]}, "child": _EMPTY},
    "inset_pair_bad": {"kind": "inset", "amounts": {"x": [0], "y": [0, 0], "z": [0, 0]}, "child": _EMPTY},
    "inset_pair_negative": {"kind": "inset", "amounts": {"x": [0, 0], "y": [0, -2], "z": [0, 0]}, "child": _EMPTY},
    "repeat_count_zero": {"kind": "repeat", "axis": "x", "count": 0, "child_extent": 1, "gap": 0, "child": _EMPTY},
    "repeat_gap_negative": {"kind": "repeat", "axis": "x", "count": 1, "child_extent": 1, "gap": -1, "child": _EMPTY},
    "at_size_none": {"kind": "at", "pos": [0, 0, 0], "rotation": 0, "size": None, "child": _EMPTY},
    "at_no_size": {"kind": "at", "pos": [0, 0, 0], "rotation": 0, "child": _EMPTY},
    "at_uses_child_min_size": {"kind": "at", "pos": [0, 0, 0], "rotation": 90, "child": _comp(min_size=[2, 1, 3])},
    "at_bad_rotation": {"kind": "at", "pos": [0, 0, 0], "rotation": 45, "size": [1, 1, 1], "child": _EMPTY},
    "transform_float_rotation": {"kind": "transform", "translation": [0, 0, 0], "rotation_y": 90.0,
                                 "child_size": [1, 1, 1], "child": _EMPTY},
    "transform_child_size_zero": {"kind": "transform", "translation": [0, 0, 0], "rotation_y": 0,
                                  "child_size": [0, 1, 1], "child": _EMPTY},
    "point_short": {"kind": "place_block", "pos": [0, 0], "block": _STONE},
    "point_float": {"kind": "place_block", "pos": [0, 0.5, 0], "block": _STONE},
    "phase_bad": {"kind": "place_block", "pos": "bad", "block": _STONE, "phase": "carve"},
    "phase_none": {"kind": "place_block", "pos": [0, 0, 0], "block": _STONE, "phase": None},
    "block_state_not_str": {"kind": "place_block", "pos": [0, 0, 0],
                            "block": {"block_type": "minecraft:stone", "block_state": {"a": 1}}},
    "block_state_none": {"kind": "place_block", "pos": [0, 0, 0],
                         "block": {"block_type": "minecraft:stone", "block_state": None}},
    "block_nbt_nan": {"kind": "place_block", "pos": [0, 0, 0],
                      "block": {"block_type": "minecraft:chest", "nbt": {"x": [1.0, float("nan")]}}},
    "box_missing_max": {"kind": "carve_region", "box": {"min": [0, 0, 0]}},
    "box_inverted": {"kind": "fill_region", "box": {"min": [2, 0, 0], "max": [1, 1, 1]}, "block": _STONE},
    "entity_bad_type": {"kind": "place_entity", "pos": [0, 0, 0], "entity": {"entity_type": "Pig"}},
    "entity_nbt_not_object": {"kind": "place_entity", "pos": [0, 0, 0],
                              "entity": {"entity_type": "minecraft:pig", "nbt": [1]}},
    "entity_reserved": {"kind": "place_entity", "pos": [0, 0, 0],
                        "entity": {"entity_type": "minecraft:pig", "nbt": {"id": 1, "Pos": 2}}},
    "entity_yaw_none": {"kind": "place_entity", "pos": [0, 0, 0],
                        "entity": {"entity_type": "minecraft:pig", "yaw": None}},
    "entity_yaw_bool": {"kind": "place_entity", "pos": [0, 0, 0],
                        "entity": {"entity_type": "minecraft:pig", "yaw": True}},
    "entity_pitch_range": {"kind": "place_entity", "pos": [0, 0, 0],
                           "entity": {"entity_type": "minecraft:pig", "pitch": -90.5}},
    "entity_ok_int_yaw": {"kind": "place_entity", "pos": [0, 0, 0],
                          "entity": {"entity_type": "minecraft:pig", "nbt": None, "yaw": 45, "pitch": 0}},
    "assembly_empty_name": {"kind": "place_assembly", "pos": [0, 0, 0], "name": "", "size": [1, 1, 1], "blocks": []},
    "assembly_no_blocks": {"kind": "place_assembly", "pos": [0, 0, 0], "name": "d", "size": [1, 1, 1], "blocks": []},
    "assembly_item_extra": {"kind": "place_assembly", "pos": [0, 0, 0], "name": "d", "size": [1, 1, 1],
                            "blocks": [{"pos": [0, 0, 0], "block": _STONE, "x": 1}]},
    "assembly_pos_after_blocks": {"kind": "place_assembly", "pos": "bad", "name": "d", "size": [1, 1, 1],
                                  "blocks": [{"pos": [0, 0], "block": _STONE}]},
}


@pytest.mark.parametrize("name", sorted(HANDWRITTEN))
def test_handwritten_cases_agree(name):
    tree = HANDWRITTEN[name]
    assert _rust(tree, "case.star") == _python(tree, "case.star")


def _library_scripts():
    library = ROOT.parents[1] / "minecraft-mcp-api" / "starlark-library"
    return sorted(library.glob("*/v*.star")) if library.is_dir() else []


@pytest.mark.parametrize("script", _library_scripts(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_library_scripts_parse_identically(script):
    """Saved minecraft-mcp-api scripts, loaded the way its runner.py loads them."""
    original = starlark_runtime.parse_node
    starlark_runtime.parse_node = lambda value, source_file=None: value
    try:
        tree = starlark_runtime.evaluate_source(
            script.read_text(encoding="utf-8"), str(script), "build", {},
            base_dir=ROOT / "scripts", loader_root=ROOT, mounts={"library": script.parents[1]})
    finally:
        starlark_runtime.parse_node = original
    assert _rust(tree, str(script)) == _python(tree, str(script))
