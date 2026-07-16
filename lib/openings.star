# Openings: doors, windows, archways. Each component carves its own hole,
# so placing one over an existing wall region "just works" — carve runs after
# structure fills, and the fixture blocks land in the cleared cells.
# Default orientation faces +Z (south); rotate with transform().


def SingleDoor(material="minecraft:oak_door"):
    """1x2x1 doorway: carves the opening and places both door halves atomically."""
    state = {"facing": "south", "hinge": "left", "open": "false", "powered": "false"}
    return component(
        name="SingleDoor",
        props={"material": material},
        min_size=[1, 2, 1],
        body=group([
            carve_region([0, 0, 0], [1, 2, 1]),
            place_assembly(
                pos=[0, 0, 0],
                name="single_door",
                size=[1, 2, 1],
                blocks=[
                    {"pos": [0, 0, 0], "block": block(material, dict(state, half="lower"))},
                    {"pos": [0, 1, 0], "block": block(material, dict(state, half="upper"))},
                ],
            ),
        ]),
    )


def DoubleDoor(material="minecraft:oak_door"):
    """2x2x1 double doorway with mirrored hinges."""
    left = {"facing": "south", "hinge": "right", "open": "false", "powered": "false"}
    right = {"facing": "south", "hinge": "left", "open": "false", "powered": "false"}
    return component(
        name="DoubleDoor",
        props={"material": material},
        min_size=[2, 2, 1],
        body=group([
            carve_region([0, 0, 0], [2, 2, 1]),
            place_assembly(
                pos=[0, 0, 0],
                name="double_door",
                size=[2, 2, 1],
                blocks=[
                    {"pos": [0, 0, 0], "block": block(material, dict(left, half="lower"))},
                    {"pos": [0, 1, 0], "block": block(material, dict(left, half="upper"))},
                    {"pos": [1, 0, 0], "block": block(material, dict(right, half="lower"))},
                    {"pos": [1, 1, 0], "block": block(material, dict(right, half="upper"))},
                ],
            ),
        ]),
    )


def Window(width=1, height=2, pane="minecraft:glass_pane"):
    """Glass-pane window; panes connect east-west along the wall run."""
    return component(
        name="Window",
        props={"width": width, "height": height, "pane": pane},
        min_size=[width, height, 1],
        body=group([
            carve_region([0, 0, 0], [width, height, 1]),
            fill_region([0, 0, 0], [width, height, 1],
                        block(pane, {"east": "true", "west": "true"}), phase="fixture"),
        ]),
    )


def ShutteredWindow(width=1, height=2, pane="minecraft:glass_pane", shutter="minecraft:oak_trapdoor"):
    """Window flanked by open-trapdoor shutters; total footprint is width+2."""
    shutter_state = {"facing": "south", "open": "true", "half": "bottom", "powered": "false", "waterlogged": "false"}
    parts = [
        carve_region([0, 0, 0], [width + 2, height, 1]),
        fill_region([1, 0, 0], [1 + width, height, 1],
                    block(pane, {"east": "true", "west": "true"}), phase="fixture"),
    ]
    for y in range(height):
        parts.append(place_block([0, y, 0], block(shutter, shutter_state), phase="fixture"))
        parts.append(place_block([width + 1, y, 0], block(shutter, shutter_state), phase="fixture"))
    return component(
        name="ShutteredWindow",
        props={"width": width, "height": height, "pane": pane, "shutter": shutter},
        min_size=[width + 2, height, 1],
        body=group(parts),
    )


def Archway(width, height, stair="minecraft:stone_brick_stairs"):
    """Carved opening with upside-down stair corners suggesting an arch."""
    return component(
        name="Archway",
        props={"width": width, "height": height, "stair": stair},
        min_size=[width, height, 1],
        body=group([
            carve_region([0, 0, 0], [width, height, 1]),
            place_block([0, height - 1, 0],
                        block(stair, {"facing": "east", "half": "top", "shape": "straight"}), phase="fixture"),
            place_block([width - 1, height - 1, 0],
                        block(stair, {"facing": "west", "half": "top", "shape": "straight"}), phase="fixture"),
        ]),
    )
