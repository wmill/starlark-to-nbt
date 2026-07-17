# Garden pavilion: one asymmetric "wing" is authored once, then a loop stamps
# it into all four quadrants by rotating it in 90-degree steps and looking up
# its edge position in a small table. Demonstrates rotation-driven symmetry --
# the DSL's only orientation primitive is transform()'s 0/90/180/270 rotation,
# so an N-fold symmetric layout is built by generating the list of transform()
# calls instead of writing each one out by hand.

load("../lib/structural.star", "Foundation")
load("../lib/fixtures.star", "Bench", "LanternPost")
load("../lib/outdoor.star", "Well")
load("../lib/roofs.star", "PyramidRoof")

PLATFORM = 13
WING_WIDTH = 5
WING_DEPTH = 2
WING_HEIGHT = 3

# Each edge stamps the wing (authored facing +Z/south) at the rotation that
# turns its front toward the plaza center, per Transform.rotate_facing's
# south -> west -> north -> east cycle.
EDGES = [0, 90, 180, 270]


def Wing():
    """A bench backed by a lantern flanked by two flowers -- asymmetric, so
    replicating it by rotation is the only way to get a symmetric plaza."""
    return component(
        name="Wing",
        props={},
        min_size=[WING_WIDTH, WING_HEIGHT, WING_DEPTH],
        body=group([
            transform([0, 0, 0], 0, [WING_WIDTH, 1, 1], Bench(WING_WIDTH)),
            transform([2, 0, 1], 0, [1, WING_HEIGHT, 1], LanternPost(height=2)),
            place_block([1, 0, 1], block("minecraft:poppy"), phase="fixture"),
            place_block([3, 0, 1], block("minecraft:dandelion"), phase="fixture"),
        ]),
    )


def wing_translation(rotation):
    center_offset = (PLATFORM - WING_WIDTH) // 2
    far_edge = PLATFORM - WING_DEPTH
    if rotation == 0:
        return [center_offset, 1, 0]
    if rotation == 90:
        return [far_edge, 1, center_offset]
    if rotation == 180:
        return [center_offset, 1, far_edge]
    return [0, 1, center_offset]


def build(platform=PLATFORM):
    wing = Wing()
    wing_size = [WING_WIDTH, WING_HEIGHT, WING_DEPTH]
    wings = [
        transform(wing_translation(rotation), rotation, wing_size, wing)
        for rotation in EDGES
    ]
    centerpiece = platform // 2 - 1
    roof_offset = centerpiece - 1
    parts = [
        Foundation(platform, platform, material="minecraft:andesite"),
        transform([centerpiece, 1, centerpiece], 0, [3, 4, 3], Well()),
        transform([roof_offset, 5, roof_offset], 0, [5, 3, 5], PyramidRoof(5)),
    ] + wings
    return component(
        name="ProceduralPavilion",
        props={"platform": platform},
        min_size=[platform, 8, platform],
        body=group(parts),
    )
