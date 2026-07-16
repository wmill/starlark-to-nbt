# Fixed-size civic square with a central well, crossing paths, stalls, gardens,
# seating, and lanterns.

load("../lib/fixtures.star", "Bench", "LanternPost")
load("../lib/outdoor.star", "Well", "Path", "FlowerBed", "MarketStall", "Tree")


def build():
    parts = [
        transform([16, 0, 16], 0, [3, 4, 3], Well()),
        transform([16, 0, 0], 0, [3, 1, 16], Path(16, 3)),
        transform([16, 0, 19], 0, [3, 1, 16], Path(16, 3)),
        transform([0, 0, 16], 90, [3, 1, 16], Path(16, 3)),
        transform([19, 0, 16], 90, [3, 1, 16], Path(16, 3)),
        transform([5, 0, 5], 0, [5, 4, 3], MarketStall()),
        transform([27, 0, 5], 90, [5, 4, 3], MarketStall(canopy="minecraft:blue_wool")),
        transform([30, 0, 27], 180, [5, 4, 3], MarketStall(canopy="minecraft:green_wool")),
        transform([5, 0, 30], 270, [5, 4, 3], MarketStall(canopy="minecraft:yellow_wool")),
        transform([5, 0, 12], 0, [7, 2, 3], FlowerBed(7, 3)),
        transform([23, 0, 20], 0, [7, 2, 3], FlowerBed(7, 3, flower_a="minecraft:cornflower")),
        transform([14, 0, 10], 90, [4, 1, 1], Bench(4)),
        transform([31, 0, 20], 270, [4, 1, 1], Bench(4)),
        transform([12, 0, 12], 0, [1, 4, 1], LanternPost()),
        transform([22, 0, 12], 0, [1, 4, 1], LanternPost()),
        transform([12, 0, 22], 0, [1, 4, 1], LanternPost()),
        transform([22, 0, 22], 0, [1, 4, 1], LanternPost()),
        transform([1, 0, 1], 0, [3, 6, 3], Tree()),
        transform([31, 0, 31], 0, [3, 6, 3], Tree()),
    ]
    return component(name="MarketSquare", props={}, min_size=[35, 6, 35], body=group(parts))
