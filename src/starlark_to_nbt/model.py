"""Public value and error types for build results.

The pipeline itself is Rust (crates/stnbt-core); these are the Python
shapes its results and diagnostics take. Coordinates: +X east, +Y up,
+Z south. Boxes are half-open (min inclusive, max exclusive).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True, order=True)
class Point:
    x: int
    y: int
    z: int

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

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

    def contains_point(self, point: Point) -> bool:
        return all(a <= p < b for a, p, b in zip(self.min.to_list(), point.to_list(), self.max.to_list()))

    def contains_box(self, other: Box) -> bool:
        return all(a <= c and d <= b for a, b, c, d in zip(
            self.min.to_list(), self.max.to_list(), other.min.to_list(), other.max.to_list()
        ))

    def to_dict(self) -> dict[str, list[int]]:
        return {"min": self.min.to_list(), "max": self.max.to_list()}


@dataclass(frozen=True, slots=True)
class BlockSpec:
    block_type: str
    block_state: dict[str, str] = field(default_factory=dict)
    # Block-entity data (e.g. sign text), serialized per block instance, never
    # in the palette (which is only Name+Properties).
    block_nbt: dict[str, Any] | None = None


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
