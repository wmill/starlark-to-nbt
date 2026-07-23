# Composite residential buildings, assembled from structural.star /
# openings.star / roofs.star / fixtures.star primitives via transform().
# Draw from [0, 0, 0]; entrance faces +Z (south) at rotation zero.

load("structural.star", "Floor", "TimberFrameWall")
load("openings.star", "SingleDoor", "Window")
load("roofs.star", "GableRoof")
load("fixtures.star", "Bed", "Chest")


def GuestHouse(width=7, depth=6, wall_height=4, log="minecraft:oak_log",
               infill="minecraft:cobblestone", door="minecraft:oak_door",
               roof_stair="minecraft:oak_stairs", roof_ridge="minecraft:oak_log",
               bed="minecraft:lime_bed"):
    """Small single-room cottage: log-post/cobblestone-infill walls, a
    south-facing door, a gable roof with a log ridge beam, and a furnished
    interior (bed, chest, bookshelves). Use an odd `width` to get a visible
    ridge beam on the roof."""
    if width < 5 or depth < 5:
        fail("GuestHouse requires width >= 5 and depth >= 5")
    roof_height = (width + 1) // 2
    door_x = width // 2
    window_x = width // 2
    parts = [
        transform([0, 0, 0], 0, [width, 1, depth], Floor(width, depth, "minecraft:oak_planks")),
        transform([0, 1, 0], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height, log, infill)),
        transform([0, 1, depth - 1], 0, [width, wall_height, 1], TimberFrameWall(width, wall_height, log, infill)),
        transform([0, 1, 1], 90, [depth - 2, wall_height, 1], TimberFrameWall(depth - 2, wall_height, log, infill)),
        transform([width - 1, 1, 1], 90, [depth - 2, wall_height, 1], TimberFrameWall(depth - 2, wall_height, log, infill)),
        transform([door_x, 1, depth - 1], 0, [1, 2, 1], SingleDoor(door)),
        transform([window_x, 1, 0], 0, [1, 2, 1], Window()),
        transform([0, 1 + wall_height, 0], 0, [width, roof_height, depth], GableRoof(width, depth, roof_stair, roof_ridge)),
        transform([1, 1, 2], 0, [1, 1, 2], Bed(bed)),
        transform([width - 2, 1, 1], 0, [1, 1, 1], Chest()),
        place_block([1, 1, 1], block("minecraft:bookshelf"), phase="fixture"),
        place_block([width - 2, 1, depth - 2], block("minecraft:bookshelf"), phase="fixture"),
        place_block([door_x, 1, 1], block("minecraft:torch"), phase="fixture"),
        place_block([door_x, 1, depth - 2], block("minecraft:torch"), phase="fixture"),
    ]
    return component(
        name="GuestHouse",
        props={"width": width, "depth": depth, "wall_height": wall_height, "log": log,
               "infill": infill, "door": door, "roof_stair": roof_stair,
               "roof_ridge": roof_ridge, "bed": bed},
        min_size=[width, 1 + wall_height + roof_height, depth],
        body=group(parts),
    )
