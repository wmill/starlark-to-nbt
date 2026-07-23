# Iterative L-system tree: the host forbids recursive def, so branching
# generations are grown with a worklist loop instead -- each round consumes
# the previous round's branch tips and produces the next round's, which is
# the standard way to unroll a recursive tree-growth rule into plain
# iteration. There is no trig, so branch directions come from a small fixed
# table of integer vectors rather than computed angles. Each segment is
# drawn with an integer line-stepper (exact via floor division, no
# rounding drift), and terminal tips are capped with a leaf-blob sphere
# using the same distance-squared test as procedural_rotunda.star's dome,
# just in three dimensions instead of two.

GENERATIONS = 4
TRUNK_LENGTH = 7
BRANCH_LENGTHS = [5, 4, 3]
BRANCHES_PER_NODE = 3
LEAF_RADIUS = 2
TRUNK_MATERIAL = "minecraft:oak_wood"
LEAF_MATERIAL = "minecraft:oak_leaves"

DIRECTIONS = [
    [1, 2, 0], [-1, 2, 0], [0, 2, 1], [0, 2, -1],
    [1, 2, 1], [-1, 2, -1], [1, 2, -1], [-1, 2, 1],
]


def line_cells(x0, y0, z0, x1, y1, z1):
    steps = max([abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)])
    if steps == 0:
        return [(x0, y0, z0)]
    cells = []
    for step in range(steps + 1):
        cells.append((
            x0 + (x1 - x0) * step // steps,
            y0 + (y1 - y0) * step // steps,
            z0 + (z1 - z0) * step // steps,
        ))
    return cells


def leaf_offsets(radius):
    offsets = []
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                if dx * dx + dy * dy + dz * dz <= radius * radius:
                    offsets.append((dx, dy, dz))
    return offsets


def scaled_direction(direction, length):
    dx, dy, dz = direction[0], direction[1], direction[2]
    return (dx * length // 2, length, dz * length // 2)


def build(generations=GENERATIONS, trunk_length=TRUNK_LENGTH, leaf_radius=LEAF_RADIUS):
    wood = {}
    for cell in line_cells(0, 0, 0, 0, trunk_length, 0):
        wood[cell] = True

    frontier = [(0, trunk_length, 0)]
    terminal_tips = []
    node_counter = 0
    for generation in range(generations - 1):
        next_frontier = []
        is_terminal_round = generation == generations - 2
        branch_length = BRANCH_LENGTHS[generation]
        for tip in frontier:
            for i in range(BRANCHES_PER_NODE):
                direction = DIRECTIONS[(node_counter * BRANCHES_PER_NODE + i) % len(DIRECTIONS)]
                node_counter += 1
                dx, dy, dz = scaled_direction(direction, branch_length)
                child = (tip[0] + dx, tip[1] + dy, tip[2] + dz)
                for cell in line_cells(tip[0], tip[1], tip[2], child[0], child[1], child[2]):
                    wood[cell] = True
                if is_terminal_round:
                    terminal_tips.append(child)
                else:
                    next_frontier.append(child)
        frontier = next_frontier

    leaves = {}
    for tip in terminal_tips:
        for offset in leaf_offsets(leaf_radius):
            cell = (tip[0] + offset[0], tip[1] + offset[1], tip[2] + offset[2])
            if cell not in wood:
                leaves[cell] = True

    wood_cells = list(wood.keys())
    leaf_cells = list(leaves.keys())
    all_x = [c[0] for c in wood_cells] + [c[0] for c in leaf_cells]
    all_y = [c[1] for c in wood_cells] + [c[1] for c in leaf_cells]
    all_z = [c[2] for c in wood_cells] + [c[2] for c in leaf_cells]
    min_x, max_x = min(all_x), max(all_x)
    min_z, max_z = min(all_z), max(all_z)
    max_y = max(all_y)
    tx, tz = -min_x, -min_z

    parts = []
    for cell in wood_cells:
        parts.append(place_block([cell[0] + tx, cell[1], cell[2] + tz], block(TRUNK_MATERIAL)))
    leaf_state = {"persistent": "true", "waterlogged": "false"}
    for cell in leaf_cells:
        parts.append(place_block([cell[0] + tx, cell[1], cell[2] + tz], block(LEAF_MATERIAL, leaf_state)))

    return component(
        name="ProceduralFractalTree",
        props={"generations": generations, "trunk_length": trunk_length, "leaf_radius": leaf_radius},
        min_size=[max_x - min_x + 1, max_y + 1, max_z - min_z + 1],
        body=group(parts),
    )
