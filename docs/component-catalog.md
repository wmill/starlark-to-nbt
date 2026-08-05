# starlark-to-nbt component catalog

This document is written to be pasted into an LLM prompt. It teaches the
Starlark DSL for generating Minecraft Java 1.21.7 structures and catalogs the
reusable component library in `lib/`.

## How a script runs

A script defines a `build(...)` entry function returning a single node tree.
Arguments arrive as keyword props (`--arg name=value` on the CLI; ints, floats,
and `true`/`false` are auto-coerced). The root region size is taken from
`width`/`height`/`length` props if all three are present, otherwise from the
root component's `min_size`.

```python
load("../lib/structural.star", "SolidWall")

def build(width=9, wall_height=4):
    return component(
        name="Demo",
        props={"width": width},
        min_size=[width, wall_height, 1],
        metadata={"ground_level": 0},
        body=SolidWall(width, wall_height),
    )
```

The root component may declare `metadata={"ground_level": n}`. Ground level is
the local Y coordinate that should align with the terrain walking plane. The
build companion metadata derives `y_offset = -ground_level`; metadata describes
placement but never shifts generated coordinates automatically. If omitted,
ground level defaults to 0. Metadata is only valid on the root component.

Every CLI build writes a deterministic companion beside the structure. For
`demo.nbt`, `demo.meta.json` contains both `ground_level` and `y_offset`. The NBT
itself remains a standard Minecraft structure with no custom metadata tags.

## Coordinates and geometry

- `+X` is east, `+Y` is up, `+Z` is south. All positions are integer block
  coordinates local to the enclosing region, starting at `[0, 0, 0]`.
- Boxes are **half-open**: `min` inclusive, `max` exclusive.
  `fill_region([0,0,0],[3,1,3],...)` fills a 3x1x3 slab.
- A component may only write inside its assigned region. Writing outside is a
  build error (`component_overflow`), never silently clamped.
- Sibling regions may overlap in space; conflicts are only detected when two
  writes actually collide on a cell.

## Build phases and overlap rules

Operations execute in three phases, in order:

1. **STRUCTURE** — `fill_region` (default), `place_block(phase="structure")`.
   Bulk geometry. Writing the **identical block** onto an occupied cell is
   allowed (walls may share corners); writing a **different** block is a
   `block_conflict` error.
2. **CARVE** — `carve_region`. Overwrites anything with air. Use it to cut
   doorways/windows through structure fills. Carved cells that stay empty are
   written to the template as explicit air (they clear terrain on paste);
   untouched cells are omitted entirely (terrain is preserved).
3. **FIXTURE** — `place_block(phase="fixture")`, `fill_region(phase="fixture")`,
   `place_assembly`. Furniture and details. Fixtures may land on air or carved
   cells but **never** overwrite solid blocks, even identical ones.

Multi-block objects that must be placed all-or-nothing (doors, beds) use
`place_assembly`, which validates and places atomically.

## DSL reference

| Constructor | Semantics |
|---|---|
| `component(name, props, body, min_size=None, metadata=None, validators=None)` | Named subtree; `min_size=[x,y,z]` is validated against the assigned region and used as the natural size when built standalone. The root may set typed placement metadata such as `metadata={"ground_level": 1}`. Optional validators apply to matching operations in this component subtree. |
| `validator("door_supported_on_both_sides", assembly="name")` | Post-execution check for matching named door assemblies. Both door halves need solid left/right jambs and clear front/back cells. |
| `group(children)` | Children share the parent's region unchanged. |
| `split(axis, sizes, children)` | Partition the region along `axis` (`"x"`/`"y"`/`"z"`). `sizes` entries are `fixed(n)` or `fill()`; fills share the remainder deterministically. Overflow/underflow are errors. |
| `inset(child, amount=n)` or `inset(child, x=[lo,hi], y=[...], z=[...])` | Shrink the region by per-axis margins. |
| `repeat(axis, count, child_extent, gap, child)` | `count` copies laid out along `axis`, each `child_extent` deep, `gap` blocks apart, starting at the region min. |
| `transform(translation, rotation_y, child_size, child)` | Place a `child_size` child at `translation`, rotated 0/90/180/270 degrees around +Y. The rotated footprint must fit in the region. Block states rotate too: `facing`, `axis`, sign `rotation`, and multi-face keys (`north`/`south`/`east`/`west`). |
| `block(block_type, block_state={}, nbt=None)` | e.g. `block("minecraft:oak_stairs", {"facing": "south", "half": "bottom"})`. States are strings. `nbt` is an optional object of block-entity data (sign text, etc.) serialized onto that block instance. |
| `entity(entity_type, nbt=None, yaw=0, pitch=0)` | Declares an entity. Engine-owned `id`, `Pos`, `Rotation`, and `UUID` fields are reserved. Rotation zero faces +Z (south). |
| `place_entity(pos, entity)` | Places an entity at an integer ground-cell anchor. Structure NBT centers it at X/Z + 0.5; transforms rotate both anchor and yaw. |
| `sign_nbt(lines=None, color="black", glowing=False, back_lines=None, back_color="black", back_glowing=False, waxed=True)` | Sign block-entity data for `block(..., nbt=...)`: up to four `lines` of front text, dye `color`, glow-ink `glowing`. Signs are waxed by default so pasted text is not editable. |
| `container_nbt(items=None, id="minecraft:chest")` | Container block-entity data (chest, barrel, furnace, hopper, ...). `items` entries are item ids or `{"id", "count", "slot", "components"}` dicts; omitted slots are assigned in order. Set `id` to the container's block id. |
| `loot_nbt(table, seed=None, id="minecraft:chest")` | Container that rolls the named loot table (e.g. `"minecraft:chests/simple_dungeon"`) when first opened. |
| `place_block(pos, block, phase="structure")` | Single block; `phase` is `"structure"` or `"fixture"`. |
| `fill_region(min, max, block, phase="structure")` | Box fill. |
| `carve_region(min, max)` | Box of air (CARVE phase). |
| `place_assembly(pos, name, size, blocks)` | Atomic multi-block placement; `blocks` is a list of `{"pos": [...], "block": block(...)}` offsets inside `size`. |

`load("relative/path.star", "Name", ...)` imports symbols from another file,
resolved relative to the loading file. Standard Starlark applies: `def`,
`if`/`elif`/`else`, `for` over `range(...)` or lists, list comprehensions,
no `while`, no recursion.

## Composition patterns

**Walls on four sides.** Walls run along +X, 1 thick in Z, and are rotated into
place. Side walls slot between the corner columns of the front/back walls:

```python
transform([0, 1, 0],          0, [w, h, 1], SolidWall(w, h))            # north (z=0)
transform([0, 1, l - 1],      0, [w, h, 1], SolidWall(w, h))            # south
transform([0, 1, 1],         90, [l - 2, h, 1], SolidWall(l - 2, h))    # west (x=0)
transform([w - 1, 1, 1],     90, [l - 2, h, 1], SolidWall(l - 2, h))    # east
```

**Openings carve themselves.** Doors, windows, and archways include their own
`carve_region`, so placing one *over* an existing wall cuts the hole and
installs the fixture in one step:

```python
transform([w // 2, 1, l - 1], 0, [1, 2, 1], SingleDoor())   # door in south wall
```

**Default orientation is south (+Z).** Components with a face (doors, windows,
benches, shutters) face +Z at rotation 0. In a wall at `z = l - 1` facing
outward/south, use rotation 0; in a wall at `z = 0`, rotate 180; for `x = 0`
(west-facing) use 90; for `x = w - 1` (east-facing) use 270.

**Fixtures need empty space.** Furniture sits on top of floors (one Y above the
floor fill) and errors if a solid block is in the way.

## Component library

All components declare `min_size` equal to what they actually draw, so any of
them builds standalone. `lib/showcase.star` builds any single component:
`build(name="GableRoof")` or `rotated(name="GableRoof", rotation=90)`.

### `lib/structural.star`

| Component | Size (X,Y,Z) | Notes |
|---|---|---|
| `Foundation(width, length, depth=1, material="minecraft:cobblestone")` | `[width, depth, length]` | Solid pad. |
| `Floor(width, length, material="minecraft:oak_planks")` | `[width, 1, length]` | Single layer. |
| `SolidWall(width, height, material="minecraft:stone_bricks")` | `[width, height, 1]` | Runs along +X. |
| `WindowedWall(width, height, spacing=3, material=..., pane="minecraft:glass_pane")` | `[width, height, 1]` | 1x2 pane windows every `spacing` starting at x=2; needs width >= 5, height >= 4. |
| `TimberFrameWall(width, height, log="minecraft:oak_log", infill="minecraft:white_terracotta")` | `[width, height, 1]` | Log posts/beams + plaster; needs >= 3x3. |
| `Column(height, material="minecraft:quartz_pillar")` | `[1, height, 1]` | Vertical pillar. |
| `Balcony(width, depth=2, material=..., railing="minecraft:oak_fence")` | `[width, 2, depth]` | Deck + railing on front/side edges. |
| `StraightStaircase(width, rise, stair="minecraft:oak_stairs")` | `[width, rise, rise]` | Ascends one block per row toward +Z; south-facing stairs. |
| `Footbridge(width, length, deck="minecraft:oak_planks", railing="minecraft:oak_fence")` | `[width, 2, length]` | Runs along +Z; plank deck with connected side rails. |

### `lib/openings.star` (all carve their own hole; face south at rotation 0)

| Component | Size | Notes |
|---|---|---|
| `SingleDoor(material="minecraft:oak_door")` | `[1, 2, 1]` | Atomic two-half door. |
| `DoubleDoor(material="minecraft:oak_door")` | `[2, 2, 1]` | Mirrored hinges. |
| `Window(width=1, height=2, pane="minecraft:glass_pane")` | `[width, height, 1]` | Glass panes. |
| `ShutteredWindow(width=1, height=2, pane=..., shutter="minecraft:oak_trapdoor")` | `[width+2, height, 1]` | Open-trapdoor shutters flank the panes. |
| `Archway(width, height, stair="minecraft:stone_brick_stairs")` | `[width, height, 1]` | Carved opening, upside-down stair corners; needs >= 3x3. |

### `lib/roofs.star` (sit on y=0 of their region; place above walls)

| Component | Size | Notes |
|---|---|---|
| `GableRoof(width, length, stair="minecraft:oak_stairs", ridge="minecraft:oak_planks", gable=None)` | `[width, (width+1)//2, length]` | Slopes along +X, ridge along +Z; triangular gable ends are closed in `gable` material (defaults to `ridge`). |
| `ShedRoof(width, length, stair=...)` | `[width, width, length]` | Single 45-degree slope ascending +X. |
| `FlatRoof(width, length, slab="minecraft:oak_slab", trim="minecraft:oak_fence")` | `[width, 2, length]` | Slab deck + fence parapet. |
| `PyramidRoof(size, stair=..., cap="minecraft:oak_planks")` | `[size, (size+1)//2, size]` | Square footprint. |

### `lib/fixtures.star` (FIXTURE phase — place into empty/carved space)

| Component | Size | Notes |
|---|---|---|
| `Bench(length, stair="minecraft:oak_stairs")` | `[length, 1, 1]` | Faces south. |
| `Chair(stair=...)` | `[1, 1, 1]` | Faces south. |
| `Table(leg="minecraft:oak_fence", top="minecraft:oak_pressure_plate")` | `[1, 2, 1]` | Fence + pressure plate. |
| `Bed(material="minecraft:red_bed")` | `[1, 1, 2]` | Atomic; foot at z=0, head at z=1. |
| `BookshelfWall(width, height, material="minecraft:bookshelf")` | `[width, height, 1]` | Stands against a wall. |
| `Fireplace(height=5, material="minecraft:stone_bricks", fire="minecraft:campfire")` | `[3, height, 1]` | Hearth + chimney; needs height >= 4. |
| `LanternPost(height=3, post="minecraft:oak_fence", lantern="minecraft:lantern")` | `[1, height+1, 1]` | Post + lantern. |
| `Chest(items=None, loot=None, material="minecraft:chest")` | `[1, 1, 1]` | Faces south; `items` preloads slots, or `loot` names a loot table rolled on first open. |
| `Barrel(items=None, loot=None, material="minecraft:barrel")` | `[1, 1, 1]` | Faces south; same item/loot props as Chest. |
| `Furnace(items=None, material="minecraft:furnace")` | `[1, 1, 1]` | Faces south, unlit; item slots are 0 input, 1 fuel, 2 output. |
| `Sign(lines=None, material="minecraft:oak_sign", color="black", glowing=False)` | `[1, 1, 1]` | Standing sign facing south; `lines` is up to four strings of front text. |
| `WallSign(lines=None, material="minecraft:oak_wall_sign", color="black", glowing=False)` | `[1, 1, 1]` | Wall sign facing south; place against a north support. |
| `Carpet(width, length, material="minecraft:red_carpet")` | `[width, 1, length]` | Lay one Y above the floor fill. |
| `Ladder(height, material="minecraft:ladder")` | `[1, height, 1]` | Faces south at rotation 0; place against a north support. |
| `DiningTable(length=3, leg="minecraft:oak_fence", top="minecraft:oak_slab")` | `[length, 2, 1]` | Runs along +X; end legs and bottom-slab top. |
| `KitchenCounter(length=3, cabinet="minecraft:barrel", top="minecraft:oak_slab")` | `[length, 2, 1]` | South-facing storage with bottom-slab worktop. |

### `lib/outdoor.star`

| Component | Size | Notes |
|---|---|---|
| `Horse(variant=0, tame=True)` | `[1, 2, 1]` | Persistent, usable horse facing +Z. `variant` is Minecraft's packed coat/marking value; transforms rotate its yaw. |
| `Well(material="minecraft:cobblestone", post="minecraft:oak_fence", roof="minecraft:oak_slab")` | `[3, 4, 3]` | Water core, corner posts, slab roof. |
| `FenceRing(width, length, fence="minecraft:oak_fence", gate="minecraft:oak_fence_gate")` | `[width, 1, length]` | Perimeter fence, gate mid-south; needs >= 3x3. |
| `Path(length, width=1, material="minecraft:dirt_path")` | `[width, 1, length]` | Runs along +Z. |
| `Tree(height=5, log="minecraft:oak_log", leaves="minecraft:oak_leaves")` | `[3, height+1, 3]` | Persistent leaves; trunk at center. |
| `RoundTree(trunk_height=7, log="minecraft:oak_log", leaves="minecraft:oak_leaves")` | `[5, trunk_height+1, 5]` | Fuller 5x5 canopy tapering cross -> diamond -> full square -> diamond -> cross from bottom to cap; requires trunk_height >= 4. |
| `CropPlot(width, length, crop="minecraft:wheat", age="7", border="minecraft:oak_log")` | `[width, 2, length]` | Bordered moist farmland, central +Z water channel, mature crops; requires at least 5x5. |
| `FlowerBed(width, length, flower_a="minecraft:poppy", flower_b="minecraft:dandelion", border="minecraft:cobblestone")` | `[width, 2, length]` | Bordered dirt with alternating flowers; requires at least 3x3. |
| `MarketStall(width=5, depth=3, canopy="minecraft:red_wool", accent="minecraft:white_wool", post="minecraft:oak_fence")` | `[width, 4, depth]` | Faces +Z; four posts, rear counter, striped canopy. |
| `HayBaleStack(width=3, height=2, depth=2, material="minecraft:hay_block")` | `[width, height, depth]` | Tapered layers with alternating horizontal X/Z axes. |
| `Pergola(width=5, depth=5, height=4, post="minecraft:oak_log", beam="minecraft:stripped_oak_log", slat="minecraft:oak_slab")` | `[width, height+1, depth]` | Corner posts, perimeter top beams, and an open slatted lattice roof; requires at least 3x3. |

### `lib/dungeons.star`

| Component | Size | Notes |
|---|---|---|
| `BspDungeon(width=48, length=48, room_height=4, min_room_size=5, target_leaf_size=18, max_depth=8, seed=0, wide_corridor_chance=0.30, light_spacing=8, burial_depth=4, surface_entrance=True, wall=..., floor=..., stair=..., door=..., torch=..., lantern=..., wall_picker=None)` | Exact `[width, generated height, length]` | Deterministic underground BSP rooms and connected tunnels. Narrow links use atomic doors when both jambs remain intact, otherwise they remain open; wide links use three-block stone arches. Every room is lit by standing torches and corridors by hanging lanterns. With an entrance, a north-edge hut and descending stair reach surface level `room_height + burial_depth + 2`; without one, height is `room_height + 2` and callers choose placement metadata. Requires enough space for inset rooms; probabilities and split controls are validated. |

The component props include `room_count`, `connection_count`,
`wide_connection_count`, and `surface_level`, making a generated topology easy
to inspect without embedding custom data in structure NBT. Its leaf-room and
bottom-up sibling-connection strategy follows the approaches described by
[RogueBasin](https://www.roguebasin.com/index.php/Basic_BSP_Dungeon_generation)
and [Gonzalo Uribe](https://medium.com/@guribemontero/dungeon-generation-using-binary-space-trees-47d4a668e2d0).
`wall_picker(base_wall, x, y, z)` can return a block identifier for each room,
corridor, and entrance-hut wall or ceiling cell. Results are cached by local
coordinate so overlapping shell writes remain consistent; omitting the picker
retains compact bulk fills.

### `lib/fortifications.star`

Linear walls run along +X. Gates, ladders, portcullises, and drawbridges face
or extend toward +Z at rotation zero. `BattlementWall`, `SquareTower`, and
`Gatehouse` accept an optional `material_picker(base_material, x, y, z)`
callback returning a block identifier. Coordinates are local to the component;
without a picker they retain their compact bulk-fill behavior.

| Component | Size | Notes |
|---|---|---|
| `BattlementWall(length, height, material="minecraft:stone_bricks", material_picker=None)` | `[length, height+1, 1]` | Solid curtain wall with alternating merlons; requires length >= 3 and height >= 2. |
| `SquareTower(size, height, material="minecraft:stone_bricks", material_picker=None)` | `[size, height+1, size]` | Hollow tower with two levels of arrow slits and a crenellated crown; requires size >= 5 and height >= 10. |
| `Portcullis(width=3, height=4, material="minecraft:iron_bars")` | `[width, height, 1]` | Self-carving closed portcullis; requires width and height >= 2. |
| `Gatehouse(width=9, height=8, depth=5, opening_width=3, opening_height=4, material=..., bars="minecraft:iron_bars", material_picker=None)` | `[width, height+1, depth]` | Centered tunnel, front portcullis, arrow slits, and battlements; leaves at least two blocks per side. |
| `Drawbridge(width=3, length=7, deck="minecraft:dark_oak_planks", chain="minecraft:chain")` | `[width, 2, length]` | Lowered deck extending toward +Z with horizontal side chains. |
| `PalisadeWall(length, height=5, log="minecraft:spruce_log")` | `[length, height+1, 1]` | Vertical logs with alternating raised tips; requires length >= 2 and height >= 3. |
| `PalisadeGate(width=5, height=6, log="minecraft:spruce_log", door="minecraft:dark_oak_door")` | `[width, height+1, 1]` | Atomic double door beneath a timber fighting platform; requires width >= 5 and height >= 4. |
| `Watchtower(size=5, platform_height=6, post="minecraft:spruce_log", deck="minecraft:spruce_planks", railing="minecraft:spruce_fence")` | `[size, platform_height+2, size]` | Four-post tower with a railed deck and south-facing ladder passing through a deck opening; requires size >= 5 and platform height >= 4. |
| `RampartWall(length, height=7, stone="minecraft:stone_bricks", core="minecraft:stone", accent="minecraft:infested_stone_bricks", railing="minecraft:oak_fence")` | `[length, height+2, 3]` | Three-thick layered curtain wall (outer/core/inner stone); torch-lit merlon crown in `accent` with a fence walkway rail filling the gaps; requires length >= 3 and height >= 3. |
| `RampartTower(size=5, height=10, stone="minecraft:stone_bricks", accent="minecraft:infested_stone_bricks", trim="minecraft:chiseled_stone_bricks", door="minecraft:oak_door")` | `[size, height+2, size]` | Hollow tower with chiseled corner quoins, an interior ladder, a south door, and a torch-lit merlon crown matching `RampartWall`; requires size >= 5 and height >= 8. |

### `lib/random.star`

Deterministic visual patterning uses a checked-in table of 1,024 independent
pseudorandom decimals in `[0, 1)`. Create caller-owned state with
`random_cycle(offset=0)`, then call `random_number(cycle)` to advance and wrap.
Separate cycles are independent. This utility is reproducible patterning data,
not security-sensitive randomness.

```python
load("../lib/random.star", "random_cycle", "random_number")

cycle = random_cycle()
roll = random_number(cycle)
```

### `lib/dwellings.star`

Composite residential buildings assembled from `structural.star` /
`openings.star` / `roofs.star` / `fixtures.star` primitives. Draw from
`[0, 0, 0]`; entrance faces +Z (south) at rotation zero.

| Component | Size | Notes |
|---|---|---|
| `GuestHouse(width=7, depth=6, wall_height=4, log="minecraft:oak_log", infill="minecraft:cobblestone", door="minecraft:oak_door", roof_stair="minecraft:oak_stairs", roof_ridge="minecraft:oak_log", bed="minecraft:lime_bed")` | `[width, 1+wall_height+(width+1)//2, depth]` | Single-room cottage: log-post/cobblestone walls, south door, north window, gable roof (use an odd `width` for a visible ridge beam), furnished with a bed, chest, bookshelves, and torches; requires width >= 5 and depth >= 5. |

### `lib/redstone.star`

Redstone parts, wiring, logic gates, circuits, and contraptions. **Signal flows
along +Z (south):** directional parts default `facing="south"`, and on a gate,
inputs enter the north edge (`z=0`) and the output leaves the south edge. Gates
and circuits draw their own solid `base` slab at `y=0` (default
`minecraft:smooth_stone`) with the redstone logic at `y=1`, so they build
standalone and drop onto any floor. State values are strings (`delay="3"`,
`powered="false"`). Rotation is handled by the engine (cardinal `facing`, dust
`north/east/south/west` connection keys, and `axis` all rotate; `up`/`down`
facings and lever/button `face` are left alone).

**Support contract:** dust, repeaters, comparators, torches, levers, buttons,
and pressure plates pop off in-game unless a solid block sits on their
attachment side (below, or behind a wall-mounted part). The build pipeline
enforces this and fails with an `unsupported_block` error naming the offending
block, its position, and the cell that needs a solid block. Bare parts default
to `base=None` and must land on existing solid blocks; pass
`base="minecraft:..."` and the part brings its own supporting block — the part
moves to `y=1` over the base at `y=0` and `min_size` becomes `[1, 2, 1]`
(`RedstoneWallTorch` instead grows to `[1, 1, 2]`: base at `z=0`, torch at
`z=1`). When wiring across a gap, prefer `RedstoneWire(base=...)` per cell or a
`RedstoneLine`, which is already self-supporting.

Gate inputs are isolated and their port coordinates are described below.
Timing, piston, and inventory mechanisms use Java 1.21.7 behavior; their
standalone layouts and rotations are covered by the library test harness.

| Component | Size (X,Y,Z) | Notes |
|---|---|---|
| `RedstoneTorch(lit=True, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | Standing torch (place on a block, or pass `base`). |
| `RedstoneWallTorch(facing="south", lit=True, base=None)` | `[1, 1, 1]` (`[1, 1, 2]` with base) | Wall torch; needs a support behind the visible face. With `base`, only `facing="south"` (rotate via `transform`). |
| `RedstoneWire(power=0, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | One dust cell; connections update in-world, `power` is 0-15. |
| `RedstoneLamp(lit=False)` | `[1, 1, 1]` | Redstone lamp block. |
| `RedstoneBlock()` | `[1, 1, 1]` | Always-on power source. |
| `Lever(face="floor", facing="south", powered=False, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | `face` is floor/wall/ceiling; `base` only with `face="floor"`. |
| `Button(material="minecraft:stone_button", face="floor", facing="south", powered=False, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | Any button material; `base` only with `face="floor"`. |
| `PressurePlate(material="minecraft:stone_pressure_plate", powered=False, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | Sits on the block below (solid, fence, wall, or hopper). |
| `WeightedPressurePlate(material="minecraft:light_weighted_pressure_plate", power=0, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | Analog light/heavy plate; `power` is 0-15. |
| `Repeater(delay=1, facing="south", locked=False, powered=False, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | Output points toward `facing`; `delay` 1-4. |
| `Comparator(mode="compare", facing="south", powered=False, base=None)` | `[1, 1, 1]` (`[1, 2, 1]` with base) | `mode` compare/subtract. |
| `Observer(facing="south", powered=False)` | `[1, 1, 1]` | Sensing face is `facing`; pulse leaves the back. |
| `Piston(sticky=False, facing="south", extended=False)` | Direction-dependent | `extended` atomically places a body/head pair for all six facings. |
| `Dispenser(items=None, facing="south")` | `[1, 1, 1]` | `items` preloads slots (see `container_nbt`). |
| `Dropper(items=None, facing="south")` | `[1, 1, 1]` | Same item model as Dispenser. |
| `Hopper(items=None, facing="down")` | `[1, 1, 1]` | `facing` is down or a cardinal (never up). |
| `NoteBlock(instrument="harp", note=0, powered=False)` | `[1, 1, 1]` | `note` 0-24. |
| `TargetBlock()` | `[1, 1, 1]` | Emits redstone when hit. |
| `DaylightDetector(inverted=False)` | `[1, 1, 1]` | `inverted` makes it a night sensor. |
| `CopperBulb(material="minecraft:copper_bulb", lit=False, powered=False)` | `[1, 1, 1]` | Pulse-toggle memory/light; material selects oxidation and wax state. |
| `RedstoneLine(length, base="minecraft:smooth_stone")` | `[1, 2, length]` | Base row + dust line along +Z. |
| `VerticalRedstone(height, base=...)` | `[1, height+1, height]` | Block staircase carrying signal up one level per step along +Z. |
| `NotGate(base=...)` | `[1, 2, 4]` | Inverter; input z=0, output z=3. |
| `OrGate(base=...)` | `[3, 2, 4]` | Isolated inputs at x=0/x=2 north; centered south output. |
| `NorGate(base=...)` | `[3, 2, 7]` | Isolated OR followed by an inverter. |
| `NandGate(base=...)` | `[3, 2, 5]` | Invert each input, then OR. |
| `AndGate(base=...)` | `[3, 2, 8]` | NAND then invert. |
| `XorGate(base=...)` | `[5, 2, 7]` | Isolated torch XOR; inputs x=0/x=4, output x=2. |
| `XnorGate(base=...)` | `[5, 2, 10]` | XOR core followed by an inverter. |
| `RedstoneClock(period=2, base=...)` | `[5, 2, 8]` | Four-repeater pulse loop; north pulse starts it, center lever locks/pauses a stage, south-east repeater is output. |
| `HopperClock(items=None, base=...)` | `[7, 2, 3]` | Alternating comparator outputs; more hopper items produce a longer period. |
| `TFlipFlop(base=...)` | `[1, 2, 5]` | Copper-bulb toggle memory with north pulse input and south comparator output. |
| `PulseExtender(ticks=4, base=...)` | `[4, 2, (ticks+3)//4+5]` | Direct/delayed copper-bulb one-shot; input pulse must be shorter than positive `ticks`. |
| `LampMatrix(width, height, lamp="minecraft:redstone_lamp", base=...)` | `[width, height, 2]` | Lamp wall on a backing panel — a drivable display. |
| `PistonTrapdoor(width=2, base=...)` | `[width, 3, 4]` | Retracting floor bridge; lever/dust on a raised control row at z=0 drive the piston row at z=1, powered = closed. |
| `PistonDoor(base=..., door="minecraft:smooth_stone")` | `[6, 4, 3]` | 2x2 side-piston door; integrated top lever, powered = closed. |
| `ItemSorter(target="minecraft:redstone", filler="minecraft:light_gray_stained_glass_pane", base=...)` | `[3, 5, 6]` | Wiki-standard overflow-safe 41+4 hopper filter; feed the top hopper, sorted items collect in the bottom barrel, non-matching items stay on top for transport. |

## Worked examples

- `examples/mega_castle.star` — Aethercourt, a 48x40x48 high-fantasy castle
  with four roofed towers, wall walks, gatehouse, three-level furnished palace,
  stocked armory, stable with four horses, gardens, and placement ground level 1.
- `examples/cottage.star` — timber-framed cottage: four rotated walls, gable
  roof with plank gable ends, self-carving door/windows, furnished interior.
  The reference for what a generated script should look like.
- `examples/keep.star` — 33x20x33 castle: four towers at each rotation,
  curtain walls, gate (archway + double door carved through a sibling wall),
  central keep with an embedded ground floor, ladder-accessible y-repeated
  upper floors, and a pyramid roof, plus courtyard dressing.
- `examples/riverside_farmstead.star` — 41x16x35 village scene with ground
  level 1: furnished two-storey farmhouse, embedded stream, footbridge,
  irrigated crops, hay storage, paths, trees, and lanterns.
- `examples/market_square.star` — 35x7x35 civic square: central well and
  crossing paths, four rotated striped stalls, flower beds, benches, and lamps.
- `examples/frontier_outpost.star` — 29x14x29 timber fort with ground level 1:
  complete palisade, four rotated watchtowers, double gate, furnished barracks,
  storage, and lamps. Its foundation and path occupy local Y=0 for embedding.
- `examples/stone_pass_fortress.star` — 35x16x21 linear stone defense: twin
  towers, battlement walls, gatehouse and portcullis, moat, and drawbridge;
  deterministic weathering defaults to 15% mossy and 7% cracked stone and is
  configurable through `mossy_percent` / `cracked_percent` build arguments.
- `examples/rampart_ward.star` — 27x13x27 walled ward corner with ground
  level 1, in the style of `training-samples/micmokum-town1.nbt`: a
  `RampartTower` and two gapped `RampartWall` runs enclosing three
  differently-bedded `GuestHouse` cottages, a well, and `RoundTree`s.
- `examples/medieval_manor.star` — 20x18x18 source-inspired medieval manor:
  stone ground floor, birch-and-oak timber upper storey, oversized white-wool
  roof with glazed end gables, two walkable stair flights, and fully furnished
  workshop, kitchen, bedrooms, library, enchanting area, and loft storage.
- `examples/claude_pergola.star` — 11x7x13 garden nook with ground level 1: an
  open pergola sheltering a bench and a standing sign with glowing orange
  block-entity text, plus an entrance path, flower beds, and lantern posts.
- `examples/redstone_showcase.star` — 52x7x45 interactive redstone lab with
  independently controlled truth-table stations for all seven gates, labeled
  timing/memory circuits, and signed piston, sorting, display, and analog-input
  demonstrations. Blue/green controls are A/B, orange controls are pulses, and
  south-edge lamps are outputs.
- `examples/procedural_facade.star` — 29x8x1 pattern wall gallery: checkerboard,
  gradient, diagonal-stripe, and triangular-wave-crenellation panels, each a
  different index-driven material formula.
- `examples/procedural_pavilion.star` — 13x8x13 garden pavilion: one
  asymmetric wing authored once and stamped into all four quadrants by looping
  over `transform()` rotations.
- `examples/procedural_ziggurat.star` — 15x17x15 stepped tower grown by a
  for-loop that shrinks the footprint and cycles a material gradient per
  level, capped with a wave-formula crenellated crown.
- `examples/procedural_spiral_stair.star` — 9x23x9 hollow shaft with a spiral
  staircase built by a hand-rolled per-step loop, since `repeat()` cannot vary
  rotation or position between copies; full-block corner landings keep every
  90-degree turn walkable under Minecraft movement rules.
- `examples/procedural_rotunda.star` — 19x19x19 round glass rotunda: a
  thin cylindrical wall shell and true hemispherical dome shell, both
  voxelized with integer distance-squared circle tests (no `sqrt()`
  available); window openings are cut into the wall by a raster-order
  modulo counter.
- `examples/procedural_twisting_spire.star` — 9x40x9 tower built from 20
  stacked square rings whose (x,z) offset cycles through a small fixed
  lookup table (not true rotation matrices, since Starlark here has no
  trig or `**`), producing a visibly twisting silhouette.
- `examples/procedural_crystal_cave.star` — 25x7x17 elliptical cavern: an
  integer distance-formula ellipse test bounds a hollow shell (floor,
  thin wall ring, ceiling), scattered with stalagmites, stalactites, and
  amethyst clusters via a hand-rolled deterministic integer hash function
  standing in for `random()`.
- `examples/procedural_fractal_tree.star` — 12x22x14 iterative L-system
  tree: a worklist loop (no recursion, which the host forbids) grows a
  trunk into branching generations from a fixed table of integer direction
  vectors, drawn with an integer line-stepper and capped with
  distance-squared leaf-blob spheres.
- `examples/bsp_dungeon.star` — 96x15x96 deterministic underground dungeon:
  iteratively subdivided BSP rooms, door and arch corridors, supported room and
  tunnel lighting, and a north-edge surface hut with a carved descending stair.
  Root metadata places its surface walking plane at local Y=10. An opt-in
  validator checks every `bsp_dungeon_door` assembly after execution. Seeded
  weathering defaults to 15% mid-wall moss and 7% cracked stone; moss ranges
  from 1.5 times the configured rate at wall bases to 0.5 times at wall tops.
  Both percentages are configurable build arguments.

## Errors

Failures raise diagnostics with a stable code, the component path, and the
offending coordinates/region: `component_too_small`, `split_overflow`,
`split_underflow`, `repeat_overflow`, `inset_collapsed`, `transform_overflow`,
`component_overflow`, `root_overflow`, `block_conflict`, `assembly_overflow`,
`invalid_metadata`, `metadata_not_root`, `load_error`, `load_cycle`,
`invalid_validator`, `validator_no_targets`, `invalid_validator_target`,
`door_not_supported`, `doorway_obstructed`, `starlark_error`. Starlark syntax/eval errors include file:line spans;
build-rule errors identify the component path instead.
