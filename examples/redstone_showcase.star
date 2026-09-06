# Interactive Java 1.21.7 gallery. See docs/redstone-gallery.md for playtests.
load("../lib/fixtures.star", "Sign")
load("../lib/redstone.star", "AndGate", "Button", "HopperClock", "ItemSorter",
     "LampMatrix", "Lever", "NandGate", "NorGate", "NotGate", "OrGate",
     "PistonDoor", "PistonTrapdoor", "PulseExtender", "RedstoneClock",
     "RedstoneLamp", "RedstoneWire", "Repeater", "TFlipFlop",
     "WeightedPressurePlate", "XnorGate", "XorGate")

WIDTH = 82
HEIGHT = 12
LENGTH = 90
_BASE = "minecraft:smooth_stone"


def _sign(x, z, lines, y=3):
    # Rotation 8 faces north, toward visitors arriving from the north aisle.
    return transform([x, y, z], 180, [1, 1, 1],
              Sign(lines, material="minecraft:dark_oak_sign", color="white", glowing=True))


def _container(x, y, z, items=None, kind="barrel", facing="up"):
    return place_block([x, y, z], block("minecraft:" + kind,
                       {"facing": facing}, nbt=container_nbt(items, id="minecraft:" + kind)))


def _input(x, z, pulse=False, color="minecraft:blue_concrete"):
    control = Button(base="minecraft:orange_concrete") if pulse else Lever(base=color)
    return group([at([x, 3, z], control), at([x, 3, z + 1], RedstoneWire(base=color))])


def _gate_station(gate, inputs, output_x, lines, pulse=False):
    size = gate["min_size"]
    x = (18 - size[0]) // 2
    z = 6
    parts = [at([x, 3, z], gate),
             at([x + output_x, 4, z + size[2]], RedstoneLamp()),
             _sign(7, 1, lines),
             _sign(x + output_x, z + size[2] + 2, ["OUTPUT", "Lamp = Q", "", ""])]
    for i in range(len(inputs)):
        ix = x + inputs[i]
        parts.append(_input(ix, z - 2, pulse=pulse,
                            color="minecraft:blue_concrete" if i == 0 else "minecraft:lime_concrete"))
        parts.append(_sign(ix, z - 3, ["PULSE" if pulse else ("A" if i == 0 else "B"), "", "", ""]))
    return group(parts)


def _hopper_station():
    return group([
        _sign(7, 1, ["HOPPER CLOCK", "Two output lamps", "More items=slower", "Edit either hopper"]),
        at([4, 3, 7], HopperClock()),
        at([5, 4, 11], RedstoneLamp()), at([12, 4, 11], RedstoneLamp()),
        _sign(5, 13, ["OUTPUT LEFT", "", "", ""]),
        _sign(12, 13, ["OUTPUT RIGHT", "", "", ""]),
        _sign(8, 5, ["INVENTORY", "16 items total", "Keep some items", "Wait for settling"]),
    ])


def _analog_station():
    parts = [_sign(7, 1, ["ANALOG METER", "Drop items on gold", "Longer = stronger", "Collect to reset"]),
             _container(1, 3, 3, [{"id": "minecraft:" + item, "count": 1} for item in [
                 "stone", "cobblestone", "dirt", "sand", "gravel", "oak_planks",
                 "spruce_planks", "glass", "redstone", "coal", "iron_ingot",
                 "gold_ingot", "diamond", "emerald", "quartz"]]),
             _sign(3, 3, ["SUPPLY", "15 distinct items", "Drop separately", "See gallery guide"]),
             at([1, 3, 9], WeightedPressurePlate(base=_BASE))]
    for i in range(15):
        x = i + 2
        parts.extend([
            at([x, 3, 9], RedstoneWire(base=_BASE)),
            at([x, 3, 8], Repeater(facing="north", base=_BASE)),
            at([x, 4, 7], RedstoneLamp()),
            _sign(x, 5, [str(i + 1), "", "", ""]),
        ])
    return group(parts)


def _bridge_station():
    return group([
        _sign(7, 1, ["PISTON BRIDGE", "Lever ON=cross", "OFF=visible gap", "Walk around sides"]),
        at([7, 1, 7], PistonTrapdoor(3)),
        # Travel cell is an explicit shallow trench, including the base slab.
        carve_region([7, 1, 10], [10, 3, 11]),
        _sign(5, 6, ["CONTROL", "Side lever", "Cross east/west", "Over moving row"]),
        # The crossing runs east/west through z=10. The surrounding floor
        # supplies fixed banks, and z=12 is a safe bypass.
    ])


def _door_station():
    return group([
        _sign(7, 1, ["2x2 PISTON DOOR", "Lever ON=closed", "OFF=walk through", "Controls at side"]),
        at([6, 2, 7], PistonDoor()),
        # Explicit passage and approaches preserve air when placed in terrain.
        carve_region([8, 3, 4], [10, 5, 7]),
        carve_region([8, 3, 11], [10, 5, 16]),
        _sign(4, 7, ["CONTROL", "Side lever", "", ""]),
    ])


def _sorter_station():
    parts = [
        _sign(7, 1, ["ITEM SORTER", "Insert at INPUT", "Redstone filtered", "Cobble -> reject"]),
        at([7, 3, 8], ItemSorter()),
        _container(8, 8, 9),
        _sign(6, 6, ["INPUT ABOVE", "Use side stairs", "Do not edit filter", "41+4 reserved"]),
        _container(4, 3, 4, [{"id": "minecraft:redstone", "count": 32},
                               {"id": "minecraft:cobblestone", "count": 32}]),
        _sign(6, 4, ["SUPPLY", "Take both types", "Insert above", ""]),
        _container(9, 7, 14),
        _sign(9, 16, ["REJECT ABOVE", "Cobblestone", "", ""]),
        _sign(6, 10, ["FILTERED", "Bottom barrel", "Redstone", ""]),
    ]
    # Turn away from the filter's dust rather than carrying inventory over it.
    parts.append(_container(8, 7, 10, kind="hopper", facing="east"))
    for z in range(10, 14):
        parts.append(_container(9, 7, z, kind="hopper", facing="south"))
    # A two-wide staircase and side balcony reach the input and reject barrels.
    for i in range(5):
        if i > 0:
            parts.append(fill_region([11, 3, 3 + i], [13, 3 + i, 4 + i], block("minecraft:deepslate_tiles")))
        parts.append(fill_region([11, 3 + i, 3 + i], [13, 4 + i, 4 + i],
                     block("minecraft:deepslate_tile_stairs", {"facing": "south", "half": "bottom", "shape": "straight"})))
    parts.append(fill_region([10, 7, 8], [13, 8, 16], block("minecraft:deepslate_tiles")))
    return group(parts)


def _matrix_station():
    parts = [_sign(7, 1, ["LAMP MATRIX", "15 rear levers", "Each drives pixel", "Walk around panel"]),
             at([6, 3, 9], LampMatrix(5, 3)),
             _sign(7, 6, ["REAR CONTROLS", "Rows match height", "Columns match X", "Front is south"])]
    for x in range(5):
        for y in range(3):
            parts.append(at([6 + x, 3 + y, 8], Lever(face="wall", facing="north")))
    return group(parts)


def InteractiveGallery():
    stations = [
        _gate_station(NotGate(), [0], 0, ["NOT", "A | Q", "0 | 1", "1 | 0"]),
        _gate_station(OrGate(), [0, 2], 1, ["OR", "00=0 01=1", "10=1 11=1", ""]),
        _gate_station(NorGate(), [0, 2], 1, ["NOR", "00=1 01=0", "10=0 11=0", ""]),
        _gate_station(NandGate(), [0, 2], 1, ["NAND", "00=1 01=1", "10=1 11=0", ""]),
        _gate_station(AndGate(), [0, 2], 1, ["AND", "00=0 01=0", "10=0 11=1", ""]),
        _gate_station(XorGate(), [0, 4], 2, ["XOR", "00=0 01=1", "10=1 11=0", ""]),
        _gate_station(XnorGate(), [0, 4], 2, ["XNOR", "00=1 01=0", "10=0 11=1", ""]),
        _gate_station(TFlipFlop(), [0], 0, ["T FLIP-FLOP", "Press to toggle", "Wait then repeat", "Bulb remembers"], pulse=True),
        _gate_station(PulseExtender(16), [1], 1, ["PULSE EXTENDER", "16 redstone ticks", "Short pulse only", "Wait before retry"], pulse=True),
        group([_gate_station(RedstoneClock(4), [1], 4, ["REPEATER CLOCK", "Button starts", "Lever=stage lock", "May need restart"], pulse=True),
               _sign(13, 10, ["STAGE LOCK", "Not pause/resume", "Unlock then start", "Reset if stuck"])]),
        _hopper_station(), _analog_station(),
        _bridge_station(), _door_station(), _sorter_station(), _matrix_station(),
    ]
    parts = [fill_region([0, 0, 0], [WIDTH, 1, LENGTH], block("minecraft:polished_andesite"))]
    # Leave mechanism recesses out of the structural floor before carving.
    for z0, z1, spans in [(0, 75, [[0, WIDTH]]),
                           (75, 79, [[0, 9], [12, 28], [34, WIDTH]]),
                           (79, LENGTH, [[0, WIDTH]])]:
        for span in spans:
            parts.append(fill_region([span[0], 1, z0], [span[1], 3, z1], block("minecraft:polished_andesite")))
    for i in range(16):
        x = 2 + (i % 4) * 20
        z = 2 + (i // 4) * 22
        parts.append(at([x, 0, z], component(name="Station", props={"index": i},
                     min_size=[18, HEIGHT, 20], body=stations[i])))
    parts.append(_sign(40, 0, ["REDSTONE LAB", "Blue=A Green=B", "Orange=pulse", "Rows go west-east"]))
    return component(name="InteractiveRedstoneGallery", props={},
                     min_size=[WIDTH, HEIGHT, LENGTH], metadata={"ground_level": 3}, body=group(parts))


def build():
    return InteractiveGallery()
