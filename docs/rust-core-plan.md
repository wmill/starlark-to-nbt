# Rust core rewrite — starlark-to-nbt

> **Resuming this work?** Read "Status" first, then the current phase. Each phase
> ends green (all tests pass, parity holds) and is committed, so the last
> committed phase is the restart point. Branch: `feature/rust-core`.
> This file (`docs/rust-core-plan.md`) is the canonical copy — keep it updated.

## Status

- [x] Prelude change (commit `574f8d3`): tree constructors now live in
      `src/starlark_to_nbt/prelude.star`, which removed most of starlark-pyo3's
      per-call JSON marshalling. Slowest example went 3.83s → 1.96s.
- [x] Phase 0 — workspace scaffolding + golden parity manifest
- [x] Phase 1 — core types, diagnostics, schema (Val → IR)
- [ ] Phase 2 — layout + lowering
- [ ] Phase 3 — execute + support + validators
- [ ] Phase 4 — serialization (NBT, gzip, meta/debug JSON)
- [ ] Phase 5 — Python integration behind an engine switch, then flip the default
- [ ] Phase 6 — Starlark eval in Rust (starlark-rust) + native CLI
- [ ] Phase 7 — retire the Python internals, port unit tests, update docs

Update this checklist and the "Notes / deviations" log at the end of each phase.

## Context

Builds are slow. The slowest example, `examples/moonspire_magical_city.star`
(~57k voxels), took 3.8s. Profiling found that starlark-pyo3 JSON-encodes the
args and result of every Python host call (2.5M `json.loads` per build). The
prelude change took about half of that out. What remains is plain Python
overhead, roughly:

| Stage | Time |
|---|---|
| Starlark eval | ~0.6s |
| lowering | ~1.0s |
| nbtlib write | ~0.7s |
| `parse_node`, layout, execute | ~0.7s |

**Decided end state** (the user chose this): a Cargo workspace with a pure-Rust
core library and a native CLI binary, which minecraft-mcp-api can call directly,
plus a thin PyO3 shim so the existing Python package, `uv run starlark-to-nbt`,
and the Python tests keep working.

**Decided test strategy**: the Python end-to-end/library tests are the spec and
keep running against the Rust core through the shim. The parity gate is
byte-identical *decompressed* NBT against the current Python output. Internal
Python unit tests (the ones that build IR objects by hand) are ported to Rust
`#[test]`s only when their Python module is deleted (Phase 7).

Target: moonspire under 0.3s end to end. Every build must still be deterministic.

## Compatibility scope (user, 2026-11-11)

The only scripts this tool must run are `examples/*.star` and the saved
scripts in `../../minecraft-mcp-api/starlark-library/<name>/v<N>.star` (39
versions). Nobody else uses it. So:

- **The corpus is the gate.** `scripts/golden.py` builds all of it: examples,
  showcase components at all four rotations, and every library version with
  its saved entry/props/root_size, exactly as the service's `runner.py` does.
  Output must stay byte-identical (decompressed) unless a change is intentional.
- **Don't replicate Python quirks for inputs the corpus never produces.**
  Exact diagnostic *codes* and *paths* still matter, because they are LLM
  feedback. Matching message text is cheap during migration, so the parity
  tests keep checking it, but it's fine to improve messages deliberately later.
- **External API contract.** `minecraft-mcp-api/starlark-service/starlark_service/runner.py`
  vendors this repo as a git submodule and uses only these:
  - `pipeline.build_source(source, entry, props, root_size, base_dir, loader_root, mounts)`
  - `serialize.write_structure_nbt(result.volume, path)`
  - `result.volume.bounds.size`, `result.volume.voxels.values()` → `.block.block_type`,
    `result.volume.entities`, `result.metadata.ground_level` / `.y_offset`
  - `model.BuildError`, `model.Diagnostic` (fields), `model.Point`
  
  Keep that working through Phase 7, or change runner.py in the same breath.
  Everything else in the Python API is test-only, so tests can change with it.

## Architecture

```
Cargo.toml                      # [workspace] members = crates/*
crates/
  stnbt-core/                   # pure Rust, no pyo3
    src/model.rs                # Point, Box, Axis, Transform, BlockSpec, Diagnostic, BuildError
    src/val.rs                  # Val: Null|Bool|Int(i64)|Float|Str|List|Dict(IndexMap) — the tagged-dict tree
    src/ir.rs                   # Node enum + ResolvedNode, BlockOperation, EntityPlacement, ...
    src/schema.rs               # port of schema.py: &Val -> Node, identical paths/messages/codes
    src/layout.rs  lowering.rs  execute.rs  support.rs  validators.rs
    src/nbt.rs                  # hand-written NBT writer (tag enum, big-endian)
    src/serialize.rs            # sparse structure NBT + gzip + meta/debug JSON
    src/pipeline.rs             # finish_build(Val, props, root_size) -> BuildResult
    src/eval/                   # Phase 6: starlark-rust runtime, prelude, math natives, loader
      prelude.star              # moved from src/starlark_to_nbt/ in Phase 6 (include_str!)
  stnbt-cli/                    # clap binary `starlark-to-nbt`, same flags/output as cli.py
  stnbt-py/                     # pyo3 cdylib -> Python module `starlark_to_nbt._core`
```

Data flow after Phase 5: Python evaluates Starlark (starlark-pyo3), which returns
one Python dict tree. `_core.finish_build(tree, props, root_size)` converts it
to `Val` in a single pass, then runs schema → layout → … → NBT bytes in Rust.
After Phase 6, `_core.build_file(...)` does everything in Rust and no Python
values cross the boundary.

### Key design decisions

- **The `Val` tree is the boundary type.** `schema.rs` parses from `Val` and
  never from starlark or pyo3 values. That lets the Python shim (Python dict →
  `Val`) and the Rust eval (starlark `Value` → `Val`) share one validator, and
  keeps `$.body.children[3].block`-style paths identical.
- **Block interning.** `BlockSpec` gets interned into a `BlockTable`, and
  operations and voxels hold a `BlockId(u32)`. Rotation is cached per
  `(BlockId, rotation)`. Equality checks in `execute` become integer compares,
  and the palette falls out of the table. This is the main lowering/execute
  speedup: fills no longer allocate a `BlockSpec` per cell.
- **Volume.** Use `FxHashMap<Point, Voxel>` (`rustc-hash`). Leave dense storage
  for later, since root boxes can be large and sparse.
- **Coordinates** are `i32`. Ints in `Val` are `i64`, and `schema.rs` rejects
  anything outside i32 with `invalid_ir`. This is a deliberate narrowing,
  because Python accepted unbounded ints; record it in the deviations log.
- **Ordering = determinism.** Use `IndexMap` for dicts so Starlark insertion
  order survives. Match the Python output order exactly:
  - blocks are sorted by `(y, z, x)`
  - the palette is sorted with air first, then by `(type, sorted state)`
  - palette `Properties` keys are sorted
  - entities are sorted by sequence
  - entity NBT keys keep user order, then `id`, `Pos`, `Rotation` are appended
- **NBT typing rules** (port `serialize._to_nbt` exactly):
  - bool → Byte
  - int → Int (out of i32 range → `serialize_error`)
  - float → Double
  - str → String
  - dict → Compound
  - list → List typed by its first element; an empty list → `List[String]`
  - Strings are written as **standard UTF-8**, matching nbtlib (`value.encode("utf-8")`),
    not Java modified UTF-8. Keep parity for now and log modified UTF-8 as a
    follow-up.
- **Diagnostics.** The Rust `Diagnostic` mirrors model.py's fields. `details`
  is `IndexMap<String, Val>`. `Display` reproduces `Diagnostic.__str__`
  exactly, so CLI output and `pytest.raises(match=...)` keep working. The shim
  converts it to Python `model.Diagnostic`/`BuildError`. Those classes stay in
  Python as the public API.
- **Prelude stays Starlark.** In Phase 6 it's embedded with `include_str!`.
  Porting the constructors to native `#[starlark_module]` functions is an
  optional later step; measure first.

## Phases

Each phase lists the files to port, the Rust tests to add, and the gate it must pass.

### Phase 0 — Scaffolding + golden manifest
1. `rustup update` (current is rustc 1.85) and pin `rust-toolchain.toml` to
   whatever the chosen `starlark` crate's MSRV requires.
2. Create the workspace and the three crates. `stnbt-py` exposes
   `_core.version()` only.
3. Switch `pyproject.toml` build backend from hatchling to **maturin**:
   - `[tool.maturin] manifest-path = "crates/stnbt-py/Cargo.toml"`
   - `python-source = "src"`
   - `module-name = "starlark_to_nbt._core"`
   - `features = ["pyo3/extension-module"]`
   - Add `[tool.uv] cache-keys = [{file = "pyproject.toml"}, {file = "Cargo.toml"}, {file = "crates/**/*.rs"}, {file = "crates/**/Cargo.toml"}, {file = "crates/**/*.star"}]`
     so `uv sync`/`uv run` rebuild after Rust edits.
   - Check that `prelude.star` is still packaged.
4. **Golden manifest** (generated by the *current Python* implementation, then
   committed): add `scripts/golden.py`, which builds:
   - every `examples/*.star` with default args
   - church with the CLAUDE.md args
   - every `COMPONENT_NAMES` entry from `lib/showcase.star` at entries `build`/`rotated`
   
   It writes `tests/golden/manifest.json` mapping each case to the sha256 of
   its **decompressed** NBT payload, plus the meta JSON. `--check` mode
   compares instead of writing. Also record expected-failure cases (code + path)
   for a handful of known-bad inputs.
5. Gate: `uv sync --dev && uv run pytest` passes, `cargo test --workspace`
   passes, `python scripts/golden.py --check` passes.

### Phase 1 — Core types, diagnostics, schema
- Port `model.py` → `model.rs`. Keep the exact rotation math and these
  `Transform` methods: `apply_point`, `rotate_facing`, `rotate_axis`,
  `rotate_sixteenth`, and the connection-key rotation in `BlockSpec.transformed`.
  Also port `Box` half-open with positive extents enforced, and `fail()`.
- Port `ir.py` → `ir.rs` as an enum `Node`, and add `Val`.
- Port `schema.py` → `schema.rs`, keeping every message, code, and path:
  - `IDENTIFIER` regex as a hand-written check
  - `_keys` missing/unknown wording with sorted names
  - the `at` default size from the child's `min_size`
  - `metadata_not_root`
  - the reserved entity NBT keys
  - finite-number checks
  - bool-is-not-int
- Rust tests: port the schema cases from `tests/test_schema_layout.py`, and the
  rotation table from `tests/test_rotation_states.py`.
- Gate: cargo tests pass. Python is untouched.

### Phase 2 — Layout + lowering
- Port `layout.py`:
  - `_component_path` labelling rules (`item[i]`, `child[i]/Name`)
  - split fill distribution (divmod with the remainder going to the first fills)
  - the `split_*`, `repeat_overflow`, `inset_collapsed`, `transform_overflow`,
    and `component_too_small` errors
- Port `lowering.py`:
  - the reversed transform stack
  - `_world_box` corner method
  - owner/provenance logic
  - entity yaw accumulation
  - fill iteration order y, z, x
  - assembly checks
  - sequence numbering
- Lowering hot path: iterate fills directly into a `Vec<BlockWrite>` holding
  `BlockId`s, and rotate the block once per op, not once per cell.
- Rust tests: port the layout/transform cases from `test_schema_layout.py` and
  `test_transform_execution.py`.

### Phase 3 — Execute, support, validators
- Port `execute.py`:
  - phase order STRUCTURE → CARVE → FIXTURE, then sequence
  - per-op error collection, raised together
  - the identical-rewrite allowance in STRUCTURE
  - strict FIXTURE
  - CARVE overwrites
  - atomic apply only after all of an op's writes validate
  - entity root check
- Port `support.py`, keeping the deny lists and suffixes verbatim, the
  pressure-plate exception, terrain/ground-level semantics, and the
  `(y, z, x)` scan order.
- Port `validators.py`:
  - door detection
  - left/right jambs
  - front/back clearance
  - `_is_in_scope`
  - `validator_no_targets`, `invalid_validator_target`
- Expose `is_supporting_block` as a `pub fn`.
- Rust tests: port `test_support.py`, `test_validators.py`, and the overlap and
  atomicity cases from `test_transform_execution.py`.

### Phase 4 — Serialization
- `nbt.rs`: a tag enum and writer:
  - named root with an empty name
  - big-endian
  - List element type id; an empty list uses String type id 8, matching nbtlib `List[String]([])`
  - confirm by diffing against nbtlib output for a sample
- `serialize.rs`: `DATA_VERSION_1_21_7 = 4438`; root keys in this order:
  1. `DataVersion`
  2. `size`
  3. `palette`
  4. `blocks`
  5. `entities`
  
  A block's `nbt` goes on the block entry only, never in the palette. Entity
  `pos` and `blockPos`, plus nbt `Pos` (x+0.5, y, z+0.5) and `Rotation`
  (Float yaw, pitch).
- Gzip: use `flate2` with the **zlib** backend at level 9, mtime 0, and an
  empty filename. Set OS byte 255 and XFL 2 to match CPython's header. Try for
  byte-identical *compressed* output. If that doesn't hold, accept it: parity is
  defined on the decompressed payload, and determinism is checked by building
  twice.
- Meta JSON `{"ground_level", "y_offset"}` and the debug JSON
  (`component-ir`, `resolved`, `operations`, `entities`, `dense`), produced with
  `serde_json` with sorted keys and indent 2. Check them by parsed-JSON
  equality, not bytes; float repr and `ensure_ascii` escapes may differ.
- Rust tests: an NBT round-trip via a small reader in test code.

### Phase 5 — Python integration (first real speedup lands here)
- `stnbt-py`:
  - `finish_build(tree, props, root_size) -> RustBuildResult`, where the
    Python → `Val` conversion is a single recursive pass using `PyDict`/`PyList`
    downcasts
  - `write_outputs(result, nbt_path, debug_dir)`
  - `BuildError` mapping that builds Python `model.Diagnostic`s
- `pipeline.py`: add `STARLARK_TO_NBT_ENGINE=python|rust`. `build_file` and
  `build_source` evaluate with the existing Python runtime, then call either
  Python `_finish_build` or `_core.finish_build`. Keep `evaluate_source`
  returning the raw tree on the Rust path (split `parse_node` out of it).
- **`BuildResult` compatibility.** runner.py reads the attributes listed in
  "Compatibility scope", and those must stay. The tests also read:
  - `result.volume.block_at(...)` (≈116 uses)
  - `.voxels` (len, iteration, `[point].block`)
  - `.bounds`
  - `result.operations`
  - `result.entities`
  - `result.component_ir.props`
  - `result.metadata.ground_level`, `.to_dict()`

  Write a Python `RustBuildResult` adapter whose attributes are lazily
  materialized views. Each one returns the existing `model.Point`, `BlockSpec`,
  and `Voxel` types, built from compact tuples that `_core` returns on demand.
  Only tests pay the conversion cost; the CLI path never touches them.
- Run the full suite under both engines:
  `STARLARK_TO_NBT_ENGINE=rust uv run pytest`. The per-stage unit tests that
  call `execute`/`resolve`/`lower_all` directly still exercise Python code,
  which is fine until Phase 7.
- Gate: all tests pass under both engines, `golden.py --check` passes under the
  Rust engine, and a benchmark is recorded in the log. Then **flip the default
  to rust**.

### Phase 6 — Starlark eval in Rust + native CLI
- Use the `starlark` crate (facebook/starlark-rust, the engine starlark-pyo3
  wraps, so the language semantics match).
- Check which `Globals`/`Dialect` `sl.Globals.standard()` corresponds to and
  match it. Note that starlark-pyo3 uses the `Dialect` default unless one is given.
- Runtime work:
  - Embed the prelude.
  - Port `sign_nbt`, `container_nbt`, and `loot_nbt` into the prelude (use
    `type(x) == "string"` and `fail()` for the container check), or write them
    natively.
  - Write the math natives: `isqrt` (non-negative int check), `round` (half
    away from zero, returns int), `floor`/`ceil` returning int,
    `sqrt`/`sin`/`cos`/`atan2`, and `PI`.
  - Use the entry trampoline `entry(**props)` with the `_ENTRY_NAME` check.
  - Convert the frozen result value to `Val`.
- Port `_Loader` to a Rust `FileLoader`:
  - relative resolution through a dir stack
  - a cache
  - `load_cycle`
  - `load_error` with the confined "module not found" message
  - `loader_root` + allowed `lib`
  - mounts, where a mounted module resolves its own loads from `base_dir`
  - absolute paths rejected when confined

  Keep the original structured error instead of a wrapped string.
- `starlark_error` diagnostics: the message is the rendered starlark error,
  including the traceback. `tests/test_end_to_end.py:336` and
  `tests/test_dungeons.py:280` check the code only.
- `stnbt-cli` (clap) reproduces `cli.py`:
  - `build SOURCE --entry --arg NAME=VALUE... --output --debug-dir`
  - `_arg_value` coercion: true/false → bool, then int, then float, else str
  - exit 1 with the `BuildError` text
  - writes `.meta.json` next to the output
- The shim adds `_core.build_file` and `_core.build_source` (with
  `base_dir`/`loader_root`/`mounts`), and `pipeline.py` routes to them when the
  engine is rust. `container_nbt` and `loot_nbt` stay importable from
  `starlark_runtime` for `tests/test_end_to_end.py:649`.
- Gate: all tests and golden checks pass under the rust engine. The native
  binary passes golden checks too. Add a variant of
  `scripts/rebuild_examples.sh` that uses the binary.

### Phase 7 — Retire the Python internals
- Delete the Python `schema`, `layout`, `lowering`, `execute`, `support`,
  `validators`, and `serialize` internals, along with the
  `starlark_runtime` eval path and the engine switch.
- Port the Python unit tests that construct IR by hand (`test_schema_layout`,
  `test_transform_execution`, `test_rotation_states`, `test_support`, and the
  internal parts of `test_validators`) to Rust tests, if Phases 1–3 haven't
  already covered them. Then delete them.
- What stays in Python:
  - `model.py` (public Python types)
  - a thin `pipeline.py` (`build_file`, `build_source`, `write_build_outputs`,
    `BuildResult` adapter)
  - `cli.py` (or point `[project.scripts]` at a wrapper that calls the Rust CLI main)
  - the end-to-end/library/entities/shapes/runtime-load/dungeon/at/build-source tests
- Update `CLAUDE.md` and `AGENTS.md`: architecture is now Rust crates, commands
  add `cargo test --workspace`, and the pipeline-stage descriptions point at
  `.rs` files. Update `docs/component-catalog.md` only if behaviour changed.

## Files touched (summary)
- New: `Cargo.toml`, `rust-toolchain.toml`, `crates/stnbt-core/**`,
  `crates/stnbt-cli/**`, `crates/stnbt-py/**`, `scripts/golden.py`,
  `tests/golden/manifest.json`
- Modified: `pyproject.toml` (maturin, uv cache-keys),
  `src/starlark_to_nbt/pipeline.py` (engine switch → Rust delegation),
  `src/starlark_to_nbt/starlark_runtime.py` (return the raw tree; later thin),
  `CLAUDE.md`, `AGENTS.md`, `scripts/rebuild_examples.sh`
- Deleted (Phase 7): Python stage modules, as listed above

## Reference: behaviours that must not drift
Coordinates are +X east, +Y up, +Z south. Boxes are half-open.

- STRUCTURE identical rewrite is allowed; a differing rewrite is `block_conflict`
  with `details.existingComponent`.
- Carve-only cells serialize as explicit `minecraft:air`. Untouched cells are
  omitted.
- Rotation changes `facing`, `axis` x↔z, sign `rotation` +4 per quarter turn
  mod 16, and N/S/E/W connection *keys*. It leaves `shape`, `hinge`, and `half`
  alone.
- In support checks, unwritten cells outside the root box, or below
  `ground_level`, count as terrain. Unwritten cells inside the box at or above
  ground level count as air.
- Every diagnostic carries `code`, `component_path`, and region/coordinates. The
  stable codes:
  - `invalid_ir`, `invalid_metadata`, `metadata_not_root`, `invalid_validator`
  - `missing_component_size`, `component_too_small`, `invalid_box`, `missing_root_size`
  - `split_overflow`, `split_underflow`, `split_empty_fill`
  - `inset_collapsed`, `repeat_overflow`, `transform_overflow`
  - `entity_component_overflow`, `entity_root_overflow`
  - `assembly_overflow`, `assembly_duplicate`, `assembly_invalid`
  - `operation_duplicate`, `root_overflow`, `component_overflow`, `block_conflict`
  - `unsupported_block`
  - `validator_no_targets`, `invalid_validator_target`, `door_not_supported`, `doorway_obstructed`
  - `serialize_error`, `starlark_error`, `load_error`, `load_cycle`, `invalid_entry`
- Root size comes from props `width`/`height`/`length` (each at least
  `min_size`), else `min_size`, else `missing_root_size`.

## Verification
- Every phase: `cargo test --workspace` and `uv run pytest` must pass.
- From Phase 5 on, also run `STARLARK_TO_NBT_ENGINE=rust uv run pytest` and
  `uv run python scripts/golden.py --check` (decompressed-NBT sha256 per case,
  plus the expected-failure codes).
- Determinism: build each example twice with the Rust engine or binary and `cmp`
  the `.nbt` files.
- In-game smoke test (manual, once after Phase 5 and once after Phase 6): load
  church and moonspire with a structure block in 1.21.7 and check that signs,
  chests, entities, and rotations look right.
- Performance: time `examples/moonspire_magical_city.star` and `examples/keep.star`
  with the Python CLI and with the native binary, and record the numbers in the log.
  Target: moonspire under 0.3s.

## Notes / deviations log
- (Phase 0) Toolchain pin deferred to Phase 6: rustc 1.85 (asdf-managed) is
  enough until the `starlark` crate arrives. The workspace sets
  `rust-version = "1.85"` + resolver 3 so cargo picks compatible versions.
- (Phase 0) pyo3 0.30.1 with `abi3-py313` (one wheel for 3.13+). maturin
  1.x backend; the editable install drops `src/starlark_to_nbt/_core.abi3.so`
  (gitignored). `uv run` rebuilds via `[tool.uv] cache-keys` (verified).
- (Phase 0) The golden gate also runs inside pytest (`tests/test_golden.py`,
  ~8s): 436 builds + 7 failure cases. Failure cases compare code, path, and
  message (not message for `starlark_error`).
- (Phase 1) Coordinates and all schema ints narrowed to i32: out-of-range
  → `invalid_ir` "expected an integer between -2147483648 and 2147483647".
  Arithmetic past ±2^31 is not guarded (Minecraft worlds are ±3·10^7).
- (Phase 1) Python `Box` is `model::Region` (avoids shadowing `std::boxed::Box`).
  `Transform.source_size` is mandatory (Python allowed `None`; nothing used it).
- (Phase 1) `Val` equality follows Python (`1 == 1.0 == True`, order-free
  dicts). Given the compatibility scope, Phase 2 may intern blocks on exact
  structure and treat `1` vs `1.0` in nbt as different blocks. No corpus
  script depends on that; the golden gate would catch it if one did.
- (Phase 1) `Val::Dict` keys are `String`. starlark-pyo3 JSON-marshals
  results, so non-str keys arrive stringified today. Phase 6's starlark → `Val`
  converter may simply reject non-string keys with a clear diagnostic, unless
  the corpus turns out to need stringification (the golden gate will show it).
- (Phase 1) Small approximations: `rotate_sixteenth` parses with
  `trim().parse::<i128>()` (no `1_0` or non-ASCII digits, unlike Python
  `int()`), and `py_str_repr` uses an approximate `isprintable` table. Both
  only matter for pathological input.
- (Phase 1) `_core.parse_ir(tree, source_file)` → `("ok", jsonable)` or
  `("error", [(code, path, message)])`. The Python → `Val` converter
  (`crates/stnbt-py/src/convert.rs`) raises TypeError on non-str dict keys
  and OverflowError past i64. `Node::to_val` mirrors `pipeline._jsonable`
  (including `Inset` amounts keyed `"Axis.X"`), so Phase 4's
  `component-ir.json` can reuse it.
- (Phase 1) Schema parity is enforced by `tests/test_rust_schema_parity.py`
  (97 tests): identical IR for every example and showcase tree, ~6.2k
  seeded random mutations plus ~1k layout-targeted ones agreeing on the first
  diagnostic, and a hand-written case for every reachable schema message.
  Two messages are unreachable from Rust by design: "object keys must be
  strings" and "props must contain only JSON-compatible values".
- (2026-11-11) The golden corpus now includes all 39 starlark-library
  versions (475 builds + 7 failures). Each library build matched its saved
  `block_count` and `size` in meta.json before being recorded.
  `tests/test_rust_schema_parity.py` also checks every library tree (136
  tests). Library cases are skipped with a notice when the directory is
  absent (override with `STARLARK_LIBRARY_DIR`).
- (record further deviations, benchmark numbers, and gzip-parity outcome here)
