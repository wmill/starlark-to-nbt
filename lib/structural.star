# Structural components: foundations, floors, walls, columns, balconies.
# All components draw in local coordinates from [0, 0, 0]; walls run along +X
# with a thickness of 1 in Z. Use transform() to rotate them into place.


def Foundation(width, length, depth=1, material="minecraft:cobblestone"):
    """Solid pad of `material`, `depth` blocks tall."""
    return component(
        name="Foundation",
        props={"width": width, "length": length, "depth": depth, "material": material},
        min_size=[width, depth, length],
        body=fill_region([0, 0, 0], [width, depth, length], block(material)),
    )


def Floor(width, length, material="minecraft:oak_planks"):
    """Single-layer floor slab."""
    return component(
        name="Floor",
        props={"width": width, "length": length, "material": material},
        min_size=[width, 1, length],
        body=fill_region([0, 0, 0], [width, 1, length], block(material)),
    )


def SolidWall(width, height, material="minecraft:stone_bricks"):
    """Wall running along +X, one block thick."""
    return component(
        name="SolidWall",
        props={"width": width, "height": height, "material": material},
        min_size=[width, height, 1],
        body=fill_region([0, 0, 0], [width, height, 1], block(material)),
    )


def WindowedWall(width, height, spacing=3, material="minecraft:stone_bricks", pane="minecraft:glass_pane"):
    """Wall along +X with 1x2 window openings every `spacing` blocks.

    Requires width >= 5 and height >= 4 so every window keeps a solid border.
    """
    sill = height // 3
    if sill < 1:
        sill = 1
    parts = [fill_region([0, 0, 0], [width, height, 1], block(material))]
    for x in range(2, width - 2, spacing):
        parts.append(carve_region([x, sill, 0], [x + 1, sill + 2, 1]))
        parts.append(fill_region(
            [x, sill, 0], [x + 1, sill + 2, 1],
            block(pane, {"east": "true", "west": "true"}),
            phase="fixture",
        ))
    return component(
        name="WindowedWall",
        props={"width": width, "height": height, "spacing": spacing, "material": material},
        min_size=[width, height, 1],
        body=group(parts),
    )


def TimberFrameWall(width, height, log="minecraft:oak_log", infill="minecraft:white_terracotta"):
    """Wall along +X with vertical log posts, horizontal log beams, plaster infill."""
    return component(
        name="TimberFrameWall",
        props={"width": width, "height": height, "log": log, "infill": infill},
        min_size=[width, height, 1],
        body=group([
            fill_region([0, 0, 0], [1, height, 1], block(log, {"axis": "y"})),
            fill_region([width - 1, 0, 0], [width, height, 1], block(log, {"axis": "y"})),
            fill_region([1, 0, 0], [width - 1, 1, 1], block(log, {"axis": "x"})),
            fill_region([1, height - 1, 0], [width - 1, height, 1], block(log, {"axis": "x"})),
            fill_region([1, 1, 0], [width - 1, height - 1, 1], block(infill)),
        ]),
    )


def Column(height, material="minecraft:quartz_pillar"):
    """1x1 vertical column; pillar materials keep their axis under rotation."""
    return component(
        name="Column",
        props={"height": height, "material": material},
        min_size=[1, height, 1],
        body=fill_region([0, 0, 0], [1, height, 1], block(material, {"axis": "y"})),
    )


def Balcony(width, depth=2, material="minecraft:oak_planks", railing="minecraft:oak_fence"):
    """Platform with fence railing on the front (+Z) and side edges."""
    rail = block(railing, {"north": "true", "south": "true"})
    front_rail = block(railing, {"east": "true", "west": "true"})
    return component(
        name="Balcony",
        props={"width": width, "depth": depth, "material": material, "railing": railing},
        min_size=[width, 2, depth],
        body=group([
            fill_region([0, 0, 0], [width, 1, depth], block(material)),
            fill_region([0, 1, depth - 1], [width, 2, depth], front_rail, phase="fixture"),
            fill_region([0, 1, 0], [1, 2, depth - 1], rail, phase="fixture"),
            fill_region([width - 1, 1, 0], [width, 2, depth - 1], rail, phase="fixture"),
        ]),
    )
