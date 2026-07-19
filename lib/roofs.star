# Roofs. All roofs sit on y=0 of their own region; place them above the walls
# with transform(). Gable and shed roofs slope along +X; the ridge runs along +Z.


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
