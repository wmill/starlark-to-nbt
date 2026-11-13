# Tree constructors, imported into every module before user code (see
# eval/mod.rs). Each returns a JSON-compatible tagged dict that
# schema::parse_node validates; the tree crosses into Rust once, as the
# entry function's result.

def _tag(kind, **values):
    out = {"kind": kind}
    for key, value in values.items():
        if value != None:
            out[key] = value
    return out

def component(name, props, body, min_size = None, metadata = None, validators = None):
    return _tag(
        "component",
        name = name,
        props = props,
        body = body,
        min_size = min_size,
        metadata = metadata,
        validators = validators,
    )

def validator(name, assembly = None):
    return _tag(name, assembly = assembly)

def group(children):
    return _tag("group", children = children)

def fixed(value):
    return _tag("fixed", value = value)

def fill():
    return _tag("fill")

def split(axis, sizes, children):
    return _tag("split", axis = axis, sizes = sizes, children = children)

def inset(child, amount = None, x = None, y = None, z = None):
    if amount != None:
        amounts = {axis: [amount, amount] for axis in ("x", "y", "z")}
    else:
        amounts = {"x": x or [0, 0], "y": y or [0, 0], "z": z or [0, 0]}
    return _tag("inset", amounts = amounts, child = child)

def repeat(axis, count, child_extent, gap, child):
    return _tag("repeat", axis = axis, count = count, child_extent = child_extent, gap = gap, child = child)

def transform(translation, rotation_y, child_size, child):
    return _tag("transform", translation = translation, rotation_y = rotation_y, child_size = child_size, child = child)

def at(pos, child, rotation = 0, size = None):
    return _tag("at", pos = pos, child = child, rotation = rotation, size = size)

def block(block_type, block_state = None, nbt = None):
    value = {"block_type": block_type, "block_state": block_state or {}}
    if nbt != None:
        value["nbt"] = nbt
    return value

def entity(entity_type, nbt = None, yaw = 0, pitch = 0):
    return {"entity_type": entity_type, "nbt": nbt, "yaw": yaw, "pitch": pitch}

def place_entity(pos, entity):
    return _tag("place_entity", pos = pos, entity = entity)

# stage = None means stage 0; _tag drops it, so unstaged trees are unchanged.
def place_block(pos, block, phase = "structure", stage = None):
    return _tag("place_block", pos = pos, block = block, phase = phase, stage = stage)

def fill_region(min, max, block, phase = "structure", stage = None):
    return _tag("fill_region", box = {"min": min, "max": max}, block = block, phase = phase, stage = stage)

def carve_region(min, max, stage = None):
    return _tag("carve_region", box = {"min": min, "max": max}, stage = stage)

def place_assembly(pos, name, size, blocks, stage = None):
    return _tag("place_assembly", pos = pos, name = name, size = size, blocks = blocks, stage = stage)
