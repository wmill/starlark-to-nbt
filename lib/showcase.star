# Standalone showcase builds for every library component, used by the test
# harness and handy for eyeballing single components in-game:
#   uv run starlark-to-nbt build lib/showcase.star --arg name=GableRoof --output roof.nbt

load("structural.star", "Foundation", "Floor", "SolidWall", "WindowedWall", "TimberFrameWall", "Column", "Balcony")
load("openings.star", "SingleDoor", "DoubleDoor", "Window", "ShutteredWindow", "Archway")
load("roofs.star", "GableRoof", "ShedRoof", "FlatRoof", "PyramidRoof")
load("fixtures.star", "Bench", "Chair", "Table", "Bed", "BookshelfWall", "Fireplace", "LanternPost", "Carpet")
load("outdoor.star", "Well", "FenceRing", "Path", "Tree")


def showcase(name):
    if name == "Foundation":
        return Foundation(5, 4)
    elif name == "Floor":
        return Floor(6, 5)
    elif name == "SolidWall":
        return SolidWall(7, 4)
    elif name == "WindowedWall":
        return WindowedWall(9, 5)
    elif name == "TimberFrameWall":
        return TimberFrameWall(7, 4)
    elif name == "Column":
        return Column(5)
    elif name == "Balcony":
        return Balcony(4)
    elif name == "SingleDoor":
        return SingleDoor()
    elif name == "DoubleDoor":
        return DoubleDoor()
    elif name == "Window":
        return Window(2, 2)
    elif name == "ShutteredWindow":
        return ShutteredWindow()
    elif name == "Archway":
        return Archway(3, 4)
    elif name == "GableRoof":
        return GableRoof(7, 9)
    elif name == "ShedRoof":
        return ShedRoof(4, 6)
    elif name == "FlatRoof":
        return FlatRoof(6, 6)
    elif name == "PyramidRoof":
        return PyramidRoof(7)
    elif name == "Bench":
        return Bench(3)
    elif name == "Chair":
        return Chair()
    elif name == "Table":
        return Table()
    elif name == "Bed":
        return Bed()
    elif name == "BookshelfWall":
        return BookshelfWall(4, 3)
    elif name == "Fireplace":
        return Fireplace()
    elif name == "LanternPost":
        return LanternPost()
    elif name == "Carpet":
        return Carpet(3, 4)
    elif name == "Well":
        return Well()
    elif name == "FenceRing":
        return FenceRing(6, 8)
    elif name == "Path":
        return Path(8, 2)
    elif name == "Tree":
        return Tree()
    else:
        fail("unknown component %s" % name)


COMPONENT_NAMES = [
    "Foundation", "Floor", "SolidWall", "WindowedWall", "TimberFrameWall", "Column", "Balcony",
    "SingleDoor", "DoubleDoor", "Window", "ShutteredWindow", "Archway",
    "GableRoof", "ShedRoof", "FlatRoof", "PyramidRoof",
    "Bench", "Chair", "Table", "Bed", "BookshelfWall", "Fireplace", "LanternPost", "Carpet",
    "Well", "FenceRing", "Path", "Tree",
]


def build(name):
    return showcase(name)


def rotated(name, rotation):
    """The named component rotated by `rotation` around Y, in a snug region."""
    inner = showcase(name)
    size = inner["min_size"]
    if rotation == 90 or rotation == 270:
        footprint = [size[2], size[1], size[0]]
    else:
        footprint = [size[0], size[1], size[2]]
    return component(
        name="Rotated" + name,
        props={"rotation": rotation},
        min_size=footprint,
        body=transform([0, 0, 0], rotation, size, inner),
    )
