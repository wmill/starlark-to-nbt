from __future__ import annotations

from pathlib import Path

import pytest

from starlark_to_nbt.execute import SparseVolume, Voxel
from starlark_to_nbt.ir import Phase
from starlark_to_nbt.model import BlockSpec, Box, BuildError, Point, Provenance
from starlark_to_nbt.pipeline import build_source
from starlark_to_nbt.serialize import write_structure_nbt


REPO_ROOT = Path(__file__).parents[1]

SIMPLE_SOURCE = (
    "def build():\n"
    '    return component(name="Cell", props={},\n'
    '                     body=place_block([0, 0, 0], block("minecraft:stone")))\n'
)


def test_build_source_happy_path():
    result = build_source(SIMPLE_SOURCE, root_size=Point(1, 1, 1))
    assert len(result.volume.voxels) == 1


def test_build_source_props_reach_entry():
    source = (
        "def build(width=2):\n"
        '    return component(name="Row", props={"width": width},\n'
        '                     body=fill_region([0, 0, 0], [width, 1, 1], block("minecraft:stone")))\n'
    )
    result = build_source(source, props={"width": 3}, root_size=Point(3, 1, 1))
    assert len(result.volume.voxels) == 3


def test_confined_loader_allows_lib_via_examples_convention(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "palette.star").write_text('STONE = "minecraft:stone"\n', encoding="utf-8")
    source = (
        'load("../lib/palette.star", "STONE")\n'
        "\n"
        "def build():\n"
        '    return component(name="Cell", props={},\n'
        "                     body=place_block([0, 0, 0], block(STONE)))\n"
    )
    result = build_source(source, root_size=Point(1, 1, 1),
                          base_dir=tmp_path / "scripts", loader_root=tmp_path)
    assert len(result.volume.voxels) == 1


def test_confined_loader_works_against_repo_lib():
    source = (
        'load("../lib/random.star", "RANDOM_NUMBERS")\n'
        "\n"
        "def build():\n"
        '    return component(name="Cell", props={"count": len(RANDOM_NUMBERS)},\n'
        '                     body=place_block([0, 0, 0], block("minecraft:stone")))\n'
    )
    result = build_source(source, root_size=Point(1, 1, 1),
                          base_dir=REPO_ROOT / "scripts", loader_root=REPO_ROOT)
    assert result.component_ir.props["count"] == 1024


def _diagnostic(source: str, **kwargs):
    with pytest.raises(BuildError) as info:
        build_source(source, root_size=Point(1, 1, 1), **kwargs)
    return info.value.diagnostics[0]


def test_confined_loader_rejects_absolute_paths(tmp_path):
    target = REPO_ROOT / "lib" / "random.star"
    source = f'load("{target.as_posix()}", "RANDOM_NUMBERS")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=tmp_path / "scripts", loader_root=tmp_path)
    assert diagnostic.code == "load_error"
    assert "module not found" in diagnostic.message


def test_confined_loader_rejects_escape_outside_root(tmp_path):
    source = 'load("../../outside.star", "X")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=tmp_path / "scripts", loader_root=tmp_path)
    assert diagnostic.code == "load_error"
    assert "module not found" in diagnostic.message


def test_confined_loader_rejects_non_allowed_directories(tmp_path):
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "hidden.star").write_text("X = 1\n", encoding="utf-8")
    source = 'load("../secrets/hidden.star", "X")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=tmp_path / "scripts", loader_root=tmp_path)
    assert diagnostic.code == "load_error"
    assert "module not found" in diagnostic.message


def test_confined_loader_hides_filesystem_details(tmp_path):
    (tmp_path / "lib").mkdir()
    source = 'load("../lib/nope.star", "X")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=tmp_path / "scripts", loader_root=tmp_path)
    assert diagnostic.code == "load_error"
    assert diagnostic.message == "module not found: ../lib/nope.star"


def test_unconfined_loader_keeps_absolute_path_support(tmp_path):
    (tmp_path / "palette.star").write_text('STONE = "minecraft:stone"\n', encoding="utf-8")
    source = (
        f'load("{(tmp_path / "palette.star").as_posix()}", "STONE")\n'
        "\n"
        "def build():\n"
        '    return component(name="Cell", props={},\n'
        "                     body=place_block([0, 0, 0], block(STONE)))\n"
    )
    result = build_source(source, root_size=Point(1, 1, 1), base_dir=tmp_path)
    assert len(result.volume.voxels) == 1


def test_missing_root_size_is_a_diagnostic():
    with pytest.raises(BuildError) as info:
        build_source(SIMPLE_SOURCE)
    assert info.value.diagnostics[0].code == "missing_root_size"


def test_non_positive_root_size_is_a_diagnostic():
    source = (
        "def build(width=1, height=1, length=1):\n"
        '    return component(name="Cell", props={},\n'
        '                     body=place_block([0, 0, 0], block("minecraft:stone")))\n'
    )
    with pytest.raises(BuildError) as info:
        build_source(source, props={"width": 0, "height": 1, "length": 1})
    assert info.value.diagnostics[0].code == "invalid_box"


def test_unserializable_block_nbt_is_a_diagnostic(tmp_path):
    bounds = Box.from_size(Point(1, 1, 1))
    provenance = Provenance("<root>", bounds)
    spec = BlockSpec("minecraft:chest", {}, {"bad": object()})
    volume = SparseVolume(bounds, {Point(0, 0, 0): Voxel(spec, provenance, Phase.STRUCTURE)})
    with pytest.raises(BuildError) as info:
        write_structure_nbt(volume, tmp_path / "out.nbt")
    assert info.value.diagnostics[0].code == "serialize_error"


def _library(tmp_path):
    library = tmp_path / "library"
    (library / "cell").mkdir(parents=True)
    (library / "cell" / "v1.star").write_text(
        'load("../lib/palette.star", "STONE")\n'
        "\n"
        "def Cell():\n"
        '    return component(name="Cell", props={},\n'
        "                     body=place_block([0, 0, 0], block(STONE)))\n",
        encoding="utf-8",
    )
    root = tmp_path / "root"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "palette.star").write_text('STONE = "minecraft:stone"\n', encoding="utf-8")
    return root, library


def test_mounted_library_module_loads_with_script_relative_paths(tmp_path):
    root, library = _library(tmp_path)
    source = 'load("../library/cell/v1.star", "Cell")\n\ndef build():\n    return Cell()\n'
    result = build_source(source, root_size=Point(1, 1, 1), base_dir=root / "scripts",
                          loader_root=root, mounts={"library": library})
    assert len(result.volume.voxels) == 1


def test_mounted_library_rejects_escape_from_mount(tmp_path):
    root, library = _library(tmp_path)
    (tmp_path / "secret.star").write_text("X = 1\n", encoding="utf-8")
    source = 'load("../library/../../secret.star", "X")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=root / "scripts", loader_root=root,
                             mounts={"library": library})
    assert diagnostic.message == "module not found: ../library/../../secret.star"


def test_mounted_library_missing_module_is_uniform(tmp_path):
    root, library = _library(tmp_path)
    source = 'load("../library/cell/v9.star", "Cell")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=root / "scripts", loader_root=root,
                             mounts={"library": library})
    assert diagnostic.message == "module not found: ../library/cell/v9.star"


def test_library_directory_is_not_loadable_without_mount(tmp_path):
    root, _ = _library(tmp_path)
    (root / "library" / "cell").mkdir(parents=True)
    (root / "library" / "cell" / "v1.star").write_text("X = 1\n", encoding="utf-8")
    source = 'load("../library/cell/v1.star", "X")\n\ndef build():\n    return None\n'
    diagnostic = _diagnostic(source, base_dir=root / "scripts", loader_root=root)
    assert diagnostic.code == "load_error"
