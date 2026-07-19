# Castle keep: the large stress build. Exercises nested transforms at all four
# rotations, y-axis repeat, assemblies, carves through sibling components, and
# a few thousand block writes.
#
#   uv run starlark-to-nbt build examples/keep.star \
#     --output keep.nbt --debug-dir build/keep

load("../lib/structural.star", "Foundation", "Floor", "WindowedWall")
load("../lib/openings.star", "Archway", "DoubleDoor", "SingleDoor")
load("../lib/roofs.star", "PyramidRoof")
load("../lib/fixtures.star", "Ladder", "LanternPost")
load("../lib/outdoor.star", "FenceRing", "Path", "Tree", "Well")
load("../lib/fortifications.star", "BattlementWall", "SquareTower")

SIZE = 33
TOWER = 7
TOWER_HEIGHT = 18
WALL_HEIGHT = 12
KEEP = 13
KEEP_WALL_HEIGHT = 10
STONE = "minecraft:stone_bricks"


def Keep():
    """Central keep: windowed shell, two upper floors, pyramid roof."""
    parts = [
        transform([0, 0, 0], 0, [KEEP, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP, KEEP_WALL_HEIGHT)),
        transform([0, 0, KEEP - 1], 180, [KEEP, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP, KEEP_WALL_HEIGHT)),
        transform([0, 0, 1], 90, [KEEP - 2, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT)),
        transform([KEEP - 1, 0, 1], 90, [KEEP - 2, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT)),
        transform([KEEP // 2, 0, KEEP - 1], 0, [1, 2, 1], SingleDoor()),
        # Two upper storeys via a y-axis repeat. The ground floor is embedded
        # into the castle foundation by KeepCastle so it aligns with the door.
        transform([1, 5, 1], 0, [KEEP - 2, 6, KEEP - 2],
                  repeat(axis="y", count=2, child_extent=1, gap=4, child=Floor(KEEP - 2, KEEP - 2))),
        # The ladder uses the solid north wall for support and passes through
        # a carved opening in the first upper floor.
        carve_region([1, 5, 1], [2, 6, 2]),
        transform([1, 0, 1], 0, [1, 6, 1], Ladder(6)),
        transform([0, KEEP_WALL_HEIGHT, 0], 0, [KEEP, (KEEP + 1) // 2, KEEP], PyramidRoof(KEEP)),
    ]
    return component(
        name="Keep",
        props={"size": KEEP, "wall_height": KEEP_WALL_HEIGHT},
        min_size=[KEEP, KEEP_WALL_HEIGHT + (KEEP + 1) // 2, KEEP],
        body=group(parts),
    )


def KeepCastle():
    span = SIZE - 2 * TOWER  # curtain wall length between towers
    keep_origin = (SIZE - KEEP) // 2
    gate_x = SIZE // 2 - 2

    parts = [
        Foundation(SIZE, SIZE, 1, "minecraft:stone"),
        # Corner towers at all four rotations.
        transform([0, 1, 0], 0, [TOWER, TOWER_HEIGHT + 1, TOWER], SquareTower(TOWER, TOWER_HEIGHT)),
        transform([SIZE - TOWER, 1, 0], 90, [TOWER, TOWER_HEIGHT + 1, TOWER], SquareTower(TOWER, TOWER_HEIGHT)),
        transform([SIZE - TOWER, 1, SIZE - TOWER], 180, [TOWER, TOWER_HEIGHT + 1, TOWER], SquareTower(TOWER, TOWER_HEIGHT)),
        transform([0, 1, SIZE - TOWER], 270, [TOWER, TOWER_HEIGHT + 1, TOWER], SquareTower(TOWER, TOWER_HEIGHT)),
        # Curtain walls; the south wall is rotated 180 to stress mirrored merlons.
        transform([TOWER, 1, 0], 0, [span, WALL_HEIGHT + 1, 1], BattlementWall(span, WALL_HEIGHT)),
        transform([TOWER, 1, SIZE - 1], 180, [span, WALL_HEIGHT + 1, 1], BattlementWall(span, WALL_HEIGHT)),
        transform([0, 1, TOWER], 90, [span, WALL_HEIGHT + 1, 1], BattlementWall(span, WALL_HEIGHT)),
        transform([SIZE - 1, 1, TOWER], 90, [span, WALL_HEIGHT + 1, 1], BattlementWall(span, WALL_HEIGHT)),
        # South gate: arch carved through the curtain wall, double door inside.
        # The arch is wider than the door, so stone jambs backfill the flanking
        # columns up to door height -- otherwise you can just walk around the door.
        transform([gate_x, 1, SIZE - 1], 0, [4, 4, 1], Archway(4, 4)),
        fill_region([gate_x, 1, SIZE - 1], [gate_x + 1, 3, SIZE], block(STONE), phase="fixture"),
        fill_region([gate_x + 3, 1, SIZE - 1], [gate_x + 4, 3, SIZE], block(STONE), phase="fixture"),
        transform([gate_x + 1, 1, SIZE - 1], 0, [2, 2, 1], DoubleDoor()),
        # Central keep and courtyard dressing.
        # Replace the foundation beneath the keep interior with a wood floor;
        # its top surface is level with the keep door at Y=1.
        carve_region([keep_origin + 1, 0, keep_origin + 1],
                     [keep_origin + KEEP - 1, 1, keep_origin + KEEP - 1]),
        fill_region([keep_origin + 1, 0, keep_origin + 1],
                    [keep_origin + KEEP - 1, 1, keep_origin + KEEP - 1],
                    block("minecraft:oak_planks"), phase="fixture"),
        transform([keep_origin, 1, keep_origin], 0,
                  [KEEP, KEEP_WALL_HEIGHT + (KEEP + 1) // 2, KEEP], Keep()),
        transform([SIZE // 2 - 1, 0, keep_origin + KEEP], 0, [2, 1, 9],
                  Path(SIZE - 2 - keep_origin - KEEP + 1, 2)),
        transform([8, 1, 2], 0, [3, 4, 3], Well()),
        transform([21, 1, 2], 0, [3, 6, 3], Tree()),
        transform([gate_x - 1, 1, SIZE - 3], 0, [1, 4, 1], LanternPost()),
        transform([gate_x + 4, 1, SIZE - 3], 0, [1, 4, 1], LanternPost()),
        transform([2, 1, 12], 0, [6, 1, 8], FenceRing(6, 8)),
    ]
    return component(
        name="KeepCastle",
        props={"size": SIZE},
        min_size=[SIZE, TOWER_HEIGHT + 2, SIZE],
        body=group(parts),
    )


def build():
    return KeepCastle()
