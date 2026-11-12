"""Rust layout + lowering (crates/stnbt-core) vs Python layout.py/lowering.py.

For every corpus case, both implementations must produce identical
resolved trees, operations (including every write and its block),
entities, and validator placements, compared as sorted-key JSON. Seeded
integer nudges of layout-heavy trees must agree too, on the output or on
the full diagnostic (code, path, message, region, coordinates, details).
"""
from __future__ import annotations

import copy
import json
import random

import pytest

from _corpus import case_names, diagnostics_dicts, load_case
from starlark_to_nbt import _core
from starlark_to_nbt.layout import resolve, resolved_to_dict
from starlark_to_nbt.lowering import entities_to_dict, lower_all, operations_to_dict
from starlark_to_nbt.model import BuildError, Box, Point
from starlark_to_nbt.pipeline import _root_size
from starlark_to_nbt.schema import parse_node

pytestmark = pytest.mark.parity



def _python(tree, root_size, source_file):
    try:
        resolved = resolve(parse_node(tree, source_file=source_file), Box.from_size(Point(*root_size)))
        lowered = lower_all(resolved)
    except BuildError as exc:
        return "error", json.dumps(diagnostics_dicts(exc), sort_keys=True)
    return "ok", json.dumps({
        "resolved": resolved_to_dict(resolved),
        "operations": operations_to_dict(lowered.operations),
        "entities": entities_to_dict(lowered.entities),
        "validators": [[v.validator.assembly, v.provenance.component_path,
                        v.provenance.assigned_region.to_dict(), v.sequence] for v in lowered.validators],
    }, sort_keys=True)


def _rust(tree, root_size, source_file):
    status, payload = _core.lower_tree(tree, list(root_size), source_file)
    return status, json.dumps(payload, sort_keys=True)


def _root(case) -> list[int]:
    if case.root_size:
        return case.root_size
    return _root_size(parse_node(case.tree, source_file=case.source_file), case.props).to_list()


@pytest.mark.parametrize("name", case_names())
def test_corpus_lowers_identically(name):
    case = load_case(name)
    root = _root(case)
    expected = _python(case.tree, root, case.source_file)
    assert expected[0] == "ok", expected
    assert _rust(case.tree, root, case.source_file) == expected


def _int_slots(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, int) and not isinstance(item, bool):
                yield value, key
            else:
                yield from _int_slots(item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, int) and not isinstance(item, bool):
                yield value, index
            else:
                yield from _int_slots(item)


NUDGE_CASES = ["example/church", "example/keep", "example/procedural_facade", "example/cottage",
               "example/redstone_showcase", "showcase/SingleDoor@90", "showcase/GableRoof@270"]


@pytest.mark.parametrize("name", NUDGE_CASES)
def test_integer_nudges_agree(name):
    case = load_case(name)
    root = _root(case)
    rng = random.Random(name)
    slots = list(_int_slots(case.tree))
    outcomes = {"ok": 0, "error": 0}
    for i in range(80):
        tree = copy.deepcopy(case.tree)
        # Re-find the chosen slot in the copy by walking in the same order.
        index = rng.randrange(len(slots))
        container, key = list(_int_slots(tree))[index]
        container[key] += rng.choice([-3, -2, -1, 1, 2, 3])
        expected = _python(tree, root, case.source_file)
        assert _rust(tree, root, case.source_file) == expected, (name, i)
        outcomes[expected[0]] += 1
    assert outcomes["error"] > 0, outcomes


_STONE = {"block_type": "minecraft:stone"}
_EMPTY = {"kind": "group", "children": []}


def _comp(body, min_size=None, name="C"):
    node = {"kind": "component", "name": name, "props": {}, "body": body}
    if min_size:
        node["min_size"] = min_size
    return node


def _block(pos, block=_STONE):
    return {"kind": "place_block", "pos": pos, "block": block}


def _entity(pos, yaw=0):
    return {"kind": "place_entity", "pos": pos, "entity": {"entity_type": "minecraft:pig", "yaw": yaw}}


def _assembly(blocks, size, pos=(0, 0, 0)):
    return {"kind": "place_assembly", "pos": list(pos), "name": "door", "size": size,
            "blocks": [{"pos": p, "block": {"block_type": "minecraft:oak_door"}} for p in blocks]}


# (tree, root size). Each layout/lowering diagnostic code, plus shape edge cases.
HANDWRITTEN = {
    "component_too_small": (_comp(_EMPTY, min_size=[3, 1, 1]), [2, 1, 1]),
    "inset_collapsed": ({"kind": "inset", "amounts": {"x": [1, 1], "y": [0, 0], "z": [0, 0]}, "child": _EMPTY}, [2, 1, 1]),
    "split_overflow": ({"kind": "split", "axis": "y", "sizes": [{"kind": "fixed", "value": 3}], "children": [_EMPTY]}, [1, 2, 1]),
    "split_underflow": ({"kind": "split", "axis": "z", "sizes": [{"kind": "fixed", "value": 1}], "children": [_EMPTY]}, [1, 1, 2]),
    "split_empty_fill": ({"kind": "split", "axis": "x", "sizes": [{"kind": "fill"}, {"kind": "fixed", "value": 2}],
                          "children": [_EMPTY, _EMPTY]}, [2, 1, 1]),
    "repeat_overflow": ({"kind": "repeat", "axis": "x", "count": 2, "child_extent": 2, "gap": 1, "child": _EMPTY}, [4, 1, 1]),
    "transform_overflow": ({"kind": "transform", "translation": [1, 0, 0], "rotation_y": 270,
                            "child_size": [1, 1, 3], "child": _EMPTY}, [3, 1, 1]),
    "entity_component_overflow": (_comp({"kind": "at", "pos": [0, 0, 0], "rotation": 90, "size": [2, 1, 1],
                                         "child": _comp(_entity([5, 0, 0]), name="Pen")}), [2, 1, 2]),
    "assembly_overflow": (_comp(_assembly([[0, 0, 0]], [1, 2, 1])), [1, 1, 1]),
    "assembly_duplicate": (_comp(_assembly([[0, 0, 0], [0, 0, 0]], [1, 1, 1])), [1, 1, 1]),
    "assembly_invalid": (_comp(_assembly([[0, 1, 0]], [1, 1, 1])), [1, 2, 1]),
    "root_not_component": ({"kind": "group", "children": [_block([0, 0, 0]), {"kind": "carve_region",
                            "box": {"min": [0, 0, 0], "max": [1, 1, 1]}}]}, [1, 1, 1]),
    "rotated_repeat_with_negative_yaw": (_comp({"kind": "repeat", "axis": "x", "count": 3, "child_extent": 2, "gap": 0,
        "child": {"kind": "at", "pos": [0, 0, 0], "rotation": 270, "size": [1, 1, 2],
                  "child": _comp({"kind": "group", "children": [
                      _entity([0, 0, 1], yaw=-45.5),
                      _block([0, 0, 0], {"block_type": "minecraft:oak_fence",
                                         "block_state": {"north": "true", "east": "false"}}),
                  ]}, name="Post")}}), [6, 1, 2]),
}


@pytest.mark.parametrize("name", sorted(HANDWRITTEN))
def test_handwritten_cases_agree(name):
    tree, root = HANDWRITTEN[name]
    expected = _python(tree, root, "case.star")
    assert _rust(tree, root, "case.star") == expected
    if name in {"root_not_component", "rotated_repeat_with_negative_yaw"}:
        assert expected[0] == "ok", expected
    else:
        assert json.loads(expected[1])[0]["code"] == name, expected
