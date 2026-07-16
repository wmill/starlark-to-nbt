# Linear stone fortress controlling a pass, with a moat and lowered drawbridge.

load("../lib/fortifications.star", "BattlementWall", "SquareTower", "Gatehouse", "Drawbridge")
load("../lib/fixtures.star", "LanternPost")
load("../lib/outdoor.star", "Path")


WIDTH = 35
HEIGHT = 16
DEPTH = 21
STONE = "minecraft:stone_bricks"


def build():
    parts = [
        # The defensive line runs east/west across the pass.
        transform([0, 1, 7], 0, [7, 15, 7], SquareTower(7, 14)),
        transform([28, 1, 7], 180, [7, 15, 7], SquareTower(7, 14)),
        transform([7, 1, 10], 0, [6, 10, 1], BattlementWall(6, 9)),
        transform([22, 1, 10], 0, [6, 10, 1], BattlementWall(6, 9)),
        transform([13, 1, 8], 0, [9, 11, 5], Gatehouse(height=10, opening_height=5)),
        # Water occupies ground level; the lowered bridge crosses one block
        # above it and aligns with the gatehouse tunnel.
        fill_region([0, 0, 13], [WIDTH, 1, 20], block("minecraft:water")),
        transform([16, 1, 13], 0, [3, 2, 7], Drawbridge()),
        transform([16, 0, 0], 0, [3, 1, 8], Path(8, 3, "minecraft:gravel")),
        transform([11, 1, 5], 0, [1, 4, 1], LanternPost()),
        transform([23, 1, 5], 0, [1, 4, 1], LanternPost()),
    ]
    return component(name="StonePassFortress", props={}, min_size=[WIDTH, HEIGHT, DEPTH], body=group(parts))
