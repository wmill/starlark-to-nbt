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
        at([0, 0, 0], WindowedWall(KEEP, KEEP_WALL_HEIGHT)),
        at([0, 0, KEEP - 1], WindowedWall(KEEP, KEEP_WALL_HEIGHT), rotation=180),
        at([0, 0, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT), rotation=90),
        at([KEEP - 1, 0, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT), rotation=90),
        at([KEEP // 2, 0, KEEP - 1], SingleDoor()),
        # Two upper storeys via a y-axis repeat. The ground floor is embedded
        # into the castle foundation by KeepCastle so it aligns with the door.
        transform([1, 5, 1], 0, [KEEP - 2, 6, KEEP - 2],
                  repeat(axis="y", count=2, child_extent=1, gap=4, child=Floor(KEEP - 2, KEEP - 2))),
        # The ladder uses the solid north wall for support and passes through
        # a carved opening in the first upper floor.
        carve_region([1, 5, 1], [2, 6, 2]),
        at([1, 0, 1], Ladder(6)),
        at([0, KEEP_WALL_HEIGHT, 0], PyramidRoof(KEEP)),
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
        at([0, 1, 0], SquareTower(TOWER, TOWER_HEIGHT)),
        at([SIZE - TOWER, 1, 0], SquareTower(TOWER, TOWER_HEIGHT), rotation=90),
        at([SIZE - TOWER, 1, SIZE - TOWER], SquareTower(TOWER, TOWER_HEIGHT), rotation=180),
        at([0, 1, SIZE - TOWER], SquareTower(TOWER, TOWER_HEIGHT), rotation=270),
        # Curtain walls; the south wall is rotated 180 to stress mirrored merlons.
        at([TOWER, 1, 0], BattlementWall(span, WALL_HEIGHT)),
        at([TOWER, 1, SIZE - 1], BattlementWall(span, WALL_HEIGHT), rotation=180),
        at([0, 1, TOWER], BattlementWall(span, WALL_HEIGHT), rotation=90),
        at([SIZE - 1, 1, TOWER], BattlementWall(span, WALL_HEIGHT), rotation=90),
        # South gate: arch carved through the curtain wall, double door inside.
        # The arch is wider than the door, so stone jambs backfill the flanking
        # columns up to door height -- otherwise you can just walk around the door.
        at([gate_x, 1, SIZE - 1], Archway(4, 4)),
        fill_region([gate_x, 1, SIZE - 1], [gate_x + 1, 3, SIZE], block(STONE), phase="fixture"),
        fill_region([gate_x + 3, 1, SIZE - 1], [gate_x + 4, 3, SIZE], block(STONE), phase="fixture"),
        at([gate_x + 1, 1, SIZE - 1], DoubleDoor()),
        # Central keep and courtyard dressing.
        # Replace the foundation beneath the keep interior with a wood floor;
        # its top surface is level with the keep door at Y=1.
        carve_region([keep_origin + 1, 0, keep_origin + 1],
                     [keep_origin + KEEP - 1, 1, keep_origin + KEEP - 1]),
        fill_region([keep_origin + 1, 0, keep_origin + 1],
                    [keep_origin + KEEP - 1, 1, keep_origin + KEEP - 1],
                    block("minecraft:oak_planks"), phase="fixture"),
        at([keep_origin, 1, keep_origin], Keep()),
        at([SIZE // 2 - 1, 0, keep_origin + KEEP], Path(SIZE - 2 - keep_origin - KEEP + 1, 2)),
        at([8, 1, 2], Well()),
        at([21, 1, 2], Tree()),
        at([gate_x - 1, 1, SIZE - 3], LanternPost()),
        at([gate_x + 4, 1, SIZE - 3], LanternPost()),
        at([2, 1, 12], FenceRing(6, 8)),
    ]
    return component(
        name="KeepCastle",
        props={"size": SIZE},
        min_size=[SIZE, TOWER_HEIGHT + 2, SIZE],
        body=group(parts),
    )


def build():
    return KeepCastle()
