load("../lib/structural.star", "Foundation")
load("../lib/fortifications.star", "SquareTower")
load("../lib/outdoor.star", "FenceRing")
load("../lib/fixtures.star", "LanternPost")

def GlassDome(size=7, glass="minecraft:light_blue_stained_glass"):
    r = size // 2
    cx = r
    cz = r
    ops = []
    for y in range(r + 1):
        for x in range(size):
            for z in range(size):
                dx = x - cx
                dz = z - cz
                d2 = dx * dx + dz * dz + y * y
                if d2 <= r * r and d2 > (r - 1) * (r - 1):
                    ops.append(place_block([x, y, z], block(glass)))
    return component(
        name="GlassDome",
        props={},
        min_size=[size, r + 1, size],
        body=group(ops),
    )

def build(size=13, height=19):
    beacon = group([
        place_block([size // 2, 14, size // 2], block("minecraft:glowstone")),
        place_block([size // 2, 15, size // 2], block("minecraft:sea_lantern")),
        place_block([size // 2, 16, size // 2], block("minecraft:glowstone")),
    ])
    return component(
        name="ArcaneObservatory",
        props={"size": size},
        min_size=[size, height, size],
        metadata={"ground_level": 1},
        body=group([
            Foundation(size, size, depth=1, material="minecraft:stone_bricks"),
            at([0, 1, 0], FenceRing(size, size)),
            at([1, 1, 1], LanternPost(3)),
            at([size - 2, 1, 1], LanternPost(3)),
            at([1, 1, size - 2], LanternPost(3)),
            at([size - 2, 1, size - 2], LanternPost(3)),
            at([3, 1, 3], SquareTower(7, 12)),
            at([3, 14, 3], GlassDome(7)),
            beacon,
        ]),
    )
