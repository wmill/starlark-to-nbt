# Block- and entity-data helpers for the Rust runtime. The Python runtime
# defines these as Python callables in starlark_runtime.py; keep the two in
# step until Phase 7 of docs/rust-core-plan.md removes the Python one.

def sign_nbt(lines = None, color = "black", glowing = False, back_lines = None, back_color = "black", back_glowing = False, waxed = True):
    """Sign block-entity data for block(..., nbt=...). Messages are plain
    strings: 1.21.5+ text components treat a bare string as literal text."""

    def side(text, side_color, side_glowing):
        text = (list(text or []) + ["", "", "", ""])[:4]
        return {"messages": text, "color": side_color, "has_glowing_text": bool(side_glowing)}

    return {
        "id": "minecraft:sign",
        "front_text": side(lines, color, glowing),
        "back_text": side(back_lines, back_color, back_glowing),
        "is_waxed": bool(waxed),
    }

def container_nbt(items = None, id = "minecraft:chest"):
    """Container block-entity data (chest, barrel, furnace, ...) for
    block(..., nbt=...). `items` entries are item ids, or dicts with "id" and
    optional "count" (default 1), "slot" (defaults to the next slot in
    order), and "components"."""
    packed = []
    next_slot = 0
    for entry in list(items or []):
        if type(entry) == "string":
            entry = {"id": entry}
        unknown = [key for key in entry if key not in ("id", "count", "slot", "components")]
        if unknown or "id" not in entry:
            fail("container item must have 'id' and only 'count', 'slot', 'components': %r" % (entry,))
        item = {"Slot": entry.get("slot", next_slot), "id": entry["id"], "count": entry.get("count", 1)}
        if "components" in entry:
            item["components"] = entry["components"]
        next_slot = item["Slot"] + 1
        packed.append(item)
    return {"id": id, "Items": packed}

def loot_nbt(table, seed = None, id = "minecraft:chest"):
    """Loot-table block-entity data: the container rolls `table` when first opened."""
    value = {"id": id, "LootTable": table}
    if seed != None:
        value["LootTableSeed"] = seed
    return value
