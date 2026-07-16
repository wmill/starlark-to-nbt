from __future__ import annotations

import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file


def test_load_resolves_relative_to_loading_file(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "palette.star").write_text('STONE = "minecraft:stone"\n', encoding="utf-8")
    (tmp_path / "nested" / "lib.star").write_text(
        'load("palette.star", "STONE")\n'
        "\n"
        "def Slab(width):\n"
        '    return component(name="Slab", props={"width": width},\n'
        "                     body=fill_region([0, 0, 0], [width, 1, 1], block(STONE)))\n",
        encoding="utf-8",
    )
    (tmp_path / "main.star").write_text(
        'load("nested/lib.star", "Slab")\n'
        "\n"
        "def build(width=4):\n"
        "    return Slab(width)\n",
        encoding="utf-8",
    )
    result = build_file(tmp_path / "main.star", root_size=Point(4, 1, 1))
    assert len(result.volume.voxels) == 4


def test_load_missing_file_reports_load_error(tmp_path):
    (tmp_path / "main.star").write_text(
        'load("nope.star", "X")\n\ndef build():\n    return None\n', encoding="utf-8",
    )
    with pytest.raises(BuildError) as info:
        build_file(tmp_path / "main.star", root_size=Point(1, 1, 1))
    assert info.value.diagnostics[0].code == "load_error"


def test_load_cycle_reports_load_cycle(tmp_path):
    (tmp_path / "a.star").write_text('load("b.star", "B")\nA = 1\n\ndef build():\n    return None\n', encoding="utf-8")
    (tmp_path / "b.star").write_text('load("a.star", "A")\nB = 1\n', encoding="utf-8")
    with pytest.raises(BuildError) as info:
        build_file(tmp_path / "a.star", root_size=Point(1, 1, 1))
    assert info.value.diagnostics[0].code == "load_cycle"


def test_props_named_like_call_parameters_do_not_collide(tmp_path):
    (tmp_path / "main.star").write_text(
        "def build(name):\n"
        '    return component(name=name, props={"name": name},\n'
        '                     body=place_block([0, 0, 0], block("minecraft:stone")))\n',
        encoding="utf-8",
    )
    result = build_file(tmp_path / "main.star", props={"name": "Named"}, root_size=Point(1, 1, 1))
    assert len(result.volume.voxels) == 1
