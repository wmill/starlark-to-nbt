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


def Chest(items=None, loot=None, material="minecraft:chest"):
    """Single chest facing +Z (south). `items` preloads slots (item ids or
    {"id", "count", "slot"} dicts); `loot` names a loot table rolled on first open."""
    if loot != None:
        nbt = loot_nbt(loot, id=material)
    else:
        nbt = container_nbt(items, id=material)
    return component(
        name="Chest",
        props={"items": items or [], "loot": loot, "material": material},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"facing": "south", "type": "single", "waterlogged": "false"}, nbt=nbt),
                         phase="fixture"),
    )


def Barrel(items=None, loot=None, material="minecraft:barrel"):
    """Barrel facing +Z (south); same item/loot props as Chest."""
    if loot != None:
        nbt = loot_nbt(loot, id=material)
    else:
        nbt = container_nbt(items, id=material)
    return component(
        name="Barrel",
        props={"items": items or [], "loot": loot, "material": material},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"facing": "south", "open": "false"}, nbt=nbt),
                         phase="fixture"),
    )


def Furnace(items=None, material="minecraft:furnace"):
    """Unlit furnace facing +Z (south); `items` slots are 0 input, 1 fuel, 2 output."""
    return component(
        name="Furnace",
        props={"items": items or [], "material": material},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"facing": "south", "lit": "false"},
                               nbt=container_nbt(items, id=material)),
                         phase="fixture"),
    )


def Sign(lines=None, material="minecraft:oak_sign", color="black", glowing=False):
    """Standing sign facing +Z (south); `lines` is up to four strings of front text."""
    if lines == None:
        lines = ["Sign"]
    return component(
        name="Sign",
        props={"lines": lines, "material": material, "color": color, "glowing": glowing},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"rotation": "0", "waterlogged": "false"},
                               nbt=sign_nbt(lines, color=color, glowing=glowing)),
                         phase="fixture"),
    )


def WallSign(lines=None, material="minecraft:oak_wall_sign", color="black", glowing=False):
    """Wall sign attached to a north support, facing +Z (south)."""
    if lines == None:
        lines = ["Sign"]
    return component(
        name="WallSign",
        props={"lines": lines, "material": material, "color": color, "glowing": glowing},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"facing": "south", "waterlogged": "false"},
                               nbt=sign_nbt(lines, color=color, glowing=glowing)),
                         phase="fixture"),
    )


def Carpet(width, length, material="minecraft:red_carpet"):
    """Fixture-phase carpet layer over an existing floor."""
    return component(
        name="Carpet",
        props={"width": width, "length": length, "material": material},
        min_size=[width, 1, length],
        body=fill_region([0, 0, 0], [width, 1, length], block(material), phase="fixture"),
    )


def Ladder(height, material="minecraft:ladder"):
    """Vertical ladder attached to a north support, facing +Z (south)."""
    return component(
        name="Ladder",
        props={"height": height, "material": material},
        min_size=[1, height, 1],
        body=fill_region([0, 0, 0], [1, height, 1],
                         block(material, {"facing": "south", "waterlogged": "false"}),
                         phase="fixture"),
    )


def DiningTable(length=3, leg="minecraft:oak_fence", top="minecraft:oak_slab"):
    """Long table running +X, with end legs and a bottom-slab top."""
    return component(
        name="DiningTable",
        props={"length": length, "leg": leg, "top": top},
        min_size=[length, 2, 1],
        body=group([
            place_block([0, 0, 0], block(leg), phase="fixture"),
            place_block([length - 1, 0, 0], block(leg), phase="fixture"),
            fill_region([0, 1, 0], [length, 2, 1],
                        block(top, {"type": "bottom", "waterlogged": "false"}), phase="fixture"),
        ]),
    )


def KitchenCounter(length=3, cabinet="minecraft:barrel", top="minecraft:oak_slab"):
    """South-facing storage run with a bottom-slab worktop."""
    return component(
        name="KitchenCounter",
        props={"length": length, "cabinet": cabinet, "top": top},
        min_size=[length, 2, 1],
        body=group([
            fill_region([0, 0, 0], [length, 1, 1], block(cabinet, {"facing": "south", "open": "false"}),
                        phase="fixture"),
            fill_region([0, 1, 0], [length, 2, 1],
                        block(top, {"type": "bottom", "waterlogged": "false"}), phase="fixture"),
        ]),
    )
