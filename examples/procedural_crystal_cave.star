# Crystal cavern: examples/procedural_facade.star's comment notes there is
# no random()/noise() builtin, so every "procedural" effect in that file is
# formula-driven instead. This example demonstrates the standard
# workaround directly: a deterministic integer hash of a cell's coordinates
# stands in for random(), scattering stalagmites, stalactites, and
# amethyst crystals while staying bit-for-bit reproducible. The cave's
# footprint is an ellipse (dx^2/rx^2 + dz^2/rz^2 <= 1, cleared of fractions
# by multiplying through) -- another distance-formula shape, this time
# non-circular.

RX = 12
RZ = 8
CAVE_HEIGHT = 7
WALL_THICKNESS = 2
FLOOR_MATERIAL = "minecraft:tuff"
ROCK_MATERIAL = "minecraft:deepslate"
STALAGMITE_MATERIAL = "minecraft:dripstone_block"
CRYSTAL_MATERIAL = "minecraft:amethyst_block"
HASH_MULT_X = 374761393
HASH_MULT_Z = 668265263
HASH_MULT_SALT = 2246822519
HASH_MOD = 1000003


def pseudo_random(x, z, salt=0):
    """Deterministic integer hash used as a random() stand-in: same inputs
    always produce the same output, so builds stay reproducible."""
    return (x * HASH_MULT_X + z * HASH_MULT_Z + salt * HASH_MULT_SALT) % HASH_MOD


def in_ellipse(dx, dz, rx, rz):
    return dx * dx * rz * rz + dz * dz * rx * rx <= rx * rx * rz * rz


def build(rx=RX, rz=RZ, cave_height=CAVE_HEIGHT, wall_thickness=WALL_THICKNESS):
    diameter_x = 2 * rx + 1
    diameter_z = 2 * rz + 1
    inner_rx, inner_rz = rx - wall_thickness, rz - wall_thickness
    parts = []

    for x in range(diameter_x):
        for z in range(diameter_z):
            dx, dz = x - rx, z - rz
            outer = in_ellipse(dx, dz, rx, rz)
            inner = in_ellipse(dx, dz, inner_rx, inner_rz)
            if not outer:
                continue

            if not inner:
                for y in range(1, cave_height - 1):
                    parts.append(place_block([x, y, z], block(ROCK_MATERIAL)))

            is_crystal = inner and (pseudo_random(x, z, 5) % 11 == 0)
            floor_material = CRYSTAL_MATERIAL if is_crystal else FLOOR_MATERIAL
            parts.append(place_block([x, 0, z], block(floor_material)))
            parts.append(place_block([x, cave_height - 1, z], block(ROCK_MATERIAL)))

            if inner:
                roll = pseudo_random(x, z, 1) % 7
                if roll == 0:
                    stalagmite_h = 1 + pseudo_random(x, z, 2) % 3
                    parts.append(fill_region([x, 1, z], [x + 1, 1 + stalagmite_h, z + 1], block(STALAGMITE_MATERIAL)))
                elif roll == 3:
                    stalactite_h = 1 + pseudo_random(x, z, 4) % 3
                    top = cave_height - 2
                    parts.append(fill_region(
                        [x, top - stalactite_h + 1, z], [x + 1, top + 1, z + 1], block(STALAGMITE_MATERIAL)))

    return component(
        name="ProceduralCrystalCave",
        props={"rx": rx, "rz": rz, "cave_height": cave_height, "wall_thickness": wall_thickness},
        min_size=[diameter_x, cave_height, diameter_z],
        body=group(parts),
    )
