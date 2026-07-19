# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Declarative Minecraft Java structure generation: Starlark scripts describe components, and the tool emits a Minecraft 1.21.7 structure NBT file. Python 3.13+, managed with `uv`. See also `AGENTS.md` for repository guidelines.

## Commands

```sh
uv sync --dev                          # Install runtime and test dependencies
uv run pytest                          # Run the full test suite
uv run pytest -q tests/test_end_to_end.py            # Run one test file
uv run pytest tests/test_end_to_end.py::test_name    # Run a single test

# Build the reference example (writes church.nbt plus debug JSON stages)
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church
```

No linter or formatter is configured; follow existing PEP 8-style formatting. Run `python -m py_compile src/starlark_to_nbt/*.py` when changing imports or types.

## Architecture

The code is a strictly staged pipeline in `src/starlark_to_nbt/`, orchestrated by `pipeline.build_file()` (called by `cli.py`). Each stage's output type is the next stage's input:

1. **Evaluate** (`starlark_runtime.py`): runs the `.star` file's entry function (default `build`) with `--arg` props (int/float/bool/str coerced). Host constructors (`component`, `split`, `inset`, `repeat`, `transform`, `place_block`, `fill_region`, `carve_region`, `place_assembly`, …) return JSON-compatible tagged dicts (`{"kind": ...}`), never IR objects. `load()` statements are supported via a `FileLoader` (`_Loader`): paths resolve relative to the loading file, with caching, cycle detection (`load_cycle`), and missing-file (`load_error`) diagnostics. The entry function is invoked through a trampoline expression, not `FrozenModule.call`, so prop names like `name` can't collide with `call()` parameters.
2. **Validate** (`schema.py`): `parse_node` converts tagged dicts into the frozen, slotted IR dataclasses in `ir.py` (the `Node` union). All validation happens here, before layout.
3. **Layout** (`layout.py`): `resolve` assigns each node a half-open `Box` region, producing a `ResolvedNode` tree. Layout combinators (`Split` with fixed/fill sizes, `Inset`, `Repeat`, `TransformNode`) fail loudly on overflow/underflow — geometry is never silently clamped.
4. **Lowering** (`lowering.py`): flattens the resolved tree into `BlockOperation`s with world-space `BlockWrite`s, applying accumulated transforms. Quarter-turn Y rotations also rotate block states: `facing`, `axis` (x↔z), sign `rotation` (0–15), and multi-face connection keys (`north`/`south`/`east`/`west` on fences, panes, walls). Relative states (`shape`, `hinge`, `half`) are correctly left alone.
5. **Execute** (`execute.py`): applies operations to a `SparseVolume` in phase order — `STRUCTURE`, then `CARVE`, then `FIXTURE`. In STRUCTURE, rewriting a cell with the *identical* block is allowed (fills may share corners); differing blocks raise `block_conflict`. FIXTURE is strict: any solid overlap errors. CARVE overwrites with air. Assemblies (e.g. doors, beds) are placed atomically as one operation. `fill_region` accepts `phase="fixture"` for things like carpets.
6. **Serialize** (`serialize.py`): writes **sparse** structure NBT — only written voxels are listed, so untouched cells preserve terrain on paste and file size scales with content, not bounding volume; carved-but-unfilled cells stay as explicit `minecraft:air`. Blocks may carry block-entity data (`BlockSpec.block_nbt`, e.g. sign text via the `sign_nbt()` builtin), emitted as a per-instance `nbt` compound — never in the palette, which stays keyed on type+state. Gzip uses `mtime=0` so identical builds are byte-for-byte deterministic. With `--debug-dir`, per-stage JSON (`component-ir.json`, `resolved.json`, `operations.json`, `dense.json` — the debug JSON is still dense by design).

Shared geometry/error types live in `model.py`: `Point`, `Box` (half-open, positive extents enforced), `Transform`, `BlockSpec`, and the `Diagnostic`/`BuildError` machinery. Every operation carries `Provenance` (component path + assigned region) so errors are component-aware.

Coordinates: `+X` east, `+Y` up, `+Z` south. Boxes are half-open (`min` inclusive, `max` exclusive).

## Conventions and invariants

- Keep pipeline boundaries explicit: Starlark constructors return tagged dicts; validation precedes layout; components must not write outside their assigned half-open boxes.
- Prefer immutable, slotted dataclasses (`frozen=True, slots=True`) for IR and geometry values.
- Errors are raised as `BuildError` wrapping `Diagnostic`s with a stable `code`, component path, and coordinates/region — extend this pattern rather than raising bare exceptions.
- Generated output must remain deterministic.
- Known limitation: build-rule diagnostics carry component paths but not Starlark line numbers — starlark-pyo3 doesn't expose the call stack to host callbacks (`SourceRef.line` is only populated for parse/eval errors, which include file:line in their message).

## Component library

`lib/*.star` is a reusable component library (structural, openings, roofs, fixtures, outdoor) meant to be composed by LLM-generated scripts via `load()`; `docs/component-catalog.md` is the prompt-ready reference for it. Conventions: components draw from `[0,0,0]`, declare `min_size` equal to what they actually draw (this is the natural size used when built standalone with no size props), face +Z (south) at rotation 0, and walls run along +X one block thick. Openings (doors/windows/arches) carve their own hole so they can be transformed onto an existing wall. `lib/showcase.star` builds any single component by name (`--arg name=GableRoof`, entries `build`/`rotated`) and drives the parametrized stress tests.

## Testing

Tests in `tests/` mirror behavior, not modules: `test_schema_layout.py` (validation and spatial invariants), `test_transform_execution.py` (transforms, overlap policy, phase conflicts, assembly atomicity), `test_rotation_states.py` (block-state rotation), `test_runtime_load.py` (load resolution/cycle/missing diagnostics), `test_library.py` (every library component standalone and at all four rotations, driven by `COMPONENT_NAMES` in `lib/showcase.star`), `test_end_to_end.py` (decoded-NBT assertions for church, cottage, keep). Any pipeline change should include an end-to-end assertion against decoded NBT.

`examples/church.star` is the reference vertical slice exercising every node kind; `examples/cottage.star` is the reference `load()` composition; `examples/keep.star` is the large stress build.
