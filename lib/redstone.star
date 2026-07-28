# Redstone components: parts, wiring, logic gates, circuits, and contraptions.
#
# Conventions (in addition to the library-wide ones):
#   - Everything draws from [0, 0, 0] and faces +Z (south) at rotation 0.
#   - Signal flows along +Z. Directional parts default facing="south"; on a
#     gate, inputs enter at the north edge (z=0) and the output leaves at the
#     south edge (z=max-1).
#   - Gates and circuits carry their own solid base slab at y=0 (material is the
#     `base` prop, default smooth_stone) with the redstone logic at y=1. Bulk
#     blocks are STRUCTURE phase; dust/torches/repeaters that sit on top are
#     FIXTURE phase, so they land on air and never overwrite the slab.
#   - Rotation is handled by the engine: `facing` (cardinal), the dust
#     connection keys north/east/south/west, and `axis` all rotate correctly;
#     up/down facings and lever/button `face` are left alone.
#
# Public circuits expose inputs on their north edge and outputs on their south
# edge.  They deliberately favor clear, isolated, rotation-safe layouts over
# minimum block count.

_BASE = "minecraft:smooth_stone"
_DUST = "minecraft:redstone_wire"
_TORCH = "minecraft:redstone_torch"
_WALL_TORCH = "minecraft:redstone_wall_torch"


def _b(value):
    """Coerce a Starlark bool to a Minecraft state string."""
    if value:
        return "true"
    return "false"


def _require_range(name, value, low, high):
    if value < low or value > high:
        fail("%s must be between %s and %s" % (name, low, high))


def _require_positive(name, value):
    if value < 1:
        fail("%s must be at least 1" % name)


def _require_cardinal(name, value):
    if value not in ["north", "east", "south", "west"]:
        fail("%s must be north, east, south, or west" % name)


def _require_facing(name, value):
    if value not in ["down", "up", "north", "east", "south", "west"]:
        fail("%s must be down, up, north, east, south, or west" % name)


def _diode_state_facing(output_facing):
    """Java diode states point from output toward input."""
    return {
        "north": "south",
        "east": "west",
        "south": "north",
        "west": "east",
    }[output_facing]


def _slab(width, length, material):
    """Solid base platform at y=0 spanning the footprint."""
    return fill_region([0, 0, 0], [width, 1, length], block(material))


def _dust(x, z, y=1):
    """A single redstone dust cell (auto-connects in-game)."""
    return place_block([x, y, z], block(_DUST), phase="fixture")


def _dust_run_z(x, z0, z1, y=1):
    """Dust line along +Z from z0 (inclusive) to z1 (exclusive)."""
    return fill_region([x, y, z0], [x + 1, y + 1, z1], block(_DUST), phase="fixture")


def _dust_run_x(x0, x1, z, y=1):
    """Dust line along +X from x0 (inclusive) to x1 (exclusive)."""
    return fill_region([x0, y, z], [x1, y + 1, z + 1], block(_DUST), phase="fixture")


def _wall_torch(x, z, facing, lit=True, y=1):
    """Redstone wall torch attached to the block behind it (opposite `facing`)."""
    return place_block([x, y, z], block(_WALL_TORCH, {"facing": facing, "lit": _b(lit)}),
                       phase="fixture")


# --------------------------------------------------------------------------- #
# Parts: thin, correctly-oriented wrappers around single redstone blocks.
# --------------------------------------------------------------------------- #


def RedstoneTorch(lit=True):
    """Standing redstone torch (place on top of a block)."""
    return component(
        name="RedstoneTorch",
        props={"lit": lit},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block(_TORCH, {"lit": _b(lit)}), phase="fixture"),
    )


def RedstoneWallTorch(facing="south", lit=True):
    """Wall torch whose visible/output side points toward `facing`."""
    _require_cardinal("facing", facing)
    return component(
        name="RedstoneWallTorch",
        props={"facing": facing, "lit": lit},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(_WALL_TORCH, {"facing": facing, "lit": _b(lit)}),
                         phase="fixture"),
    )


def RedstoneWire(power=0):
    """One redstone-wire cell. Connections are recalculated in-world."""
    _require_range("power", power, 0, 15)
    return component(
        name="RedstoneWire",
        props={"power": power},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(_DUST, {"power": str(power)}),
                         phase="fixture"),
    )


def RedstoneLamp(lit=False):
    """Redstone lamp block."""
    return component(
        name="RedstoneLamp",
        props={"lit": lit},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block("minecraft:redstone_lamp", {"lit": _b(lit)})),
    )


def RedstoneBlock():
    """Solid always-on power source."""
    return component(
        name="RedstoneBlock",
        props={},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block("minecraft:redstone_block")),
    )


def Lever(face="floor", facing="south", powered=False):
    """Lever. `face` is floor/wall/ceiling; `facing` is the cardinal it points."""
    if face not in ["floor", "wall", "ceiling"]:
        fail("face must be floor, wall, or ceiling")
    _require_cardinal("facing", facing)
    return component(
        name="Lever",
        props={"face": face, "facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:lever",
                               {"face": face, "facing": facing, "powered": _b(powered)}),
                         phase="fixture"),
    )


def Button(material="minecraft:stone_button", face="floor", facing="south", powered=False):
    """Button of any button material; same face/facing model as Lever."""
    if face not in ["floor", "wall", "ceiling"]:
        fail("face must be floor, wall, or ceiling")
    _require_cardinal("facing", facing)
    return component(
        name="Button",
        props={"material": material, "face": face, "facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"face": face, "facing": facing, "powered": _b(powered)}),
                         phase="fixture"),
    )


def PressurePlate(material="minecraft:stone_pressure_plate", powered=False):
    """Pressure plate; lay one Y above the floor."""
    if material in ["minecraft:light_weighted_pressure_plate", "minecraft:heavy_weighted_pressure_plate"]:
        fail("weighted plates must use WeightedPressurePlate")
    return component(
        name="PressurePlate",
        props={"material": material, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block(material, {"powered": _b(powered)}), phase="fixture"),
    )


def WeightedPressurePlate(material="minecraft:light_weighted_pressure_plate", power=0):
    """Light/heavy weighted plate with an analog power level from 0 to 15."""
    if material not in ["minecraft:light_weighted_pressure_plate", "minecraft:heavy_weighted_pressure_plate"]:
        fail("material must be a light or heavy weighted pressure plate")
    _require_range("power", power, 0, 15)
    return component(
        name="WeightedPressurePlate",
        props={"material": material, "power": power},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block(material, {"power": str(power)}), phase="fixture"),
    )


def Repeater(delay=1, facing="south", locked=False, powered=False):
    """Repeater; output points toward `facing`. `delay` is 1-4 ticks."""
    _require_range("delay", delay, 1, 4)
    _require_cardinal("facing", facing)
    return component(
        name="Repeater",
        props={"delay": delay, "facing": facing, "locked": locked, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:repeater",
                               {"delay": str(delay), "facing": _diode_state_facing(facing),
                                "locked": _b(locked), "powered": _b(powered)}),
                         phase="fixture"),
    )


def Comparator(mode="compare", facing="south", powered=False):
    """Comparator; `mode` is compare/subtract, output points toward `facing`."""
    if mode not in ["compare", "subtract"]:
        fail("mode must be compare or subtract")
    _require_cardinal("facing", facing)
    return component(
        name="Comparator",
        props={"mode": mode, "facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:comparator",
                               {"mode": mode, "facing": _diode_state_facing(facing),
                                "powered": _b(powered)}),
                         phase="fixture"),
    )


def Observer(facing="south", powered=False):
    """Observer; the sensing face points toward `facing`, pulse leaves the back."""
    _require_facing("facing", facing)
    return component(
        name="Observer",
        props={"facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:observer", {"facing": facing, "powered": _b(powered)})),
    )


def Piston(sticky=False, facing="south", extended=False):
    """Piston facing `facing`; extended body/head pairs are atomic."""
    _require_facing("facing", facing)
    body_type = "minecraft:sticky_piston" if sticky else "minecraft:piston"
    head_variant = "sticky" if sticky else "normal"
    if extended:
        offsets = {
            "down": [[0, 1, 0], [0, 0, 0], [1, 2, 1]],
            "up": [[0, 0, 0], [0, 1, 0], [1, 2, 1]],
            "north": [[0, 0, 1], [0, 0, 0], [1, 1, 2]],
            "south": [[0, 0, 0], [0, 0, 1], [1, 1, 2]],
            "west": [[1, 0, 0], [0, 0, 0], [2, 1, 1]],
            "east": [[0, 0, 0], [1, 0, 0], [2, 1, 1]],
        }
        body_pos, head_pos, size = offsets[facing]
        return component(
            name="Piston",
            props={"sticky": sticky, "facing": facing, "extended": extended},
            min_size=size,
            body=place_assembly(
                pos=[0, 0, 0],
                name="piston",
                size=size,
                blocks=[
                    {"pos": body_pos, "block": block(body_type, {"facing": facing, "extended": "true"})},
                    {"pos": head_pos, "block": block("minecraft:piston_head",
                                                     {"facing": facing, "type": head_variant, "short": "false"})},
                ],
            ),
        )
    return component(
        name="Piston",
        props={"sticky": sticky, "facing": facing, "extended": extended},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block(body_type, {"facing": facing, "extended": "false"})),
    )


def Dispenser(items=None, facing="south"):
    """Dispenser facing `facing`; `items` preloads its 9 slots (see container_nbt)."""
    _require_facing("facing", facing)
    return component(
        name="Dispenser",
        props={"items": items or [], "facing": facing},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:dispenser", {"facing": facing, "triggered": "false"},
                               nbt=container_nbt(items, id="minecraft:dispenser"))),
    )


def Dropper(items=None, facing="south"):
    """Dropper facing `facing`; same item model as Dispenser."""
    _require_facing("facing", facing)
    return component(
        name="Dropper",
        props={"items": items or [], "facing": facing},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:dropper", {"facing": facing, "triggered": "false"},
                               nbt=container_nbt(items, id="minecraft:dropper"))),
    )


def Hopper(items=None, facing="down"):
    """Hopper feeding toward `facing` (down or a cardinal, never up)."""
    if facing not in ["down", "north", "east", "south", "west"]:
        fail("hopper facing must be down or cardinal")
    return component(
        name="Hopper",
        props={"items": items or [], "facing": facing},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:hopper", {"facing": facing, "enabled": "true"},
                               nbt=container_nbt(items, id="minecraft:hopper"))),
    )


def NoteBlock(instrument="harp", note=0, powered=False):
    """Note block. `note` is 0-24 (pitch); `instrument` sets the timbre."""
    _require_range("note", note, 0, 24)
    return component(
        name="NoteBlock",
        props={"instrument": instrument, "note": note, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:note_block",
                               {"instrument": instrument, "note": str(note), "powered": _b(powered)})),
    )


def TargetBlock():
    """Target block (emits redstone when hit by a projectile)."""
    return component(
        name="TargetBlock",
        props={},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block("minecraft:target", {"power": "0"})),
    )


def DaylightDetector(inverted=False):
    """Daylight sensor; `inverted` makes it a night sensor."""
    return component(
        name="DaylightDetector",
        props={"inverted": inverted},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:daylight_detector", {"inverted": _b(inverted), "power": "0"})),
    )


def CopperBulb(material="minecraft:copper_bulb", lit=False, powered=False):
    """Pulse-toggle memory/light block; oxidation is selected by `material`."""
    valid = [
        "minecraft:copper_bulb",
        "minecraft:exposed_copper_bulb",
        "minecraft:weathered_copper_bulb",
        "minecraft:oxidized_copper_bulb",
        "minecraft:waxed_copper_bulb",
        "minecraft:waxed_exposed_copper_bulb",
        "minecraft:waxed_weathered_copper_bulb",
        "minecraft:waxed_oxidized_copper_bulb",
    ]
    if material not in valid:
        fail("material must be a copper bulb block")
    return component(
        name="CopperBulb",
        props={"material": material, "lit": lit, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block(material, {"lit": _b(lit), "powered": _b(powered)})),
    )


# --------------------------------------------------------------------------- #
# Wiring: carry a signal across distance or up a level.
# --------------------------------------------------------------------------- #


def RedstoneLine(length, base=_BASE):
    """Base row along +Z with a dust line on top."""
    _require_positive("length", length)
    return component(
        name="RedstoneLine",
        props={"length": length, "base": base},
        min_size=[1, 2, length],
        body=group([
            fill_region([0, 0, 0], [1, 1, length], block(base)),
            _dust_run_z(0, 0, length),
        ]),
    )


def VerticalRedstone(height, base=_BASE):
    """Staircase of blocks rising one level per step along +Z, dust on each."""
    _require_positive("height", height)
    parts = []
    for i in range(height):
        parts.append(place_block([0, i, i], block(base)))
        parts.append(place_block([0, i + 1, i], block(_DUST), phase="fixture"))
    return component(
        name="VerticalRedstone",
        props={"height": height, "base": base},
        min_size=[1, height + 1, height],
        body=group(parts),
    )


# --------------------------------------------------------------------------- #
# Logic gates. Inputs enter at z=0 (north); output leaves at the south edge.
# A raised block (y=1) fed by a dust line is inverted by a south-facing wall
# torch on its front face — the shared inverter primitive for every gate.
# --------------------------------------------------------------------------- #


def _inverter(x, z, base):
    """Block at (x,1,z) inverted by a south wall torch at (x,1,z+1).

    Input dust points into the block from the north (z-1); the torch output
    (=NOT input) leaves to the south (z+1). Returns the parts list."""
    return [
        place_block([x, 1, z], block(base)),
        _wall_torch(x, z + 1, "south"),
    ]


def NotGate(base=_BASE):
    """Inverter: output = NOT input. Input at z=0, output at z=3."""
    return component(
        name="NotGate",
        props={"base": base},
        min_size=[1, 2, 4],
        body=group(
            [_slab(1, 4, base), _dust(0, 0)] + _inverter(0, 1, base) + [_dust(0, 3)]
        ),
    )


def OrGate(base=_BASE):
    """Output = A OR B. Repeaters keep the two north inputs isolated."""
    return component(
        name="OrGate",
        props={"base": base},
        min_size=[3, 2, 4],
        body=group([
            _slab(3, 4, base),
            _dust(0, 0),
            _dust(2, 0),
            place_block([0, 1, 1],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                        phase="fixture"),
            place_block([2, 1, 1],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                        phase="fixture"),
            _dust_run_x(0, 3, 2),
            _dust(1, 3),
        ]),
    )


def NorGate(base=_BASE):
    """Output = NOT (A OR B). Inputs at north edge; output at south edge."""
    return component(
        name="NorGate",
        props={"base": base},
        min_size=[3, 2, 7],
        body=group(
            [
                _slab(3, 7, base),
                _dust(0, 0),
                _dust(2, 0),
                place_block([0, 1, 1],
                            block("minecraft:repeater",
                                  {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                            phase="fixture"),
                place_block([2, 1, 1],
                            block("minecraft:repeater",
                                  {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                            phase="fixture"),
                _dust_run_x(0, 3, 2),
                _dust(1, 3),
            ]
            + _inverter(1, 4, base)
            + [_dust(1, 6)]
        ),
    )


def NandGate(base=_BASE):
    """Output = NOT A OR NOT B. Each input is inverted, then the two are OR'd."""
    return component(
        name="NandGate",
        props={"base": base},
        min_size=[3, 2, 5],
        body=group(
            [_slab(3, 5, base), _dust(0, 0), _dust(2, 0)]   # inputs A, B
            + _inverter(0, 1, base)     # NOT A -> torch output at (0,1,2)
            + _inverter(2, 1, base)     # NOT B -> torch output at (2,1,2)
            + [
                _dust_run_x(0, 3, 3),   # OR the two inverted outputs
                _dust(1, 4),            # output
            ]
        ),
    )


def AndGate(base=_BASE):
    """Output = A AND B. NAND of the inputs, then a final inverter."""
    return component(
        name="AndGate",
        props={"base": base},
        min_size=[3, 2, 8],
        body=group(
            [_slab(3, 8, base), _dust(0, 0), _dust(2, 0)]
            + _inverter(0, 1, base)     # NOT A  (block z=1, torch z=2)
            + _inverter(2, 1, base)     # NOT B
            + [
                _dust_run_x(0, 3, 3),   # NAND = NOT A OR NOT B
                _dust(1, 4),            # feed final inverter
            ]
            + _inverter(1, 5, base)     # invert NAND -> AND  (block z=5, torch z=6)
            + [_dust(1, 7)]             # output
        ),
    )


def _xor_core(base):
    """Torch XOR: NOT(A OR NOR(A,B)) OR NOT(B OR NOR(A,B))."""
    return [
        _dust(0, 0), _dust(4, 0),
        _dust(0, 1), _dust(4, 1),
        # Isolated direct A/B feeds drive their blocks without an intervening
        # dust cell that can turn sideways toward the NOR branch.
        place_block([0, 1, 2],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "north",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        place_block([4, 1, 2],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "north",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        # A/B also merge through inward-facing repeaters to make NOR.
        place_block([1, 1, 0],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "west",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        place_block([3, 1, 0],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "east",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        _dust(2, 0), _dust(2, 1),
        place_block([2, 1, 2], block(base)),
        _wall_torch(2, 3, "south"),
        # The center torch drives each side block through an outward repeater;
        # unlike dust, this cannot turn away from the block it must power.
        place_block([1, 1, 3],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "east",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        place_block([3, 1, 3],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "west",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
        place_block([0, 1, 3], block(base)),
        place_block([4, 1, 3], block(base)),
        _wall_torch(0, 4, "south"),
        _wall_torch(4, 4, "south"),
        # OR the two product terms.
        _dust_run_x(0, 5, 5),
        place_block([2, 1, 6],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "north",
                           "locked": "false", "powered": "false"}),
                    phase="fixture"),
    ]


def XorGate(base=_BASE):
    """Output = A XOR B (on iff inputs differ)."""
    return component(
        name="XorGate",
        props={"base": base},
        min_size=[5, 2, 7],
        body=group([_slab(5, 7, base)] + _xor_core(base)),
    )


def XnorGate(base=_BASE):
    """Output = A XNOR B (on iff inputs match) = NOT (A XOR B)."""
    return component(
        name="XnorGate",
        props={"base": base},
        min_size=[5, 2, 10],
        body=group(
            [_slab(5, 10, base)]
            + _xor_core(base)
            + _inverter(2, 7, base)
            + [
                place_block([2, 1, 9],
                            block("minecraft:repeater",
                                  {"delay": "1", "facing": "north",
                                   "locked": "false", "powered": "false"}),
                            phase="fixture"),
            ]
        ),
    )


# --------------------------------------------------------------------------- #
# Simple circuits.
# --------------------------------------------------------------------------- #


def RedstoneClock(period=2, base=_BASE):
    """Four-repeater pulse loop with a one-way north input.

    The center lever locks the north ring repeater, pausing its current state.
    `period` is the delay of each ring repeater (1-4 ticks)."""
    _require_range("period", period, 1, 4)
    return component(
        name="RedstoneClock",
        props={"period": period, "base": base},
        min_size=[5, 2, 8],
        body=group([
            _slab(5, 8, base),
            # Start pulse enters through a diode, then travels clockwise.
            _dust(1, 0),
            place_block([1, 1, 1], block("minecraft:repeater",
                                         {"delay": "1", "facing": "north",
                                          "locked": "false", "powered": "false"}), phase="fixture"),
            _dust(0, 2), _dust(1, 2), _dust(3, 2), _dust(4, 2),
            _dust(4, 3), _dust(4, 5),
            _dust(4, 6), _dust(3, 6), _dust(1, 6), _dust(0, 6),
            _dust(0, 5), _dust(0, 3),
            place_block([2, 1, 2], block("minecraft:repeater",
                                         {"delay": str(period), "facing": "west",
                                          "locked": "false", "powered": "false"}), phase="fixture"),
            place_block([4, 1, 4], block("minecraft:repeater",
                                         {"delay": str(period), "facing": "north",
                                          "locked": "false", "powered": "false"}), phase="fixture"),
            place_block([2, 1, 6], block("minecraft:repeater",
                                         {"delay": str(period), "facing": "east",
                                          "locked": "false", "powered": "false"}), phase="fixture"),
            place_block([0, 1, 4], block("minecraft:repeater",
                                         {"delay": str(period), "facing": "south",
                                          "locked": "false", "powered": "false"}), phase="fixture"),
            # Center lever drives a repeater into the side of the north ring
            # repeater, freezing that stage.
            place_block([2, 1, 4],
                        block("minecraft:lever",
                              {"face": "floor", "facing": "south", "powered": "false"}),
                        phase="fixture"),
            place_block([2, 1, 3],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "south", "locked": "false", "powered": "false"}),
                        phase="fixture"),
            # Explicit output avoids relying on dust's connection shape.
            place_block([4, 1, 7],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "north",
                               "locked": "false", "powered": "false"}),
                        phase="fixture"),
        ]),
    )


def HopperClock(items=None, base=_BASE):
    """Adjustable hopper clock with alternating comparator outputs."""
    if items == None:
        items = [{"id": "minecraft:redstone", "count": 16}]
    return component(
        name="HopperClock",
        props={"items": items, "base": base},
        min_size=[7, 2, 3],
        body=group([
            _slab(7, 3, base),
            place_block([2, 1, 1],
                        block("minecraft:hopper", {"facing": "east", "enabled": "true"},
                              nbt=container_nbt(items, id="minecraft:hopper"))),
            place_block([3, 1, 1],
                        block("minecraft:hopper", {"facing": "west", "enabled": "true"},
                              nbt=container_nbt(None, id="minecraft:hopper"))),
            place_block([1, 1, 1],
                        block("minecraft:comparator",
                              {"mode": "compare", "facing": "east", "powered": "false"}),
                        phase="fixture"),
            place_block([4, 1, 1],
                        block("minecraft:comparator",
                              {"mode": "compare", "facing": "west", "powered": "false"}),
                        phase="fixture"),
            _dust(0, 1), _dust(5, 1),
            place_block([1, 1, 0],
                        block("minecraft:sticky_piston", {"facing": "east", "extended": "false"})),
            place_block([4, 1, 0],
                        block("minecraft:sticky_piston", {"facing": "west", "extended": "false"})),
            place_block([3, 1, 0], block("minecraft:redstone_block")),
            _dust(0, 2), _dust(6, 2),
        ]),
    )


def TFlipFlop(base=_BASE):
    """Copper-bulb toggle memory. Input is north; comparator output is south."""
    return component(
        name="TFlipFlop",
        props={"base": base},
        min_size=[1, 2, 5],
        body=group([
            _slab(1, 5, base),
            _dust(0, 0),
            place_block([0, 1, 1],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                        phase="fixture"),
            place_block([0, 1, 2],
                        block("minecraft:copper_bulb", {"lit": "false", "powered": "false"})),
            place_block([0, 1, 3],
                        block("minecraft:comparator",
                              {"mode": "compare", "facing": "north", "powered": "false"}),
                        phase="fixture"),
            _dust(0, 4),
        ]),
    )


def PulseExtender(ticks=4, base=_BASE):
    """One-shot: direct and delayed rising edges toggle a copper bulb.

    The output stays on for `ticks` repeater ticks. The input pulse must be
    shorter than `ticks` so the bulb is unpowered before the delayed edge."""
    _require_positive("ticks", ticks)
    stages = (ticks + 3) // 4
    parts = [_slab(4, stages + 5, base), _dust_run_x(1, 4, 0)]
    parts.append(_dust_run_z(1, 1, stages + 1))
    remaining = ticks
    for i in range(stages):
        delay = min(remaining, 4)
        parts.append(place_block([3, 1, i + 1],
                                 block("minecraft:repeater",
                                       {"delay": str(delay), "facing": "north",
                                        "locked": "false", "powered": "false"}),
                                 phase="fixture"))
        remaining -= delay
    bulb_z = stages + 2
    parts.extend([
        place_block([1, 1, bulb_z - 1],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "north", "locked": "false", "powered": "false"}),
                    phase="fixture"),
        _dust(3, bulb_z - 1),
        _dust(3, bulb_z),
        place_block([2, 1, bulb_z],
                    block("minecraft:repeater",
                          {"delay": "1", "facing": "east", "locked": "false", "powered": "false"}),
                    phase="fixture"),
        place_block([1, 1, bulb_z],
                    block("minecraft:copper_bulb", {"lit": "false", "powered": "false"})),
        place_block([1, 1, bulb_z + 1],
                    block("minecraft:comparator",
                          {"mode": "compare", "facing": "north", "powered": "false"}),
                    phase="fixture"),
        _dust(1, bulb_z + 2),
    ])
    return component(
        name="PulseExtender",
        props={"ticks": ticks, "base": base},
        min_size=[4, 2, stages + 5],
        body=group(parts),
    )


# --------------------------------------------------------------------------- #
# Practical assemblies.
# --------------------------------------------------------------------------- #


def LampMatrix(width, height, lamp="minecraft:redstone_lamp", base=_BASE):
    """A `width` x `height` wall of lamps on a one-block backing — a display
    panel whose backing is driven by wiring supplied by the caller."""
    _require_positive("width", width)
    _require_positive("height", height)
    return component(
        name="LampMatrix",
        props={"width": width, "height": height, "lamp": lamp, "base": base},
        min_size=[width, height, 2],
        body=group([
            fill_region([0, 0, 0], [width, height, 1], block(base)),                       # backing
            fill_region([0, 0, 1], [width, height, 2], block(lamp, {"lit": "false"})),     # lamp face
        ]),
    )


def PistonTrapdoor(width=2, base=_BASE):
    """Retracting floor bridge. Power the dust above the piston row to close."""
    _require_positive("width", width)
    parts = [fill_region([0, 0, 0], [width, 1, 4], block(base))]
    for x in range(width):
        parts.append(place_block([x, 1, 0],
                                 block("minecraft:sticky_piston",
                                       {"facing": "south", "extended": "false"})))
        parts.append(place_block([x, 1, 1], block(base)))
        if x == 0:
            parts.append(place_block([x, 2, 0],
                                     block("minecraft:lever",
                                           {"face": "floor", "facing": "south", "powered": "false"}),
                                     phase="fixture"))
        else:
            parts.append(_dust(x, 0, y=2))
    return component(
        name="PistonTrapdoor",
        props={"width": width, "base": base},
        min_size=[width, 3, 4],
        body=group(parts),
    )


def PistonDoor(base=_BASE, door="minecraft:smooth_stone"):
    """2x2 side-piston door. Power the raised north control line to close."""
    parts = [
        fill_region([0, 0, 0], [6, 1, 3], block(base)),
        fill_region([0, 1, 0], [6, 3, 1], block(base)),
        place_block([0, 3, 0],
                    block("minecraft:lever",
                          {"face": "floor", "facing": "south", "powered": "false"}),
                    phase="fixture"),
        _dust_run_x(1, 6, 0, y=3),
    ]
    for y in range(1, 3):
        parts.append(place_block([0, y, 1],
                                 block("minecraft:sticky_piston",
                                       {"facing": "east", "extended": "false"})))
        parts.append(place_block([1, y, 1], block(door)))
        parts.append(place_block([5, y, 1],
                                 block("minecraft:sticky_piston",
                                       {"facing": "west", "extended": "false"})))
        parts.append(place_block([4, y, 1], block(door)))
    return component(
        name="PistonDoor",
        props={"base": base, "door": door},
        min_size=[6, 4, 3],
        body=group(parts),
    )


def ItemSorter(target="minecraft:redstone",
               filler="minecraft:light_gray_stained_glass_pane",
               base=_BASE):
    """Overflow-safe single-item filter.

    Feed enters the top hopper at north. Matching items leave the lower hopper
    to the south; non-matching items continue through the upper hopper."""
    if target == filler:
        fail("item sorter target and filler must differ")
    filter_items = [
        {"id": target, "count": 41, "slot": 0},
        {"id": filler, "count": 1, "slot": 1},
        {"id": filler, "count": 1, "slot": 2},
        {"id": filler, "count": 1, "slot": 3},
        {"id": filler, "count": 1, "slot": 4},
    ]
    return component(
        name="ItemSorter",
        props={"target": target, "filler": filler, "base": base},
        min_size=[3, 5, 6],
        body=group([
            fill_region([0, 0, 0], [3, 1, 6], block(base)),
            # Transport stream and filter inventory.
            place_block([1, 4, 1], block("minecraft:hopper", {"facing": "south", "enabled": "true"},
                                         nbt=container_nbt(None, id="minecraft:hopper"))),
            place_block([1, 3, 1], block("minecraft:hopper", {"facing": "north", "enabled": "true"},
                                         nbt=container_nbt(filter_items, id="minecraft:hopper"))),
            # Locked extraction hopper; its south face is the filtered output.
            place_block([1, 2, 1], block("minecraft:hopper", {"facing": "south", "enabled": "false"},
                                         nbt=container_nbt(None, id="minecraft:hopper"))),
            place_block([1, 3, 2], block("minecraft:comparator",
                                         {"mode": "compare", "facing": "north", "powered": "false"}),
                        phase="fixture"),
            place_block([1, 3, 3], block(_DUST), phase="fixture"),
            place_block([1, 2, 4], block(_DUST), phase="fixture"),
            place_block([1, 1, 4],
                        block("minecraft:repeater",
                              {"delay": "1", "facing": "south",
                               "locked": "false", "powered": "false"}),
                        phase="fixture"),
            place_block([1, 1, 3], block(base)),
            _wall_torch(1, 2, "north", y=2),
        ]),
    )
