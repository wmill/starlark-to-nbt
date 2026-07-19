# Fixed-size village farmstead: a furnished two-storey farmhouse, fields,
# hay storage, and a footbridge across a stream.

load("../lib/structural.star", "Foundation", "Floor", "TimberFrameWall", "StraightStaircase", "Footbridge")
load("../lib/openings.star", "SingleDoor", "Window")
load("../lib/roofs.star", "GableRoof")
load("../lib/fixtures.star", "Ladder", "DiningTable", "KitchenCounter", "Bed", "LanternPost")
load("../lib/outdoor.star", "CropPlot", "HayBaleStack", "Path", "Tree")


def Farmhouse():
    width = 13
    length = 11
    wall_height = 8
    shell = [
        Foundation(width, length),
        transform([0, 1, 0], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height)),
        transform([0, 1, length - 1], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height)),
        transform([0, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height)),
        transform([width - 1, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height)),
        transform([0, 9, 0], 0, [width, 7, length], GableRoof(width, length)),
        # Upper floor leaves a two-block-wide stair opening at the east side.
        transform([1, 5, 1], 0, [8, 1, length - 2], Floor(8, length - 2)),
        transform([11, 5, 1], 0, [1, 1, length - 2], Floor(1, length - 2)),
        transform([9, 1, 2], 0, [2, 4, 4], StraightStaircase(2, 4)),
    ]
    details = [
        transform([6, 1, 10], 0, [1, 2, 1], SingleDoor()),
        transform([2, 2, 10], 0, [1, 2, 1], Window()),
        transform([10, 2, 10], 0, [1, 2, 1], Window()),
        transform([2, 6, 10], 0, [1, 2, 1], Window()),
        transform([10, 6, 10], 0, [1, 2, 1], Window()),
        transform([2, 1, 3], 0, [5, 2, 1], DiningTable(5)),
        transform([2, 1, 7], 0, [4, 2, 1], KitchenCounter(4)),
        transform([11, 1, 7], 180, [1, 4, 1], Ladder(4)),
        transform([2, 6, 2], 0, [1, 1, 2], Bed()),
    ]
    return component(name="Farmhouse", props={}, min_size=[width, 16, length], body=group(shell + details))


def build():
    parts = [
        transform([2, 0, 3], 0, [13, 16, 11], Farmhouse()),
        transform([18, 0, 3], 0, [9, 2, 9], CropPlot(9, 9)),
        transform([29, 1, 4], 0, [5, 3, 3], HayBaleStack(5, 3, 3)),
        # Stream runs east/west; the bridge crosses it north/south.
        fill_region([0, 0, 17], [41, 1, 22], block("minecraft:water")),
        transform([16, 1, 15], 0, [5, 2, 9], Footbridge(5, 9)),
        transform([17, 0, 24], 0, [3, 1, 8], Path(8, 3)),
        transform([4, 1, 25], 0, [3, 6, 3], Tree()),
        transform([34, 1, 26], 0, [3, 6, 3], Tree()),
        transform([12, 1, 15], 0, [1, 4, 1], LanternPost()),
        transform([28, 1, 23], 0, [1, 4, 1], LanternPost()),
    ]
    return component(
        name="RiversideFarmstead",
        props={},
        min_size=[41, 16, 35],
        metadata={"ground_level": 1},
        body=group(parts),
    )
