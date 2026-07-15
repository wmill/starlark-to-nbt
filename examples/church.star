def Door(material="minecraft:oak_door"):
    return component(
        name="Door",
        props={"material": material},
        min_size=[1, 2, 1],
        body=place_assembly(
            pos=[0, 0, 0],
            name="door",
            size=[1, 2, 1],
            blocks=[
                {"pos": [0, 0, 0], "block": block(material, {"facing": "south", "half": "lower", "hinge": "left", "open": "false", "powered": "false"})},
                {"pos": [0, 1, 0], "block": block(material, {"facing": "south", "half": "upper", "hinge": "left", "open": "false", "powered": "false"})},
            ],
        ),
    )


def Pew(length, material="minecraft:oak_stairs"):
    return component(
        name="Pew",
        props={"length": length, "material": material},
        min_size=[length, 1, 1],
        body=group([
            place_block(
                pos=[x, 0, 0],
                block=block(material, {"facing": "south", "half": "bottom", "shape": "straight", "waterlogged": "false"}),
                phase="fixture",
            )
            for x in range(length)
        ]),
    )


def PewBank(pew_count):
    return component(
        name="PewBank",
        props={"count": pew_count},
        body=repeat(axis="z", count=pew_count, child_extent=1, gap=1, child=Pew(3)),
    )


def Church(width, length, height):
    door_x = width // 2
    interior_length = length - 3
    pew_count = (interior_length + 1) // 2
    shell = group([
        fill_region([0, 0, 0], [width, 1, length], block("minecraft:stone_bricks")),
        fill_region([0, 1, 0], [1, height, length], block("minecraft:stone_bricks")),
        fill_region([width - 1, 1, 0], [width, height, length], block("minecraft:stone_bricks")),
        fill_region([1, 1, 0], [width - 1, height, 1], block("minecraft:stone_bricks")),
        fill_region([1, 1, length - 1], [width - 1, height, length], block("minecraft:stone_bricks")),
        carve_region([door_x, 1, 0], [door_x + 1, 3, 1]),
        transform([door_x, 1, 0], 180, [1, 2, 1], Door()),
    ])
    interior = inset(
        x=[1, 1], y=[1, height - 2], z=[2, 1],
        child=split(
            axis="x",
            sizes=[fill(), fixed(3), fill()],
            children=[PewBank(pew_count), group([]), PewBank(pew_count)],
        ),
    )
    return component(
        name="Church",
        props={"width": width, "length": length, "height": height},
        min_size=[9, 4, 9],
        body=group([shell, interior]),
    )


def build(width=11, length=19, height=4):
    return Church(width, length, height)
