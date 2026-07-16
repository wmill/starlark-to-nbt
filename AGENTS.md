# Repository Guidelines

## Project Structure & Module Organization

Python source lives in `src/starlark_to_nbt/`. The pipeline is intentionally staged:

- `starlark_runtime.py` evaluates `.star` files (with `load()` support) and exposes host constructors.
- `schema.py`, `ir.py`, and `model.py` validate and represent component data.
- `layout.py` resolves spatial allocations; `lowering.py` creates block operations and rotates block states (`facing`, `axis`, `rotation`, multi-face keys).
- `execute.py` applies phased operations to a sparse volume (identical structural rewrites allowed; conflicting solids error; fixtures strict).
- `serialize.py` writes debug JSON and sparse Minecraft structure NBT (untouched cells omitted).
- `pipeline.py` and `cli.py` provide the public orchestration interfaces.

The reusable component library lives in `lib/*.star` (documented for LLM prompting in `docs/component-catalog.md`); `lib/showcase.star` builds any single component by name. Starlark examples belong in `examples/`; `examples/church.star` is the reference vertical slice, `examples/cottage.star` the reference `load()` composition, and `examples/keep.star` the large stress build. Tests live in `tests/` and mirror behavior rather than individual modules.

## Build, Test, and Development Commands

Use `uv` for dependency and environment management:

```sh
uv sync --dev                 # Install runtime and test dependencies
uv run pytest                 # Run the complete test suite
uv run pytest -q tests/test_end_to_end.py
uv run starlark-to-nbt build examples/church.star \
  --arg width=11 --arg length=19 --arg height=4 \
  --output church.nbt --debug-dir build/church
```

The final command generates a Minecraft 1.21.7 NBT structure plus inspectable intermediate JSON files.

## Coding Style & Naming Conventions

Use four-space indentation, type annotations, and Python 3.13+ syntax. Prefer immutable, slotted dataclasses for IR and geometry values. Name modules, functions, and variables with `snake_case`; classes and component types use `PascalCase`; constants use `UPPER_SNAKE_CASE`.

Keep pipeline boundaries explicit. Starlark constructors must return JSON-compatible tagged dictionaries, and validation must occur before layout. Do not silently clamp geometry or permit components to write outside assigned half-open boxes. No formatter or linter is currently configured; follow existing PEP 8-style formatting and run `python -m py_compile src/starlark_to_nbt/*.py` when changing imports or types.

## Testing Guidelines

Tests use `pytest` and follow `test_<behavior>.py` / `test_<scenario>()` naming. Add focused tests for schema errors, spatial invariants, transforms, phase conflicts, and assembly atomicity. Any pipeline change should include an end-to-end assertion against decoded NBT. Generated output must remain deterministic.

## Commit & Pull Request Guidelines

History uses brief, lowercase summaries such as `basic test` and `brief description`. Keep commits small and use a concise imperative subject describing one logical change.

Pull requests should explain the behavior changed, identify affected pipeline stages, and include test results. Link relevant issues and include example CLI output or debug artifacts when serialization or generated geometry changes; screenshots are only useful for in-game visual differences.
