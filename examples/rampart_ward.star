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
TOWER_HEIGHT = 11
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
        at([0, 0, 0], RampartTower(TOWER, TOWER_HEIGHT)),
        at([TOWER, 1, 0], RampartWall(north_length, WALL_HEIGHT), rotation=180),
        at([0, 1, WEST_WALL_Z], RampartWall(west_length, WALL_HEIGHT), rotation=90),
        # Guest houses, each a different bed color like the source sample.
        at([6, 0, 7], GuestHouse(bed="minecraft:lime_bed")),
        at([16, 0, 7], GuestHouse(bed="minecraft:cyan_bed")),
        at([6, 0, 17], GuestHouse(bed="minecraft:orange_bed")),
        # A well just inside the gate, and round trees dressing the courtyard.
        at([8, 1, 3], Well()),
        at([1, 0, 5], Path(6, 2)),
        at([20, 1, 17], RoundTree()),
        at([16, 1, 22], RoundTree(trunk_height=6)),
    ]
    return component(
        name="RampartWard",
        props={"size": SIZE},
        min_size=[SIZE, TOWER_HEIGHT + 3, SIZE],
        metadata={"ground_level": 1},
        body=group(parts),
    )
