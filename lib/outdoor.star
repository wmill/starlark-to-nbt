# Outdoor components: wells, fences, paths, trees.


def Well(material="minecraft:cobblestone", post="minecraft:oak_fence", roof="minecraft:oak_slab"):
    """3x3 well: stone ring around water, corner posts, slab roof."""
    parts = [
        fill_region([0, 0, 0], [3, 1, 1], block(material)),
        fill_region([0, 0, 2], [3, 1, 3], block(material)),
        fill_region([0, 0, 1], [1, 1, 2], block(material)),
        fill_region([2, 0, 1], [3, 1, 2], block(material)),
        place_block([1, 0, 1], block("minecraft:water")),
        fill_region([0, 3, 0], [3, 4, 3], block(roof, {"type": "bottom", "waterlogged": "false"})),
    ]
    for x, z in [(0, 0), (2, 0), (0, 2), (2, 2)]:
        parts.append(fill_region([x, 1, z], [x + 1, 3, z + 1], block(post), phase="fixture"))
    return component(
        name="Well",
        props={"material": material, "post": post, "roof": roof},
        min_size=[3, 4, 3],
        body=group(parts),
    )


def FenceRing(width, length, fence="minecraft:oak_fence", gate="minecraft:oak_fence_gate"):
    """Fenced perimeter with connection states set per run, gated on the south edge."""
    gate_x = width // 2
    ew = {"east": "true", "west": "true"}
    ns = {"north": "true", "south": "true"}
    parts = []
    for x in range(width):
        north_state = dict(ew)
        south_state = dict(ew)
        if x == 0:
            north_state = {"east": "true", "south": "true"}
            south_state = {"east": "true", "north": "true"}
        elif x == width - 1:
            north_state = {"west": "true", "south": "true"}
            south_state = {"west": "true", "north": "true"}
        parts.append(place_block([x, 0, 0], block(fence, north_state), phase="fixture"))
        if x == gate_x:
            parts.append(place_block([x, 0, length - 1],
                                     block(gate, {"facing": "south", "open": "false", "powered": "false", "in_wall": "false"}),
                                     phase="fixture"))
        else:
            parts.append(place_block([x, 0, length - 1], block(fence, south_state), phase="fixture"))
    for z in range(1, length - 1):
        parts.append(place_block([0, 0, z], block(fence, ns), phase="fixture"))
        parts.append(place_block([width - 1, 0, z], block(fence, ns), phase="fixture"))
    return component(
        name="FenceRing",
        props={"width": width, "length": length, "fence": fence, "gate": gate},
        min_size=[width, 1, length],
        body=group(parts),
    )


def Path(length, width=1, material="minecraft:dirt_path"):
    """Ground path running along +Z."""
    return component(
        name="Path",
        props={"length": length, "width": width, "material": material},
        min_size=[width, 1, length],
        body=fill_region([0, 0, 0], [width, 1, length], block(material)),
    )


def Tree(height=5, log="minecraft:oak_log", leaves="minecraft:oak_leaves"):
    """Simple tree: vertical trunk with a 3x3 persistent-leaf canopy."""
    leaf = block(leaves, {"persistent": "true", "waterlogged": "false"})
    parts = [fill_region([1, 0, 1], [2, height, 2], block(log, {"axis": "y"}))]
    for y in range(height - 2, height):
        parts.append(fill_region([0, y, 0], [3, y + 1, 1], leaf))
        parts.append(fill_region([0, y, 2], [3, y + 1, 3], leaf))
        parts.append(fill_region([0, y, 1], [1, y + 1, 2], leaf))
        parts.append(fill_region([2, y, 1], [3, y + 1, 2], leaf))
    parts.append(fill_region([0, height, 0], [3, height + 1, 3], leaf))
    return component(
        name="Tree",
        props={"height": height, "log": log, "leaves": leaves},
        min_size=[3, height + 1, 3],
        body=group(parts),
    )
