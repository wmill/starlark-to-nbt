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
# The gates' *structure* (block types, states, positions) is asserted by tests,
# but redstone *timing/behavior* can only be confirmed in-game. XOR/XNOR and the
# big contraptions in particular are best double-checked in a 1.21.7 world.

_BASE = "minecraft:smooth_stone"
_DUST = "minecraft:redstone_wire"
_TORCH = "minecraft:redstone_torch"
_WALL_TORCH = "minecraft:redstone_wall_torch"


def _b(value):
    """Coerce a Starlark bool to a Minecraft state string."""
    if value:
        return "true"
    return "false"


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
    return component(
        name="PressurePlate",
        props={"material": material, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0], block(material, {"powered": _b(powered)}), phase="fixture"),
    )


def Repeater(delay=1, facing="south", locked=False, powered=False):
    """Repeater; output points toward `facing`. `delay` is 1-4 ticks."""
    return component(
        name="Repeater",
        props={"delay": delay, "facing": facing, "locked": locked, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:repeater",
                               {"delay": str(delay), "facing": facing,
                                "locked": _b(locked), "powered": _b(powered)}),
                         phase="fixture"),
    )


def Comparator(mode="compare", facing="south", powered=False):
    """Comparator; `mode` is compare/subtract, output points toward `facing`."""
    return component(
        name="Comparator",
        props={"mode": mode, "facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:comparator",
                               {"mode": mode, "facing": facing, "powered": _b(powered)}),
                         phase="fixture"),
    )


def Observer(facing="south", powered=False):
    """Observer; the sensing face points toward `facing`, pulse leaves the back."""
    return component(
        name="Observer",
        props={"facing": facing, "powered": powered},
        min_size=[1, 1, 1],
        body=place_block([0, 0, 0],
                         block("minecraft:observer", {"facing": facing, "powered": _b(powered)})),
    )


def Piston(sticky=False, facing="south", extended=False):
    """Piston facing `facing`. When `extended`, the head is placed one block
    ahead (assumes facing="south" for standalone; rotate the whole component
    for other directions)."""
    body_type = "minecraft:sticky_piston" if sticky else "minecraft:piston"
    head_variant = "sticky" if sticky else "normal"
    if extended:
        return component(
            name="Piston",
            props={"sticky": sticky, "facing": facing, "extended": extended},
            min_size=[1, 1, 2],
            body=place_assembly(
                pos=[0, 0, 0],
                name="piston",
                size=[1, 1, 2],
                blocks=[
                    {"pos": [0, 0, 0], "block": block(body_type, {"facing": facing, "extended": "true"})},
                    {"pos": [0, 0, 1], "block": block("minecraft:piston_head",
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


# --------------------------------------------------------------------------- #
# Wiring: carry a signal across distance or up a level.
# --------------------------------------------------------------------------- #


def RedstoneLine(length, base=_BASE):
    """Base row along +Z with a dust line on top."""
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
    """Output = A OR B. Inputs at (0,z0) and (2,z0); output at (1,z2)."""
    return component(
        name="OrGate",
        props={"base": base},
        min_size=[3, 2, 3],
        body=group([
            _slab(3, 3, base),
            _dust_run_x(0, 3, 0),       # north bus links both inputs
            _dust(1, 1),                # merge
            _dust(1, 2),                # output
        ]),
    )


def NorGate(base=_BASE):
    """Output = NOT (A OR B). Inputs at north edge; output at south edge."""
    return component(
        name="NorGate",
        props={"base": base},
        min_size=[3, 2, 5],
        body=group(
            [
                _slab(3, 5, base),
                _dust_run_x(0, 3, 0),   # inputs A (x=0) and B (x=2)
                _dust(1, 1),            # merge -> points into inverter block
            ]
            + _inverter(1, 2, base)     # block (1,1,2) + torch (1,1,3)
            + [_dust(1, 4)]             # output
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


def _differencer(base):
    """Two subtract-comparators reading opposite input rails: the parts that
    turn |A - B| into an XOR core. Inputs at (0,0)/(2,0); XOR core out at (1,4).

    NOTE: comparator-based first draft — verify/tune the crossover in-game."""
    return [
        _dust(0, 0), _dust(2, 0),
        _dust(0, 1), _dust(2, 1),
        place_block([0, 1, 2],
                    block("minecraft:comparator", {"mode": "subtract", "facing": "south", "powered": "false"}),
                    phase="fixture"),
        place_block([2, 1, 2],
                    block("minecraft:comparator", {"mode": "subtract", "facing": "south", "powered": "false"}),
                    phase="fixture"),
        _dust(1, 2),                    # side coupling between the two comparators
        _dust_run_x(0, 3, 3),           # merge the two differences
        _dust(1, 4),
    ]


def XorGate(base=_BASE):
    """Output = A XOR B (on iff inputs differ). Comparator differencer.

    NOTE: first-draft schematic — confirm behavior in a 1.21.7 world."""
    return component(
        name="XorGate",
        props={"base": base},
        min_size=[3, 2, 5],
        body=group([_slab(3, 5, base)] + _differencer(base)),
    )


def XnorGate(base=_BASE):
    """Output = A XNOR B (on iff inputs match) = NOT (A XOR B).

    NOTE: XorGate core followed by an inverter; confirm behavior in-game."""
    return component(
        name="XnorGate",
        props={"base": base},
        min_size=[3, 2, 8],
        body=group(
            [_slab(3, 8, base)]
            + _differencer(base)        # XOR core out at (1,4)
            + _inverter(1, 5, base)     # invert -> XNOR  (block z=5, torch z=6)
            + [_dust(1, 7)]
        ),
    )


# --------------------------------------------------------------------------- #
# Simple circuits.
# --------------------------------------------------------------------------- #


def RedstoneClock(period=2, base=_BASE):
    """Repeater loop clock: a dust ring with a repeater setting the `period`
    (1-4 ticks per side). Toggle by breaking a dust cell."""
    return component(
        name="RedstoneClock",
        props={"period": period, "base": base},
        min_size=[3, 2, 3],
        body=group([
            _slab(3, 3, base),
            # Square dust loop around the perimeter...
            _dust_run_x(0, 3, 0),
            _dust_run_x(0, 3, 2),
            _dust(0, 1),
            # ...with one repeater in the ring to keep it oscillating.
            place_block([2, 1, 1],
                        block("minecraft:repeater",
                              {"delay": str(period), "facing": "north", "locked": "false", "powered": "false"}),
                        phase="fixture"),
        ]),
    )


def HopperClock(items=None, base=_BASE):
    """Two hoppers passing an item back and forth, each read by a comparator —
    a slow, adjustable clock. `items` seeds one hopper (more items = longer
    period)."""
    if items == None:
        items = ["minecraft:redstone"]
    return component(
        name="HopperClock",
        props={"items": items, "base": base},
        min_size=[2, 2, 2],
        body=group([
            _slab(2, 2, base),
            place_block([0, 1, 0],
                        block("minecraft:hopper", {"facing": "east", "enabled": "true"},
                              nbt=container_nbt(items, id="minecraft:hopper"))),
            place_block([1, 1, 0],
                        block("minecraft:hopper", {"facing": "west", "enabled": "true"},
                              nbt=container_nbt(None, id="minecraft:hopper"))),
            place_block([0, 1, 1],
                        block("minecraft:comparator",
                              {"mode": "compare", "facing": "south", "powered": "false"}),
                        phase="fixture"),
            place_block([1, 1, 1],
                        block("minecraft:comparator",
                              {"mode": "compare", "facing": "south", "powered": "false"}),
                        phase="fixture"),
        ]),
    )


def TFlipFlop(base=_BASE):
    """Toggle memory: each input pulse flips the stored output. Built around a
    sticky piston holding a redstone block against a read block.

    NOTE: a compact known layout; verify latch behavior in-game."""
    return component(
        name="TFlipFlop",
        props={"base": base},
        min_size=[3, 2, 3],
        body=group([
            _slab(3, 3, base),
            _dust(1, 0),                # trigger input
            place_block([1, 1, 1], block("minecraft:sticky_piston", {"facing": "up", "extended": "false"})),
            place_block([0, 1, 1], block("minecraft:redstone_block")),
            place_block([2, 1, 1], block("minecraft:redstone_lamp", {"lit": "false"})),
            _dust(1, 2),                # output tap
        ]),
    )


def PulseExtender(ticks=4, base=_BASE):
    """Monostable: a short input pulse is stretched to `ticks`. A repeater chain
    feeds an inverter loop; longer `ticks` = longer output pulse."""
    return component(
        name="PulseExtender",
        props={"ticks": ticks, "base": base},
        min_size=[1, 2, 4],
        body=group([
            _slab(1, 4, base),
            _dust(0, 0),                # input
            place_block([0, 1, 1],
                        block("minecraft:repeater",
                              {"delay": str(min(ticks, 4)), "facing": "south",
                               "locked": "false", "powered": "false"}),
                        phase="fixture"),
            place_block([0, 1, 2],
                        block("minecraft:comparator",
                              {"mode": "subtract", "facing": "south", "powered": "false"}),
                        phase="fixture"),
            _dust(0, 3),                # stretched output
        ]),
    )


# --------------------------------------------------------------------------- #
# Big contraptions. These place a plausible, rotation-safe structure; their
# mechanics should be verified (and likely fine-tuned) in a 1.21.7 world.
# --------------------------------------------------------------------------- #


def LampMatrix(width, height, lamp="minecraft:redstone_lamp", base=_BASE):
    """A `width` x `height` wall of lamps on a one-block backing — a display
    panel you can drive per-column/row with redstone."""
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
    """Flush floor trapdoor: a row of upward sticky pistons holding floor blocks,
    dropped when the input is powered. Draw at floor level; input dust at z=0.

    NOTE: verify piston timing/retraction in-game."""
    parts = [fill_region([0, 0, 0], [width, 1, 3], block(base))]   # frame base
    for x in range(width):
        parts.append(place_block([x, 1, 1], block("minecraft:sticky_piston", {"facing": "up", "extended": "false"})))
        parts.append(place_block([x, 2, 1], block(base)))          # flush lid block
    parts.append(_dust_run_x(0, width, 0))                          # control line
    return component(
        name="PistonTrapdoor",
        props={"width": width, "base": base},
        min_size=[width, 3, 3],
        body=group(parts),
    )


def PistonDoor(base=_BASE, door="minecraft:smooth_stone"):
    """Flush 2x2 double piston door: two sticky pistons per side push a stack of
    `door` blocks into the central 2x2 gap, retracting when the control line is
    powered. Faces +Z; the walkway is at x=[1,3), y=[1,3), z=1.

    NOTE: a compact schematic — verify the open/close cycle and control wiring
    in a 1.21.7 world."""
    parts = [fill_region([0, 0, 0], [4, 1, 3], block(base))]    # base pad under the mechanism
    for y in range(1, 3):
        # Left side pushes east into x=1; right side pushes west into x=2.
        parts.append(place_block([0, y, 1], block("minecraft:sticky_piston", {"facing": "east", "extended": "false"})))
        parts.append(place_block([1, y, 1], block(door)))       # left door block (closed position)
        parts.append(place_block([3, y, 1], block("minecraft:sticky_piston", {"facing": "west", "extended": "false"})))
        parts.append(place_block([2, y, 1], block(door)))       # right door block
    parts.append(_dust_run_x(0, 4, 0))                          # control line on the base top (z=0)
    return component(
        name="PistonDoor",
        props={"base": base, "door": door},
        min_size=[4, 3, 3],
        body=group(parts),
    )


def ItemSorter(target="minecraft:redstone", base=_BASE):
    """Single-item sorter: a hopper chain with a comparator reading a filtered
    hopper, ejecting the `target` item into an output dropper.

    NOTE: fill the filter hopper with 18 non-target + 1 target items in-game to
    tune; this places the structure only."""
    return component(
        name="ItemSorter",
        props={"target": target, "base": base},
        min_size=[3, 3, 2],
        body=group([
            fill_region([0, 0, 0], [3, 1, 2], block(base)),
            # Feed hopper -> filter hopper -> output dropper.
            place_block([0, 2, 0], block("minecraft:hopper", {"facing": "south", "enabled": "true"},
                                         nbt=container_nbt(None, id="minecraft:hopper"))),
            place_block([0, 1, 1], block("minecraft:hopper", {"facing": "east", "enabled": "true"},
                                         nbt=container_nbt([target], id="minecraft:hopper"))),
            place_block([1, 1, 1], block("minecraft:comparator",
                                         {"mode": "subtract", "facing": "east", "powered": "false"}),
                        phase="fixture"),
            place_block([2, 1, 1], block("minecraft:dropper", {"facing": "down", "triggered": "false"},
                                         nbt=container_nbt(None, id="minecraft:dropper"))),
        ]),
    )
