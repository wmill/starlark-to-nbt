# Spiral staircase inside a hollow shaft. repeat() can only tile identical
# copies of one child at fixed spacing along a single axis -- it cannot vary
# rotation or position per copy. A spiral needs both to change every step, so
# this is the idiomatic escape hatch: a plain for-loop computing each stair
# block's position and facing directly, rather than composing repeat()/
# transform() nodes.

SHAFT = 9
STEPS = 20
INSET = 2
WALL_MATERIAL = "minecraft:deepslate_tiles"
FLOOR_MATERIAL = "minecraft:polished_deepslate"
STAIR_MATERIAL = "minecraft:cobbled_deepslate_stairs"

# Facing per edge of the square walk -- the direction of travel, matching
# lib/structural.star's StraightStaircase convention that "facing" is the
# direction a stair ascends toward.
EDGE_FACINGS = ["east", "south", "west", "north"]


def build(shaft=SHAFT, steps=STEPS, inset=INSET):
    leg_length = shaft - 1 - 2 * inset
    wall_top = steps + 3
    parts = [
        fill_region([0, 0, 0], [shaft, 1, shaft], block(FLOOR_MATERIAL)),
        fill_region([0, 1, 0], [shaft, wall_top, 1], block(WALL_MATERIAL)),
        fill_region([0, 1, shaft - 1], [shaft, wall_top, shaft], block(WALL_MATERIAL)),
        fill_region([0, 1, 1], [1, wall_top, shaft - 1], block(WALL_MATERIAL)),
        fill_region([shaft - 1, 1, 1], [shaft, wall_top, shaft - 1], block(WALL_MATERIAL)),
    ]

    for step in range(steps):
        edge = (step // leg_length) % 4
        pos_along = step % leg_length
        facing = EDGE_FACINGS[edge]
        if edge == 0:
            sx, sz = inset + pos_along, inset
        elif edge == 1:
            sx, sz = shaft - 1 - inset, inset + pos_along
        elif edge == 2:
            sx, sz = shaft - 1 - inset - pos_along, shaft - 1 - inset
        else:
            sx, sz = inset, shaft - 1 - inset - pos_along
        material = block(STAIR_MATERIAL, {
            "facing": facing,
            "half": "bottom",
            "shape": "straight",
            "waterlogged": "false",
        })
        # Minecraft stairs cannot make a walkable one-block rise while also
        # turning 90 degrees. Use a full landing block where each new leg
        # begins so the player can step up and turn normally.
        if pos_along == 0:
            material = block(FLOOR_MATERIAL)
        parts.append(place_block([sx, step + 1, sz], material))

    return component(
        name="ProceduralSpiralStair",
        props={"shaft": shaft, "steps": steps, "inset": inset},
        min_size=[shaft, wall_top, shaft],
        body=group(parts),
    )
