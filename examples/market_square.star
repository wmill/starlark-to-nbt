# Fixed-size civic square with a central well, crossing paths, stalls, gardens,
# seating, and lanterns.

load("../lib/fixtures.star", "Bench", "LanternPost")
load("../lib/outdoor.star", "Well", "Path", "FlowerBed", "MarketStall", "Tree")


def build():
    parts = [
        at([16, 1, 16], Well()),
        at([16, 0, 0], Path(16, 3)),
        at([16, 0, 19], Path(16, 3)),
        at([0, 0, 16], Path(16, 3), rotation=90),
        at([19, 0, 16], Path(16, 3), rotation=90),
        at([5, 1, 5], MarketStall()),
        at([27, 1, 5], MarketStall(canopy="minecraft:blue_wool"), rotation=90),
        at([30, 1, 27], MarketStall(canopy="minecraft:green_wool"), rotation=180),
        at([5, 1, 30], MarketStall(canopy="minecraft:yellow_wool"), rotation=270),
        at([5, 0, 12], FlowerBed(7, 3)),
        at([23, 0, 20], FlowerBed(7, 3, flower_a="minecraft:cornflower")),
        at([14, 1, 10], Bench(4), rotation=90),
        at([31, 1, 20], Bench(4), rotation=270),
        at([12, 1, 12], LanternPost()),
        at([22, 1, 12], LanternPost()),
        at([12, 1, 22], LanternPost()),
        at([22, 1, 22], LanternPost()),
        at([1, 1, 1], Tree()),
        at([31, 1, 31], Tree()),
    ]
    return component(
        name="MarketSquare",
        props={},
        min_size=[35, 7, 35],
        metadata={"ground_level": 1},
        body=group(parts),
    )
