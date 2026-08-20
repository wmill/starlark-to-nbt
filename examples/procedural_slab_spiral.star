# Freestanding round spiral staircase. The footprint is a circular annulus,
# split into radial wedges by choosing the nearest direction for each cell.
# Alternating bottom and top slabs raises the walking surface half a block per
# wedge, producing a broad corkscrew with a hollow centre.

RADIUS = 12
INNER_RADIUS = 4
TURNS = 2
SLAB = "minecraft:smooth_stone_slab"

# Sixteen unit directions, scaled to integers because the Starlark runtime has
# no trigonometric functions. The order turns clockwise from +X/east toward
# +Z/south when viewed from above.
STEP_DIRECTIONS = [
    [1000, 0], [924, 383], [707, 707], [383, 924],
    [0, 1000], [-383, 924], [-707, 707], [-924, 383],
    [-1000, 0], [-924, -383], [-707, -707], [-383, -924],
    [0, -1000], [383, -924], [707, -707], [924, -383],
]


def nearest_step(dx, dz):
    """Return the clockwise wedge whose direction is closest to (dx, dz)."""
    best_step = 0
    best_dot = dx * STEP_DIRECTIONS[0][0] + dz * STEP_DIRECTIONS[0][1]
    for step in range(1, len(STEP_DIRECTIONS)):
        direction = STEP_DIRECTIONS[step]
        dot = dx * direction[0] + dz * direction[1]
        if dot > best_dot:
            best_step = step
            best_dot = dot
    return best_step


def build(radius=RADIUS, inner_radius=INNER_RADIUS, turns=TURNS, slab=SLAB):
    diameter = 2 * radius + 1
    rise_per_turn = len(STEP_DIRECTIONS) // 2
    parts = []

    for x in range(diameter):
        for z in range(diameter):
            dx, dz = x - radius, z - radius
            distance_squared = dx * dx + dz * dz
            if distance_squared > radius * radius or distance_squared <= inner_radius * inner_radius:
                continue

            step = nearest_step(dx, dz)
            slab_type = "bottom" if step % 2 == 0 else "top"
            material = block(slab, {"type": slab_type, "waterlogged": "false"})
            for turn in range(turns):
                y = turn * rise_per_turn + step // 2
                parts.append(place_block([x, y, z], material))

    return component(
        name="ProceduralSlabSpiral",
        props={"radius": radius, "inner_radius": inner_radius, "turns": turns, "slab": slab},
        min_size=[diameter, turns * rise_per_turn, diameter],
        body=group(parts),
    )
