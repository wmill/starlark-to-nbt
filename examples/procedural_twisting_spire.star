# Twisting spire: this DSL has no trig and no `**` power operator (both
# absent from Starlark itself, unused anywhere in this repo), so there is
# no way to compute a rotation matrix. Instead, each level's square ring is
# nudged by an (x, z) offset pulled from a small fixed lookup table,
# indexed by level modulo the table length -- a cheap substitute for a true
# rotation that still reads as a twisting silhouette once stacked. Each
# ring reuses the non-overlapping-perimeter idiom from
# procedural_spiral_stair.star: north/south walls span the full width,
# east/west walls are narrowed to skip the corners those already cover.

LEVELS = 20
RING_OUTER = 7
LEVEL_HEIGHT = 2
AMPLITUDE = 2
OFFSET_TABLE = [[0, 0], [1, 0], [1, 1], [0, 1]]
PALETTE = [
    "minecraft:purpur_block",
    "minecraft:end_stone_bricks",
    "minecraft:purpur_pillar",
    "minecraft:quartz_block",
]


def build(levels=LEVELS, ring_outer=RING_OUTER, level_height=LEVEL_HEIGHT, amplitude=AMPLITUDE):
    parts = []
    for level in range(levels):
        table_x, table_z = OFFSET_TABLE[level % len(OFFSET_TABLE)]
        ox, oz = table_x * amplitude, table_z * amplitude
        y0, y1 = level * level_height, (level + 1) * level_height
        material = block(PALETTE[level % len(PALETTE)])
        x0, z0 = ox, oz
        x1, z1 = ox + ring_outer, oz + ring_outer
        parts.append(fill_region([x0, y0, z0], [x1, y1, z0 + 1], material))
        parts.append(fill_region([x0, y0, z1 - 1], [x1, y1, z1], material))
        parts.append(fill_region([x0, y0, z0 + 1], [x0 + 1, y1, z1 - 1], material))
        parts.append(fill_region([x1 - 1, y0, z0 + 1], [x1, y1, z1 - 1], material))

    max_table_x = max([entry[0] for entry in OFFSET_TABLE])
    max_table_z = max([entry[1] for entry in OFFSET_TABLE])
    width = ring_outer + max_table_x * amplitude
    length = ring_outer + max_table_z * amplitude
    return component(
        name="ProceduralTwistingSpire",
        props={"levels": levels, "ring_outer": ring_outer, "level_height": level_height, "amplitude": amplitude},
        min_size=[width, levels * level_height, length],
        body=group(parts),
    )
