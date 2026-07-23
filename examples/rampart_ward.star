# A walled ward corner in the style of training-samples/micmokum-town1.nbt:
# a textured rampart wall and corner tower enclosing a small cluster of
# guest houses, round trees, and a well. Showcases the RampartWall,
# RampartTower, GuestHouse, and RoundTree components added alongside the
# library's existing BattlementWall/SquareTower/Tree family.
#
#   uv run starlark-to-nbt build examples/rampart_ward.star \
#     --output rampart_ward.nbt --debug-dir build/rampart_ward

load("../lib/fortifications.star", "RampartWall", "RampartTower")
load("../lib/dwellings.star", "GuestHouse")
load("../lib/outdoor.star", "RoundTree", "Well", "Path")

SIZE = 27
TOWER = 5
TOWER_HEIGHT = 10
WALL_HEIGHT = 7
# The tower's door faces south into the west wall's run; gapping the wall's
# start by two blocks leaves the door somewhere to open onto instead of
# walking straight into solid stone.
GATE_GAP = 2
WEST_WALL_Z = TOWER + GATE_GAP


def build():
    north_length = SIZE - TOWER
    west_length = SIZE - WEST_WALL_Z
    parts = [
        transform([0, 1, 0], 0, [TOWER, TOWER_HEIGHT + 2, TOWER], RampartTower(TOWER, TOWER_HEIGHT)),
        transform([TOWER, 1, 0], 0, [north_length, WALL_HEIGHT + 2, 3], RampartWall(north_length, WALL_HEIGHT)),
        transform([0, 1, WEST_WALL_Z], 90, [west_length, WALL_HEIGHT + 2, 3], RampartWall(west_length, WALL_HEIGHT)),
        # Guest houses, each a different bed color like the source sample.
        transform([6, 1, 7], 0, [7, 9, 6], GuestHouse(bed="minecraft:lime_bed")),
        transform([16, 1, 7], 0, [7, 9, 6], GuestHouse(bed="minecraft:cyan_bed")),
        transform([6, 1, 17], 0, [7, 9, 6], GuestHouse(bed="minecraft:orange_bed")),
        # A well just inside the gate, and round trees dressing the courtyard.
        transform([8, 1, 3], 0, [3, 4, 3], Well()),
        transform([1, 1, 5], 0, [2, 1, 6], Path(6, 2)),
        transform([20, 1, 17], 0, [5, 8, 5], RoundTree()),
        transform([16, 1, 22], 0, [5, 8, 5], RoundTree(trunk_height=6)),
    ]
    return component(
        name="RampartWard",
        props={"size": SIZE},
        min_size=[SIZE, TOWER_HEIGHT + 3, SIZE],
        metadata={"ground_level": 1},
        body=group(parts),
    )
