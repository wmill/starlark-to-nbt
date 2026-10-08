# Round glass rotunda built from lib/shapes.star: a disc floor, a ring wall
# with windows cut in by a raster-order counter, and a glass Dome cap. The
# shape helpers round radii to r + 0.5, so the outline has no lone
# single-block nubs at its cardinal points.

load("../lib/shapes.star", "Dome", "disc_cells", "fill_cells", "ring_cells")

RADIUS = 9
WALL_THICKNESS = 2
WALL_HEIGHT = 8
WINDOW_PERIOD = 5
FLOOR_MATERIAL = "minecraft:smooth_stone"
WALL_MATERIAL = "minecraft:quartz_block"
GLASS_MATERIAL = "minecraft:glass"


def build(radius=RADIUS, wall_thickness=WALL_THICKNESS, wall_height=WALL_HEIGHT):
    diameter = 2 * radius + 1
    parts = fill_cells(disc_cells(radius), 0, 1, block(FLOOR_MATERIAL))

    # Wall: every WINDOW_PERIOD-th ring column is glass from floor to dome.
    wall = ring_cells(radius, wall_thickness)
    windows = [wall[i] for i in range(len(wall)) if i % WINDOW_PERIOD == 0]
    solid = [wall[i] for i in range(len(wall)) if i % WINDOW_PERIOD != 0]
    parts += fill_cells(windows, 1, wall_height + 1, block(GLASS_MATERIAL))
    parts += fill_cells(solid, 1, wall_height + 1, block(WALL_MATERIAL))

    dome_y0 = wall_height + 1
    parts.append(at([0, dome_y0, 0], Dome(radius, GLASS_MATERIAL)))

    return component(
        name="ProceduralRotunda",
        props={"radius": radius, "wall_thickness": wall_thickness, "wall_height": wall_height},
        min_size=[diameter, dome_y0 + radius + 1, diameter],
        body=group(parts),
    )
