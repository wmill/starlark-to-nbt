"""Rasterizer invariants for lib/shapes.star, the round roofs in
lib/roofs.star, and the math builtins."""
from __future__ import annotations

from pathlib import Path

import nbtlib
import pytest

from starlark_to_nbt.model import BuildError, Point
from starlark_to_nbt.pipeline import build_file
from starlark_to_nbt.serialize import write_structure_nbt
from starlark_to_nbt.starlark_runtime import evaluate_source

LIB = Path(__file__).parents[1] / "lib"
SHOWCASE = LIB / "showcase.star"


def _eval(expr: str):
    """Evaluate a Starlark expression with lib/shapes.star loaded; the value
    rides back on a throwaway component's props."""
    source = f'''
load("shapes.star", "disc_cells", "ellipse_cells", "ring_cells", "ellipse_ring_cells",
     "sphere_layer_cells", "cell_runs")

def build():
    return component(name="Probe", props={{"value": {expr}}}, min_size=[1, 1, 1],
                     body=place_block([0, 0, 0], block("minecraft:stone")))
'''
    return evaluate_source(source, "<probe>", "build", {}, base_dir=LIB).props["value"]


def _cells(expr: str) -> set[tuple[int, int]]:
    return {(x, z) for x, z in _eval(expr)}


@pytest.mark.parametrize("r", range(1, 13))
def test_disc_is_four_fold_symmetric(r):
    cells = _cells(f"disc_cells({r})")
    n = 2 * r
    assert cells == {(n - x, z) for x, z in cells}
    assert cells == {(z, x) for x, z in cells}


@pytest.mark.parametrize("r", range(2, 13))
def test_disc_has_no_lone_cardinal_cell(r):
    # Regression: the naive d2 <= r*r test leaves a one-block nub at each
    # cardinal tip. The edge row must be at least three blocks wide.
    cells = _cells(f"disc_cells({r})")
    edge_row = [z for x, z in cells if x == 0]
    assert len(edge_row) >= 3


def test_disc_cell_counts():
    counts = [len(_eval(f"disc_cells({r})")) for r in range(1, 7)]
    # Independent reference: count of x*x + z*z <= r*r + r.
    assert counts == [9, 21, 37, 69, 97, 137]


def _leaks(wall: set[tuple[int, int]], width: int, depth: int) -> bool:
    """Flood fill from the footprint edge through 4-neighbours; True when it
    reaches the center without crossing the wall."""
    outside = {(x, z) for x in range(-1, width + 1) for z in range(-1, depth + 1)
               if not (0 <= x < width and 0 <= z < depth)}
    seen, frontier = set(outside), list(outside)
    while frontier:
        x, z = frontier.pop()
        for nx, nz in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if (nx, nz) in seen or (nx, nz) in wall:
                continue
            if not (-1 <= nx <= width and -1 <= nz <= depth):
                continue
            seen.add((nx, nz))
            frontier.append((nx, nz))
    return (width // 2, depth // 2) in seen


@pytest.mark.parametrize("r", range(2, 16))
def test_ring_is_watertight(r):
    wall = _cells(f"ring_cells({r})")
    assert (r, r) not in wall
    assert not _leaks(wall, 2 * r + 1, 2 * r + 1)


@pytest.mark.parametrize("rx,rz", [(rx, rz) for rx in range(2, 12) for rz in range(2, 12)])
def test_ellipse_ring_is_watertight(rx, rz):
    wall = _cells(f"ellipse_ring_cells({rx}, {rz})")
    assert (rx, rz) not in wall
    assert not _leaks(wall, 2 * rx + 1, 2 * rz + 1)


def test_ring_is_disc_minus_smaller_disc():
    assert _cells("ring_cells(7, 2)") == (
        _cells("disc_cells(7)") - {(x + 2, z + 2) for x, z in _cells("disc_cells(5)")})


def test_cell_runs_cover_cells_exactly():
    runs = _eval("cell_runs(disc_cells(6))")
    covered = {(x, z) for x, z0, z1 in runs for z in range(z0, z1)}
    assert covered == _cells("disc_cells(6)")
    assert len(runs) == 13


def test_sphere_shell_is_closed_top_and_bottom():
    assert _cells("sphere_layer_cells(6, 6, 1)") == _cells("sphere_layer_cells(6, 6)")
    assert (6, 6) not in _cells("sphere_layer_cells(6, 0, 1)")


def test_dome_base_ring_matches_cylinder_ring():
    dome = build_file(SHOWCASE, props={"name": "Dome"}).volume
    cylinder = _cells("ring_cells(5)")
    base = {(p.x, p.z) for p in dome.voxels if p.y == 0}
    assert base == cylinder


def test_cylinder_floor_fills_interior_only():
    volume = build_file(SHOWCASE, props={"name": "Cylinder"}).volume
    assert volume.block_at(Point(4, 0, 4)).block_type == "minecraft:oak_planks"
    assert volume.block_at(Point(0, 0, 4)).block_type == "minecraft:stone_bricks"
    assert volume.block_at(Point(4, 3, 4)).block_type == "minecraft:air"


def test_shape_validation_fails_loudly():
    source = '''
load("shapes.star", "Cylinder")

def build():
    return Cylinder(4, 3, hollow=False, floor="minecraft:oak_planks")
'''
    with pytest.raises(BuildError, match="floor needs hollow"):
        evaluate_source(source, "<bad>", "build", {}, base_dir=LIB)


def _decoded_blocks(tmp_path, name):
    path = tmp_path / f"{name}.nbt"
    write_structure_nbt(build_file(SHOWCASE, props={"name": name}).volume, path)
    decoded = nbtlib.load(path)
    palette = decoded["palette"]
    blocks = {}
    for entry in decoded["blocks"]:
        pos = tuple(int(c) for c in entry["pos"])
        state = palette[int(entry["state"])]
        props = {str(k): str(v) for k, v in state.get("Properties", {}).items()}
        blocks[pos] = (str(state["Name"]), props)
    return blocks


def test_hip_roof_corners_have_outer_shapes_and_ridge(tmp_path):
    blocks = _decoded_blocks(tmp_path, "HipRoof")  # HipRoof(7, 11)
    assert blocks[(0, 0, 0)] == ("minecraft:oak_stairs",
                                 {"facing": "south", "half": "bottom", "shape": "outer_left"})
    assert blocks[(6, 0, 0)][1]["shape"] == "outer_right"
    assert blocks[(0, 0, 10)][1] == {"facing": "north", "half": "bottom", "shape": "outer_right"}
    assert blocks[(6, 0, 10)][1]["shape"] == "outer_left"
    assert blocks[(0, 0, 5)][1]["facing"] == "east"
    assert blocks[(3, 0, 0)][1] == {"facing": "south", "half": "bottom", "shape": "straight"}
    # Odd short side: a planks ridge along the long (Z) axis at the top.
    ridge = sorted(z for (x, y, z), (name, _) in blocks.items()
                   if y == 3 and name == "minecraft:oak_planks")
    assert ridge == list(range(3, 8))
    assert all(x == 3 for (x, y, z) in blocks if y == 3)


def test_cone_roof_stairs_face_the_axis_and_cap_the_apex(tmp_path):
    blocks = _decoded_blocks(tmp_path, "ConeRoof")  # ConeRoof(4)
    assert blocks[(0, 0, 4)][1]["facing"] == "east"
    assert blocks[(8, 0, 4)][1]["facing"] == "west"
    assert blocks[(4, 0, 0)][1]["facing"] == "south"
    assert blocks[(4, 0, 8)][1]["facing"] == "north"
    assert blocks[(4, 4, 4)][0] == "minecraft:oak_planks"
    assert max(y for _, y, _ in blocks) == 4
    # Each layer's ring covers the previous ring's inner edge: seen from
    # above, the cone hides the whole footprint disc.
    assert {(x, z) for x, _, z in blocks} == _cells("disc_cells(4)")


def test_math_builtins():
    assert _eval("[isqrt(50), round(2.5), round(-2.5), floor(-0.5), ceil(0.2), "
                 "round(cos(PI)), round(sqrt(2.0) * 10), round(atan2(1.0, 1.0) * 4 / PI), round(sin(PI / 2))]") \
        == [7, 3, -3, -1, 1, -1, 14, 1, 1]
    with pytest.raises(BuildError, match="isqrt"):
        _eval("isqrt(-1)")
