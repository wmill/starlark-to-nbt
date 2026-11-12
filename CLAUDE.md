# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Declarative Minecraft Java structure generation: Starlark scripts describe components, and the tool emits a Minecraft 1.21.7 structure NBT file. The pipeline is Rust (a Cargo workspace in `crates/`), packaged as a Python distribution via maturin (`starlark_to_nbt`, Python 3.13+, managed with `uv`) and as a native binary. See also `AGENTS.md` for repository guidelines, and `docs/rust-core-plan.md` for the history of the Python → Rust port.

## Commands

```sh
uv sync --dev                          # Install; builds the Rust extension (rebuilt automatically on uv run after Rust edits)
uv run pytest                          # Full Python suite (end-to-end, library, golden manifest, native CLI)
uv run pytest -m "not parity"          # Skip the slower native-binary golden gate
uv run pytest tests/test_end_to_end.py::test_name    # A single test
cargo test --workspace                 # Rust unit tests (schema, layout, lowering, execute, support, validators, eval, serialize)
cargo clippy --workspace --all-targets # Lint (keep it warning-free)
cargo run --release -p stnbt-cli -- build examples/church.star --output church.nbt   # Native binary
scripts/rebuild_examples.sh            # Rebuild every example via the Python entry point
scripts/rebuild_examples_native.sh     # ... or via the native binary
uv run python scripts/golden.py --check  # Output parity vs tests/golden/manifest.json (also run by pytest)

# Build the reference example (writes church.nbt, church.meta.json, plus debug JSON stages)
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church
```

Rust is pinned to 1.99.1 (`.tool-versions` for asdf, `rust-toolchain.toml` for rustup). No Python formatter is configured; follow PEP 8-style formatting. Run `python -m py_compile src/starlark_to_nbt/*.py` when changing Python imports.

## Layout

- `crates/stnbt-core` — the whole pipeline (pure Rust, no Python).
- `crates/stnbt-py` — thin PyO3 bindings, built as `starlark_to_nbt._core`. `build.rs` bakes a fingerprint of all Rust sources (prelude included) into `_core.build_fingerprint()`.
- `crates/stnbt-cli` — the native `starlark-to-nbt` binary (same flags, output, and exit codes as `src/starlark_to_nbt/cli.py`).
- `src/starlark_to_nbt/` — the Python API: `pipeline.py` (`build_file`, `build_source`, `evaluate_source`, `write_build_outputs`, `BuildResult`), `model.py`/`ir.py` (result and diagnostic types), `serialize.py` (`write_structure_nbt`), `cli.py`.

## Architecture

A strictly staged pipeline in `crates/stnbt-core/src/`, orchestrated by `pipeline::build` (called by the Python API and the CLI). Each stage's output is the next stage's input:

1. **Evaluate** (`eval/`): runs the `.star` file's entry function (default `build`) with props as keyword arguments, on starlark-rust with the Standard dialect and globals (no f-strings, type annotations, or top-level `if`/`for`). Tree constructors (`component`, `split`, `inset`, `repeat`, `transform`/`at`, `place_block`, `fill_region`, `carve_region`, `place_assembly`, `entity`/`place_entity`, …) are Starlark in `eval/prelude.star`, and the block-entity helpers (`sign_nbt`, `container_nbt`, `loot_nbt`) are in `eval/helpers.star`. Both are frozen once and imported into every module; they return JSON-compatible tagged dicts (`{"kind": ...}`), never IR. Math builtins are natives (`eval/natives.rs`: `isqrt`, `round`/`floor`/`ceil` returning ints, `sqrt`/`sin`/`cos`/`atan2`, `PI`). `load()` resolves relative to the loading file, with caching, cycle detection (`load_cycle`), and missing-file (`load_error`) diagnostics. With a `loader_root`, loads are confined to its `lib/` dir; `mounts` (e.g. `{"library": path}`) map extra top-level names to outside directories, confined to them, and modules loaded from a mount resolve their own loads from `base_dir`. The result converts to `val::Val`.
2. **Validate** (`schema.rs`): `parse_node` turns the `Val` tree into the `ir::Node` tree. All validation happens here, before layout; errors carry a JSON path (`$.body.children[3]`).
3. **Layout** (`layout.rs`): `resolve` assigns each node a half-open `Region` and a component path. Combinators (`Split` fixed/fill sizes, `Inset`, `Repeat`, `Transform`) fail loudly on overflow/underflow; geometry is never silently clamped. Root size comes from `width`/`height`/`length` props (each at least `min_size`), else `min_size` (`pipeline::root_size`).
4. **Lowering** (`lowering.rs`): flattens the resolved tree into `BlockOperation`s with world-space writes, applying accumulated transforms. Quarter-turn Y rotations also rotate block states: `facing`, `axis` (x↔z), sign `rotation` (0–15), and multi-face connection keys (`north`/`south`/`east`/`west`); relative states (`shape`, `hinge`, `half`) are left alone. Blocks are interned (`blocks.rs`: `BlockId`, air is id 0, identity is type + sorted state + nbt).
5. **Execute** (`execute.rs`): applies operations to a `SparseVolume` in phase order — STRUCTURE, CARVE, FIXTURE. In STRUCTURE, rewriting a cell with the identical block is allowed (fills share corners); differing blocks raise `block_conflict`. FIXTURE is strict: any non-air overlap errors. CARVE overwrites with air. Each operation is validated in full before any write applies, so assemblies (doors, beds) are atomic, and all of an operation's errors are reported together.
6. **Checks** (`support.rs`, `validators.rs`): redstone attachables (dust, repeaters, comparators, torches, levers, buttons, pressure plates) need a solid block on their attachment side or the build fails with `unsupported_block`. Unwritten support cells outside the root box, or below `metadata.ground_level`, count as terrain; unwritten cells inside the box at or above ground level count as air. Solidity is a conservative denylist; pressure plates may sit on fences, walls, and hoppers. Components can declare `validator("door_supported_on_both_sides", assembly=...)`. Support and validator diagnostics are collected into one error.
7. **Serialize** (`serialize.rs`, `nbt.rs`, `json.rs`): writes **sparse** structure NBT — only written voxels are listed, so untouched cells preserve terrain on paste; carved-but-unfilled cells stay explicit `minecraft:air`. Block-entity nbt rides on the block entry, never the palette (keyed on type + state). Gzip level 6 with mtime 0, so identical builds are byte-for-byte identical. Every build also writes `<stem>.meta.json` (`ground_level`, `y_offset`). `--debug-dir` writes `component-ir.json`, `resolved.json`, `operations.json`, `entities.json`, and `dense.json` (dense by design).

Shared types live in `model.rs`: `Point`, `Region` (half-open, positive extents enforced; Python's `Box`), `Transform`, `BlockSpec`, `Diagnostic`/`BuildError`, `Provenance`. Every operation carries provenance (component path + assigned region), so errors are component-aware. In Python, `BuildResult.volume.voxels`/`.operations`/`.entities` materialize lazily from compact tables; `block_at` and the writers stay in Rust.

Coordinates: `+X` east, `+Y` up, `+Z` south. Boxes are half-open (`min` inclusive, `max` exclusive).

## Conventions and invariants

- Keep pipeline boundaries explicit: Starlark constructors return tagged dicts; validation precedes layout; components must not write outside their assigned half-open boxes.
- Errors are `BuildError`s wrapping `Diagnostic`s with a stable `code`, component path, and coordinates/region/details. Extend this pattern rather than panicking or returning bare strings; diagnostics are LLM feedback, so codes and paths must stay stable.
- Generated output must remain deterministic (`tests/golden/manifest.json` pins it; regenerate only for an intentional output change, with `uv run python scripts/golden.py`).
- What must keep working: `examples/*.star` and minecraft-mcp-api's `starlark-library` scripts (the golden corpus covers both), plus the API its `starlark_service/runner.py` uses (`build_source` with loader options, `BuildResult.volume.bounds`/`.voxels`/`.entities`, `.metadata`, `serialize.write_structure_nbt`, `BuildError`/`Diagnostic`/`Point`, `build_fingerprint()` for its cache key).
- Known limitation: build-rule diagnostics carry component paths but not Starlark line numbers (`SourceRef.line` is only set for parse/eval errors, whose message includes the traceback).

## Component library

`lib/*.star` is a reusable component library (structural, openings, roofs, fixtures, outdoor, dwellings, fortifications, dungeons, redstone, `shapes.star` for watertight r+0.5-rounded discs/cylinders/domes/spheres, plus `random.star` for deterministic pseudo-random scattering) meant to be composed by LLM-generated scripts via `load()`; `docs/component-catalog.md` is the prompt-ready reference for it. Conventions: components draw from `[0,0,0]`, declare `min_size` equal to what they actually draw (this is the natural size used when built standalone with no size props), face +Z (south) at rotation 0, and walls run along +X one block thick. Openings (doors/windows/arches) carve their own hole so they can be transformed onto an existing wall. `lib/showcase.star` builds any single component by name (`--arg name=GableRoof`, entries `build`/`rotated`) and drives the parametrized stress tests; every public `def UpperCamel(...)` in `lib/*.star` must be listed in its `COMPONENT_NAMES` (a test enforces this).

Redstone specifics (`lib/redstone.star`): signal flows +Z; gates/circuits carry their own base slab at y=0 with logic at y=1; bare attachable parts (RedstoneWire, Repeater, Comparator, torches, Lever, Button, pressure plates) default to `base=None` and must land on existing solid blocks, or take `base="minecraft:..."` to bring their own supporting block (part moves to y=1, `min_size` `[1,2,1]`).

## Testing

Rust unit tests sit beside each stage (`cargo test --workspace`): schema messages and check order, layout allocation, rotation tables, lowering, execute overlap/atomicity, support rules, door validators, NBT/JSON byte formats, and the eval loader (relative loads, cycles, confinement, mounts) and builtins.

Python tests in `tests/` are behavioral, through the public API: `test_end_to_end.py` (decoded-NBT assertions for church, cottage, keep, redstone_showcase, and other examples), `test_library.py` (every library component standalone and at all four rotations, driven by `COMPONENT_NAMES`), `test_runtime_load.py` and `test_build_source.py` (`load()` resolution, loader roots and mounts), `test_shapes.py`, `test_entities.py`, `test_dungeons.py`, `test_at.py`, `test_validators.py`, `test_api.py` (the runner.py contract, determinism, fingerprint), `test_golden.py` (byte-for-byte output for the whole corpus, including the starlark-library scripts when `../../minecraft-mcp-api/starlark-library` exists or `STARLARK_LIBRARY_DIR` points to it), and `test_native_cli.py` (the binary against the golden manifest and `cli.py`). Any pipeline change should include an end-to-end assertion against decoded NBT.

`examples/church.star` is the reference vertical slice exercising every node kind; `examples/cottage.star` is the reference `load()` composition; `examples/keep.star` is the large stress build; `examples/redstone_showcase.star` is the interactive redstone gallery; the `examples/procedural_*.star` files exercise loop/parametric generation. For performance work, `scripts/dump_tree.py` plus `cargo run --release -p stnbt-core --example bench_stages` time each stage.
