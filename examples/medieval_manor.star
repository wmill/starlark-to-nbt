"""A furnished 20 x 18 x 18 medieval manor inspired by training sample 1340."""

load("../lib/structural.star", "StraightStaircase", "TimberFrameWall")
load("../lib/openings.star", "DoubleDoor", "ShutteredWindow", "Window")
load(
    "../lib/fixtures.star",
    "Bed",
    "BookshelfWall",
    "Chair",
    "Chest",
    "DiningTable",
    "Furnace",
    "KitchenCounter",
    "Table",
)


WIDTH = 20
HEIGHT = 18
LENGTH = 18

STONE = block("minecraft:stone_bricks")
OAK = block("minecraft:oak_planks")
OAK_LOG = block("minecraft:oak_log", {"axis": "y"})
PLASTER = block("minecraft:birch_planks")
ROOF = block("minecraft:white_wool")


def ManorFloors():
    """Floor plates with holes reserved for the two stair flights."""
    parts = [
        # Ground floor and three-piece first floor around the lower stairwell.
        fill_region([3, 0, 2], [17, 1, 16], OAK),
        fill_region([4, 4, 3], [16, 5, 5], OAK),
        fill_region([4, 4, 5], [10, 5, 9], OAK),
        fill_region([12, 4, 5], [16, 5, 9], OAK),
        fill_region([4, 4, 9], [16, 5, 15], OAK),
        # The loft floor similarly leaves the upper flight and its emergence open.
        fill_region([3, 9, 4], [17, 10, 9], block("minecraft:oak_slab", {"type": "top", "waterlogged": "false"})),
        fill_region([3, 9, 9], [10, 10, 14], block("minecraft:oak_slab", {"type": "top", "waterlogged": "false"})),
        fill_region([12, 9, 9], [17, 10, 14], block("minecraft:oak_slab", {"type": "top", "waterlogged": "false"})),
        fill_region([3, 9, 14], [17, 10, 15], block("minecraft:oak_slab", {"type": "top", "waterlogged": "false"})),
        # Stair flights finish beside intact landing rows.
        transform([10, 1, 5], 0, [2, 4, 4], StraightStaircase(2, 4)),
        transform([10, 5, 9], 0, [2, 5, 5], StraightStaircase(2, 5)),
    ]
    return component(name="ManorFloors", props={}, min_size=[WIDTH, 14, LENGTH], body=group(parts))


def GroundStorey():
    parts = [
        fill_region([3, 1, 2], [17, 4, 3], STONE),
        fill_region([3, 1, 15], [17, 4, 16], STONE),
        fill_region([3, 1, 3], [4, 4, 15], STONE),
        fill_region([16, 1, 3], [17, 4, 15], STONE),
        # Broad west entrance and paired windows on every other face.
        transform([3, 1, 8], 90, [2, 2, 1], DoubleDoor()),
        transform([3, 1, 4], 90, [3, 2, 1], ShutteredWindow()),
        transform([3, 1, 11], 90, [3, 2, 1], ShutteredWindow()),
        transform([16, 1, 4], 270, [3, 2, 1], ShutteredWindow()),
        transform([16, 1, 11], 270, [3, 2, 1], ShutteredWindow()),
        transform([5, 1, 2], 180, [3, 2, 1], ShutteredWindow()),
        transform([12, 1, 2], 180, [3, 2, 1], ShutteredWindow()),
        transform([5, 1, 15], 0, [3, 2, 1], ShutteredWindow()),
        transform([12, 1, 15], 0, [3, 2, 1], ShutteredWindow()),
    ]
    return component(name="StoneGroundStorey", props={}, min_size=[WIDTH, 4, LENGTH], body=group(parts))


def UpperStorey():
    parts = [
        transform([3, 5, 2], 0, [14, 4, 1], TimberFrameWall(14, 4, log="minecraft:oak_log", infill="minecraft:birch_planks")),
        transform([3, 5, 15], 180, [14, 4, 1], TimberFrameWall(14, 4, log="minecraft:oak_log", infill="minecraft:birch_planks")),
        transform([3, 5, 3], 90, [12, 4, 1], TimberFrameWall(12, 4, log="minecraft:oak_log", infill="minecraft:birch_planks")),
        transform([16, 5, 3], 270, [12, 4, 1], TimberFrameWall(12, 4, log="minecraft:oak_log", infill="minecraft:birch_planks")),
        transform([3, 6, 6], 90, [3, 2, 1], ShutteredWindow()),
        transform([3, 6, 11], 90, [3, 2, 1], ShutteredWindow()),
        transform([16, 6, 6], 270, [3, 2, 1], ShutteredWindow()),
        transform([16, 6, 11], 270, [3, 2, 1], ShutteredWindow()),
        transform([5, 6, 2], 180, [3, 2, 1], ShutteredWindow()),
        transform([12, 6, 2], 180, [3, 2, 1], ShutteredWindow()),
        transform([5, 6, 15], 0, [3, 2, 1], ShutteredWindow()),
        transform([12, 6, 15], 0, [3, 2, 1], ShutteredWindow()),
    ]
    return component(name="TimberUpperStorey", props={}, min_size=[WIDTH, 9, LENGTH], body=group(parts))


def DecorativeRoof():
    """Stepped white roof planes with oak bargeboards and glazed end gables."""
    parts = []
    for layer in range(8):
        north = layer
        south = LENGTH - 1 - layer
        parts.append(fill_region([2, layer, north], [18, layer + 1, north + 1], ROOF))
        parts.append(fill_region([2, layer, south], [18, layer + 1, south + 1], ROOF))
        parts.append(place_block([1, layer, north], OAK))
        parts.append(place_block([18, layer, north], OAK))
        parts.append(place_block([1, layer, south], OAK))
        parts.append(place_block([18, layer, south], OAK))
        # Filled end gables make the attic read as a full storey from east/west.
        parts.append(fill_region([2, layer, north + 1], [3, layer + 1, south], ROOF))
        parts.append(fill_region([17, layer, north + 1], [18, layer + 1, south], ROOF))

    ridge = block("minecraft:oak_slab", {"type": "top", "waterlogged": "false"})
    parts.append(fill_region([1, 8, 8], [19, 9, 10], ridge))

    # Carve framed two-by-two windows through both solid gable ends.
    for x in [2, 17]:
        parts.append(carve_region([x, 2, 7], [x + 1, 6, 11]))
        parts.append(fill_region([x, 3, 8], [x + 1, 5, 10], block("minecraft:glass"), phase="fixture"))
        parts.append(fill_region([x, 2, 7], [x + 1, 3, 11], OAK, phase="fixture"))
        parts.append(fill_region([x, 5, 7], [x + 1, 6, 11], OAK, phase="fixture"))
        parts.append(fill_region([x, 3, 7], [x + 1, 5, 8], OAK, phase="fixture"))
        parts.append(fill_region([x, 3, 10], [x + 1, 5, 11], OAK, phase="fixture"))

    return component(name="DecorativeRoof", props={}, min_size=[WIDTH, 9, LENGTH], body=group(parts))


def GroundFloorInterior():
    parts = [
        # Smithy and kitchen occupy the north half, echoing the dense original workshop.
        transform([4, 1, 3], 0, [1, 1, 1], Furnace(["minecraft:iron_ore", "minecraft:coal"])),
        transform([6, 1, 3], 0, [1, 1, 1], Furnace(["minecraft:raw_copper", "minecraft:coal"])),
        place_block([8, 1, 3], block("minecraft:anvil", {"facing": "east"}), phase="fixture"),
        place_block([4, 1, 5], block("minecraft:crafting_table"), phase="fixture"),
        place_block([6, 1, 5], block("minecraft:cauldron", {"level": "3"}), phase="fixture"),
        place_block([8, 1, 5], block("minecraft:brewing_stand", {"has_bottle_0": "false", "has_bottle_1": "false", "has_bottle_2": "false"}), phase="fixture"),
        transform([4, 1, 13], 180, [5, 2, 1], KitchenCounter(5)),
        # Dining nook, bedroom, storage, and enchanting study fill the south/east rooms.
        transform([12, 1, 5], 0, [3, 2, 1], DiningTable(3)),
        transform([12, 1, 4], 180, [1, 1, 1], Chair()),
        transform([14, 1, 6], 0, [1, 1, 1], Chair()),
        transform([14, 1, 9], 0, [1, 1, 2], Bed()),
        transform([15, 1, 9], 0, [1, 1, 2], Bed()),
        transform([12, 1, 13], 180, [1, 1, 1], Chest(["minecraft:book", "minecraft:bread", "minecraft:apple"])),
        transform([14, 1, 13], 180, [1, 1, 1], Chest(["minecraft:iron_ingot", "minecraft:gold_ingot", "minecraft:emerald"])),
        place_block([15, 1, 12], block("minecraft:enchanting_table"), phase="fixture"),
        transform([9, 1, 14], 180, [5, 2, 1], BookshelfWall(5, 2)),
        # Small tables and ceiling lamps keep the large open plan legible in-game.
        transform([5, 1, 10], 0, [1, 2, 1], Table()),
        transform([7, 1, 10], 0, [1, 2, 1], Table()),
        place_block([6, 3, 8], block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}), phase="fixture"),
        place_block([13, 3, 8], block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}), phase="fixture"),
    ]
    return component(name="GroundFloorInterior", props={}, min_size=[WIDTH, 4, LENGTH], body=group(parts))


def UpperFloorInterior():
    parts = [
        transform([4, 5, 3], 0, [5, 2, 1], BookshelfWall(5, 2)),
        transform([4, 5, 5], 0, [1, 1, 2], Bed("minecraft:green_bed")),
        transform([5, 5, 5], 0, [1, 1, 2], Bed("minecraft:green_bed")),
        transform([14, 5, 4], 180, [1, 1, 2], Bed("minecraft:red_bed")),
        transform([15, 5, 4], 180, [1, 1, 2], Bed("minecraft:red_bed")),
        transform([4, 5, 12], 0, [4, 2, 1], DiningTable(4)),
        transform([4, 5, 11], 180, [1, 1, 1], Chair()),
        transform([7, 5, 13], 0, [1, 1, 1], Chair()),
        transform([14, 5, 12], 180, [1, 1, 1], Chest(["minecraft:map", "minecraft:compass", "minecraft:clock"])),
        place_block([6, 7, 9], block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}), phase="fixture"),
        place_block([14, 7, 9], block("minecraft:lantern", {"hanging": "true", "waterlogged": "false"}), phase="fixture"),
        # Loft storage is accessible from the upper stair landing.
        transform([5, 10, 7], 0, [1, 1, 1], Chest(["minecraft:paper", "minecraft:book", "minecraft:candle"])),
        transform([14, 10, 10], 180, [1, 1, 1], Chest(["minecraft:wheat", "minecraft:leather", "minecraft:string"])),
    ]
    return component(name="UpperFloorInterior", props={}, min_size=[WIDTH, 11, LENGTH], body=group(parts))


def build():
    site = [
        fill_region([0, 0, 0], [WIDTH, 1, 2], block("minecraft:grass_block")),
        fill_region([0, 0, 16], [WIDTH, 1, LENGTH], block("minecraft:grass_block")),
        fill_region([0, 0, 2], [3, 1, 8], block("minecraft:grass_block")),
        fill_region([0, 0, 10], [3, 1, 16], block("minecraft:grass_block")),
        fill_region([17, 0, 2], [WIDTH, 1, 16], block("minecraft:grass_block")),
        fill_region([0, 0, 8], [3, 1, 10], block("minecraft:gravel")),
        # Exterior timber posts and flower boxes soften the rectangular shell.
        fill_region([2, 1, 3], [3, 5, 4], OAK_LOG),
        fill_region([2, 1, 14], [3, 5, 15], OAK_LOG),
        fill_region([17, 1, 3], [18, 5, 4], OAK_LOG),
        fill_region([17, 1, 14], [18, 5, 15], OAK_LOG),
        place_block([2, 1, 6], block("minecraft:oak_fence"), phase="fixture"),
        place_block([2, 1, 11], block("minecraft:oak_fence"), phase="fixture"),
        place_block([17, 1, 6], block("minecraft:oak_fence"), phase="fixture"),
        place_block([17, 1, 11], block("minecraft:oak_fence"), phase="fixture"),
        place_block([1, 1, 7], block("minecraft:poppy"), phase="fixture"),
        place_block([1, 1, 10], block("minecraft:dandelion"), phase="fixture"),
    ]
    return component(
        name="MedievalManor",
        props={},
        min_size=[WIDTH, HEIGHT, LENGTH],
        metadata={"ground_level": 1},
        body=group(site + [
            ManorFloors(),
            GroundStorey(),
            UpperStorey(),
            transform([0, 8, 0], 0, [WIDTH, 9, LENGTH], DecorativeRoof()),
            GroundFloorInterior(),
            UpperFloorInterior(),
        ]),
    )
