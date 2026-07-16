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

1. **Evaluate** (`starlark_runtime.py`): runs the `.star` file's entry function (default `build`) with `--arg` props. Host constructors (`component`, `split`, `inset`, `repeat`, `transform`, `place_block`, `fill_region`, `carve_region`, `place_assembly`, …) return JSON-compatible tagged dicts (`{"kind": ...}`), never IR objects.
2. **Validate** (`schema.py`): `parse_node` converts tagged dicts into the frozen, slotted IR dataclasses in `ir.py` (the `Node` union). All validation happens here, before layout.
3. **Layout** (`layout.py`): `resolve` assigns each node a half-open `Box` region, producing a `ResolvedNode` tree. Layout combinators (`Split` with fixed/fill sizes, `Inset`, `Repeat`, `TransformNode`) fail loudly on overflow/underflow — geometry is never silently clamped.
4. **Lowering** (`lowering.py`): flattens the resolved tree into `BlockOperation`s with world-space `BlockWrite`s, applying accumulated transforms (translation + quarter-turn Y rotations that also rotate `facing` block states).
5. **Execute** (`execute.py`): applies operations to a `SparseVolume` in phase order — `STRUCTURE`, then `CARVE`, then `FIXTURE`. Solid overlaps in STRUCTURE/FIXTURE phases raise `BuildError`; CARVE overwrites. Assemblies (e.g. doors) are placed atomically as one operation.
6. **Serialize** (`serialize.py`): writes the structure NBT (gzip with `mtime=0` so identical builds are byte-for-byte deterministic) and, with `--debug-dir`, per-stage JSON (`component-ir.json`, `resolved.json`, `operations.json`, `dense.json`).

Shared geometry/error types live in `model.py`: `Point`, `Box` (half-open, positive extents enforced), `Transform`, `BlockSpec`, and the `Diagnostic`/`BuildError` machinery. Every operation carries `Provenance` (component path + assigned region) so errors are component-aware.

Coordinates: `+X` east, `+Y` up, `+Z` south. Boxes are half-open (`min` inclusive, `max` exclusive).

## Conventions and invariants

- Keep pipeline boundaries explicit: Starlark constructors return tagged dicts; validation precedes layout; components must not write outside their assigned half-open boxes.
- Prefer immutable, slotted dataclasses (`frozen=True, slots=True`) for IR and geometry values.
- Errors are raised as `BuildError` wrapping `Diagnostic`s with a stable `code`, component path, and coordinates/region — extend this pattern rather than raising bare exceptions.
- Generated output must remain deterministic.

## Testing

Tests in `tests/` mirror behavior, not modules: `test_schema_layout.py` (validation and spatial invariants), `test_transform_execution.py` (transforms, phase conflicts, assembly atomicity), `test_end_to_end.py` (decoded-NBT assertions). Any pipeline change should include an end-to-end assertion against decoded NBT.

`examples/church.star` is the reference vertical slice exercising every node kind.
