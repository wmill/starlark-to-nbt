# Linear stone fortress controlling a pass, with a moat and lowered drawbridge.

load("../lib/fortifications.star", "BattlementWall", "SquareTower", "Gatehouse", "Drawbridge")
load("../lib/fixtures.star", "LanternPost")
load("../lib/outdoor.star", "Path")
load("../lib/random.star", "random_cycle", "random_number")


WIDTH = 35
HEIGHT = 16
DEPTH = 21
STONE = "minecraft:stone_bricks"
MOSSY_STONE = "minecraft:mossy_stone_bricks"
CRACKED_STONE = "minecraft:cracked_stone_bricks"
DEFAULT_MOSSY_PERCENT = 0.15
DEFAULT_CRACKED_PERCENT = 0.07
WEATHERING = {
    "cycle": random_cycle(),
    "mossy_percent": DEFAULT_MOSSY_PERCENT,
    "cracked_percent": DEFAULT_CRACKED_PERCENT,
}


def weathered_stone(material, _x, _y, _z):
    roll = random_number(WEATHERING["cycle"])
    if roll < WEATHERING["mossy_percent"]:
        return MOSSY_STONE
    if roll < WEATHERING["mossy_percent"] + WEATHERING["cracked_percent"]:
        return CRACKED_STONE
    return material


def build(mossy_percent=DEFAULT_MOSSY_PERCENT, cracked_percent=DEFAULT_CRACKED_PERCENT):
    if mossy_percent < 0 or mossy_percent > 1:
        fail("mossy_percent must be between 0 and 1")
    if cracked_percent < 0 or cracked_percent > 1:
        fail("cracked_percent must be between 0 and 1")
    if mossy_percent + cracked_percent > 1:
        fail("mossy_percent + cracked_percent must be at most 1")

    WEATHERING["cycle"] = random_cycle()
    WEATHERING["mossy_percent"] = mossy_percent
    WEATHERING["cracked_percent"] = cracked_percent
    parts = [
        # The defensive line runs east/west across the pass.
        transform([0, 1, 7], 0, [7, 15, 7], SquareTower(7, 14, material_picker=weathered_stone)),
        transform([28, 1, 7], 180, [7, 15, 7], SquareTower(7, 14, material_picker=weathered_stone)),
        transform([7, 1, 10], 0, [6, 10, 1], BattlementWall(6, 9, material_picker=weathered_stone)),
        transform([22, 1, 10], 0, [6, 10, 1], BattlementWall(6, 9, material_picker=weathered_stone)),
        transform([13, 1, 8], 0, [9, 11, 5],
                  Gatehouse(height=10, opening_height=5, material_picker=weathered_stone)),
        # Water occupies ground level; the lowered bridge crosses one block
        # above it and aligns with the gatehouse tunnel.
        fill_region([0, 0, 13], [WIDTH, 1, 20], block("minecraft:water")),
        transform([16, 1, 13], 0, [3, 2, 7], Drawbridge()),
        transform([16, 0, 0], 0, [3, 1, 8], Path(8, 3, "minecraft:gravel")),
        transform([11, 1, 5], 0, [1, 4, 1], LanternPost()),
        transform([23, 1, 5], 0, [1, 4, 1], LanternPost()),
    ]
    return component(
        name="StonePassFortress",
        props={"mossy_percent": mossy_percent, "cracked_percent": cracked_percent},
        min_size=[WIDTH, HEIGHT, DEPTH],
        body=group(parts),
    )
