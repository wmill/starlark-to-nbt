"""The Rust engine behind the Python API.

`build_source()` evaluates, validates, and builds entirely in Rust (no
Python values cross the boundary until asked for). `build()` takes a raw
tree evaluated elsewhere. Both return a `RustBuildResult`. Its attributes match `pipeline.BuildResult`:
`volume`, `metadata`, `entities`, `operations`, `component_ir`, `resolved`.
They're backed by a `_core.Build` handle and turn into the usual Python
objects lazily, so the hot path (build, then write) never materializes
them. `block_at` and the writers go straight to Rust.

minecraft-mcp-api's runner.py reads `volume.bounds`, `volume.voxels`,
`volume.entities`, and `metadata`; those must keep working. The rest serves
the tests until Phase 7 of docs/rust-core-plan.md.
"""
from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any

from . import _core
from .execute import Voxel
from .ir import BlockOperation, BlockWrite, BuildMetadata, EntityPlacement, EntitySpec, Phase
from .model import BlockSpec, Box, BuildError, Diagnostic, Point, Provenance, SourceRef


def _box(pair) -> Box:
    low, high = pair
    return Box(Point(*low), Point(*high))


def diagnostics_from_core(items: list[dict[str, Any]]) -> BuildError:
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


class RustVolume:
    """`execute.SparseVolume`'s interface over a Rust build."""

    def __init__(self, result: RustBuildResult):
        self._result = result
        self._handle = result._handle
        self.bounds = _box(self._handle.bounds())

    def block_at(self, point: Point) -> BlockSpec:
        return self._result._blocks[self._handle.block_at(point.x, point.y, point.z)]

    @cached_property
    def voxels(self) -> dict[Point, Voxel]:
        blocks, provenances = self._result._blocks, self._result._provenances
        return {
            Point(x, y, z): Voxel(blocks[block], provenances[prov], Phase(phase))
            for x, y, z, block, prov, phase in self._handle.voxels()
        }

    @property
    def entities(self) -> list[EntityPlacement]:
        return self._result.entities


class RustBuildResult:
    """`pipeline.BuildResult`'s interface over a Rust build."""

    def __init__(self, handle, raw_tree: Any, source_file: str | None):
        """`raw_tree` is the evaluated tree, or a zero-argument callable that
        re-evaluates it; it's only needed for the test-facing `component_ir`."""
        self._handle = handle
        self._raw_tree = raw_tree
        self._source_file = source_file
        self.volume = RustVolume(self)
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

    @cached_property
    def component_ir(self):
        # Test-facing only; the Python schema still exists until Phase 7.
        from .schema import parse_node
        tree = self._raw_tree() if callable(self._raw_tree) else self._raw_tree
        return parse_node(tree, source_file=self._source_file)

    @cached_property
    def resolved(self):
        from .layout import resolve
        return resolve(self.component_ir, self.volume.bounds)

    def write_outputs(self, nbt_path: str | Path, debug_dir: str | Path | None = None) -> None:
        try:
            self._handle.write_outputs(Path(nbt_path), Path(debug_dir) if debug_dir is not None else None)
        except _core.CoreBuildError as exc:
            raise diagnostics_from_core(exc.args[0]) from None

    def write_structure_nbt(self, path: str | Path) -> None:
        try:
            self._handle.write_structure_nbt(Path(path))
        except _core.CoreBuildError as exc:
            raise diagnostics_from_core(exc.args[0]) from None


def build(raw_tree: Any, props: dict[str, Any], root_size: Point | None,
          source_file: str | None) -> RustBuildResult:
    try:
        handle = _core.build(raw_tree, props, root_size.to_list() if root_size else None, source_file)
    except _core.CoreBuildError as exc:
        raise diagnostics_from_core(exc.args[0]) from None
    return RustBuildResult(handle, raw_tree, source_file)


def build_source(source: str, filename: str, entry: str, props: dict[str, Any], root_size: Point | None,
                 base_dir: str | Path | None, loader_root: str | Path | None,
                 mounts: dict[str, str | Path] | None) -> RustBuildResult:
    loader = {
        "base_dir": Path(base_dir) if base_dir is not None else None,
        "loader_root": Path(loader_root) if loader_root is not None else None,
        "mounts": {name: Path(path) for name, path in mounts.items()} if mounts else None,
    }
    try:
        handle = _core.build_source(source, filename, entry, props,
                                    root_size.to_list() if root_size else None, **loader)
    except _core.CoreBuildError as exc:
        raise diagnostics_from_core(exc.args[0]) from None

    def raw_tree():
        return _core.evaluate_source(source, filename, entry, props, **loader)

    return RustBuildResult(handle, raw_tree, filename)
