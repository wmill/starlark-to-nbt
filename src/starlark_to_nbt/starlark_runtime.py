from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import starlark as sl

from .ir import Node
from .model import BuildError, Diagnostic, SourceRef
from .schema import parse_node


def _tag(kind: str, **values: Any) -> dict[str, Any]:
    return {"kind": kind, **{key: value for key, value in values.items() if value is not None}}


def component(name, props, body, min_size=None):
    return _tag("component", name=name, props=props, body=body, min_size=min_size)


def group(children):
    return _tag("group", children=children)


def fixed(value):
    return _tag("fixed", value=value)


def fill():
    return _tag("fill")


def split(axis, sizes, children):
    return _tag("split", axis=axis, sizes=sizes, children=children)


def inset(child, amount=None, x=None, y=None, z=None):
    if amount is not None:
        amounts = {axis: [amount, amount] for axis in ("x", "y", "z")}
    else:
        amounts = {"x": x or [0, 0], "y": y or [0, 0], "z": z or [0, 0]}
    return _tag("inset", amounts=amounts, child=child)


def repeat(axis, count, child_extent, gap, child):
    return _tag("repeat", axis=axis, count=count, child_extent=child_extent, gap=gap, child=child)


def transform(translation, rotation_y, child_size, child):
    return _tag("transform", translation=translation, rotation_y=rotation_y, child_size=child_size, child=child)


def block(block_type, block_state=None):
    return {"block_type": block_type, "block_state": block_state or {}}


def place_block(pos, block, phase="structure"):
    return _tag("place_block", pos=pos, block=block, phase=phase)


def fill_region(min, max, block):
    return _tag("fill_region", box={"min": min, "max": max}, block=block)


def carve_region(min, max):
    return _tag("carve_region", box={"min": min, "max": max})


def place_assembly(pos, name, size, blocks):
    return _tag("place_assembly", pos=pos, name=name, size=size, blocks=blocks)


BOUND_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "component": component, "group": group, "fixed": fixed, "fill": fill,
    "split": split, "inset": inset, "repeat": repeat, "transform": transform,
    "block": block, "place_block": place_block, "fill_region": fill_region,
    "carve_region": carve_region, "place_assembly": place_assembly,
}


def evaluate_source(source: str, filename: str, entry: str, props: dict[str, Any]) -> Node:
    try:
        module = sl.Module()
        for name, function in BOUND_FUNCTIONS.items():
            module.add_callable(name, function)
        ast = sl.parse(filename, source)
        sl.eval(module, ast, sl.Globals.standard())
        result = module.freeze().call(entry, **props)
    except Exception as exc:
        if isinstance(exc, BuildError):
            raise
        raise BuildError(Diagnostic("starlark_error", str(exc), entry, SourceRef(filename))) from exc
    return parse_node(result, source_file=filename)


def evaluate_file(path: str | Path, entry: str = "build", props: dict[str, Any] | None = None) -> Node:
    source_path = Path(path)
    return evaluate_source(source_path.read_text(encoding="utf-8"), str(source_path), entry, props or {})
