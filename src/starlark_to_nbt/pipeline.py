"""The public build API, over the Rust core (`starlark_to_nbt._core`).

`build_file` / `build_source` evaluate a Starlark script and run the whole
pipeline in Rust: validation, layout, lowering, execution, the support
check, and validators. They return a `BuildResult`, whose `volume`,
`entities`, and `operations` become Python objects only on first access.
`block_at` and the writers go straight to Rust, so build-then-write never
materializes them.

minecraft-mcp-api's starlark-service (runner.py) relies on `build_source`
(with `base_dir`/`loader_root`/`mounts`), `BuildResult.volume.bounds`,
`.volume.voxels`, `.volume.entities`, `.metadata`, and
`serialize.write_structure_nbt`; keep those stable.
"""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any

from . import _core
from .ir import BlockOperation, BlockWrite, BuildMetadata, EntityPlacement, EntitySpec, Phase, Voxel
from .model import BlockSpec, Box, BuildError, Diagnostic, Point, Provenance, SourceRef


def _box(pair) -> Box:
    low, high = pair
    return Box(Point(*low), Point(*high))


def _build_error(items: list[dict[str, Any]]) -> BuildError:
    return BuildError([
        Diagnostic(
            item["code"], item["message"], item["component_path"],
            source=SourceRef(item["source"][0], item["source"][1]) if item["source"] else None,
            region=Box(Point(*item["region"]["min"]), Point(*item["region"]["max"])) if item["region"] else None,
            coordinates=Point(*item["coordinates"]) if item["coordinates"] else None,
            details=item["details"],
        )
        for item in items
    ])


class Volume:
    """The finished sparse volume: written cells only; unwritten cells read as air."""

    def __init__(self, result: BuildResult):
        self._result = result
        self._handle = result._handle
        self.bounds = _box(self._handle.bounds())

    def block_at(self, point: Point) -> BlockSpec:
        return self._result._blocks[self._handle.block_at(point.x, point.y, point.z)]

    @cached_property
    def voxels(self) -> dict[Point, Voxel]:
        """Written cells, in y/z/x order."""
        blocks, provenances = self._result._blocks, self._result._provenances
        return {
            Point(x, y, z): Voxel(blocks[block], provenances[prov], Phase(phase))
            for x, y, z, block, prov, phase in self._handle.voxels()
        }

    @property
    def entities(self) -> list[EntityPlacement]:
        return self._result.entities


class BuildResult:
    def __init__(self, handle):
        self._handle = handle
        self.volume = Volume(self)
        self.metadata = BuildMetadata(handle.ground_level())

    @cached_property
    def _blocks(self) -> list[BlockSpec]:
        return [BlockSpec(block_type, state, nbt) for block_type, state, nbt in self._handle.blocks()]

    @cached_property
    def _provenances(self) -> list[Provenance]:
        return [
            Provenance(path, _box(region), SourceRef(source[0], source[1]) if source else None)
            for path, region, source in self._handle.provenances()
        ]

    @cached_property
    def root_props(self) -> dict[str, Any] | None:
        """The root component's props (None if the root isn't a component)."""
        return self._handle.root_props()

    @cached_property
    def entities(self) -> list[EntityPlacement]:
        provenances = self._provenances
        return [
            EntityPlacement(Point(*pos), EntitySpec(entity_type, nbt, yaw, pitch), provenances[prov], sequence)
            for pos, entity_type, nbt, yaw, pitch, prov, sequence in self._handle.entities()
        ]

    @cached_property
    def operations(self) -> list[BlockOperation]:
        blocks, provenances = self._blocks, self._provenances
        return [
            BlockOperation(Phase(phase), kind, tuple(BlockWrite(Point(x, y, z), blocks[b]) for x, y, z, b in writes),
                           provenances[prov], assembly, sequence)
            for phase, kind, writes, prov, assembly, sequence in self._handle.operations()
        ]

    def write_structure_nbt(self, path: str | Path) -> None:
        try:
            self._handle.write_structure_nbt(Path(path))
        except _core.CoreBuildError as exc:
            raise _build_error(exc.args[0]) from None

    def write_outputs(self, nbt_path: str | Path, debug_dir: str | Path | None = None) -> None:
        try:
            self._handle.write_outputs(Path(nbt_path), Path(debug_dir) if debug_dir is not None else None)
        except _core.CoreBuildError as exc:
            raise _build_error(exc.args[0]) from None


def _loader(base_dir, loader_root, mounts) -> dict[str, Any]:
    return {
        "base_dir": Path(base_dir) if base_dir is not None else None,
        "loader_root": Path(loader_root) if loader_root is not None else None,
        "mounts": {name: Path(path) for name, path in mounts.items()} if mounts else None,
    }


def build_source(source: str, entry: str = "build", props: dict[str, Any] | None = None,
                 root_size: Point | None = None, filename: str = "<input>",
                 base_dir: str | Path | None = None,
                 loader_root: str | Path | None = None,
                 mounts: dict[str, str | Path] | None = None) -> BuildResult:
    """Build a script. Relative `load()`s resolve from `base_dir` (default
    `loader_root`). With `loader_root`, loads are confined to its `lib/` and
    to `mounts`, which map extra top-level names to outside directories."""
    try:
        handle = _core.build_source(source, filename, entry, props or {},
                                    root_size.to_list() if root_size else None,
                                    **_loader(base_dir, loader_root, mounts))
    except _core.CoreBuildError as exc:
        raise _build_error(exc.args[0]) from None
    return BuildResult(handle)


def build_file(path: str | Path, entry: str = "build", props: dict[str, Any] | None = None,
               root_size: Point | None = None) -> BuildResult:
    source_path = Path(path)
    return build_source(source_path.read_text(encoding="utf-8"), entry, props, root_size,
                        filename=str(source_path), base_dir=source_path.resolve().parent)


def evaluate_source(source: str, filename: str = "<input>", entry: str = "build",
                    props: dict[str, Any] | None = None,
                    base_dir: str | Path | None = None,
                    loader_root: str | Path | None = None,
                    mounts: dict[str, str | Path] | None = None) -> Any:
    """Evaluate a script's entry function and return its raw tagged-dict tree,
    unvalidated. Useful for probing helper functions from tests."""
    try:
        return _core.evaluate_source(source, filename, entry, props or {}, **_loader(base_dir, loader_root, mounts))
    except _core.CoreBuildError as exc:
        raise _build_error(exc.args[0]) from None


def write_build_outputs(result: BuildResult, nbt_path: str | Path, debug_dir: str | Path | None = None) -> None:
    """Write the structure NBT, `<stem>.meta.json` beside it, and with
    `debug_dir` the per-stage debug JSON."""
    result.write_outputs(nbt_path, debug_dir)
