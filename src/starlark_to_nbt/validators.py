"""Opt-in post-execution validators declared by Starlark components."""

from __future__ import annotations

from .execute import SparseVolume
from .ir import BlockOperation, DoorSupportedOnBothSides, BuildMetadata, ValidatorPlacement
from .model import Box, Diagnostic, Point
from .support import is_supporting_block

_AIR_TYPES = frozenset({"minecraft:air", "minecraft:cave_air", "minecraft:void_air"})

_FRONT = {
    "north": Point(0, 0, -1),
    "south": Point(0, 0, 1),
    "east": Point(1, 0, 0),
    "west": Point(-1, 0, 0),
}


def validator_diagnostics(validators: list[ValidatorPlacement], operations: list[BlockOperation],
                          volume: SparseVolume, root_box: Box,
                          metadata: BuildMetadata) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    for placement in sorted(validators, key=lambda item: item.sequence):
        if isinstance(placement.validator, DoorSupportedOnBothSides):
            errors.extend(_validate_doors(placement, operations, volume, root_box, metadata))
    return errors


def _validate_doors(placement: ValidatorPlacement, operations: list[BlockOperation],
                    volume: SparseVolume, root_box: Box,
                    metadata: BuildMetadata) -> list[Diagnostic]:
    validator = placement.validator
    assert isinstance(validator, DoorSupportedOnBothSides)
    targets = [
        operation for operation in operations
        if operation.assembly_name == validator.assembly
        and _is_in_scope(operation.provenance.component_path,
                         placement.provenance.component_path)
    ]
    if not targets:
        return [Diagnostic(
            "validator_no_targets",
            f"door validator found no assembly named {validator.assembly!r} in its component subtree",
            placement.provenance.component_path,
            placement.provenance.source,
            region=placement.provenance.assigned_region,
            details={"validator": "door_supported_on_both_sides", "assembly": validator.assembly},
        )]

    errors: list[Diagnostic] = []
    for operation in targets:
        door = _door_halves(operation)
        if door is None:
            coordinate = operation.writes[0].pos if operation.writes else None
            errors.append(Diagnostic(
                "invalid_validator_target",
                f"assembly {validator.assembly!r} is not a matching two-block door",
                operation.provenance.component_path,
                operation.provenance.source,
                region=operation.provenance.assigned_region,
                coordinates=coordinate,
                details={"validator": "door_supported_on_both_sides",
                         "assembly": validator.assembly},
            ))
            continue
        lower, upper, facing = door
        front = _FRONT[facing]
        left = Point(front.z, 0, -front.x)
        right = Point(-left.x, 0, -left.z)
        for height, anchor in (("lower", lower), ("upper", upper)):
            for side, offset in (("left", left), ("right", right)):
                support = anchor + offset
                if not _has_support(volume, root_box, metadata, support):
                    errors.append(_door_error(
                        "door_not_supported",
                        f"{height} half has no solid {side} jamb at {support.to_list()}",
                        operation, lower, validator.assembly,
                        {"half": height, "side": side, "support": support.to_list()},
                    ))
            for direction, offset in (("front", front), ("back", Point(-front.x, 0, -front.z))):
                clearance = anchor + offset
                if not _is_clear(volume, root_box, metadata, clearance):
                    errors.append(_door_error(
                        "doorway_obstructed",
                        f"{height} half is obstructed at its {direction} cell {clearance.to_list()}",
                        operation, lower, validator.assembly,
                        {"half": height, "direction": direction,
                         "obstruction": clearance.to_list()},
                    ))
    return errors


def _is_in_scope(path: str, scope: str) -> bool:
    return path == scope or path.startswith(f"{scope}/")


def _door_halves(operation: BlockOperation) -> tuple[Point, Point, str] | None:
    if len(operation.writes) != 2:
        return None
    lower_writes = [write for write in operation.writes
                    if write.block.block_state.get("half") == "lower"]
    upper_writes = [write for write in operation.writes
                    if write.block.block_state.get("half") == "upper"]
    if len(lower_writes) != 1 or len(upper_writes) != 1:
        return None
    lower = lower_writes[0]
    upper = upper_writes[0]
    facing = lower.block.block_state.get("facing")
    if (
        not lower.block.block_type.endswith("_door")
        or upper.block.block_type != lower.block.block_type
        or facing not in _FRONT
        or upper.block.block_state.get("facing") != facing
        or upper.pos != lower.pos + Point(0, 1, 0)
    ):
        return None
    return lower.pos, upper.pos, facing


def _has_support(volume: SparseVolume, root_box: Box, metadata: BuildMetadata,
                 point: Point) -> bool:
    voxel = volume.voxels.get(point)
    if voxel is not None:
        return is_supporting_block(voxel.block.block_type)
    if not root_box.contains_point(point):
        return True
    return point.y < metadata.ground_level


def _is_clear(volume: SparseVolume, root_box: Box, metadata: BuildMetadata,
              point: Point) -> bool:
    voxel = volume.voxels.get(point)
    if voxel is not None:
        return voxel.block.block_type in _AIR_TYPES
    if not root_box.contains_point(point):
        return True
    return point.y >= metadata.ground_level


def _door_error(code: str, message: str, operation: BlockOperation, door: Point,
                assembly: str, details: dict[str, object]) -> Diagnostic:
    return Diagnostic(
        code,
        message,
        operation.provenance.component_path,
        operation.provenance.source,
        region=operation.provenance.assigned_region,
        coordinates=door,
        details={"validator": "door_supported_on_both_sides", "assembly": assembly, **details},
    )
