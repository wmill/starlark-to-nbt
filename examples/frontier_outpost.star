# Timber frontier outpost with a complete palisade, four watchtowers, a
# furnished barracks, storage, and a defended south gate.

load("../lib/fortifications.star", "PalisadeWall", "PalisadeGate", "Watchtower")
load("../lib/structural.star", "Foundation", "TimberFrameWall")
load("../lib/openings.star", "SingleDoor", "Window")
load("../lib/roofs.star", "GableRoof")
load("../lib/fixtures.star", "Bed", "DiningTable", "LanternPost")
load("../lib/outdoor.star", "HayBaleStack", "Path")


SIZE = 29


def Barracks():
    width = 11
    length = 9
    wall_height = 5
    parts = [
        Foundation(width, length, 1, "minecraft:cobblestone"),
        at([0, 1, 0], TimberFrameWall(width, wall_height, log="minecraft:spruce_log")),
        at([0, 1, length - 1], TimberFrameWall(width, wall_height, log="minecraft:spruce_log"), rotation=180),
        at([0, 1, 1], TimberFrameWall(length - 2, wall_height, log="minecraft:spruce_log"), rotation=90),
        at([width - 1, 1, 1], TimberFrameWall(length - 2, wall_height, log="minecraft:spruce_log"), rotation=90),
        at([0, 6, 0], GableRoof(width, length, stair="minecraft:spruce_stairs", ridge="minecraft:spruce_planks")),
        at([5, 1, length - 1], SingleDoor("minecraft:spruce_door")),
        at([2, 2, length - 1], Window()),
        at([8, 2, length - 1], Window()),
        at([2, 1, 2], Bed("minecraft:green_bed")),
        at([8, 1, 2], Bed("minecraft:green_bed")),
        at([4, 1, 5], DiningTable()),
    ]
    return component(name="Barracks", props={}, min_size=[width, 12, length], body=group(parts))


def build():
    wall_span = SIZE - 2
    parts = [
        # North and side walls are continuous; the south wall leaves room for
        # the centered five-block gate.
        at([0, 1, 0], PalisadeWall(SIZE)),
        at([0, 1, 1], PalisadeWall(wall_span), rotation=90),
        at([SIZE - 1, 1, 1], PalisadeWall(wall_span), rotation=90),
        at([0, 1, SIZE - 1], PalisadeWall(12)),
        at([17, 1, SIZE - 1], PalisadeWall(12)),
        at([12, 1, SIZE - 1], PalisadeGate()),
        # Towers sit just inside the perimeter so their posts remain distinct
        # from the palisade columns.
        at([2, 1, 2], Watchtower()),
        at([22, 1, 2], Watchtower(), rotation=90),
        at([22, 1, 22], Watchtower(), rotation=180),
        at([2, 1, 22], Watchtower(), rotation=270),
        at([9, 0, 8], Barracks()),
        at([13, 0, 17], Path(11, 3, "minecraft:coarse_dirt")),
        at([4, 1, 12], HayBaleStack(4, 3, 2)),
        at([7, 1, 18], LanternPost(post="minecraft:spruce_fence")),
        at([21, 1, 18], LanternPost(post="minecraft:spruce_fence")),
    ]
    return component(
        name="FrontierOutpost",
        props={"size": SIZE},
        min_size=[SIZE, 14, SIZE],
        metadata={"ground_level": 1},
        body=group(parts),
    )
