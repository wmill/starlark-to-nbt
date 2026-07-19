# Repository Guidelines

## Purpose and Project Layout

This project turns declarative Starlark components into deterministic, sparse
Minecraft Java 1.21.7 structure NBT files. Python source lives in
`src/starlark_to_nbt/`; Starlark code lives in `examples/` and `lib/`.

The pipeline is deliberately staged, with `pipeline.py` orchestrating:

1. `starlark_runtime.py` evaluates `.star` files, resolves `load()` calls, and
   exposes host constructors that return JSON-compatible tagged dictionaries.
2. `schema.py` validates those dictionaries and creates the immutable IR types
   in `ir.py`. Validation must finish before spatial layout begins.
3. `layout.py` assigns half-open `model.Box` regions to components.
4. `lowering.py` produces phased block operations and applies transforms,
   including rotation of directional block states.
5. `execute.py` applies `STRUCTURE`, `CARVE`, then `FIXTURE` operations to a
   sparse volume and enforces overlap rules and assembly atomicity.
6. `serialize.py` writes debug JSON and sparse structure NBT, including
   per-block block-entity NBT. Untouched cells are omitted; deliberately carved
   cells remain explicit air.

Shared geometry, block, transform, and diagnostic types live in `model.py`.
The CLI entry point is `cli.py` (`starlark-to-nbt`).

The reusable component library is grouped in `lib/*.star`; its prompt-ready DSL
and component reference is `docs/component-catalog.md`. `lib/showcase.star`
builds individual components for testing. `examples/church.star` is the full
pipeline vertical slice, `examples/cottage.star` demonstrates `load()`-based
composition, `examples/keep.star` is the large stress build, and
`examples/mega_castle.star` is the 48x40x48 entity-enabled showcase. The remaining
files in `examples/` are representative composed builds and procedural cases.

## Development Commands

Use `uv` for the environment and all Python commands:

```sh
uv sync --dev
uv run pytest
uv run pytest -q tests/test_end_to_end.py
uv run pytest tests/test_end_to_end.py::test_name
uv run python -m py_compile src/starlark_to_nbt/*.py
./scripts/rebuild_examples.sh
```

Build the reference example with inspectable intermediate output:

```sh
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church
```

Building an NBT file also writes a sibling `.meta.json` placement sidecar.
Generated `.nbt`, `.meta.json`, and `build/` artifacts are development output;
do not commit them unless a task explicitly calls for fixtures or examples.

## Coding Conventions and Invariants

Use four-space indentation, type annotations, and Python 3.13+ syntax. Follow
the existing PEP 8-style formatting; no formatter or linter is configured.
Prefer frozen, slotted dataclasses for IR and geometry values. Use
`snake_case` for modules, functions, and variables, `PascalCase` for classes and
component types, and `UPPER_SNAKE_CASE` for constants.

Preserve these boundaries and invariants:

- Starlark host constructors return tagged, JSON-compatible data—not Python IR
  objects. Parse and validate it before layout.
- Coordinates use `+X` east, `+Y` up, and `+Z` south. Boxes are half-open: the
  minimum is inclusive and the maximum is exclusive.
- Never silently clamp geometry or allow a component to write outside its
  assigned box. Invalid allocations must produce a diagnostic.
- Extend the existing `BuildError`/`Diagnostic` pattern with stable error codes,
  provenance, and useful regions or coordinates instead of raising bare errors.
- Preserve execution semantics: identical structural rewrites are allowed,
  conflicting solid writes fail, fixture overlap is strict, and multi-block
  assemblies are atomic.
- When adding transforms, account for both coordinates and affected block-state
  properties (`facing`, `axis`, numeric `rotation`, and horizontal face keys).
- Treat block-entity NBT as per-block instance data, not palette data. Preserve
  it unchanged through transforms and serialize it on the block entry. Use the
  Starlark `sign_nbt`, `container_nbt`, and `loot_nbt` helpers rather than
  duplicating raw block-entity shapes in library components.
- Entity positions are integer ground-cell anchors serialized at centered X/Z
  coordinates. Rotate anchors and yaw together, keep placements within both
  component and root regions, and reserve `id`, `Pos`, `Rotation`, and `UUID`
  for deterministic structure serialization. Entities do not collide with blocks.
- Root-only build metadata is typed and validated before layout. Keep
  `ground_level` non-negative and preserve the derived `y_offset` in the
  deterministic `.meta.json` sidecar; do not add custom placement tags to the
  standard structure NBT.
- Output must be deterministic. Serialization changes should preserve stable
  palette/block ordering, metadata JSON, and reproducible gzip bytes.

Starlark library components conventionally draw from `[0, 0, 0]`, face `+Z` at
rotation zero, and declare a `min_size` matching what they actually draw.
Openings carve their own holes so they can be transformed onto existing walls.
Update `docs/component-catalog.md` whenever the public DSL or component library
changes.

## Testing Expectations

Tests describe behavior rather than mirroring every source module:

- `test_schema_layout.py`: validation and spatial invariants
- `test_transform_execution.py`: transforms, phases, conflicts, and assemblies
- `test_rotation_states.py`: directional block-state rotation
- `test_runtime_load.py`: `load()` resolution, caching, cycles, and diagnostics
- `test_library.py`: every library component standalone and under rotation
- `test_end_to_end.py`: decoded NBT, block-entity data, metadata sidecars, and
  reference-build assertions

Add the narrowest regression test that demonstrates a change. Pipeline,
execution, or serialization changes should also include an end-to-end assertion
against decoded NBT. Run the focused test while iterating, then the full suite
before handing off. If imports or annotations changed, also run `py_compile`.

## Commits and Pull Requests

Keep commits small and use a concise, imperative, lowercase subject describing
one logical change. Do not mix generated artifacts or unrelated cleanup into a
feature commit.

Pull requests should explain the behavior change and affected pipeline stages,
list the tests run, and link relevant issues. Include representative CLI output
or debug artifacts when serialization or generated geometry changes; screenshots
are useful only when the in-game appearance materially changes.
