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
        at([0, 1, 0], TimberFrameWall(width, wall_height)),
        at([0, 1, length - 1], TimberFrameWall(width, wall_height)),
        at([0, 1, 1], TimberFrameWall(length - 2, wall_height), rotation=90),
        at([width - 1, 1, 1], TimberFrameWall(length - 2, wall_height), rotation=90),
        at([0, base, 0], GableRoof(width, length)),
        at([door_x, 1, length - 1], SingleDoor()),
    ]

    windows = [
        at([2, 2, length - 1], Window()),
        at([width - 3, 2, length - 1], Window()),
        at([2, 2, 0], Window()),
        at([width - 3, 2, 0], Window()),
        at([0, 2, mid_z - 1], ShutteredWindow(), rotation=90),
        at([width - 1, 2, mid_z - 1], ShutteredWindow(), rotation=270),
    ]

    furniture = [
        at([(width - 3) // 2, 1, 1], Fireplace(4)),
        at([1, 1, 2], Bed()),
        at([width - 4, 1, length - 4], Table()),
        at([width - 4, 1, length - 3], Chair(), rotation=180),
        at([(width - 3) // 2, 1, (length - 3) // 2], Carpet(3, 3)),
        at([width - 2, 1, 3], BookshelfWall(3, 2), rotation=90),
    ]

    return component(
        name="Cottage",
        props={"width": width, "length": length, "wall_height": wall_height},
        min_size=[width, base + roof_height, length],
        body=group(shell + windows + furniture),
    )


def build(width=13, length=11, wall_height=5):
    return Cottage(width, length, wall_height)
