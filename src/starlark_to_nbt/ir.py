"""Result types: what a finished build exposes to Python (see pipeline.BuildResult)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from .model import BlockSpec, Point, Provenance


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    ground_level: int = 0
    # Ticks between install stages, if the script's metadata set it.
    stage_delay_ticks: int | None = None

    @property
    def y_offset(self) -> int:
        return -self.ground_level

    def to_dict(self) -> dict[str, int]:
        out = {"ground_level": self.ground_level, "y_offset": self.y_offset}
        if self.stage_delay_ticks is not None:
            out["stage_delay_ticks"] = self.stage_delay_ticks
        return out


# Ticks between install stages when a staged script doesn't set them.
DEFAULT_STAGE_DELAY_TICKS = 2


@dataclass(frozen=True, slots=True)
class Stage:
    """One install stage of a staged build (see `stage=` on the placement
    constructors): the cells it writes, placed after every lower stage."""
    stage: int
    block_count: int


class Phase(IntEnum):
    STRUCTURE = 0
    CARVE = 1
    FIXTURE = 2


@dataclass(frozen=True, slots=True)
class BlockWrite:
    pos: Point
    block: BlockSpec


@dataclass(frozen=True, slots=True)
class BlockOperation:
    phase: Phase
    kind: str
    writes: tuple[BlockWrite, ...]
    provenance: Provenance
    assembly_name: str | None = None
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class EntitySpec:
    entity_type: str
    nbt: dict[str, Any] | None = None
    yaw: float = 0.0
    pitch: float = 0.0


@dataclass(frozen=True, slots=True)
class EntityPlacement:
    pos: Point
    entity: EntitySpec
    provenance: Provenance
    sequence: int = 0


@dataclass(frozen=True, slots=True)
class Voxel:
    block: BlockSpec
    provenance: Provenance
    phase: Phase
