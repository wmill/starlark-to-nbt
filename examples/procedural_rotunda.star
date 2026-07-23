# Round glass rotunda: the DSL has no circle/sphere primitive and no
# sqrt(), so both the cylindrical wall and the hemispherical dome are
# voxelized with plain integer distance-squared tests. A cell belongs to a
# ring's shell when its squared distance from the axis falls between an
# inner and outer radius; a dome layer's radius is found by scanning
# candidate radii downward from the base radius until one fits the
# Pythagorean budget left over at that height. The apex layer naturally
# resolves to radius 0, leaving an open oculus at the top -- a deliberate
# feature, not a bug.

RADIUS = 9
WALL_THICKNESS = 2
WALL_HEIGHT = 8
WINDOW_PERIOD = 5
FLOOR_MATERIAL = "minecraft:smooth_stone"
WALL_MATERIAL = "minecraft:quartz_block"
GLASS_MATERIAL = "minecraft:glass"


def dome_ring_radius(y, r):
    """Largest integer radius whose circle fits at height y of a radius-r dome."""
    budget = r * r - y * y
    if budget < 0:
        return -1
    for candidate in range(r, -1, -1):
        if candidate * candidate <= budget:
            return candidate
    return 0


def build(radius=RADIUS, wall_thickness=WALL_THICKNESS, wall_height=WALL_HEIGHT):
    diameter = 2 * radius + 1
    center = radius
    inner_radius = radius - wall_thickness
    parts = []

    # Floor: solid disk.
    for x in range(diameter):
        for z in range(diameter):
            dx, dz = x - center, z - center
            if dx * dx + dz * dz <= radius * radius:
                parts.append(place_block([x, 0, z], block(FLOOR_MATERIAL)))

    # Wall: thin annulus shell, windows cut in by a raster-order counter.
    col_index = 0
    for x in range(diameter):
        for z in range(diameter):
            dx, dz = x - center, z - center
            d2 = dx * dx + dz * dz
            if d2 <= radius * radius and d2 > inner_radius * inner_radius:
                material = GLASS_MATERIAL if col_index % WINDOW_PERIOD == 0 else WALL_MATERIAL
                for y in range(1, wall_height + 1):
                    parts.append(place_block([x, y, z], block(material)))
                col_index += 1

    # Dome: one thin ring per height layer, radius shrinking toward the apex.
    dome_y0 = wall_height + 1
    dome_layers = radius + 1
    for layer in range(dome_layers):
        r_y = dome_ring_radius(layer, radius)
        if r_y < 0:
            continue
        for dx in range(-r_y, r_y + 1):
            for dz in range(-r_y, r_y + 1):
                d2 = dx * dx + dz * dz
                if d2 <= r_y * r_y and d2 > (r_y - 1) * (r_y - 1):
                    parts.append(place_block([center + dx, dome_y0 + layer, center + dz], block(GLASS_MATERIAL)))

    return component(
        name="ProceduralRotunda",
        props={"radius": radius, "wall_thickness": wall_thickness, "wall_height": wall_height},
        min_size=[diameter, dome_y0 + dome_layers, diameter],
        body=group(parts),
    )
