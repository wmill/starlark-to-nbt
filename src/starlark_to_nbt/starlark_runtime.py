from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import starlark as sl

from .ir import Node
from .model import BuildError, Diagnostic, SourceRef
from .schema import parse_node


def _tag(kind: str, **values: Any) -> dict[str, Any]:
    return {"kind": kind, **{key: value for key, value in values.items() if value is not None}}


def component(name, props, body, min_size=None, metadata=None):
    return _tag("component", name=name, props=props, body=body, min_size=min_size, metadata=metadata)


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


def block(block_type, block_state=None, nbt=None):
    value = {"block_type": block_type, "block_state": block_state or {}}
    if nbt is not None:
        value["nbt"] = nbt
    return value


def sign_nbt(lines=None, color="black", glowing=False,
             back_lines=None, back_color="black", back_glowing=False, waxed=True):
    """Sign block-entity data for block(..., nbt=...). Messages are plain
    strings: 1.21.5+ text components treat a bare string as literal text."""
    def side(text, side_color, side_glowing):
        text = (list(text or []) + ["", "", "", ""])[:4]
        return {"messages": text, "color": side_color, "has_glowing_text": bool(side_glowing)}
    return {
        "id": "minecraft:sign",
        "front_text": side(lines, color, glowing),
        "back_text": side(back_lines, back_color, back_glowing),
        "is_waxed": bool(waxed),
    }


def container_nbt(items=None, id="minecraft:chest"):
    """Container block-entity data (chest, barrel, furnace, ...) for
    block(..., nbt=...). `items` entries are item ids or dicts with "id" and
    optional "count" (default 1), "slot" (defaults to the next slot in order),
    and "components"."""
    packed = []
    next_slot = 0
    for entry in list(items or []):
        if isinstance(entry, str):
            entry = {"id": entry}
        unknown = entry.keys() - {"id", "count", "slot", "components"}
        if unknown or "id" not in entry:
            raise ValueError(f"container item must have 'id' and only 'count', 'slot', 'components': {entry}")
        item = {"Slot": entry.get("slot", next_slot), "id": entry["id"], "count": entry.get("count", 1)}
        if "components" in entry:
            item["components"] = entry["components"]
        next_slot = item["Slot"] + 1
        packed.append(item)
    return {"id": id, "Items": packed}


def loot_nbt(table, seed=None, id="minecraft:chest"):
    """Loot-table block-entity data: the container rolls `table` when first opened."""
    value = {"id": id, "LootTable": table}
    if seed is not None:
        value["LootTableSeed"] = seed
    return value


def place_block(pos, block, phase="structure"):
    return _tag("place_block", pos=pos, block=block, phase=phase)


def fill_region(min, max, block, phase="structure"):
    return _tag("fill_region", box={"min": min, "max": max}, block=block, phase=phase)


def carve_region(min, max):
    return _tag("carve_region", box={"min": min, "max": max})


def place_assembly(pos, name, size, blocks):
    return _tag("place_assembly", pos=pos, name=name, size=size, blocks=blocks)


BOUND_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "component": component, "group": group, "fixed": fixed, "fill": fill,
    "split": split, "inset": inset, "repeat": repeat, "transform": transform,
    "block": block, "sign_nbt": sign_nbt, "container_nbt": container_nbt, "loot_nbt": loot_nbt,
    "place_block": place_block, "fill_region": fill_region, "carve_region": carve_region,
    "place_assembly": place_assembly,
}


def _new_module() -> sl.Module:
    module = sl.Module()
    for name, function in BOUND_FUNCTIONS.items():
        module.add_callable(name, function)
    return module


class _Loader:
    """Resolves load() statements relative to the file issuing the load."""

    def __init__(self, base_dir: Path):
        self._dir_stack = [base_dir]
        self._cache: dict[str, sl.FrozenModule] = {}
        self._in_progress: set[str] = set()
        # The Rust eval layer wraps Python exceptions raised by the load
        # callback, so the original BuildError is kept here for re-raising.
        self.error: BuildError | None = None
        self.file_loader = sl.FileLoader(self._load)

    def _load(self, path: str) -> sl.FrozenModule:
        raw = Path(path)
        resolved = raw if raw.is_absolute() else self._dir_stack[-1] / raw
        resolved = resolved.resolve()
        key = str(resolved)
        if key in self._cache:
            return self._cache[key]
        if key in self._in_progress:
            raise self._fail("load_cycle", f"circular load of {path}", key)
        try:
            source = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            raise self._fail("load_error", f"cannot load {path}: {exc}", key) from exc
        self._in_progress.add(key)
        self._dir_stack.append(resolved.parent)
        try:
            module = _new_module()
            ast = sl.parse(key, source)
            sl.eval(module, ast, sl.Globals.standard(), self.file_loader)
            frozen = module.freeze()
        finally:
            self._dir_stack.pop()
            self._in_progress.discard(key)
        self._cache[key] = frozen
        return frozen

    def _fail(self, code: str, message: str, file: str) -> BuildError:
        error = BuildError(Diagnostic(code, message, "<load>", SourceRef(file)))
        if self.error is None:
            self.error = error
        return error


_ENTRY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def evaluate_source(source: str, filename: str, entry: str, props: dict[str, Any],
                    base_dir: str | Path | None = None) -> Node:
    if not _ENTRY_NAME.fullmatch(entry):
        raise BuildError(Diagnostic("invalid_entry", f"entry {entry!r} is not a valid identifier", entry,
                                    SourceRef(filename)))
    loader = _Loader(Path(base_dir)) if base_dir is not None else None
    file_loader = loader.file_loader if loader else None
    try:
        module = _new_module()
        ast = sl.parse(filename, source)
        sl.eval(module, ast, sl.Globals.standard(), file_loader)
        # Calling via a trampoline expression instead of FrozenModule.call()
        # keeps prop names like "name" from colliding with call()'s own
        # parameters.
        module["__starlark_to_nbt_props__"] = props
        call_ast = sl.parse(f"<entry {entry}>", f"{entry}(**__starlark_to_nbt_props__)")
        result = sl.eval(module, call_ast, sl.Globals.standard(), file_loader)
    except Exception as exc:
        if isinstance(exc, BuildError):
            raise
        if loader is not None and loader.error is not None:
            raise loader.error from exc
        raise BuildError(Diagnostic("starlark_error", str(exc), entry, SourceRef(filename))) from exc
    return parse_node(result, source_file=filename)


def evaluate_file(path: str | Path, entry: str = "build", props: dict[str, Any] | None = None) -> Node:
    source_path = Path(path)
    return evaluate_source(source_path.read_text(encoding="utf-8"), str(source_path), entry, props or {},
                           base_dir=source_path.resolve().parent)
