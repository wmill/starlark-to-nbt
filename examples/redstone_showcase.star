# Redstone logic bench: a load()-composed slab of gates and parts, the
# reference example for the redstone library.
#
#   uv run starlark-to-nbt build examples/redstone_showcase.star \
#     --output redstone.nbt --debug-dir build/redstone
#
# Gate mechanics should be confirmed in a 1.21.7 world (see the redstone notes
# in docs/component-catalog.md); this example demonstrates composition and
# placement, laying every piece out on a shared foundation with no overlaps.

load("../lib/structural.star", "Foundation")
load("../lib/redstone.star",
     "AndGate", "OrGate", "XorGate", "NotGate",
     "RedstoneLine", "RedstoneLamp", "Lever", "Repeater")


def LogicBench(width, length):
    parts = [
        Foundation(width, length, material="minecraft:polished_andesite"),
        # A row of gates along +X, each on its own base slab, drawing +Z.
        transform([0, 1, 0], 0, [3, 2, 8], AndGate()),
        transform([4, 1, 0], 0, [3, 2, 3], OrGate()),
        transform([8, 1, 0], 0, [3, 2, 5], XorGate()),
        transform([12, 1, 0], 0, [1, 2, 4], NotGate()),
        # A signal run feeding across the bench, plus loose parts in free cells.
        transform([4, 1, 5], 0, [1, 2, 5], RedstoneLine(5)),
        transform([8, 1, 7], 0, [1, 1, 1], Repeater(2)),
        place_block([12, 1, 6], block("minecraft:redstone_lamp", {"lit": "false"})),
        LeverOn([13, 1, 6]),
    ]
    return component(
        name="LogicBench",
        props={"width": width, "length": length},
        min_size=[width, 3, length],
        body=group(parts),
    )


def LeverOn(pos):
    return transform(pos, 0, [1, 1, 1], Lever(powered=True))


def build(width=14, length=13):
    return LogicBench(width, length)
