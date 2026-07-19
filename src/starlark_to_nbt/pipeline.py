from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .execute import SparseVolume, dense_to_dict, execute
from .ir import BlockOperation, BuildMetadata, Component, EntityPlacement, Node, ResolvedNode
from .layout import resolve, resolved_to_dict
from .lowering import entities_to_dict, lower_all, operations_to_dict
from .model import Box, Point
from .serialize import write_json, write_structure_nbt
from .starlark_runtime import evaluate_file


@dataclass(slots=True)
class BuildResult:
    component_ir: Node
    resolved: ResolvedNode
    operations: list[BlockOperation]
    entities: list[EntityPlacement]
    volume: SparseVolume
    metadata: BuildMetadata


def build_file(path: str | Path, entry: str = "build", props: dict[str, Any] | None = None,
               root_size: Point | None = None) -> BuildResult:
    props = props or {}
    component_ir = evaluate_file(path, entry, props)
    if root_size is None:
        root_size = _root_size(component_ir, props)
    root_box = Box.from_size(root_size)
    resolved = resolve(component_ir, root_box)
    lowered = lower_all(resolved)
    operations = lowered.operations
    volume = execute(operations, root_box, lowered.entities)
    metadata = (
        component_ir.metadata
        if isinstance(component_ir, Component) and component_ir.metadata
        else BuildMetadata()
    )
    return BuildResult(component_ir, resolved, operations, lowered.entities, volume, metadata)


def write_build_outputs(result: BuildResult, nbt_path: str | Path, debug_dir: str | Path | None = None) -> None:
    write_structure_nbt(result.volume, nbt_path)
    write_json(result.metadata.to_dict(), Path(nbt_path).with_suffix(".meta.json"))
    if debug_dir is None:
        return
    directory = Path(debug_dir)
    directory.mkdir(parents=True, exist_ok=True)
    write_json(_jsonable(result.component_ir), directory / "component-ir.json")
    write_json(resolved_to_dict(result.resolved), directory / "resolved.json")
    write_json(operations_to_dict(result.operations), directory / "operations.json")
    write_json(entities_to_dict(result.entities), directory / "entities.json")
    write_json(dense_to_dict(result.volume), directory / "dense.json")


def _root_size(node: Node, props: dict[str, Any]) -> Point:
    if all(key in props for key in ("width", "height", "length")):
        return Point(int(props["width"]), int(props["height"]), int(props["length"]))
    min_size = getattr(node, "min_size", None)
    if min_size is not None:
        return min_size
    raise ValueError("root_size is required when width, height, and length props are not all supplied")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Point):
        return value.to_list()
    if isinstance(value, Box):
        return value.to_dict()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        result = {"kind": type(value).__name__}
        for item in fields(value):
            result[item.name] = _jsonable(getattr(value, item.name))
        return result
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
