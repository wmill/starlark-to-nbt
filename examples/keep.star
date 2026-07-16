# Castle keep: the large stress build. Exercises nested transforms at all four
# rotations, y-axis repeat, assemblies, carves through sibling components, and
# a few thousand block writes.
#
#   uv run starlark-to-nbt build examples/keep.star \
#     --output keep.nbt --debug-dir build/keep

load("../lib/structural.star", "Foundation", "Floor", "WindowedWall")
load("../lib/openings.star", "Archway", "DoubleDoor", "SingleDoor")
load("../lib/roofs.star", "PyramidRoof")
load("../lib/fixtures.star", "LanternPost")
load("../lib/outdoor.star", "FenceRing", "Path", "Tree", "Well")

SIZE = 33
TOWER = 7
TOWER_HEIGHT = 18
WALL_HEIGHT = 12
KEEP = 13
KEEP_WALL_HEIGHT = 10
STONE = "minecraft:stone_bricks"


def Tower(size, height, material=STONE):
    """Hollow square tower with arrow slits and a crenellated crown."""
    parts = [
        fill_region([0, 0, 0], [size, height, 1], block(material)),
        fill_region([0, 0, size - 1], [size, height, size], block(material)),
        fill_region([0, 0, 1], [1, height, size - 1], block(material)),
        fill_region([size - 1, 0, 1], [size, height, size - 1], block(material)),
    ]
    for x in range(0, size, 2):
        parts.append(place_block([x, height, 0], block(material)))
        parts.append(place_block([x, height, size - 1], block(material)))
    for z in range(2, size - 2, 2):
        parts.append(place_block([0, height, z], block(material)))
        parts.append(place_block([size - 1, height, z], block(material)))
    mid = size // 2
    for y in [height - 10, height - 5]:
        parts.append(carve_region([mid, y, 0], [mid + 1, y + 2, 1]))
        parts.append(carve_region([mid, y, size - 1], [mid + 1, y + 2, size]))
        parts.append(carve_region([0, y, mid], [1, y + 2, mid + 1]))
        parts.append(carve_region([size - 1, y, mid], [size, y + 2, mid + 1]))
    return component(
        name="Tower",
        props={"size": size, "height": height, "material": material},
        min_size=[size, height + 1, size],
        body=group(parts),
    )


def CurtainWall(length, height, material=STONE):
    """Wall segment along +X with merlons every other block on top."""
    parts = [fill_region([0, 0, 0], [length, height, 1], block(material))]
    for x in range(0, length, 2):
        parts.append(place_block([x, height, 0], block(material)))
    return component(
        name="CurtainWall",
        props={"length": length, "height": height, "material": material},
        min_size=[length, height + 1, 1],
        body=group(parts),
    )


def Keep():
    """Central keep: windowed shell, two upper floors, pyramid roof."""
    parts = [
        transform([0, 0, 0], 0, [KEEP, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP, KEEP_WALL_HEIGHT)),
        transform([0, 0, KEEP - 1], 180, [KEEP, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP, KEEP_WALL_HEIGHT)),
        transform([0, 0, 1], 90, [KEEP - 2, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT)),
        transform([KEEP - 1, 0, 1], 90, [KEEP - 2, KEEP_WALL_HEIGHT, 1], WindowedWall(KEEP - 2, KEEP_WALL_HEIGHT)),
        transform([KEEP // 2, 0, KEEP - 1], 0, [1, 2, 1], SingleDoor()),
        # Ground floor plus two upper storeys via a y-axis repeat.
        transform([1, 0, 1], 0, [KEEP - 2, 1, KEEP - 2], Floor(KEEP - 2, KEEP - 2)),
        transform([1, 5, 1], 0, [KEEP - 2, 6, KEEP - 2],
                  repeat(axis="y", count=2, child_extent=1, gap=4, child=Floor(KEEP - 2, KEEP - 2))),
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
        transform([0, 1, 0], 0, [TOWER, TOWER_HEIGHT + 1, TOWER], Tower(TOWER, TOWER_HEIGHT)),
        transform([SIZE - TOWER, 1, 0], 90, [TOWER, TOWER_HEIGHT + 1, TOWER], Tower(TOWER, TOWER_HEIGHT)),
        transform([SIZE - TOWER, 1, SIZE - TOWER], 180, [TOWER, TOWER_HEIGHT + 1, TOWER], Tower(TOWER, TOWER_HEIGHT)),
        transform([0, 1, SIZE - TOWER], 270, [TOWER, TOWER_HEIGHT + 1, TOWER], Tower(TOWER, TOWER_HEIGHT)),
        # Curtain walls; the south wall is rotated 180 to stress mirrored merlons.
        transform([TOWER, 1, 0], 0, [span, WALL_HEIGHT + 1, 1], CurtainWall(span, WALL_HEIGHT)),
        transform([TOWER, 1, SIZE - 1], 180, [span, WALL_HEIGHT + 1, 1], CurtainWall(span, WALL_HEIGHT)),
        transform([0, 1, TOWER], 90, [span, WALL_HEIGHT + 1, 1], CurtainWall(span, WALL_HEIGHT)),
        transform([SIZE - 1, 1, TOWER], 90, [span, WALL_HEIGHT + 1, 1], CurtainWall(span, WALL_HEIGHT)),
        # South gate: arch carved through the curtain wall, double door inside.
        # The arch is wider than the door, so stone jambs backfill the flanking
        # columns up to door height -- otherwise you can just walk around the door.
        transform([gate_x, 1, SIZE - 1], 0, [4, 4, 1], Archway(4, 4)),
        fill_region([gate_x, 1, SIZE - 1], [gate_x + 1, 3, SIZE], block(STONE), phase="fixture"),
        fill_region([gate_x + 3, 1, SIZE - 1], [gate_x + 4, 3, SIZE], block(STONE), phase="fixture"),
        transform([gate_x + 1, 1, SIZE - 1], 0, [2, 2, 1], DoubleDoor()),
        # Central keep and courtyard dressing.
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
