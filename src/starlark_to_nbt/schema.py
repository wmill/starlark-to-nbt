from __future__ import annotations

import re
from typing import Any

from .ir import (
    AssemblyBlock, CarveRegion, Component, Fill, FillRegion, Fixed, Group, Inset,
    Node, PlaceAssembly, PlaceBlock, Repeat, SizeExpr, Split, TransformNode,
)
from .model import Axis, BlockSpec, Box, BuildError, Diagnostic, Point, SourceRef


IDENTIFIER = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")


def _error(path: str, message: str, code: str = "invalid_ir") -> BuildError:
    return BuildError(Diagnostic(code, message, path))


def _dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, "expected an object")
    if not all(isinstance(k, str) for k in value):
        raise _error(path, "object keys must be strings")
    return value


def _keys(value: dict[str, Any], required: set[str], optional: set[str], path: str) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise _error(path, f"missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise _error(path, f"unknown fields: {', '.join(sorted(unknown))}")


def _int(value: Any, path: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(path, "expected an integer")
    if minimum is not None and value < minimum:
        raise _error(path, f"expected an integer >= {minimum}")
    return value


def _point(value: Any, path: str, positive: bool = False) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise _error(path, "expected a three-integer coordinate")
    values = [_int(v, f"{path}[{i}]", 1 if positive else None) for i, v in enumerate(value)]
    return Point(*values)


def _box(value: Any, path: str) -> Box:
    obj = _dict(value, path)
    _keys(obj, {"min", "max"}, set(), path)
    try:
        return Box(_point(obj["min"], f"{path}.min"), _point(obj["max"], f"{path}.max"))
    except ValueError as exc:
        raise _error(path, str(exc)) from exc


def _axis(value: Any, path: str) -> Axis:
    try:
        return Axis(value)
    except (ValueError, TypeError) as exc:
        raise _error(path, "axis must be x, y, or z") from exc


def _block(value: Any, path: str) -> BlockSpec:
    obj = _dict(value, path)
    _keys(obj, {"block_type"}, {"block_state"}, path)
    block_type = obj["block_type"]
    if not isinstance(block_type, str) or not IDENTIFIER.fullmatch(block_type):
        raise _error(f"{path}.block_type", "expected a namespaced Minecraft identifier")
    state = obj.get("block_state", {})
    if not isinstance(state, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in state.items()):
        raise _error(f"{path}.block_state", "expected a string-to-string object")
    return BlockSpec(block_type, dict(state))


def _json_value(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [_json_value(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: _json_value(v, f"{path}.{k}") for k, v in value.items()}
    raise _error(path, "props must contain only JSON-compatible values")


def _source(value: Any, path: str) -> SourceRef:
    obj = _dict(value, path)
    _keys(obj, {"file"}, {"line", "column"}, path)
    if not isinstance(obj["file"], str):
        raise _error(f"{path}.file", "expected a string")
    return SourceRef(
        obj["file"],
        _int(obj["line"], f"{path}.line", 1) if obj.get("line") is not None else None,
        _int(obj["column"], f"{path}.column", 1) if obj.get("column") is not None else None,
    )


def parse_size(value: Any, path: str) -> SizeExpr:
    obj = _dict(value, path)
    kind = obj.get("kind")
    if kind == "fixed":
        _keys(obj, {"kind", "value"}, set(), path)
        return Fixed(_int(obj["value"], f"{path}.value", 1))
    if kind == "fill":
        _keys(obj, {"kind"}, set(), path)
        return Fill()
    raise _error(path, f"unknown size expression kind {kind!r}")


def parse_node(value: Any, path: str = "$", source_file: str | None = None) -> Node:
    obj = _dict(value, path)
    kind = obj.get("kind")
    if not isinstance(kind, str):
        raise _error(path, "missing string field 'kind'")

    if kind == "component":
        _keys(obj, {"kind", "name", "props", "body"}, {"min_size", "source"}, path)
        if not isinstance(obj["name"], str) or not obj["name"]:
            raise _error(f"{path}.name", "expected a non-empty string")
        props_obj = _dict(obj["props"], f"{path}.props")
        source = _source(obj["source"], f"{path}.source") if obj.get("source") else (SourceRef(source_file) if source_file else None)
        return Component(
            obj["name"], _json_value(props_obj, f"{path}.props"),
            parse_node(obj["body"], f"{path}.body", source_file),
            _point(obj["min_size"], f"{path}.min_size", True) if obj.get("min_size") is not None else None,
            source,
        )
    if kind == "group":
        _keys(obj, {"kind", "children"}, set(), path)
        if not isinstance(obj["children"], list):
            raise _error(f"{path}.children", "expected a list")
        return Group(tuple(parse_node(v, f"{path}.children[{i}]", source_file) for i, v in enumerate(obj["children"])))
    if kind == "split":
        _keys(obj, {"kind", "axis", "sizes", "children"}, set(), path)
        if not isinstance(obj["sizes"], list) or not isinstance(obj["children"], list):
            raise _error(path, "sizes and children must be lists")
        sizes = tuple(parse_size(v, f"{path}.sizes[{i}]") for i, v in enumerate(obj["sizes"]))
        children = tuple(parse_node(v, f"{path}.children[{i}]", source_file) for i, v in enumerate(obj["children"]))
        if not sizes or len(sizes) != len(children):
            raise _error(path, "split requires equal, non-empty sizes and children")
        return Split(_axis(obj["axis"], f"{path}.axis"), sizes, children)
    if kind == "inset":
        _keys(obj, {"kind", "amounts", "child"}, set(), path)
        amounts_obj = _dict(obj["amounts"], f"{path}.amounts")
        _keys(amounts_obj, {"x", "y", "z"}, set(), f"{path}.amounts")
        amounts: dict[Axis, tuple[int, int]] = {}
        for axis in Axis:
            pair = amounts_obj[axis.value]
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise _error(f"{path}.amounts.{axis.value}", "expected [low, high]")
            amounts[axis] = (_int(pair[0], path, 0), _int(pair[1], path, 0))
        return Inset(amounts, parse_node(obj["child"], f"{path}.child", source_file))
    if kind == "repeat":
        _keys(obj, {"kind", "axis", "count", "child_extent", "gap", "child"}, set(), path)
        return Repeat(
            _axis(obj["axis"], f"{path}.axis"), _int(obj["count"], f"{path}.count", 1),
            _int(obj["child_extent"], f"{path}.child_extent", 1), _int(obj["gap"], f"{path}.gap", 0),
            parse_node(obj["child"], f"{path}.child", source_file),
        )
    if kind == "transform":
        _keys(obj, {"kind", "translation", "rotation_y", "child_size", "child"}, set(), path)
        rotation = _int(obj["rotation_y"], f"{path}.rotation_y")
        if rotation not in (0, 90, 180, 270):
            raise _error(f"{path}.rotation_y", "expected 0, 90, 180, or 270")
        return TransformNode(_point(obj["translation"], f"{path}.translation"), rotation,
                             _point(obj["child_size"], f"{path}.child_size", True),
                             parse_node(obj["child"], f"{path}.child", source_file))
    if kind == "place_block":
        _keys(obj, {"kind", "pos", "block"}, {"phase"}, path)
        phase = obj.get("phase", "structure")
        if phase not in ("structure", "fixture"):
            raise _error(f"{path}.phase", "phase must be structure or fixture")
        return PlaceBlock(_point(obj["pos"], f"{path}.pos"), _block(obj["block"], f"{path}.block"), phase)
    if kind == "fill_region":
        _keys(obj, {"kind", "box", "block"}, {"phase"}, path)
        phase = obj.get("phase", "structure")
        if phase not in ("structure", "fixture"):
            raise _error(f"{path}.phase", "phase must be structure or fixture")
        return FillRegion(_box(obj["box"], f"{path}.box"), _block(obj["block"], f"{path}.block"), phase)
    if kind == "carve_region":
        _keys(obj, {"kind", "box"}, set(), path)
        return CarveRegion(_box(obj["box"], f"{path}.box"))
    if kind == "place_assembly":
        _keys(obj, {"kind", "pos", "name", "size", "blocks"}, set(), path)
        if not isinstance(obj["name"], str) or not obj["name"]:
            raise _error(f"{path}.name", "expected a non-empty string")
        if not isinstance(obj["blocks"], list) or not obj["blocks"]:
            raise _error(f"{path}.blocks", "expected a non-empty list")
        blocks: list[AssemblyBlock] = []
        for i, raw in enumerate(obj["blocks"]):
            item_path = f"{path}.blocks[{i}]"
            item = _dict(raw, item_path)
            _keys(item, {"pos", "block"}, set(), item_path)
            blocks.append(AssemblyBlock(_point(item["pos"], f"{item_path}.pos"), _block(item["block"], f"{item_path}.block")))
        return PlaceAssembly(_point(obj["pos"], f"{path}.pos"), obj["name"],
                             _point(obj["size"], f"{path}.size", True), tuple(blocks))
    raise _error(path, f"unknown node kind {kind!r}")
