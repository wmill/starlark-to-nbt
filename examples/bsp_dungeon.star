load("../lib/dungeons.star", "BspDungeon")


def build(width=96, length=96, room_height=4, min_room_size=6,
          target_leaf_size=20, max_depth=8, seed=20250721,
          wide_corridor_chance=0.30, light_spacing=8, burial_depth=4):
    surface_level = room_height + burial_depth + 2
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
    )
    return component(
        name="BspDungeonReference",
        props=dict(dungeon["props"]),
        min_size=dungeon["min_size"],
        metadata={"ground_level": surface_level},
        validators=[validator(
            "door_supported_on_both_sides",
            assembly="bsp_dungeon_door",
        )],
        body=dungeon,
    )
