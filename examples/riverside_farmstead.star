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
        at([0, 1, 0], TimberFrameWall(width, wall_height)),
        at([0, 1, length - 1], TimberFrameWall(width, wall_height)),
        at([0, 1, 1], TimberFrameWall(length - 2, wall_height), rotation=90),
        at([width - 1, 1, 1], TimberFrameWall(length - 2, wall_height), rotation=90),
        at([0, 9, 0], GableRoof(width, length)),
        # Upper floor leaves a two-block-wide stairwell at the east side and
        # resumes beyond the top tread to form the landing.
        at([1, 5, 1], Floor(8, length - 2)),
        at([11, 5, 1], Floor(1, length - 2)),
        at([9, 5, 7], Floor(2, 3)),
        at([9, 1, 2], StraightStaircase(2, 5)),
    ]
    details = [
        at([6, 1, 10], SingleDoor()),
        at([2, 2, 10], Window()),
        at([10, 2, 10], Window()),
        at([2, 6, 10], Window()),
        at([10, 6, 10], Window()),
        at([2, 1, 3], DiningTable(5)),
        at([2, 1, 7], KitchenCounter(4)),
        at([11, 1, 7], Ladder(4), rotation=180),
        at([2, 6, 2], Bed()),
    ]
    return component(name="Farmhouse", props={}, min_size=[width, 16, length], body=group(shell + details))


def build():
    parts = [
        at([2, 0, 3], Farmhouse()),
        at([18, 0, 3], CropPlot(9, 9)),
        at([29, 1, 4], HayBaleStack(5, 3, 3)),
        # Stream runs east/west; the bridge crosses it north/south.
        fill_region([0, 0, 17], [41, 1, 22], block("minecraft:water")),
        at([16, 1, 15], Footbridge(5, 9)),
        at([17, 0, 24], Path(8, 3)),
        at([4, 1, 25], Tree()),
        at([34, 1, 26], Tree()),
        at([12, 1, 15], LanternPost()),
        at([28, 1, 23], LanternPost()),
    ]
    return component(
        name="RiversideFarmstead",
        props={},
        min_size=[41, 16, 35],
        metadata={"ground_level": 1},
        body=group(parts),
    )
