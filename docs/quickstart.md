# Build a custom scene

Write a Starlark `build()` function returning a sized component. Library
components contain their own geometry; use `at(position, child, rotation=0)`
to position them without repeating their dimensions.

```python
load("../lib/structural.star", "Foundation")
load("../lib/outdoor.star", "MarketStall", "FlowerBed")
load("../lib/fixtures.star", "Bench")

def build():
    return component(
        name="GardenMarket",
        props={},
        min_size=[13, 6, 13],
        metadata={"ground_level": 1},
        body=group([
            Foundation(13, 13),
            at([1, 1, 1], MarketStall()),
            at([9, 1, 1], MarketStall(canopy="minecraft:blue_wool"), rotation=90),
            at([2, 1, 8], FlowerBed(5, 3)),
            at([9, 1, 8], Bench(3), rotation=90),
        ]),
    )
```

## Compile and place

Call `build_starlark_structure(source=<script>)` to compile only. The result
contains an `artifact_id` for `place_starlark_structure`.

When world coordinates are known, use one call:
`build_starlark_structure(source=<script>, placement={"x": 100, "y": 64, "z": 100})`.
This writes to the world only after compilation succeeds. Compilation alone
does not change the world. Placement can replace existing blocks.

`placement.y` is the desired walking plane. Here ground_level=1 embeds the
foundation one block below it; the offset is automatic. Choose coordinates
before placing. A lost placement response means the outcome is unknown:
inspect the world before retrying, especially when entities are included.

## Geometry rules

- Coordinates are local integers: +X east, +Y up, +Z south.
- Sizes are `[width, height, length]`. Root `min_size` must contain every part.
- Boxes have exclusive maxima: `fill_region([0,0,0], [3,1,3], block("minecraft:stone"))`
  makes a 3 by 1 by 3 slab.
- `at` infers a component's `min_size`. For an unsized node, pass `size=[w,h,l]`.
  Position is the minimum corner of the rotated footprint. Rotations are
  0, 90, 180, 270; 90/270 swap width and length. Faces rotate south, west,
  north, east. Existing `transform(pos, rotation, size, child)` is also available.
- Structural writes may overlap only when blocks are identical. Carves run
  after all structure, then fixtures run into empty/carved cells. Moving a
  carve earlier in the source does not change this ordering.
- Doors/windows carve their own holes. Furniture belongs above floors.
- Untouched cells preserve terrain; explicitly carved air clears it on placement.
- Starlark supports functions, loops, and comprehensions; no while or recursion.
  Block states are strings. Use namespaced identifiers such as `minecraft:oak_planks`.

## Find details only when needed

Call `get_starlark_docs(component="GableRoof")` for an import, exact signature,
size, orientation, and constraints. Or select a topic:
`dsl`, `composition`, `errors`, `components`, `structural`, `openings`, `roofs`,
`fixtures`, `outdoor`, `dwellings`, `fortifications`, `dungeons`, `redstone`,
`random`, or `full`. `quickstart` returns this guide.

On failure, fix the first distinct error using its component path, bounds,
and coordinate samples, then compile again. A successful compile followed by
a failed placement retains its artifact ID; use `place_starlark_structure`
to retry placement without resubmitting source.
