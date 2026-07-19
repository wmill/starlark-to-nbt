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
| `component(name, props, body, min_size=None, metadata=None)` | Named subtree; `min_size=[x,y,z]` is validated against the assigned region and used as the natural size when built standalone. The root may set typed placement metadata such as `metadata={"ground_level": 1}`. |
| `group(children)` | Children share the parent's region unchanged. |
| `split(axis, sizes, children)` | Partition the region along `axis` (`"x"`/`"y"`/`"z"`). `sizes` entries are `fixed(n)` or `fill()`; fills share the remainder deterministically. Overflow/underflow are errors. |
| `inset(child, amount=n)` or `inset(child, x=[lo,hi], y=[...], z=[...])` | Shrink the region by per-axis margins. |
| `repeat(axis, count, child_extent, gap, child)` | `count` copies laid out along `axis`, each `child_extent` deep, `gap` blocks apart, starting at the region min. |
| `transform(translation, rotation_y, child_size, child)` | Place a `child_size` child at `translation`, rotated 0/90/180/270 degrees around +Y. The rotated footprint must fit in the region. Block states rotate too: `facing`, `axis`, sign `rotation`, and multi-face keys (`north`/`south`/`east`/`west`). |
| `block(block_type, block_state={})` | e.g. `block("minecraft:oak_stairs", {"facing": "south", "half": "bottom"})`. States are strings. |
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
| `Carpet(width, length, material="minecraft:red_carpet")` | `[width, 1, length]` | Lay one Y above the floor fill. |
| `Ladder(height, material="minecraft:ladder")` | `[1, height, 1]` | Faces south at rotation 0; place against a north support. |
| `DiningTable(length=3, leg="minecraft:oak_fence", top="minecraft:oak_slab")` | `[length, 2, 1]` | Runs along +X; end legs and bottom-slab top. |
| `KitchenCounter(length=3, cabinet="minecraft:barrel", top="minecraft:oak_slab")` | `[length, 2, 1]` | South-facing storage with bottom-slab worktop. |

### `lib/outdoor.star`

| Component | Size | Notes |
|---|---|---|
| `Well(material="minecraft:cobblestone", post="minecraft:oak_fence", roof="minecraft:oak_slab")` | `[3, 4, 3]` | Water core, corner posts, slab roof. |
| `FenceRing(width, length, fence="minecraft:oak_fence", gate="minecraft:oak_fence_gate")` | `[width, 1, length]` | Perimeter fence, gate mid-south; needs >= 3x3. |
| `Path(length, width=1, material="minecraft:dirt_path")` | `[width, 1, length]` | Runs along +Z. |
| `Tree(height=5, log="minecraft:oak_log", leaves="minecraft:oak_leaves")` | `[3, height+1, 3]` | Persistent leaves; trunk at center. |
| `CropPlot(width, length, crop="minecraft:wheat", age="7", border="minecraft:oak_log")` | `[width, 2, length]` | Bordered moist farmland, central +Z water channel, mature crops; requires at least 5x5. |
| `FlowerBed(width, length, flower_a="minecraft:poppy", flower_b="minecraft:dandelion", border="minecraft:cobblestone")` | `[width, 2, length]` | Bordered dirt with alternating flowers; requires at least 3x3. |
| `MarketStall(width=5, depth=3, canopy="minecraft:red_wool", accent="minecraft:white_wool", post="minecraft:oak_fence")` | `[width, 4, depth]` | Faces +Z; four posts, rear counter, striped canopy. |
| `HayBaleStack(width=3, height=2, depth=2, material="minecraft:hay_block")` | `[width, height, depth]` | Tapered layers with alternating horizontal X/Z axes. |

### `lib/fortifications.star`

Linear walls run along +X. Gates, ladders, portcullises, and drawbridges face
or extend toward +Z at rotation zero.

| Component | Size | Notes |
|---|---|---|
| `BattlementWall(length, height, material="minecraft:stone_bricks")` | `[length, height+1, 1]` | Solid curtain wall with alternating merlons; requires length >= 3 and height >= 2. |
| `SquareTower(size, height, material="minecraft:stone_bricks")` | `[size, height+1, size]` | Hollow tower with two levels of arrow slits and a crenellated crown; requires size >= 5 and height >= 10. |
| `Portcullis(width=3, height=4, material="minecraft:iron_bars")` | `[width, height, 1]` | Self-carving closed portcullis; requires width and height >= 2. |
| `Gatehouse(width=9, height=8, depth=5, opening_width=3, opening_height=4, material=..., bars="minecraft:iron_bars")` | `[width, height+1, depth]` | Centered tunnel, front portcullis, arrow slits, and battlements; leaves at least two blocks per side. |
| `Drawbridge(width=3, length=7, deck="minecraft:dark_oak_planks", chain="minecraft:chain")` | `[width, 2, length]` | Lowered deck extending toward +Z with horizontal side chains. |
| `PalisadeWall(length, height=5, log="minecraft:spruce_log")` | `[length, height+1, 1]` | Vertical logs with alternating raised tips; requires length >= 2 and height >= 3. |
| `PalisadeGate(width=5, height=6, log="minecraft:spruce_log", door="minecraft:dark_oak_door")` | `[width, height+1, 1]` | Atomic double door beneath a timber fighting platform; requires width >= 5 and height >= 4. |
| `Watchtower(size=5, platform_height=6, post="minecraft:spruce_log", deck="minecraft:spruce_planks", railing="minecraft:spruce_fence")` | `[size, platform_height+2, size]` | Four-post tower with a railed deck and south-facing ladder passing through a deck opening; requires size >= 5 and platform height >= 4. |

## Worked examples

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
- `examples/market_square.star` — 35x6x35 civic square: central well and
  crossing paths, four rotated striped stalls, flower beds, benches, and lamps.
- `examples/frontier_outpost.star` — 29x14x29 timber fort with ground level 1:
  complete palisade, four rotated watchtowers, double gate, furnished barracks,
  storage, and lamps. Its foundation and path occupy local Y=0 for embedding.
- `examples/stone_pass_fortress.star` — 35x16x21 linear stone defense: twin
  towers, battlement walls, gatehouse and portcullis, moat, and drawbridge.
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

## Errors

Failures raise diagnostics with a stable code, the component path, and the
offending coordinates/region: `component_too_small`, `split_overflow`,
`split_underflow`, `repeat_overflow`, `inset_collapsed`, `transform_overflow`,
`component_overflow`, `root_overflow`, `block_conflict`, `assembly_overflow`,
`invalid_metadata`, `metadata_not_root`, `load_error`, `load_cycle`,
`starlark_error`. Starlark syntax/eval errors include file:line spans;
build-rule errors identify the component path instead.
