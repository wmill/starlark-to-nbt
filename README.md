Declarative Minecraft Java structure generation with Starlark components.

The MVP evaluates Starlark into a validated component IR, resolves spatial layout,
lowers components into phased block operations, executes them into a sparse voxel
map, and writes a Minecraft 1.21.7 structure NBT file.

```sh
uv sync --dev
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church
```

Coordinates use `+X` east, `+Y` up, and `+Z` south. Boxes are half-open. The
executor runs `STRUCTURE`, `CARVE`, then `FIXTURE` operations; accidental solid
overlaps fail with component-aware diagnostics, and assemblies such as doors are
placed atomically.

Run the test suite with `uv run pytest`.
