# Repository Guidelines

## Purpose and Project Layout

This project turns declarative Starlark components into deterministic, sparse
Minecraft Java 1.21.7 structure NBT files. The pipeline is Rust in `crates/`;
`src/starlark_to_nbt/` is the Python API over it (built with maturin as one
package); Starlark code lives in `examples/` and `lib/`.

The pipeline is deliberately staged in `crates/stnbt-core/src/`, with
`pipeline.rs` orchestrating:

1. `eval/` evaluates `.star` files on starlark-rust, resolves `load()` calls,
   and provides the tree constructors (`eval/prelude.star`), block-entity
   helpers (`eval/helpers.star`), and math builtins (`eval/natives.rs`), all
   of which return JSON-compatible tagged data.
2. `schema.rs` validates that data into the IR in `ir.rs`. Validation must
   finish before spatial layout begins.
3. `layout.rs` assigns half-open `model::Region` boxes to components.
4. `lowering.rs` produces phased block operations and applies transforms,
   including rotation of directional block states.
5. `execute.rs` applies `STRUCTURE`, `CARVE`, then `FIXTURE` operations to a
   sparse volume and enforces overlap rules and assembly atomicity.
   `support.rs` then validates the finished volume: redstone attachables
   (dust, repeaters, comparators, torches, levers, buttons, pressure plates)
   must have a solid block on their attachment side or the build fails with
   `unsupported_block`. `validators.rs` runs validators components declare.
6. `serialize.rs` writes sparse structure NBT (`nbt.rs`), including per-block
   block-entity NBT, plus the meta sidecar and debug JSON (`json.rs`).
   Untouched cells are omitted; deliberately carved cells remain explicit air.

Shared geometry, block, transform, and diagnostic types live in `model.rs`.
`crates/stnbt-py` is the PyO3 binding (`starlark_to_nbt._core`) and
`crates/stnbt-cli` the native binary. In Python, `pipeline.py` holds the
public API (`build_file`, `build_source`, `evaluate_source`,
`write_build_outputs`, `BuildResult`) and `cli.py` the `starlark-to-nbt` entry
point.

The reusable component library is grouped in `lib/*.star`; its prompt-ready DSL
and component reference is `docs/component-catalog.md`. `lib/showcase.star`
builds individual components for testing. `examples/church.star` is the full
pipeline vertical slice, `examples/cottage.star` demonstrates `load()`-based
composition, and `examples/keep.star` is the large stress build. The remaining
files in `examples/` are representative composed builds and procedural cases.

## Development Commands

Use `uv` for the environment and Python commands (`uv sync` and `uv run`
rebuild the Rust extension when crate sources change) and `cargo` for Rust:

```sh
uv sync --dev
uv run pytest
uv run pytest -m "not parity"          # skip the native-binary golden gate
uv run pytest tests/test_end_to_end.py::test_name
cargo test --workspace
cargo clippy --workspace --all-targets
uv run python -m py_compile src/starlark_to_nbt/*.py
./scripts/rebuild_examples.sh          # or rebuild_examples_native.sh
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

Rust follows rustfmt-style formatting and must stay clippy-clean; keep
`stnbt-core` free of Python and put conversion in `stnbt-py`. Python uses
four-space indentation, type annotations, and Python 3.13+ syntax, following
the existing PEP 8-style formatting, with frozen, slotted dataclasses for
result types. Use `snake_case` for modules, functions, and variables,
`PascalCase` for types and component types, and `UPPER_SNAKE_CASE` for
constants. Rust toolchain: 1.99.1 (`rust-toolchain.toml`).

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
  palette/block ordering, metadata JSON, and reproducible gzip bytes. The
  golden manifest (`tests/golden/manifest.json`, `scripts/golden.py`) pins
  output for every example, library component, and minecraft-mcp-api
  starlark-library script; regenerate it only for intentional changes.

Starlark library components conventionally draw from `[0, 0, 0]`, face `+Z` at
rotation zero, and declare a `min_size` matching what they actually draw.
Openings carve their own holes so they can be transformed onto existing walls.
Update `docs/component-catalog.md` whenever the public DSL or component library
changes.

## Testing Expectations

Rust unit tests sit beside each stage in `crates/stnbt-core/src/`
(validation messages, layout, rotation, lowering, execution, support,
validators, NBT/JSON formats, and the `load()` resolver). Python tests in
`tests/` describe behavior through the public API:

- `test_end_to_end.py`: decoded NBT, block-entity data, metadata sidecars, and
  reference-build assertions
- `test_library.py`: every library component standalone and under rotation
- `test_runtime_load.py`, `test_build_source.py`: `load()` resolution, loader
  roots and mounts, and diagnostics
- `test_api.py`: the Python API contract minecraft-mcp-api relies on
- `test_golden.py`, `test_native_cli.py`: byte-for-byte output for the whole
  corpus, through the API and through the native binary

Add the narrowest regression test that demonstrates a change. Pipeline,
execution, or serialization changes should also include an end-to-end assertion
against decoded NBT. Run the focused test while iterating, then the full suite
before handing off, plus `cargo test --workspace` and clippy for Rust changes.
If Python imports or annotations changed, also run `py_compile`.

## Commits and Pull Requests

Keep commits small and use a concise, imperative, lowercase subject describing
one logical change. Do not mix generated artifacts or unrelated cleanup into a
feature commit.

Pull requests should explain the behavior change and affected pipeline stages,
list the tests run, and link relevant issues. Include representative CLI output
or debug artifacts when serialization or generated geometry changes; screenshots
are useful only when the in-game appearance materially changes.
