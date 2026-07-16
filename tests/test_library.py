"""Stress harness: every library component must build standalone (at its
showcase size, via the min_size root fallback) and under all four rotations,
with every write landing inside the root bounds."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from starlark_to_nbt.pipeline import build_file

SHOWCASE = Path(__file__).parents[1] / "lib" / "showcase.star"


def _component_names() -> list[str]:
    listing = re.search(r"COMPONENT_NAMES = \[(.*?)\]", SHOWCASE.read_text(encoding="utf-8"), re.S)
    return re.findall(r'"(\w+)"', listing.group(1))


COMPONENT_NAMES = _component_names()


def test_showcase_names_cover_all_library_constructors():
    lib_dir = SHOWCASE.parent
    exported = set()
    for star in lib_dir.glob("*.star"):
        if star.name == "showcase.star":
            continue
        exported |= set(re.findall(r"^def ([A-Z]\w*)\(", star.read_text(encoding="utf-8"), re.M))
    assert exported == set(COMPONENT_NAMES)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
def test_component_builds_standalone(name):
    result = build_file(SHOWCASE, props={"name": name})
    assert len(result.volume.voxels) > 0
    assert all(result.volume.bounds.contains_point(write.pos)
               for op in result.operations for write in op.writes)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_component_builds_under_rotation(name, rotation):
    result = build_file(SHOWCASE, entry="rotated", props={"name": name, "rotation": rotation})
    assert len(result.volume.voxels) > 0
    assert all(result.volume.bounds.contains_point(write.pos)
               for op in result.operations for write in op.writes)


@pytest.mark.parametrize("name", COMPONENT_NAMES)
def test_rotations_preserve_voxel_count(name):
    counts = {
        rotation: len(build_file(SHOWCASE, entry="rotated",
                                 props={"name": name, "rotation": rotation}).volume.voxels)
        for rotation in (0, 90, 180, 270)
    }
    assert len(set(counts.values())) == 1, counts
