"""Rust execute + support + validators vs Python's `_finish_build`.

Every corpus case must produce the same sparse volume (each voxel's
position, block, owning component, and phase, in y/z/x order), entities,
and metadata. Seeded integer nudges, and hand-written cases for each
execute, support, and validator code, must agree on the full diagnostics
(code, path, message, region, coordinates, details, source).
"""
from __future__ import annotations

import copy
import json
import random

import pytest

from _corpus import case_names, diagnostics_dicts, load_case
from starlark_to_nbt import _core
from starlark_to_nbt.lowering import entities_to_dict
from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import _finish_build, _root_size
from starlark_to_nbt.schema import parse_node

pytestmark = pytest.mark.parity



def _python(tree, root_size, source_file):
    try:
        node = parse_node(tree, source_file=source_file)
        result = _finish_build(node, {}, Point(*root_size))
    except BuildError as exc:
        return "error", json.dumps(diagnostics_dicts(exc), sort_keys=True)
    volume = result.volume
    voxels = [[p.to_list(), volume.voxels[p].block.to_dict(), volume.voxels[p].provenance.component_path,
               volume.voxels[p].phase.name] for p in sorted(volume.voxels, key=lambda p: (p.y, p.z, p.x))]
    return "ok", json.dumps({"voxels": voxels, "entities": entities_to_dict(volume.entities),
                             "metadata": result.metadata.to_dict()}, sort_keys=True)


def _rust(tree, root_size, source_file):
    status, payload = _core.build_tree(tree, list(root_size), source_file)
    return status, json.dumps(payload, sort_keys=True)


def _root(case) -> list[int]:
    if case.root_size:
        return case.root_size
    return _root_size(parse_node(case.tree, source_file=case.source_file), case.props).to_list()


@pytest.mark.parametrize("name", case_names())
def test_corpus_executes_identically(name):
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


# Support-heavy, validator-bearing, and overlap-heavy trees.
NUDGE_CASES = ["example/redstone_showcase", "example/bsp_dungeon", "example/church", "example/cottage",
               "showcase/SingleDoor", "showcase/DoubleDoor@90"]


@pytest.mark.parametrize("name", NUDGE_CASES)
def test_integer_nudges_agree(name):
    case = load_case(name)
    root = _root(case)
    rng = random.Random(name)
    count = len(list(_int_slots(case.tree)))
    codes = set()
    for i in range(60):
        tree = copy.deepcopy(case.tree)
        container, key = list(_int_slots(tree))[rng.randrange(count)]
        container[key] += rng.choice([-2, -1, 1, 2])
        expected = _python(tree, root, case.source_file)
        assert _rust(tree, root, case.source_file) == expected, (name, i)
        if expected[0] == "error":
            codes.update(d["code"] for d in json.loads(expected[1]))
    assert codes, "nudges never produced an error"


_STONE = {"block_type": "minecraft:stone"}


def _comp(body, name="C", **extra):
    return {"kind": "component", "name": name, "props": {}, "body": body, **extra}


def _block(pos, block_type="minecraft:stone", state=None, phase="structure"):
    return {"kind": "place_block", "pos": pos, "phase": phase,
            "block": {"block_type": block_type, "block_state": state or {}}}


def _group(*children):
    return {"kind": "group", "children": list(children)}


def _door(pos, facing="south", hinge="left"):
    states = {"facing": facing, "hinge": hinge, "open": "false", "powered": "false"}
    return {"kind": "place_assembly", "pos": pos, "name": "door", "size": [1, 2, 1], "blocks": [
        {"pos": [0, 0, 0], "block": {"block_type": "minecraft:oak_door", "block_state": {**states, "half": "lower"}}},
        {"pos": [0, 1, 0], "block": {"block_type": "minecraft:oak_door", "block_state": {**states, "half": "upper"}}},
    ]}


_DOOR_VALIDATOR = [{"kind": "door_supported_on_both_sides", "assembly": "door"}]

# (tree, root size). Each execute/support/validator code, plus passing cases.
# entity_root_overflow is unreachable through the pipeline (assigned regions
# always sit inside the root box, and lowering checks those first); a Rust
# unit test in execute.rs covers it.
HANDWRITTEN = {
    "root_overflow": (_comp(_block([2, 0, 0])), [2, 1, 1]),
    "component_overflow": (_comp({"kind": "at", "pos": [0, 0, 0], "rotation": 0, "size": [1, 1, 1],
                                  "child": _comp(_block([1, 0, 0]), name="Inner")}), [2, 1, 1]),
    "block_conflict": (_comp(_group(_block([0, 0, 0]), _block([0, 0, 0], "minecraft:dirt"))), [1, 1, 1]),
    "fixture_conflict": (_comp(_group(_block([0, 0, 0], phase="fixture"), _block([0, 0, 0], phase="fixture"))), [1, 1, 1]),
    "identical_structure_rewrite": (_comp(_group(_block([0, 0, 0]), _block([0, 0, 0]))), [1, 1, 1]),
    "carve_then_fixture": (_comp(_group(_block([0, 0, 0]), {"kind": "carve_region", "box": {"min": [0, 0, 0], "max": [1, 1, 1]}},
                                        _block([0, 0, 0], "minecraft:lantern", phase="fixture"))), [1, 1, 1]),
    "unsupported_block": (_comp(_group(_block([0, 1, 0], "minecraft:redstone_wire", phase="fixture"),
                                       _block([1, 1, 0], "minecraft:lever", {"face": "wall", "facing": "east"}, phase="fixture"),
                                       _block([1, 0, 0], "minecraft:oak_slab"),
                                       _block([1, 2, 0], "minecraft:stone_button", {"face": "ceiling", "facing": "north"}))),
                          [2, 3, 1]),
    "supported_on_terrain": (_comp(_block([0, 1, 0], "minecraft:redstone_wire"), metadata={"ground_level": 1}), [1, 2, 1]),
    "validator_no_targets": (_comp(_group(_block([0, 0, 0])), validators=_DOOR_VALIDATOR, source={"file": "v.star", "line": 3}), [1, 1, 1]),
    "invalid_validator_target": (_comp({"kind": "place_assembly", "pos": [0, 0, 0], "name": "door", "size": [1, 1, 1],
                                        "blocks": [{"pos": [0, 0, 0], "block": _STONE}]}, validators=_DOOR_VALIDATOR), [1, 1, 1]),
    "door_not_supported": (_comp(_door([1, 0, 1]), validators=_DOOR_VALIDATOR), [3, 2, 3]),
    "doorway_obstructed": (_comp(_group(_door([1, 0, 1], facing="east"), _block([0, 1, 0]), _block([0, 0, 0]),
                                        _block([1, 0, 0]), _block([1, 1, 0]), _block([1, 0, 2]), _block([1, 1, 2]),
                                        _block([2, 0, 1])), validators=_DOOR_VALIDATOR), [3, 2, 3]),
}


@pytest.mark.parametrize("name", sorted(HANDWRITTEN))
def test_handwritten_cases_agree(name):
    tree, root = HANDWRITTEN[name]
    expected = _python(tree, root, "case.star")
    assert _rust(tree, root, "case.star") == expected
    passing = {"identical_structure_rewrite", "carve_then_fixture", "supported_on_terrain"}
    if name in passing:
        assert expected[0] == "ok", expected
    else:
        code = "block_conflict" if name == "fixture_conflict" else name
        assert code in {d["code"] for d in json.loads(expected[1])}, expected
