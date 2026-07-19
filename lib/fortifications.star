# Reusable stone and timber defenses. Linear components run along +X and
# gateways face +Z at rotation zero.

load("openings.star", "DoubleDoor")
load("fixtures.star", "Ladder")


def BattlementWall(length, height, material="minecraft:stone_bricks"):
    """Solid curtain wall with alternating merlons along its crown."""
    if length < 3 or height < 2:
        fail("BattlementWall requires length >= 3 and height >= 2")
    parts = [fill_region([0, 0, 0], [length, height, 1], block(material))]
    for x in range(0, length, 2):
        parts.append(place_block([x, height, 0], block(material)))
    return component(
        name="BattlementWall",
        props={"length": length, "height": height, "material": material},
        min_size=[length, height + 1, 1],
        body=group(parts),
    )


def SquareTower(size, height, material="minecraft:stone_bricks"):
    """Hollow square tower with arrow slits and a crenellated crown."""
    if size < 5 or height < 10:
        fail("SquareTower requires size >= 5 and height >= 10")
    parts = [
        fill_region([0, 0, 0], [size, height, 1], block(material)),
        fill_region([0, 0, size - 1], [size, height, size], block(material)),
        fill_region([0, 0, 1], [1, height, size - 1], block(material)),
        fill_region([size - 1, 0, 1], [size, height, size - 1], block(material)),
    ]
    for x in range(0, size, 2):
        parts.append(place_block([x, height, 0], block(material)))
        parts.append(place_block([x, height, size - 1], block(material)))
    for z in range(2, size - 2, 2):
        parts.append(place_block([0, height, z], block(material)))
        parts.append(place_block([size - 1, height, z], block(material)))
    mid = size // 2
    for y in [height - 10, height - 5]:
        parts.append(carve_region([mid, y, 0], [mid + 1, y + 2, 1]))
        parts.append(carve_region([mid, y, size - 1], [mid + 1, y + 2, size]))
        parts.append(carve_region([0, y, mid], [1, y + 2, mid + 1]))
        parts.append(carve_region([size - 1, y, mid], [size, y + 2, mid + 1]))
    return component(
        name="SquareTower",
        props={"size": size, "height": height, "material": material},
        min_size=[size, height + 1, size],
        body=group(parts),
    )


def Portcullis(width=3, height=4, material="minecraft:iron_bars"):
    """South-facing self-carving closed portcullis."""
    if width < 2 or height < 2:
        fail("Portcullis requires width and height >= 2")
    bars = block(material, {"east": "true", "west": "true", "north": "false", "south": "false", "waterlogged": "false"})
    return component(
        name="Portcullis",
        props={"width": width, "height": height, "material": material},
        min_size=[width, height, 1],
        body=group([
            carve_region([0, 0, 0], [width, height, 1]),
            fill_region([0, 0, 0], [width, height, 1], bars, phase="fixture"),
        ]),
    )


def Gatehouse(width=9, height=8, depth=5, opening_width=3, opening_height=4,
              material="minecraft:stone_bricks", bars="minecraft:iron_bars"):
    """Battlemented gatehouse with a centered tunnel and front portcullis."""
    if width < opening_width + 4 or depth < 3:
        fail("Gatehouse requires side walls >= 2 and depth >= 3")
    if opening_width < 2 or opening_height < 3 or height < opening_height + 2:
        fail("Gatehouse opening is too small or too tall")
    opening_x = (width - opening_width) // 2
    parts = [
        fill_region([0, 0, 0], [width, height, depth], block(material)),
        carve_region([opening_x, 0, 0], [opening_x + opening_width, opening_height, depth]),
        transform([opening_x, 0, depth - 1], 0, [opening_width, opening_height, 1],
                  Portcullis(opening_width, opening_height, bars)),
    ]
    for x in range(0, width, 2):
        parts.append(fill_region([x, height, 0], [x + 1, height + 1, depth], block(material)))
    slit_y = opening_height + 1
    parts.append(carve_region([1, slit_y, depth - 1], [2, slit_y + 2, depth]))
    parts.append(carve_region([width - 2, slit_y, depth - 1], [width - 1, slit_y + 2, depth]))
    return component(
        name="Gatehouse",
        props={"width": width, "height": height, "depth": depth,
               "opening_width": opening_width, "opening_height": opening_height,
               "material": material, "bars": bars},
        min_size=[width, height + 1, depth],
        body=group(parts),
    )


def Drawbridge(width=3, length=7, deck="minecraft:dark_oak_planks", chain="minecraft:chain"):
    """Lowered bridge running toward +Z with horizontal chains on both sides."""
    if width < 2 or length < 2:
        fail("Drawbridge requires width and length >= 2")
    parts = [fill_region([0, 0, 0], [width, 1, length], block(deck))]
    chain_block = block(chain, {"axis": "z", "waterlogged": "false"})
    parts.append(fill_region([0, 1, 0], [1, 2, length], chain_block, phase="fixture"))
    parts.append(fill_region([width - 1, 1, 0], [width, 2, length], chain_block, phase="fixture"))
    return component(
        name="Drawbridge",
        props={"width": width, "length": length, "deck": deck, "chain": chain},
        min_size=[width, 2, length],
        body=group(parts),
    )


def PalisadeWall(length, height=5, log="minecraft:spruce_log"):
    """Vertical-log wall with alternating raised tips."""
    if length < 2 or height < 3:
        fail("PalisadeWall requires length >= 2 and height >= 3")
    parts = []
    for x in range(length):
        column_height = height
        if x % 2 == 0:
            column_height = height + 1
        parts.append(fill_region([x, 0, 0], [x + 1, column_height, 1], block(log, {"axis": "y"})))
    return component(
        name="PalisadeWall",
        props={"length": length, "height": height, "log": log},
        min_size=[length, height + 1, 1],
        body=group(parts),
    )


def PalisadeGate(width=5, height=6, log="minecraft:spruce_log", door="minecraft:dark_oak_door"):
    """Timber gateway with a double door and overhead fighting platform."""
    if width < 5 or height < 4:
        fail("PalisadeGate requires width >= 5 and height >= 4")
    opening_x = (width - 2) // 2
    parts = [
        fill_region([0, 0, 0], [opening_x, height, 1], block(log, {"axis": "y"})),
        fill_region([opening_x + 2, 0, 0], [width, height, 1], block(log, {"axis": "y"})),
        fill_region([opening_x, 2, 0], [opening_x + 2, height, 1], block(log, {"axis": "y"})),
        fill_region([0, height, 0], [width, height + 1, 1], block("minecraft:spruce_planks")),
        transform([opening_x, 0, 0], 0, [2, 2, 1], DoubleDoor(door)),
    ]
    return component(
        name="PalisadeGate",
        props={"width": width, "height": height, "log": log, "door": door},
        min_size=[width, height + 1, 1],
        body=group(parts),
    )


def Watchtower(size=5, platform_height=6, post="minecraft:spruce_log",
               deck="minecraft:spruce_planks", railing="minecraft:spruce_fence"):
    """Four-post timber watchtower with a ladder and railed platform."""
    if size < 5 or platform_height < 4:
        fail("Watchtower requires size >= 5 and platform_height >= 4")
    parts = []
    for x, z in [(0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)]:
        parts.append(fill_region([x, 0, z], [x + 1, platform_height + 1, z + 1], block(post, {"axis": "y"})))
    # Leave the four post cells exposed so the deck does not conflict with
    # their differing block type.
    parts.append(fill_region([1, platform_height, 0], [size - 1, platform_height + 1, size], block(deck)))
    parts.append(fill_region([0, platform_height, 1], [1, platform_height + 1, size - 1], block(deck)))
    parts.append(fill_region([size - 1, platform_height, 1], [size, platform_height + 1, size - 1], block(deck)))
    center = size // 2
    # Continue the ladder through a carved deck cell so a climber can step
    # onto the platform instead of stopping beneath its ceiling.
    parts.append(carve_region([center, platform_height, 1], [center + 1, platform_height + 1, 2]))
    parts.append(transform([center, 0, 1], 0, [1, platform_height + 1, 1], Ladder(platform_height + 1)))
    ew = block(railing, {"east": "true", "west": "true"})
    ns = block(railing, {"north": "true", "south": "true"})
    parts.append(fill_region([0, platform_height + 1, 0], [size, platform_height + 2, 1], ew, phase="fixture"))
    parts.append(fill_region([0, platform_height + 1, size - 1], [size, platform_height + 2, size], ew, phase="fixture"))
    parts.append(fill_region([0, platform_height + 1, 1], [1, platform_height + 2, size - 1], ns, phase="fixture"))
    parts.append(fill_region([size - 1, platform_height + 1, 1], [size, platform_height + 2, size - 1], ns, phase="fixture"))
    return component(
        name="Watchtower",
        props={"size": size, "platform_height": platform_height, "post": post,
               "deck": deck, "railing": railing},
        min_size=[size, platform_height + 2, size],
        body=group(parts),
    )
