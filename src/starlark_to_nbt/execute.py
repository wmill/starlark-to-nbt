from __future__ import annotations

from dataclasses import dataclass, field

from .ir import BlockOperation, EntityPlacement, Phase
from .model import AIR, BlockSpec, Box, BuildError, Diagnostic, Point, Provenance


@dataclass(frozen=True, slots=True)
class Voxel:
    block: BlockSpec
    provenance: Provenance
    phase: Phase


@dataclass(slots=True)
class SparseVolume:
    bounds: Box
    voxels: dict[Point, Voxel]
    entities: list[EntityPlacement] = field(default_factory=list)

    def block_at(self, point: Point) -> BlockSpec:
        voxel = self.voxels.get(point)
        return voxel.block if voxel else AIR


def execute(operations: list[BlockOperation], root_box: Box,
            entities: list[EntityPlacement] | None = None) -> SparseVolume:
    entities = list(entities or [])
    for item in entities:
        if not root_box.contains_point(item.pos):
            raise BuildError(Diagnostic("entity_root_overflow", "entity anchor is outside root bounds",
                                        item.provenance.component_path, region=root_box, coordinates=item.pos))
    volume = SparseVolume(root_box, {}, entities)
    for operation in sorted(operations, key=lambda op: (op.phase, op.sequence)):
        _execute_operation(volume, operation)
    return volume


def _execute_operation(volume: SparseVolume, operation: BlockOperation) -> None:
    seen: set[Point] = set()
    errors: list[Diagnostic] = []
    for write in operation.writes:
        if write.pos in seen:
            errors.append(Diagnostic("operation_duplicate", "operation writes the same cell more than once",
                                     operation.provenance.component_path, coordinates=write.pos))
            continue
        seen.add(write.pos)
        if not volume.bounds.contains_point(write.pos):
            errors.append(Diagnostic("root_overflow", "block is outside root bounds", operation.provenance.component_path,
                                     region=volume.bounds, coordinates=write.pos))
            continue
        if not operation.provenance.assigned_region.contains_point(write.pos):
            errors.append(Diagnostic("component_overflow", "block is outside its component's assigned region",
                                     operation.provenance.component_path, region=operation.provenance.assigned_region,
                                     coordinates=write.pos))
            continue
        existing = volume.voxels.get(write.pos)
        if operation.phase == Phase.STRUCTURE and existing and existing.block != AIR:
            # Identical rewrites are harmless: structural fills naturally share
            # corners and edges. Only differing blocks are a conflict.
            if existing.block != write.block:
                errors.append(_collision(operation, write.pos, existing))
        elif operation.phase == Phase.FIXTURE and existing and existing.block != AIR:
            errors.append(_collision(operation, write.pos, existing))
    if errors:
        raise BuildError(errors)

    for write in operation.writes:
        volume.voxels[write.pos] = Voxel(write.block, operation.provenance, operation.phase)


def _collision(operation: BlockOperation, point: Point, existing: Voxel) -> Diagnostic:
    return Diagnostic(
        "block_conflict",
        f"cannot overwrite {existing.block.block_type} from {existing.provenance.component_path}",
        operation.provenance.component_path,
        coordinates=point,
        details={"existingComponent": existing.provenance.component_path},
    )


def dense_to_dict(volume: SparseVolume) -> dict:
    bounds = volume.bounds
    blocks = []
    for y in range(bounds.min.y, bounds.max.y):
        y_layer = []
        for z in range(bounds.min.z, bounds.max.z):
            y_layer.append([volume.block_at(Point(x, y, z)).to_dict() for x in range(bounds.min.x, bounds.max.x)])
        blocks.append(y_layer)
    return {"origin": bounds.min.to_list(), "size": bounds.size.to_list(), "order": "y,z,x", "blocks": blocks}
