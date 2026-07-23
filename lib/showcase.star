# Standalone showcase builds for every library component, used by the test
# harness and handy for eyeballing single components in-game:
#   uv run starlark-to-nbt build lib/showcase.star --arg name=GableRoof --output roof.nbt

load("structural.star", "Foundation", "Floor", "SolidWall", "WindowedWall", "TimberFrameWall", "Column", "Balcony", "StraightStaircase", "Footbridge")
load("openings.star", "SingleDoor", "DoubleDoor", "Window", "ShutteredWindow", "Archway")
load("roofs.star", "GableRoof", "ShedRoof", "FlatRoof", "PyramidRoof")
load("fixtures.star", "Bench", "Chair", "Table", "Bed", "BookshelfWall", "Fireplace", "LanternPost", "Chest", "Barrel", "Furnace", "Sign", "WallSign", "Carpet", "Ladder", "DiningTable", "KitchenCounter")
load("outdoor.star", "Well", "FenceRing", "Path", "Tree", "RoundTree", "CropPlot", "FlowerBed", "MarketStall", "HayBaleStack", "Pergola", "Horse")
load("fortifications.star", "BattlementWall", "SquareTower", "Portcullis", "Gatehouse", "Drawbridge", "PalisadeWall", "PalisadeGate", "Watchtower", "RampartWall", "RampartTower")
load("dwellings.star", "GuestHouse")


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
    elif name == "StraightStaircase":
        return StraightStaircase(2, 4)
    elif name == "Footbridge":
        return Footbridge(4, 7)
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
    elif name == "Chest":
        return Chest([{"id": "minecraft:bread", "count": 3}, "minecraft:apple"])
    elif name == "Barrel":
        return Barrel(loot="minecraft:chests/simple_dungeon")
    elif name == "Furnace":
        return Furnace([{"slot": 0, "id": "minecraft:raw_iron", "count": 8},
                        {"slot": 1, "id": "minecraft:coal", "count": 4}])
    elif name == "Sign":
        return Sign(["Hello"])
    elif name == "WallSign":
        return WallSign(["Hello"])
    elif name == "Carpet":
        return Carpet(3, 4)
    elif name == "Ladder":
        return Ladder(5)
    elif name == "DiningTable":
        return DiningTable()
    elif name == "KitchenCounter":
        return KitchenCounter()
    elif name == "Well":
        return Well()
    elif name == "Horse":
        return Horse()
    elif name == "FenceRing":
        return FenceRing(6, 8)
    elif name == "Path":
        return Path(8, 2)
    elif name == "Tree":
        return Tree()
    elif name == "RoundTree":
        return RoundTree()
    elif name == "CropPlot":
        return CropPlot(7, 7)
    elif name == "FlowerBed":
        return FlowerBed(5, 4)
    elif name == "MarketStall":
        return MarketStall()
    elif name == "HayBaleStack":
        return HayBaleStack()
    elif name == "Pergola":
        return Pergola()
    elif name == "BattlementWall":
        return BattlementWall(9, 5)
    elif name == "SquareTower":
        return SquareTower(7, 12)
    elif name == "Portcullis":
        return Portcullis()
    elif name == "Gatehouse":
        return Gatehouse()
    elif name == "Drawbridge":
        return Drawbridge()
    elif name == "PalisadeWall":
        return PalisadeWall(9)
    elif name == "PalisadeGate":
        return PalisadeGate()
    elif name == "Watchtower":
        return Watchtower()
    elif name == "RampartWall":
        return RampartWall(12)
    elif name == "RampartTower":
        return RampartTower()
    elif name == "GuestHouse":
        return GuestHouse()
    else:
        fail("unknown component %s" % name)


COMPONENT_NAMES = [
    "Foundation", "Floor", "SolidWall", "WindowedWall", "TimberFrameWall", "Column", "Balcony", "StraightStaircase", "Footbridge",
    "SingleDoor", "DoubleDoor", "Window", "ShutteredWindow", "Archway",
    "GableRoof", "ShedRoof", "FlatRoof", "PyramidRoof",
    "Bench", "Chair", "Table", "Bed", "BookshelfWall", "Fireplace", "LanternPost", "Chest", "Barrel", "Furnace", "Sign", "WallSign", "Carpet", "Ladder", "DiningTable", "KitchenCounter",
    "Well", "FenceRing", "Path", "Tree", "RoundTree", "CropPlot", "FlowerBed", "MarketStall", "HayBaleStack", "Pergola", "Horse",
    "BattlementWall", "SquareTower", "Portcullis", "Gatehouse", "Drawbridge", "PalisadeWall", "PalisadeGate", "Watchtower", "RampartWall", "RampartTower",
    "GuestHouse",
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
