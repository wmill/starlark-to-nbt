# Interior fixtures and furniture. Everything here is FIXTURE-phase (or an
# assembly), so it must be placed into empty or carved space — fixtures refuse
# to overwrite solid structure blocks.


def Bench(length, stair="minecraft:oak_stairs"):
    """Row of stairs facing +Z (south)."""
    return component(
        name="Bench",
        props={"length": length, "stair": stair},
        min_size=[length, 1, 1],
        body=group([
            place_block([x, 0, 0],
                        block(stair, {"facing": "south", "half": "bottom", "shape": "straight"}),
                        phase="fixture")
            for x in range(length)
        ]),
    )


def Chair(stair="minecraft:oak_stairs"):
    """Single stair seat facing +Z (south)."""
    return component(
        name="Chair",
        props={"stair": stair},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(stair, {"facing": "south", "half": "bottom", "shape": "straight"}),
                         phase="fixture"),
    )


def Table(leg="minecraft:oak_fence", top="minecraft:oak_pressure_plate"):
    """Classic fence-and-pressure-plate table, 1x2x1."""
    return component(
        name="Table",
        props={"leg": leg, "top": top},
        min_size=[1, 2, 1],
        body=group([
            place_block([0, 0, 0], block(leg), phase="fixture"),
            place_block([0, 1, 0], block(top), phase="fixture"),
        ]),
    )


def Bed(material="minecraft:red_bed"):
    """Two-part bed assembly; head toward +Z (south)."""
    return component(
        name="Bed",
        props={"material": material},
        min_size=[1, 1, 2],
        body=place_assembly(
            pos=[0, 0, 0],
            name="bed",
            size=[1, 1, 2],
            blocks=[
                {"pos": [0, 0, 0], "block": block(material, {"facing": "south", "part": "foot", "occupied": "false"})},
                {"pos": [0, 0, 1], "block": block(material, {"facing": "south", "part": "head", "occupied": "false"})},
            ],
        ),
    )


def BookshelfWall(width, height, material="minecraft:bookshelf"):
    """Bank of bookshelves stood against a wall."""
    return component(
        name="BookshelfWall",
        props={"width": width, "height": height, "material": material},
        min_size=[width, height, 1],
        body=fill_region([0, 0, 0], [width, height, 1], block(material), phase="fixture"),
    )


def Fireplace(height=5, material="minecraft:stone_bricks", fire="minecraft:campfire"):
    """Hearth with lintel, lit campfire, and a chimney rising to `height`."""
    return component(
        name="Fireplace",
        props={"height": height, "material": material, "fire": fire},
        min_size=[3, height, 1],
        body=group([
            fill_region([0, 0, 0], [1, 2, 1], block(material)),
            fill_region([2, 0, 0], [3, 2, 1], block(material)),
            fill_region([0, 2, 0], [3, 3, 1], block(material)),
            fill_region([1, 3, 0], [2, height, 1], block(material)),
            place_block([1, 0, 0],
                        block(fire, {"lit": "true", "facing": "south", "signal_fire": "false", "waterlogged": "false"}),
                        phase="fixture"),
        ]),
    )


def LanternPost(height=3, post="minecraft:oak_fence", lantern="minecraft:lantern"):
    """Fence post with a lantern on top; total height is `height` + 1."""
    return component(
        name="LanternPost",
        props={"height": height, "post": post, "lantern": lantern},
        min_size=[1, height + 1, 1],
        body=group([
            fill_region([0, 0, 0], [1, height, 1], block(post), phase="fixture"),
            place_block([0, height, 0], block(lantern, {"hanging": "false", "waterlogged": "false"}),
                        phase="fixture"),
        ]),
    )


def Carpet(width, length, material="minecraft:red_carpet"):
    """Fixture-phase carpet layer over an existing floor."""
    return component(
        name="Carpet",
        props={"width": width, "length": length, "material": material},
        min_size=[width, 1, length],
        body=fill_region([0, 0, 0], [width, 1, length], block(material), phase="fixture"),
    )
