from __future__ import annotations

from starlark_to_nbt.model import BlockSpec, Point, Transform


def _rotate(block: BlockSpec, rotation: int, size: Point = Point(3, 1, 3)) -> BlockSpec:
    return block.transformed(Transform(Point(0, 0, 0), rotation, size))


def test_axis_swaps_on_quarter_turns_only():
    log = BlockSpec("minecraft:oak_log", {"axis": "x"})
    assert _rotate(log, 90).block_state["axis"] == "z"
    assert _rotate(log, 180).block_state["axis"] == "x"
    assert _rotate(log, 270).block_state["axis"] == "z"
    vertical = BlockSpec("minecraft:oak_log", {"axis": "y"})
    assert _rotate(vertical, 90).block_state["axis"] == "y"


def test_sixteenth_rotation_advances_by_four_per_quarter_turn():
    sign = BlockSpec("minecraft:oak_sign", {"rotation": "1"})
    assert _rotate(sign, 90).block_state["rotation"] == "5"
    assert _rotate(sign, 180).block_state["rotation"] == "9"
    assert _rotate(sign, 270).block_state["rotation"] == "13"
    assert _rotate(BlockSpec("minecraft:oak_sign", {"rotation": "14"}), 90).block_state["rotation"] == "2"


def test_multi_face_connection_keys_rotate_with_block():
    pane = BlockSpec("minecraft:glass_pane", {"east": "true", "west": "true", "waterlogged": "false"})
    rotated = _rotate(pane, 90)
    assert rotated.block_state == {"north": "true", "south": "true", "waterlogged": "false"}
    corner_fence = BlockSpec("minecraft:oak_fence", {"east": "true", "south": "true"})
    assert _rotate(corner_fence, 90).block_state == {"south": "true", "west": "true"}


def test_four_quarter_turns_return_all_state_families_to_identity():
    block = BlockSpec("minecraft:oak_stairs", {
        "facing": "south", "axis": "x", "rotation": "3", "north": "true", "east": "false",
    })
    size = Point(3, 1, 3)
    rotated = block
    for _ in range(4):
        rotated = rotated.transformed(Transform(Point(0, 0, 0), 90, size))
    assert rotated == block


def test_relative_states_are_untouched_by_rotation():
    stair = BlockSpec("minecraft:oak_stairs", {"facing": "east", "shape": "inner_left", "half": "top"})
    rotated = _rotate(stair, 90)
    assert rotated.block_state["shape"] == "inner_left"
    assert rotated.block_state["half"] == "top"
    assert rotated.block_state["facing"] == "south"


def test_block_nbt_is_preserved_unchanged_through_rotation():
    text = {"front_text": {"messages": ["hi", "", "", ""], "has_glowing_text": True}}
    sign = BlockSpec("minecraft:oak_sign", {"rotation": "0"}, text)
    rotated = _rotate(sign, 90)
    assert rotated.block_state["rotation"] == "4"
    assert rotated.block_nbt == text
