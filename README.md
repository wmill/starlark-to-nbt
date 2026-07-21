Declarative Minecraft Java structure generation with Starlark components.

The MVP evaluates Starlark into a validated component IR, resolves spatial layout,
lowers components into phased block operations, executes them into a sparse voxel
map, and writes a Minecraft 1.21.7 structure NBT file.

```sh
uv sync --dev
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church

# Compose from the component library (lib/*.star) via load():
uv run starlark-to-nbt build examples/cottage.star --output cottage.nbt
uv run starlark-to-nbt build examples/keep.star --output keep.nbt
uv run starlark-to-nbt build examples/riverside_farmstead.star --output riverside_farmstead.nbt
uv run starlark-to-nbt build examples/market_square.star --output market_square.nbt
uv run starlark-to-nbt build examples/frontier_outpost.star --output frontier_outpost.nbt
uv run starlark-to-nbt build examples/stone_pass_fortress.star --output stone_pass_fortress.nbt
uv run starlark-to-nbt build examples/medieval_manor.star --output medieval_manor.nbt
uv run starlark-to-nbt build examples/mega_castle.star --output mega_castle.nbt

# Rebuild every example into build/<example-name>.nbt:
./scripts/rebuild_examples.sh

# Build a single library component by name:
uv run starlark-to-nbt build lib/showcase.star --arg name=GableRoof --output roof.nbt
```

Coordinates use `+X` east, `+Y` up, and `+Z` south. Boxes are half-open. The
executor runs `STRUCTURE`, `CARVE`, then `FIXTURE` operations; identical
structural rewrites are permitted, conflicting solid overlaps fail with
component-aware diagnostics, and assemblies such as doors are placed
atomically. Output NBT is sparse: untouched cells are omitted so pasting
preserves terrain.

`docs/component-catalog.md` documents the DSL and every library component in a
form suitable for LLM prompting.

Run the test suite with `uv run pytest`.
