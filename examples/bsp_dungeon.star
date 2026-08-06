load("../lib/dungeons.star", "BspDungeon")
load("../lib/random.star", "random_cycle", "random_number")


MOSSY_STONE = "minecraft:mossy_stone_bricks"
CRACKED_STONE = "minecraft:cracked_stone_bricks"
DEFAULT_MOSSY_PERCENT = 0.15
DEFAULT_CRACKED_PERCENT = 0.07
WEATHERING = {
    "cycle": None,  # re-seeded in build() before any use
    "mossy_percent": DEFAULT_MOSSY_PERCENT,
    "cracked_percent": DEFAULT_CRACKED_PERCENT,
    "room_height": 4,
    "surface_level": 10,
}


def _moss_factor(y):
    surface_level = WEATHERING["surface_level"]
    if surface_level > 0 and y > surface_level:
        local_y = y - surface_level
        top_y = 4  # entrance hut: walls at local y 1..3, ceiling at 4
    else:
        local_y = y
        top_y = WEATHERING["room_height"] + 1
    if local_y < 1:
        local_y = 1
    if local_y > top_y:
        local_y = top_y
    return 1.5 - (local_y - 1.0) / (top_y - 1.0)


def weathered_stone(material, _x, y, _z):
    mossy_chance = WEATHERING["mossy_percent"] * _moss_factor(y)
    maximum_mossy = 1.0 - WEATHERING["cracked_percent"]
    if mossy_chance > maximum_mossy:
        mossy_chance = maximum_mossy
    roll = random_number(WEATHERING["cycle"])
    if roll < mossy_chance:
        return MOSSY_STONE
    if roll < mossy_chance + WEATHERING["cracked_percent"]:
        return CRACKED_STONE
    return material


def build(width=96, length=96, room_height=4, min_room_size=6,
          target_leaf_size=20, max_depth=8, seed=20250721,
          wide_corridor_chance=0.30, light_spacing=8, burial_depth=4,
          mossy_percent=DEFAULT_MOSSY_PERCENT, cracked_percent=DEFAULT_CRACKED_PERCENT):
    if mossy_percent < 0 or mossy_percent > 1:
        fail("mossy_percent must be between 0 and 1")
    if cracked_percent < 0 or cracked_percent > 1:
        fail("cracked_percent must be between 0 and 1")
    if mossy_percent + cracked_percent > 1:
        fail("mossy_percent + cracked_percent must be at most 1")

    surface_level = room_height + burial_depth + 2
    WEATHERING["cycle"] = random_cycle(seed)
    WEATHERING["mossy_percent"] = mossy_percent
    WEATHERING["cracked_percent"] = cracked_percent
    WEATHERING["room_height"] = room_height
    WEATHERING["surface_level"] = surface_level
    dungeon = BspDungeon(
        width=width,
        length=length,
        room_height=room_height,
        min_room_size=min_room_size,
        target_leaf_size=target_leaf_size,
        max_depth=max_depth,
        seed=seed,
        wide_corridor_chance=wide_corridor_chance,
        light_spacing=light_spacing,
        burial_depth=burial_depth,
        surface_entrance=True,
        wall_picker=weathered_stone,
    )
    props = dict(dungeon["props"])
    props["mossy_percent"] = mossy_percent
    props["cracked_percent"] = cracked_percent
    return component(
        name="BspDungeonReference",
        props=props,
        min_size=dungeon["min_size"],
        metadata={"ground_level": surface_level},
        validators=[validator(
            "door_supported_on_both_sides",
            assembly="bsp_dungeon_door",
        )],
        body=dungeon,
    )
