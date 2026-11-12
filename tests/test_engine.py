"""The engine switch and build fingerprint (docs/rust-core-plan.md, Phase 5).

The default engine is Rust. STARLARK_TO_NBT_ENGINE=python keeps the
pure-Python pipeline available until Phase 7 removes it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import starlark_to_nbt
from starlark_to_nbt import _rust
from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import BuildResult, build_file, build_source, write_build_outputs
from starlark_to_nbt.serialize import write_structure_nbt

ROOT = Path(__file__).resolve().parents[1]


def test_default_engine_is_rust(monkeypatch):
    monkeypatch.delenv("STARLARK_TO_NBT_ENGINE", raising=False)
    assert starlark_to_nbt.engine() == "rust"
    assert isinstance(build_file(ROOT / "examples" / "procedural_ziggurat.star"), _rust.RustBuildResult)


def test_unknown_engine_is_rejected(monkeypatch):
    monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", "fortran")
    with pytest.raises(ValueError, match="STARLARK_TO_NBT_ENGINE"):
        build_file(ROOT / "examples" / "procedural_ziggurat.star")


def test_fingerprint_names_engine_and_core(monkeypatch):
    monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", "rust")
    rust = starlark_to_nbt.build_fingerprint()
    monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", "python")
    python = starlark_to_nbt.build_fingerprint()
    assert rust.startswith("rust-") and python.startswith("python-")
    assert rust.split("-", 1)[1] == python.split("-", 1)[1]
    assert len(rust.rsplit("-", 1)[1]) == 16


@pytest.mark.parametrize("name", ["church", "redstone_showcase"])
def test_engines_write_identical_outputs(name, tmp_path, monkeypatch):
    outputs = {}
    for engine in ("python", "rust"):
        monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", engine)
        result = build_file(ROOT / "examples" / f"{name}.star")
        write_build_outputs(result, tmp_path / f"{engine}.nbt", tmp_path / f"{engine}-debug")
        write_structure_nbt(result.volume, tmp_path / f"{engine}-direct.nbt")
        outputs[engine] = [
            (tmp_path / f"{engine}.nbt").read_bytes(),
            (tmp_path / f"{engine}.meta.json").read_bytes(),
            (tmp_path / f"{engine}-direct.nbt").read_bytes(),
            *[(tmp_path / f"{engine}-debug" / f).read_bytes() for f in sorted(p.name for p in (tmp_path / f"{engine}-debug").iterdir())],
        ]
    assert isinstance(result, _rust.RustBuildResult)
    assert outputs["rust"] == outputs["python"]


def test_rust_results_match_python_result_api(monkeypatch):
    """runner.py's attribute surface, plus what the tests read."""
    results = {}
    for engine in ("python", "rust"):
        monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", engine)
        results[engine] = build_file(ROOT / "examples" / "cottage.star")
    py, rs = results["python"], results["rust"]
    assert isinstance(py, BuildResult)
    assert rs.volume.bounds == py.volume.bounds
    assert rs.volume.voxels == py.volume.voxels
    assert all(rs.volume.block_at(p) == py.volume.block_at(p) for p in py.volume.voxels)
    assert rs.volume.block_at(Point(-5, -5, -5)) == py.volume.block_at(Point(-5, -5, -5))
    assert rs.volume.entities == py.volume.entities == rs.entities
    assert rs.operations == py.operations
    assert rs.metadata == py.metadata
    assert rs.component_ir == py.component_ir


def test_rust_diagnostics_become_build_errors(monkeypatch):
    source = ('def build():\n    return component("C", {}, group([place_block([0, 0, 0], block("minecraft:stone")),'
              ' place_block([0, 0, 0], block("minecraft:dirt"))]), min_size=[1, 1, 1])\n')
    errors = {}
    for engine in ("python", "rust"):
        monkeypatch.setenv("STARLARK_TO_NBT_ENGINE", engine)
        with pytest.raises(BuildError) as info:
            build_source(source)
        errors[engine] = info.value
    diagnostic = errors["rust"].diagnostics[0]
    assert (diagnostic.code, diagnostic.component_path, diagnostic.coordinates) == ("block_conflict", "C", Point(0, 0, 0))
    assert diagnostic.details == {"existingComponent": "C"}
    assert errors["rust"].diagnostics == errors["python"].diagnostics
    assert str(errors["rust"]) == str(errors["python"]) == "block_conflict: C: cannot overwrite minecraft:stone from C"
