# Deterministic underground dungeon generation using a flat binary-space tree.
# Nodes are subdivided in depth passes because the embedded Starlark runtime
# deliberately does not support recursion.

_HASH_MOD = 2147483647


def _hash(seed, key, salt=0):
    return (seed * 1103515245 + key * 374761393 + salt * 668265263 + 12345) % _HASH_MOD


def _key(x, z):
    return "%s,%s" % (x, z)


def _wall_key(x, y, z):
    return "%s,%s,%s" % (x, y, z)


def _picked_wall(wall, wall_picker, wall_materials, x, y, z):
    if wall_picker == None:
        return wall
    key = _wall_key(x, y, z)
    if key not in wall_materials:
        wall_materials[key] = wall_picker(wall, x, y, z)
    return wall_materials[key]


def _wall_fill(min_pos, max_pos, wall, wall_picker, wall_materials):
    if wall_picker == None:
        return [fill_region(min_pos, max_pos, block(wall))]
    parts = []
    for y in range(min_pos[1], max_pos[1]):
        for z in range(min_pos[2], max_pos[2]):
            for x in range(min_pos[0], max_pos[0]):
                parts.append(place_block(
                    [x, y, z], block(_picked_wall(
                        wall, wall_picker, wall_materials, x, y, z))))
    return parts


def _wall_block(pos, wall, wall_picker, wall_materials):
    return place_block(pos, block(_picked_wall(
        wall, wall_picker, wall_materials, pos[0], pos[1], pos[2])))


def _plain_room(room, room_height, wall, floor, torch, wall_picker, wall_materials):
    """Render one replaceable room type from its outer half-open box."""
    x0, z0, x1, z1 = room["x0"], room["z0"], room["x1"], room["z1"]
    parts = [
        fill_region([x0, 0, z0], [x1, 1, z1], block(floor)),
        carve_region([x0 + 1, 1, z0 + 1], [x1 - 1, room_height + 1, z1 - 1]),
        place_block([x0 + 1, 1, z0 + 1], block(torch), phase="fixture"),
        place_block([x1 - 2, 1, z1 - 2], block(torch), phase="fixture"),
    ]
    parts.extend(_wall_fill(
        [x0, 1, z0], [x1, room_height + 1, z0 + 1], wall, wall_picker, wall_materials))
    parts.extend(_wall_fill(
        [x0, 1, z1 - 1], [x1, room_height + 1, z1], wall, wall_picker, wall_materials))
    parts.extend(_wall_fill(
        [x0, 1, z0 + 1], [x0 + 1, room_height + 1, z1 - 1], wall, wall_picker, wall_materials))
    parts.extend(_wall_fill(
        [x1 - 1, 1, z0 + 1], [x1, room_height + 1, z1 - 1], wall, wall_picker, wall_materials))
    parts.extend(_wall_fill(
        [x0, room_height + 1, z0], [x1, room_height + 2, z1], wall, wall_picker, wall_materials))
    return parts


def _add_cell(cells, ordered, x, z):
    key = _key(x, z)
    if key not in cells:
        cells[key] = True
        ordered.append([x, z])


def _add_line(cells, ordered, x0, z0, x1, z1, corridor_width):
    if x0 == x1:
        lo, hi = (z0, z1) if z0 <= z1 else (z1, z0)
        for z in range(lo, hi + 1):
            for offset in range(-(corridor_width // 2), corridor_width // 2 + 1):
                _add_cell(cells, ordered, x0 + offset, z)
    else:
        lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
        for x in range(lo, hi + 1):
            for offset in range(-(corridor_width // 2), corridor_width // 2 + 1):
                _add_cell(cells, ordered, x, z0 + offset)


def _inside_room(x, z, rooms):
    for room in rooms:
        if room["x0"] < x and x < room["x1"] - 1 and room["z0"] < z and z < room["z1"] - 1:
            return True
    return False


def _door(door_candidates, fixture_cells, x, z, facing, door, y=1):
    key = _key(x, z)
    if key in fixture_cells:
        return
    fixture_cells[key] = True
    door_candidates.append({
        "x": x, "y": y, "z": z, "facing": facing, "door": door,
    })


def _emit_door(parts, candidate):
    x, y, z = candidate["x"], candidate["y"], candidate["z"]
    facing, door = candidate["facing"], candidate["door"]
    state = {"facing": facing, "hinge": "left", "open": "false", "powered": "false"}
    parts.append(carve_region([x, y, z], [x + 1, y + 2, z + 1]))
    parts.append(place_assembly(
        pos=[x, y, z],
        name="bsp_dungeon_door",
        size=[1, 2, 1],
        blocks=[
            {"pos": [0, 0, 0], "block": block(door, dict(state, half="lower"))},
            {"pos": [0, 1, 0], "block": block(door, dict(state, half="upper"))},
        ],
    ))


def _door_has_jambs(candidate, corridor_cells, room_height):
    # Dungeon corridors carve from y=1 through room_height. Surface doors are
    # above that range and retain the hut wall on each side.
    if candidate["y"] > room_height:
        return True
    facing = candidate["facing"]
    if facing == "north" or facing == "south":
        offsets = [[-1, 0], [1, 0]]
    else:
        offsets = [[0, -1], [0, 1]]
    for offset in offsets:
        if _key(candidate["x"] + offset[0], candidate["z"] + offset[1]) in corridor_cells:
            return False
    return True


def _arch(parts, fixture_cells, x, z, axis, room_height, stair):
    # axis is the corridor's direction through the wall. The opening runs on
    # the perpendicular axis and is capped by two upside-down stair corners.
    if axis == "x":
        parts.append(carve_region([x, 1, z - 1], [x + 1, room_height + 1, z + 2]))
        positions = [[x, room_height, z - 1, "north"], [x, room_height, z + 1, "south"]]
    else:
        parts.append(carve_region([x - 1, 1, z], [x + 2, room_height + 1, z + 1]))
        positions = [[x - 1, room_height, z, "west"], [x + 1, room_height, z, "east"]]
    for item in positions:
        key = _key(item[0], item[2])
        if key not in fixture_cells:
            fixture_cells[key] = True
            parts.append(place_block(
                [item[0], item[1], item[2]],
                block(stair, {"facing": item[3], "half": "top", "shape": "straight"}),
                phase="fixture",
            ))


def _validate(width, length, room_height, min_room_size, target_leaf_size,
              max_depth, wide_corridor_chance, light_spacing, burial_depth,
              surface_entrance):
    if width < min_room_size + 4 or length < min_room_size + 4:
        fail("BspDungeon width and length must leave room for an inset room")
    if room_height < 3:
        fail("BspDungeon room_height must be at least 3")
    if min_room_size < 3:
        fail("BspDungeon min_room_size must be at least 3")
    if target_leaf_size < min_room_size + 4:
        fail("BspDungeon target_leaf_size must be at least min_room_size + 4")
    if max_depth < 0:
        fail("BspDungeon max_depth must be non-negative")
    if wide_corridor_chance < 0.0 or wide_corridor_chance > 1.0:
        fail("BspDungeon wide_corridor_chance must be between 0 and 1")
    if light_spacing < 1:
        fail("BspDungeon light_spacing must be at least 1")
    if burial_depth < 0:
        fail("BspDungeon burial_depth must be non-negative")


def BspDungeon(
        width=48,
        length=48,
        room_height=4,
        min_room_size=5,
        target_leaf_size=18,
        max_depth=8,
        seed=0,
        wide_corridor_chance=0.30,
        light_spacing=8,
        burial_depth=4,
        surface_entrance=True,
        wall="minecraft:stone_bricks",
        floor="minecraft:polished_andesite",
        stair="minecraft:stone_brick_stairs",
        door="minecraft:oak_door",
        torch="minecraft:torch",
        lantern="minecraft:lantern",
        wall_picker=None):
    """A deterministic, sparse, single-level underground BSP dungeon."""
    _validate(width, length, room_height, min_room_size, target_leaf_size,
              max_depth, wide_corridor_chance, light_spacing, burial_depth,
              surface_entrance)

    surface_level = room_height + burial_depth + 2 if surface_entrance else 0
    entrance_depth = surface_level + 4 if surface_entrance else 0
    bsp_z0 = entrance_depth
    min_partition = min_room_size + 4
    if length - bsp_z0 < min_partition:
        fail("BspDungeon has insufficient north-edge entrance clearance")

    nodes = [{
        "x0": 0, "z0": bsp_z0, "x1": width, "z1": length,
        "depth": 0, "leaf": True, "left": -1, "right": -1,
        "axis": "", "split": -1, "rep": -1,
    }]
    level_start = 0
    level_end = 1
    for depth in range(max_depth):
        next_start = len(nodes)
        for node_index in range(level_start, level_end):
            node = nodes[node_index]
            node_width = node["x1"] - node["x0"]
            node_length = node["z1"] - node["z0"]
            if node_width <= target_leaf_size and node_length <= target_leaf_size:
                continue
            can_x = node_width >= 2 * min_partition
            can_z = node_length >= 2 * min_partition
            if not can_x and not can_z:
                continue
            if can_x and (not can_z or node_width * 2 >= node_length * 3):
                axis = "x"
            elif can_z and (not can_x or node_length * 2 >= node_width * 3):
                axis = "z"
            else:
                axis = "x" if _hash(seed, node_index, 1) % 2 == 0 else "z"
            span = node_width if axis == "x" else node_length
            base = node["x0"] if axis == "x" else node["z0"]
            split_range = span - 2 * min_partition + 1
            split_at = base + min_partition + _hash(seed, node_index, 2) % split_range
            if axis == "x":
                left = {"x0": node["x0"], "z0": node["z0"], "x1": split_at, "z1": node["z1"]}
                right = {"x0": split_at, "z0": node["z0"], "x1": node["x1"], "z1": node["z1"]}
            else:
                left = {"x0": node["x0"], "z0": node["z0"], "x1": node["x1"], "z1": split_at}
                right = {"x0": node["x0"], "z0": split_at, "x1": node["x1"], "z1": node["z1"]}
            for child in [left, right]:
                child.update({"depth": depth + 1, "leaf": True, "left": -1, "right": -1,
                              "axis": "", "split": -1, "rep": -1})
            node["leaf"] = False
            node["axis"] = axis
            node["split"] = split_at
            node["left"] = len(nodes)
            node["right"] = len(nodes) + 1
            nodes.extend([left, right])
        level_start = next_start
        level_end = len(nodes)
        if level_start == level_end:
            break

    rooms = []
    for node_index in range(len(nodes)):
        node = nodes[node_index]
        if not node["leaf"]:
            continue
        leaf_width = node["x1"] - node["x0"]
        leaf_length = node["z1"] - node["z0"]
        min_outer = min_room_size + 2
        room_width = min_outer + _hash(seed, node_index, 3) % (leaf_width - min_outer - 1)
        room_length = min_outer + _hash(seed, node_index, 4) % (leaf_length - min_outer - 1)
        x_slack = leaf_width - room_width - 2
        z_slack = leaf_length - room_length - 2
        x0 = node["x0"] + 1 + _hash(seed, node_index, 5) % (x_slack + 1)
        z0 = node["z0"] + 1 + _hash(seed, node_index, 6) % (z_slack + 1)
        room = {"x0": x0, "z0": z0, "x1": x0 + room_width, "z1": z0 + room_length,
                "node": node_index}
        node["rep"] = len(rooms)
        rooms.append(room)

    # Select a deterministic representative room for each internal subtree.
    for node_index in range(len(nodes) - 1, -1, -1):
        node = nodes[node_index]
        if not node["leaf"]:
            choose_right = _hash(seed, node_index, 7) % 2
            child_index = node["right"] if choose_right else node["left"]
            node["rep"] = nodes[child_index]["rep"]

    parts = []
    wall_materials = {}
    for room in rooms:
        parts.extend(_plain_room(
            room, room_height, wall, floor, torch, wall_picker, wall_materials))

    corridor_cells = {}
    ordered_corridor_cells = []
    stair_cells = {}
    fixture_cells = {}
    door_candidates = []
    connection_count = 0
    wide_connection_count = 0
    chance_threshold = int(wide_corridor_chance * 10000)
    for node_index in range(len(nodes) - 1, -1, -1):
        node = nodes[node_index]
        if node["leaf"]:
            continue
        a = rooms[nodes[node["left"]]["rep"]]
        b = rooms[nodes[node["right"]]["rep"]]
        is_wide = _hash(seed, node_index, 8) % 10000 < chance_threshold
        corridor_width = 3 if is_wide else 1
        connection_count += 1
        if is_wide:
            wide_connection_count += 1
        if node["axis"] == "x":
            overlap_lo = max(a["z0"] + 2, b["z0"] + 2)
            overlap_hi = min(a["z1"] - 3, b["z1"] - 3)
            za = (a["z0"] + a["z1"]) // 2
            zb = (b["z0"] + b["z1"]) // 2
            if overlap_lo <= overlap_hi:
                za = overlap_lo + _hash(seed, node_index, 9) % (overlap_hi - overlap_lo + 1)
                zb = za
            ax, bx = a["x1"] - 2, b["x0"] + 1
            _add_line(corridor_cells, ordered_corridor_cells, ax, za, node["split"], za, corridor_width)
            _add_line(corridor_cells, ordered_corridor_cells, node["split"], za, node["split"], zb, corridor_width)
            _add_line(corridor_cells, ordered_corridor_cells, node["split"], zb, bx, zb, corridor_width)
            if is_wide:
                _arch(parts, fixture_cells, a["x1"] - 1, za, "x", room_height, stair)
                _arch(parts, fixture_cells, b["x0"], zb, "x", room_height, stair)
            else:
                _door(door_candidates, fixture_cells, a["x1"] - 1, za, "east", door)
                _door(door_candidates, fixture_cells, b["x0"], zb, "west", door)
        else:
            overlap_lo = max(a["x0"] + 2, b["x0"] + 2)
            overlap_hi = min(a["x1"] - 3, b["x1"] - 3)
            xa = (a["x0"] + a["x1"]) // 2
            xb = (b["x0"] + b["x1"]) // 2
            if overlap_lo <= overlap_hi:
                xa = overlap_lo + _hash(seed, node_index, 10) % (overlap_hi - overlap_lo + 1)
                xb = xa
            az, bz = a["z1"] - 2, b["z0"] + 1
            _add_line(corridor_cells, ordered_corridor_cells, xa, az, xa, node["split"], corridor_width)
            _add_line(corridor_cells, ordered_corridor_cells, xa, node["split"], xb, node["split"], corridor_width)
            _add_line(corridor_cells, ordered_corridor_cells, xb, node["split"], xb, bz, corridor_width)
            if is_wide:
                _arch(parts, fixture_cells, xa, a["z1"] - 1, "z", room_height, stair)
                _arch(parts, fixture_cells, xb, b["z0"], "z", room_height, stair)
            else:
                _door(door_candidates, fixture_cells, xa, a["z1"] - 1, "south", door)
                _door(door_candidates, fixture_cells, xb, b["z0"], "north", door)

    # Entrance hut, descending stair tunnel, and its dungeon-level landing.
    if surface_entrance:
        center = width // 2
        hx0, hx1 = center - 2, center + 3
        if hx0 < 0 or hx1 > width:
            fail("BspDungeon width is too small for the surface entrance hut")
        parts.extend([
            fill_region([hx0, surface_level, 0], [center, surface_level + 1, 5], block(floor)),
            fill_region([center + 1, surface_level, 0], [hx1, surface_level + 1, 5], block(floor)),
            place_block([center, surface_level, 0], block(floor)),
            carve_region([hx0 + 1, surface_level + 1, 1], [hx1 - 1, surface_level + 4, 4]),
        ])
        parts.extend(_wall_fill(
            [hx0, surface_level + 1, 0], [hx1, surface_level + 4, 1],
            wall, wall_picker, wall_materials))
        parts.extend(_wall_fill(
            [hx0, surface_level + 1, 4], [hx1, surface_level + 4, 5],
            wall, wall_picker, wall_materials))
        parts.extend(_wall_fill(
            [hx0, surface_level + 1, 1], [hx0 + 1, surface_level + 4, 4],
            wall, wall_picker, wall_materials))
        parts.extend(_wall_fill(
            [hx1 - 1, surface_level + 1, 1], [hx1, surface_level + 4, 4],
            wall, wall_picker, wall_materials))
        parts.extend(_wall_fill(
            [hx0, surface_level + 4, 0], [hx1, surface_level + 5, 5],
            wall, wall_picker, wall_materials))
        _door(door_candidates, fixture_cells, center, 0, "north", door, y=surface_level + 1)
        for step in range(surface_level):
            y = surface_level - step
            z = 3 + step
            stair_cells[_key(center, z)] = True
            parts.append(place_block([center, y, z], block(stair, {
                "facing": "north", "half": "bottom", "shape": "straight",
            })))
            parts.append(carve_region([center, y + 1, z], [center + 1, y + 4, z + 1]))
        landing_z = 3 + surface_level
        north_room = rooms[0]
        for room in rooms[1:]:
            if room["z0"] < north_room["z0"]:
                north_room = room
        room_x = (north_room["x0"] + north_room["x1"]) // 2
        room_z = north_room["z0"] + 1
        _add_line(corridor_cells, ordered_corridor_cells, center, landing_z, center, bsp_z0, 1)
        _add_line(corridor_cells, ordered_corridor_cells, center, bsp_z0, room_x, bsp_z0, 1)
        _add_line(corridor_cells, ordered_corridor_cells, room_x, bsp_z0, room_x, room_z, 1)

    # Each path cell gets a complete tunnel cross-section. Neighboring tunnel
    # cells are subsequently carved, leaving only the exterior side shell.
    for cell in ordered_corridor_cells:
        x, z = cell[0], cell[1]
        parts.append(place_block([x, 0, z], block(floor)))
        parts.append(_wall_block(
            [x, room_height + 1, z], wall, wall_picker, wall_materials))
        parts.append(carve_region([x, 1, z], [x + 1, room_height + 1, z + 1]))
        if _key(x - 1, z) not in corridor_cells and _key(x - 1, z) not in stair_cells:
            parts.extend(_wall_fill(
                [x - 1, 1, z], [x, room_height + 2, z + 1],
                wall, wall_picker, wall_materials))
        if _key(x + 1, z) not in corridor_cells and _key(x + 1, z) not in stair_cells:
            parts.extend(_wall_fill(
                [x + 1, 1, z], [x + 2, room_height + 2, z + 1],
                wall, wall_picker, wall_materials))
        if _key(x, z - 1) not in corridor_cells and _key(x, z - 1) not in stair_cells:
            parts.extend(_wall_fill(
                [x, 1, z - 1], [x + 1, room_height + 2, z],
                wall, wall_picker, wall_materials))
        if _key(x, z + 1) not in corridor_cells and _key(x, z + 1) not in stair_cells:
            parts.extend(_wall_fill(
                [x, 1, z + 1], [x + 1, room_height + 2, z + 2],
                wall, wall_picker, wall_materials))

    for candidate in door_candidates:
        if _door_has_jambs(candidate, corridor_cells, room_height):
            _emit_door(parts, candidate)

    light_cells = {}
    for index in range(0, len(ordered_corridor_cells), light_spacing):
        cell = ordered_corridor_cells[index]
        x, z = cell[0], cell[1]
        key = _key(x, z)
        if key not in light_cells and key not in fixture_cells and not _inside_room(x, z, rooms):
            light_cells[key] = True
            parts.append(place_block(
                [x, room_height, z], block(lantern, {"hanging": "true"}), phase="fixture"))

    total_height = surface_level + 5 if surface_entrance else room_height + 2
    return component(
        name="BspDungeon",
        props={
            "width": width, "length": length, "room_height": room_height,
            "min_room_size": min_room_size, "target_leaf_size": target_leaf_size,
            "max_depth": max_depth, "seed": seed,
            "wide_corridor_chance": wide_corridor_chance, "light_spacing": light_spacing,
            "burial_depth": burial_depth, "surface_entrance": surface_entrance,
            "room_count": len(rooms), "connection_count": connection_count,
            "wide_connection_count": wide_connection_count, "surface_level": surface_level,
        },
        min_size=[width, total_height, length],
        body=group(parts),
    )
