# Outdoor components: wells, fences, paths, trees.


def Horse(variant=0, tame=True):
    """A persistent, usable horse facing +Z. Variant is Minecraft's packed
    coat/marking integer; transforms rotate its anchor and yaw."""
    return component(
        name="Horse",
        props={"variant": variant, "tame": tame},
        min_size=[1, 2, 1],
        body=place_entity([0, 0, 0], entity(
            "minecraft:horse",
            nbt={
                "Variant": variant,
                "Tame": tame,
                "PersistenceRequired": True,
                "Health": 30.0,
            },
        )),
    )


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
    """Ground path running along +Z; carves through whatever is already there so it can overlay a foundation."""
    return component(
        name="Path",
        props={"length": length, "width": width, "material": material},
        min_size=[width, 1, length],
        body=group([
            carve_region([0, 0, 0], [width, 1, length]),
            fill_region([0, 0, 0], [width, 1, length], block(material), phase="fixture"),
        ]),
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


def CropPlot(width, length, crop="minecraft:wheat", age="7", border="minecraft:oak_log"):
    """Bordered farmland with a central +Z irrigation channel and mature crops."""
    if width < 5 or length < 5:
        fail("CropPlot requires width and length >= 5")
    water_x = width // 2
    parts = []
    for x in range(width):
        for z in range(length):
            edge = x == 0 or x == width - 1 or z == 0 or z == length - 1
            if edge:
                axis = "x"
                if x == 0 or x == width - 1:
                    axis = "z"
                parts.append(place_block([x, 0, z], block(border, {"axis": axis})))
            elif x == water_x:
                parts.append(place_block([x, 0, z], block("minecraft:water")))
            else:
                parts.append(place_block([x, 0, z], block("minecraft:farmland", {"moisture": "7"})))
                parts.append(place_block([x, 1, z], block(crop, {"age": age}), phase="fixture"))
    return component(name="CropPlot", props={"width": width, "length": length, "crop": crop, "age": age, "border": border},
                     min_size=[width, 2, length], body=group(parts))


def FlowerBed(width, length, flower_a="minecraft:poppy", flower_b="minecraft:dandelion", border="minecraft:cobblestone"):
    """Stone-bordered soil bed with alternating flowers."""
    if width < 3 or length < 3:
        fail("FlowerBed requires width and length >= 3")
    parts = []
    for x in range(width):
        for z in range(length):
            if x == 0 or x == width - 1 or z == 0 or z == length - 1:
                parts.append(place_block([x, 0, z], block(border)))
            else:
                parts.append(place_block([x, 0, z], block("minecraft:dirt")))
                flower = flower_a
                if (x + z) % 2 == 1:
                    flower = flower_b
                parts.append(place_block([x, 1, z], block(flower), phase="fixture"))
    return component(name="FlowerBed", props={"width": width, "length": length, "flower_a": flower_a, "flower_b": flower_b, "border": border},
                     min_size=[width, 2, length], body=group(parts))


def MarketStall(width=5, depth=3, canopy="minecraft:red_wool", accent="minecraft:white_wool", post="minecraft:oak_fence"):
    """South-facing counter stall with four posts and a striped canopy."""
    parts = []
    for x, z in [(0, 0), (width - 1, 0), (0, depth - 1), (width - 1, depth - 1)]:
        parts.append(fill_region([x, 0, z], [x + 1, 3, z + 1], block(post), phase="fixture"))
    parts.append(fill_region([1, 1, depth - 1], [width - 1, 2, depth], block("minecraft:oak_slab", {"type": "bottom", "waterlogged": "false"}), phase="fixture"))
    for x in range(width):
        material = canopy
        if x % 2 == 1:
            material = accent
        parts.append(fill_region([x, 3, 0], [x + 1, 4, depth], block(material)))
    return component(name="MarketStall", props={"width": width, "depth": depth, "canopy": canopy, "accent": accent, "post": post},
                     min_size=[width, 4, depth], body=group(parts))


def Pergola(width=5, depth=5, height=4, post="minecraft:oak_log", beam="minecraft:stripped_oak_log", slat="minecraft:oak_slab"):
    """Open garden pergola: corner posts, perimeter top beams, and a slatted
    lattice roof with gaps between every other run."""
    if width < 3 or depth < 3:
        fail("Pergola requires width and depth >= 3")
    parts = []
    for x, z in [(0, 0), (width - 1, 0), (0, depth - 1), (width - 1, depth - 1)]:
        parts.append(fill_region([x, 0, z], [x + 1, height, z + 1], block(post, {"axis": "y"})))
    parts.append(fill_region([0, height, 0], [width, height + 1, 1], block(beam, {"axis": "x"})))
    parts.append(fill_region([0, height, depth - 1], [width, height + 1, depth], block(beam, {"axis": "x"})))
    parts.append(fill_region([0, height, 1], [1, height + 1, depth - 1], block(beam, {"axis": "z"})))
    parts.append(fill_region([width - 1, height, 1], [width, height + 1, depth - 1], block(beam, {"axis": "z"})))
    for x in range(1, width - 1, 2):
        parts.append(fill_region([x, height, 1], [x + 1, height + 1, depth - 1],
                                 block(slat, {"type": "top", "waterlogged": "false"})))
    return component(
        name="Pergola",
        props={"width": width, "depth": depth, "height": height, "post": post, "beam": beam, "slat": slat},
        min_size=[width, height + 1, depth],
        body=group(parts),
    )


def HayBaleStack(width=3, height=2, depth=2, material="minecraft:hay_block"):
    """Layered hay pile with alternating horizontal bale axes."""
    parts = []
    for y in range(height):
        layer_width = width - y
        if layer_width < 1:
            layer_width = 1
        x_offset = (width - layer_width) // 2
        for x in range(layer_width):
            for z in range(depth):
                axis = "x"
                if (x + z + y) % 2 == 1:
                    axis = "z"
                parts.append(place_block([x_offset + x, y, z], block(material, {"axis": axis})))
    return component(name="HayBaleStack", props={"width": width, "height": height, "depth": depth, "material": material},
                     min_size=[width, height, depth], body=group(parts))
