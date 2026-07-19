"""Aethercourt: a walkable 48 x 40 x 48 high-fantasy castle."""

load("../lib/outdoor.star", "Horse")


STONE = block("minecraft:stone_bricks")
MOSS = block("minecraft:mossy_stone_bricks")
FLOOR = block("minecraft:polished_diorite")
WOOD = block("minecraft:dark_oak_planks")
COPPER = block("minecraft:oxidized_copper")


def label(pos, text, facing="south"):
    return place_block(pos, block(
        "minecraft:dark_oak_wall_sign",
        {"facing": facing, "waterlogged": "false"},
        sign_nbt([text], color="light_blue", glowing=True),
    ), phase="fixture")


def tower(name, ox, oz):
    parts = []
    for y in range(1, 32):
        material = STONE
        if (y + ox + oz) % 7 == 0:
            material = MOSS
        for x in range(9):
            for z in range(9):
                if x == 0 or x == 8 or z == 0 or z == 8:
                    # Doorways and arrow slits make every deck useful.
                    slit = (y == 5 or y == 13 or y == 21) and (x == 4 or z == 4)
                    door = y <= 3 and ((x == 4 and (z == 0 or z == 8)) or (z == 4 and (x == 0 or x == 8)))
                    if not slit and not door:
                        parts.append(place_block([x, y, z], material))
    for y in [8, 16, 24, 31]:
        parts.append(fill_region([1, y, 1], [8, y + 1, 8], STONE))
        parts.append(carve_region([2, y, 2], [3, y + 1, 3]))
    parts.append(fill_region([2, 1, 2], [3, 31, 3], block("minecraft:ladder", {"facing": "east", "waterlogged": "false"}), phase="fixture"))
    for layer in range(5):
        parts.append(fill_region([layer, 32 + layer, layer], [9 - layer, 33 + layer, 9 - layer], COPPER))
    parts.append(fill_region([4, 37, 4], [5, 39, 5], block("minecraft:amethyst_block")))
    parts.append(place_block([4, 39, 4], block("minecraft:purple_banner", {"rotation": "0"}), phase="fixture"))
    return transform([ox, 0, oz], 0, [9, 40, 9], component(name, {}, group(parts), min_size=[9, 40, 9]))


def curtain_walls():
    parts = []
    # North/south runs, leaving the gatehouse frontage open in the south.
    for y in range(1, 15):
        for x in range(9, 39):
            for z in [0, 1]:
                parts.append(place_block([x, y, z], STONE))
            if x < 18 or x >= 30:
                for z in [39, 40]:
                    parts.append(place_block([x, y, z], STONE))
        for z in range(9, 39):
            for x in [0, 1, 46, 47]:
                parts.append(place_block([x, y, z], STONE))
    # Crenellations and inner parapets around two-wide walks.
    for x in range(9, 39, 2):
        parts.append(place_block([x, 15, 0], STONE))
        if x < 18 or x >= 30:
            parts.append(place_block([x, 15, 40], STONE))
    for z in range(9, 39, 2):
        parts.append(place_block([0, 15, z], STONE))
        parts.append(place_block([47, 15, z], STONE))
    return component("CurtainWalls", {}, group(parts), min_size=[48, 16, 48])


def gatehouse():
    parts = []
    # Shell and floors in [18,1,41]-[30,25,48].
    for y in range(1, 22):
        for x in range(18, 30):
            for z in range(41, 48):
                if x == 18 or x == 29 or z == 41 or z == 47:
                    parts.append(place_block([x, y, z], STONE))
    parts.append(fill_region([19, 9, 42], [29, 10, 47], STONE))
    parts.append(fill_region([19, 17, 42], [29, 18, 47], STONE))
    # Four-wide, six-high passage and inner doors.
    parts.append(carve_region([22, 1, 41], [26, 7, 48]))
    for x in range(22, 26):
        parts.append(place_block([x, 7, 42], block("minecraft:iron_bars"), phase="fixture"))
    for x in [22, 25]:
        parts.append(place_assembly([x, 1, 41], "gate door", [1, 2, 1], [
            {"pos": [0, 0, 0], "block": block("minecraft:dark_oak_door", {"facing": "south", "half": "lower", "hinge": "left", "open": "false", "powered": "false"})},
            {"pos": [0, 1, 0], "block": block("minecraft:dark_oak_door", {"facing": "south", "half": "upper", "hinge": "left", "open": "false", "powered": "false"})},
        ]))
    for x in range(18, 30, 2):
        parts.append(place_block([x, 22, 41], STONE))
        parts.append(place_block([x, 22, 47], STONE))
    parts.append(label([21, 8, 40], "AETHERCOURT", "south"))
    return component("GrandGatehouse", {}, group(parts), min_size=[48, 25, 48])


def palace():
    parts = []
    # Three floor plates and a tall perimeter. The central hall is double-height.
    for y in [1, 10, 19]:
        parts.append(fill_region([11, y, 9], [37, y + 1, 24], FLOOR))
    for y in range(2, 30):
        parts.append(fill_region([10, y, 8], [11, y + 1, 25], STONE))
        parts.append(fill_region([37, y, 8], [38, y + 1, 25], STONE))
        parts.append(fill_region([11, y, 8], [37, y + 1, 9], STONE))
        parts.append(fill_region([11, y, 24], [37, y + 1, 25], STONE))
    # Copper gable roof with crystal ridge and spire.
    for layer in range(9):
        parts.append(fill_region([10 + layer, 30 + layer, 8], [38 - layer, 31 + layer, 25], COPPER))
    parts.append(carve_region([23, 38, 15], [25, 40, 17]))
    parts.append(fill_region([23, 38, 15], [25, 40, 17], block("minecraft:amethyst_block"), phase="fixture"))
    # Entry, windows and throne-hall balcony opening.
    parts.append(carve_region([22, 2, 24], [26, 7, 25]))
    for x in [13, 18, 29, 34]:
        for y in [5, 14, 23]:
            parts.append(carve_region([x, y, 8], [x + 2, y + 3, 9]))
            parts.append(fill_region([x, y, 8], [x + 2, y + 3, 9], block("minecraft:cyan_stained_glass"), phase="fixture"))
    # Main carpet, throne, columns, galleries and twin stair cores.
    parts.append(fill_region([22, 2, 12], [26, 3, 24], block("minecraft:purple_carpet"), phase="fixture"))
    parts.append(fill_region([22, 2, 10], [26, 3, 12], block("minecraft:purpur_block"), phase="fixture"))
    parts.append(place_block([23, 3, 10], block("minecraft:gold_block"), phase="fixture"))
    for x in [13, 19, 28, 34]:
        parts.append(fill_region([x, 2, 12], [x + 1, 10, 13], block("minecraft:calcite")))
    for side in [12, 34]:
        for step in range(8):
            parts.append(place_block([side, 2 + step, 16 + step], block("minecraft:dark_oak_stairs", {"facing": "south", "half": "bottom", "shape": "straight", "waterlogged": "false"})))
    # Interior labels, guest rooms, library and council suite.
    labels = [
        ([22, 4, 23], "THRONE HALL"), ([11, 4, 13], "ROYAL ARMORY"),
        ([11, 13, 11], "GUEST AZURE"), ([11, 13, 15], "GUEST VIOLET"),
        ([36, 13, 11], "GUEST GOLD"), ([36, 13, 15], "GUEST JADE"),
        ([11, 22, 11], "ROYAL SUITE"), ([36, 22, 11], "LIBRARY"),
        ([36, 22, 18], "WAR COUNCIL"),
    ]
    for pos, text in labels:
        parts.append(label(pos, text))
    # Four deliberately stocked armory chests.
    stocks = [
        ["minecraft:diamond_sword", "minecraft:iron_sword", "minecraft:bow", "minecraft:crossbow", {"id": "minecraft:arrow", "count": 64}],
        ["minecraft:diamond_helmet", "minecraft:diamond_chestplate", "minecraft:iron_leggings", "minecraft:iron_boots", "minecraft:shield"],
        ["minecraft:saddle", "minecraft:lead", "minecraft:diamond_horse_armor", "minecraft:iron_horse_armor"],
        [{"id": "minecraft:torch", "count": 32}, {"id": "minecraft:bread", "count": 16}, {"id": "minecraft:cooked_beef", "count": 16}, "minecraft:apple"],
    ]
    for i in range(4):
        parts.append(place_block([12 + i, 2, 13], block("minecraft:chest", {"facing": "south", "type": "single", "waterlogged": "false"}, container_nbt(stocks[i])), phase="fixture"))
    # Beds, tables, shelves, dining/kitchen detail and chandeliers.
    for x, z, color in [(13, 11, "blue"), (13, 17, "purple"), (33, 11, "yellow"), (33, 17, "green")]:
        parts.append(place_block([x, 11, z], block("minecraft:%s_bed" % color, {"facing": "south", "part": "foot", "occupied": "false"}), phase="fixture"))
        parts.append(place_block([x, 11, z + 1], block("minecraft:%s_bed" % color, {"facing": "south", "part": "head", "occupied": "false"}), phase="fixture"))
        parts.append(place_block([x + 2, 11, z], block("minecraft:chest", {"facing": "south", "type": "single", "waterlogged": "false"}, container_nbt(["minecraft:book", "minecraft:apple"])), phase="fixture"))
    parts.append(fill_region([30, 20, 9], [37, 24, 10], block("minecraft:bookshelf")))
    parts.append(fill_region([13, 2, 20], [20, 3, 22], WOOD))
    parts.append(fill_region([29, 2, 20], [36, 3, 22], block("minecraft:smooth_stone")))
    for x in [18, 29]:
        parts.append(place_block([x, 8, 16], block("minecraft:chain"), phase="fixture"))
        parts.append(place_block([x, 7, 16], block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}), phase="fixture"))
    return component("RoyalPalace", {}, group(parts), min_size=[48, 40, 48])


def stable():
    parts = []
    # Open-front timber stable [10,1,28]-[21,13,41].
    parts.append(fill_region([10, 1, 28], [21, 2, 39], WOOD))
    for y in range(2, 9):
        parts.append(fill_region([10, y, 28], [11, y + 1, 39], WOOD))
        parts.append(fill_region([20, y, 28], [21, y + 1, 39], WOOD))
        parts.append(fill_region([11, y, 28], [20, y + 1, 29], WOOD))
    parts.append(fill_region([10, 9, 28], [21, 10, 39], block("minecraft:dark_oak_slab", {"type": "top", "waterlogged": "false"})))
    for x in [12, 14, 16, 18]:
        parts.append(fill_region([x, 2, 30], [x + 1, 4, 38], block("minecraft:dark_oak_fence"), phase="fixture"))
        parts.append(place_block([x, 2, 38], block("minecraft:dark_oak_fence_gate", {"facing": "south", "open": "false", "powered": "false", "in_wall": "false"}), phase="fixture"))
    parts.append(label([14, 5, 29], "ROYAL STABLES"))
    parts.append(place_block([11, 2, 29], block("minecraft:barrel", {"facing": "south", "open": "false"}, container_nbt(["minecraft:saddle", "minecraft:lead", "minecraft:wheat", "minecraft:apple"], id="minecraft:barrel")), phase="fixture"))
    for i in range(4):
        parts.append(transform([11 + i * 2, 2, 34], 0, [1, 2, 1], Horse(variant=i * 256, tame=True)))
    return component("RoyalStables", {}, group(parts), min_size=[48, 13, 48])


def courtyard():
    parts = []
    # Avenue and cross paths replace the grass foundation explicitly.
    parts.append(carve_region([22, 0, 25], [26, 1, 48]))
    parts.append(fill_region([22, 0, 25], [26, 1, 48], block("minecraft:polished_andesite"), phase="fixture"))
    parts.append(carve_region([10, 0, 34], [39, 1, 38]))
    parts.append(fill_region([10, 0, 34], [22, 1, 38], block("minecraft:polished_andesite"), phase="fixture"))
    parts.append(fill_region([26, 0, 34], [39, 1, 38], block("minecraft:polished_andesite"), phase="fixture"))
    # Fountain, gardens, benches, tree and training targets.
    parts.append(fill_region([32, 1, 32], [37, 2, 37], block("minecraft:amethyst_block")))
    parts.append(carve_region([33, 1, 33], [36, 2, 36]))
    parts.append(fill_region([34, 2, 34], [35, 7, 35], block("minecraft:amethyst_block")))
    parts.append(place_block([34, 7, 34], block("minecraft:sea_lantern"), phase="fixture"))
    for x, z, flower in [(30, 30, "minecraft:allium"), (38, 30, "minecraft:azure_bluet"), (32, 30, "minecraft:blue_orchid"), (36, 30, "minecraft:poppy")]:
        parts.append(place_block([x, 1, z], block(flower), phase="fixture"))
    for x, z in [(30, 32), (38, 32), (30, 37), (38, 37)]:
        parts.append(fill_region([x, 1, z], [x + 1, 5, z + 1], block("minecraft:dark_oak_log", {"axis": "y"})))
        parts.append(fill_region([x - 1, 5, z - 1], [x + 2, 7, z + 2], block("minecraft:azalea_leaves", {"persistent": "true", "waterlogged": "false"})))
    parts.append(place_block([31, 2, 38], block("minecraft:target", {"power": "0"}), phase="fixture"))
    return component("EastCourtyard", {}, group(parts), min_size=[48, 12, 48])


def build():
    return component(
        name="AethercourtMegaCastle",
        props={},
        min_size=[48, 40, 48],
        metadata={"ground_level": 1},
        body=group([
            fill_region([0, 0, 0], [48, 1, 48], block("minecraft:grass_block")),
            tower("NorthwestTower", 0, 0), tower("NortheastTower", 39, 0),
            tower("SouthwestTower", 0, 39), tower("SoutheastTower", 39, 39),
            curtain_walls(), gatehouse(), palace(), stable(), courtyard(),
        ]),
    )
