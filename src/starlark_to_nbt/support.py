"""Post-execute validation of redstone attachment/support rules.

Minecraft removes attachable redstone blocks (dust, repeaters, comparators,
torches, levers, buttons, pressure plates) the moment they receive a block
update without a valid supporting block, so a structure that places them over
air is silently broken in-game. This pass walks the final world-space voxels
and raises ``unsupported_block`` diagnostics for any redstone attachable whose
support cell cannot hold it.

Scope is deliberately limited to redstone blocks: decorative attachables
(lanterns, ladders, banners, carpets, flowers, ...) have their own rules and
are not checked. The solidity test is a conservative approximation — a support
cell counts as solid unless its block type is a known non-supporting block.

Support-cell semantics for the sparse output format:
  - written with a supporting block -> ok
  - written with a non-supporting block (including carved air) -> error
  - unwritten and outside the root box -> unknown terrain, assumed ok (this is
    what lets a bare one-block part build standalone)
  - unwritten, inside the root box, below ``metadata.ground_level`` -> buried
    in terrain on paste, ok
  - unwritten, inside the root box, at or above ground level -> air on paste,
    error
"""

from __future__ import annotations

from .execute import SparseVolume, Voxel
from .ir import BuildMetadata
from .model import BlockSpec, Box, BuildError, Diagnostic, Point

_DOWN = Point(0, -1, 0)
_UP = Point(0, 1, 0)

# Offset from an attachable to its supporting block, opposite its `facing`
# (wall torches, wall levers/buttons face away from the block they hang on).
_BEHIND = {
    "south": Point(0, 0, -1),
    "north": Point(0, 0, 1),
    "east": Point(-1, 0, 0),
    "west": Point(1, 0, 0),
}

_NEEDS_BELOW = frozenset({
    "minecraft:redstone_wire",
    "minecraft:repeater",
    "minecraft:comparator",
    "minecraft:redstone_torch",
})

_FACE_ATTACHED = frozenset({"minecraft:lever"})

# Block types that cannot hold an attachable, by exact id.
_NON_SUPPORTING_TYPES = frozenset({
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:water",
    "minecraft:lava",
    "minecraft:torch",
    "minecraft:wall_torch",
    "minecraft:redstone_wire",
    "minecraft:repeater",
    "minecraft:comparator",
    "minecraft:lever",
    "minecraft:hopper",
    "minecraft:piston",
    "minecraft:sticky_piston",
    "minecraft:piston_head",
    "minecraft:moving_piston",
    "minecraft:rail",
    "minecraft:ladder",
    "minecraft:lantern",
    "minecraft:soul_lantern",
    "minecraft:chain",
})

# ... and by suffix (covers dyed/wood/material variants in one rule).
_NON_SUPPORTING_SUFFIXES = (
    "_torch",
    "_pressure_plate",
    "_button",
    "_sign",
    "_banner",
    "_pane",
    "_fence",
    "_fence_gate",
    "_carpet",
    "_door",
    "_trapdoor",
    "_slab",
    "_stairs",
    "_wall",
    "_rail",
    "_bed",
)


def is_supporting_block(block_type: str) -> bool:
    if block_type in _NON_SUPPORTING_TYPES:
        return False
    return not block_type.endswith(_NON_SUPPORTING_SUFFIXES)


def _can_support(support_type: str, attachable_type: str) -> bool:
    if attachable_type.endswith("_pressure_plate") and (
        support_type.endswith(("_fence", "_wall")) or support_type == "minecraft:hopper"
    ):
        # Pressure plates are special-cased in vanilla: they may sit on fence
        # posts, walls, and hoppers (tables, hopper timers).
        return True
    return is_supporting_block(support_type)


def _support_offset(block: BlockSpec) -> Point | None:
    """Offset from the block to its required support cell, or None."""
    block_type = block.block_type
    if block_type in _NEEDS_BELOW or block_type.endswith("_pressure_plate"):
        return _DOWN
    if block_type == "minecraft:redstone_wall_torch":
        return _BEHIND.get(block.block_state.get("facing", "north"))
    if block_type in _FACE_ATTACHED or block_type.endswith("_button"):
        face = block.block_state.get("face", "wall")
        if face == "floor":
            return _DOWN
        if face == "ceiling":
            return _UP
        return _BEHIND.get(block.block_state.get("facing", "north"))
    return None


def validate_support(volume: SparseVolume, root_box: Box, metadata: BuildMetadata) -> None:
    errors = support_diagnostics(volume, root_box, metadata)
    if errors:
        raise BuildError(errors)


def support_diagnostics(volume: SparseVolume, root_box: Box,
                        metadata: BuildMetadata) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    for pos in sorted(volume.voxels, key=lambda p: (p.y, p.z, p.x)):
        voxel = volume.voxels[pos]
        offset = _support_offset(voxel.block)
        if offset is None:
            continue
        support = pos + offset
        diagnostic = _check_support(volume, root_box, metadata, pos, voxel, support)
        if diagnostic is not None:
            errors.append(diagnostic)
    return errors


def _check_support(volume: SparseVolume, root_box: Box, metadata: BuildMetadata,
                   pos: Point, voxel: Voxel, support: Point) -> Diagnostic | None:
    existing = volume.voxels.get(support)
    if existing is not None:
        if _can_support(existing.block.block_type, voxel.block.block_type):
            return None
        reason = f"it rests on {existing.block.block_type}, which cannot hold it"
    else:
        if not root_box.contains_point(support):
            return None  # outside the structure: unknown terrain
        if support.y < metadata.ground_level:
            return None  # buried in terrain when pasted at ground level
        reason = "the cell there is unwritten and will be air when pasted"
    return Diagnostic(
        "unsupported_block",
        f"{voxel.block.block_type} at {pos.to_list()} needs a solid block at "
        f"{support.to_list()}, but {reason}; place a supporting block "
        f"(e.g. the part's base prop) or move the component",
        voxel.provenance.component_path,
        region=voxel.provenance.assigned_region,
        coordinates=pos,
        details={"support": support.to_list()},
    )
