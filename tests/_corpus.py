"""Raw-tree access to the golden corpus, for Rust-vs-Python parity tests.

Each case is evaluated with the real Starlark runtime but stops before
schema validation, yielding the raw tagged-dict tree plus the props,
root_size, and source file the pipeline would use. The cases mirror
scripts/golden.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from starlark_to_nbt import starlark_runtime

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "lib" / "showcase.star"
LIBRARY = ROOT.parents[1] / "minecraft-mcp-api" / "starlark-library"


@dataclass
class Case:
    name: str
    source_file: str
    tree: Any
    props: dict[str, Any] = field(default_factory=dict)
    root_size: list[int] | None = None


def _raw(source: str, filename: str, entry: str, props: dict, **loader) -> Any:
    original = starlark_runtime.parse_node
    starlark_runtime.parse_node = lambda value, source_file=None: value
    try:
        return starlark_runtime.evaluate_source(source, filename, entry, props, **loader)
    finally:
        starlark_runtime.parse_node = original


def _file(path: Path, entry: str = "build", props: dict | None = None) -> Any:
    return _raw(path.read_text(encoding="utf-8"), str(path), entry, props or {},
                base_dir=path.resolve().parent)


def showcase_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))


def case_names() -> list[str]:
    names = [f"example/{p.stem}" for p in sorted((ROOT / "examples").glob("*.star"))]
    names.append("example/church@11x4x19")
    for name in showcase_names():
        names.append(f"showcase/{name}")
        names.extend(f"showcase/{name}@{r}" for r in (90, 180, 270))
    if LIBRARY.is_dir():
        for meta_path in sorted(LIBRARY.glob("*/meta.json")):
            for version in json.loads(meta_path.read_text(encoding="utf-8"))["versions"]:
                names.append(f"library/{meta_path.parent.name}/v{version['version']}")
    return names


@dataclass
class EvalInputs:
    source: str
    filename: str
    entry: str
    props: dict[str, Any]
    loader: dict[str, Any]
    root_size: list[int] | None = None


def eval_inputs(name: str) -> EvalInputs:
    """How the pipeline evaluates a corpus case: exactly what build_file /
    build_source (or the service's runner.py) pass to the Starlark runtime."""
    kind, _, rest = name.partition("/")
    if kind == "example":
        stem, _, variant = rest.partition("@")
        path = ROOT / "examples" / f"{stem}.star"
        props = {"width": 11, "length": 19, "height": 4} if variant else {}
        return EvalInputs(path.read_text(encoding="utf-8"), str(path), "build", props,
                          {"base_dir": path.resolve().parent})
    if kind == "showcase":
        component, _, rotation = rest.partition("@")
        entry, props = ("rotated", {"name": component, "rotation": int(rotation)}) if rotation else ("build", {"name": component})
        return EvalInputs(SHOWCASE.read_text(encoding="utf-8"), str(SHOWCASE), entry, props,
                          {"base_dir": SHOWCASE.resolve().parent})
    script_dir, version = rest.split("/")
    meta = json.loads((LIBRARY / script_dir / "meta.json").read_text(encoding="utf-8"))
    saved = next(v for v in meta["versions"] if f"v{v['version']}" == version)
    script = LIBRARY / script_dir / f"{version}.star"
    return EvalInputs(script.read_text(encoding="utf-8"), str(script), saved.get("entry") or "build",
                      saved.get("props") or {},
                      {"base_dir": ROOT / "scripts", "loader_root": ROOT, "mounts": {"library": LIBRARY}},
                      saved.get("root_size"))


def load_case(name: str) -> Case:
    kind, _, rest = name.partition("/")
    if kind == "example":
        stem, _, variant = rest.partition("@")
        path = ROOT / "examples" / f"{stem}.star"
        props = {"width": 11, "length": 19, "height": 4} if variant else {}
        return Case(name, str(path), _file(path, props=props), props)
    if kind == "showcase":
        component, _, rotation = rest.partition("@")
        if rotation:
            props = {"name": component, "rotation": int(rotation)}
            return Case(name, str(SHOWCASE), _file(SHOWCASE, "rotated", props), props)
        props = {"name": component}
        return Case(name, str(SHOWCASE), _file(SHOWCASE, props=props), props)
    script_dir, version = rest.split("/")
    meta = json.loads((LIBRARY / script_dir / "meta.json").read_text(encoding="utf-8"))
    saved = next(v for v in meta["versions"] if f"v{v['version']}" == version)
    script = LIBRARY / script_dir / f"{version}.star"
    props = saved.get("props") or {}
    tree = _raw(script.read_text(encoding="utf-8"), str(script), saved.get("entry") or "build", props,
                base_dir=ROOT / "scripts", loader_root=ROOT, mounts={"library": LIBRARY})
    return Case(name, str(script), tree, props, saved.get("root_size"))


def diagnostics_dicts(exc) -> list[dict]:
    """A BuildError's diagnostics in the shape `_core` returns them."""
    return [{
        "code": d.code, "component_path": d.component_path, "message": d.message,
        "region": d.region.to_dict() if d.region else None,
        "coordinates": d.coordinates.to_list() if d.coordinates else None,
        "details": d.details,
        "source": [d.source.file, d.source.line] if d.source else None,
    } for d in exc.diagnostics]
