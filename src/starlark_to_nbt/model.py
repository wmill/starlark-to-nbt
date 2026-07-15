from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class Axis(str, Enum):
    X = "x"
    Y = "y"
    Z = "z"


@dataclass(frozen=True, slots=True, order=True)
class Point:
    x: int
    y: int
    z: int

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def component(self, axis: Axis) -> int:
        return getattr(self, axis.value)

    def replace(self, axis: Axis, value: int) -> Point:
        values = {"x": self.x, "y": self.y, "z": self.z}
        values[axis.value] = value
        return Point(**values)

    def to_list(self) -> list[int]:
        return [self.x, self.y, self.z]


@dataclass(frozen=True, slots=True)
class Box:
    min: Point
    max: Point

    def __post_init__(self) -> None:
        if any(a >= b for a, b in zip(self.min.to_list(), self.max.to_list())):
            raise ValueError(f"box must have positive extents: {self}")

    @classmethod
    def from_size(cls, size: Point, origin: Point = Point(0, 0, 0)) -> Box:
        return cls(origin, origin + size)

    @property
    def size(self) -> Point:
        return self.max - self.min

    def extent(self, axis: Axis) -> int:
        return self.max.component(axis) - self.min.component(axis)

    def contains_point(self, point: Point) -> bool:
        return all(a <= p < b for a, p, b in zip(self.min.to_list(), point.to_list(), self.max.to_list()))

    def contains_box(self, other: Box) -> bool:
        return all(a <= c and d <= b for a, b, c, d in zip(
            self.min.to_list(), self.max.to_list(), other.min.to_list(), other.max.to_list()
        ))

    def translated(self, offset: Point) -> Box:
        return Box(self.min + offset, self.max + offset)

    def to_dict(self) -> dict[str, list[int]]:
        return {"min": self.min.to_list(), "max": self.max.to_list()}


FACING_ORDER = ("south", "west", "north", "east")


@dataclass(frozen=True, slots=True)
class Transform:
    """A normalized quarter-turn followed by translation."""

    translation: Point = Point(0, 0, 0)
    rotation_y: int = 0
    source_size: Point | None = None

    def __post_init__(self) -> None:
        if self.rotation_y not in (0, 90, 180, 270):
            raise ValueError("rotation_y must be 0, 90, 180, or 270")

    @property
    def footprint_size(self) -> Point | None:
        if self.source_size is None:
            return None
        if self.rotation_y in (90, 270):
            return Point(self.source_size.z, self.source_size.y, self.source_size.x)
        return self.source_size

    def apply_point(self, point: Point) -> Point:
        if self.source_size is None:
            raise ValueError("normalized rotation requires source_size")
        w, d = self.source_size.x, self.source_size.z
        if self.rotation_y == 0:
            rotated = point
        elif self.rotation_y == 90:
            rotated = Point(d - 1 - point.z, point.y, point.x)
        elif self.rotation_y == 180:
            rotated = Point(w - 1 - point.x, point.y, d - 1 - point.z)
        else:
            rotated = Point(point.z, point.y, w - 1 - point.x)
        return rotated + self.translation

    def rotate_facing(self, facing: str) -> str:
        if facing not in FACING_ORDER:
            return facing
        return FACING_ORDER[(FACING_ORDER.index(facing) + self.rotation_y // 90) % 4]


@dataclass(frozen=True, slots=True)
class BlockSpec:
    block_type: str
    block_state: dict[str, str] = field(default_factory=dict)

    def transformed(self, transform: Transform) -> BlockSpec:
        state = dict(self.block_state)
        if "facing" in state:
            state["facing"] = transform.rotate_facing(state["facing"])
        return BlockSpec(self.block_type, state)

    def key(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        return self.block_type, tuple(sorted(self.block_state.items()))

    def to_dict(self) -> dict[str, Any]:
        return {"blockType": self.block_type, "blockState": dict(sorted(self.block_state.items()))}


AIR = BlockSpec("minecraft:air")


@dataclass(frozen=True, slots=True)
class SourceRef:
    file: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True, slots=True)
class Provenance:
    component_path: str
    assigned_region: Box
    source: SourceRef | None = None


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    component_path: str = "<root>"
    source: SourceRef | None = None
    region: Box | None = None
    coordinates: Point | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        location = self.component_path
        if self.source:
            location += f" ({self.source.file}"
            if self.source.line is not None:
                location += f":{self.source.line}"
            location += ")"
        return f"{self.code}: {location}: {self.message}"


class BuildError(Exception):
    def __init__(self, diagnostics: Diagnostic | Iterable[Diagnostic]):
        if isinstance(diagnostics, Diagnostic):
            diagnostics = (diagnostics,)
        self.diagnostics = tuple(diagnostics)
        super().__init__("\n".join(map(str, self.diagnostics)))


def fail(code: str, message: str, path: str = "<root>", **kwargs: Any) -> BuildError:
    return BuildError(Diagnostic(code, message, path, **kwargs))
