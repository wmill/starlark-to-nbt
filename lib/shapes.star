# Round shapes: discs, ellipses, cylinders, domes and spheres.
#
# Every shape rounds its radius to r + 0.5 (a cell is inside when
# dx*dx + dz*dz <= r*r + r). The plain `<= r*r` test leaves a lone
# one-block nub at each cardinal point; the half-block bias gives smooth
# outlines whose cardinal edges are at least three blocks wide.
#
# Footprints are (2*rx + 1) x (2*rz + 1) with the center cell at [rx, rz],
# so shapes are symmetric and rotation is a no-op. Rings and shells are
# the outer shape minus the shape `thickness` smaller, widened where needed
# so they stay watertight under face (4/6-neighbour) connectivity: water
# and mobs cannot leak through diagonal gaps.
#
# The *_cells helpers return [x, z] lists for custom shapes; *_runs
# helpers merge them into [x, z_min, z_max_exclusive] rows so one
# fill_region covers each row.


def _inside(dx, dy, dz, rx, ry, rz):
    """Biased ellipsoid test, exact in integers: (dx/(rx+.5))^2 + ... <= 1."""
    if rx < 0 or ry < 0 or rz < 0:
        return False
    a = 2 * rx + 1
    b = 2 * ry + 1
    c = 2 * rz + 1
    return 4 * (dx * dx * b * b * c * c + dy * dy * a * a * c * c + dz * dz * a * a * b * b) <= a * a * b * b * c * c


def ellipse_cells(rx, rz):
    """Cells [x, z] of a filled ellipse in a (2rx+1) x (2rz+1) footprint,
    centered at [rx, rz]."""
    return [[x, z] for x in range(2 * rx + 1) for z in range(2 * rz + 1)
            if _inside(x - rx, 0, z - rz, rx, 0, rz)]


def disc_cells(r):
    """Cells [x, z] of a filled disc in a (2r+1)-square footprint, centered
    at [r, r]. Offset by (R - r) to center it inside a radius-R shape."""
    return ellipse_cells(r, r)


def _erode(cells, steps):
    """Keys of `cells` (a {(x, z): True} dict) at least `steps` 4-neighbour
    moves from any outside cell."""
    for _ in range(steps):
        cells = {key: True for key in cells
                 if (key[0] + 1, key[1]) in cells and (key[0] - 1, key[1]) in cells
                 and (key[0], key[1] + 1) in cells and (key[0], key[1] - 1) in cells}
    return cells


def ellipse_ring_cells(rx, rz, thickness=1):
    """Cells [x, z] of an elliptical ring `thickness` blocks wide. Interior
    cells must sit inside the smaller ellipse *and* `thickness` face-steps
    in from the outer edge; the second test closes the diagonal gaps a plain
    difference leaves along the flat sides of eccentric ellipses."""
    outer = ellipse_cells(rx, rz)
    core = _erode({(c[0], c[1]): True for c in outer}, thickness)
    return [c for c in outer
            if not ((c[0], c[1]) in core
                    and _inside(c[0] - rx, 0, c[1] - rz, rx - thickness, 0, rz - thickness))]


def ring_cells(r, thickness=1):
    """Cells [x, z] of a circular ring `thickness` blocks wide, centered at [r, r]."""
    return ellipse_ring_cells(r, r, thickness)


def sphere_layer_cells(r, dy, thickness=None):
    """Cells [x, z] of a radius-r sphere's horizontal slice at height dy
    from its center. With `thickness`, only that slice of the shell."""
    cells = []
    for x in range(2 * r + 1):
        for z in range(2 * r + 1):
            if not _inside(x - r, dy, z - r, r, r, r):
                continue
            if thickness != None and _inside(x - r, dy, z - r, r - thickness, r - thickness, r - thickness):
                continue
            cells.append([x, z])
    return cells


def cell_runs(cells):
    """Merge [x, z] cells into [x, z_min, z_max_exclusive] rows. Cells must
    be ordered by x then z, as every *_cells helper returns them."""
    runs = []
    for cell in cells:
        if runs and runs[-1][0] == cell[0] and runs[-1][2] == cell[1]:
            runs[-1][2] = cell[1] + 1
        else:
            runs.append([cell[0], cell[1], cell[1] + 1])
    return runs


def fill_cells(cells, y_min, y_max, block_value, phase="structure"):
    """fill_region ops covering `cells` from y_min (inclusive) to y_max
    (exclusive), one op per row."""
    return [fill_region([run[0], y_min, run[1]], [run[0] + 1, y_max, run[2]], block_value, phase=phase)
            for run in cell_runs(cells)]


def _require(condition, message):
    if not condition:
        fail(message)


def _column(name, rx, rz, height, material, hollow, thickness, floor, props):
    _require(rx >= 1 and rz >= 1 and height >= 1, name + " requires radii >= 1 and height >= 1")
    _require(thickness >= 1, name + " requires thickness >= 1")
    _require(floor == None or hollow, name + " floor needs hollow=True")
    if hollow:
        parts = fill_cells(ellipse_ring_cells(rx, rz, thickness), 0, height, block(material))
        if floor != None and rx > thickness and rz > thickness:
            inner = [[c[0] + thickness, c[1] + thickness]
                     for c in ellipse_cells(rx - thickness, rz - thickness)]
            parts += fill_cells(inner, 0, 1, block(floor))
    else:
        parts = fill_cells(ellipse_cells(rx, rz), 0, height, block(material))
    return component(
        name=name,
        props=props,
        min_size=[2 * rx + 1, height, 2 * rz + 1],
        body=group(parts),
    )


def Disc(radius, material="minecraft:stone"):
    """Filled one-block-thick disc; footprint 2*radius+1."""
    _require(radius >= 1, "Disc requires radius >= 1")
    return component(
        name="Disc",
        props={"radius": radius, "material": material},
        min_size=[2 * radius + 1, 1, 2 * radius + 1],
        body=group(fill_cells(disc_cells(radius), 0, 1, block(material))),
    )


def Ellipse(rx, rz, material="minecraft:stone"):
    """Filled one-block-thick ellipse with half-axes rx (X) and rz (Z)."""
    _require(rx >= 1 and rz >= 1, "Ellipse requires rx >= 1 and rz >= 1")
    return component(
        name="Ellipse",
        props={"rx": rx, "rz": rz, "material": material},
        min_size=[2 * rx + 1, 1, 2 * rz + 1],
        body=group(fill_cells(ellipse_cells(rx, rz), 0, 1, block(material))),
    )


def Cylinder(radius, height, material="minecraft:stone_bricks", hollow=True, thickness=1, floor=None):
    """Round tower body. Hollow by default: a `thickness`-wide wall ring,
    optionally with a `floor` disc filling the interior at y=0."""
    return _column("Cylinder", radius, radius, height, material, hollow, thickness, floor,
                   {"radius": radius, "height": height, "material": material,
                    "hollow": hollow, "thickness": thickness, "floor": floor})


def EllipticCylinder(rx, rz, height, material="minecraft:stone_bricks", hollow=True, thickness=1, floor=None):
    """Oval tower body; same options as Cylinder."""
    return _column("EllipticCylinder", rx, rz, height, material, hollow, thickness, floor,
                   {"rx": rx, "rz": rz, "height": height, "material": material,
                    "hollow": hollow, "thickness": thickness, "floor": floor})


def _ball_layers(r, dys, material, hollow, thickness):
    parts = []
    for y in range(len(dys)):
        cells = sphere_layer_cells(r, dys[y], thickness if hollow else None)
        parts += fill_cells(cells, y, y + 1, block(material))
    return parts


def Dome(radius, material="minecraft:glass", hollow=True, thickness=1):
    """Upper hemisphere, radius+1 tall; its base ring matches a Cylinder of
    the same radius, so it caps a round tower or works as a round roof."""
    _require(radius >= 1 and thickness >= 1, "Dome requires radius >= 1 and thickness >= 1")
    return component(
        name="Dome",
        props={"radius": radius, "material": material, "hollow": hollow, "thickness": thickness},
        min_size=[2 * radius + 1, radius + 1, 2 * radius + 1],
        body=group(_ball_layers(radius, list(range(radius + 1)), material, hollow, thickness)),
    )


def Sphere(radius, material="minecraft:stone", hollow=True, thickness=1):
    """Full sphere in a (2*radius+1) cube."""
    _require(radius >= 1 and thickness >= 1, "Sphere requires radius >= 1 and thickness >= 1")
    return component(
        name="Sphere",
        props={"radius": radius, "material": material, "hollow": hollow, "thickness": thickness},
        min_size=[2 * radius + 1, 2 * radius + 1, 2 * radius + 1],
        body=group(_ball_layers(radius, list(range(-radius, radius + 1)), material, hollow, thickness)),
    )
