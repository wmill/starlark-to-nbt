from __future__ import annotations

from itertools import product

from .ir import (
    BlockOperation, BlockWrite, CarveRegion, Component, FillRegion, Group, Phase,
    PlaceAssembly, PlaceBlock, ResolvedNode,
)
from .model import AIR, Box, BuildError, Diagnostic, Point, Provenance, Transform


def _apply(point: Point, transforms: tuple[Transform, ...]) -> Point:
    for transform in reversed(transforms):
        point = transform.apply_point(point)
    return point


def _world_point(local: Point, node: ResolvedNode) -> Point:
    return _apply(node.region.min + local, node.world_transforms)


def _world_block(block, transforms: tuple[Transform, ...]):
    for transform in reversed(transforms):
        block = block.transformed(transform)
    return block


def _world_box(box: Box, transforms: tuple[Transform, ...]) -> Box:
    corners = [
        _apply(Point(x, y, z), transforms)
        for x, y, z in product(
            (box.min.x, box.max.x - 1), (box.min.y, box.max.y - 1), (box.min.z, box.max.z - 1)
        )
    ]
    return Box(
        Point(min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)),
        Point(max(p.x for p in corners) + 1, max(p.y for p in corners) + 1, max(p.z for p in corners) + 1),
    )


def lower(root: ResolvedNode) -> list[BlockOperation]:
    operations: list[BlockOperation] = []
    _lower(root, operations, None)
    return [BlockOperation(op.phase, op.kind, op.writes, op.provenance, op.assembly_name, i)
            for i, op in enumerate(operations)]


def _lower(node: ResolvedNode, operations: list[BlockOperation], owner: ResolvedNode | None) -> None:
    if isinstance(node.node, Component):
        owner = node
    for child in node.children:
        _lower(child, operations, owner)
    if node.children:
        return

    leaf = node.node
    if isinstance(leaf, Group):  # childless group: nothing to emit
        return
    owner = owner or node
    owner_region = _world_box(owner.region, owner.world_transforms)
    provenance = Provenance(owner.path, owner_region, owner.node.source if isinstance(owner.node, Component) else None)

    if isinstance(leaf, PlaceBlock):
        phase = Phase.STRUCTURE if leaf.phase == "structure" else Phase.FIXTURE
        operations.append(BlockOperation(phase, "place_block", (
            BlockWrite(_world_point(leaf.pos, node), _world_block(leaf.block, node.world_transforms)),
        ), provenance))
    elif isinstance(leaf, FillRegion):
        writes = tuple(
            BlockWrite(_world_point(Point(x, y, z), node), _world_block(leaf.block, node.world_transforms))
            for y in range(leaf.box.min.y, leaf.box.max.y)
            for z in range(leaf.box.min.z, leaf.box.max.z)
            for x in range(leaf.box.min.x, leaf.box.max.x)
        )
        phase = Phase.STRUCTURE if leaf.phase == "structure" else Phase.FIXTURE
        operations.append(BlockOperation(phase, "fill_region", writes, provenance))
    elif isinstance(leaf, CarveRegion):
        writes = tuple(
            BlockWrite(_world_point(Point(x, y, z), node), AIR)
            for y in range(leaf.box.min.y, leaf.box.max.y)
            for z in range(leaf.box.min.z, leaf.box.max.z)
            for x in range(leaf.box.min.x, leaf.box.max.x)
        )
        operations.append(BlockOperation(Phase.CARVE, "carve_region", writes, provenance))
    elif isinstance(leaf, PlaceAssembly):
        assembly_bounds = Box.from_size(leaf.size)
        placed_bounds = _world_box(assembly_bounds.translated(node.region.min + leaf.pos), node.world_transforms)
        if not owner_region.contains_box(placed_bounds):
            raise BuildError(Diagnostic(
                "assembly_overflow", f"assembly {leaf.name} bounds are outside the assigned region",
                owner.path, region=owner_region, details={"assemblyRegion": placed_bounds.to_dict()},
            ))
        seen: set[Point] = set()
        writes: list[BlockWrite] = []
        for item in leaf.blocks:
            if item.pos in seen:
                raise BuildError(Diagnostic("assembly_duplicate", f"assembly {leaf.name} contains duplicate offset {item.pos.to_list()}", owner.path))
            seen.add(item.pos)
            if not assembly_bounds.contains_point(item.pos):
                raise BuildError(Diagnostic("assembly_invalid", f"assembly block {item.pos.to_list()} is outside declared size", owner.path))
            writes.append(BlockWrite(_world_point(leaf.pos + item.pos, node), _world_block(item.block, node.world_transforms)))
        operations.append(BlockOperation(Phase.FIXTURE, "place_assembly", tuple(writes), provenance, leaf.name))


def operations_to_dict(operations: list[BlockOperation]) -> list[dict]:
    return [
        {
            "phase": op.phase.name,
            "kind": op.kind,
            "sequence": op.sequence,
            "componentPath": op.provenance.component_path,
            "assignedRegion": op.provenance.assigned_region.to_dict(),
            "assembly": op.assembly_name,
            "writes": [{"pos": write.pos.to_list(), "block": write.block.to_dict()} for write in op.writes],
        }
        for op in operations
    ]
