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
        transform([0, 1, 0], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height, log="minecraft:spruce_log")),
        transform([0, 1, length - 1], 180, [width, wall_height, 1], TimberFrameWall(width, wall_height, log="minecraft:spruce_log")),
        transform([0, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height, log="minecraft:spruce_log")),
        transform([width - 1, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height, log="minecraft:spruce_log")),
        transform([0, 6, 0], 0, [width, 6, length], GableRoof(width, length, stair="minecraft:spruce_stairs", ridge="minecraft:spruce_planks")),
        transform([5, 1, length - 1], 0, [1, 2, 1], SingleDoor("minecraft:spruce_door")),
        transform([2, 2, length - 1], 0, [1, 2, 1], Window()),
        transform([8, 2, length - 1], 0, [1, 2, 1], Window()),
        transform([2, 1, 2], 0, [1, 1, 2], Bed("minecraft:green_bed")),
        transform([8, 1, 2], 0, [1, 1, 2], Bed("minecraft:green_bed")),
        transform([4, 1, 5], 0, [3, 2, 1], DiningTable()),
    ]
    return component(name="Barracks", props={}, min_size=[width, 12, length], body=group(parts))


def build():
    wall_span = SIZE - 2
    parts = [
        # North and side walls are continuous; the south wall leaves room for
        # the centered five-block gate.
        transform([0, 0, 0], 0, [SIZE, 6, 1], PalisadeWall(SIZE)),
        transform([0, 0, 1], 90, [wall_span, 6, 1], PalisadeWall(wall_span)),
        transform([SIZE - 1, 0, 1], 90, [wall_span, 6, 1], PalisadeWall(wall_span)),
        transform([0, 0, SIZE - 1], 0, [12, 6, 1], PalisadeWall(12)),
        transform([17, 0, SIZE - 1], 0, [12, 6, 1], PalisadeWall(12)),
        transform([12, 0, SIZE - 1], 0, [5, 7, 1], PalisadeGate()),
        # Towers sit just inside the perimeter so their posts remain distinct
        # from the palisade columns.
        transform([2, 0, 2], 0, [5, 8, 5], Watchtower()),
        transform([22, 0, 2], 90, [5, 8, 5], Watchtower()),
        transform([22, 0, 22], 180, [5, 8, 5], Watchtower()),
        transform([2, 0, 22], 270, [5, 8, 5], Watchtower()),
        transform([9, 0, 8], 0, [11, 12, 9], Barracks()),
        transform([13, 0, 17], 0, [3, 1, 11], Path(11, 3, "minecraft:coarse_dirt")),
        transform([4, 0, 12], 0, [4, 3, 2], HayBaleStack(4, 3, 2)),
        transform([7, 0, 18], 0, [1, 4, 1], LanternPost(post="minecraft:spruce_fence")),
        transform([21, 0, 18], 0, [1, 4, 1], LanternPost(post="minecraft:spruce_fence")),
    ]
    return component(name="FrontierOutpost", props={"size": SIZE}, min_size=[SIZE, 14, SIZE], body=group(parts))
