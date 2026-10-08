# Roofs. All roofs sit on y=0 of their own region; place them above the walls
# with transform(). Gable and shed roofs slope along +X; the ridge runs along +Z.
# Round roofs (ConeRoof, and Dome in shapes.star) share Cylinder's footprint.

load("shapes.star", "ring_cells")


def GableRoof(width, length, stair="minecraft:oak_stairs", ridge="minecraft:oak_planks", gable=None):
    """Two opposed stair slopes meeting at a ridge, with the triangular gable
    ends closed in `gable` material (defaults to `ridge`). Height is
    (width+1)//2."""
    if gable == None:
        gable = ridge
    half = width // 2
    rows = []
    for i in range(half):
        rows.append(fill_region([i, i, 0], [i + 1, i + 1, length],
                                block(stair, {"facing": "east", "half": "bottom", "shape": "straight"})))
        rows.append(fill_region([width - 1 - i, i, 0], [width - i, i + 1, length],
                                block(stair, {"facing": "west", "half": "bottom", "shape": "straight"})))
        if i + 1 < width - 1 - i:
            for z in [0, length - 1]:
                rows.append(fill_region([i + 1, i, z], [width - 1 - i, i + 1, z + 1], block(gable)))
    if width % 2 == 1:
        rows.append(fill_region([half, half, 0], [half + 1, half + 1, length], block(ridge)))
    return component(
        name="GableRoof",
        props={"width": width, "length": length, "stair": stair, "ridge": ridge, "gable": gable},
        min_size=[width, (width + 1) // 2, length],
        body=group(rows),
    )


def ShedRoof(width, length, stair="minecraft:oak_stairs"):
    """Single 45-degree slope ascending toward +X."""
    rows = []
    for i in range(width):
        rows.append(fill_region([i, i, 0], [i + 1, i + 1, length],
                                block(stair, {"facing": "east", "half": "bottom", "shape": "straight"})))
    return component(
        name="ShedRoof",
        props={"width": width, "length": length, "stair": stair},
        min_size=[width, width, length],
        body=group(rows),
    )


def FlatRoof(width, length, slab="minecraft:oak_slab", trim="minecraft:oak_fence"):
    """Slab deck with a fence parapet around the rim."""
    ew = block(trim, {"east": "true", "west": "true"})
    ns = block(trim, {"north": "true", "south": "true"})
    return component(
        name="FlatRoof",
        props={"width": width, "length": length, "slab": slab, "trim": trim},
        min_size=[width, 2, length],
        body=group([
            fill_region([0, 0, 0], [width, 1, length], block(slab, {"type": "bottom", "waterlogged": "false"})),
            fill_region([0, 1, 0], [width, 2, 1], ew, phase="fixture"),
            fill_region([0, 1, length - 1], [width, 2, length], ew, phase="fixture"),
            fill_region([0, 1, 1], [1, 2, length - 1], ns, phase="fixture"),
            fill_region([width - 1, 1, 1], [width, 2, length - 1], ns, phase="fixture"),
        ]),
    )


def PyramidRoof(size, stair="minecraft:oak_stairs", cap="minecraft:oak_planks"):
    """Square pyramid of concentric stair rings; `size` is the square footprint."""
    parts = []
    levels = size // 2
    for i in range(levels):
        low = i
        high = size - i
        parts.append(fill_region([low, i, low], [high, i + 1, low + 1],
                                 block(stair, {"facing": "south", "half": "bottom", "shape": "straight"})))
        parts.append(fill_region([low, i, high - 1], [high, i + 1, high],
                                 block(stair, {"facing": "north", "half": "bottom", "shape": "straight"})))
        if high - 1 > low + 1:
            parts.append(fill_region([low, i, low + 1], [low + 1, i + 1, high - 1],
                                     block(stair, {"facing": "east", "half": "bottom", "shape": "straight"})))
            parts.append(fill_region([high - 1, i, low + 1], [high, i + 1, high - 1],
                                     block(stair, {"facing": "west", "half": "bottom", "shape": "straight"})))
    if size % 2 == 1:
        parts.append(place_block([levels, levels, levels], block(cap)))
    return component(
        name="PyramidRoof",
        props={"size": size, "stair": stair, "cap": cap},
        min_size=[size, (size + 1) // 2, size],
        body=group(parts),
    )


def _stair(material, facing, shape="straight"):
    return block(material, {"facing": facing, "half": "bottom", "shape": shape})


def HipRoof(width, length, stair="minecraft:oak_stairs", ridge="minecraft:oak_planks"):
    """Four slopes rising from every eave to a ridge along the longer axis (a
    single cap block when square and odd). Corner stairs carry explicit
    outer shapes, since pasted structures do not recompute stair shapes.
    Height is (min(width, length)+1)//2."""
    if width < 2 or length < 2:
        fail("HipRoof requires width >= 2 and length >= 2")
    short = min(width, length)
    levels = short // 2
    parts = []
    for i in range(levels):
        x0, x1 = i, width - 1 - i
        z0, z1 = i, length - 1 - i
        parts.append(place_block([x0, i, z0], _stair(stair, "south", "outer_left")))
        parts.append(place_block([x1, i, z0], _stair(stair, "south", "outer_right")))
        parts.append(place_block([x0, i, z1], _stair(stair, "north", "outer_right")))
        parts.append(place_block([x1, i, z1], _stair(stair, "north", "outer_left")))
        if x1 - x0 > 1:
            parts.append(fill_region([x0 + 1, i, z0], [x1, i + 1, z0 + 1], _stair(stair, "south")))
            parts.append(fill_region([x0 + 1, i, z1], [x1, i + 1, z1 + 1], _stair(stair, "north")))
        if z1 - z0 > 1:
            parts.append(fill_region([x0, i, z0 + 1], [x0 + 1, i + 1, z1], _stair(stair, "east")))
            parts.append(fill_region([x1, i, z0 + 1], [x1 + 1, i + 1, z1], _stair(stair, "west")))
    if short % 2 == 1:
        parts.append(fill_region([levels, levels, levels], [width - levels, levels + 1, length - levels],
                                 block(ridge)))
    return component(
        name="HipRoof",
        props={"width": width, "length": length, "stair": stair, "ridge": ridge},
        min_size=[width, (short + 1) // 2, length],
        body=group(parts),
    )


def ConeRoof(radius, stair="minecraft:oak_stairs", cap="minecraft:oak_planks", steep=False):
    """Round stair cone over a (2*radius+1) footprint, matching a Cylinder of
    the same radius. Each layer is a one-block ring that steps in by one
    (every two layers when steep=True); stairs face the axis, diagonal ring
    cells are full `cap` blocks, and a `cap` block closes the apex. Height
    is radius+1 (2*radius+1 when steep)."""
    if radius < 1:
        fail("ConeRoof requires radius >= 1")
    step = 2 if steep else 1
    layers = radius * step + 1
    parts = []
    for y in range(layers):
        r = radius - y // step
        if r == 0:
            parts.append(place_block([radius, y, radius], block(cap)))
            continue
        for cell in ring_cells(r):
            dx, dz = cell[0] - r, cell[1] - r
            ax = dx if dx >= 0 else -dx
            az = dz if dz >= 0 else -dz
            if ax == az:
                value = block(cap)
            elif ax > az:
                value = _stair(stair, "east" if dx < 0 else "west")
            else:
                value = _stair(stair, "south" if dz < 0 else "north")
            parts.append(place_block([radius + dx, y, radius + dz], value))
    return component(
        name="ConeRoof",
        props={"radius": radius, "stair": stair, "cap": cap, "steep": steep},
        min_size=[2 * radius + 1, layers, 2 * radius + 1],
        body=group(parts),
    )
