# Timber-framed cottage composed from the component library. This is the
# reference example of load()-based composition:
#
#   uv run starlark-to-nbt build examples/cottage.star \
#     --output cottage.nbt --debug-dir build/cottage

load("../lib/structural.star", "Foundation", "TimberFrameWall")
load("../lib/openings.star", "SingleDoor", "Window", "ShutteredWindow")
load("../lib/roofs.star", "GableRoof")
load("../lib/fixtures.star", "Bed", "BookshelfWall", "Carpet", "Chair", "Fireplace", "Table")


def Cottage(width, length, wall_height):
    base = 1 + wall_height
    roof_height = (width + 1) // 2
    door_x = width // 2
    mid_z = (length - 1) // 2

    shell = [
        Foundation(width, length),
        # Perimeter walls; side walls slot between the front/back corners.
        transform([0, 1, 0], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height)),
        transform([0, 1, length - 1], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height)),
        transform([0, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height)),
        transform([width - 1, 1, 1], 90, [length - 2, wall_height, 1], TimberFrameWall(length - 2, wall_height)),
        transform([0, base, 0], 0, [width, roof_height, length], GableRoof(width, length)),
        transform([door_x, 1, length - 1], 0, [1, 2, 1], SingleDoor()),
    ]

    windows = [
        transform([2, 2, length - 1], 0, [1, 2, 1], Window()),
        transform([width - 3, 2, length - 1], 0, [1, 2, 1], Window()),
        transform([2, 2, 0], 0, [1, 2, 1], Window()),
        transform([width - 3, 2, 0], 0, [1, 2, 1], Window()),
        transform([0, 2, mid_z - 1], 90, [3, 2, 1], ShutteredWindow()),
        transform([width - 1, 2, mid_z - 1], 270, [3, 2, 1], ShutteredWindow()),
    ]

    furniture = [
        transform([(width - 3) // 2, 1, 1], 0, [3, 4, 1], Fireplace(4)),
        transform([1, 1, 2], 0, [1, 1, 2], Bed()),
        transform([width - 4, 1, length - 4], 0, [1, 2, 1], Table()),
        transform([width - 4, 1, length - 3], 180, [1, 1, 1], Chair()),
        transform([(width - 3) // 2, 1, (length - 3) // 2], 0, [3, 1, 3], Carpet(3, 3)),
        transform([width - 2, 1, 3], 90, [3, 2, 1], BookshelfWall(3, 2)),
    ]

    return component(
        name="Cottage",
        props={"width": width, "length": length, "wall_height": wall_height},
        min_size=[width, base + roof_height, length],
        body=group(shell + windows + furniture),
    )


def build(width=13, length=11, wall_height=5):
    return Cottage(width, length, wall_height)
