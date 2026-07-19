from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any, TypeAlias

from .model import Axis, BlockSpec, Box, Point, Provenance, SourceRef, Transform


@dataclass(frozen=True, slots=True)
class Fixed:
    value: int


@dataclass(frozen=True, slots=True)
class Fill:
    pass


SizeExpr: TypeAlias = Fixed | Fill


@dataclass(frozen=True, slots=True)
class BuildMetadata:
    ground_level: int = 0

    @property
    def y_offset(self) -> int:
        return -self.ground_level

    def to_dict(self) -> dict[str, int]:
        return {"ground_level": self.ground_level, "y_offset": self.y_offset}


@dataclass(frozen=True, slots=True)
class Component:
    name: str
    props: dict[str, Any]
    body: Node
    min_size: Point | None = None
    source: SourceRef | None = None
    metadata: BuildMetadata | None = None


@dataclass(frozen=True, slots=True)
class Group:
    children: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Split:
    axis: Axis
    sizes: tuple[SizeExpr, ...]
    children: tuple[Node, ...]


@dataclass(frozen=True, slots=True)
class Inset:
    amounts: dict[Axis, tuple[int, int]]
    child: Node


@dataclass(frozen=True, slots=True)
class Repeat:
    axis: Axis
    count: int
    child_extent: int
    gap: int
    child: Node


@dataclass(frozen=True, slots=True)
class TransformNode:
    translation: Point
    rotation_y: int
    child_size: Point
    child: Node


@dataclass(frozen=True, slots=True)
class PlaceBlock:
    pos: Point
    block: BlockSpec
    phase: str


@dataclass(frozen=True, slots=True)
class FillRegion:
    box: Box
    block: BlockSpec
    phase: str = "structure"


@dataclass(frozen=True, slots=True)
class CarveRegion:
    box: Box


@dataclass(frozen=True, slots=True)
class AssemblyBlock:
    pos: Point
    block: BlockSpec


@dataclass(frozen=True, slots=True)
class PlaceAssembly:
    pos: Point
    name: str
    size: Point
    blocks: tuple[AssemblyBlock, ...]


Node: TypeAlias = Component | Group | Split | Inset | Repeat | TransformNode | PlaceBlock | FillRegion | CarveRegion | PlaceAssembly


@dataclass(frozen=True, slots=True)
class ResolvedNode:
    node: Node
    region: Box
    path: str
    world_transforms: tuple[Transform, ...] = ()
    children: tuple[ResolvedNode, ...] = ()


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
