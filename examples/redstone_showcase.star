# Interactive redstone gallery for Java 1.21.7.
#
#   uv run starlark-to-nbt build examples/redstone_showcase.star \
#     --output build/redstone_showcase.nbt --debug-dir build/redstone_showcase
#
# Blue controls are input A, green controls are input B, and lamps on the
# south edge are outputs. Every mechanism is separated from its neighbors so
# its dust cannot cross-connect after structure placement.

load("../lib/structural.star", "Foundation")
load("../lib/fixtures.star", "Sign")
load("../lib/redstone.star",
     "AndGate", "Button", "HopperClock", "ItemSorter", "LampMatrix",
     "Lever", "NandGate", "NorGate", "NotGate", "OrGate", "PistonDoor",
     "PistonTrapdoor", "PulseExtender", "RedstoneClock", "RedstoneLamp",
     "RedstoneWire", "TFlipFlop", "WeightedPressurePlate",
     "XnorGate", "XorGate")

WIDTH = 52
HEIGHT = 7
LENGTH = 45


def _standing_sign(pos, lines, color="white"):
    return transform(pos, 0, [1, 1, 1],
                     Sign(lines, material="minecraft:dark_oak_sign",
                          color=color, glowing=True))


def _lever_input(x, z, color):
    # Lever and bridging dust each bring their own colored pad so the wire
    # never floats: pad at y=1, control/dust at y=2, meeting the gate's dust.
    return group([
        transform([x, 1, z], 0, [1, 2, 1], Lever(base=color)),
        transform([x, 1, z + 1], 0, [1, 2, 1], RedstoneWire(base=color)),
    ])


def _gate_station(x, z, size, gate, inputs, output_x, lines):
    parts = [
        transform([x, 1, z], 0, size, gate),
        # Output lamp on a walkway-colored pedestal, driven by the gate's
        # south-edge dust.
        place_block([x + output_x, 1, z + size[2]], block("minecraft:deepslate_tiles")),
        transform([x + output_x, 2, z + size[2]], 0, [1, 1, 1], RedstoneLamp()),
        _standing_sign([x + output_x, 1, z - 4], lines, color="yellow"),
    ]
    if len(inputs) >= 1:
        parts.append(_lever_input(x + inputs[0], z - 2, "minecraft:blue_concrete"))
    if len(inputs) == 2:
        parts.append(_lever_input(x + inputs[1], z - 2, "minecraft:lime_concrete"))
    return group(parts)


def _pulse_input(x, z):
    return group([
        transform([x, 1, z], 0, [1, 2, 1],
                  Button(base="minecraft:orange_concrete")),
        transform([x, 1, z + 1], 0, [1, 2, 1],
                  RedstoneWire(base="minecraft:orange_concrete")),
    ])


def InteractiveGallery():
    parts = [
        Foundation(WIDTH, LENGTH, material="minecraft:polished_andesite"),
        # Visitor aisle and color legend.
        fill_region([0, 1, 14], [WIDTH, 2, 15], block("minecraft:deepslate_tiles")),
        fill_region([0, 1, 29], [WIDTH, 2, 31], block("minecraft:deepslate_tiles")),
        _standing_sign([25, 1, 1],
                       ["REDSTONE LAB", "Blue=A  Green=B", "Orange=pulse", "Lamp=output"],
                       color="aqua"),

        # Logic classroom, row one.
        _gate_station(2, 6, [1, 2, 4], NotGate(), [0], 0,
                      ["NOT", "A | OUT", "0 | 1", "1 | 0"]),
        _gate_station(8, 6, [3, 2, 4], OrGate(), [0, 2], 1,
                      ["OR", "A B | OUT", "00=0  01=1", "10=1  11=1"]),
        _gate_station(15, 6, [3, 2, 7], NorGate(), [0, 2], 1,
                      ["NOR", "A B | OUT", "00=1  01=0", "10=0  11=0"]),
        _gate_station(22, 6, [3, 2, 5], NandGate(), [0, 2], 1,
                      ["NAND", "A B | OUT", "00=1  01=1", "10=1  11=0"]),
        _gate_station(29, 6, [3, 2, 8], AndGate(), [0, 2], 1,
                      ["AND", "A B | OUT", "00=0  01=0", "10=0  11=1"]),

        # Logic classroom, row two.
        _gate_station(4, 20, [5, 2, 7], XorGate(), [0, 4], 2,
                      ["XOR", "A B | OUT", "00=0  01=1", "10=1  11=0"]),
        # z=19 keeps the XNOR sign south of the NOR station's lamp column.
        _gate_station(14, 19, [5, 2, 10], XnorGate(), [0, 4], 2,
                      ["XNOR", "A B | OUT", "00=1  01=0", "10=0  11=1"]),

        # Timing and memory stations.
        transform([24, 1, 17], 0, [1, 2, 5], TFlipFlop()),
        _pulse_input(24, 15),
        place_block([24, 1, 22], block("minecraft:deepslate_tiles")),
        transform([24, 2, 22], 0, [1, 1, 1], RedstoneLamp()),
        _standing_sign([24, 1, 28],
                       ["T FLIP-FLOP", "Press to toggle", "Bulb remembers", "Lamp = Q"],
                       color="light_blue"),

        # x=32 keeps the pulse button clear of the AND station's output lamp.
        transform([32, 1, 17], 0, [4, 2, 9], PulseExtender(16)),
        _pulse_input(33, 15),
        place_block([33, 1, 26], block("minecraft:deepslate_tiles")),
        transform([33, 2, 26], 0, [1, 1, 1], RedstoneLamp()),
        _standing_sign([33, 1, 28],
                       ["PULSE EXTENDER", "Press orange", "Output stays on", "for 16 ticks"],
                       color="light_blue"),

        transform([37, 1, 17], 0, [5, 2, 8], RedstoneClock(4)),
        _pulse_input(38, 15),
        place_block([41, 1, 25], block("minecraft:deepslate_tiles")),
        transform([41, 2, 25], 0, [1, 1, 1], RedstoneLamp()),
        _standing_sign([39, 1, 28],
                       ["REPEATER CLOCK", "Button starts", "Center lever", "locks/pauses"],
                       color="light_blue"),

        _standing_sign([47, 1, 28],
                       ["MEMORY DEMOS", "Bulb toggles", "Clock circulates", "Lever pauses it"],
                       color="light_blue"),

        # Practical applications.
        transform([2, 1, 34], 0, [7, 2, 3], HopperClock()),
        _standing_sign([5, 1, 32],
                       ["HOPPER CLOCK", "Items move", "Comparators alternate", "More = slower"],
                       color="orange"),

        transform([12, 1, 34], 0, [3, 3, 4], PistonTrapdoor(3)),
        _standing_sign([13, 1, 32],
                       ["PISTON BRIDGE", "Top lever", "ON = closed", "OFF = open"],
                       color="orange"),

        transform([20, 1, 34], 0, [6, 4, 3], PistonDoor()),
        _standing_sign([22, 1, 32],
                       ["2x2 PISTON DOOR", "Top lever", "ON = closed", "OFF = open"],
                       color="orange"),

        transform([30, 1, 34], 0, [3, 5, 6], ItemSorter()),
        _standing_sign([31, 1, 32],
                       ["ITEM SORTER", "Redstone filtered", "Other items pass", "41+4 filter"],
                       color="orange"),

        transform([38, 1, 34], 0, [5, 3, 2], LampMatrix(5, 3)),
        _standing_sign([40, 1, 32],
                       ["LAMP MATRIX", "Passive display", "Drive backing", "from rear"],
                       color="orange"),

        transform([47, 1, 34], 0, [1, 1, 1],
                  WeightedPressurePlate(power=0)),
        transform([47, 1, 35], 0, [1, 1, 1], RedstoneWire()),
        place_block([47, 1, 36], block("minecraft:redstone_lamp", {"lit": "false"})),
        _standing_sign([47, 1, 32],
                       ["ANALOG INPUT", "Weighted plate", "Power is 0-15", "Lamp is output"],
                       color="orange"),
    ]
    return component(
        name="InteractiveRedstoneGallery",
        props={},
        min_size=[WIDTH, HEIGHT, LENGTH],
        metadata={"ground_level": 1},
        body=group(parts),
    )


def build():
    return InteractiveGallery()
